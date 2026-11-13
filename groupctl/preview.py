"""Strictly read-only previews: no fetch, worktree, index, commit or object writes."""
from .collaboration import ObservedRepository
from .core import GroupError
from .presentation import safe, safe_commands


def changed(r, *revisions):
    return set(filter(None, r.git("diff", "--name-only", "-z", *revisions).stdout.split("\0")))


def working_files(r):
    return changed(r, "HEAD") | set(filter(None, r.git("ls-files", "--others", "--exclude-standard", "-z").stdout.split("\0")))


def common(r):
    return {"preview": True, "branch": r.branch, "current_commit": r.head,
            "freshness": {"mode": "cached_preview", "may_be_stale": True},
            "tests_to_execute": safe_commands(r.config.get("validation_commands", [])),
            "tests_executed": False, "actions_performed": [],
            "warnings": ["只讀預覽使用已知 Git refs；資料可能過期。需要更新時先 SYNC。",
                         "尚未執行測試、審查、Commit、Merge 或 Push。"]}


def pub(args):
    from .commands import check_source_files
    r = ObservedRepository(args.repo)
    result = common(r)
    problems = []
    if not r.branch.startswith(f"people/{r.identity()}/"):
        problems.append("PUB 必須在自己的個人分支執行。")
    local = working_files(r)
    base = r.output("merge-base", "HEAD", r.canonical)
    published = changed(r, base, "HEAD")
    source = sorted(p for p in (local | published) if not p.startswith(".group/"))
    if any(p.startswith(".group/") for p in local):
        problems.append("先檢查並分別提交 .group 設定或協作紀錄變更。")
    if r.output("diff", "--name-only", "--diff-filter=U"):
        problems.append("仍有未解決的 Git conflicts。")
    if not source:
        problems.append("沒有相對於 canonical 的程式貢獻。")
    try:
        check_source_files(r, source)
    except GroupError as exc:
        problems.append(str(exc))
    if not result["tests_to_execute"]:
        problems.append("沒有設定驗證命令；實際 PUB 需要明確的 unverified reason。")
    result.update({"operation": "pub", "target_commit": r.head, "base_commit": base,
        "files_to_commit": sorted(local), "files_to_publish": source,
        "would_publish": {"event_type": "change_published", "summary": getattr(args, "summary", None),
                          "branch": r.branch, "change_id": "generated_only_on_execution",
                          "source_commit": "created_after_validation" if local else r.head},
        "can_execute_without_preparation": not problems, "safety_issues": problems})
    return safe(result)


def integrate(args):
    r = ObservedRepository(args.repo)
    result = common(r)
    events = r.events()
    change = r.change(args.change, events)
    base = r.output("merge-base", "HEAD", change["commit"])
    incoming, ours = changed(r, base, change["commit"]), changed(r, base, "HEAD")
    local = working_files(r)
    overlap = sorted(incoming & (ours | local))
    if local:
        result["warnings"].append("有未提交修改；實際 integrate 會拒絕，請先保護工作。")
    if overlap:
        result["warnings"].append("重疊檔案只是潛在風險，不代表已證實會發生 Git conflict。")
    if ".group/group.json" in incoming:
        result["warnings"].append("Incoming change 修改了驗證設定；實際命令需在審查後確認。")
    result.update({"operation": "integrate", "change_id": args.change, "target_commit": change["commit"],
        "incoming_files": sorted(incoming), "local_modified_files": sorted(local), "potential_conflict_files": overlap,
        "conflict_assessment": "file_overlap_risk_only_not_a_git_merge_result", "interface_changes": change["interface_changes"],
        "already_incorporated": r.ancestor(change["commit"]),
        "can_execute_without_preparation": not local and r.branch.startswith(f"people/{r.identity()}/"),
        "would_publish": {"event_type": "integration_result", "after": "explicit semantic assessment and automated verification"}})
    return safe(result)
