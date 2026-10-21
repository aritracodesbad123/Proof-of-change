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
    assert rows[0]["report_pdf"] is None and rows[0]["report_html"] is None


def test_list_runs_bounded_does_not_remember_every_file(tmp_path, monkeypatch):
    monkeypatch.setattr(console_api, "RUNS_ROOT", tmp_path / "runs")
    monkeypatch.setattr(console_api, "REPO_ROOT", tmp_path)
    console_api._recent_runs.clear()
    remembered: list[str] = []

    def spy_remember(rec, path=None):
        remembered.append(str(rec.get("id")))
        return console_api._row_from_record(rec, path)

    monkeypatch.setattr(console_api, "remember_run", spy_remember)
    root = tmp_path / "runs"
    for i in range(12):
        d = root / "day" / f"run-{i}"
        d.mkdir(parents=True)
        (d / "record.json").write_text(json.dumps({
            "record_kind": "pr_run", "id": f"pr-{i}", "repo": "me/demo", "verdict": "verified",
            "reason": "ok", "pr": {"number": i, "url": f"https://github.com/me/demo/pull/{i}", "title": "t"},
        }))
        # Distinct mtimes so newest-N ordering is stable.
        import os
        os.utime(d / "record.json", (1_700_000_000 + i, 1_700_000_000 + i))
    rows = console_api.list_runs(limit=5)
    assert len(rows) == 5
    assert remembered == []  # list_runs must not remember_run every file
    assert {r["id"] for r in rows} == {f"pr-{i}" for i in range(7, 12)}


def test_tail_bytes_and_console_log_tee(tmp_path):
    log = tmp_path / "console.log"
    log.write_text("hello\n" + ("x" * 10_000) + "\ntail-line\n")
    tail = console_api._tail_bytes(log, 8192)
    assert "tail-line" in tail
    assert len(tail.encode()) <= 8192 + 32  # decode may expand slightly; still bounded source read


def test_start_check_sets_hitl_env(tmp_path, monkeypatch):
    class FakeThread:
        def __init__(self, target=None, daemon=None):
            self.target = target

        def start(self):
            pass

    monkeypatch.setattr(console_api.threading, "Thread", FakeThread)
    monkeypatch.setattr(console_api, "console_run_flags", lambda: console_api.ConsoleRunPlan([], None, False, None))
    monkeypatch.setattr(console_api, "REPO_ROOT", tmp_path)
    (tmp_path / "ops" / "runs" / "_jobs").mkdir(parents=True)
    (tmp_path / "ops" / "daily_run.py").write_text("# stub\n")
    job = console_api.start_check("https://github.com/me/demo/pull/3", model_provider="none")
    assert job["status"] == "queued"
    with console_api._jobs_lock:
        raw = console_api._jobs[job["id"]]
    assert raw.get("hitl_dir")
    assert (tmp_path / "ops" / "runs" / "_jobs" / job["id"]).is_dir()


def test_find_reviewer_report_under_daily(tmp_path, monkeypatch):
    monkeypatch.setattr(console_api, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(console_api, "REPORTS_DAILY", tmp_path / "reports" / "daily")
    day = tmp_path / "reports" / "daily" / "2026-10-17-check-1200"
    rid = "marshmallow-3079"
    (day / rid).mkdir(parents=True)
    pdf = day / rid / "REPORT.pdf"
    html = day / rid / "REPORT.html"
    pdf.write_bytes(b"%PDF-1.4 fake")
    html.write_text("<html>ok</html>")
    assert console_api.find_reviewer_report_file(rid, "pdf") == pdf
    assert console_api.find_reviewer_report_file("pr-other-id", "html", folder=f"ops/runs/x/{rid}") == html
    links = console_api.report_links(rid)
    assert links["report_pdf"] and links["report_pdf"].endswith("/report.pdf")
    assert links["report_html"] and links["report_html"].endswith("/report.html")


def test_github_reads_gh_token_alias(monkeypatch):
    from ops import daily_run
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.setenv("GH_TOKEN", "ghp_test_alias")
    assert daily_run.GitHub(None).token == "ghp_test_alias"


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
    monkeypatch.delenv("POC_UNSAFE_NO_SANDBOX", raising=False)
    monkeypatch.setattr(console_api, "contree_usable", lambda: True)
    plan = console_api.console_run_flags()
    assert plan.flags == ["--sandbox-backend", "contree"]
    assert "--unsafe-no-sandbox" not in plan.flags
    assert plan.refused is False
    assert plan.warning is None
    assert plan.note and "Contree" in plan.note


def test_console_run_flags_skips_contree_without_sdk(monkeypatch):
    monkeypatch.setattr(console_api, "contree_usable", lambda: False)
    monkeypatch.delenv("POC_UNSAFE_NO_SANDBOX", raising=False)
    import guardrails.sandbox as sb
    monkeypatch.setattr(sb, "check", lambda: (False, "bwrap down"))
    plan = console_api.console_run_flags()
    assert plan.flags == []
    assert plan.refused is True
    assert plan.warning is None
    assert plan.note and "will not run pull-request code" in plan.note


def test_console_run_flags_refuses_when_bwrap_down(monkeypatch):
    monkeypatch.delenv("NEBIUS_API_KEY", raising=False)
    monkeypatch.delenv("NEBIUS_PROJECT_ID", raising=False)
    monkeypatch.delenv("POC_UNSAFE_NO_SANDBOX", raising=False)
    import guardrails.sandbox as sb
    monkeypatch.setattr(sb, "check", lambda: (False, "bwrap: uid map not permitted"))
    plan = console_api.console_run_flags()
    assert plan.flags == []
    assert plan.refused is True
    assert plan.warning is None
    assert plan.note and "will not run pull-request code" in plan.note
    assert "--unsafe-no-sandbox" not in (plan.note or "")


def test_explicit_unsafe_opt_in_warns(monkeypatch):
    monkeypatch.setenv("POC_UNSAFE_NO_SANDBOX", "1")
    monkeypatch.setattr(console_api, "contree_usable", lambda: False)
    import guardrails.sandbox as sb
    monkeypatch.setattr(sb, "check", lambda: (False, "bwrap down"))
    plan = console_api.console_run_flags()
    assert plan.flags == ["--unsafe-no-sandbox"]
    assert plan.refused is False
    assert plan.warning and "Warning" in plan.warning and "POC_UNSAFE_NO_SANDBOX=1" in plan.warning

    class FakeThread:
        def __init__(self, target=None, daemon=None):
            self.target = target

        def start(self):
            pass

    monkeypatch.setattr(console_api.threading, "Thread", FakeThread)
    job = console_api.start_check("https://github.com/me/demo/pull/3", model_provider="recorded")
    assert job["status"] == "queued"
    assert job["run_flags"] == ["--unsafe-no-sandbox"]
    assert job["refused"] is False
    assert job["warning"] and "Warning" in job["warning"] and "POC_UNSAFE_NO_SANDBOX=1" in job["warning"]


def test_unsafe_opt_in_with_contree_warns(monkeypatch):
    monkeypatch.setenv("POC_UNSAFE_NO_SANDBOX", "1")
    monkeypatch.setattr(console_api, "contree_usable", lambda: True)
    plan = console_api.console_run_flags()
    assert plan.flags == ["--sandbox-backend", "contree", "--unsafe-no-sandbox"]
    assert plan.refused is False
    assert plan.note and "Contree" in plan.note
    assert plan.warning and "POC_UNSAFE_NO_SANDBOX=1" in plan.warning

    class FakeThread:
        def __init__(self, target=None, daemon=None):
            self.target = target

        def start(self):
            pass

    monkeypatch.setattr(console_api.threading, "Thread", FakeThread)
    job = console_api.start_check("https://github.com/me/demo/pull/3", model_provider="recorded")
    assert job["run_flags"] == ["--sandbox-backend", "contree", "--unsafe-no-sandbox"]
    assert job["refused"] is False
    assert job["warning"] and "POC_UNSAFE_NO_SANDBOX=1" in job["warning"]
    assert job["run_note"] and "Contree" in job["run_note"]


def test_start_check_refuses_unsandboxed_pr_code(monkeypatch):
    """Missing sandbox and no POC_UNSAFE_NO_SANDBOX=1: the child never starts."""
    monkeypatch.delenv("SPACE_ID", raising=False)
    monkeypatch.setattr(console_api, "contree_usable", lambda: False)
    import guardrails.sandbox as sb
    monkeypatch.setattr(sb, "check", lambda: (False, "bwrap down"))
    started: list[str] = []

    def refuse_process(*_args, **_kwargs):
        started.append("popen")
        raise AssertionError("pull-request code must not start without a sandbox")

    monkeypatch.setattr(console_api.subprocess, "Popen", refuse_process)

    for value in (None, "0", "false", "no", ""):
        if value is None:
            monkeypatch.delenv("POC_UNSAFE_NO_SANDBOX", raising=False)
        else:
            monkeypatch.setenv("POC_UNSAFE_NO_SANDBOX", value)
        try:
            console_api.start_check("https://github.com/me/demo/pull/3", model_provider="recorded")
            raise AssertionError(f"expected refusal for POC_UNSAFE_NO_SANDBOX={value!r}")
        except ValueError as exc:
            assert "will not run pull-request code" in str(exc)
    assert started == []


def test_start_check_queues_job(monkeypatch):
    class FakeThread:
        def __init__(self, target=None, daemon=None):
            self.target = target

        def start(self):
            pass  # do not run daily_run in unit tests

    monkeypatch.setattr(console_api.threading, "Thread", FakeThread)
    monkeypatch.setattr(
        console_api, "console_run_flags",
        lambda: console_api.ConsoleRunPlan(
            ["--unsafe-no-sandbox"],
            "sandbox unavailable (test); running with --unsafe-no-sandbox",
            False,
            "sandbox unavailable (test); running with --unsafe-no-sandbox",
        ),
    )
    job = console_api.start_check("https://github.com/me/demo/pull/3", model_provider="recorded")
    assert job["status"] == "queued" and job["pr"] == 3
    assert job["current_stage"] == "queued"
    assert job["model_provider"] == "recorded"
    assert job["run_flags"] == ["--unsafe-no-sandbox"]
    assert job["run_note"] and "unsafe" in job["run_note"]
    assert "ultra" in job["swarm"]
    got = console_api.get_job(job["id"])
    assert got["repo"] == "me/demo"
    assert got["stages"] and got["stages"][0]["stage"] == "queued"
    assert got["model_provider"] == "recorded"
