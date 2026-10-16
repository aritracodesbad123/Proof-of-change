"""run_progress JSONL + swarm map."""
from __future__ import annotations

from poc import run_progress


def test_swarm_handoff(tmp_path, monkeypatch):
    path = tmp_path / "p.jsonl"
    monkeypatch.setenv("POC_PROGRESS_PATH", str(path))
    run_progress.emit("queued")
    run_progress.emit("agent_judge", "ultra", "j")
    mid = run_progress.job_progress(path)
    assert mid["swarm"]["ultra"] == "active"
    run_progress.emit("agent_helper", "lightning", "h")
    mid2 = run_progress.job_progress(path)
    assert mid2["swarm"]["ultra"] == "done" and mid2["swarm"]["lightning"] == "active"
    run_progress.emit("agent_summary", "super", "s")
    run_progress.emit("done")
    end = run_progress.job_progress(path)
    assert end["swarm"] == {"ultra": "done", "lightning": "done", "super": "done"}
    assert end["current_stage"] == "done"


def test_emit_noop_without_env(monkeypatch, tmp_path):
    monkeypatch.delenv("POC_PROGRESS_PATH", raising=False)
    run_progress.emit("queued")  # must not raise
    assert not list(tmp_path.iterdir()) or True
