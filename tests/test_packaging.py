import importlib.util
import subprocess
import sys
import unittest
from pathlib import Path

from groupctl import __version__

ROOT = Path(__file__).resolve().parents[1]


class PackagingTests(unittest.TestCase):
    def test_version_checker_and_cli_share_single_version(self):
        result = subprocess.run([sys.executable, str(ROOT / "scripts/check_version.py")], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        cli = subprocess.check_output([sys.executable, "-m", "groupctl", "--version"], cwd=ROOT, text=True).strip()
        self.assertEqual(cli, __version__)

    def test_wrong_tag_is_rejected(self):
        result = subprocess.run([sys.executable, str(ROOT / "scripts/check_version.py"), "--tag", "v0.0.0"], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("does not match", result.stderr)

    def test_installed_smoke_and_archive_checker_are_in_sdist_manifest(self):
        manifest = (ROOT / "MANIFEST.in").read_text(encoding="utf-8")
        self.assertIn("recursive-include scripts *.py", manifest)
        self.assertIn("recursive-include tests *.py", manifest)
        for name in ("check_artifacts", "installed_smoke", "check_version"):
            self.assertIsNotNone(importlib.util.spec_from_file_location(name, ROOT / f"scripts/{name}.py"))
