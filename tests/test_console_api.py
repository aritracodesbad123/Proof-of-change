"""Console API: list/get runs, start check validation, jobs."""
from __future__ import annotations

import json

from poc import console_api


def test_list_runs_reads_record(tmp_path, monkeypatch):
    runs = tmp_path / "runs" / "2026-10-16" / "demo-1"
    runs.mkdir(parents=True)
    rec = {"record_kind": "pr_run", "id": "pr-demo-1", "repo": "me/demo", "verdict": "verified",
           "reason": "ok", "pr": {"number": 1, "url": "https://github.com/me/demo/pull/1", "title": "t"},
           "tested_at_ist": "2026-10-16 12:00 IST"}
    (runs / "record.json").write_text(json.dumps(rec))
    monkeypatch.setattr(console_api, "RUNS_ROOT", tmp_path / "runs")
    monkeypatch.setattr(console_api, "REPO_ROOT", tmp_path)
    rows = console_api.list_runs()
    assert rows and rows[0]["id"] == "pr-demo-1" and rows[0]["verdict"] == "verified"


def test_job_log_and_error_prefers_stderr_and_stopped_line():
    tail, err = console_api.job_log_and_error(
        "run log: /app/ops/runs/x/REPORT.md\n",
        "Stopped: only 0 GB of free disk space; a run needs at least 5 GB.\n",
        2,
    )
    assert "stderr" in tail and "Stopped:" in (err or "")
    assert "free disk" in (err or "")


def test_remember_run_under_jobs_lock_does_not_deadlock(tmp_path, monkeypatch):
    """Job finish used to call remember_run while holding _jobs_lock (non-reentrant Lock → wedge)."""
    import threading

    monkeypatch.setattr(console_api, "REPO_ROOT", tmp_path)
    console_api._recent_runs.clear()
    rec = {
        "record_kind": "pr_run",
        "id": "pr-lock-nest",
        "repo": "me/demo",
        "verdict": "verified",
        "reason": "ok",
        "pr": {"number": 1, "url": "https://github.com/me/demo/pull/1", "title": "t"},
    }
    done = threading.Event()

    def hold_and_remember():
        with console_api._jobs_lock:
            console_api.remember_run(rec)
        done.set()

    t = threading.Thread(target=hold_and_remember)
    t.start()
    assert done.wait(2), "remember_run deadlocked under _jobs_lock"
    t.join(1)


def test_remember_run_survives_empty_disk(tmp_path, monkeypatch):
    monkeypatch.setattr(console_api, "RUNS_ROOT", tmp_path / "missing")
    monkeypatch.setattr(console_api, "REPO_ROOT", tmp_path)
    console_api._recent_runs.clear()
    rec = {
        "record_kind": "pr_run",
        "id": "pr-demo-memory",
        "repo": "me/demo",
        "verdict": "needs_attention",
        "reason": "x",
        "pr": {"number": 9, "url": "https://github.com/me/demo/pull/9", "title": "t"},
    }
    console_api.remember_run(rec)
    rows = console_api.list_runs()
    assert any(r["id"] == "pr-demo-memory" for r in rows)
    got = console_api.get_run("pr-demo-memory")
    assert got and got["record"]["verdict"] == "needs_attention" and got.get("source") == "memory"


def test_start_check_rejects_bad_url():
    try:
        console_api.start_check("not-a-url")
        assert False, "expected ValueError"
    except ValueError as e:
        assert "github.com" in str(e)


def test_console_run_flags_prefers_contree(monkeypatch):
    monkeypatch.setattr(console_api, "contree_usable", lambda: True)
    flags, note = console_api.console_run_flags()
    assert flags[:2] == ["--sandbox-backend", "contree"]
    assert "--unsafe-no-sandbox" in flags
    assert note and "Contree" in note


def test_console_run_flags_skips_contree_without_sdk(monkeypatch):
    monkeypatch.setattr(console_api, "contree_usable", lambda: False)
    monkeypatch.delenv("POC_UNSAFE_NO_SANDBOX", raising=False)
    import guardrails.sandbox as sb
    monkeypatch.setattr(sb, "check", lambda: (False, "bwrap down"))
    flags, note = console_api.console_run_flags()
    assert flags == ["--unsafe-no-sandbox"]


def test_console_run_flags_unsafe_when_bwrap_down(monkeypatch):
    monkeypatch.delenv("NEBIUS_API_KEY", raising=False)
    monkeypatch.delenv("NEBIUS_PROJECT_ID", raising=False)
    monkeypatch.delenv("POC_UNSAFE_NO_SANDBOX", raising=False)
    import guardrails.sandbox as sb
    monkeypatch.setattr(sb, "check", lambda: (False, "bwrap: uid map not permitted"))
    flags, note = console_api.console_run_flags()
    assert flags == ["--unsafe-no-sandbox"]
    assert note and "unsafe" in note


def test_start_check_queues_job(monkeypatch):
    class FakeThread:
        def __init__(self, target=None, daemon=None):
            self.target = target

        def start(self):
            pass  # do not run daily_run in unit tests

    monkeypatch.setattr(console_api.threading, "Thread", FakeThread)
    job = console_api.start_check("https://github.com/me/demo/pull/3", model_provider="none")
    assert job["status"] == "queued" and job["pr"] == 3
    assert job["current_stage"] == "queued"
    assert "ultra" in job["swarm"]
    got = console_api.get_job(job["id"])
    assert got["repo"] == "me/demo"
    assert got["stages"] and got["stages"][0]["stage"] == "queued"
