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

from check_version import ROOT, version


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
        for path in ["pyproject.toml", "README.md", "CHANGELOG.md", "scripts/installed_smoke.py",
                     "tests/test_agent_setup.py", "docs/LICENSING_REVIEW.md"] + ["groupctl/agent_data/" + p for p in required]:
            assert prefix + path in names, path
    return wheels + sources


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dist", type=Path, default=ROOT / "dist")
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--tag")
    args = parser.parse_args()
    archives = check(args.dist)
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
