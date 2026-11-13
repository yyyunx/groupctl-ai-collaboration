"""Execute checks without a shell and separate missing evidence from failure."""
import re
import subprocess
import sys

from .errors import GroupError


def validate_commands(commands):
    if not isinstance(commands, list) or not all(isinstance(command, list) and command and
            all(isinstance(arg, str) and arg for arg in command) for command in commands):
        raise GroupError("validation_commands must be a list of nonempty argument arrays")
    return commands


def parse_counts(output):
    match = re.search(r"Ran (\d+) tests? in", output)
    if match:
        bad = sum(int(n) for n in re.findall(r"(?:failures|errors|unexpected successes)=(\d+)", output))
        skipped = re.search(r"skipped=(\d+)", output)
        skipped = int(skipped[1]) if skipped else 0
        return max(0, int(match[1]) - bad - skipped), bad, skipped
    # pytest summaries; exclude other application output by requiring a summary line.
    lines = [line for line in output.splitlines() if re.search(r"=+ .*\b(?:passed|failed|skipped|no tests ran)\b.*=+", line)]
    if lines:
        line = lines[-1]
        totals = {name: int(n) for n, name in re.findall(r"(\d+) (passed|failed|error|errors|skipped)", line)}
        return totals.get("passed", 0), totals.get("failed", 0) + totals.get("error", 0) + totals.get("errors", 0), totals.get("skipped", 0)
    return None


def run_checks(root, commands, timeout=300):
    results = []
    for original in validate_commands(commands):
        command = [sys.executable if arg == "{python}" and i == 0 else arg for i, arg in enumerate(original)]
        try:
            process = subprocess.run(command, cwd=root, capture_output=True, text=True,
                                     encoding="utf-8", errors="replace", timeout=timeout)
            output = process.stdout + process.stderr
            counts = parse_counts(output)
            # unittest exits 0 even with zero tests; pytest exits 5 for no collection.
            empty = counts == (0, 0, 0) or (process.returncode == 5 and "no tests ran" in output)
            result = {"argv": command, "exit_code": process.returncode,
                      "stdout": process.stdout[-16000:], "stderr": process.stderr[-16000:],
                      "counts": list(counts) if counts is not None else None,
                      "evidence_state": "not_available" if empty else "fail" if process.returncode else "pass"}
        except (OSError, subprocess.TimeoutExpired) as exc:
            result = {"argv": command, "exit_code": None, "error": str(exc), "evidence_state": "partial"}
        results.append(result)
    states = {r["evidence_state"] for r in results}
    state = ("not_available" if not states or states == {"not_available"} else
             "fail" if "fail" in states else "partial" if states & {"partial", "not_available"} else "pass")
    return {"automated_result": state, "results": results}
