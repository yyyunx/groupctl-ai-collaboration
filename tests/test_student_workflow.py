"""Student journeys against disposable repos, never the tool's production remote."""
import argparse
import json
import subprocess
import sys

from groupctl import commands, onboarding
from groupctl.core import Repository, GroupError
from test_groupctl import GitFixture, call, git, ROOT
from test_product_features import index_bytes
from test_product_features import view, talk
from groupctl.communication import assessment_input


def cli(path, *args):
    return subprocess.run([sys.executable, "-m", "groupctl", "--repo", str(path), *args],
                          cwd=ROOT, capture_output=True, text=True, encoding="utf-8")


class StudentOnboardingTests(GitFixture):
    def fresh(self, name="Fresh"):
        path = self.base / name
        git(self.base, "clone", str(self.remote), str(path))
        git(path, "config", "user.name", name)
        git(path, "config", "user.email", "fixture@example.invalid")
        return path

    def test_returning_member_resumes_in_one_command_without_registering_or_pushing(self):
        fresh = self.fresh()
        remote_before = git(self.remote, "show-ref")
        failed = cli(fresh, "join", "--person", "P22")
        self.assertEqual(failed.returncode, 1)
        self.assertIn("--resume", json.loads(failed.stderr)["hint"])
        self.assertEqual(git(fresh, "branch", "--show-current"), "main")
        other_topic = cli(fresh, "join", "--person", "P22", "--topic", "other")
        self.assertEqual(other_topic.returncode, 1)
        self.assertEqual(git(fresh, "branch", "--show-current"), "main")
        result = cli(fresh, "join", "--resume", "--person", "P22")
        self.assertEqual(result.returncode, 0, result.stderr)
        head = git(fresh, "rev-parse", "HEAD")
        self.assertEqual(head, git(self.b, "rev-parse", "HEAD"))
        self.assertEqual(Repository(fresh).identity(), "P22")
        again = cli(fresh, "join", "--resume", "--person", "P22")
        self.assertEqual(again.returncode, 0, again.stderr)
        self.assertEqual(git(fresh, "rev-parse", "HEAD"), head)
        self.assertEqual(remote_before, git(self.remote, "show-ref"))
        self.assertEqual(cli(fresh, "context", "--offline", "--format", "json").returncode, 0)

    def test_resume_preserves_dirty_work_and_refuses_divergence_before_switch(self):
        fresh = self.fresh()
        (fresh / "draft.txt").write_text("unfinished")
        before = index_bytes(fresh)
        result = cli(fresh, "join", "--resume", "--person", "P22")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(index_bytes(fresh), before)
        self.assertEqual((fresh / "draft.txt").read_text(), "unfinished")
        (fresh / "draft.txt").unlink()
        self.assertEqual(cli(fresh, "join", "--resume", "--person", "P22").returncode, 0)
        (fresh / "local.txt").write_text("local")
        git(fresh, "add", "local.txt"); git(fresh, "commit", "-m", "Local work")
        (self.b / "remote.txt").write_text("remote")
        git(self.b, "add", "remote.txt"); git(self.b, "commit", "-m", "Remote work")
        git(self.b, "push", "origin", "HEAD")
        git(fresh, "switch", "main")
        result = cli(fresh, "join", "--resume", "--person", "P22")
        self.assertEqual(result.returncode, 1)
        self.assertIn("分歧", json.loads(result.stderr)["error"])
        self.assertEqual(git(fresh, "branch", "--show-current"), "main")

    def test_init_publish_presets_reduce_setup_steps_and_doctor_never_runs_tests(self):
        remote = self.base / "new.git"; remote.mkdir()
        git(remote, "init", "--bare", "--initial-branch=main")
        path = self.base / "NewTeam"
        git(self.base, "clone", str(remote), str(path))
        git(path, "config", "user.name", "New"); git(path, "config", "user.email", "new@example.invalid")
        (path / "README.md").write_text("Existing real project\n")
        git(path, "add", "README.md"); git(path, "commit", "-m", "Project baseline")
        result = cli(path, "init", "--group", "G-new", "--person", "P1", "--assignment", str(self.assignment),
                     "--checks", "unittest", "--publish")
        self.assertEqual(result.returncode, 0, result.stderr)
        value = json.loads(result.stdout)
        self.assertTrue(value["published"])
        self.assertFalse(value["tests_executed"])
        self.assertEqual(git(path, "branch", "--show-current"), "people/P1/work")
        self.assertEqual(Repository(path).config["validation_commands"], onboarding.CHECK_PRESETS["unittest"])
        self.assertEqual(git(remote, "show", "main:README.md"), "Existing real project")
        before = index_bytes(path), git(path, "show-ref"), git(remote, "show-ref")
        result = cli(path, "doctor", "--format", "json")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(json.loads(result.stdout)["network_used"])
        self.assertEqual(before, (index_bytes(path), git(path, "show-ref"), git(remote, "show-ref")))

    def test_doctor_explains_missing_identity_and_wrong_repo_without_mutating(self):
        fresh = self.fresh()
        before = index_bytes(fresh)
        result = cli(fresh, "doctor", "--format", "json")
        self.assertEqual(result.returncode, 2)
        checks = json.loads(result.stdout)["checks"]
        member = next(c for c in checks if c["check"] == "member")
        self.assertIn("join --resume", member["action"])
        self.assertEqual(index_bytes(fresh), before)
        result = cli(ROOT, "doctor")
        self.assertEqual(result.returncode, 2)
        self.assertIn("工具原始碼目錄", result.stdout)
        self.assertIn("--repo", result.stdout)

    def test_initialization_dirty_guard_and_failed_push_resume_without_duplicate_setup(self):
        remote = self.base / "setup.git"; remote.mkdir()
        git(remote, "init", "--bare", "--initial-branch=main")
        path = self.base / "Setup"
        git(self.base, "clone", str(remote), str(path))
        git(path, "config", "user.name", "Setup"); git(path, "config", "user.email", "setup@example.invalid")
        (path / "README.md").write_text("Baseline")
        git(path, "add", "README.md"); git(path, "commit", "-m", "Baseline")
        args = ("init", "--group", "G-setup", "--person", "P1", "--assignment", str(self.assignment), "--publish")
        (path / "draft.txt").write_text("Keep me")
        before = index_bytes(path)
        self.assertEqual(cli(path, *args).returncode, 1)
        self.assertFalse((path / ".group").exists())
        self.assertEqual(index_bytes(path), before)
        (path / "draft.txt").unlink()
        git(path, "remote", "set-url", "--push", "origin", str(self.base / "absent.git"))
        result = cli(path, *args)
        self.assertEqual(result.returncode, 1)
        self.assertIn("recover --retry-push", json.loads(result.stderr)["hint"])
        head = git(path, "rev-parse", "HEAD")
        git(path, "remote", "set-url", "--push", "origin", str(remote))
        self.assertEqual(cli(path, "recover", "--retry-push").returncode, 0)
        self.assertEqual(cli(path, "join", "--resume", "--person", "P1").returncode, 0)
        self.assertEqual(git(path, "rev-parse", "HEAD"), head)
        self.assertEqual(git(remote, "rev-parse", "main"), head)


class StudentDailyWorkflowTests(GitFixture):
    def test_inbox_tasks_explain_review_reply_and_read_does_not_complete_work(self):
        (self.a / "feature.py").write_text("VALUE = 1\n")
        change = self.publish(self.a, "Needs a real review")
        Repository(self.b).fetch()
        inbox = view(self.b, relevant=True)
        self.assertEqual(inbox["counts"]["reviews_requiring_attention"], 1)
        task = next(t for t in inbox["tasks"] if t["kind"] == "review_change")
        self.assertEqual(task["command"], ["inspect", change["change_id"]])
        self.assertIn("not_assignment", task["responsibility"])
        marked = view(self.b, mark_all_read=True)
        self.assertEqual(marked["counts"]["unread_events"], 0)
        self.assertEqual(marked["counts"]["reviews_requiring_attention"], 1)
        question = talk(self.a, "ask", text="Should the response use JSON?")["event"]
        Repository(self.b).fetch()
        inbox = view(self.b, type=["question"])
        reply = next(t for t in inbox["tasks"] if t["kind"] == "answer_question")
        self.assertEqual(reply["command"][1], question["question_id"])
        self.assertTrue(reply["requires_input"])
        result = cli(self.b, "inbox", "--offline", "--type", "question")
        self.assertIn(question["question_id"], result.stdout)
        talk(self.b, "answer", question=question["question_id"], text="Yes, JSON.")
        self.assertFalse(any(t["kind"] == "answer_question" for t in view(self.b)["tasks"]))
        pack = view(self.b, "context", max_chars=3000)
        self.assertEqual(pack["command_prefix"][:2], ["groupctl", "--repo"])
        self.assertIn("真正的人類確認", pack["agent_workflow"])

    def test_inline_review_and_semantic_assessment_keep_exact_commit_and_failure_guards(self):
        (self.a / "feature.py").write_text("VALUE = 1\n")
        change = self.publish(self.a, "Inline assessment target")
        base = ("review", change["change_id"], "--verdict", "accept", "--summary", "Inspected exact fixture diff")
        before = git(self.b, "rev-parse", "HEAD")
        missing = cli(self.b, *base)
        self.assertEqual(missing.returncode, 2)
        self.assertEqual(git(self.b, "rev-parse", "HEAD"), before)
        wrong = cli(self.b, *base, "--diff-inspected", "--inspected-commit", before)
        self.assertEqual(wrong.returncode, 1)
        self.assertEqual(git(self.b, "rev-parse", "HEAD"), before)
        result = cli(self.b, *base, "--diff-inspected", "--inspected-commit", change["event"]["commit"], "--evidence", "Exact source inspected")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["event"]["inspected_commit"], change["event"]["commit"])
        call(self.b, "integrate", change=change["change_id"])
        result = cli(self.b, "integrate-finish", "--semantic-review", "fail", "--reviewed-commit", git(self.b, "rev-parse", "HEAD"),
                     "--build", "not_applicable", "--summary", "Fixture semantic concern despite passing tests", "--resolution", "No textual conflict")
        self.assertEqual(result.returncode, 2, result.stderr)
        event = json.loads(result.stdout)["event"]
        self.assertEqual(event["result"], "failed")
        self.assertEqual(event["verification"], {"build": "not_applicable", "tests": "pass", "semantic_review": "fail"})

    def test_inline_assessments_refuse_mixed_json_and_secrets_before_publication(self):
        args = argparse.Namespace(file="unused.json", verdict="accept")
        with self.assertRaisesRegex(GroupError, "不能混用"):
            assessment_input(args, "review")
        args = argparse.Namespace(file=None, verdict="accept", inspected_commit="a" * 40, diff_inspected=True,
                                  summary="password=do-not-publish", issue=[], test_run=[], evidence=[])
        with self.assertRaisesRegex(GroupError, "secret"):
            assessment_input(args, "review")


class StudentRecoveryTests(GitFixture):
    def peer_clone(self):
        path = self.base / "PeerB"
        git(self.base, "clone", str(self.remote), str(path))
        git(path, "config", "user.name", "Peer B"); git(path, "config", "user.email", "peer@example.invalid")
        result = cli(path, "join", "--resume", "--person", "P22")
        self.assertEqual(result.returncode, 0, result.stderr)
        return path

    def test_recover_explains_behind_and_updates_only_after_explicit_clean_request(self):
        peer = self.peer_clone()
        (self.b / "remote.txt").write_text("Latest work")
        git(self.b, "add", "remote.txt"); git(self.b, "commit", "-m", "Team work advanced")
        git(self.b, "push", "origin", "HEAD")
        before = git(peer, "rev-parse", "HEAD")
        result = cli(peer, "recover", "--format", "json")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["remote_relation"], "behind")
        self.assertEqual(git(peer, "rev-parse", "HEAD"), before)
        (peer / "draft.txt").write_text("unfinished")
        index = index_bytes(peer)
        self.assertEqual(cli(peer, "recover", "--update").returncode, 1)
        self.assertEqual(index_bytes(peer), index)
        self.assertEqual((peer / "draft.txt").read_text(), "unfinished")
        (peer / "draft.txt").unlink()
        result = cli(peer, "recover", "--update", "--format", "json")
        self.assertEqual(result.returncode, 0, result.stderr)
        value = json.loads(result.stdout)
        self.assertEqual(value["remote_relation"], "synced")
        self.assertFalse(value["tests_executed"])
        self.assertEqual(value["commit"], git(self.b, "rev-parse", "HEAD"))
        self.assertEqual((peer / "remote.txt").read_text(), "Latest work")

    def test_recover_divergence_refuses_both_update_and_push_without_reset(self):
        peer = self.peer_clone()
        (self.b / "remote.txt").write_text("Remote work")
        git(self.b, "add", "remote.txt"); git(self.b, "commit", "-m", "Remote work")
        git(self.b, "push", "origin", "HEAD")
        (peer / "local.txt").write_text("Local work")
        git(peer, "add", "local.txt"); git(peer, "commit", "-m", "Local work")
        head, index = git(peer, "rev-parse", "HEAD"), index_bytes(peer)
        remote_head = git(self.remote, "rev-parse", "refs/heads/people/P22/work")
        result = cli(peer, "recover", "--format", "json")
        self.assertEqual(json.loads(result.stdout)["remote_relation"], "diverged")
        for arguments in (("--update",), ("--retry-push",), ("--offline", "--update")):
            result = cli(peer, "recover", *arguments)
            self.assertEqual(result.returncode, 1, result.stderr)
            self.assertEqual(git(peer, "rev-parse", "HEAD"), head)
            self.assertEqual(index_bytes(peer), index)
            self.assertEqual(git(self.remote, "rev-parse", "refs/heads/people/P22/work"), remote_head)
