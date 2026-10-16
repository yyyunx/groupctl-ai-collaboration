from __future__ import annotations

import hashlib
import json
import re
import sys
import tempfile
import uuid
from pathlib import Path

from .core import GroupError, Repository, identifier, now, read_json, write_json


def repo(args):
    return Repository(args.repo)


def init(args):
    r = Repository(args.repo, configured=False)
    if r.meta.exists():
        raise GroupError(".group already exists; refusing to overwrite group state")
    identifier(args.group)
    identifier(args.person)
    r.git("check-ref-format", "--branch", args.canonical)
    assignment = Path(args.assignment).read_text(encoding="utf-8-sig")
    checks = read_json(args.checks_file) if args.checks_file else []
    if not isinstance(checks, list) or not all(isinstance(c, list) and c and
            all(isinstance(v, str) and v for v in c) for c in checks):
        raise GroupError("Checks file must contain a list of command argument arrays")
    config = {"protocol_version": "0.1", "group_id": args.group,
              "canonical_branch": args.canonical, "assignment_file": ".group/assignment/assignment.md",
              "remote": "origin", "validation_commands": checks}
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
        "protocol_version": "0.1", "person_id": args.person, "display_name": args.name, "joined_at": now()})
    return {"group_id": args.group, "person_id": args.person,
            "next": "Commit .group setup, push canonical branch, then create your personal branch. "
                    "Commands: git add .group; git commit; git push -u origin main; "
                    f"git switch -c people/{args.person}/work"}


def join(args):
    r = repo(args)
    r.clean()
    identifier(args.person)
    identifier(args.topic)
    r.fetch()
    branch = f"people/{args.person}/{args.topic}"
    if (r.meta / "members" / f"{args.person}.json").exists():
        raise GroupError("Member exists. Use identity to select an existing recognized person.")
    r.git("switch", "-c", branch, r.canonical)
    member = f".group/members/{args.person}.json"
    write_json(r.root / member, {"protocol_version": "0.1", "person_id": args.person,
                               "display_name": args.name, "joined_at": now()})
    write_json(r.local / "identity.json", {"person_id": args.person})
    r.git("add", "--", member)
    r.git("commit", "-m", f"group: register {args.person}", "--", member)
    r.git("push", "-u", r.remote, f"HEAD:refs/heads/{branch}")
    return {"person_id": args.person, "branch": branch, "published": True}


def identity(args):
    r = repo(args)
    identifier(args.person)
    member = read_json(r.meta / "members" / f"{args.person}.json")
    if member.get("person_id") != args.person:
        raise GroupError("Unknown person")
    write_json(r.local / "identity.json", {"person_id": args.person})
    return {"person_id": r.identity()}


def state(r, events):
    sync_path = r.local / "sync.json"
    seen = set(read_json(sync_path).get("seen", [])) if sync_path.exists() else set()
    counts = r.output("rev-list", "--left-right", "--count", f"HEAD...{r.canonical}").split()
    return {"person_id": r.identity(), "group_id": r.config["group_id"], "branch": r.branch,
            "commit": r.head, "uncommitted": r.output("status", "--porcelain").splitlines(),
            "canonical_branch": r.config["canonical_branch"], "canonical_commit": r.output("rev-parse", r.canonical),
            "ahead": int(counts[0]), "behind": int(counts[1]),
            "new_events": [e for e in events if e["event_id"] not in seen],
            "published_local_changes": [e for e in events if e["event_type"] == "change_published"
                                        and e["person_id"] == r.identity()],
            "latest_test": next((e for e in reversed(events) if e["event_type"] == "test_result"), None),
            "blockers": unresolved_blockers(events),
            "recommended_next_action": "Inspect relevant new events and actual diffs before integrating."}


def unresolved_blockers(events):
    resolved = {event_id for e in events for event_id in e.get("resolves_events", [])}
    return [e for e in events if e["event_type"] == "blocker" and e["event_id"] not in resolved]


def final_concerns(r, events, commit):
    incorporated = {e["change_id"] for e in events if e["event_type"] == "change_published"
                    and r.ancestor(e["commit"], commit)}
    resolved = {event_id for e in events for event_id in e.get("resolves_events", [])}
    latest_reviews, latest_integrations = {}, {}
    for event in events:
        if event.get("change_id") not in incorporated:
            continue
        if event["event_type"] == "review":
            latest_reviews[event["change_id"]] = event
        if event["event_type"] == "integration_result" and r.ancestor(event["merge_commit"], commit):
            latest_integrations[event["change_id"]] = event
    concerns = [e for e in latest_reviews.values() if e["verdict"] != "accept"]
    concerns += [e for e in latest_integrations.values() if e["result"] != "success"]
    return [e["event_id"] for e in concerns if e["event_id"] not in resolved]


def status(args):
    r = repo(args)
    r.fetch()
    return state(r, r.events())


def sync(args):
    r = repo(args)
    before = {"branch": r.branch, "commit": r.head, "uncommitted": r.output("status", "--porcelain")}
    r.fetch()
    events = r.events()
    result = state(r, events)
    if args.update:
        r.clean()
        r.git("merge", "--no-edit", r.canonical)
        result["incorporated_canonical"] = r.head != before["commit"]
        if r.head != before["commit"]:
            result["validation"] = r.checks()
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
    checks = r.checks()
    if checks["automated_result"] != "pass" and not (checks["automated_result"] == "not_available" and args.unverified_reason):
        raise GroupError("PUB requires passing checks (or an explicit reason when no automated checks exist): " + json.dumps(checks))
    # Reinspect test-created files before staging; don't silently add generated outputs.
    after = set(filter(None, r.git("diff", "--name-only", "-z", "HEAD").stdout.split("\0")))
    after.update(filter(None, r.git("ls-files", "--others", "--exclude-standard", "-z").stdout.split("\0")))
    if after != set(paths):
        raise GroupError("Validation changed repository files; inspect these before PUB")
    if paths:
        r.git("add", "--", *paths)
        r.git("commit", "-m", args.summary, "--", *paths)
    commit = r.head
    r.clean()
    r.git("push", "-u", r.remote, f"HEAD:refs/heads/{r.branch}")
    change_id = f"C-{r.identity()}-{uuid.uuid4().hex[:10]}"
    event = r.event("change_published", {"change_id": change_id, "branch": r.branch, "commit": commit,
        "summary": args.summary, "files_changed": source_paths, "interface_changes": args.interface_change,
        "tests_run": [json.dumps(x["argv"]) for x in checks["results"]],
        "known_issues": args.known_issue + ([args.unverified_reason] if args.unverified_reason else []),
        "proposed_for_integration": not args.draft, "validation": checks})
    return {"published": True, "change_id": change_id, "event": r.publish(event)}


def inspect(args):
    r = repo(args)
    r.fetch()
    change = r.change(args.change)
    base = r.output("merge-base", change["commit"], r.canonical)
    return {"event": change, "base": base,
            "diff": r.git("diff", base, change["commit"], "--", ".", ":(exclude).group").stdout,
            "already_incorporated": r.ancestor(change["commit"])}


def review(args):
    r = repo(args)
    r.clean()
    r.fetch()
    change = r.change(args.change)
    assessment = read_json(args.file)
    if assessment.get("inspected_commit") != change["commit"] or not assessment.get("diff_inspected"):
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
    if commit == r.head:
        checks = r.checks()
        r.clean()
    else:
        # Use a disposable worktree; never switch/discard the student's current work.
        with tempfile.TemporaryDirectory(prefix="groupctl-test-") as directory:
            target = Path(directory).resolve() / "checkout"
            r.git("worktree", "add", "--detach", str(target), commit)
            try:
                checks = Repository(target).checks()
                Repository(target).clean()
            finally:
                if target.parent == Path(directory).resolve():
                    r.git("worktree", "remove", "--force", str(target))
    event = r.test_event(scope, commit, checks, args.human_check)
    return {"published": True, "event": r.publish(event)}


def integrate(args):
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
    assessment = read_json(args.file)
    if assessment.get("reviewed_commit") != r.head or assessment.get("semantic_review") not in {"pass", "fail"} or not assessment.get("summary"):
        raise GroupError("Assessment needs exact reviewed_commit, semantic_review=pass/fail and summary")
    checks = r.checks()
    r.clean()
    result = "success" if checks["automated_result"] == "pass" and assessment["semantic_review"] == "pass" else "failed"
    if checks["automated_result"] in {"not_available", "partial"}:
        result = "needs_human"
    event = r.event("integration_result", {"change_id": saved["change_id"], "target_branch": r.branch,
        "result": result, "merge_commit": r.head, "conflicts": saved["conflicts"],
        "conflict_resolution_summary": assessment.get("conflict_resolution_summary", "No textual conflicts"),
        "verification": {"build": assessment.get("build", "not_applicable"),
                         "tests": checks["automated_result"] if checks["automated_result"] in {"pass", "fail"} else "not_available",
                         "semantic_review": assessment["semantic_review"]},
        "summary": assessment["summary"], "validation": checks}, [saved["event_id"]])
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


def canonical_ready(r):
    r.clean()
    r.fetch()
    if r.branch != r.config["canonical_branch"] or r.head != r.output("rev-parse", r.canonical):
        raise GroupError("FINAL must run on a clean, up-to-date canonical branch")
    r.identity()


def final_prepare(args):
    r = repo(args)
    canonical_ready(r)
    commit = r.head
    events = r.events()
    pending = [e for e in events if e["event_type"] == "change_published" and
               not r.ancestor(e["commit"], commit)]
    dispositions = read_json(args.dispositions) if args.dispositions else {}
    if not isinstance(dispositions, dict):
        raise GroupError("Dispositions must map change IDs to explicit rejection/obsolete explanations")
    unknown = [e["change_id"] for e in pending if not isinstance(dispositions.get(e["change_id"]), str)
               or not dispositions[e["change_id"]].strip()]
    if unknown:
        raise GroupError("Unincorporated changes need integration or explicit disposition: " + ", ".join(unknown))
    unresolved_reviews = final_concerns(r, events, commit)
    if unresolved_reviews:
        raise GroupError("Incorporated changes have unresolved review concerns. Address and re-review: "
                         + ", ".join(unresolved_reviews))
    blockers = unresolved_blockers(events)
    if blockers:
        raise GroupError("Resolve and record blockers before finalization: " + ", ".join(e["event_id"] for e in blockers))
    if args.human_check and not args.human_evidence:
        raise GroupError("Provide concrete human-check results using --human-evidence")
    checks = r.checks()
    r.clean()
    if checks["automated_result"] != "pass":
        # Failed final validation is shared evidence, never a successful final result.
        event = r.test_event("canonical_final", commit, checks, args.human_check)
        r.publish(event)
        raise GroupError("Final checks did not pass. Test evidence published; no final result created.")
    test_event = r.publish(r.test_event("canonical_final", commit, checks))
    lines = ["# Group Final Report", "", "## Assignment", r.path(r.config["assignment_file"]).read_text(encoding="utf-8"),
             "", "## Result", args.result, "", "## Canonical Commit", commit,
             "", "## Important Changes"]
    lines += [f"- {e['change_id']}: {e['summary']} ({e['person_id']})" for e in events
              if e["event_type"] == "change_published" and r.ancestor(e["commit"], commit)]
    lines += ["", "## Validation", f"Automated checks passed. Evidence: {test_event['event_id']}."]
    lines += ["- " + json.dumps(result["argv"], ensure_ascii=False) for result in checks["results"]]
    lines += [f"- Review {e['event_id']}: {e['verdict']} — {e['summary']}" for e in events if e["event_type"] == "review"]
    lines += ["- Human evidence: " + evidence for evidence in args.human_evidence]
    lines += ["", "## Known Limitations", *(args.limitation or ["None reported."]),
              "", "## Unincorporated Changes", *(f"- {e['change_id']}: {dispositions[e['change_id']]}" for e in pending),
              "", "## Contributors"]
    people = {e["person_id"] for e in events if e["event_type"] == "change_published" and r.ancestor(e["commit"], commit)}
    lines += [f"- {person}" for person in sorted(people)]
    text = "\n".join(lines) + "\n"
    candidate = r.meta / "final/candidate.md"
    candidate.parent.mkdir(exist_ok=True)
    candidate.write_text(text, encoding="utf-8")
    event = r.event("final_candidate", {"canonical_commit": commit,
        "candidate_report_path": ".group/final/candidate.md", "test_evidence": [test_event["event_id"]],
        "known_issues": args.limitation, "report_sha256": hashlib.sha256(text.encode()).hexdigest(),
        "dispositions": dispositions, "human_evidence": args.human_evidence}, [test_event["event_id"]])
    r.publish(event, [".group/final/candidate.md"])
    return {"candidate_id": event["event_id"], "canonical_commit": commit, "candidate_report": text,
            "next": "Show this report to the human. Only after explicit confirmation run final-publish --confirm."}


def final_publish(args):
    r = repo(args)
    if not args.confirm:
        raise GroupError("Human confirmation is required after reviewing the concrete candidate")
    canonical_ready(r)
    events = r.events()
    matches = [e for e in events if e["event_id"] == args.candidate and e["event_type"] == "final_candidate"]
    if len(matches) != 1:
        raise GroupError("Public final candidate not found")
    candidate = matches[0]
    commit = candidate["canonical_commit"]
    if not r.ancestor(commit):
        raise GroupError("Candidate canonical commit is no longer an ancestor")
    changed = r.output("diff", "--name-only", commit, "HEAD").splitlines()
    if any(not p.startswith((".group/events/", ".group/final/")) for p in changed):
        raise GroupError("Canonical code/configuration changed; prepare and validate a new candidate")
    latest = next((e for e in reversed(events) if e["event_type"] == "final_candidate"), None)
    if not latest or latest["event_id"] != args.candidate:
        raise GroupError("A newer final candidate exists; inspect it first")
    if unresolved_blockers(events):
        raise GroupError("A blocker prevents final publication")
    for evidence_id in candidate["test_evidence"]:
        evidence = next((e for e in events if e["event_id"] == evidence_id), None)
        if not evidence or evidence["event_type"] != "test_result" or evidence["commit"] != commit or evidence["automated_result"] != "pass":
            raise GroupError("Candidate lacks passing test evidence for its exact canonical commit")
    latest_exact_test = next((e for e in reversed(events) if e["event_type"] == "test_result"
                              and e["commit"] == commit), None)
    if latest_exact_test and latest_exact_test["automated_result"] != "pass":
        raise GroupError("Latest test evidence no longer passes; investigate and prepare a new candidate")
    if final_concerns(r, events, commit):
        raise GroupError("Unresolved review concerns prevent final publication")
    pending = [e for e in events if e["event_type"] == "change_published" and not r.ancestor(e["commit"], commit)
               and e["change_id"] not in candidate.get("dispositions", {})]
    if pending:
        raise GroupError("New unincorporated work exists; prepare a new candidate")
    text = (r.meta / "final/candidate.md").read_text(encoding="utf-8")
    if hashlib.sha256(text.encode()).hexdigest() != candidate["report_sha256"]:
        raise GroupError("Candidate report changed; prepare it again")
    (r.meta / "final/final_report.md").write_text(text, encoding="utf-8")
    envelope = {"protocol_version": "0.1", "group_id": r.config["group_id"],
                "canonical_branch": r.config["canonical_branch"], "canonical_commit": commit,
                "report_file": ".group/final/final_report.md", "initiated_by": r.identity(),
                "created_at": now(), "status": "completed_with_known_limitations" if candidate["known_issues"] else "completed",
                "known_limitations": candidate["known_issues"]}
    write_json(r.meta / "final/final.json", envelope)
    event = r.event("final_result", {"canonical_commit": commit, "final_report_path": envelope["report_file"],
        "test_evidence": candidate["test_evidence"], "known_limitations": candidate["known_issues"],
        "initiated_by": r.identity()}, [candidate["event_id"]])
    r.publish(event, [".group/final/final_report.md", ".group/final/final.json"])
    return {"published": True, "final": envelope, "event": event}
