"""Independent protocol fixtures, including graph integrity inspired by Group 2."""
import copy
import unittest

from groupctl.core import GroupError
from groupctl.events import validate_event, validate_event_graph, event_time


COMMIT = "a" * 40
PAYLOADS = {
    "change_published": dict(change_id="C-17", branch="people/P17/topic", commit=COMMIT, summary="Feature",
        files_changed=["src/app.py"], interface_changes=[], tests_run=["unit tests"], known_issues=[], proposed_for_integration=True),
    "finding": dict(summary="Finding", evidence=[]),
    "question": dict(question_id="Q-1", text="Preserve positions?", blocking=True),
    "answer": dict(question_id="Q-1", text="Yes"),
    "review": dict(change_id="C-17", verdict="accept", summary="Reviewed", issues=[], tests_run=[]),
    "test_result": dict(scope="current_branch", commit=COMMIT, commands=["unit tests"], automated_result="pass",
        passed=2, failed=0, skipped=0, human_checks_required=[], summary="Two tests passed"),
    "integration_result": dict(change_id="C-17", target_branch="people/P22/topic", result="success", merge_commit=COMMIT,
        conflicts=[], conflict_resolution_summary="No conflicts", verification=dict(build="not_applicable", tests="pass", semantic_review="pass"), summary="Integrated"),
    "blocker": dict(summary="Need a decision", blocking_change_id="C-17", requested_action="Choose interface"),
    "final_candidate": dict(canonical_commit=COMMIT, candidate_report_path=".group/final/candidate.md", test_evidence=["E-tests"], known_issues=[]),
    "final_result": dict(canonical_commit=COMMIT, final_report_path=".group/final/final_report.md", test_evidence=["E-tests"], known_limitations=[], initiated_by="P17"),
}


def event(kind="finding", event_id="E-one", **changes):
    return dict(protocol_version="0.1", event_id=event_id, event_type=kind, group_id="G-1", person_id="P17",
                created_at="2026-11-13T08:00:00Z", related_events=[], **copy.deepcopy(PAYLOADS[kind])) | changes


class EventContractTests(unittest.TestCase):
    def test_all_ten_event_types_and_required_fields(self):
        for kind in PAYLOADS:
            valid = event(kind)
            validate_event(valid)
            for key in valid:
                with self.subTest(kind=kind, missing=key):
                    invalid = copy.deepcopy(valid)
                    del invalid[key]
                    with self.assertRaises(GroupError):
                        validate_event(invalid)

    def test_invalid_types_enums_timestamps_counts_and_paths(self):
        invalid = [event(event_type=[]), event(protocol_version="9"), event(created_at="2026-11-13T08:00:00"),
            event(event_id="../outside"), event(related_events="E-other"), event(evidence=[{}]),
            event("review", verdict="looks_good"), event("test_result", automated_result="unknown"),
            event("test_result", failed=True), event("test_result", passed=-1),
            event("test_result", commands=[]), event("test_result", passed=0),
            event("integration_result", result="merged"), event("final_candidate", test_evidence=[])]
        for value in invalid:
            with self.subTest(value=value), self.assertRaises(GroupError):
                validate_event(value)

    def test_all_allowed_verdicts_and_nonpassing_test_results(self):
        for verdict in ("accept", "accept_with_changes", "reject", "needs_more_evidence"):
            validate_event(event("review", verdict=verdict))
        for result in ("fail", "partial", "not_available"):
            validate_event(event("test_result", automated_result=result, commands=[], passed=None, failed=None, skipped=None))

    def test_success_cannot_hide_missing_tests_or_semantic_failure(self):
        for key in ("tests", "semantic_review"):
            for result in ("not_available", "not_applicable", "fail"):
                value = event("integration_result")
                value["verification"][key] = result
                with self.subTest(key=key, result=result), self.assertRaises(GroupError):
                    validate_event(value)

    def test_related_event_integrity_duplicates_cycles_and_groups(self):
        first = event(event_id="E-first")
        second = event(event_id="E-second", related_events=["E-first"])
        validate_event_graph([first, second])
        bad_graphs = [[second], [first, first], [first, event(related_events=["E-one"])],
            [first, second | {"group_id": "G-other"}],
            [first | {"related_events": ["E-second"]}, second],
            [first, second | {"related_events": ["E-first", "E-first"]}]]
        for graph in bad_graphs:
            with self.subTest(graph=graph), self.assertRaises(GroupError):
                validate_event_graph(graph)

    def test_answers_and_resolution_need_matching_references(self):
        question = event("question", "E-question")
        answer = event("answer", "E-answer", related_events=["E-question"])
        validate_event_graph([question, answer])
        with self.assertRaises(GroupError):
            validate_event_graph([question, answer | {"question_id": "Q-other"}])
        with self.assertRaises(GroupError):
            validate_event_graph([question, answer | {"related_events": []}])
        with self.assertRaises(GroupError):
            validate_event_graph([question, event(resolves_events=["E-question"])])

    def test_final_evidence_is_passing_and_bound_to_canonical_commit(self):
        tests = event("test_result", "E-tests")
        candidate = event("final_candidate", "E-candidate", related_events=["E-tests"])
        validate_event_graph([tests, candidate])
        for bad in (tests | {"commit": "b" * 40}, tests | {"automated_result": "fail"}):
            with self.assertRaises(GroupError):
                validate_event_graph([bad, candidate])

    def test_timestamps_compare_in_utc(self):
        self.assertEqual(event_time(event(created_at="2026-11-13T16:00:00+08:00")), event_time(event()))
