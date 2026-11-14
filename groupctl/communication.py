"""Convenient inputs for the existing protocol; never manufacture a verdict."""
import json
import uuid
from pathlib import Path

from .core import Repository, GroupError, read_json
from .collaboration import ObservedRepository
from .presentation import reject_secrets, safe


def nonempty(value, name):
    if not isinstance(value, str) or not value.strip():
        raise GroupError(name + " must not be blank")
    return value.strip()


def publish_communication(args):
    r = Repository(args.repo)
    r.clean()
    r.fetch()
    events = r.events()
    related = []
    change_id = getattr(args, "change", None)
    if change_id:
        change = r.change(change_id, events)
        related.append(change["event_id"])
    if args.command == "ask":
        kind = "question"
        payload = {"question_id": f"Q-{r.identity()}-{uuid.uuid4().hex[:10]}",
                   "text": nonempty(args.text, "text"), "blocking": False}
    elif args.command == "answer":
        candidates = [e for e in events if e["event_type"] == "question" and
                      args.question in (e["question_id"], e["event_id"])]
        if len(candidates) != 1:
            raise GroupError("Expected one published question for this question ID/event ID")
        question = candidates[0]
        kind, related = "answer", [question["event_id"]]
        payload = {"question_id": question["question_id"], "text": nonempty(args.text, "text")}
    elif args.command == "block":
        kind = "blocker"
        payload = {"summary": nonempty(args.summary, "summary"), "blocking_change_id": change_id or "GROUP",
                   "requested_action": nonempty(args.action, "action")}
    else:
        candidates = [e for e in events if e["event_id"] == args.event]
        if len(candidates) != 1 or candidates[0]["event_type"] not in {"blocker", "question", "review", "integration_result"}:
            raise GroupError("resolve needs a published blocker, question, review or integration_result event ID")
        reason = nonempty(args.reason, "reason")
        kind, related = "finding", [args.event]
        payload = {"summary": "Resolution recorded: " + reason, "evidence": getattr(args, "evidence", []),
                   "resolves_events": [args.event]}
    if change_id:
        payload["change_id"] = change_id
    reject_secrets(payload)
    event = r.event(kind, payload, related)
    r.publish(event)
    return safe({"published": True, "event": event,
                 "note": "解決紀錄是操作者提供的理由；不會改寫原審查 verdict，也不代表新的 Review Pass。" if args.command == "resolve" else "已推送公開事件。"})


def template(args):
    r = ObservedRepository(args.repo)
    if args.kind == "review":
        if not args.change:
            raise GroupError("template review requires a change ID")
        change = r.change(args.change)
        value = {"inspected_commit": change["commit"], "diff_inspected": False,
                 "verdict": "needs_more_evidence", "summary": "Describe actual review findings after inspecting the diff.",
                 "issues": [], "tests_run": [], "evidence": []}
    else:
        value = {"reviewed_commit": r.head, "semantic_review": "fail", "build": "not_available",
                 "summary": "Record actual compatibility findings before selecting pass.",
                 "conflict_resolution_summary": "Explain both intended behaviors and the deliberate resolution."}
    if getattr(args, "output", None):
        output = Path(args.output)
        # Explicit output is a creation request; never replace an existing assessment.
        with output.open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        return {"created": str(output.resolve()), "template": value, "approved": False}
    return value


def assessment_input(args, kind):
    """Inline flags are explicit attestations, with the same downstream checks as JSON."""
    fields = ("verdict", "inspected_commit", "diff_inspected", "summary", "issue", "test_run", "evidence") if kind == "review" else (
        "semantic_review", "reviewed_commit", "build", "summary", "resolution")
    file = getattr(args, "file", None)
    if file:
        if any(getattr(args, key, None) for key in fields):
            raise GroupError("請選 --file 或 inline assessment flags，不能混用。", code=2)
        return read_json(file)
    required = ("verdict", "inspected_commit", "summary") if kind == "review" else ("semantic_review", "reviewed_commit", "build", "summary", "resolution")
    missing = [key for key in required if not isinstance(getattr(args, key, None), str) or not getattr(args, key).strip()]
    if missing or (kind == "review" and not getattr(args, "diff_inspected", False)):
        raise GroupError("請明確提供實際 assessment、完整 commit 和 summary；Review 還須 --diff-inspected。", code=2,
                         hint="review --help 或 integrate-finish --help；不會替你預設 Pass。")
    if kind == "review":
        result = {"verdict": args.verdict, "inspected_commit": args.inspected_commit, "diff_inspected": True,
                  "summary": args.summary, "issues": getattr(args, "issue", []), "tests_run": getattr(args, "test_run", []),
                  "evidence": getattr(args, "evidence", [])}
    else:
        result = {"semantic_review": args.semantic_review, "reviewed_commit": args.reviewed_commit,
                  "build": args.build, "summary": args.summary, "conflict_resolution_summary": args.resolution}
    reject_secrets(result)
    return result
