import argparse
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from groupctl import agent_setup
from groupctl.errors import GroupError

ROOT = Path(__file__).resolve().parents[1]


class AgentSetupTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.target = self.base / "team 專案 with spaces"

    def setup(self, **changes):
        args = dict(target=str(self.target), agent=None, dry_run=False, overwrite=False, confirm=False)
        args.update(changes)
        return agent_setup.setup(argparse.Namespace(**args))

    def test_preview_is_read_only_and_contains_actual_contents(self):
        result = self.setup(dry_run=True)
        self.assertFalse(self.target.exists())
        self.assertEqual(len(result["files"]), 10)
        self.assertFalse(result["network_used"])
        self.assertTrue(all(item["content"] for item in result["files"]))

    def test_default_install_all_agents_and_idempotent_repeat(self):
        result = self.setup()
        self.assertEqual(len(result["written"]), 10)
        for name in ("AGENTS.md", "CLAUDE.md", "GEMINI.md", "AGENT_COLLABORATION.md"):
            self.assertTrue((self.target / name).is_file())
        for directory in (".agents", ".claude", ".gemini"):
            self.assertTrue((self.target / directory / "skills/group-collaboration/references/commands.md").is_file())
        self.assertEqual(self.setup()["written"], [])
        self.assertFalse((self.target / ".group").exists())

    def test_agent_selection_has_shared_references_and_no_other_vendor_files(self):
        self.setup(agent=["claude", "claude"])
        self.assertTrue((self.target / "CLAUDE.md").is_file())
        self.assertTrue((self.target / ".agents/skills/group-collaboration/SKILL.md").is_file())
        self.assertFalse((self.target / "GEMINI.md").exists())
        self.assertFalse((self.target / "AGENTS.md").exists())
        # Selected entry points must not point at a missing AGENTS.md.
        text = (self.target / "CLAUDE.md").read_text(encoding="utf-8")
        self.assertNotIn("Read `AGENTS.md`", text)

    def test_conflicts_prevent_entire_install_and_preserve_bytes(self):
        self.target.mkdir()
        existing = self.target / "AGENTS.md"
        existing.write_bytes(b"user instructions\r\n")
        result = self.setup()
        self.assertEqual(result["conflicts"], ["AGENTS.md"])
        self.assertEqual(result["written"], [])
        self.assertEqual(list(self.target.iterdir()), [existing])
        self.assertEqual(existing.read_bytes(), b"user instructions\r\n")

    def test_replacement_requires_both_flags_and_creates_exact_backup(self):
        self.setup()
        existing = self.target / "AGENTS.md"
        existing.write_bytes(b"custom rules\r\n")
        for flags in (dict(overwrite=True), dict(confirm=True)):
            with self.assertRaises(GroupError):
                self.setup(**flags)
            self.assertEqual(existing.read_bytes(), b"custom rules\r\n")
        result = self.setup(overwrite=True, confirm=True)
        self.assertEqual(len(result["backups"]), 1)
        self.assertEqual((self.target / result["backups"][0]).read_bytes(), b"custom rules\r\n")
        self.assertEqual(self.setup()["written"], [])

    def test_overwrite_preview_does_not_backup_or_replace(self):
        self.setup()
        existing = self.target / "AGENTS.md"
        existing.write_text("mine", encoding="utf-8")
        result = self.setup(dry_run=True, overwrite=True, confirm=True)
        self.assertEqual(result["written"], [])
        self.assertEqual(result["backups"], [])
        self.assertEqual(existing.read_text(encoding="utf-8"), "mine")

    def test_file_in_parent_path_and_directory_conflicts_fail_before_writes(self):
        self.target.mkdir()
        (self.target / ".agents").write_text("file", encoding="utf-8")
        with self.assertRaises(GroupError):
            self.setup()
        self.assertFalse((self.target / "AGENTS.md").exists())
        (self.target / ".agents").unlink()
        (self.target / "AGENTS.md").mkdir()
        with self.assertRaises(GroupError):
            self.setup(overwrite=True, confirm=True)

    @unittest.skipIf(os.name == "nt", "Windows junctions are verified separately without symlink privilege")
    def test_symlinked_target_parent_and_files_never_followed(self):
        outside = self.base / "outside"
        outside.mkdir()
        self.target.symlink_to(outside, target_is_directory=True)
        with self.assertRaises(GroupError):
            self.setup(overwrite=True, confirm=True)
        self.assertEqual(list(outside.iterdir()), [])
        self.target.unlink()
        self.target.mkdir()
        (outside / "mine").write_text("mine", encoding="utf-8")
        (self.target / "AGENTS.md").symlink_to(outside / "mine")
        with self.assertRaises(GroupError):
            self.setup(overwrite=True, confirm=True)
        self.assertEqual((outside / "mine").read_text(encoding="utf-8"), "mine")

    @unittest.skipUnless(os.name == "nt", "Windows junction regression")
    def test_windows_junction_target_is_rejected(self):
        outside = self.base / "outside"
        outside.mkdir()
        subprocess.run(["cmd", "/c", "mklink", "/J", str(self.target), str(outside)], check=True, capture_output=True)
        try:
            with self.assertRaises(GroupError):
                self.setup(overwrite=True, confirm=True)
            self.assertEqual(list(outside.iterdir()), [])
        finally:
            self.target.rmdir()  # Remove only the junction, never recurse into its target.

    def test_cli_is_available_from_unrelated_cwd_and_relative_target(self):
        env = {**os.environ, "PYTHONPATH": str(ROOT)}
        result = subprocess.run([sys.executable, "-m", "groupctl", "agent-setup", "--target", "relative", "--agent", "gemini"],
                                cwd=self.base, env=env, capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.base / "relative/GEMINI.md").is_file())
        self.assertFalse(self.target.exists())

    def test_packaged_copies_match_canonical_procedures(self):
        pairs = {"AGENT_COLLABORATION.md": "AGENT_COLLABORATION.md",
                 "skill/SKILL.md": ".agents/skills/group-collaboration/SKILL.md",
                 "skill/references/commands.md": ".agents/skills/group-collaboration/references/commands.md"}
        for packaged, source in pairs.items():
            self.assertEqual((ROOT / "groupctl/agent_data" / packaged).read_text(encoding="utf-8"),
                             (ROOT / source).read_text(encoding="utf-8"))
