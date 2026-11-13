"""Protocol 0.1 schema and graph validation (no Git or agent judgments)."""
from datetime import datetime, timezone
import re

from .errors import GroupError


COMMON_FIELDS = {"protocol_version": str, "event_id": str, "event_type": str,
                 "group_id": str, "person_id": str, "created_at": str, "related_events": list}
EVENT_FIELDS = {
    "change_published": {"change_id": str, "branch": str, "commit": str, "summary": str,
                         "files_changed": list, "interface_changes": list, "tests_run": list,
                         "known_issues": list, "proposed_for_integration": bool},
    "finding": {"summary": str, "evidence": list},
    "question": {"question_id": str, "text": str, "blocking": bool},
    "answer": {"question_id": str, "text": str},
    "review": {"change_id": str, "verdict": str, "summary": str, "issues": list, "tests_run": list},
    "test_result": {"scope": str, "commit": str, "commands": list, "automated_result": str,
                    "passed": (int, type(None)), "failed": (int, type(None)),
                    "skipped": (int, type(None)), "human_checks_required": list, "summary": str},
    "integration_result": {"change_id": str, "target_branch": str, "result": str,
                           "merge_commit": str, "conflicts": list,
                           "conflict_resolution_summary": str, "verification": dict, "summary": str},
    "blocker": {"summary": str, "blocking_change_id": str, "requested_action": str},
    "final_candidate": {"canonical_commit": str, "candidate_report_path": str,
                        "test_evidence": list, "known_issues": list},
    "final_result": {"canonical_commit": str, "final_report_path": str,
                     "test_evidence": list, "known_limitations": list, "initiated_by": str},
}


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,255}", value):
        raise GroupError(f"Invalid identifier: {value!r}")
    return value


def event_time(event):
    try:
        value = datetime.fromisoformat(event["created_at"].replace("Z", "+00:00"))
        if value.tzinfo is None:
            raise ValueError("timezone required")
        return value.astimezone(timezone.utc)
    except (ValueError, TypeError, KeyError) as exc:
        raise GroupError("created_at must be an ISO timestamp with timezone") from exc


def validate_event(event):
    if not isinstance(event, dict):
        raise GroupError("An event must be a JSON object")
    kind = event.get("event_type")
    if not isinstance(kind, str) or kind not in EVENT_FIELDS:
        raise GroupError("Unsupported event_type")
    for key, expected in (COMMON_FIELDS | EVENT_FIELDS[kind]).items():
        value = event.get(key)
        if key not in event or not isinstance(value, expected):
            raise GroupError(f"Missing or invalid event field: {key}")
        if expected is str and not value.strip():
            raise GroupError(f"Event field must not be blank: {key}")
    if event["protocol_version"] != "0.1":
        raise GroupError("Unsupported protocol_version")
    for key in ("event_id", "person_id", "group_id"):
        identifier(event[key])
    event_time(event)
    for key in ("related_events", "files_changed", "interface_changes", "tests_run", "known_issues",
                "evidence", "issues", "commands", "human_checks_required", "conflicts",
                "test_evidence", "known_limitations", "resolves_events"):
        if key in event and (not isinstance(event[key], list) or
                            not all(isinstance(v, str) and v.strip() for v in event[key])):
            raise GroupError(f"{key} must contain nonempty strings")
    for key in ("related_events", "resolves_events", "test_evidence"):
        for value in event.get(key, []):
            identifier(value)
        if len(event.get(key, [])) != len(set(event.get(key, []))):
            raise GroupError(f"Duplicate event reference in {key}")
    for key in ("passed", "failed", "skipped"):
        if key in event and event[key] is not None and (type(event[key]) is not int or event[key] < 0):
            raise GroupError(f"{key} must be a nonnegative integer or null")
    enums = {"verdict": {"accept", "accept_with_changes", "reject", "needs_more_evidence"},
             "automated_result": {"pass", "fail", "partial", "not_available"},
             "result": {"success", "failed", "needs_human"}}
    for key, choices in enums.items():
        if key in event and (not isinstance(event[key], str) or event[key] not in choices):
            raise GroupError(f"Invalid {key}: {event[key]!r}")
    if kind == "test_result" and event["automated_result"] == "pass":
        if not event["commands"] or event["failed"] not in (None, 0):
            raise GroupError("A passing test_result needs commands and no known failures")
        if event["passed"] == 0 and event["skipped"] == 0:
            raise GroupError("Zero discovered tests cannot be a passing test_result")
    if kind == "integration_result":
        verification = event["verification"]
        if not all(isinstance(verification.get(key), str) and verification[key] in
                   {"pass", "fail", "not_available", "not_applicable"}
                   for key in ("build", "tests", "semantic_review")):
            raise GroupError("verification must describe build, tests and semantic_review")
        if event["result"] == "success" and (verification["tests"] != "pass" or
                verification["semantic_review"] != "pass" or verification["build"] not in {"pass", "not_applicable"}):
            raise GroupError("Successful integration requires passing tests AND semantic review")
    if kind in {"final_candidate", "final_result"} and not event["test_evidence"]:
        raise GroupError("Finalization requires test evidence")
    return event


def validate_event_graph(events):
    """Verify cross-file references on the union of public remote branches."""
    index = {}
    for event in events:
        validate_event(event)
        event_id = event["event_id"]
        if event_id in index:
            raise GroupError(f"Duplicate event_id: {event_id}")
        index[event_id] = event
    for event in events:
        for key in ("related_events", "resolves_events", "test_evidence"):
            for target in event.get(key, []):
                if target == event["event_id"] or target not in index:
                    raise GroupError(f"Broken {key} reference {target} in {event['event_id']}")
                if index[target]["group_id"] != event["group_id"]:
                    raise GroupError(f"Cross-group event reference: {target}")
        if event["event_type"] == "answer" and not any(
                index[e]["event_type"] == "question" and index[e]["question_id"] == event["question_id"]
                for e in event["related_events"]):
            raise GroupError("An answer must reference its matching question event")
        for target in event.get("resolves_events", []):
            if target not in event["related_events"]:
                raise GroupError("A resolution must also include its target in related_events")
        for target in event.get("test_evidence", []):
            evidence = index[target]
            if evidence["event_type"] != "test_result" or evidence["commit"] != event["canonical_commit"] or evidence["automated_result"] != "pass":
                raise GroupError("Final evidence must be a passing test_result for the exact canonical commit")
    # Graphs must be acyclic; use an iterative walk to support long event histories.
    done = set()
    for event_id in index:
        stack, active = [(event_id, False)], set()
        while stack:
            node, leaving = stack.pop()
            if leaving:
                active.discard(node)
                done.add(node)
            elif node not in done:
                if node in active:
                    raise GroupError(f"Cycle in related_events: {node}")
                active.add(node)
                stack.append((node, True))
                stack.extend((target, False) for target in index[node]["related_events"])
    return events
