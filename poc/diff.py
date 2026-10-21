"""Deterministic normalisation and comparison of probe outputs (spec 6.6).

Guardrail: this module, not a model, decides whether main and PR behaved the same. Probes only print one JSON
object; they never assert. A model may *propose* new noise rules, but they are added here as code and reviewed.
"""
from __future__ import annotations

import json
import re

NOISE_RULES: list[tuple[str, str]] = [
    (r"0x[0-9a-fA-F]{6,}", "<addr>"),
    (r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", "<uuid>"),
    (r"\b\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:?\d{2})?\b", "<timestamp>"),
    (r"/tmp/[^\s'\"]+", "<tmp>"),
    (r"127\.0\.0\.1:\d+|localhost:\d+", "<local>:<port>"),
]
VOLATILE_KEYS = {"duration", "duration_s", "elapsed", "seconds", "pid", "port"}


def parse_probe_output(stdout: str, exit_code: int | str) -> dict:
    """A probe must print exactly one JSON object. Anything else is itself a recorded result."""
    if exit_code == "timeout":
        return {"timeout": True}
    lines = [ln for ln in (stdout or "").strip().splitlines() if ln.strip()]
    try:
        obj = json.loads(lines[-1]) if lines else None
    except json.JSONDecodeError:
        obj = None
    if not isinstance(obj, dict):
        return {"crash": "non-json output", "exit_code": exit_code}
    if exit_code not in (0, "0"):
        obj = dict(obj, exit_code=exit_code)
    return obj


def normalise(value):
    if isinstance(value, dict):
        return {k: normalise(v) for k, v in sorted(value.items()) if k not in VOLATILE_KEYS}
    if isinstance(value, list):
        return [normalise(v) for v in value]
    if isinstance(value, str):
        for pat, rep in NOISE_RULES:
            value = re.sub(pat, rep, value)
    return value


def compare(main: dict, pr: dict) -> list[dict]:
    """Field-by-field differences after normalisation. Type-aware: 1 != 1.0 != "1", True != 1."""
    a, b = normalise(main), normalise(pr)
    out: list[dict] = []

    def walk(x, y, path):
        if isinstance(x, dict) and isinstance(y, dict):
            for k in sorted(set(x) | set(y)):
                walk(x.get(k, "<absent>"), y.get(k, "<absent>"), f"{path}.{k}" if path else k)
        elif type(x) is not type(y) or x != y:
            out.append({"field": path or "<root>", "main": x, "pr": y})
    walk(a, b, "")
    return out


def _fingerprints(runs: list) -> set[str]:
    return {json.dumps(normalise(r), sort_keys=True) for r in runs}


def confirm(main_runs: list[dict], pr_runs: list[dict]) -> str:
    """Compare the runs of each side.

    'same' or 'differs' when each side agrees with itself. 'flaky' when the base disagrees with itself, or both
    sides do (that stays noise). 'pr_unstable' when the base is stable and only the pull request is not: a possible
    regression, not noise.
    """
    nm, npr = _fingerprints(main_runs), _fingerprints(pr_runs)
    if len(nm) == 1 and len(npr) > 1:
        return "pr_unstable"
    if len(nm) > 1 or len(npr) > 1:
        return "flaky"
    return "same" if nm == npr else "differs"


def pr_runs_too_noisy(pr_runs: list) -> bool:
    """True when every pull-request run is its own result, so a regression cannot be called."""
    if len(pr_runs) < 3:
        return False
    return len(_fingerprints(pr_runs)) == len(pr_runs)
