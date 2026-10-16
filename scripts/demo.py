"""Offline acceptance demo: three real clones sharing a real local Git remote.

Only this known fixture simulates a semantic decision and human confirmation.
The collaboration tool itself never auto-resolves arbitrary source conflicts.
"""
import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class Demo:
    def __init__(self, output):
        self.output = output.resolve()
        self.output.mkdir(parents=True, exist_ok=False)
        self.transcript = []
        self.env = {**os.environ, "PYTHONPATH": str(ROOT) + os.pathsep + os.environ.get("PYTHONPATH", ""),
                    "PYTHONIOENCODING": "utf-8"}

    def run(self, cwd, argv, ok=(0,)):
        result = subprocess.run(argv, cwd=cwd, env=self.env, capture_output=True,
                                text=True, encoding="utf-8", errors="replace")
        self.transcript.append({"cwd": str(cwd), "argv": argv, "exit_code": result.returncode,
                                "stdout": result.stdout, "stderr": result.stderr})
        self.save()
        if result.returncode not in ok:
            raise RuntimeError(f"Demo command failed: {argv}\n{result.stdout}\n{result.stderr}")
        return result.stdout.strip()

    def git(self, cwd, *args):
        return self.run(cwd, ["git", *args])

    def tool(self, cwd, *args, ok=(0,)):
        return json.loads(self.run(cwd, [sys.executable, "-m", "groupctl", "--repo", str(cwd), *args], ok=ok))

    def save(self):
        (self.output / "transcript.json").write_text(json.dumps(self.transcript, ensure_ascii=False, indent=2), encoding="utf-8")

    def json_file(self, name, value):
        path = self.output / name
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
        return str(path)

    def clone(self, name, person=None):
        path = self.output / name
        self.git(self.output, "clone", str(self.output / "remote.git"), str(path))
        self.git(path, "config", "user.name", name)
        self.git(path, "config", "user.email", name.lower() + "@example.invalid")
        self.git(path, "config", "core.autocrlf", "false")
        if person:
            self.tool(path, "join", "--person", person, "--name", name, "--topic", "work")
        return path

    def finish(self, target, resolution):
        commit = self.git(target, "rev-parse", "HEAD")
        assessment = self.json_file("semantic-" + commit[:12] + ".json", {
            "reviewed_commit": commit, "semantic_review": "pass", "build": "not_applicable",
            "summary": "DEMO FIXTURE: inspected greeting preservation, whitespace handling and independent addition helper.",
            "conflict_resolution_summary": resolution})
        return self.tool(target, "integrate-finish", "--file", assessment)

    def perform(self):
        remote = self.output / "remote.git"
        remote.mkdir()
        self.git(remote, "init", "--bare", "--initial-branch=main")
        a = self.clone("student-A")
        (a / "tests").mkdir()
        (a / "greet.py").write_text('def greet(name):\n    return "Hello " + name\n', encoding="utf-8")
        (a / ".gitignore").write_text("__pycache__/\n*.pyc\n", encoding="utf-8")
        (a / "tests/test_greet.py").write_text(
            'import unittest\nfrom greet import greet\nclass GreetingTest(unittest.TestCase):\n'
            '    def test_name(self):\n        self.assertIn("Ada", greet("Ada"))\n', encoding="utf-8")
        checks = self.json_file("checks.json", [[sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"]])
        self.tool(a, "init", "--group", "G-DEMO", "--person", "P17", "--name", "Student A",
                  "--assignment", str(ROOT / "examples/assignment.md"), "--checks-file", checks)
        self.git(a, "add", ".")
        self.git(a, "commit", "-m", "Initialize shared example project")
        self.git(a, "push", "-u", "origin", "main")
        self.git(a, "switch", "-c", "people/P17/greeting")
        b = self.clone("student-B", "P22")
        c = self.clone("student-C", "P31")
        print("[1/7] Three independent clones and personal branches created.", flush=True)

        (a / "greet.py").write_text('def greet(name):\n    return "Hello " + name.strip()\n', encoding="utf-8")
        with (a / "tests/test_greet.py").open("a", encoding="utf-8") as stream:
            stream.write('    def test_trim(self):\n        self.assertEqual(greet("  Ada  ").split()[-1], "Ada")\n'
                         '        self.assertFalse(greet("  Ada  ").endswith(" "))\n')
        change_a = self.tool(a, "pub", "--summary", "Trim surrounding name whitespace")
        (b / "numbers_lib.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
        (b / "tests/test_numbers.py").write_text(
            'import unittest\nfrom numbers_lib import add\nclass AdditionTest(unittest.TestCase):\n'
            '    def test_positive(self):\n        self.assertEqual(add(2, 3), 5)\n'
            '    def test_negative(self):\n        self.assertEqual(add(-2, 1), -1)\n', encoding="utf-8")
        change_b = self.tool(b, "pub", "--summary", "Add arithmetic helper with positive and negative tests")
        discovered = self.tool(b, "sync")
        assert change_a["change_id"] in [e.get("change_id") for e in discovered["new_events"]]
        inspected = self.tool(b, "inspect", change_a["change_id"])
        assert "strip()" in inspected["diff"]
        review = self.json_file("review.json", {"inspected_commit": change_a["event"]["commit"],
            "diff_inspected": True, "verdict": "accept", "summary": "DEMO FIXTURE: name preserved; whitespace is normalized.",
            "issues": [], "tests_run": [], "evidence": ["Inspected exact diff; combined tests follow."]})
        self.tool(b, "review", change_a["change_id"], "--file", review)
        print("[2/7] A/B independently published; B discovered and reviewed A's exact diff.", flush=True)

        normal = self.tool(b, "integrate", change_a["change_id"])
        assert normal["git_merged"]
        integration_a = self.finish(b, "No textual conflicts; preserved greeting and independent arithmetic behavior.")
        assert integration_a["event"]["result"] == "success"
        print("[3/7] Automatic Git merge followed by tests and explicit semantic assessment.", flush=True)

        (c / "greet.py").write_text('def greet(name):\n    return "Welcome " + name\n', encoding="utf-8")
        change_c = self.tool(c, "pub", "--summary", "Use a welcoming greeting")
        conflict = self.tool(b, "integrate", change_c["change_id"], ok=(0, 2))
        assert conflict["conflicts"] == ["greet.py"]
        # Known fixture decision: combine C's Welcome intent and A's stripping intent.
        (b / "greet.py").write_text('def greet(name):\n    return "Welcome " + name.strip()\n', encoding="utf-8")
        self.git(b, "add", "greet.py")
        self.git(b, "commit", "-m", "Resolve fixture conflict: Welcome plus whitespace normalization")
        integration_c = self.finish(b, "DEMO FIXTURE decision: preserved Welcome and whitespace normalization.")
        assert integration_c["event"]["result"] == "success"
        tested = self.tool(b, "test")
        assert tested["event"]["automated_result"] == "pass"
        print("[4/7] Genuine conflict detected, deliberately resolved, and combined tests passed.", flush=True)

        self.git(b, "switch", "main")
        self.git(b, "merge", "--no-edit", "people/P22/work")
        self.git(b, "push", "origin", "main")
        self.tool(c, "sync", "--update")
        canonical_test = self.tool(c, "test", "main")
        assert canonical_test["event"]["automated_result"] == "pass"
        print("[5/7] Verified combined work promoted to main; C independently tested main.", flush=True)

        prepared = self.tool(b, "final-prepare", "--result", "Greeting normalization, welcoming text, and tested arithmetic helper.")
        # This is a simulated confirmation in a generated teaching fixture only.
        final = self.tool(b, "final-publish", prepared["candidate_id"], "--confirm")
        self.tool(c, "sync", "--update")
        assert (c / ".group/final/final_report.md").exists()
        print("[6/7] Candidate report shown in transcript; simulated confirmation published final records.", flush=True)

        summary = {"mode": "offline local Git remote; NOT a GitHub-hosted demonstration",
            "human_confirmation": "simulated only in this generated fixture",
            "people": ["P17", "P22", "P31"], "changes": [x["change_id"] for x in (change_a, change_b, change_c)],
            "normal_integration": integration_a["event"]["result"], "conflicting_files": conflict["conflicts"],
            "conflict_integration": integration_c["event"]["result"], "test_result": tested["event"],
            "final": final["final"], "command_count": len(self.transcript),
            "paths": {"output": str(self.output), "final_report": str(b / ".group/final/final_report.md"),
                      "transcript": str(self.output / "transcript.json")}}
        self.json_file("summary.json", summary)
        print("[7/7] Complete. Evidence: " + str(self.output / "summary.json"), flush=True)
        return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    output = args.output or ROOT / "demo-output" / stamp
    Demo(output).perform()


if __name__ == "__main__":
    main()
