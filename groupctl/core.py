"""Mechanical facts belong here; semantic decisions belong to humans/agents."""
from __future__ import annotations

import json
import os
import tempfile
from contextlib import contextmanager
import re
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path


from .errors import GroupError
from .events import EVENT_FIELDS, identifier, validate_event, validate_event_graph, event_time
from .validation import run_checks, parse_counts


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


def execute(args, cwd, ok=(0,), timeout=180, env=None, binary=False):
    try:
        result = subprocess.run(args, cwd=cwd, capture_output=True, text=not binary,
                                encoding=None if binary else "utf-8", errors=None if binary else "replace",
                                timeout=timeout, env=None if env is None else dict(os.environ, **env))
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise GroupError(f"Cannot run {args[0]}: {exc}") from exc
    if result.returncode not in ok:
        raise GroupError(f"Command failed ({result.returncode}): {args!r}\n"
                         f"{result.stdout}{result.stderr}")
    return result


class Repository:
    def __init__(self, cwd=".", configured=True):
        self.root = Path(execute(["git", "rev-parse", "--show-toplevel"], cwd).stdout.strip()).resolve()
        self.meta = self.root / ".group"
        self.local = self.meta / "local"
        self.path(".group/local")
        self.config = read_json(self.meta / "group.json") if configured else {}
        if configured:
            if not isinstance(self.config, dict):
                raise GroupError("group.json must be a JSON object")
            if type(self.config.get("simulation", False)) is not bool:
                raise GroupError("simulation must be a boolean; only explicit true marks fixtures")
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

    def git(self, *args, ok=(0,), env=None, binary=False):
        return execute(["git", *args], self.root, ok=ok, env=env, binary=binary)

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
        if not isinstance(value, dict):
            raise GroupError("Local identity must be a JSON object")
        person = identifier(value.get("person_id"))
        member = read_json(self.meta / "members" / f"{person}.json")
        if not isinstance(member, dict) or member.get("person_id") != person or member.get("protocol_version") != "0.1":
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
        remote_refs = self.output("for-each-ref", "--format=%(refname)", f"refs/remotes/{self.remote}/").splitlines()
        refs = []
        for ref in remote_refs:
            config_entry = self.output("ls-tree", ref, "--", ".group/group.json")
            if not config_entry:
                if self.output("ls-tree", "-r", ref, "--", ".group/events/"):
                    raise GroupError(f"Remote events have no group configuration: {ref}")
                continue
            config_blob = config_entry.split()[2]
            try:
                scope = json.loads(self.git("cat-file", "blob", config_blob, binary=True).stdout)
            except ValueError as exc:
                raise GroupError(f"Invalid remote group configuration: {ref}") from exc
            if not isinstance(scope, dict):
                raise GroupError(f"Invalid remote group configuration: {ref}")
            if scope.get("group_id") == self.config["group_id"]:
                refs.append(ref)
        events, contents, blobs = {}, {}, {}
        if refs:
            # Inspect historical filenames too: a force-updated event on a single
            # remote tip must not bypass immutability checks.
            # -m examines a merge against EACH parent. Default git log diffs
            # omit merge commits and can hide a rewrite introduced only there.
            mutated = self.output("log", "--full-history", "-m", "--format=", "--name-only",
                                  "--diff-filter=MD", *refs, "--", ".group/events/")
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
                        contents[blob] = validate_event(json.loads(self.git("cat-file", "blob", blob, binary=True).stdout))
                    except ValueError as exc:
                        raise GroupError(f"Malformed event: {path}") from exc
                event = contents[blob]
                if event["group_id"] != self.config["group_id"]:
                    raise GroupError(f"Event belongs to another group: {path}")
                if Path(path).stem != event["event_id"]:
                    raise GroupError(f"Event filename does not match event_id: {path}")
                previous = events.get(event["event_id"])
                if previous is not None and (previous != event or blobs[event["event_id"]] != blob):
                    raise GroupError(f"Immutable event was changed: {event['event_id']}")
                events[event["event_id"]] = event
                blobs[event["event_id"]] = blob
        self._event_blobs = blobs
        result = sorted(events.values(), key=lambda x: (event_time(x), x["event_id"]))
        validate_event_graph(result)
        return result

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

    def publish(self, event, extra=(), *, expected_public_ids=None, expected_canonical=None):
        validate_event(event)
        if event["group_id"] != self.config["group_id"] or event["person_id"] != self.identity():
            raise GroupError("Publication envelope must match current group and identity")
        self.fetch()
        public = self.events()
        if expected_public_ids is not None and {e["event_id"] for e in public} != set(expected_public_ids):
            raise GroupError("Group state changed before publication; revalidate the final candidate",
                             hint="Generated final files may be uncommitted. Inspect them and prepare a fresh candidate.")
        if expected_canonical is not None and (self.head != expected_canonical or
                self.output("rev-parse", self.canonical) != expected_canonical):
            raise GroupError("Canonical state changed before publication; revalidate the final candidate")
        path = self.meta / "events" / f"{event['event_id']}.json"
        if path.exists():
            raise GroupError("Refusing to overwrite an immutable event")
        # Retain immutable public evidence on the publishing branch, so deleting
        # feature branches later cannot make accepted collaboration history vanish.
        local = {}
        for existing in (self.meta / "events").glob("*.json"):
            value = validate_event(read_json(existing))
            if existing.stem != value["event_id"] or value["group_id"] != self.config["group_id"]:
                raise GroupError(f"Invalid local event filename/group: {existing.name}")
            local[value["event_id"]] = value
        combined = {e["event_id"]: e for e in public}
        for event_id, value in local.items():
            if event_id in combined and combined[event_id] != value:
                raise GroupError(f"Immutable event was changed locally: {event_id}")
            combined[event_id] = value
        if event["event_id"] in combined:
            raise GroupError("Refusing to overwrite an immutable event")
        validate_event_graph([*combined.values(), event])
        paths = []
        for published in public:
            name = published["event_id"]
            raw = self.git("cat-file", "blob", self._event_blobs[name], binary=True).stdout
            archive = self.meta / "events" / f"{name}.json"
            if archive.exists():
                relative = archive.relative_to(self.root).as_posix()
                if self.output("hash-object", f"--path={relative}", str(archive)) != self._event_blobs[name]:
                    raise GroupError(f"Immutable event bytes were changed locally: {name}")
            else:
                archive.parent.mkdir(parents=True, exist_ok=True)
                with archive.open("xb") as stream:
                    stream.write(raw)
                paths.append(str(archive.relative_to(self.root)))
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(event, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        paths += [str(path.relative_to(self.root)), *extra]
        self.git("add", "--", *paths)
        self.git("commit", "-m", f"group: {event['event_type']} {event['event_id']}", "--", *paths)
        try:
            self.git("push", "-u", self.remote, f"HEAD:refs/heads/{self.branch}")
        except GroupError as exc:
            from .localstate import push_failure
            push_failure(self, "event_push", [event["event_id"]])
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
        source_ref = f"refs/remotes/{self.remote}/{branch}"
        branch_exists = self.git("show-ref", "--verify", "--quiet", source_ref, ok=(0, 1)).returncode == 0
        if branch_exists and not self.ancestor(commit, source_ref):
            raise GroupError("Change commit is not contained in its published remote branch")
        if not branch_exists and not self.ancestor(commit, self.canonical):
            raise GroupError("Source branch is missing and the change is not accepted in canonical history")
        return event

    def checks(self, checks=None):
        commands = self.config.get("validation_commands", []) if checks is None else checks
        return run_checks(self.root, commands, self.config.get("validation_timeout", 300))

    @contextmanager
    def isolated(self, commit):
        """Disposable checkout for every TEST scope, including current HEAD."""
        with tempfile.TemporaryDirectory(prefix="groupctl-test-") as directory:
            target = Path(directory).resolve() / "checkout"
            self.git("worktree", "add", "--detach", str(target), commit)
            try:
                yield Repository(target)
            finally:
                if target.parent != Path(directory).resolve():
                    raise GroupError("Unsafe temporary worktree path")
                self.git("worktree", "remove", "--force", str(target))

    def check_commit(self, commit):
        with self.isolated(commit) as checkout:
            checks = checkout.checks()
            if checkout.output("status", "--porcelain"):
                checks["automated_result"] = "fail"
                checks["repository_modified"] = True
                checks["summary"] = "Validation modified tracked/unignored files in the isolated checkout"
            return checks

    def snapshot(self, paths):
        """Snapshot selected working files using a private index; preserve user's index."""
        with tempfile.TemporaryDirectory(prefix="groupctl-index-") as directory:
            environment = {"GIT_INDEX_FILE": str(Path(directory) / "index")}
            self.git("read-tree", "HEAD", env=environment)
            self.git("--literal-pathspecs", "add", "--all", "--", *paths, env=environment)
            tree = self.git("write-tree", env=environment).stdout.strip()
            return self.output("commit-tree", tree, "-p", self.head, "-m", "groupctl isolated validation snapshot")

    def test_event(self, scope, commit, checks, human=()):
        # Keep unknown counts null instead of inventing totals for custom runners.
        counts = [result.get("counts") for result in checks["results"]]
        passed = failed = skipped = None
        if counts and all(value is not None for value in counts):
            passed, failed, skipped = map(sum, zip(*counts))
        return self.event("test_result", {"scope": scope, "commit": commit,
            "commands": [json.dumps(r["argv"], ensure_ascii=False) for r in checks["results"]],
            "automated_result": checks["automated_result"], "passed": passed, "failed": failed,
            "skipped": skipped, "human_checks_required": list(human),
            "summary": f"Automated validation: {checks['automated_result']}", "command_results": checks["results"],
            "validation_issues": ([checks["summary"]] if checks.get("summary") else []) +
                                 [r["error"] for r in checks["results"] if "error" in r]})
