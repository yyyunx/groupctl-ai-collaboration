"""Failure-path regressions backed by real independent Git clones."""
import io
import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

from groupctl.core import GroupError, Repository, now, read_json, write_json
from test_groupctl import GitFixture, call, git, ROOT


class SynthesisRegressions(GitFixture):
    def configure(self, path, commands=None, simulation=None):
        file = path / ".group/group.json"
        value = read_json(file)
        if commands is not None:
            value["validation_commands"] = commands
        if simulation is not None:
            value["simulation"] = simulation
        write_json(file, value)
        git(path, "add", ".group/group.json")
        git(path, "commit", "-m", "Configure deliberate validation fixture", "--", ".group/group.json")

    def test_current_test_runs_isolated_even_if_runner_mutates_source(self):
        self.configure(self.a, [[sys.executable, "-c", "from pathlib import Path;Path('greet.py').write_text('BROKEN')"]])
        before = (self.a / "greet.py").read_bytes()
        branch = git(self.a, "branch", "--show-current")
        result = call(self.a, "test", scope="current", human_check=[])
        self.assertEqual(result["event"]["automated_result"], "fail")
        self.assertEqual((self.a / "greet.py").read_bytes(), before)
        self.assertEqual(branch, git(self.a, "branch", "--show-current"))
        self.assertEqual(git(self.a, "status", "--porcelain"), "")
        self.assertEqual(git(self.a, "worktree", "list", "--porcelain").count("worktree "), 1)

    def test_pub_private_snapshot_preserves_staged_and_unstaged_versions(self):
        self.configure(self.a, [[sys.executable, "-c", "from pathlib import Path;Path('greet.py').write_text('BROKEN')"]])
        (self.a / "greet.py").write_text('def greet(name):\n    return "Staged " + name\n', encoding="utf-8")
        git(self.a, "add", "greet.py")
        (self.a / "greet.py").write_text('def greet(name):\n    return "Working " + name\n', encoding="utf-8")
        staged, working = git(self.a, "show", ":greet.py"), (self.a / "greet.py").read_bytes()
        with self.assertRaisesRegex(GroupError, "passing checks"):
            self.publish(self.a, "Unvalidated changes")
        self.assertEqual(git(self.a, "show", ":greet.py"), staged)
        self.assertEqual((self.a / "greet.py").read_bytes(), working)

    def test_zero_tests_cannot_become_successful_integration(self):
        (self.a / "feature.py").write_text("VALUE = 1\n", encoding="utf-8")
        change = self.publish(self.a, "Useful feature")
        (self.b / "empty_tests").mkdir()
        (self.b / "empty_tests/.gitkeep").touch()
        git(self.b, "add", "empty_tests")
        git(self.b, "commit", "-m", "Empty test collection fixture")
        self.configure(self.b, [[sys.executable, "-m", "unittest", "discover", "-s", "empty_tests"]])
        tested = call(self.b, "test", scope="current", human_check=[])
        self.assertEqual(tested["event"]["automated_result"], "not_available")
        call(self.b, "integrate", change=change["change_id"])
        result = call(self.b, "integrate_finish", file=str(self.semantic(self.b)))
        self.assertEqual(result["event"]["verification"]["semantic_review"], "pass")
        self.assertEqual(result["event"]["verification"]["tests"], "not_available")
        self.assertEqual(result["event"]["result"], "needs_human")
        call(self.b, "integrate", change=change["change_id"])
        failed = call(self.b, "integrate_finish", file=str(self.semantic(self.b, state="fail")))
        self.assertEqual(failed["event"]["result"], "failed")

    def test_status_has_pending_interfaces_test_relevance_and_dirty_priority(self):
        (self.a / "feature.py").write_text("VALUE = 1\n", encoding="utf-8")
        change = call(self.a, "pub", summary="API addition", interface_change=["Adds VALUE"], known_issue=[], draft=False, unverified_reason=None)
        tested = call(self.b, "test", scope="current", human_check=[])
        status = call(self.b, "status")
        pending = next(c for c in status["pending_changes"] if c["change_id"] == change["change_id"])
        self.assertFalse(pending["in_current"])
        self.assertEqual(pending["interface_changes"], ["Adds VALUE"])
        self.assertEqual(status["tests"]["latest_for_current_code"]["event_id"], tested["event"]["event_id"])
        self.assertFalse(status["tests"]["exact_current_commit"])
        (self.b / "unfinished.txt").write_text("My work", encoding="utf-8")
        before = git(self.b, "rev-parse", "HEAD")
        status = call(self.b, "status")
        self.assertEqual(status["next_action_reason"], "dirty_worktree")
        self.assertEqual(before, git(self.b, "rev-parse", "HEAD"))
        output = subprocess.run([sys.executable, "-m", "groupctl", "--repo", str(self.b), "status", "--format", "text"],
                                cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(output.returncode, 0)
        self.assertIn("P22", output.stdout)
        self.assertIn(change["change_id"], output.stdout)
        self.assertIn("下一步", output.stdout)

    def test_failed_push_is_visible_as_unpublished_work_in_status(self):
        r = Repository(self.a)
        git(self.a, "remote", "set-url", "--push", "origin", str(self.base / "missing.git"))
        finding = r.event("finding", {"summary": "Important result", "evidence": []})
        with self.assertRaisesRegex(GroupError, "NOT published"):
            r.publish(finding)
        status = call(self.a, "status")
        self.assertIn(finding["event_id"], status["unpublished_events"])
        self.assertEqual(status["next_action_reason"], "push_pending")

    def test_dangling_references_and_local_event_byte_rewrite_are_rejected(self):
        r = Repository(self.a)
        with self.assertRaisesRegex(GroupError, "Broken"):
            r.publish(r.event("finding", {"summary": "Missing evidence", "evidence": []}, ["E-missing"]))
        published = r.publish(r.event("finding", {"summary": "Original", "evidence": []}))
        file = self.a / ".group/events" / (published["event_id"] + ".json")
        file.write_text(json.dumps(published, separators=(",", ":")), encoding="utf-8")
        with self.assertRaisesRegex(GroupError, "bytes were changed"):
            r.publish(r.event("finding", {"summary": "Next", "evidence": []}))

    def test_formal_final_requires_candidate_bound_human_attestation(self):
        git(self.a, "switch", "main")
        self.configure(self.a, simulation=False)
        git(self.a, "push", "origin", "main")
        prepared = call(self.a, "final_prepare", result="Validated base greeting", dispositions=None,
                        limitation=[], human_check=[], human_evidence=[])
        with patch("sys.stdin", io.StringIO("")), self.assertRaisesRegex(GroupError, "Real human confirmation"):
            call(self.a, "final_publish", candidate=prepared["candidate_id"], confirm=True)
        self.assertFalse((self.a / ".group/final/final.json").exists())
        candidate = next(e for e in Repository(self.a).events() if e["event_id"] == prepared["candidate_id"])
        attestation = self.base / "human-attestation-fixture.json"
        record = {"candidate_id": candidate["event_id"], "canonical_commit": candidate["canonical_commit"],
            "report_sha256": candidate["report_sha256"], "confirmed_by": "P17", "confirmed_at": now(),
            "statement": "TEST FIXTURE: simulates a human's explicit attestation for validation only."}
        write_json(attestation, record | {"candidate_id": "E-wrong"})
        with self.assertRaisesRegex(GroupError, "must match"):
            call(self.a, "final_publish", candidate=candidate["event_id"], confirm=True, confirmation_file=str(attestation))
        write_json(attestation, record)
        result = call(self.a, "final_publish", candidate=candidate["event_id"], confirm=True, confirmation_file=str(attestation))
        self.assertEqual(result["final"]["human_confirmation"]["kind"], "human_attestation_file")
        with self.assertRaisesRegex(GroupError, "already finalized"):
            call(self.a, "final_publish", candidate=candidate["event_id"], confirm=True, confirmation_file=str(attestation))

    def test_simulation_is_explicit_in_report_and_final_envelope(self):
        git(self.a, "switch", "main")
        prepared = call(self.a, "final_prepare", result="Simulation fixture", dispositions=None,
                        limitation=[], human_check=[], human_evidence=[])
        self.assertIn("SIMULATION ONLY", prepared["candidate_report"])
        final = call(self.a, "final_publish", candidate=prepared["candidate_id"], confirm=True)
        self.assertEqual(final["final"]["evidence_mode"], "simulation")
        self.assertEqual(final["final"]["human_confirmation"]["kind"], "simulation")

    def test_late_blocker_new_work_and_report_tampering_invalidate_candidate(self):
        git(self.a, "switch", "main")
        prepared = call(self.a, "final_prepare", result="Base", dispositions=None, limitation=[], human_check=[], human_evidence=[])
        file = self.a / ".group/final/candidate.md"
        original = file.read_text(encoding="utf-8")
        file.write_text(original + "Tampered report\n", encoding="utf-8")
        git(self.a, "add", ".group/final/candidate.md")
        git(self.a, "commit", "-m", "Deliberate report tampering fixture")
        git(self.a, "push", "origin", "main")
        with self.assertRaisesRegex(GroupError, "report changed"):
            call(self.a, "final_publish", candidate=prepared["candidate_id"], confirm=True)
        file.write_text(original, encoding="utf-8")
        git(self.a, "add", ".group/final/candidate.md")
        git(self.a, "commit", "-m", "Restore fixture report")
        git(self.a, "push", "origin", "main")
        (self.c / "late.py").write_text("IMPORTANT = True\n", encoding="utf-8")
        self.publish(self.c, "Late important proposal")
        with self.assertRaisesRegex(GroupError, "New unincorporated"):
            call(self.a, "final_publish", candidate=prepared["candidate_id"], confirm=True)
        r = Repository(self.c)
        r.publish(r.event("blocker", {"summary": "Unresolved requirement", "blocking_change_id": "C-late", "requested_action": "Decide first"}))
        with self.assertRaisesRegex(GroupError, "blocker"):
            call(self.a, "final_publish", candidate=prepared["candidate_id"], confirm=True)

    def test_sync_conflict_exit_code_and_both_abort_paths(self):
        (self.a / "greet.py").write_text('def greet(name):\n    return "Hi " + name\n', encoding="utf-8")
        change = self.publish(self.a, "Hi")
        (self.b / "greet.py").write_text('def greet(name):\n    return "Welcome " + name\n', encoding="utf-8")
        self.publish(self.b, "Welcome")
        git(self.a, "switch", "main")
        git(self.a, "merge", "--no-edit", "people/P17/greeting")
        git(self.a, "push", "origin", "main")
        before = git(self.b, "rev-parse", "HEAD")
        output = subprocess.run([sys.executable, "-m", "groupctl", "--repo", str(self.b), "sync", "--update"],
                                cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(output.returncode, 2)
        self.assertIn("greet.py", json.loads(output.stdout)["conflicts"])
        git(self.b, "merge", "--abort")
        self.assertEqual(git(self.b, "rev-parse", "HEAD"), before)
        result = call(self.b, "integrate", change=change["change_id"])
        self.assertTrue(result["conflicts"])
        call(self.b, "integrate_abort")
        self.assertEqual(git(self.b, "rev-parse", "HEAD"), before)

    def test_fresh_clone_recovers_archived_events_without_private_cache(self):
        (self.a / "feature.py").write_text("VALUE = 1\n", encoding="utf-8")
        change = self.publish(self.a, "Recoverable feature")
        self.integrate(self.b, change["change_id"])
        git(self.b, "switch", "main")
        git(self.b, "merge", "--no-edit", "people/P22/work")
        git(self.b, "push", "origin", "main")
        # Accepted commits/events remain discoverable after a temporary source branch is pruned.
        git(self.remote, "update-ref", "-d", "refs/heads/people/P17/greeting")
        fresh = self.base / "Fresh"
        git(self.base, "-c", "core.autocrlf=false", "clone", str(self.remote), str(fresh))
        call(fresh, "identity", person="P17")
        status = call(fresh, "status")
        self.assertIn(change["change_id"], [e.get("change_id") for e in status["new_events"]])
        self.assertTrue((fresh / ".group/events" / (change["event"]["event_id"] + ".json")).exists())
        self.assertFalse((fresh / ".group/local/sync.json").exists())
        for e in Repository(fresh).events():
            for related in e["related_events"]:
                self.assertTrue((fresh / ".group/events" / (related + ".json")).exists())
        inspected = call(fresh, "inspect", change=change["change_id"])
        self.assertTrue(inspected["already_incorporated"])

    def test_other_group_verification_branches_do_not_mix_event_graphs(self):
        config = self.b / ".group/group.json"
        value = read_json(config)
        value["group_id"] = "G-unrelated-fixture"
        write_json(config, value)
        git(self.b, "add", ".group/group.json")
        git(self.b, "commit", "-m", "Independent verification group fixture")
        r = Repository(self.b)
        foreign = r.publish(r.event("finding", {"summary": "Other group's evidence", "evidence": []}))
        mine = Repository(self.a)
        mine.fetch()
        self.assertNotIn(foreign["event_id"], {e["event_id"] for e in mine.events()})
        with self.assertRaisesRegex(GroupError, "Broken"):
            mine.publish(mine.event("finding", {"summary": "Cross-group reference refused", "evidence": []}, [foreign["event_id"]]))

    def test_new_blocker_arriving_during_confirmation_prevents_publication(self):
        git(self.a, "switch", "main")
        prepared = call(self.a, "final_prepare", result="Base", dispositions=None,
                        limitation=[], human_check=[], human_evidence=[])
        def concurrent_fixture(*_):
            peer = Repository(self.b)
            peer.publish(peer.event("blocker", {"summary": "New requirement during confirmation", "blocking_change_id": "C-new",
                                               "requested_action": "Review before finalizing"}))
            return {"kind": "simulation", "statement": "Fixture only"}
        with patch("groupctl.finalization.confirm_candidate", side_effect=concurrent_fixture):
            with self.assertRaisesRegex(GroupError, "state changed during"):
                call(self.a, "final_publish", candidate=prepared["candidate_id"], confirm=True)
        self.assertFalse((self.a / ".group/final/final.json").exists())

    def test_code_commit_during_confirmation_cannot_reuse_old_test_evidence(self):
        git(self.a, "switch", "main")
        prepared = call(self.a, "final_prepare", result="Base", dispositions=None,
                        limitation=[], human_check=[], human_evidence=[])
        def concurrent_fixture(*_):
            (self.a / "concurrent.py").write_text("VALUE = 2\n", encoding="utf-8")
            git(self.a, "add", "concurrent.py")
            git(self.a, "commit", "-m", "Concurrent source update fixture")
            git(self.a, "push", "origin", "main")
            return {"kind": "simulation", "statement": "Fixture only"}
        with patch("groupctl.finalization.confirm_candidate", side_effect=concurrent_fixture):
            with self.assertRaisesRegex(GroupError, "state changed during"):
                call(self.a, "final_publish", candidate=prepared["candidate_id"], confirm=True)
        self.assertTrue((self.a / "concurrent.py").exists())
        self.assertFalse((self.a / ".group/final/final.json").exists())

    def test_historical_diff_preserves_multi_commit_contribution_after_merge(self):
        (self.a / "first.py").write_text("FIRST = 1\n", encoding="utf-8")
        git(self.a, "add", "first.py")
        git(self.a, "commit", "-m", "First part of one contribution")
        (self.a / "second.py").write_text("SECOND = 2\n", encoding="utf-8")
        change = self.publish(self.a, "Two-commit contribution")
        before = call(self.b, "inspect", change=change["change_id"])
        self.assertIn("FIRST = 1", before["diff"])
        self.assertIn("SECOND = 2", before["diff"])
        self.integrate(self.b, change["change_id"])
        git(self.b, "switch", "main")
        git(self.b, "merge", "--no-edit", "people/P22/work")
        git(self.b, "push", "origin", "main")
        after = call(self.b, "inspect", change=change["change_id"])
        self.assertTrue(after["already_incorporated"])
        self.assertEqual(after["diff"], before["diff"])
        self.assertEqual(after["base"], change["event"]["base_commit"])
        self.assertEqual(after["diff_base_source"], "published_base")
        # Protocol 0.1 legacy events are still accepted, with an explicit fallback warning.
        r = Repository(self.b)
        legacy = dict(change["event"])
        legacy.pop("base_commit")
        with patch.object(Repository, "change", return_value=legacy):
            inspected = call(self.b, "inspect", change=legacy["change_id"])
        self.assertIn("SECOND = 2", inspected["diff"])
        self.assertEqual(inspected["diff_base_source"], "legacy_first_parent")
        self.assertIn("Legacy", inspected["warning"])

    def test_event_mutation_introduced_only_in_merge_commit_is_rejected(self):
        r = Repository(self.a)
        event = r.publish(r.event("finding", {"summary": "Original immutable fact", "evidence": []}))
        branch = r.branch
        git(self.a, "switch", "-c", "side-fixture")
        (self.a / "side.txt").write_text("side", encoding="utf-8")
        git(self.a, "add", "side.txt")
        git(self.a, "commit", "-m", "Side fixture")
        git(self.a, "switch", branch)
        (self.a / "other.txt").write_text("other", encoding="utf-8")
        git(self.a, "add", "other.txt")
        git(self.a, "commit", "-m", "Other fixture")
        git(self.a, "merge", "--no-commit", "--no-ff", "side-fixture")
        event["summary"] = "Tampered ONLY in merge commit"
        write_json(self.a / ".group/events" / (event["event_id"] + ".json"), event)
        git(self.a, "add", ".group/events")
        git(self.a, "commit", "-m", "Deliberate merge-only event rewrite fixture")
        git(self.a, "push", "origin", "HEAD")
        with self.assertRaisesRegex(GroupError, "modifications/deletions"):
            Repository(self.a).events()
        # Another independent clone must reject the same public history too.
        peer = Repository(self.b)
        peer.fetch()
        with self.assertRaisesRegex(GroupError, "modifications/deletions"):
            peer.events()
