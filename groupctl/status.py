"""Read-only status projections and concise student-facing rendering."""
from .core import read_json
from .policy import unresolved_blockers


def same_code(r, commit, target="HEAD"):
    return r.git("diff", "--quiet", commit, target, "--", ".", ":(exclude).group/events",
                 ":(exclude).group/final", ok=(0, 1)).returncode == 0


def state(r, events):
    sync_path = r.local / "sync.json"
    seen = set(read_json(sync_path).get("seen", [])) if sync_path.exists() else set()
    counts = r.output("rev-list", "--left-right", "--count", f"HEAD...{r.canonical}").split()
    person, head = r.identity(), r.head
    raw = r.output("status", "--porcelain")
    conflicts = r.output("diff", "--name-only", "--diff-filter=U").splitlines()
    pending = []
    for event in events:
        if event["event_type"] != "change_published":
            continue
        in_current = r.ancestor(event["commit"])
        in_canonical = r.ancestor(event["commit"], r.canonical)
        if not (in_current and in_canonical):
            pending.append({key: event[key] for key in ("change_id", "person_id", "branch", "commit", "summary", "interface_changes")}
                           | {"in_current": in_current, "in_canonical": in_canonical})
    tests = [e for e in events if e["event_type"] == "test_result"]
    exact = next((e for e in reversed(tests) if e["commit"] == head), None)
    relevant = exact or next((e for e in reversed(tests) if same_code(r, e["commit"])), None)
    public_ids = {e["event_id"] for e in events}
    unpublished = [p.stem for p in (r.meta / "events").glob("*.json") if p.stem not in public_ids]
    integration_path = r.local / "integration.json"
    integration = read_json(integration_path) if integration_path.exists() else None
    result = {"person_id": person, "group_id": r.config["group_id"], "branch": r.branch,
        "commit": head, "uncommitted": raw.splitlines(), "canonical_branch": r.config["canonical_branch"],
        "canonical_commit": r.output("rev-parse", r.canonical), "ahead": int(counts[0]), "behind": int(counts[1]),
        "new_events": [e for e in events if e["event_id"] not in seen],
        "published_local_changes": [e for e in events if e["event_type"] == "change_published" and e["person_id"] == person],
        "latest_test": tests[-1] if tests else None, "blockers": unresolved_blockers(events),
        "pending_changes": pending, "conflicts": conflicts, "pending_integration": integration,
        "unpublished_events": unpublished,
        "tests": {"configured": bool(r.config.get("validation_commands")), "latest_for_current_code": relevant,
                  "exact_current_commit": exact is not None, "dirty_work_not_tested": bool(raw)},
        "interface_warnings": [{"change_id": e["change_id"], "changes": e["interface_changes"]}
                               for e in pending if e["interface_changes"]]}
    result["recommended_next_action"], result["next_action_reason"] = recommend(result)
    return result


def recommend(s):
    if s["conflicts"]:
        return "Resolve conflicts, commit the deliberate resolution, then integrate-finish.", "merge_conflict"
    if s["uncommitted"]:
        return "Protect unfinished work; inspect the diff and complete it before PUB or SYNC --update.", "dirty_worktree"
    if s["pending_integration"]:
        return "Inspect semantic compatibility and run integrate-finish with the exact reviewed commit.", "integration_pending"
    if s["unpublished_events"]:
        return "Retry git push on the current branch; locally committed events are not published yet.", "push_pending"
    if s["blockers"]:
        return "Resolve the recorded blockers with evidence before preparing FINAL.", "blocker"
    if not s["tests"]["configured"]:
        return "Configure real validation_commands; missing tests cannot be counted as pass.", "missing_tests"
    evidence = s["tests"]["latest_for_current_code"]
    if evidence and evidence["automated_result"] != "pass":
        return "Investigate failing or unavailable validation, then run TEST again.", "validation_failed"
    if s["behind"] or s["new_events"]:
        return "Run SYNC, inspect relevant events and update canonical state when safe.", "sync_needed"
    if any(not change["in_current"] for change in s["pending_changes"]):
        return "Inspect a teammate change, then use REV or INT with its change ID.", "pending_change"
    if evidence is None:
        return "Run TEST to publish evidence for the current code; old results cover other versions.", "untested_code"
    if s["pending_changes"]:
        return "Review and promote verified contributions to canonical state using normal Git merge.", "canonical_pending"
    return "Continue agreed work; if the group is ready, prepare FINAL for human review.", "up_to_date"


def render_status(s):
    evidence = s["tests"]["latest_for_current_code"]
    test_state = evidence["automated_result"] if evidence else "尚無目前程式碼的測試證據"
    lines = [f"小組 {s['group_id']} / 成員 {s['person_id']}", f"目前分支：{s['branch']} ({s['commit'][:12]})",
        f"正式分支：{s['canonical_branch']} ({s['canonical_commit'][:12]})；ahead {s['ahead']} / behind {s['behind']}",
        f"未提交：{len(s['uncommitted'])}；衝突：{len(s['conflicts'])}；新事件：{len(s['new_events'])}",
        f"待整合工作：{len(s['pending_changes'])}；Blockers：{len(s['blockers'])}", f"Tests：{test_state}"]
    lines += [f"  {line}" for line in s["uncommitted"]]
    lines += [f"  {e['change_id']} ({e['person_id']}): {e['summary']} [current={e['in_current']}, canonical={e['in_canonical']}]"
              for e in s["pending_changes"]]
    lines += [f"  Blocker {e['event_id']}: {e['summary']} → {e['requested_action']}" for e in s["blockers"]]
    if evidence:
        lines.append(f"受測 commit：{evidence['commit']}；與 HEAD 完全相同：{s['tests']['exact_current_commit']}")
    lines.append("下一步：" + s["recommended_next_action"])
    return "\n".join(lines)
