"""Student journeys against disposable repos, never the tool's production remote."""
import argparse
import json
import subprocess
import sys

from groupctl import commands, onboarding
from groupctl.core import Repository, GroupError
from test_groupctl import GitFixture, call, git, ROOT
from test_product_features import index_bytes


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
