from __future__ import annotations

import json
import re
import uuid
from pathlib import Path

from .core import GroupError, Repository, identifier, now, read_json, write_json
from .validation import validate_commands


def repo(args):
    return Repository(args.repo)


def init(args):
    r = Repository(args.repo, configured=False)
    if r.meta.exists():
        raise GroupError(".group already exists; refusing to overwrite group state", hint="先 doctor／recover；既有成員用 join --resume，不要重做 init。")
    identifier(args.group)
    identifier(args.person)
    r.git("check-ref-format", "--branch", args.canonical)
    assignment = Path(args.assignment).read_text(encoding="utf-8-sig")
    from .onboarding import CHECK_PRESETS, prepare_init, publish_init
    preset = getattr(args, "checks", None)
    if preset and args.checks_file:
        raise GroupError("Choose --checks or --checks-file, not both", code=2)
    checks = CHECK_PRESETS[preset] if preset else read_json(args.checks_file) if args.checks_file else []
    validate_commands(checks)
    prepare_init(r, args, assignment, checks)
    config = {"protocol_version": "0.1", "group_id": args.group,
              "canonical_branch": args.canonical, "assignment_file": ".group/assignment/assignment.md",
              "remote": "origin", "validation_commands": checks}
    if getattr(args, "simulation", False):
        config["simulation"] = True
    write_json(r.meta / "group.json", config)
    (r.meta / "assignment").mkdir()
    (r.meta / "assignment/assignment.md").write_text(assignment, encoding="utf-8")
    (r.meta / "events").mkdir()
    (r.meta / "final").mkdir()
    r.local.mkdir()
    (r.local / ".gitkeep").touch()
    (r.local / ".gitignore").write_text("*\n!.gitkeep\n!.gitignore\n", encoding="utf-8")
    write_json(r.local / "identity.json", {"person_id": args.person})
    write_json(r.meta / "members" / f"{args.person}.json", {
        "protocol_version": "0.1", "person_id": args.person, "display_name": args.name or args.person, "joined_at": now()})
    if getattr(args, "publish", False):
        return publish_init(args)
    return {"group_id": args.group, "person_id": args.person,
            "next": "Commit .group setup, push canonical branch, then create your personal branch. "
                    f"Commands: git add .group; git commit; git push -u origin {args.canonical}; "
                    f"git switch -c people/{args.person}/work"}


def join(args):
    r = repo(args)
    r.clean()
    identifier(args.person)
    identifier(args.topic)
    r.fetch()
    from .onboarding import exists, member_at, member_branches, resume_join
    if getattr(args, "resume", False):
        return resume_join(r, args)
    branch = f"people/{args.person}/{args.topic}"
    if (r.meta / "members" / f"{args.person}.json").exists() or member_at(r, r.canonical, args.person) or exists(r, f"refs/remotes/{r.remote}/{branch}") or member_branches(r, args.person):
        raise GroupError("Member or personal branch exists; no new registration was created.",
                         hint=f"join --resume --person {args.person} --topic {args.topic}")
    r.git("switch", "-c", branch, r.canonical)
    member = f".group/members/{args.person}.json"
    write_json(r.root / member, {"protocol_version": "0.1", "person_id": args.person,
                               "display_name": args.name or args.person, "joined_at": now()})
    write_json(r.local / "identity.json", {"person_id": args.person})
    r.git("add", "--", member)
    r.git("commit", "-m", f"group: register {args.person}", "--", member)
    try:
        r.git("push", "-u", r.remote, f"HEAD:refs/heads/{branch}")
    except GroupError as exc:
        from .localstate import push_failure
        push_failure(r, "join_push")
        raise GroupError("成員註冊已提交，但尚未確認發布；不要重新 join。",
                         hint="確認網路／權限後 recover --retry-push；不會重複建立成員紀錄。") from exc
    return {"person_id": args.person, "branch": branch, "published": True, "next": "context --format markdown；inbox。"}


def identity(args):
    r = repo(args)
    identifier(args.person)
    member = read_json(r.meta / "members" / f"{args.person}.json")
    if member.get("person_id") != args.person:
        raise GroupError("Unknown person")
    write_json(r.local / "identity.json", {"person_id": args.person})
    return {"person_id": r.identity()}


from .status import state
from .policy import unresolved_blockers, final_concerns


def status(args):
    from .collaboration import observed, conflict_warnings
    from .presentation import safe
    r, events, freshness = observed(args)
    result = state(r, events)
    result["freshness"] = freshness
    result["potential_conflict_warnings"] = conflict_warnings(r, events, result)
    return safe(result)


def sync(args):
    r = repo(args)
    before = {"branch": r.branch, "commit": r.head, "uncommitted": r.output("status", "--porcelain")}
    r.fetch()
    events = r.events()
    result = state(r, events)
    if args.update:
        r.clean()
        merged = r.git("merge", "--no-edit", r.canonical, ok=(0, 1))
        if merged.returncode:
            result["conflicts"] = r.output("diff", "--name-only", "--diff-filter=U").splitlines()
            result["needs_human"] = True
            result["next"] = "Resolve the canonical merge deliberately, or git merge --abort. Local work was not discarded."
            return result
        result["incorporated_canonical"] = r.head != before["commit"]
        if r.head != before["commit"]:
            result["validation"] = r.check_commit(r.head)
    else:
        result["incorporated_canonical"] = False
    write_json(r.local / "sync.json", {"seen": [e["event_id"] for e in events], "at": now()})
    result["before"] = before
    result["current_commit"] = r.head
    return result


def events_command(args):
    r = repo(args)
    r.fetch()
    return {"events": r.events()}


def event_command(args):
    r = repo(args)
    r.clean()
    fields = read_json(args.file)
    if not isinstance(fields, dict):
        raise GroupError("Event payload must be a JSON object")
    if args.type in {"change_published", "review", "test_result", "integration_result", "final_candidate", "final_result"}:
        raise GroupError("Use the dedicated command for changes, reviews, tests, integrations and finalization")
    event = r.event(args.type, fields, args.related)
    return {"published": True, "event": r.publish(event)}


def check_source_files(r, paths):
    for name in paths:
        path = r.path(name)
        if not path.is_file():
            continue
        if path.name.lower() in {".env", "id_rsa", "id_ed25519", "credentials.json"} or path.suffix.lower() in {".pem", ".key"}:
            raise GroupError(f"Review possible secret file before publication: {name}")
        if path.stat().st_size > 5_000_000:
            raise GroupError(f"Review large/generated file before publication: {name}")
        text = path.read_text(encoding="utf-8", errors="ignore")
        if re.search(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|gh[pousr]_[A-Za-z0-9]{30,}|AKIA[A-Z0-9]{16}", text):
            raise GroupError(f"Possible secret found in {name}; inspect locally")


def pub(args):
    if getattr(args, "dry_run", False):
        from .preview import pub as preview_pub
        return preview_pub(args)
    r = repo(args)
    r.personal()
    r.fetch()
    if r.git("diff", "--name-only", "--diff-filter=U").stdout.strip():
        raise GroupError("Resolve conflicts before publication")
    paths = r.git("diff", "--name-only", "-z", "HEAD").stdout.split("\0")
    paths += r.git("ls-files", "--others", "--exclude-standard", "-z").stdout.split("\0")
    paths = sorted(set(p for p in paths if p))
    if any(p.startswith(".group/") for p in paths):
        raise GroupError("Commit deliberate collaboration/configuration changes separately before PUB")
    base = r.output("merge-base", "HEAD", r.canonical)
    existing = r.git("diff", "--name-only", "-z", base, "HEAD").stdout.split("\0")
    source_paths = sorted(set(paths + [p for p in existing if p and not p.startswith(".group/")]))
    if not source_paths:
        raise GroupError("No contribution relative to canonical state")
    check_source_files(r, source_paths)
    snapshot = r.snapshot(paths) if paths else r.head
    original = {name: r.path(name).read_bytes() if r.path(name).is_file() else None for name in paths}
    checks = r.check_commit(snapshot)
    if checks["automated_result"] != "pass" and not (checks["automated_result"] == "not_available" and args.unverified_reason):
        raise GroupError("PUB requires passing checks (or an explicit reason when no automated checks exist): " + json.dumps(checks))
    # Reinspect test-created files before staging; don't silently add generated outputs.
    after = set(filter(None, r.git("diff", "--name-only", "-z", "HEAD").stdout.split("\0")))
    after.update(filter(None, r.git("ls-files", "--others", "--exclude-standard", "-z").stdout.split("\0")))
    if after != set(paths):
        raise GroupError("Validation changed repository files; inspect these before PUB")
    if any((r.path(name).read_bytes() if r.path(name).is_file() else None) != content
           for name, content in original.items()):
        raise GroupError("Working files changed during validation. Inspect and retry PUB.")
    if paths:
        r.git("add", "--", *paths)
        r.git("commit", "-m", args.summary, "--", *paths)
    commit = r.head
    r.clean()
    try:
        r.git("push", "-u", r.remote, f"HEAD:refs/heads/{r.branch}")
    except GroupError:
        from .localstate import push_failure
        push_failure(r, "source_push")
        raise
    change_id = f"C-{r.identity()}-{uuid.uuid4().hex[:10]}"
    event = r.event("change_published", {"change_id": change_id, "branch": r.branch, "commit": commit,
        "summary": args.summary, "base_commit": base, "files_changed": source_paths, "interface_changes": args.interface_change,
        "tests_run": [json.dumps(x["argv"]) for x in checks["results"]],
        "known_issues": args.known_issue + ([args.unverified_reason] if args.unverified_reason else []),
        "proposed_for_integration": not args.draft, "validation": checks})
    return {"published": True, "change_id": change_id, "event": r.publish(event)}


def inspect(args):
    r = repo(args)
    r.fetch()
    change = r.change(args.change)
    recorded = change.get("base_commit")
    warning = None
    if recorded is not None:
        if not isinstance(recorded, str) or not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", recorded):
            raise GroupError("Published base_commit must be an exact commit hash")
        if recorded == change["commit"] or not r.ancestor(recorded, change["commit"]):
            raise GroupError("Published base_commit must precede the published change")
        base, source = recorded, "published_base"
    else:
        base = r.output("merge-base", change["commit"], r.canonical)
        source = "legacy_merge_base"
        if base == change["commit"]:
            parents = r.output("rev-list", "--parents", "-n", "1", change["commit"]).split()[1:]
            base = parents[0] if parents else None
            source = "legacy_first_parent" if parents else "legacy_root"
            warning = "Legacy event has no recorded base_commit; this diff may cover only its last commit. Inspect Git history for the full contribution."
    diff = (r.git("diff", base, change["commit"], "--", ".", ":(exclude).group").stdout if base else
            r.git("show", "--format=", "--root", change["commit"], "--", ".", ":(exclude).group").stdout)
    return {"event": change, "base": base, "diff_base_source": source, "warning": warning,
            "diff": diff,
            "already_incorporated": r.ancestor(change["commit"])}


def review(args):
    from .communication import assessment_input
    assessment = assessment_input(args, "review")
    r = repo(args)
    r.clean()
    r.fetch()
    change = r.change(args.change)
    if not isinstance(assessment, dict):
        raise GroupError("Review assessment must be a JSON object")
    if assessment.get("inspected_commit") != change["commit"] or assessment.get("diff_inspected") is not True:
        raise GroupError("Review must identify inspected_commit and diff_inspected=true after actual inspection")
    event = r.event("review", {"change_id": args.change, "verdict": assessment.get("verdict"),
        "summary": assessment.get("summary"), "issues": assessment.get("issues"),
        "tests_run": assessment.get("tests_run"), "inspected_commit": change["commit"],
        "evidence": assessment.get("evidence", [])}, [change["event_id"]])
    return {"published": True, "event": r.publish(event)}


def test(args):
    r = repo(args)
    r.clean()
    r.fetch()
    scope = args.scope
    if scope in ("current", "current_branch"):
        commit = r.head
    elif scope in ("main", "canonical"):
        commit = r.output("rev-parse", r.canonical)
    else:
        commit = r.change(scope)["commit"]
    checks = r.check_commit(commit)
    r.clean()
    event = r.test_event(scope, commit, checks, args.human_check)
    return {"published": True, "event": r.publish(event)}


def integrate(args):
    if getattr(args, "preview", False):
        from .preview import integrate as preview_integration
        return preview_integration(args)
    r = repo(args)
    r.personal()
    r.clean()
    r.fetch()
    change = r.change(args.change)
    path = r.local / "integration.json"
    if path.exists():
        raise GroupError("An integration is already pending; finish or abort it first")
    base = r.output("merge-base", "HEAD", change["commit"])
    diff = r.git("diff", base, change["commit"], "--", ".", ":(exclude).group").stdout
    write_json(path, {"change_id": args.change, "event_id": change["event_id"], "commit": change["commit"],
                      "before": r.head, "branch": r.branch, "conflicts": []})
    result = r.git("merge", "--no-edit", "--no-ff", change["commit"], ok=(0, 1, 128))
    conflicts = r.output("diff", "--name-only", "--diff-filter=U").splitlines()
    saved = read_json(path)
    saved["conflicts"] = conflicts
    write_json(path, saved)
    if result.returncode and not conflicts:
        path.unlink()
        raise GroupError("Git did not integrate the change: " + result.stderr)
    return {"change": change, "diff": diff, "git_merged": not conflicts, "conflicts": conflicts,
            "accepted": False, "next": "Inspect both intents; resolve conflicts and commit if needed. "
                    "Then supply semantic assessment to integrate-finish. Git merge alone is insufficient."}


def integrate_finish(args):
    from .communication import assessment_input
    assessment = assessment_input(args, "semantic")
    r = repo(args)
    r.clean()
    saved = read_json(r.local / "integration.json")
    if saved["branch"] != r.branch:
        raise GroupError("Return to the branch where integration began")
    if not r.ancestor(saved["commit"]):
        raise GroupError("Referenced commit is not actually incorporated")
    markers = r.git("grep", "-n", "-E", "^(<<<<<<< |=======$|>>>>>>> )", "HEAD", "--", ".",
                    ":(exclude).group", ok=(0, 1))
    if markers.returncode == 0:
        raise GroupError("Possible conflict markers remain: " + markers.stdout)
    if not isinstance(assessment, dict):
        raise GroupError("Semantic assessment must be a JSON object")
    if assessment.get("reviewed_commit") != r.head or assessment.get("semantic_review") not in {"pass", "fail"} or not assessment.get("summary"):
        raise GroupError("Assessment needs exact reviewed_commit, semantic_review=pass/fail and summary")
    checks = r.check_commit(r.head)
    r.clean()
    result = "success" if checks["automated_result"] == "pass" and assessment["semantic_review"] == "pass" else "failed"
    if checks["automated_result"] in {"not_available", "partial"} and assessment["semantic_review"] == "pass":
        result = "needs_human"
    event = r.event("integration_result", {"change_id": saved["change_id"], "target_branch": r.branch,
        "result": result, "merge_commit": r.head, "conflicts": saved["conflicts"],
        "conflict_resolution_summary": assessment.get("conflict_resolution_summary", "No textual conflicts"),
        "verification": {"build": assessment.get("build", "not_applicable"),
                         "tests": checks["automated_result"] if checks["automated_result"] in {"pass", "fail"} else "not_available",
                         "semantic_review": assessment["semantic_review"]},
        "summary": assessment["summary"], "validation": checks}, [saved["event_id"]])
    if saved.get("recovered_state"):
        event["recovery"] = {"reconstructed": True, "conflict_history_complete": False}
    if event["verification"]["build"] == "fail":
        event["result"] = "failed"
    elif event["verification"]["build"] == "not_available" and event["result"] == "success":
        event["result"] = "needs_human"
    published = r.publish(event)
    (r.local / "integration.json").unlink()
    return {"published": True, "event": published}


def integrate_abort(args):
    r = repo(args)
    saved_path = r.local / "integration.json"
    saved = read_json(saved_path)
    if r.branch != saved["branch"]:
        raise GroupError("Return to the original integration branch")
    if r.git("rev-parse", "--verify", "-q", "MERGE_HEAD", ok=(0, 1)).returncode == 0:
        r.git("merge", "--abort")
    elif r.head != saved["before"]:
        raise GroupError("Merge is already committed. Revert deliberately; abort will not reset your history.")
    saved_path.unlink()
    return {"aborted": True, "commit": r.head}


from .finalization import final_prepare, final_publish
