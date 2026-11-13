import argparse
import json
import subprocess
import sys
from unittest.mock import patch

from groupctl import collaboration
from groupctl.collaboration import ObservedRepository
from groupctl.core import Repository, write_json
from test_groupctl import GitFixture, call, git, ROOT
from test_product_features import index_bytes, talk


class TraceOfflineTests(GitFixture):
    def test_offline_status_preserves_dirty_index_and_labels_overlap_as_risk(self):
        (self.a / "greet.py").write_text('def greet(name):\n    return "Hi " + name\n', encoding="utf-8")
        change = call(self.a, "pub", summary="Greeting interface", interface_change=["greet now accepts whitespace"],
                      known_issue=[], draft=False, unverified_reason=None)
        Repository(self.b).fetch()
        (self.b / "greet.py").write_text('def greet(name):\n    return "Welcome " + name\n', encoding="utf-8")
        git(self.b, "add", "greet.py")
        before = index_bytes(self.b)
        with patch.object(ObservedRepository, "fetch", side_effect=AssertionError("Offline fetched")):
            result = call(self.b, "status", offline=True)
        self.assertTrue(result["freshness"]["may_be_stale"])
        self.assertEqual(result["conflicts"], [])
        risk = result["potential_conflict_warnings"][0]
        self.assertEqual(risk["change_id"], change["change_id"])
        self.assertEqual(risk["overlapping_files"], ["greet.py"])
        self.assertTrue(risk["risk_only"])
        self.assertTrue(risk["interface_changes"])
        git(self.b, "remote", "set-url", "origin", str(self.base / "unavailable.git"))
        output = subprocess.run([sys.executable, "-m", "groupctl", "--repo", str(self.b), "status", "--offline"],
                                cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(output.returncode, 0, output.stderr)
        self.assertEqual(json.loads(output.stdout)["freshness"]["mode"], "offline")
        self.assertEqual(index_bytes(self.b), before)

    def test_trace_preserves_review_history_tests_and_canonical_ancestry(self):
        (self.a / "feature.py").write_text("VALUE = 1\n", encoding="utf-8")
        change = self.publish(self.a, "Traceable feature")
        assessment = self.base / "review.json"
        for verdict in ("reject", "accept"):
            write_json(assessment, {"inspected_commit": change["event"]["commit"], "diff_inspected": True,
                "verdict": verdict, "summary": "Explicit fixture review", "issues": [], "tests_run": [],
                "evidence": ["Exact diff inspected"]})
            call(self.b, "review", change=change["change_id"], file=str(assessment))
        integrated = self.integrate(self.b, change["change_id"])
        tested = call(self.b, "test", scope="current", human_check=[])
        git(self.b, "switch", "main")
        git(self.b, "merge", "--no-edit", "people/P22/work")
        git(self.b, "push", "origin", "main")
        args = argparse.Namespace(repo=str(self.b), change=change["change_id"], offline=False)
        result = collaboration.trace(args)
        self.assertEqual(result["status"], "in_canonical_history")
        integration = next(e for e in result["timeline"] if e["event_type"] == "integration_result")
        self.assertEqual(integration["merge_commit"], integrated["event"]["merge_commit"])
        self.assertEqual(integration["verification"]["semantic_review"], "pass")
        self.assertEqual([e["verdict"] for e in result["timeline"] if e["event_type"] == "review"], ["reject", "accept"])
        evidence = next(e for e in result["timeline"] if e["event_id"] == tested["event"]["event_id"])
        self.assertEqual(evidence["passed"], 1)
        self.assertEqual(evidence["relation"], "tested_commit_contains_change_history")
        blocker = talk(self.c, "block", summary="Need group decision", action="Confirm schema")["event"]
        self.assertEqual(collaboration.trace(args)["status"], "blocked")
        resolution = talk(self.c, "resolve", event=blocker["event_id"], reason="Schema confirmed", evidence=[])["event"]
        result = collaboration.trace(args)
        self.assertTrue(result["canonical_incorporation"]["in_history"])
        self.assertEqual(result["status"], "in_canonical_history")
        self.assertIn(resolution["event_id"], [e["event_id"] for e in result["timeline"]])
        self.assertIn("不等於語意正確", collaboration.render_trace(result))
