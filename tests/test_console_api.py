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


def test_start_check_rejects_bad_url():
    try:
        console_api.start_check("not-a-url")
        assert False, "expected ValueError"
    except ValueError as e:
        assert "github.com" in str(e)


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
