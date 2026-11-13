import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from groupctl.core import GroupError
from groupctl.validation import run_checks, parse_counts


class ValidationTests(unittest.TestCase):
    def test_missing_commands_and_empty_unittest_are_not_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "tests").mkdir()
            self.assertEqual(run_checks(tmp, [])["automated_result"], "not_available")
            empty = run_checks(tmp, [[sys.executable, "-m", "unittest", "discover", "-s", "tests"]])
            self.assertEqual(empty["automated_result"], "not_available")
            self.assertEqual(empty["results"][0]["counts"], [0, 0, 0])

    def test_exit_failure_missing_program_and_timeout_are_distinct(self):
        with tempfile.TemporaryDirectory() as tmp:
            failed = run_checks(tmp, [[sys.executable, "-c", "raise SystemExit(7)"]])
            missing = run_checks(tmp, [["groupctl-definitely-not-installed-13579"]])
            timed = run_checks(tmp, [[sys.executable, "-c", "import time;time.sleep(2)"]], timeout=0.03)
            self.assertEqual(failed["automated_result"], "fail")
            self.assertEqual(failed["results"][0]["exit_code"], 7)
            self.assertEqual(missing["automated_result"], "partial")
            self.assertEqual(timed["automated_result"], "partial")
            self.assertIsNone(timed["results"][0]["exit_code"])

    def test_interpreter_placeholder_and_unknown_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            checks = run_checks(tmp, [["{python}", "-c", "print('build checked')"]])
            self.assertEqual(checks["automated_result"], "pass")
            self.assertEqual(checks["results"][0]["argv"][0], sys.executable)
            self.assertIsNone(checks["results"][0]["counts"])

    def test_commands_are_argument_arrays_without_shell_interpretation(self):
        with tempfile.TemporaryDirectory() as tmp:
            checks = run_checks(tmp, [[sys.executable, "-c", "import sys;print(sys.argv[1])", "literal;$(echo unsafe)"]])
            self.assertEqual(checks["results"][0]["stdout"].strip(), "literal;$(echo unsafe)")
            for invalid in ("python test.py", [[]], [[1]], ["python"]):
                with self.subTest(invalid=invalid), self.assertRaises(GroupError):
                    run_checks(tmp, invalid)

    def test_counts_from_independent_runner_outputs(self):
        self.assertEqual(parse_counts("Ran 7 tests in 0.01s\nFAILED (failures=1, errors=1, skipped=2)"), (3, 2, 2))
        self.assertEqual(parse_counts("=== 3 passed, 2 failed, 1 skipped in 0.3s ==="), (3, 2, 1))
        self.assertIsNone(parse_counts("Application prints 99 passed"))

    def test_skipped_only_suite_is_incomplete_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            tests = Path(tmp) / "tests"
            tests.mkdir()
            (tests / "test_skipped.py").write_text("import unittest\n@unittest.skip('environment missing')\nclass T(unittest.TestCase):\n def test_required(self): pass\n", encoding="utf-8")
            result = run_checks(tmp, [[sys.executable, "-m", "unittest", "discover", "-s", "tests"]])
            self.assertEqual(result["automated_result"], "partial")
