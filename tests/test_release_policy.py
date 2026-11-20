import hashlib
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from scripts.check_artifacts import ROOT, check_source_archive, excluded_material, reject_excluded_material


class ReleasePolicyTests(unittest.TestCase):
    def test_known_eight_course_documents_are_absent_from_release_tree(self):
        names, hashes = excluded_material()
        self.assertEqual(len(names), 8)
        self.assertEqual(len(hashes), 8)
        for name in names:
            self.assertFalse((ROOT / "spec" / name).exists())
        self.assertIn("prune spec", (ROOT / "MANIFEST.in").read_text(encoding="utf-8"))

    def test_exclusion_rejects_original_names_and_renamed_identical_content(self):
        payload = b"Independent fixture standing in for excluded material.\n"
        digest = hashlib.sha256(payload).hexdigest()
        for files in ({"spec/course.md": b"different"}, {"docs/renamed.md": payload}):
            with self.subTest(files=tuple(files)), self.assertRaises(AssertionError):
                reject_excluded_material(files, files.__getitem__, blocked_names={"course.md"}, blocked_hashes={digest})
        files = {"docs/overview.md": b"Our independently written summary."}
        reject_excluded_material(files, files.__getitem__, blocked_names={"course.md"}, blocked_hashes={digest})

    def test_source_archive_checks_license_and_rejects_excluded_path(self):
        name = sorted(excluded_material()[0])[0]
        with tempfile.TemporaryDirectory() as temporary:
            archive = Path(temporary) / "source.zip"
            with zipfile.ZipFile(archive, "w") as output:
                output.writestr("groupctl/LICENSE", (ROOT / "LICENSE").read_bytes())
                output.writestr("groupctl/docs/overview.md", "Own summary")
            check_source_archive(archive)
            with zipfile.ZipFile(archive, "a") as output:
                output.writestr("groupctl/spec/" + name, "Excluded name even with changed bytes")
            with self.assertRaises(AssertionError):
                check_source_archive(archive)

    def test_github_authorization_does_not_authorize_pypi(self):
        state = json.loads((ROOT / "docs/publishing-state.json").read_text(encoding="utf-8"))
        self.assertTrue(state["redistribution_approved"])
        self.assertTrue(state["github_publication_approved"])
        self.assertFalse(state["pypi_publication_approved"])
        self.assertEqual(state["license"], "MIT")
        workflow = (ROOT / ".github/workflows/publish-pypi.yml").read_text(encoding="utf-8")
        self.assertEqual(workflow.count('["pypi_publication_approved"]'), 2)
