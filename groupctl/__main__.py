"""Run with python -m groupctl. Core commands use JSON; handoff views offer text."""
import argparse
import json
import sys

from . import commands
from .core import GroupError
from .status import render_status
from . import __version__
from . import collaboration, communication, recovery, onboarding
from .presentation import safe
from .events import EVENT_FIELDS


def parser():
    p = argparse.ArgumentParser(description="groupctl — Git collaboration protocol 0.1",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="第一次使用：doctor → init --help / join --help → context → inbox\n"
               "換電腦／新 clone：join --resume --person 你的ID --topic 原topic\n"
               "Human shorthand: SYNC / PUB / INT / REV / TEST / STATUS / FINAL\n"
               "Examples:\n  python -m groupctl --repo ../team status --format text\n"
               "  python -m groupctl --repo ../team inspect C-P17-...\n"
               "  python -m groupctl --repo ../team test main\n"
               "FINAL: final-prepare -> show report to human -> final-publish --confirm\n"
               "Exit codes: 0 success, 1 operation/precondition error, 2 invalid usage or incomplete/failed verification.")
    p.add_argument("--version", action="version", version=__version__)
    p.add_argument("--repo", default=".", help="Git working directory")
    subs = p.add_subparsers(dest="command", required=True)

    def command(name, function, help):
        sub = subs.add_parser(name, help=help)
        sub.set_defaults(function=function)
        return sub

    sub = command("init", commands.init, "Create .group configuration without committing unrelated files")
    for name in ("group", "person", "assignment"):
        sub.add_argument("--" + name, required=True)
    sub.add_argument("--name", help="顯示名稱；預設使用 person ID")
    sub.add_argument("--publish", action="store_true", help="乾淨且已同步的 canonical：只提交 .group、Push、建立個人分支")
    sub.add_argument("--topic", default="work")
    sub.add_argument("--checks", choices=tuple(onboarding.CHECK_PRESETS), help="明確選用驗證命令 preset；不會安裝依賴或宣稱 Pass")
    sub.add_argument("--canonical", default="main")
    sub.add_argument("--checks-file", help="JSON list of argument arrays (executed without a shell)")
    sub.add_argument("--simulation", action="store_true", help="Mark an isolated teaching fixture; final records explicitly remain simulation evidence")
    sub = command("join", commands.join, "Register a member on a new personal branch and publish")
    for name in ("person",):
        sub.add_argument("--" + name, required=True)
    sub.add_argument("--name", help="顯示名稱；預設使用 person ID")
    sub.add_argument("--topic", default="work")
    sub.add_argument("--resume", action="store_true", help="既有成員：恢復原本分支與本機身分，不重複註冊或 Push")
    sub = command("doctor", onboarding.doctor, "中文設定診斷：Git、身分、Tests、目標 Repository（只讀、離線）")
    sub.add_argument("--format", choices=("text", "json"), default="text")
    sub = command("identity", commands.identity, "Select an already recognized member locally")
    sub.add_argument("--person", required=True)
    sub = command("status", commands.status, "STATUS: report local and freshly fetched group state")
    sub.add_argument("--format", choices=("json", "text"), default="json", help="JSON for agents (default), readable Chinese text for students")
    sub.add_argument("--offline", action="store_true", help="Use only known local refs/events; data may be stale")
    sub = command("sync", commands.sync, "SYNC: discover events on all remote branches")
    sub.add_argument("--update", action="store_true", help="Also merge canonical branch and run quick checks")
    command("events", commands.events_command, "List public events from all remote branches")
    sub = command("event", commands.event_command, "Publish a finding, question, answer, or blocker")
    sub.add_argument("--type", required=True)
    sub.add_argument("--file", required=True, help="JSON payload, without envelope fields")
    sub.add_argument("--related", action="append", default=[])
    sub = command("pub", commands.pub, "PUB: validate, commit and push contribution plus change event")
    sub.add_argument("--summary")
    sub.add_argument("--dry-run", action="store_true", help="Read-only cached preview; no tests, Git writes or network")
    sub.add_argument("--interface-change", action="append", default=[])
    sub.add_argument("--known-issue", action="append", default=[])
    sub.add_argument("--draft", action="store_true")
    sub.add_argument("--unverified-reason")
    sub = command("inspect", commands.inspect, "Show a published change's actual diff")
    sub.add_argument("change")
    sub = command("review", commands.review, "REV: publish an agent/human review; never merge")
    sub.add_argument("change")
    choice = sub.add_mutually_exclusive_group(required=True)
    choice.add_argument("--file", help="保留 JSON assessment 操作")
    choice.add_argument("--verdict", choices=("accept", "accept_with_changes", "reject", "needs_more_evidence"))
    sub.add_argument("--inspected-commit", help="實際讀過的完整 change commit；不自動填入")
    sub.add_argument("--diff-inspected", action="store_true", help="明確聲明已檢查精確 diff")
    sub.add_argument("--summary")
    sub.add_argument("--issue", action="append", default=[])
    sub.add_argument("--test-run", action="append", default=[])
    sub.add_argument("--evidence", action="append", default=[])
    sub = command("test", commands.test, "TEST: run configured commands at an exact commit and publish evidence")
    sub.add_argument("scope", nargs="?", default="current")
    sub.add_argument("--human-check", action="append", default=[])
    sub = command("integrate", commands.integrate, "INT phase 1: merge; conflicts and semantic review remain explicit")
    sub.add_argument("change")
    sub.add_argument("--preview", action="store_true", help="Read-only file-overlap risk preview; not a Git merge result")
    sub = command("integrate-finish", commands.integrate_finish, "INT phase 2: validate and publish integration outcome")
    choice = sub.add_mutually_exclusive_group(required=True)
    choice.add_argument("--file", help="保留 JSON assessment 操作")
    choice.add_argument("--semantic-review", choices=("pass", "fail"), help="實際語意判斷；沒有預設 Pass")
    sub.add_argument("--reviewed-commit", help="實際檢查過的完整 HEAD")
    sub.add_argument("--build", choices=("pass", "fail", "not_applicable", "not_available"))
    sub.add_argument("--summary")
    sub.add_argument("--resolution", help="衝突如何處理；沒有文字衝突也須明確說明")
    command("integrate-abort", commands.integrate_abort, "Abort only an uncommitted pending merge")
    sub = command("final-prepare", commands.final_prepare, "FINAL phase 1: verify canonical state and show candidate report")
    sub.add_argument("--result", required=True)
    sub.add_argument("--dispositions", help="JSON object: unintegrated change ID -> reason it is rejected/obsolete")
    sub.add_argument("--limitation", action="append", default=[])
    sub.add_argument("--human-check", action="append", default=[])
    sub.add_argument("--human-evidence", action="append", default=[])
    sub = command("final-publish", commands.final_publish, "FINAL phase 2: publish human-confirmed final records")
    sub.add_argument("candidate")
    sub.add_argument("--confirm", action="store_true")
    sub.add_argument("--confirmation-file", help="Candidate-bound human attestation JSON; required for real noninteractive finalization")
    sub = command("context", collaboration.context, "Bounded, redacted context for any local AI agent")
    sub.add_argument("--format", choices=("markdown", "json"), default="markdown")
    sub.add_argument("--max-chars", type=int, default=12000)
    sub.add_argument("--offline", action="store_true")
    sub = command("inbox", collaboration.inbox, "Collaboration events and actionable attention items")
    sub.add_argument("--format", choices=("text", "json"), default="text")
    sub.add_argument("--offline", action="store_true")
    sub.add_argument("--type", action="append", choices=tuple(EVENT_FIELDS), default=[])
    sub.add_argument("--person")
    sub.add_argument("--change")
    sub.add_argument("--relevant", action="store_true")
    sub.add_argument("--limit", type=int, default=20)
    sub.add_argument("--mark-read", action="append", default=[])
    sub.add_argument("--mark-all-read", action="store_true")
    for name in ("ask", "answer", "block", "resolve"):
        sub = command(name, communication.publish_communication, "Publish a protocol 0.1 communication without a JSON input file")
        if name in ("ask", "answer"):
            sub.add_argument("--text", required=True)
        if name == "answer":
            sub.add_argument("question")
        if name == "block":
            sub.add_argument("--summary", required=True)
            sub.add_argument("--action", required=True)
        if name in ("ask", "block"):
            sub.add_argument("--change")
        if name == "resolve":
            sub.add_argument("event")
            sub.add_argument("--reason", required=True)
            sub.add_argument("--evidence", action="append", default=[])
    sub = command("template", communication.template, "Generate an unapproved review/semantic assessment template")
    sub.add_argument("kind", choices=("review", "semantic"))
    sub.add_argument("change", nargs="?")
    sub.add_argument("--output", help="Create UTF-8 JSON exclusively; refuses to overwrite a file")
    sub = command("recover", recovery.recover, "Diagnose incomplete operations; retry only existing commits when explicitly requested")
    sub.add_argument("--format", choices=("text", "json"), default="text")
    sub.add_argument("--offline", action="store_true")
    action = sub.add_mutually_exclusive_group()
    action.add_argument("--retry-push", action="store_true", help="Fresh fetch + normal fast-forward push of existing HEAD; no new events")
    action.add_argument("--update", action="store_true", help="只 fast-forward 目前分支到剛 fetch 的遠端版本；拒絕 dirty、分歧及 pending integration")
    action.add_argument("--resume-integration", metavar="CHANGE_ID", help="Restore missing local integration metadata from an exact Git merge")
    sub = command("trace", collaboration.trace, "Read a change lifecycle from events and exact Git ancestry")
    sub.add_argument("change")
    sub.add_argument("--format", choices=("text", "json"), default="text")
    sub.add_argument("--offline", action="store_true")
    return p


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    cli = parser()
    if not sys.argv[1:]:
        cli.print_help()
        return 0
    args = cli.parse_args()
    if args.command == "pub" and not args.dry_run and not args.summary:
        cli.error("pub requires --summary unless --dry-run is selected")
    try:
        result = args.function(args)
        if args.command == "doctor" and args.format == "text":
            print(onboarding.render_doctor(result))
        elif args.command == "context":
            print(collaboration.render_context(result, args.format))
        elif args.command == "inbox" and args.format == "text":
            print(collaboration.render_inbox(result))
        elif args.command == "recover" and args.format == "text":
            print(recovery.render_recovery(result))
        elif args.command == "trace" and args.format == "text":
            print(collaboration.render_trace(result))
        elif getattr(args, "format", "json") == "text":
            print(render_status(result))
        else:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        event = result.get("event", {})
        if args.command == "doctor" and not result["ready"]:
            return 2
        if result.get("conflicts") or result.get("needs_human"):
            return 2
        if event.get("automated_result") in {"fail", "partial", "not_available"} or event.get("result") in {"failed", "needs_human"}:
            return 2
        if args.command != "context" and (result.get("validation") or {}).get("automated_result") in {"fail", "partial", "not_available"}:
            return 2
        return 0
    except GroupError as exc:
        print(json.dumps(safe({"error": str(exc), "exit_code": exc.code, "hint": exc.hint}), ensure_ascii=False), file=sys.stderr)
        return exc.code
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps(safe({"error": str(exc), "exit_code": 1,
                          "hint": "Check input JSON, paths and repository configuration; no success is claimed."}), ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
