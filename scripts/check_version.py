"""Check single-source version, release documents, and an optional exact Git tag."""
import argparse
import ast
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def version():
    tree = ast.parse((ROOT / "groupctl/__init__.py").read_text(encoding="utf-8"))
    return next(ast.literal_eval(node.value) for node in tree.body
                if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "__version__" for t in node.targets))


def check(tag=None):
    value = version()
    assert re.fullmatch(r"\d+\.\d+\.\d+", value), "Expected a stable three-component version"
    project = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'dynamic = ["version"]' in project and 'version = {attr = "groupctl.__version__"}' in project
    assert f"工具版本 {value}" in (ROOT / "README.md").read_text(encoding="utf-8")
    assert f"## [{value}]" in (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert (ROOT / f"docs/releases/v{value}.md").is_file()
    if tag:
        assert tag == "v" + value, f"Tag {tag!r} does not match package {value}"
        def git(*args):
            return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()
        assert git("rev-parse", "HEAD") == git("rev-parse", f"refs/tags/{tag}^{{commit}}"), "HEAD is not the exact tagged commit"
    print(f"Version consistency OK: {value}" + (f" ({tag}, exact HEAD)" if tag else ""))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag")
    check(parser.parse_args().tag)
