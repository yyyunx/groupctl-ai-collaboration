"""Two-stage canonical finalization; never infer a human decision."""
import hashlib
import json
import sys
from datetime import datetime
from .core import GroupError, Repository, now, read_json, write_json
from .errors import VerificationError
from .policy import unresolved_blockers, final_concerns
from .events import event_time
from .status import same_code

def repo(args):
    return Repository(args.repo)


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
    if len(args.human_evidence) < len(args.human_check):
        raise GroupError("Provide concrete human-check results using --human-evidence")
    checks = r.check_commit(commit)
    r.clean()
    if checks["automated_result"] != "pass":
        # Failed final validation is shared evidence, never a successful final result.
        event = r.test_event("canonical_final", commit, checks, args.human_check)
        r.publish(event)
        raise VerificationError("Final checks did not pass. Test evidence published; no final result created.",
                                hint="Inspect the test_result, fix failures or configure real tests, then prepare again.")
    test_event = r.publish(r.test_event("canonical_final", commit, checks))
    lines = ["# Group Final Report", "", "## Assignment", r.path(r.config["assignment_file"]).read_text(encoding="utf-8"),
             "", "## Result", args.result, "", "## Canonical Commit", commit,
             "", "## Important Changes"]
    if r.config.get("simulation") is True:
        lines.insert(1, "\n> SIMULATION ONLY: decisions and confirmation are fixtures, not real human feedback.\n")
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
        "dispositions": dispositions, "human_evidence": args.human_evidence,
        "evidence_mode": "simulation" if r.config.get("simulation") is True else "real"}, [test_event["event_id"]])
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
    if any(e["event_type"] == "final_result" and candidate["event_id"] in e["related_events"] for e in events):
        raise GroupError("This candidate was already finalized; do not publish duplicate final results")
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
                              and same_code(r, e["commit"], commit)), None)
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
    confirmation = confirm_candidate(r, args, candidate, text)
    (r.meta / "final/final_report.md").write_text(text, encoding="utf-8")
    envelope = {"protocol_version": "0.1", "group_id": r.config["group_id"],
                "canonical_branch": r.config["canonical_branch"], "canonical_commit": commit,
                "report_file": ".group/final/final_report.md", "initiated_by": r.identity(),
                "created_at": now(), "status": "completed_with_known_limitations" if candidate["known_issues"] else "completed",
                "known_limitations": candidate["known_issues"], "human_confirmation": confirmation,
                "evidence_mode": candidate.get("evidence_mode", "real")}
    write_json(r.meta / "final/final.json", envelope)
    event = r.event("final_result", {"canonical_commit": commit, "final_report_path": envelope["report_file"],
        "test_evidence": candidate["test_evidence"], "known_limitations": candidate["known_issues"],
        "initiated_by": r.identity(), "human_confirmation": confirmation,
        "evidence_mode": envelope["evidence_mode"]}, [candidate["event_id"]])
    r.publish(event, [".group/final/final_report.md", ".group/final/final.json"])
    return {"published": True, "final": envelope, "event": event}


def confirm_candidate(r, args, candidate, text):
    binding = {"candidate_id": candidate["event_id"], "canonical_commit": candidate["canonical_commit"],
               "report_sha256": candidate["report_sha256"], "confirmed_by": r.identity()}
    if r.config.get("simulation") is True:
        return binding | {"kind": "simulation", "confirmed_at": now(),
                          "statement": "Simulated test fixture confirmation; not a human observation."}
    file = getattr(args, "confirmation_file", None)
    if file:
        supplied = read_json(file)
        if not isinstance(supplied, dict) or any(supplied.get(k) != v for k, v in binding.items()):
            raise GroupError("Human confirmation must match this candidate, exact commit, report hash and current member")
        if not isinstance(supplied.get("statement"), str) or not supplied["statement"].strip():
            raise GroupError("Human confirmation needs an explicit statement of approval")
        try:
            confirmed_at = datetime.fromisoformat(supplied["confirmed_at"].replace("Z", "+00:00"))
            if confirmed_at.tzinfo is None or confirmed_at < event_time(candidate):
                raise ValueError("confirmation predates candidate")
        except (KeyError, TypeError, ValueError) as exc:
            raise GroupError("Human confirmation needs a timezone-aware confirmed_at after candidate creation") from exc
        return binding | {"kind": "human_attestation_file", "confirmed_at": supplied["confirmed_at"], "statement": supplied["statement"]}
    if not sys.stdin.isatty():
        raise GroupError("Real human confirmation is required: use an interactive terminal or --confirmation-file after human review",
                         hint="The AI must show the candidate to a human; --confirm alone in automation is insufficient.")
    print(text, file=sys.stderr)
    challenge = f"FINAL {candidate['event_id']} {candidate['report_sha256'][:12]}"
    print("Human approval required. Type exactly: " + challenge, file=sys.stderr, flush=True)
    if sys.stdin.readline().strip() != challenge:
        raise GroupError("Human confirmation did not match; no final result was published")
    return binding | {"kind": "interactive_human_attestation", "confirmed_at": now(),
                      "statement": "Operator explicitly confirmed the displayed candidate and report hash."}
