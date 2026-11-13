"""Recover from Git facts; never invent events, reset work or force a push."""
import json

from .collaboration import ObservedRepository
from .core import GroupError, now
from .events import validate_event, validate_event_graph
from . import localstate
from .presentation import safe, summary


def committed_events(r):
    events, blobs = [], {}
    for line in r.output("ls-tree", "-r", "HEAD", "--", ".group/events/").splitlines():
        entry, path = line.split("\t", 1)
        if not path.endswith(".json"):
            continue
        blob = entry.split()[2]
        event = validate_event(json.loads(r.git("cat-file", "blob", blob, binary=True).stdout))
        if path != f".group/events/{event['event_id']}.json" or event["group_id"] != r.config["group_id"]:
            raise GroupError("Invalid locally committed event identity/group")
        events.append(event)
        blobs[event["event_id"]] = blob
    return events, blobs


def remote_tip(r):
    ref = f"refs/remotes/{r.remote}/{r.branch}"
    if r.git("show-ref", "--quiet", "--verify", ref, ok=(0, 1)).returncode:
        return None
    return r.output("rev-parse", ref)


def recover(args):
    r = ObservedRepository(args.repo)
    offline = getattr(args, "offline", False)
    network_error = None
    if not offline:
        try:
            r.fetch()
        except GroupError as exc:
            network_error = str(exc)
            offline = True
    public = r.events()
    local, local_blobs = committed_events(r)
    public_index = {e["event_id"]: e for e in public}
    pending = [e for e in local if e["event_id"] not in public_index]
    union = dict(public_index)
    for event in local:
        if event["event_id"] in public_index and local_blobs[event["event_id"]] != r._event_blobs[event["event_id"]]:
            raise GroupError("Local committed event differs from public immutable bytes; refusing recovery")
        union[event["event_id"]] = event
    validate_event_graph(list(union.values()))
    tip = remote_tip(r)
    ahead = int(r.output("rev-list", "--count", f"{tip}..HEAD")) if tip else None
    behind = int(r.output("rev-list", "--count", f"HEAD..{tip}")) if tip else None
    dirty = r.git("status", "--porcelain").stdout.splitlines()
    uncommitted = list(filter(None, r.git("diff", "--name-only", "-z", "HEAD", "--", ".group/events/").stdout.split("\0")))
    uncommitted += list(filter(None, r.git("ls-files", "--others", "--exclude-standard", "-z", "--", ".group/events/").stdout.split("\0")))
    diagnostics = []
    def cache(name, default):
        try:
            return localstate.load(r, name, default)
        except GroupError as exc:
            diagnostics.append(str(exc))
            return default
    integration = cache("integration.json", None)
    receipt = cache("push-failure.json", None)
    sync = cache("sync.json", {})
    stale = []
    if isinstance(sync, dict) and isinstance(sync.get("seen", []), list) and all(isinstance(e, str) for e in sync.get("seen", [])):
        stale = sorted(set(sync.get("seen", [])) - set(public_index))
    else:
        diagnostics.append("Invalid sync cache; inspect .group/local/sync.json")
    merge = r.git("rev-parse", "--verify", "-q", "MERGE_HEAD", ok=(0, 1))
    source_changes = False
    if r.git("show-ref", "--verify", "--quiet", r.canonical, ok=(0, 1)).returncode == 0:
        base = r.output("merge-base", "HEAD", r.canonical)
        source_changes = bool(r.output("diff", "--name-only", base, "HEAD", "--", ".", ":(exclude).group"))
    announced = any(e["event_type"] == "change_published" and e["branch"] == r.branch and
        r.git("diff", "--quiet", e["commit"], "HEAD", "--", ".", ":(exclude).group", ok=(0, 1)).returncode == 0
        for e in union.values())
    result = {"branch": r.branch, "commit": r.head, "person_id": r.identity(), "remote_commit": tip,
        "freshness": {"mode": "offline" if offline else "fetched", "may_be_stale": offline},
        "network_error": network_error, "unpublished_events": [summary(e) for e in pending],
        "uncommitted_event_files": uncommitted, "local_ahead": ahead, "local_behind": behind,
        "uncommitted_files": dirty, "pending_integration": integration,
        "merge_in_progress": merge.returncode == 0, "last_push_failure": receipt,
        "stale_sync_event_ids": stale, "local_state_diagnostics": diagnostics,
        "source_needs_announcement": source_changes and not announced,
        "actions": [], "recommendations": []}
    if pending:
        result["recommendations"].append("確認後執行 recover --retry-push，重用已提交的事件 ID；不要重新 PUB 產生副本。")
    if source_changes and not announced:
        result["recommendations"].append("目前程式碼沒有對應的 change_published；先 inspect Git history，再以真實 summary 執行 PUB。")
    if integration or merge.returncode == 0:
        result["recommendations"].append("檢查雙方意圖並解決衝突；提交後產生 semantic template，再 integrate-finish。遺失記錄時可 recover --resume-integration C-ID。")
    if dirty or uncommitted:
        result["recommendations"].append("先保護未提交工作與事件；recover 不會自動 commit、reset 或丟棄檔案。")
    if offline:
        result["recommendations"].append("遠端資料可能過期；恢復連線後再 recover，離線不會宣稱已發布。")
    if diagnostics or stale:
        result["recommendations"].append("檢查 .group/local 快取並重新 SYNC；不要改寫公開事件來修正本機狀態。")
    if getattr(args, "resume_integration", None):
        change = r.change(args.resume_integration, public)
        if not r.branch.startswith(f"people/{r.identity()}/"):
            raise GroupError("Resume integration only on your own personal branch")
        if integration is not None or diagnostics:
            raise GroupError("A local integration record or invalid cache already exists; inspect it before resuming")
        if merge.returncode == 0:
            if merge.stdout.strip() != change["commit"]:
                raise GroupError("MERGE_HEAD does not match the requested published change")
            before = r.head
        else:
            parents = r.output("show", "-s", "--format=%P", "HEAD").split()
            if len(parents) < 2 or change["commit"] not in parents[1:]:
                raise GroupError("Cannot safely infer this integration from the current merge commit")
            before = parents[0]
        record = {"change_id": change["change_id"], "event_id": change["event_id"], "commit": change["commit"],
            "before": before, "branch": r.branch, "conflicts": r.output("diff", "--name-only", "--diff-filter=U").splitlines(),
            "recovered_state": True, "conflict_history_complete": False}
        localstate.save(r, "integration.json", record)
        result["pending_integration"] = record
        result["actions"].append("Restored only .group/local/integration.json from verified Git facts; original conflict history may be incomplete.")
    if getattr(args, "retry_push", False):
        if offline:
            raise GroupError("Cannot retry push without a successful fresh fetch; reconnect and rerun recover")
        r.clean()
        if r.branch != r.config["canonical_branch"] and not r.branch.startswith(f"people/{r.identity()}/"):
            raise GroupError("Retry is restricted to canonical or your own personal branch")
        if tip and not r.ancestor(tip):
            raise GroupError("Remote branch diverged or advanced; inspect and integrate deliberately. No force push is allowed.")
        if r.output("log", "--full-history", "-m", "--format=", "--name-only", "--diff-filter=MD", "HEAD", "--", ".group/events/"):
            raise GroupError("Local event history contains modifications/deletions; refusing to push")
        if tip == r.head:
            result["actions"].append("Already synchronized; no push and no event creation were needed.")
        else:
            r.git("push", "-u", r.remote, f"HEAD:refs/heads/{r.branch}")
            r.fetch()
            if remote_tip(r) != r.head:
                raise GroupError("Push could not be confirmed; rerun recover before taking another action")
            result["actions"].append("Pushed the existing HEAD with a normal fast-forward push; no new events were created.")
        result["retry_confirmed"] = True
        result["unpublished_events"] = []
        result["remote_commit"] = r.head
        result["local_ahead"] = result["local_behind"] = 0
        result["last_push_failure_resolved"] = True if receipt else None
        result["recommendations"] = ["已確認遠端 HEAD；既有事件未重建。接著用 inbox／SYNC 查看進度。"]
        if result["source_needs_announcement"]:
            result["recommendations"].append("程式碼已推送，但仍需用真實 summary 執行 PUB 建立發布說明。")
    if not result["recommendations"]:
        result["recommendations"].append("沒有發現需要自動修復的狀況；用 inbox 查看協作待辦。")
    return safe(result)


def render_recovery(result):
    lines = ["恢復檢查（不自動改寫 Git 工作）", f"成員：{result['person_id']}；分支：{result['branch']}",
             f"本機 commit：{result['commit']}", f"已知遠端 commit：{result['remote_commit'] or '尚無紀錄'}",
             f"可能過期：{result['freshness']['may_be_stale']}；未公開事件：{len(result['unpublished_events'])}",
             f"未提交檔案：{len(result['uncommitted_files'])}；進行中 Merge：{result['merge_in_progress']}"]
    lines += [f"- 待推送 {e['event_id']}: {e.get('summary', e.get('text', ''))}" for e in result["unpublished_events"]]
    if result["pending_integration"]:
        lines.append("有未完成的 integration 記錄；請依下方建議恢復。")
    if result["source_needs_announcement"]:
        lines.append("目前程式碼尚無對應的 change_published 說明。")
    lines += ["已執行：" + action for action in result["actions"]]
    lines += ["下一步：" + action for action in result["recommendations"]]
    return "\n".join(lines)
