import argparse
import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

from groupctl import commands, recovery
from groupctl.collaboration import ObservedRepository
from groupctl.core import Repository, GroupError, write_json
from test_groupctl import GitFixture, call, git, ROOT
from test_product_features import index_bytes


def recover(path, **kwargs):
    return recovery.recover(argparse.Namespace(**({"repo": str(path), "offline": False,
        "retry_push": False, "resume_integration": None} | kwargs)))


def fingerprint(path, remote):
    return {"head": git(path, "rev-parse", "HEAD"), "index": index_bytes(path),
        "refs": git(path, "for-each-ref", "--format=%(refname) %(objectname)"),
        "remote_refs": git(remote, "for-each-ref", "--format=%(refname) %(objectname)"),
        "objects": sorted(p.relative_to(path).as_posix() for p in (path / ".git/objects").rglob("*") if p.is_file()),
        "work": {p.relative_to(path).as_posix(): p.read_bytes() for p in path.rglob("*")
                 if p.is_file() and ".git" not in p.relative_to(path).parts}}


class PreviewRecoveryTests(GitFixture):
    def test_pub_dry_run_is_strictly_read_only_and_never_runs_checks(self):
        (self.a / "greet.py").write_text('def greet(name):\n    return "Hi " + name\n', encoding="utf-8")
        before = fingerprint(self.a, self.remote)
        args = argparse.Namespace(repo=str(self.a), dry_run=True, summary=None)
        with patch.object(ObservedRepository, "fetch", side_effect=AssertionError("Preview fetched")), \
             patch.object(Repository, "check_commit", side_effect=AssertionError("Preview tested")):
            result = commands.pub(args)
        self.assertTrue(result["preview"])
        self.assertIn("greet.py", result["files_to_commit"])
        self.assertFalse(result["tests_executed"])
        self.assertEqual(before, fingerprint(self.a, self.remote))
        output = subprocess.run([sys.executable, "-m", "groupctl", "--repo", str(self.a), "pub", "--dry-run"],
                                cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(output.returncode, 0)
        self.assertTrue(json.loads(output.stdout)["preview"])

    def test_integration_preview_reports_only_potential_conflicts_without_writes(self):
        (self.a / "greet.py").write_text('def greet(name):\n    return "Hi " + name\n', encoding="utf-8")
        change = self.publish(self.a, "Incoming greeting")
        Repository(self.b).fetch()
        (self.b / "greet.py").write_text('def greet(name):\n    return "Welcome " + name\n', encoding="utf-8")
        before = fingerprint(self.b, self.remote)
        with patch.object(ObservedRepository, "fetch", side_effect=AssertionError("Preview fetched")):
            result = call(self.b, "integrate", change=change["change_id"], preview=True)
        self.assertEqual(result["target_commit"], change["event"]["commit"])
        self.assertEqual(result["potential_conflict_files"], ["greet.py"])
        self.assertIn("not_a_git_merge_result", result["conflict_assessment"])
        self.assertFalse(result["can_execute_without_preparation"])
        self.assertEqual(before, fingerprint(self.b, self.remote))

    def fail_event_push(self):
        git(self.a, "remote", "set-url", "--push", "origin", str(self.base / "missing.git"))
        r = Repository(self.a)
        event = r.event("finding", {"summary": "Completed useful investigation", "evidence": []})
        with self.assertRaisesRegex(GroupError, "NOT published"):
            r.publish(event)
        return event

    def test_recover_retries_same_commit_and_event_without_duplicates(self):
        event = self.fail_event_push()
        result = recover(self.a)
        self.assertEqual(result["unpublished_events"][0]["event_id"], event["event_id"])
        self.assertEqual(result["last_push_failure"]["phase"], "event_push")
        head, index = git(self.a, "rev-parse", "HEAD"), index_bytes(self.a)
        git(self.a, "remote", "set-url", "--push", "origin", str(self.remote))
        result = recover(self.a, retry_push=True)
        self.assertTrue(result["retry_confirmed"])
        self.assertEqual(git(self.a, "rev-parse", "HEAD"), head)
        self.assertEqual(index_bytes(self.a), index)
        self.assertEqual(len(list((self.a / ".group/events").glob("*.json"))), 1)
        result = recover(self.a, retry_push=True)
        self.assertIn("Already synchronized", result["actions"][0])
        self.assertEqual([e["event_id"] for e in Repository(self.a).events()], [event["event_id"]])

    def test_retry_refuses_remote_divergence_without_reset_or_force(self):
        self.fail_event_push()
        (self.b / "peer.py").write_text("PEER = True\n", encoding="utf-8")
        git(self.b, "add", "peer.py")
        git(self.b, "commit", "-m", "Concurrent branch fixture")
        git(self.b, "push", "origin", "HEAD:refs/heads/people/P17/greeting")
        git(self.a, "remote", "set-url", "--push", "origin", str(self.remote))
        before = git(self.a, "rev-parse", "HEAD")
        peer = git(self.b, "rev-parse", "HEAD")
        with self.assertRaisesRegex(GroupError, "diverged or advanced"):
            recover(self.a, retry_push=True)
        self.assertEqual(git(self.a, "rev-parse", "HEAD"), before)
        self.assertEqual(git(self.remote, "rev-parse", "refs/heads/people/P17/greeting"), peer)

    def test_recover_network_failure_is_honest_and_offline_retry_is_forbidden(self):
        self.fail_event_push()
        with patch.object(ObservedRepository, "fetch", side_effect=GroupError("password=network-secret")):
            result = recover(self.a)
        self.assertTrue(result["freshness"]["may_be_stale"])
        self.assertEqual(result["freshness"]["mode"], "offline")
        self.assertNotIn("network-secret", json.dumps(result))
        with self.assertRaisesRegex(GroupError, "fresh fetch"):
            recover(self.a, offline=True, retry_push=True)

    def test_recover_restores_missing_integration_record_from_exact_merge(self):
        (self.a / "greet.py").write_text('def greet(name):\n    return "Hi " + name\n', encoding="utf-8")
        change = self.publish(self.a, "Hi")
        (self.b / "greet.py").write_text('def greet(name):\n    return "Welcome " + name\n', encoding="utf-8")
        self.publish(self.b, "Welcome")
        result = call(self.b, "integrate", change=change["change_id"])
        self.assertTrue(result["conflicts"])
        record = self.b / ".group/local/integration.json"
        record.unlink()
        before = fingerprint(self.b, self.remote)
        resumed = recover(self.b, offline=True, resume_integration=change["change_id"])
        after = fingerprint(self.b, self.remote)
        for key in ("head", "index", "refs", "remote_refs", "objects"):
            self.assertEqual(before[key], after[key])
        self.assertEqual((self.b / "greet.py").read_bytes(), before["work"]["greet.py"])
        self.assertTrue(resumed["pending_integration"]["recovered_state"])
        (self.b / "greet.py").write_text('def greet(name):\n    return "Hi, welcome " + name\n', encoding="utf-8")
        git(self.b, "add", "greet.py")
        git(self.b, "commit", "-m", "Explicit fixture conflict resolution")
        final = call(self.b, "integrate_finish", file=str(self.semantic(self.b)))
        self.assertEqual(final["event"]["result"], "success")
        self.assertFalse(final["event"]["recovery"]["conflict_history_complete"])

    def test_recover_never_commits_uncommitted_event_or_dirty_source(self):
        r = Repository(self.a)
        event = r.event("finding", {"summary": "Uncommitted", "evidence": []})
        file = self.a / ".group/events" / (event["event_id"] + ".json")
        write_json(file, event)
        before = fingerprint(self.a, self.remote)
        result = recover(self.a, offline=True)
        self.assertIn(file.relative_to(self.a).as_posix(), result["uncommitted_event_files"])
        self.assertEqual(result["unpublished_events"], [])
        with self.assertRaisesRegex(GroupError, "not clean"):
            recover(self.a, retry_push=True)
        self.assertEqual(before["head"], git(self.a, "rev-parse", "HEAD"))
        self.assertEqual(before["index"], index_bytes(self.a))
        self.assertEqual(file.read_bytes(), before["work"][file.relative_to(self.a).as_posix()])

    def test_failed_source_push_is_distinct_from_an_unpublished_event(self):
        (self.a / "feature.py").write_text("VALUE = 1\n", encoding="utf-8")
        git(self.a, "remote", "set-url", "--push", "origin", str(self.base / "missing.git"))
        with self.assertRaises(GroupError):
            self.publish(self.a, "Source publication fixture")
        result = recover(self.a)
        self.assertEqual(result["last_push_failure"]["phase"], "source_push")
        self.assertEqual(result["unpublished_events"], [])
        self.assertTrue(result["source_needs_announcement"])
