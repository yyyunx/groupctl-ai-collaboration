"""Real local Git remotes, independent clones and failure-path integration tests."""
import argparse
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from groupctl import commands
from groupctl.core import GroupError, Repository, validate_event, write_json


ROOT = Path(__file__).resolve().parents[1]


def git(cwd, *args, ok=(0,)):
    result = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True,
                            encoding="utf-8", errors="replace")
    if result.returncode not in ok:
        raise AssertionError(f"git {args}: {result.stdout}\n{result.stderr}")
    return result.stdout.strip()


def call(path, operation, **kwargs):
    return getattr(commands, operation)(argparse.Namespace(repo=str(path), **kwargs))


class GitFixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="groupctl-tests-")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.remote = self.base / "remote.git"
        self.remote.mkdir()
        git(self.remote, "init", "--bare", "--initial-branch=main")
        self.a = self.base / "A"
        git(self.base, "clone", str(self.remote), str(self.a))
        git(self.a, "config", "user.name", "Student A")
        git(self.a, "config", "user.email", "a@example.invalid")
        git(self.a, "config", "core.autocrlf", "false")
        self.assignment = self.base / "assignment.md"
        self.assignment.write_text("Build a greeting library with independently testable features.", encoding="utf-8")
        self.checks = self.base / "checks.json"
        write_json(self.checks, [[sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"]])
        (self.a / ".gitignore").write_text("__pycache__/\n*.pyc\n", encoding="utf-8")
        (self.a / "greet.py").write_text('def greet(name):\n    return "Hello " + name\n', encoding="utf-8")
        (self.a / "tests").mkdir()
        (self.a / "tests/test_greet.py").write_text(
            'import unittest\nfrom greet import greet\nclass GreetingTest(unittest.TestCase):\n'
            '    def test_name(self):\n        self.assertIn("Ada", greet("Ada"))\n', encoding="utf-8")
        call(self.a, "init", group="G-demo", person="P17", name="A", assignment=str(self.assignment),
             checks_file=str(self.checks), canonical="main")
        git(self.a, "add", ".")
        git(self.a, "commit", "-m", "Initial group project")
        git(self.a, "push", "-u", "origin", "main")
        git(self.a, "switch", "-c", "people/P17/greeting")
        self.b = self.clone("B", "P22")
        self.c = self.clone("C", "P31")

    def clone(self, name, person):
        path = self.base / name
        git(self.base, "clone", str(self.remote), str(path))
        git(path, "config", "user.name", name)
        git(path, "config", "user.email", name.lower() + "@example.invalid")
        git(path, "config", "core.autocrlf", "false")
        call(path, "join", person=person, name=name, topic="work")
        return path

    def publish(self, path, summary):
        return call(path, "pub", summary=summary, interface_change=[], known_issue=[],
                    draft=False, unverified_reason=None)

    def semantic(self, path, state="pass", resolution="No textual conflicts"):
        file = self.base / (path.name + "-semantic.json")
        write_json(file, {"reviewed_commit": git(path, "rev-parse", "HEAD"), "semantic_review": state,
                          "build": "not_applicable", "summary": "Greeting behavior and independent features inspected.",
                          "conflict_resolution_summary": resolution})
        return file

    def integrate(self, target, change):
        result = call(target, "integrate", change=change)
        self.assertTrue(result["git_merged"])
        return call(target, "integrate_finish", file=str(self.semantic(target)))


class CollaborationTests(GitFixture):
    def test_three_people_publish_discover_integrate_test_and_finalize(self):
        (self.a / "greet.py").write_text('def greet(name):\n    return "Hello " + name.strip()\n', encoding="utf-8")
        a = self.publish(self.a, "Trim surrounding whitespace")
        (self.b / "numbers.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
        b = self.publish(self.b, "Add independent arithmetic helper")
        sync = call(self.b, "sync", update=False)
        self.assertIn(a["change_id"], [e.get("change_id") for e in sync["new_events"]])
        self.assertFalse((self.b / "greet.py").read_text().find("strip") >= 0)
        inspected = call(self.b, "inspect", change=a["change_id"])
        self.assertIn("name.strip()", inspected["diff"])
        review_file = self.base / "review.json"
        write_json(review_file, {"inspected_commit": a["event"]["commit"], "diff_inspected": True,
            "verdict": "accept", "summary": "Whitespace handling preserves greeting contract.",
            "issues": [], "tests_run": [], "evidence": ["Inspected exact diff"]})
        reviewed = call(self.b, "review", change=a["change_id"], file=str(review_file))
        self.assertEqual(reviewed["event"]["verdict"], "accept")
        self.assertFalse(Repository(self.b).ancestor(a["event"]["commit"]))
        integrated = self.integrate(self.b, a["change_id"])
        self.assertEqual(integrated["event"]["result"], "success")
        tested = call(self.b, "test", scope="current", human_check=[])
        self.assertEqual(tested["event"]["automated_result"], "pass")
        self.assertEqual(tested["event"]["passed"], 1)
        # Ordinary Git promotes the verified combination; no special permanent integrator.
        git(self.b, "switch", "main")
        git(self.b, "merge", "--no-edit", "people/P22/work")
        git(self.b, "merge", "--no-edit", "origin/people/P31/work")
        git(self.b, "push", "origin", "main")
        prepared = call(self.b, "final_prepare", result="Greeting and arithmetic features combined.",
                        dispositions=None, limitation=[], human_check=[], human_evidence=[])
        with self.assertRaisesRegex(GroupError, "confirmation"):
            call(self.b, "final_publish", candidate=prepared["candidate_id"], confirm=False)
        final = call(self.b, "final_publish", candidate=prepared["candidate_id"], confirm=True)
        self.assertEqual(final["final"]["canonical_commit"], prepared["canonical_commit"])
        self.assertTrue((self.b / ".group/final/final_report.md").exists())
        call(self.c, "sync", update=True)
        self.assertEqual(read_json_local(self.c / ".group/final/final.json")["status"], "completed")
        self.assertTrue((self.c / "numbers.py").exists())
        self.assertEqual(len({e["person_id"] for e in Repository(self.c).events()}), 2)

    def test_conflict_is_visible_then_resolution_is_verified(self):
        (self.a / "greet.py").write_text('def greet(name):\n    return "Hi " + name\n', encoding="utf-8")
        published = self.publish(self.a, "Use Hi greeting")
        (self.b / "greet.py").write_text('def greet(name):\n    return "Welcome " + name\n', encoding="utf-8")
        self.publish(self.b, "Use Welcome greeting")
        result = call(self.b, "integrate", change=published["change_id"])
        self.assertEqual(result["conflicts"], ["greet.py"])
        self.assertFalse(result["accepted"])
        with self.assertRaises(GroupError):
            call(self.b, "integrate_finish", file=str(self.semantic(self.b)))
        # Simulated explicit human/agent semantic decision, not automatic side selection.
        (self.b / "greet.py").write_text('def greet(name):\n    return "Hi, welcome " + name\n', encoding="utf-8")
        git(self.b, "add", "greet.py")
        git(self.b, "commit", "-m", "Resolve both greeting intents")
        final = call(self.b, "integrate_finish", file=str(self.semantic(self.b, resolution="Preserved Hi and welcome intents")))
        self.assertEqual(final["event"]["conflicts"], ["greet.py"])
        self.assertEqual(final["event"]["verification"]["tests"], "pass")

    def test_sync_protects_dirty_work_and_status_does_not_merge(self):
        (self.a / "new.py").write_text("VALUE = 1\n", encoding="utf-8")
        self.publish(self.a, "Add value")
        before = git(self.b, "rev-parse", "HEAD")
        (self.b / "private.txt").write_text("unfinished", encoding="utf-8")
        result = call(self.b, "status")
        self.assertTrue(result["uncommitted"])
        self.assertEqual(before, git(self.b, "rev-parse", "HEAD"))
        with self.assertRaisesRegex(GroupError, "not clean"):
            call(self.b, "sync", update=True)
        self.assertEqual((self.b / "private.txt").read_text(), "unfinished")

    def test_failed_test_publishes_evidence_and_cannot_finalize(self):
        (self.a / "greet.py").write_text('def greet(name):\n    return "wrong"\n', encoding="utf-8")
        with self.assertRaisesRegex(GroupError, "passing checks"):
            self.publish(self.a, "Broken change")
        git(self.a, "add", "greet.py")
        git(self.a, "commit", "-m", "Deliberately broken test fixture")
        result = call(self.a, "test", scope="current", human_check=[])
        self.assertEqual(result["event"]["automated_result"], "fail")
        self.assertEqual(result["event"]["failed"], 1)
        git(self.a, "switch", "main")
        git(self.a, "merge", "--no-edit", "people/P17/greeting")
        git(self.a, "push", "origin", "main")
        with self.assertRaisesRegex(GroupError, "did not pass"):
            call(self.a, "final_prepare", result="Broken", dispositions=None, limitation=[], human_check=[], human_evidence=[])
        self.assertFalse((self.a / ".group/final/final.json").exists())

    def test_semantic_failure_overrides_successful_git_and_tests(self):
        (self.a / "feature.py").write_text("VALUE = 1\n", encoding="utf-8")
        change = self.publish(self.a, "Independent feature")
        call(self.b, "integrate", change=change["change_id"])
        result = call(self.b, "integrate_finish", file=str(self.semantic(self.b, state="fail")))
        self.assertEqual(result["event"]["verification"]["tests"], "pass")
        self.assertEqual(result["event"]["result"], "failed")

    def test_pending_change_blocks_final_until_explicit_disposition(self):
        (self.a / "experimental.py").write_text("EXPERIMENT = True\n", encoding="utf-8")
        change = self.publish(self.a, "Experimental proposal")
        git(self.a, "switch", "main")
        with self.assertRaisesRegex(GroupError, "Unincorporated"):
            call(self.a, "final_prepare", result="Base", dispositions=None, limitation=[], human_check=[], human_evidence=[])
        dispositions = self.base / "dispositions.json"
        write_json(dispositions, {change["change_id"]: "Rejected: outside the agreed greeting requirements."})
        result = call(self.a, "final_prepare", result="Base", dispositions=str(dispositions), limitation=[], human_check=[], human_evidence=[])
        self.assertIn("Rejected", result["candidate_report"])

    def test_test_named_change_uses_isolated_checkout(self):
        (self.a / "feature.py").write_text("VALUE = 7\n", encoding="utf-8")
        change = self.publish(self.a, "Add feature")
        branch = git(self.b, "branch", "--show-current")
        result = call(self.b, "test", scope=change["change_id"], human_check=[])
        self.assertEqual(result["event"]["commit"], change["event"]["commit"])
        self.assertEqual(result["event"]["automated_result"], "pass")
        self.assertEqual(branch, git(self.b, "branch", "--show-current"))
        self.assertFalse((self.b / "feature.py").exists())

    def test_remote_push_failure_is_not_reported_as_publication(self):
        r = Repository(self.a)
        event = r.event("finding", {"summary": "Local only", "evidence": []})
        git(self.a, "remote", "set-url", "--push", "origin", str(self.base / "missing.git"))
        with self.assertRaisesRegex(GroupError, "NOT published"):
            r.publish(event)
        self.assertNotIn(event["event_id"], [e["event_id"] for e in Repository(self.b).events()])

    def test_schema_secret_and_event_mutation_protection(self):
        r = Repository(self.a)
        with self.assertRaises(GroupError):
            r.event("review", {"change_id": "C-1", "verdict": "looks_good", "summary": "x", "issues": [], "tests_run": []})
        with self.assertRaises(GroupError):
            r.event("finding", {"summary": "x", "evidence": [], "person_id": "P22"})
        with self.assertRaises(GroupError):
            r.event("finding", {"summary": "x", "evidence": [], "resolves_events": "not-a-list"})
        event = r.publish(r.event("finding", {"summary": "Original", "evidence": []}))
        with self.assertRaisesRegex(GroupError, "overwrite"):
            r.publish(event)
        (self.a / ".env").write_text("PASSWORD=example", encoding="utf-8")
        with self.assertRaisesRegex(GroupError, "secret"):
            self.publish(self.a, "Should refuse")

    def test_candidate_is_invalidated_by_changed_source(self):
        git(self.a, "switch", "main")
        prepared = call(self.a, "final_prepare", result="Base greeting", dispositions=None,
                        limitation=[], human_check=[], human_evidence=[])
        (self.a / "feature.py").write_text("VALUE = 99\n", encoding="utf-8")
        git(self.a, "add", "feature.py")
        git(self.a, "commit", "-m", "New source after candidate")
        git(self.a, "push", "origin", "main")
        with self.assertRaisesRegex(GroupError, "changed"):
            call(self.a, "final_publish", candidate=prepared["candidate_id"], confirm=True)

    def test_modified_public_event_is_detected_from_history(self):
        r = Repository(self.a)
        event = r.publish(r.event("finding", {"summary": "Original", "evidence": []}))
        path = self.a / ".group/events" / (event["event_id"] + ".json")
        event["summary"] = "Illegally rewritten"
        write_json(path, event)
        git(self.a, "add", ".group/events")
        git(self.a, "commit", "-m", "Invalid fixture: change immutable event")
        git(self.a, "push", "origin", "HEAD")
        Repository(self.b).fetch()
        with self.assertRaisesRegex(GroupError, "modifications/deletions"):
            Repository(self.b).events()

    def test_blocker_requires_explicit_resolution_event(self):
        git(self.a, "switch", "main")
        r = Repository(self.a)
        blocked = r.publish(r.event("blocker", {"summary": "Missing decision", "blocking_change_id": "C-none",
                                               "requested_action": "Decide behavior"}))
        with self.assertRaisesRegex(GroupError, "blockers"):
            call(self.a, "final_prepare", result="Base", dispositions=None, limitation=[], human_check=[], human_evidence=[])
        r.publish(r.event("finding", {"summary": "Decision made: preserve greeting requirement.",
            "evidence": ["Requirement checked"], "resolves_events": [blocked["event_id"]]}, [blocked["event_id"]]))
        result = call(self.a, "final_prepare", result="Base", dispositions=None, limitation=[], human_check=[], human_evidence=[])
        self.assertIn("candidate_id", result)

    def test_review_concerns_block_finalization(self):
        (self.a / "feature.py").write_text("VALUE = 1\n", encoding="utf-8")
        change = self.publish(self.a, "Feature with unresolved review")
        self.integrate(self.b, change["change_id"])
        r = Repository(self.b)
        r.publish(r.event("review", {"change_id": change["change_id"], "verdict": "accept_with_changes",
                  "summary": "Missing edge case", "issues": ["Missing empty input test"], "tests_run": []}))
        git(self.b, "switch", "main")
        git(self.b, "merge", "--no-edit", "people/P22/work")
        git(self.b, "push", "origin", "main")
        with self.assertRaisesRegex(GroupError, "review concerns"):
            call(self.b, "final_prepare", result="Feature", dispositions=None, limitation=[], human_check=[], human_evidence=[])

    def test_unavailable_checks_are_not_a_success(self):
        r = Repository(self.a)
        missing = r.checks([["groupctl-nonexistent-executable-123456"]])
        self.assertEqual(missing["automated_result"], "partial")
        self.assertIsNone(missing["results"][0]["exit_code"])
        self.assertEqual(r.checks([])["automated_result"], "not_available")

    def test_cli_failed_test_returns_nonzero_with_published_evidence(self):
        (self.a / "greet.py").write_text('def greet(name):\n    return "wrong"\n', encoding="utf-8")
        git(self.a, "add", "greet.py")
        git(self.a, "commit", "-m", "Broken fixture")
        result = subprocess.run([sys.executable, "-m", "groupctl", "--repo", str(self.a), "test"],
                                cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(result.returncode, 2)
        output = json.loads(result.stdout)
        self.assertTrue(output["published"])
        self.assertEqual(output["event"]["automated_result"], "fail")


def read_json_local(path):
    return json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
