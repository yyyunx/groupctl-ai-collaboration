"""15-step acceptance simulation. Optional remote creates new verification branches.
Review decisions and confirmation are fixtures, NEVER actual human feedback.
"""
import argparse
import json
import os
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class Demo:
    def __init__(self, output, remote=None, base_ref="origin/synthesis/groupctl-final"):
        self.output = output.resolve()
        self.output.mkdir(parents=True, exist_ok=False)
        self.remote, self.base_ref = remote, base_ref
        self.run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:6]
        self.canonical = f"synthesis/verification/{self.run_id}" if remote else "main"
        self.people = [f"SYN-{self.run_id}-{p}" for p in ("P17", "P22", "P31")] if remote else ["P17", "P22", "P31"]
        self.group = "G-" + self.run_id if remote else "G-DEMO"
        self.transcript, self.steps, self.branches = [], [], []
        self.env = {**os.environ, "PYTHONPATH": str(ROOT) + os.pathsep + os.environ.get("PYTHONPATH", ""),
                    "PYTHONIOENCODING": "utf-8", "GIT_TERMINAL_PROMPT": "0"}
        self.source = "collaboration_fixture/" if remote else ""
        self.tests = "collaboration_fixture_tests" if remote else "tests"
        self.remote_url = remote or str(self.output / "remote.git")

    def run(self, cwd, argv, ok=(0,)):
        result = subprocess.run(argv, cwd=cwd, env=self.env, capture_output=True,
                                text=True, encoding="utf-8", errors="replace", timeout=300)
        self.transcript.append({"cwd": str(cwd), "argv": argv, "exit_code": result.returncode,
                                "stdout": result.stdout, "stderr": result.stderr})
        self.json_file("transcript.json", self.transcript)
        if result.returncode not in ok:
            raise RuntimeError(f"Demo command failed: {argv}\n{result.stdout}\n{result.stderr}")
        return result.stdout.strip()

    def git(self, cwd, *args):
        return self.run(cwd, ["git", "-c", "credential.interactive=never", *args])

    def tool(self, cwd, *args, ok=(0,)):
        return json.loads(self.run(ROOT, [sys.executable, "-m", "groupctl", "--repo", str(cwd), *args], ok=ok))

    def mark(self, number, name, evidence):
        if number != len(self.steps) + 1:
            raise RuntimeError("Acceptance steps must be recorded in order")
        self.steps.append({"step": number, "name": name, "result": "pass", "evidence": evidence})
        self.json_file("acceptance.json", self.steps)
        print(f"[{number}/15] {name}", flush=True)

    def json_file(self, name, value):
        path = self.output / name
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return str(path)

    def clone(self, name, person=None):
        path = self.output / name
        self.git(self.output, "-c", "core.autocrlf=false", "clone", self.remote_url, str(path))
        self.git(path, "config", "user.name", name)
        self.git(path, "config", "user.email", name.lower() + "@example.invalid")
        self.git(path, "config", "core.autocrlf", "false")
        if person:
            self.git(path, "switch", "--detach", "origin/" + self.canonical)
            result = self.tool(path, "join", "--person", person, "--name", name, "--topic", "work")
            self.branches.append(result["branch"])
        return path

    def finish(self, target, resolution):
        commit = self.git(target, "rev-parse", "HEAD")
        assessment = self.json_file("semantic-" + commit[:12] + ".json", {
            "reviewed_commit": commit, "semantic_review": "pass", "build": "not_applicable",
            "summary": "SIMULATED fixture assessment: greeting, whitespace and arithmetic intents inspected.",
            "conflict_resolution_summary": resolution})
        result = self.tool(target, "integrate-finish", "--file", assessment)
        if result["event"]["result"] != "success":
            raise RuntimeError("Demo integration did not pass all verification layers")
        return result

    def perform(self):
        if not self.remote:
            remote = self.output / "remote.git"
            remote.mkdir()
            self.git(remote, "init", "--bare", "--initial-branch=main")
        a = self.clone("student-A")
        if self.remote:
            self.git(a, "switch", "-c", self.canonical, self.base_ref)
            if (a / ".group").exists():
                raise RuntimeError("Verification base already has .group; refusing to overwrite a real group")
        (a / self.tests).mkdir(exist_ok=True)
        (a / self.source).mkdir(exist_ok=True)
        greet, numbers = self.source + "greet.py", self.source + "numbers_lib.py"
        module = self.source.replace("/", ".")
        (a / greet).write_text('def greet(name):\n    return "Hello " + name\n', encoding="utf-8")
        with (a / ".gitignore").open("a", encoding="utf-8") as stream:
            stream.write("\n__pycache__/\n*.pyc\n")
        (a / self.tests / "test_greet.py").write_text(
            f'import unittest\nfrom {module}greet import greet\nclass GreetingTest(unittest.TestCase):\n'
            '    def test_name(self):\n        self.assertIn("Ada", greet("Ada"))\n', encoding="utf-8")
        checks = self.json_file("checks.json", [["{python}", "-m", "unittest", "discover", "-s", self.tests, "-v"]])
        self.tool(a, "init", "--group", self.group, "--person", self.people[0], "--name", "Student A",
                  "--canonical", self.canonical, "--simulation", "--assignment", str(ROOT / "examples/assignment.md"), "--checks-file", checks)
        self.git(a, "add", "--", ".group", ".gitignore", self.tests, greet)
        self.git(a, "commit", "-m", "Initialize isolated collaboration simulation fixture")
        self.git(a, "push", "-u", "origin", self.canonical)
        self.branches.append(self.canonical)
        a_branch = f"people/{self.people[0]}/greeting"
        self.git(a, "switch", "-c", a_branch)
        self.branches.append(a_branch)
        b, c = self.clone("student-B", self.people[1]), self.clone("student-C", self.people[2])
        self.mark(1, "Three independent clones share one Git remote", [str(a), str(b), str(c)])
        self.mark(2, "Each member has a separate personal branch", [self.git(p, "branch", "--show-current") for p in (a, b, c)])
        (a / greet).write_text('def greet(name):\n    return "Hello " + name.strip()\n', encoding="utf-8")
        with (a / self.tests / "test_greet.py").open("a", encoding="utf-8") as stream:
            stream.write('    def test_trim(self):\n        self.assertEqual(greet("  Ada  ").split()[-1], "Ada")\n'
                         '        self.assertFalse(greet("  Ada  ").endswith(" "))\n')
        (b / numbers).write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
        (b / self.tests / "test_numbers.py").write_text(
            f'import unittest\nfrom {module}numbers_lib import add\nclass AdditionTest(unittest.TestCase):\n'
            '    def test_positive(self):\n        self.assertEqual(add(2, 3), 5)\n'
            '    def test_negative(self):\n        self.assertEqual(add(-2, 1), -1)\n', encoding="utf-8")
        self.mark(3, "A and B implement independent changes", [self.git(a, "diff", "--stat"), self.git(b, "status", "--short")])
        change_a = self.tool(a, "pub", "--summary", "Trim surrounding name whitespace")
        self.mark(4, "A publishes code and an immutable event", change_a["event"])
        change_b = self.tool(b, "pub", "--summary", "Add arithmetic helper and positive/negative tests")
        discovered = self.tool(b, "sync")
        if change_a["change_id"] not in [e.get("change_id") for e in discovered["new_events"]]:
            raise RuntimeError("SYNC did not discover A")
        self.mark(5, "B discovers A through SYNC", [e["event_id"] for e in discovered["new_events"]])
        inspected = self.tool(b, "inspect", change_a["change_id"])
        if "strip()" not in inspected["diff"]:
            raise RuntimeError("The actual diff lacks the intended feature")
        assessment = self.json_file("review.json", {"inspected_commit": change_a["event"]["commit"], "diff_inspected": True,
            "verdict": "accept", "summary": "SIMULATED review: preserves name and normalizes whitespace.",
            "issues": [], "tests_run": [], "evidence": ["Exact diff inspected; combined checks follow."]})
        reviewed = self.tool(b, "review", change_a["change_id"], "--file", assessment)
        self.mark(6, "B reviews the actual diff without accepting by default", reviewed["event"])
        normal = self.tool(b, "integrate", change_a["change_id"])
        if not normal["git_merged"] or normal["accepted"]:
            raise RuntimeError("Git merge must not count as semantic acceptance")
        self.mark(7, "Git automatically merges a compatible case", normal["git_merged"])
        integrated_a = self.finish(b, "No textual conflicts; preserve both greeting and arithmetic features")
        self.mark(8, "Tests and semantic review separately verify integration", integrated_a["event"])
        (c / greet).write_text('def greet(name):\n    return "Welcome " + name\n', encoding="utf-8")
        change_c = self.tool(c, "pub", "--summary", "Use a welcoming greeting")
        conflict = self.tool(b, "integrate", change_c["change_id"], ok=(2,))
        if conflict["conflicts"] != [greet]:
            raise RuntimeError("The intended genuine Git conflict was not detected")
        self.mark(9, "Overlapping changes produce a genuine Git conflict", conflict["conflicts"])
        (b / greet).write_text('def greet(name):\n    return "Welcome " + name.strip()\n', encoding="utf-8")
        self.git(b, "add", greet)
        self.git(b, "commit", "-m", "Resolve known fixture: Welcome plus whitespace normalization")
        integrated_c = self.finish(b, "SIMULATED fixture decision: preserve Welcome and whitespace normalization")
        self.mark(10, "Known fixture conflict is resolved deliberately and verified", integrated_c["event"])
        tested = self.tool(b, "test")
        self.mark(11, "Combined software passes TEST in an isolated worktree", tested["event"])
        public = self.tool(c, "events")["events"]
        if tested["event"]["event_id"] not in {e["event_id"] for e in public}:
            raise RuntimeError("C cannot discover published test evidence")
        self.mark(12, "C independently discovers published test evidence", tested["event"]["event_id"])
        if self.remote:
            self.git(b, "switch", "-c", self.canonical, "origin/" + self.canonical)
        else:
            self.git(b, "switch", self.canonical)
        self.git(b, "merge", "--no-edit", f"people/{self.people[1]}/work")
        self.git(b, "push", "origin", self.canonical)
        self.tool(c, "sync", "--update")
        self.tool(c, "test", "main")
        self.mark(13, "Verified contributions reach canonical state", self.git(b, "rev-parse", "HEAD"))
        prepared = self.tool(b, "final-prepare", "--result", "Greeting normalization, welcoming text and tested arithmetic")
        self.mark(14, "A recognized member prepares a concrete final candidate", prepared)
        final = self.tool(b, "final-publish", prepared["candidate_id"], "--confirm")
        recovery = self.clone("fresh-session")
        self.git(recovery, "switch", "-c", f"people/{self.people[0]}/recovery", "origin/" + self.canonical)
        self.tool(recovery, "identity", "--person", self.people[0])
        recovered = self.tool(recovery, "status")
        if final["event"]["event_id"] not in {e["event_id"] for e in recovered["new_events"]}:
            raise RuntimeError("Fresh session lost final evidence")
        if final["final"]["evidence_mode"] != "simulation":
            raise RuntimeError("Fixture confirmation must never appear as real human feedback")
        self.mark(15, "Simulated confirmation yields one recoverable group result", final)
        summary = {"mode": "real GitHub remote" if self.remote and "github.com" in self.remote else "local bare Git remote",
            "evidence_mode": "simulation", "human_confirmation": "simulated fixture, not real human feedback",
            "people": self.people, "changes": [item["change_id"] for item in (change_a, change_b, change_c)],
            "normal_integration": integrated_a["event"]["result"], "conflicting_files": conflict["conflicts"],
            "conflict_integration": integrated_c["event"]["result"], "test_result": tested["event"], "final": final["final"],
            "acceptance_steps": len(self.steps), "fresh_session_recovery": True, "command_count": len(self.transcript),
            "verification_branches": self.branches,
            "paths": {"output": str(self.output), "final_report": str(b / ".group/final/final_report.md"),
                      "transcript": str(self.output / "transcript.json")}}
        self.json_file("summary.json", summary)
        print("Evidence: " + str(self.output / "summary.json"), flush=True)
        return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--remote", help="Explicitly authorize pushes to NEW verification branches; never changes main")
    parser.add_argument("--base-ref", default="origin/synthesis/groupctl-final")
    args = parser.parse_args()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    Demo(args.output or ROOT / "demo-output" / stamp, args.remote, args.base_ref).perform()


if __name__ == "__main__":
    main()
