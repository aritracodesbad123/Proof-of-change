"""Thin progress channel for operator-console live jobs.

When POC_PROGRESS_PATH is set (console_api sets it for each check), callers
append JSONL events. get_job reloads them so the UI can show stages + swarm.
No-op when the env var is unset (CLI / CI unchanged).
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

# Fixed vocabulary (console UI + docs).
STAGES = (
    "queued",
    "fetch_pr",
    "setup_lookup",
    "setup_python",
    "install_deps",
    "install_main",
    "install_pr",
    "claims",
    "await_human",
    "probes",
    "pytest",
    "retry",
    "verdict",
    "demo_helper",
    "agent_judge",
    "agent_helper",
    "agent_summary",
    "report",
    "done",
    "failed",
)

ROLE_AGENT = {"judge": "ultra", "helper": "lightning", "summary": "super", "claims": "super"}

_SWARM_STAGES = {
    "agent_judge": "ultra",
    "agent_helper": "lightning",
    "agent_summary": "super",
}


_marks: list[tuple[str, float]] = []


_model_calls: list[tuple[str, float]] = []


def reset_timings() -> None:
    """Start a fresh step timer for one check (timing only; nothing reads it to decide anything)."""
    _marks.clear()
    _model_calls.clear()


def note_model_call(task: str, seconds: float) -> None:
    _model_calls.append((task, round(max(0.0, seconds), 1)))


def model_call_timings() -> list[tuple[str, float]]:
    return list(_model_calls)


def timings(now: float | None = None) -> dict[str, float]:
    """Seconds spent in each step since reset_timings(): a step runs from its first emit until the next emit of a
    different step. Repeated emits of the same step (progress ticks) do not split it."""
    out: dict[str, float] = {}
    end = time.time() if now is None else now
    for i, (stage, at) in enumerate(_marks):
        nxt = _marks[i + 1][1] if i + 1 < len(_marks) else end
        out[stage] = round(out.get(stage, 0.0) + max(0.0, nxt - at), 1)
    return out


def emit(
    stage: str, agent: str | None = None, detail: str | None = None, path: str | Path | None = None
) -> None:
    """Record a stage. ``path`` targets one check's file without touching the process environment."""
    if not _marks or _marks[-1][0] != stage:
        _marks.append((stage, time.time()))
    if path is None:
        path = os.environ.get("POC_PROGRESS_PATH")
    if not path:
        return
    ev = {"at": time.time(), "stage": stage, "agent": agent, "detail": detail}
    try:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as f:
            f.write(json.dumps(ev, default=str) + "\n")
    except OSError:
        return


def read_events(path: str | Path | None) -> list[dict[str, Any]]:
    if not path:
        return []
    p = Path(path)
    if not p.is_file():
        return []
    out: list[dict[str, Any]] = []
    try:
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    except OSError:
        return []
    return out


def swarm_status(events: list[dict[str, Any]]) -> dict[str, str]:
    """idle | active | done | skipped for ultra / lightning / super."""
    status = {"ultra": "idle", "lightning": "idle", "super": "idle"}
    seen_active: str | None = None
    for ev in events:
        stage = ev.get("stage") or ""
        if stage in _SWARM_STAGES:
            agent = _SWARM_STAGES[stage]
            if seen_active and seen_active != agent and status[seen_active] == "active":
                status[seen_active] = "done"
            status[agent] = "active"
            seen_active = agent
        if stage in ("done", "report") and seen_active:
            for k, v in list(status.items()):
                if v == "active":
                    status[k] = "done"
            seen_active = None
        if stage == "failed":
            for k, v in list(status.items()):
                if v == "active":
                    status[k] = "done"
    # If swarm never started but job finished, leave idle (not skipped) — UI shows standby.
    return status


def job_progress(path: str | Path | None) -> dict[str, Any]:
    events = read_events(path)
    current_stage = events[-1]["stage"] if events else None
    current_agent = None
    detail = None
    if events:
        current_agent = events[-1].get("agent")
        detail = events[-1].get("detail")
    return {
        "stages": events,
        "current_stage": current_stage,
        "current_agent": current_agent,
        "current_detail": detail,
        "swarm": swarm_status(events),
    }


if __name__ == "__main__":
    # ponytail: one assert-based self-check for swarm map handoff
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        os.environ["POC_PROGRESS_PATH"] = str(Path(d) / "p.jsonl")
        emit("queued")
        emit("agent_judge", "ultra", "judging")
        emit("agent_helper", "lightning", "hints")
        emit("agent_summary", "super", "summary")
        emit("done")
        prog = job_progress(os.environ["POC_PROGRESS_PATH"])
        assert prog["swarm"]["ultra"] == "done"
        assert prog["swarm"]["lightning"] == "done"
        assert prog["swarm"]["super"] == "done"
        assert prog["current_stage"] == "done"
        print("ok", prog["swarm"])
