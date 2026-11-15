"""Install each built artifact in a fresh venv and exercise real CLI paths off-repo.

No PYTHONPATH or source imports. The sdist install also proves its build inputs work.
All Git writes and identities are confined to disposable local fixtures.
"""
import argparse
import json
import os
import subprocess
import tempfile
import venv
from pathlib import Path

from check_version import ROOT, version


def run(argv, cwd, env, ok=(0,)):
    result = subprocess.run([str(a) for a in argv], cwd=cwd, env=env, capture_output=True,
                            text=True, encoding="utf-8", errors="replace", timeout=300)
    if result.returncode not in ok:
        raise RuntimeError(f"{argv}: exit {result.returncode}\n{result.stdout}\n{result.stderr}")
    return result.stdout.strip()


def verify(artifact):
    with tempfile.TemporaryDirectory(prefix="groupctl-installed-") as temporary:
        base = Path(temporary)
        environment = base / "venv"
        venv.EnvBuilder(with_pip=True).create(environment)
        bin_dir = environment / ("Scripts" if os.name == "nt" else "bin")
        python = bin_dir / ("python.exe" if os.name == "nt" else "python")
        cli = bin_dir / ("groupctl.exe" if os.name == "nt" else "groupctl")
        env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "PYTHONHOME")}
        env.update(PYTHONUTF8="1", PYTHONIOENCODING="utf-8", GIT_TERMINAL_PROMPT="0",
                   GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1")
        run([python, "-m", "pip", "install", "--disable-pip-version-check", artifact], base, env)
        assert run([cli, "--version"], base, env) == version()
        assert run([python, "-I", "-c", "import groupctl, importlib.metadata as m; assert groupctl.__version__ == m.version('groupctl'); print(groupctl.__file__)"], base, env).startswith(str(environment))
        assert run([python, "-I", "-m", "groupctl", "--version"], base, env) == version()
        # Outside any Git checkout: structured diagnosis/errors, never an import error.
        assert not json.loads(run([cli, "doctor", "--format", "json"], base, env, ok=(2,)))["ready"]
        target = base / "team 專案 with spaces"
        preview = json.loads(run([cli, "agent-setup", "--target", target, "--dry-run"], base, env))
        assert preview["dry_run"] and not target.exists()
        installed = json.loads(run([cli, "agent-setup", "--target", target], base, env))
        assert len(installed["written"]) == 10
        assert not json.loads(run([cli, "agent-setup", "--target", "."], target, env))["written"]
        (target / "AGENTS.md").write_text("User rules\n", encoding="utf-8")
        assert json.loads(run([cli, "agent-setup", "--target", target], base, env, ok=(2,)))["conflicts"] == ["AGENTS.md"]
        assert (target / "AGENTS.md").read_text(encoding="utf-8") == "User rules\n"
        def git(cwd, *args):
            return run(["git", *args], cwd, env)
        remote = base / "remote.git"
        git(base, "init", "--bare", "--initial-branch=main", str(remote))
        git(target, "init", "--initial-branch=main")
        git(target, "config", "user.name", "Installed fixture")
        git(target, "config", "user.email", "installed@example.invalid")
        git(target, "config", "core.autocrlf", "false")
        git(target, "remote", "add", "origin", str(remote))
        (target / "assignment.md").write_text("Installed CLI verification fixture.\n", encoding="utf-8")
        (target / "tests").mkdir()
        (target / "tests/test_ready.py").write_text("import unittest\nclass Ready(unittest.TestCase):\n    def test_ready(self): self.assertEqual(2 + 2, 4)\n", encoding="utf-8")
        git(target, "add", ".")
        git(target, "commit", "-m", "Installed CLI fixture")
        # Absolute --repo works from an unrelated CWD, and assignment is relative to CWD.
        run([cli, "--repo", target, "init", "--group", "G-installed", "--person", "P1",
             "--assignment", target / "assignment.md", "--checks", "unittest", "--publish"], base, env)
        for cwd, prefix in ((base, [cli, "--repo", target]), (target, [cli])):
            diagnosis = json.loads(run([*prefix, "doctor", "--format", "json"], cwd, env))
            assert diagnosis["ready"] and not diagnosis["network_used"]
            context = json.loads(run([*prefix, "context", "--offline", "--format", "json"], cwd, env))
            assert context
            assert json.loads(run([*prefix, "inbox", "--offline", "--format", "json"], cwd, env))
        assert not git(target, "status", "--porcelain"), "Read-only commands changed tracked project state"
        print(f"Installed artifact OK: {artifact.name}; fresh venv, off-repo CLI, all agents, protected conflicts, doctor/context/inbox")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dist", type=Path, default=ROOT / "dist")
    args = parser.parse_args()
    artifacts = sorted(args.dist.resolve().glob("*.whl")) + sorted(args.dist.resolve().glob("*.tar.gz"))
    assert len(artifacts) == 2, "Expected wheel and sdist"
    for artifact in artifacts:
        verify(artifact)
