"""Reproducible similarity inventory; this is evidence, not a rights determination.

Reads Git blobs only. Emits paths, hashes and line spans, never third-party source.
Usage: python scripts/audit_sources.py --reference NAME=PATH@COMMIT ... --output FILE
"""
import argparse
import difflib
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args])


def snapshot(root, commit):
    paths = git(root, "ls-tree", "-r", "--name-only", commit).decode().splitlines()
    result = {}
    for path in paths:
        if path.startswith((".group/", "evidence/", ".git/")) or Path(path).suffix not in (".py", ".md", ".toml", ".ps1"):
            continue
        result[path] = git(root, "show", f"{commit}:{path}")
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="0c74f16")
    parser.add_argument("--reference", action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    base_sha = git(ROOT, "rev-parse", args.base).decode().strip()
    own = snapshot(ROOT, base_sha)
    report = {"base": base_sha, "method": "Exact blobs and >=6 contiguous nonblank whitespace-normalized lines totaling >=240 characters; compare same file suffix, excluding .group and evidence. Similarity does not establish copying or permission. No third-party source excerpts emitted.", "references": []}
    for argument in args.reference:
        name, location = argument.split("=", 1)
        path, commit = location.rsplit("@", 1)
        other = snapshot(Path(path), commit)
        result = {"name": name, "commit": git(path, "rev-parse", commit).decode().strip(),
                  "files_examined": len(other), "license_paths": git(path, "ls-tree", "-r", "--name-only", commit).decode().splitlines(),
                  "exact_files": [], "matching_blocks": []}
        result["license_paths"] = [p for p in result["license_paths"] if any(s in Path(p).name.lower() for s in ("license", "licence", "copying", "notice"))]
        for a, raw_a in own.items():
            for b, raw_b in other.items():
                if Path(a).suffix != Path(b).suffix:
                    continue
                if raw_a == raw_b:
                    result["exact_files"].append({"base_path": a, "reference_path": b, "sha256": hashlib.sha256(raw_a).hexdigest()})
                    continue
                def lines(raw):
                    return [(n, " ".join(line.split())) for n, line in enumerate(raw.decode("utf-8-sig", errors="replace").splitlines(), 1) if line.strip()]
                la, lb = lines(raw_a), lines(raw_b)
                for block in difflib.SequenceMatcher(None, [v for _, v in la], [v for _, v in lb], autojunk=False).get_matching_blocks():
                    length = sum(len(v) for _, v in la[block.a:block.a + block.size])
                    if block.size >= 6 and length >= 240:
                        result["matching_blocks"].append({"base_path": a, "reference_path": b,
                            "base_start": la[block.a][0], "reference_start": lb[block.b][0],
                            "nonblank_lines": block.size, "characters": length})
        report["references"].append(result)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for result in report["references"]:
        print(result["name"], "exact files:", len(result["exact_files"]), "matching blocks:", len(result["matching_blocks"]), "licenses:", result["license_paths"])


if __name__ == "__main__":
    main()
