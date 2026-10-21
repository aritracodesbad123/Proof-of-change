"""Judge demo: session key stays in memory, the request worker waits, replay needs no network."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from ops import export_replay, request_worker
from poc import console_api, session_key

IST = ZoneInfo("Asia/Kolkata")
UTC = ZoneInfo("UTC")
SECRET = "nf-test-secret-value-123456"
TOKEN = "ghp_testtokenvalue1234567890"


def _at(hour: int, minute: int) -> datetime:
    return datetime(2026, 10, 21, hour, minute, tzinfo=IST)


class FakeClient:
    def __init__(self, issues, facts=None, comments=None):
        self.issues = issues
        self.facts = facts if facts is not None else {"language": "Python", "private": False}
        self.known_comments = {issue["number"]: list(comments or []) for issue in issues}
        self.posted = []
        self.labels = []
        self.removed = []
        self.heartbeats = 0
        self.reports = []

    def heartbeat(self, now):
        self.heartbeats += 1

    def list_open_requests(self):
        return self.issues

    def comments(self, number):
        return list(self.known_comments.get(number, []))

    def comment(self, number, body):
        self.posted.append((number, body))
        self.known_comments.setdefault(number, []).append(body)

    def add_labels(self, number, labels):
        self.labels.append((number, list(labels)))
        for issue in self.issues:
            if issue["number"] == number:
                issue.setdefault("labels", []).extend(labels)

    def remove_label(self, number, label):
        self.removed.append((number, label))

    def repo_facts(self, owner, name):
        return self.facts

    def publish_report(self, run_id, markdown):
        self.reports.append((run_id, markdown))
        return f"https://github.com/owner/repo/blob/checker-heartbeat/reports/{run_id}/REPORT.md"


def _issue(number, body, created="2026-10-21T01:00:00Z", labels=None):
    return {
        "number": number,
        "body": body,
        "state": "open",
        "created_at": created,
        "labels": list(labels or ["request-a-check"]),
    }


def _settings(tmp_path, **kwargs):
    base = request_worker.Settings(
        cap=5,
        study_lock=tmp_path / "missing.lock",
        state_path=tmp_path / "state.json",
        results_url="https://example.github.io/Proof-of-change/",
    )
    for key, value in kwargs.items():
        setattr(base, key, value)
    return base


def test_session_key_is_not_written_or_echoed(tmp_path, monkeypatch):
    def refuse_write(*_args, **_kwargs):
        raise AssertionError("session key touched the disk")

    monkeypatch.setattr(Path, "write_text", refuse_write)
    monkeypatch.setattr(Path, "write_bytes", refuse_write)
    monkeypatch.delenv("NEBIUS_API_KEY", raising=False)
    session_key.clear_key("sess-1")
    session_key.set_key("sess-1", SECRET)
    status = session_key.public_status("sess-1")
    assert status == {"nebius_key": True}
    assert SECRET not in json.dumps(status)
    assert os_environ_clean()
    env, secrets = console_api.child_environment({"PATH": "/usr/bin"}, "nebius", "sess-1")
    assert env["NEBIUS_API_KEY"] == SECRET
    assert "NEBIUS_API_KEY" not in __import__("os").environ
    assert SECRET in secrets
    cleared, _ = console_api.child_environment(dict(env), "recorded", "sess-1")
    assert "NEBIUS_API_KEY" not in cleared
    scrubbed = session_key.scrub(f"NEBIUS_API_KEY={SECRET} Bearer {TOKEN}", [SECRET, TOKEN])
    assert SECRET not in scrubbed and TOKEN not in scrubbed
    poisoned = {"log_tail": f"leaked {SECRET}", "error": f"Authorization: Bearer {TOKEN}"}
    public = console_api._scrub_public(poisoned)
    blob = json.dumps(public)
    assert SECRET not in blob and TOKEN not in blob
    session_key.clear_key("sess-1")


def os_environ_clean():
    import os
    return SECRET not in os.environ.values()


def test_logged_check_output_drops_the_key(tmp_path, monkeypatch):
    monkeypatch.delenv("NEBIUS_API_KEY", raising=False)
    monkeypatch.delenv("CODESPACES", raising=False)
    monkeypatch.setattr(console_api, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(console_api, "RUNS_ROOT", tmp_path / "ops" / "runs")
    monkeypatch.setattr(
        console_api, "console_run_flags",
        lambda: console_api.ConsoleRunPlan([], None, False, None),
    )
    session_key.set_key("sess-log", SECRET)

    def fake_read(proc, logf, collected, deadline):
        line = f"debug NEBIUS_API_KEY={SECRET}\n"
        logf.write(line)
        collected.append(line)
        return 0, False

    class Proc:
        pass

    monkeypatch.setattr(console_api, "_read_child", fake_read)
    monkeypatch.setattr(console_api.subprocess, "Popen", lambda *a, **k: Proc())
    monkeypatch.setattr(console_api, "find_record_for_pr", lambda *a, **k: None)
    holder = {}

    class FakeThread:
        def __init__(self, target=None, daemon=None):
            holder["target"] = target

        def start(self):
            pass

    monkeypatch.setattr(console_api.threading, "Thread", FakeThread)
    job = console_api.start_check(
        "https://github.com/me/demo/pull/3", model_provider="nebius", session_token="sess-log",
    )
    assert job["model_provider"] == "nebius"
    assert SECRET not in json.dumps(job)
    holder["target"]()
    log = (tmp_path / "ops" / "runs" / "_jobs" / job["id"] / "console.log").read_text()
    assert SECRET not in log
    public = console_api.get_job(job["id"])
    assert SECRET not in json.dumps(public)
    session_key.clear_key("sess-log")


def test_live_check_without_a_key_uses_recorded_answers(monkeypatch):
    monkeypatch.delenv("NEBIUS_API_KEY", raising=False)
    monkeypatch.delenv("CODESPACES", raising=False)

    class FakeThread:
        def __init__(self, target=None, daemon=None):
            pass

        def start(self):
            pass

    monkeypatch.setattr(console_api.threading, "Thread", FakeThread)
    monkeypatch.setattr(
        console_api, "console_run_flags",
        lambda: console_api.ConsoleRunPlan([], None, False, None),
    )
    job = console_api.start_check("https://github.com/me/demo/pull/4", model_provider="nebius")
    assert job["model_provider"] == "recorded"
    assert "recorded AI answers" in (job.get("run_note") or "")
    assert SECRET not in json.dumps(job)


def test_codespace_refuses_unsandboxed_pull_request_code(monkeypatch):
    """A Codespace follows the same rule as every other host: refuse, unless the opt-in is set."""
    monkeypatch.setenv("CODESPACES", "true")
    monkeypatch.delenv("NEBIUS_API_KEY", raising=False)
    monkeypatch.delenv("NEBIUS_PROJECT_ID", raising=False)
    monkeypatch.delenv("POC_UNSAFE_NO_SANDBOX", raising=False)
    import guardrails.sandbox as sb
    monkeypatch.setattr(sb, "check", lambda: (False, "bwrap missing"))
    monkeypatch.setattr(console_api, "contree_usable", lambda: False)
    plan = console_api.console_run_flags()
    assert plan.flags == []
    assert plan.refused is True
    assert plan.note and "will not run pull-request code" in plan.note
    with pytest.raises(ValueError, match="will not run pull-request code"):
        console_api.start_check("https://github.com/me/demo/pull/8", model_provider="recorded")
    monkeypatch.setenv("POC_UNSAFE_NO_SANDBOX", "1")
    opted = console_api.console_run_flags()
    assert opted.flags == ["--unsafe-no-sandbox"]
    assert opted.refused is False
    assert opted.warning and "POC_UNSAFE_NO_SANDBOX=1" in opted.warning


def test_codespace_uses_contree_without_the_unsandboxed_flag(monkeypatch):
    monkeypatch.setenv("CODESPACES", "true")
    monkeypatch.delenv("POC_UNSAFE_NO_SANDBOX", raising=False)
    monkeypatch.setattr(console_api, "contree_usable", lambda: True)
    plan = console_api.console_run_flags()
    assert plan.flags == ["--sandbox-backend", "contree"]
    assert "--unsafe-no-sandbox" not in plan.flags
    assert plan.warning is None
    assert plan.note and "Contree" in plan.note


def test_quiet_window_cap_study_lock_and_offline():
    assert request_worker.in_quiet_window(_at(10, 39)) is False
    assert request_worker.in_quiet_window(_at(10, 40)) is True
    assert request_worker.in_quiet_window(_at(12, 30)) is True
    assert request_worker.in_quiet_window(_at(12, 31)) is False
    assert request_worker.cap_reached(4, 5) is False
    assert request_worker.cap_reached(5, 5) is True
    now = _at(9, 0)
    assert request_worker.started_today({"date_ist": "2026-10-20", "started": 5}, now) == 0
    assert request_worker.started_today({"date_ist": "2026-10-21", "started": 2}, now) == 2
    fresh = datetime(2026, 10, 21, 5, 0, tzinfo=UTC)
    assert request_worker.checker_is_offline(None, fresh) is True
    assert request_worker.checker_is_offline("2026-10-21T04:50:00Z", fresh) is False
    assert request_worker.checker_is_offline("2026-10-21T04:30:00Z", fresh) is True
    assert "token" not in json.dumps(request_worker.heartbeat_document(fresh))


def test_study_lock_file(tmp_path):
    missing = tmp_path / "nope"
    assert request_worker.study_needs_slot(missing) is False
    off = tmp_path / "off"
    off.write_text("0\n")
    assert request_worker.study_needs_slot(off) is False
    on = tmp_path / "on"
    on.write_text("study\n")
    assert request_worker.study_needs_slot(on) is True
    settings = request_worker.settings_from_env({
        "POC_DAILY_CAP": "2",
        "POC_STUDY_LOCK": str(on),
        "POC_QUIET_START": "10:40",
        "POC_QUIET_END": "12:30",
    })
    assert settings.cap == 2
    assert settings.study_lock == on


def test_worker_does_not_start_during_the_window_cap_or_study(tmp_path, capsys):
    url = "https://github.com/pandas-dev/pandas/pull/70520"
    calls = []

    def run(pr_url, settings, secrets):
        calls.append(pr_url)
        raise AssertionError("check must not start")

    client = FakeClient([_issue(1, url)])
    request_worker.process_queue(
        client, _settings(tmp_path), _at(11, 0), {}, run=run, secrets=[TOKEN],
    )
    assert calls == []
    assert QUIET in client.posted[0][1]
    assert TOKEN not in client.posted[0][1]
    out = capsys.readouterr().out
    assert TOKEN not in out

    client = FakeClient([_issue(2, url)])
    request_worker.process_queue(
        client, _settings(tmp_path, cap=1), _at(9, 0),
        {"date_ist": "2026-10-21", "started": 1}, run=run, secrets=[TOKEN],
    )
    assert calls == []
    assert request_worker.CAP_MARKER in client.posted[0][1]

    lock = tmp_path / "study.lock"
    lock.write_text("yes\n")
    client = FakeClient([_issue(3, url)])
    request_worker.process_queue(
        client, _settings(tmp_path, study_lock=lock), _at(9, 0), {}, run=run, secrets=[TOKEN],
    )
    assert calls == []
    assert request_worker.STUDY_MARKER in client.posted[0][1]


QUIET = request_worker.QUIET_MARKER


def test_worker_runs_one_sandboxed_check_and_hides_the_token(tmp_path, capsys):
    url = "https://github.com/pandas-dev/pandas/pull/70520"
    calls = []

    def run(pr_url, settings, secrets):
        calls.append(request_worker.default_check_argv(settings.python, settings.root, pr_url))
        return request_worker.CheckResult(
            verdict="verified",
            reason=f"ok but token {TOKEN} sat in the log",
            report_markdown=f"# report\n{TOKEN}\n",
            run_id="pandas-70520",
            ok=True,
        )

    older = _issue(7, "https://github.com/numpy/numpy/pull/1", created="2026-10-21T02:00:00Z")
    newer_first = _issue(8, url, created="2026-10-21T00:00:00Z")
    running = _issue(9, url, labels=["request-a-check", "request-running"])
    assert request_worker.another_running([running, newer_first]) is True
    client = FakeClient([running])
    request_worker.process_queue(client, _settings(tmp_path), _at(9, 0), {}, run=run, secrets=[TOKEN])
    assert calls == []

    client = FakeClient([older, newer_first])
    state = request_worker.process_queue(
        client, _settings(tmp_path), _at(9, 0), {}, run=run, secrets=[TOKEN],
    )
    assert len(calls) == 1
    assert calls[0][-2:] == ["--pr", url]
    assert "--unsafe-no-sandbox" not in calls[0]
    assert state["started"] == 1
    body = client.posted[-1][1]
    assert "verified" in body and TOKEN not in body
    assert TOKEN not in client.reports[0][1]
    assert (8, ["request-done"]) in client.labels
    assert TOKEN not in capsys.readouterr().out

    bad = FakeClient([_issue(4, "not a link")])
    request_worker.process_queue(bad, _settings(tmp_path), _at(9, 0), {}, run=run, secrets=[TOKEN])
    assert any(labels == ["request-done"] for _n, labels in bad.labels)
    go = FakeClient([_issue(5, "https://github.com/golang/go/pull/9")], facts={"language": "Go", "private": False, "root": []})
    request_worker.process_queue(go, _settings(tmp_path), _at(9, 0), {}, run=run, secrets=[TOKEN])
    assert any("not a public Python library" in text for _n, text in go.posted)


def test_replay_export_and_committed_catalog_need_no_network(tmp_path, monkeypatch):
    def boom(*_args, **_kwargs):
        raise AssertionError("replay used the network")

    monkeypatch.setattr("urllib.request.urlopen", boom)
    sample = {
        "id": "pr-demo",
        "record_kind": "pr_run",
        "repo": "me/demo",
        "verdict": "verified",
        "reason": f"fine NEBIUS_API_KEY={SECRET}",
        "pr": {"number": 3, "url": "https://github.com/me/demo/pull/3", "title": "t"},
    }
    root = tmp_path / "src"
    (root / "tests" / "fixtures" / "day1").mkdir(parents=True)
    (root / "evals" / "fixtures").mkdir(parents=True)
    (root / "reports" / "samples" / "golden-v1").mkdir(parents=True)
    # Curated paths are absent on purpose: a tiny extra run is enough for the exporter test.
    run = root / "ops" / "runs" / "day" / "pr-demo"
    run.mkdir(parents=True)
    (run / "record.json").write_text(json.dumps(sample))
    catalog = export_replay.export(root, tmp_path / "replay", root / "ops" / "runs", root / "no-reports")
    stored = (tmp_path / "replay" / "checks" / "pr-demo" / "record.json").read_text()
    assert SECRET not in stored
    assert catalog["checks"][0]["verdict"] == "verified"

    repo_catalog = json.loads((Path(export_replay.ROOT) / "replay" / "catalog.json").read_text())
    assert repo_catalog["mode"] == "replay"
    verdicts = {row["verdict"] for row in repo_catalog["checks"]}
    assert {"needs_attention", "verified", "could_not_verify"} <= verdicts
    for row in repo_catalog["checks"]:
        record_path = Path(export_replay.ROOT) / "replay" / row["record"]
        text = record_path.read_text()
        assert SECRET not in text
        assert "NEBIUS_API_KEY=" not in text
        json.loads(text)
        if row.get("report_html"):
            html_path = Path(export_replay.ROOT) / "replay" / row["report_html"]
            assert html_path.is_file()
            assert "fonts.googleapis.com" not in html_path.read_text()
