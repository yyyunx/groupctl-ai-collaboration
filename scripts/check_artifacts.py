"""Inspect both archives, validate metadata/resources, write or verify SHA256SUMS."""
import argparse
import email
import hashlib
import json
import os
import subprocess
import tarfile
import zipfile
from pathlib import Path

try:
    from .check_version import ROOT, version
except ImportError:
    from check_version import ROOT, version


def excluded_material():
    inventory = json.loads((ROOT / "docs/provenance/source-comparison.json").read_text(encoding="utf-8"))
    records = [record for reference in inventory["references"] for record in reference["exact_files"]
               if record["base_path"].startswith("spec/")]
    return {Path(record["base_path"]).name for record in records}, {record["sha256"] for record in records}


def reject_excluded_material(names, read, *, blocked_names=None, blocked_hashes=None):
    if blocked_names is None or blocked_hashes is None:
        blocked_names, blocked_hashes = excluded_material()
    for name in names:
        assert Path(name).name not in blocked_names, f"Excluded course document: {name}"
        content = read(name)
        digests = {hashlib.sha256(content).hexdigest(), hashlib.sha256(content.replace(b"\r\n", b"\n")).hexdigest()}
        assert not digests & blocked_hashes, f"Excluded course content: {name}"


def check_license(metadata, content):
    assert metadata["License-Expression"] == "MIT", "Expected SPDX MIT metadata"
    assert "LICENSE" in metadata.get_all("License-File", []), "License file not declared"
    assert content.decode("utf-8").replace("\r\n", "\n") == (ROOT / "LICENSE").read_text(encoding="utf-8")


def check_source_archive(path):
    def inspect(names, read):
        reject_excluded_material(names, read)
        licenses = [name for name in names if Path(name).name == "LICENSE" and len(Path(name).parts) <= 2]
        assert len(licenses) == 1, "Source archive must have exactly one root LICENSE"
        assert read(licenses[0]).decode("utf-8").replace("\r\n", "\n") == (ROOT / "LICENSE").read_text(encoding="utf-8")
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as archive:
            inspect([entry.filename for entry in archive.infolist() if not entry.is_dir()], archive.read)
    else:
        with tarfile.open(path) as archive:
            inspect([entry.name for entry in archive.getmembers() if entry.isfile()], lambda name: archive.extractfile(name).read())
    print("Source archive licensing/exclusion OK:", path)


def check(directory):
    wheels = list(directory.glob("*.whl"))
    sources = list(directory.glob("*.tar.gz"))
    assert len(wheels) == len(sources) == 1, "Expected exactly one wheel and one sdist"
    required = ["AGENTS.md", "CLAUDE.md", "GEMINI.md", "AGENT_COLLABORATION.md",
                "skill/SKILL.md", "skill/references/commands.md"]
    with zipfile.ZipFile(wheels[0]) as archive:
        names = archive.namelist()
        metadata = email.message_from_bytes(archive.read(next(n for n in names if n.endswith(".dist-info/METADATA"))))
        assert metadata["Name"] == "groupctl" and metadata["Version"] == version()
        assert metadata["Requires-Python"] == ">=3.10"
        assert metadata["Description-Content-Type"] == "text/markdown"
        check_license(metadata, archive.read(next(n for n in names if n.endswith(".dist-info/licenses/LICENSE"))))
        reject_excluded_material([n for n in names if not n.endswith("/")], archive.read)
        entries = archive.read(next(n for n in names if n.endswith(".dist-info/entry_points.txt"))).decode()
        assert "groupctl = groupctl.__main__:main" in entries
        for path in required:
            # The same Ubuntu-built wheel is verified on Windows checkouts,
            # where Git may use CRLF. Compare Markdown content independently
            # of checkout newlines; archive bytes are protected by SHA256SUMS.
            expected = (ROOT / "groupctl/agent_data" / path).read_text(encoding="utf-8")
            actual = archive.read("groupctl/agent_data/" + path).decode("utf-8").replace("\r\n", "\n")
            assert actual == expected, path
        assert not any(".group/" in n or "/tests/" in n or "/evidence/" in n for n in names)
    with tarfile.open(sources[0]) as archive:
        names = archive.getnames()
        prefix = f"groupctl-{version()}/"
        members = [member.name for member in archive.getmembers() if member.isfile()]
        reject_excluded_material(members, lambda name: archive.extractfile(name).read())
        assert not any(name.startswith(prefix + "spec/") for name in names), "Course spec directory must not enter sdist"
        metadata = email.message_from_bytes(archive.extractfile(prefix + "PKG-INFO").read())
        check_license(metadata, archive.extractfile(prefix + "LICENSE").read())
        for path in ["pyproject.toml", "README.md", "CHANGELOG.md", "scripts/installed_smoke.py",
                     "tests/test_agent_setup.py", "docs/LICENSING_REVIEW.md"] + ["groupctl/agent_data/" + p for p in required]:
            assert prefix + path in names, path
    return wheels + sources


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dist", type=Path, default=ROOT / "dist")
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--tag")
    parser.add_argument("--source-archive", type=Path, help="Also inspect the Git/GitHub source ZIP")
    args = parser.parse_args()
    archives = check(args.dist)
    if args.source_archive:
        check_source_archive(args.source_archive)
    provenance_path = args.dist / "RELEASE-PROVENANCE.json"
    if not args.verify:
        provenance_path.write_text(json.dumps({"version": version(), "tag": args.tag,
            "commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
            "run_id": os.environ.get("GITHUB_RUN_ID"),
            "workflow_ref": os.environ.get("GITHUB_WORKFLOW_REF")}, indent=2) + "\n", encoding="utf-8")
    provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    assert provenance["version"] == version()
    if args.tag:
        assert provenance["tag"] == args.tag
        head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
        assert provenance["commit"] == head, "Artifacts were built from another commit"
    # pathlib ordering is case-insensitive on Windows, case-sensitive on POSIX.
    # Sort filename strings explicitly so the manifest is identical on both.
    hashes = "".join(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}\n"
                     for p in sorted(archives + [provenance_path], key=lambda p: p.name))
    checksum = args.dist / "SHA256SUMS"
    if args.verify:
        assert checksum.read_text(encoding="utf-8") == hashes, "Artifact checksum mismatch"
    else:
        checksum.write_text(hashes, encoding="utf-8")
    print(hashes, end="")


if __name__ == "__main__":
    main()
