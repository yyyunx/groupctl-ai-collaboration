"""Disposable, per-clone UI state; never an authoritative collaboration record."""
import json
import os
import tempfile

from .errors import GroupError


def load(r, name, default):
    path = r.path(".group/local/" + name)
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (ValueError, OSError) as exc:
        raise GroupError(f"Invalid local state {name}; inspect this disposable file before replacing it") from exc


def save(r, name, value):
    path = r.path(".group/local/" + name)
    relative = path.relative_to(r.root).as_posix()
    if r.git("ls-files", "--error-unmatch", "--", relative, ok=(0, 1)).returncode == 0:
        raise GroupError("Local state must not be tracked in Git: " + relative)
    if r.git("check-ignore", "-q", "--", relative, ok=(0, 1)).returncode != 0:
        raise GroupError("Configure .group/local/.gitignore before saving local-only state")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as stream:
            temporary = stream.name
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        os.replace(temporary, path)
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)


def push_failure(r, phase, event_ids=()):
    # A failed convenience receipt must never obscure the original push failure.
    try:
        from .core import now
        save(r, "push-failure.json", {"phase": phase, "branch": r.branch, "commit": r.head,
                                     "event_ids": list(event_ids), "recorded_at": now()})
    except (GroupError, OSError):
        pass
