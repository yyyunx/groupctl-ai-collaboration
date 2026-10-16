"""Mechanical facts belong here; semantic decisions belong to humans/agents."""
from __future__ import annotations

import json
import re
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path


class GroupError(Exception):
    pass


def now():
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        raise GroupError(f"Cannot read JSON {path}: {exc}") from exc


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,255}", value):
        raise GroupError(f"Invalid identifier: {value!r}")
    return value


def execute(args, cwd, ok=(0,), timeout=180):
    try:
        result = subprocess.run(args, cwd=cwd, capture_output=True, text=True,
                                encoding="utf-8", errors="replace", timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise GroupError(f"Cannot run {args[0]}: {exc}") from exc
    if result.returncode not in ok:
        raise GroupError(f"Command failed ({result.returncode}): {args!r}\n"
                         f"{result.stdout}{result.stderr}")
    return result


EVENT_FIELDS = {
    "change_published": {"change_id": str, "branch": str, "commit": str, "summary": str,
                         "files_changed": list, "interface_changes": list, "tests_run": list,
                         "known_issues": list, "proposed_for_integration": bool},
    "finding": {"summary": str, "evidence": list},
    "question": {"question_id": str, "text": str, "blocking": bool},
    "answer": {"question_id": str, "text": str},
    "review": {"change_id": str, "verdict": str, "summary": str, "issues": list, "tests_run": list},
    "test_result": {"scope": str, "commit": str, "commands": list, "automated_result": str,
                    "passed": (int, type(None)), "failed": (int, type(None)),
                    "skipped": (int, type(None)), "human_checks_required": list, "summary": str},
    "integration_result": {"change_id": str, "target_branch": str, "result": str,
                           "merge_commit": str, "conflicts": list,
                           "conflict_resolution_summary": str, "verification": dict, "summary": str},
    "blocker": {"summary": str, "blocking_change_id": str, "requested_action": str},
    "final_candidate": {"canonical_commit": str, "candidate_report_path": str,
                        "test_evidence": list, "known_issues": list},
    "final_result": {"canonical_commit": str, "final_report_path": str,
                     "test_evidence": list, "known_limitations": list, "initiated_by": str},
}


def validate_event(event):
    if not isinstance(event, dict):
        raise GroupError("An event must be a JSON object")
    common = {"protocol_version": str, "event_id": str, "event_type": str,
              "group_id": str, "person_id": str, "created_at": str, "related_events": list}
    if event.get("event_type") not in EVENT_FIELDS:
        raise GroupError("Unsupported event_type")
    for key, kind in (common | EVENT_FIELDS[event["event_type"]]).items():
        if key not in event or not isinstance(event[key], kind):
            raise GroupError(f"Missing or invalid event field: {key}")
    if event["protocol_version"] != "0.1":
        raise GroupError("Unsupported protocol_version")
    for key in ("event_id", "person_id", "group_id"):
        identifier(event[key])
    try:
        if datetime.fromisoformat(event["created_at"].replace("Z", "+00:00")).tzinfo is None:
            raise ValueError("timezone required")
    except ValueError as exc:
        raise GroupError("created_at must be an ISO timestamp with timezone") from exc
    for key in ("related_events", "files_changed", "interface_changes", "tests_run", "known_issues",
                "evidence", "issues", "commands", "human_checks_required", "conflicts",
                "test_evidence", "known_limitations", "resolves_events"):
        if key in event and (not isinstance(event[key], list) or not all(isinstance(x, str) for x in event[key])):
            raise GroupError(f"{key} must contain strings")
    enums = {"verdict": {"accept", "accept_with_changes", "reject", "needs_more_evidence"},
             "automated_result": {"pass", "fail", "partial", "not_available"},
             "result": {"success", "failed", "needs_human"}}
    for key, values in enums.items():
        if key in event and event[key] not in values:
            raise GroupError(f"Invalid {key}: {event[key]}")
    if event["event_type"] == "integration_result":
        verification = event["verification"]
        if not all(verification.get(key) in {"pass", "fail", "not_available", "not_applicable"}
                   for key in ("build", "tests", "semantic_review")):
            raise GroupError("verification must describe build, tests and semantic_review")
    return event


class Repository:
    def __init__(self, cwd=".", configured=True):
        self.root = Path(execute(["git", "rev-parse", "--show-toplevel"], cwd).stdout.strip()).resolve()
        self.meta = self.root / ".group"
        self.local = self.meta / "local"
        self.config = read_json(self.meta / "group.json") if configured else {}
        if configured:
            if not isinstance(self.config, dict):
                raise GroupError("group.json must be a JSON object")
            for key in ("protocol_version", "group_id", "canonical_branch", "assignment_file"):
                if not isinstance(self.config.get(key), str) or not self.config[key]:
                    raise GroupError(f"Missing group configuration: {key}")
            if self.config["protocol_version"] != "0.1":
                raise GroupError("Unsupported protocol_version")
            identifier(self.config["group_id"])
            identifier(self.config.get("remote", "origin"))
            self.git("check-ref-format", "--branch", self.config["canonical_branch"])
            self.path(self.config["assignment_file"])

    def path(self, relative):
        path = (self.root / relative).resolve()
        if not path.is_relative_to(self.root):
            raise GroupError("Path must stay inside the repository")
        return path

    def git(self, *args, ok=(0,)):
        return execute(["git", *args], self.root, ok=ok)

    def output(self, *args):
        return self.git(*args).stdout.strip()

    @property
    def branch(self):
        branch = self.output("symbolic-ref", "--quiet", "--short", "HEAD")
        if not branch:
            raise GroupError("A named branch is required")
        return branch

    @property
    def head(self):
        return self.output("rev-parse", "HEAD")

    @property
    def remote(self):
        return self.config.get("remote", "origin")

    @property
    def canonical(self):
        return f"refs/remotes/{self.remote}/{self.config['canonical_branch']}"

    def clean(self):
        if self.output("status", "--porcelain"):
            raise GroupError("Working tree is not clean. Commit/protect unfinished work first.")
        if self.git("rev-parse", "--verify", "-q", "MERGE_HEAD", ok=(0, 1)).returncode == 0:
            raise GroupError("An unfinished merge must be resolved first")

    def identity(self):
        value = read_json(self.local / "identity.json")
        person = identifier(value.get("person_id"))
        member = read_json(self.meta / "members" / f"{person}.json")
        if member.get("person_id") != person or member.get("protocol_version") != "0.1":
            raise GroupError("Identity must match a recognized membership descriptor")
        return person

    def personal(self):
        if not self.branch.startswith(f"people/{self.identity()}/"):
            raise GroupError("Use your own people/<person_id>/<topic> branch")

    def fetch(self):
        self.git("fetch", "--prune", self.remote,
                 f"+refs/heads/*:refs/remotes/{self.remote}/*", "--tags")

    def ancestor(self, commit, target="HEAD"):
        return self.git("merge-base", "--is-ancestor", commit, target, ok=(0, 1)).returncode == 0

    def events(self):
        """Read public events from ALL remote branches without merging those branches."""
        refs = self.output("for-each-ref", "--format=%(refname)", f"refs/remotes/{self.remote}/").splitlines()
        events, contents = {}, {}
        if refs:
            # Inspect historical filenames too: a force-updated event on a single
            # remote tip must not bypass immutability checks.
            mutated = self.output("log", "--format=", "--name-only", "--diff-filter=MD", *refs, "--", ".group/events/")
            if mutated:
                raise GroupError("Published event history contains modifications/deletions: " + mutated)
        for ref in refs:
            lines = self.output("ls-tree", "-r", ref, "--", ".group/events/").splitlines()
            for line in lines:
                entry, path = line.split("\t", 1)
                if not path.endswith(".json"):
                    continue
                blob = entry.split()[2]
                if blob not in contents:
                    try:
                        contents[blob] = validate_event(json.loads(self.output("cat-file", "blob", blob)))
                    except ValueError as exc:
                        raise GroupError(f"Malformed event: {path}") from exc
                event = contents[blob]
                if event["group_id"] != self.config["group_id"]:
                    raise GroupError(f"Event belongs to another group: {path}")
                if Path(path).stem != event["event_id"]:
                    raise GroupError(f"Event filename does not match event_id: {path}")
                previous = events.get(event["event_id"])
                if previous is not None and previous != event:
                    raise GroupError(f"Immutable event was changed: {event['event_id']}")
                events[event["event_id"]] = event
        return sorted(events.values(), key=lambda x: (x["created_at"], x["event_id"]))

    def event(self, kind, fields, related=()):
        if kind not in EVENT_FIELDS:
            raise GroupError("Unsupported event type")
        person = self.identity()
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        protected = {"protocol_version", "event_id", "event_type", "group_id", "person_id", "created_at", "related_events"}
        if protected & fields.keys():
            raise GroupError("Event payload must not replace common envelope fields")
        return validate_event({"protocol_version": "0.1", "event_id": f"E-{stamp}-{person}-{uuid.uuid4().hex[:10]}",
                               "event_type": kind, "group_id": self.config["group_id"], "person_id": person,
                               "created_at": now(), "related_events": list(related), **fields})

    def publish(self, event, extra=()):
        validate_event(event)
        path = self.meta / "events" / f"{event['event_id']}.json"
        if path.exists():
            raise GroupError("Refusing to overwrite an immutable event")
        write_json(path, event)
        paths = [str(path.relative_to(self.root)), *extra]
        self.git("add", "--", *paths)
        self.git("commit", "-m", f"group: {event['event_type']} {event['event_id']}", "--", *paths)
        try:
            self.git("push", "-u", self.remote, f"HEAD:refs/heads/{self.branch}")
        except GroupError as exc:
            raise GroupError(f"Event is committed locally, NOT published. Retry git push; event {event['event_id']}.\n{exc}") from exc
        return event

    def change(self, change_id, events=None):
        candidates = [e for e in (events if events is not None else self.events())
                      if e["event_type"] == "change_published" and e["change_id"] == change_id]
        if len(candidates) != 1:
            raise GroupError(f"Expected one published change for {change_id}; found {len(candidates)}")
        event = candidates[0]
        branch = event["branch"]
        if not branch.startswith(f"people/{event['person_id']}/"):
            raise GroupError("Published change must identify the author's personal branch")
        self.git("check-ref-format", "--branch", branch)
        commit = event["commit"]
        if not re.fullmatch(r"[0-9a-f]{40,64}", commit):
            raise GroupError("Published change must use an exact commit hash")
        self.git("cat-file", "-e", f"{commit}^{{commit}}")
        if not self.ancestor(commit, f"refs/remotes/{self.remote}/{branch}"):
            raise GroupError("Change commit is not contained in its published remote branch")
        return event

    def checks(self, checks=None):
        commands = self.config.get("validation_commands", []) if checks is None else checks
        if not isinstance(commands, list) or not all(isinstance(c, list) and c and
                all(isinstance(x, str) and x for x in c) for c in commands):
            raise GroupError("validation_commands must be a list of nonempty argument arrays")
        results = []
        for command in commands:
            try:
                result = execute(command, self.root, ok=tuple(range(256)), timeout=300)
                results.append({"argv": command, "exit_code": result.returncode,
                                "stdout": result.stdout[-16000:], "stderr": result.stderr[-16000:]})
            except GroupError as exc:
                results.append({"argv": command, "exit_code": None, "error": str(exc)})
        state = ("not_available" if not results else
                 "fail" if any(r["exit_code"] not in (0, None) for r in results) else
                 "partial" if any(r["exit_code"] is None for r in results) else "pass")
        return {"automated_result": state, "results": results}

    def test_event(self, scope, commit, checks, human=()):
        # Counts are unknown for arbitrary test runners; never invent test totals.
        passed = failed = skipped = None
        counts = []
        for result in checks["results"]:
            output = result.get("stdout", "") + result.get("stderr", "")
            match = re.search(r"Ran (\d+) tests? in", output)
            if match:
                errors = re.search(r"FAILED \(([^)]+)\)", output)
                bad = sum(int(x) for x in re.findall(r"(?:failures|errors)=(\d+)", errors[1] if errors else ""))
                skip_match = re.search(r"skipped=(\d+)", output)
                skip = int(skip_match[1]) if skip_match else 0
                counts.append((int(match[1]) - bad - skip, bad, skip))
        if counts and len(counts) == len(checks["results"]):
            passed, failed, skipped = map(sum, zip(*counts))
        return self.event("test_result", {"scope": scope, "commit": commit,
            "commands": [json.dumps(r["argv"], ensure_ascii=False) for r in checks["results"]],
            "automated_result": checks["automated_result"], "passed": passed, "failed": failed,
            "skipped": skipped, "human_checks_required": list(human),
            "summary": f"Automated validation: {checks['automated_result']}", "command_results": checks["results"]})
