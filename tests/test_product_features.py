"""Product-facing commands tested against real collaboration records."""
import argparse
import hashlib
import json
import subprocess
import sys
import unittest
from pathlib import Path

from groupctl import collaboration, communication
from groupctl.core import Repository, GroupError
from groupctl.presentation import redact, safe, safe_commands
from test_groupctl import GitFixture, call, git, ROOT


def talk(path, command, **kwargs):
    return communication.publish_communication(argparse.Namespace(repo=str(path), command=command, change=None, **kwargs))


def view(path, command="inbox", **kwargs):
    defaults = {"repo": str(path), "offline": True, "format": "json", "max_chars": 12000,
                "type": [], "person": None, "change": None, "relevant": False, "limit": 20,
                "mark_read": [], "mark_all_read": False}
    return getattr(collaboration, command)(argparse.Namespace(**(defaults | kwargs)))


def index_bytes(path):
    return (path / ".git/index").read_bytes()


class PresentationTests(unittest.TestCase):
    def test_common_secrets_and_credentials_are_redacted(self):
        token = "ghp_" + "a" * 40
        key = "sk-" + "x" * 40
        value = f"password=test-secret API_KEY={key}\nBearer {token}\nhttps://user:password@example.com?access_token=test-value"
        result = redact(value)
        for secret in (token, key, "test-secret", "user:password", "test-value"):
            self.assertNotIn(secret, result)
        self.assertIn("[REDACTED]", result)
        self.assertEqual(safe({"commit": "a" * 40})["commit"], "a" * 40)

    def test_private_keys_and_argument_pairs_are_hidden(self):
        value = "-----BEGIN " + "PRIVATE KEY-----\nnot-a-real-key\n-----END " + "PRIVATE KEY-----"
        self.assertNotIn("not-a-real-key", redact(value))
        self.assertEqual(safe_commands([["runner", "--token", "hidden", "--flag"]])[0][2], "[REDACTED]")


class ContextInboxCommunicationTests(GitFixture):
    def test_ask_answer_block_resolve_use_existing_protocol_without_fake_verdicts(self):
        question = talk(self.a, "ask", text="API 格式要統一嗎？")["event"]
        answer = talk(self.b, "answer", question=question["question_id"], text="統一使用 JSON")["event"]
        self.assertEqual(answer["related_events"], [question["event_id"]])
        self.assertEqual(answer["event_type"], "answer")
        blocked = talk(self.c, "block", summary="資料格式衝突", action="請確認 schema")["event"]
        self.assertEqual(blocked["blocking_change_id"], "GROUP")
        resolved = talk(self.a, "resolve", event=blocked["event_id"], reason="已更新並驗證", evidence=["Schema checks passed"])["event"]
        self.assertEqual(resolved["event_type"], "finding")
        self.assertEqual(resolved["resolves_events"], [blocked["event_id"]])
        r = Repository(self.b)
        r.fetch()
        inbox = view(self.b)
        self.assertEqual(inbox["counts"]["questions_awaiting_answers"], 0)
        self.assertEqual(inbox["counts"]["unresolved_blockers"], 0)
        self.assertNotIn("verdict", resolved)

    def test_context_is_bounded_and_does_not_export_logs_or_secrets(self):
        r = Repository(self.a)
        assignment = self.a / ".group/assignment/assignment.md"
        assignment.write_text("Build API.\npassword=fixture-secret\n" + "Requirement text. " * 500, encoding="utf-8")
        git(self.a, "add", ".group/assignment/assignment.md")
        git(self.a, "commit", "-m", "Context input fixture")
        talk(self.a, "ask", text="Which public interface should we keep?")
        before = index_bytes(self.a)
        for format in ("json", "markdown"):
            pack = view(self.a, "context", format=format, max_chars=3000)
            text = collaboration.render_context(pack, format)
            self.assertLessEqual(len(text) + 1, 3000)
            self.assertIn(r.head, text)
            self.assertNotIn("fixture-secret", text)
            self.assertNotIn("command_results", text)
            self.assertEqual(pack["totals"]["unanswered_questions"], 1)
            self.assertTrue(pack["truncated"])
        self.assertEqual(index_bytes(self.a), before)
        for format in ("json", "markdown"):
            output = subprocess.run([sys.executable, "-m", "groupctl", "--repo", str(self.a), "context", "--offline",
                                     "--format", format, "--max-chars", "3000"], cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(output.returncode, 0, output.stderr)
            self.assertLessEqual(len(output.stdout), 3000)
            if format == "json":
                self.assertEqual(json.loads(output.stdout)["person_id"], "P17")
            else:
                self.assertTrue(output.stdout.startswith("# Agent Context Pack"))
        # A read-only handoff succeeds while reporting failed evidence honestly.
        (self.a / "greet.py").write_text('def greet(name):\n    return "wrong"\n', encoding="utf-8")
        git(self.a, "add", "greet.py")
        git(self.a, "commit", "-m", "Failing validation context fixture")
        call(self.a, "test", scope="current", human_check=[])
        output = subprocess.run([sys.executable, "-m", "groupctl", "--repo", str(self.a), "context", "--offline",
                                 "--format", "json"], cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(output.returncode, 0, output.stderr)
        self.assertEqual(json.loads(output.stdout)["validation"]["automated_result"], "fail")

    def test_inbox_read_state_is_local_per_member_and_does_not_touch_index(self):
        question = talk(self.a, "ask", text="Need a schema decision")["event"]
        Repository(self.b).fetch()
        before_head, before_index = git(self.b, "rev-parse", "HEAD"), index_bytes(self.b)
        event_bytes = {p.name: p.read_bytes() for p in (self.b / ".group/events").glob("*.json")}
        initial = view(self.b)
        self.assertIn(question["event_id"], [e["event_id"] for e in initial["unread_events"]])
        marked = view(self.b, mark_read=[question["event_id"]])
        self.assertEqual(marked["counts"]["unread_events"], 0)
        self.assertEqual(marked["counts"]["questions_awaiting_answers"], 1)
        self.assertEqual(git(self.b, "rev-parse", "HEAD"), before_head)
        self.assertEqual(index_bytes(self.b), before_index)
        self.assertEqual(event_bytes, {p.name: p.read_bytes() for p in (self.b / ".group/events").glob("*.json")})
        self.assertTrue((self.b / ".group/local/inbox.json").exists())
        call(self.b, "identity", person="P17")
        self.assertEqual(view(self.b)["counts"]["unread_events"], 1)

    def test_inbox_filters_and_context_pending_review_are_real(self):
        (self.a / "feature.py").write_text("VALUE = 1\n", encoding="utf-8")
        change = self.publish(self.a, "API addition")
        args = argparse.Namespace(repo=str(self.b), command="ask", text="How to call this API?", change=change["change_id"])
        question = communication.publish_communication(args)["event"]
        Repository(self.c).fetch()
        filtered = view(self.c, type=["question"], person="P22", change=change["change_id"])
        self.assertEqual([e["event_id"] for e in filtered["unread_events"]], [question["event_id"]])
        pack = view(self.c, "context")
        self.assertIn(change["change_id"], [e.get("change_id") for e in pack["pending_reviews"]])
        self.assertIn(change["change_id"], [e["change_id"] for e in pack["pending_integrations"]])

    def test_quick_commands_reject_bad_inputs_and_preserve_dirty_work(self):
        before = git(self.a, "rev-parse", "HEAD")
        with self.assertRaises(GroupError):
            talk(self.a, "ask", text="password=do-not-publish")
        with self.assertRaises(GroupError):
            talk(self.a, "answer", question="Q-missing", text="Unknown question")
        with self.assertRaises(GroupError):
            talk(self.a, "ask", text="  ")
        self.assertEqual(git(self.a, "rev-parse", "HEAD"), before)
        (self.a / "unfinished.py").write_text("UNFINISHED = True", encoding="utf-8")
        before_index = index_bytes(self.a)
        with self.assertRaisesRegex(GroupError, "not clean"):
            talk(self.a, "ask", text="Do not discard my work")
        self.assertEqual(index_bytes(self.a), before_index)
        self.assertEqual((self.a / "unfinished.py").read_text(), "UNFINISHED = True")

    def test_assessment_templates_are_unapproved_and_never_overwrite(self):
        (self.a / "feature.py").write_text("VALUE = 1\n", encoding="utf-8")
        change = self.publish(self.a, "Template target")
        Repository(self.b).fetch()
        args = argparse.Namespace(repo=str(self.b), kind="review", change=change["change_id"], output=None)
        value = communication.template(args)
        self.assertIs(value["diff_inspected"], False)
        self.assertEqual(value["verdict"], "needs_more_evidence")
        self.assertEqual(value["inspected_commit"], change["event"]["commit"])
        args.kind = "semantic"
        self.assertEqual(communication.template(args)["semantic_review"], "fail")
        output = self.base / "assessment.json"
        args.output = str(output)
        communication.template(args)
        with self.assertRaises(FileExistsError):
            communication.template(args)
