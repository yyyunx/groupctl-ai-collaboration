"""Install bundled, vendor-neutral instructions without requiring a source checkout."""
import os
import stat
import tempfile
import uuid
from importlib.resources import files
from pathlib import Path

from . import __version__
from .errors import GroupError


AGENTS = {"codex": "AGENTS.md", "claude": "CLAUDE.md", "gemini": "GEMINI.md"}


def payloads(agents):
    data = files("groupctl").joinpath("agent_data")
    result = {"AGENT_COLLABORATION.md": data.joinpath("AGENT_COLLABORATION.md").read_bytes()}
    for agent in sorted(set(agents)):
        result[AGENTS[agent]] = data.joinpath(AGENTS[agent]).read_bytes()
    # Shared path keeps all entry points portable, even for a single selected agent.
    roots = [".agents"] + ["." + a for a in ("claude", "gemini") if a in agents]
    for root in roots:
        for name in ("SKILL.md", "references/commands.md"):
            result[f"{root}/skills/group-collaboration/{name}"] = data.joinpath("skill", *name.split("/")).read_bytes()
    return result


def checked_path(target, relative):
    """Reject links, Windows junctions/reparse points and non-directory ancestors."""
    path = target / relative
    # Inspect ancestors before children: POSIX lstat(child) raises ENOTDIR when
    # an ancestor is a regular file; it must remain a structured preflight error.
    for part in (*reversed(path.parents), path):
        try:
            info = part.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise GroupError(f"Refusing linked/reparse path: {part}")
        if part != path and not stat.S_ISDIR(info.st_mode):
            raise GroupError(f"Expected a directory: {part}")
    if path.exists() and not path.is_file():
        raise GroupError(f"Expected a regular file: {path}")
    return path


def setup(args):
    if args.overwrite != args.confirm:
        raise GroupError("Replacing files requires both --overwrite and --confirm.", code=2,
                         hint="Review agent-setup --target PATH --dry-run first.")
    # abspath normalizes relative paths without following a target symlink.
    target = Path(os.path.abspath(os.path.expanduser(args.target)))
    agents = sorted(set(args.agent or AGENTS))
    contents = payloads(agents)
    plan = []
    for relative, content in contents.items():
        path = checked_path(target, relative)
        before = path.read_bytes() if path.exists() else None
        action = "unchanged" if before == content else "conflict" if before is not None else "create"
        plan.append({"path": relative, "action": action, "content": content.decode("utf-8")})
    conflicts = [entry["path"] for entry in plan if entry["action"] == "conflict"]
    result = {"version": __version__, "target": str(target), "agents": agents, "dry_run": args.dry_run,
              "files": plan, "conflicts": conflicts if not args.overwrite else [],
              "written": [], "backups": [], "network_used": False}
    if args.dry_run or (conflicts and not args.overwrite):
        result["next"] = "Review conflicts and merge instructions manually, or explicitly use --overwrite --confirm (creates backups)." if conflicts else "Run again without --dry-run to install."
        return result
    for entry in plan:
        if entry["action"] == "unchanged":
            continue
        path = checked_path(target, entry["path"])
        path.parent.mkdir(parents=True, exist_ok=True)
        if entry["action"] == "create":
            # Exclusive creation also protects a file that appeared after preview.
            with path.open("xb") as stream:
                stream.write(contents[entry["path"]])
        else:
            backup = path.with_name(path.name + ".groupctl-backup-" + uuid.uuid4().hex)
            with backup.open("xb") as stream:
                stream.write(path.read_bytes())
            result["backups"].append(str(backup.relative_to(target)))
            fd, temporary = tempfile.mkstemp(prefix=".groupctl-", dir=path.parent)
            try:
                with os.fdopen(fd, "wb") as stream:
                    stream.write(contents[entry["path"]])
                os.replace(temporary, path)
            finally:
                if os.path.exists(temporary):
                    os.unlink(temporary)
        result["written"].append(entry["path"])
    result["next"] = "Read AGENT_COLLABORATION.md; restart your agent in the target project, then run groupctl doctor, context and inbox."
    return result
