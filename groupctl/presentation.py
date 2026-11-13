"""Allowlisted projections and best-effort secret redaction for agent handoffs."""
import json
import re

from .errors import GroupError

MASK = "[REDACTED]"
PATTERNS = [
    re.compile(r"-----BEGIN [^\n]*PRIVATE KEY-----.*?(?:-----END [^\n]*PRIVATE KEY-----|$)", re.S),
    re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|sk-[A-Za-z0-9_-]{16,}|AIza[A-Za-z0-9_-]{20,}|AKIA[A-Z0-9]{16})\b"),
    re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+"),
    re.compile(r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b"),
]
ASSIGNMENT = re.compile(r'''(?im)(["']?(?:[\w-]*(?:api[_-]?key|password|passwd|secret|access[_-]?token|auth[_-]?token)[\w-]*|token)["']?\s*[:=]\s*)("[^"\n]*"|'[^'\n]*'|[^\s,;&}\n]+)''')


def redact(text):
    for pattern in PATTERNS:
        text = pattern.sub(MASK, text)
    text = re.sub(r"(?i)(https?://)[^\s/@]+:[^\s/@]+@", r"\1[REDACTED]@", text)
    return ASSIGNMENT.sub(lambda m: m[1] + MASK, text)


def safe(value):
    if isinstance(value, str):
        return redact(value)
    if isinstance(value, list):
        return [safe(item) for item in value]
    if isinstance(value, dict):
        return {redact(str(key)): safe(item) for key, item in value.items()}
    return value


def reject_secrets(value):
    if safe(value) != value:
        raise GroupError("Possible secret in communication input; nothing was published",
                         hint="Remove credentials and share a reference to the protected configuration instead.")


def safe_commands(commands):
    result = []
    for command in commands:
        hide = False
        arguments = []
        for argument in command:
            arguments.append(MASK if hide else redact(argument))
            hide = bool(re.fullmatch(r"--?(?:token|password|secret|api[-_]key|access[-_]token)", argument, re.I))
        result.append(arguments)
    return result


def summary(event):
    keys = ("event_id", "event_type", "person_id", "created_at", "change_id", "question_id", "commit",
            "summary", "text", "verdict", "result", "automated_result", "blocking", "requested_action",
            "blocking_change_id", "interface_changes", "related_events", "resolves_events")
    value = {key: event[key] for key in keys if key in event}
    for key in ("summary", "text", "requested_action"):
        if key in value:
            value[key] = redact(value[key])[:320]
    if "interface_changes" in value:
        value["interface_changes"] = [redact(item)[:160] for item in value["interface_changes"][:5]]
    return safe(value)


def json_text(value):
    return json.dumps(safe(value), ensure_ascii=False, indent=2)
