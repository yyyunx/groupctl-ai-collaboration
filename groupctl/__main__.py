"""Run with python -m groupctl. All successful output is JSON."""
import argparse
import json
import sys

from . import commands
from .core import GroupError
from .status import render_status
from . import __version__


def parser():
    p = argparse.ArgumentParser(description="groupctl — Git collaboration protocol 0.1",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Human shorthand: SYNC / PUB / INT / REV / TEST / STATUS / FINAL\n"
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
    for name in ("group", "person", "name", "assignment"):
        sub.add_argument("--" + name, required=True)
    sub.add_argument("--canonical", default="main")
    sub.add_argument("--checks-file", help="JSON list of argument arrays (executed without a shell)")
    sub.add_argument("--simulation", action="store_true", help="Mark an isolated teaching fixture; final records explicitly remain simulation evidence")
    sub = command("join", commands.join, "Register a member on a new personal branch and publish")
    for name in ("person", "name", "topic"):
        sub.add_argument("--" + name, required=True)
    sub = command("identity", commands.identity, "Select an already recognized member locally")
    sub.add_argument("--person", required=True)
    sub = command("status", commands.status, "STATUS: report local and freshly fetched group state")
    sub.add_argument("--format", choices=("json", "text"), default="json", help="JSON for agents (default), readable Chinese text for students")
    sub = command("sync", commands.sync, "SYNC: discover events on all remote branches")
    sub.add_argument("--update", action="store_true", help="Also merge canonical branch and run quick checks")
    command("events", commands.events_command, "List public events from all remote branches")
    sub = command("event", commands.event_command, "Publish a finding, question, answer, or blocker")
    sub.add_argument("--type", required=True)
    sub.add_argument("--file", required=True, help="JSON payload, without envelope fields")
    sub.add_argument("--related", action="append", default=[])
    sub = command("pub", commands.pub, "PUB: validate, commit and push contribution plus change event")
    sub.add_argument("--summary", required=True)
    sub.add_argument("--interface-change", action="append", default=[])
    sub.add_argument("--known-issue", action="append", default=[])
    sub.add_argument("--draft", action="store_true")
    sub.add_argument("--unverified-reason")
    sub = command("inspect", commands.inspect, "Show a published change's actual diff")
    sub.add_argument("change")
    sub = command("review", commands.review, "REV: publish an agent/human review; never merge")
    sub.add_argument("change")
    sub.add_argument("--file", required=True)
    sub = command("test", commands.test, "TEST: run configured commands at an exact commit and publish evidence")
    sub.add_argument("scope", nargs="?", default="current")
    sub.add_argument("--human-check", action="append", default=[])
    sub = command("integrate", commands.integrate, "INT phase 1: merge; conflicts and semantic review remain explicit")
    sub.add_argument("change")
    sub = command("integrate-finish", commands.integrate_finish, "INT phase 2: validate and publish integration outcome")
    sub.add_argument("--file", required=True)
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
    try:
        result = args.function(args)
        if getattr(args, "format", "json") == "text":
            print(render_status(result))
        else:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        event = result.get("event", {})
        if result.get("conflicts") or result.get("needs_human"):
            return 2
        if event.get("automated_result") in {"fail", "partial", "not_available"} or event.get("result") in {"failed", "needs_human"}:
            return 2
        if result.get("validation", {}).get("automated_result") in {"fail", "partial", "not_available"}:
            return 2
        return 0
    except GroupError as exc:
        print(json.dumps({"error": str(exc), "exit_code": exc.code, "hint": exc.hint}, ensure_ascii=False), file=sys.stderr)
        return exc.code
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({"error": str(exc), "exit_code": 1,
                          "hint": "Check input JSON, paths and repository configuration; no success is claimed."}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
