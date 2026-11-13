import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run_cli(*arguments):
    return subprocess.run([sys.executable, "-m", "groupctl", *arguments], cwd=ROOT,
                          capture_output=True, text=True, encoding="utf-8")


class CliUsabilityTests(unittest.TestCase):
    def test_help_and_no_arguments_are_successful_and_list_commands(self):
        for arguments in ((), ("--help",)):
            result = run_cli(*arguments)
            self.assertEqual(result.returncode, 0)
            for command in ("sync", "pub", "integrate", "review", "test", "status", "final-prepare", "final-publish"):
                self.assertIn(command, result.stdout)

    def test_invalid_command_and_missing_arguments_return_usage_error(self):
        for arguments in (("does-not-exist",), ("review",), ("integrate",), ("final-publish",), ("pub",)):
            result = run_cli(*arguments)
            self.assertEqual(result.returncode, 2)
            self.assertIn("usage:", result.stderr)
            self.assertNotIn("Traceback", result.stderr)

    def test_bad_repository_is_structured_error_not_traceback(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_cli("--repo", tmp, "status")
            self.assertEqual(result.returncode, 1)
            error = json.loads(result.stderr)
            self.assertIn("error", error)
            self.assertEqual(error["exit_code"], 1)

    def test_version_and_status_format_validation(self):
        self.assertEqual(run_cli("--version").returncode, 0)
        result = run_cli("status", "--format", "unknown")
        self.assertEqual(result.returncode, 2)

    def test_all_stage_help_is_discoverable(self):
        for command in ("init", "join", "inspect", "sync", "pub", "review", "integrate", "integrate-finish",
                        "integrate-abort", "test", "status", "final-prepare", "final-publish", "event"):
            with self.subTest(command=command):
                result = run_cli(command, "--help")
                self.assertEqual(result.returncode, 0)
                self.assertIn("usage:", result.stdout)
