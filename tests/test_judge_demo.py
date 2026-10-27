"""Judge demo: session key stays in memory, the request worker waits, replay needs no network."""
from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from ops import daily_run, export_replay, request_worker
from poc import console_api, demo_helper, session_key

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
    assert status == {"nebius_key": True, "tavily_key": False, "contree_project": False}
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
        lambda *_a, **_k: console_api.ConsoleRunPlan([], None, False, None),
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


@pytest.mark.real_key_gate
def test_live_check_without_a_key_is_refused(monkeypatch):
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
        lambda *_a, **_k: console_api.ConsoleRunPlan([], None, False, None),
    )
    for provider in ("nebius", "recorded", "none"):
        with pytest.raises(console_api.CheckRefused, match="Add your Nebius API key to run a live check."):
            console_api.start_check("https://github.com/me/demo/pull/4", model_provider=provider)


def test_codespace_refuses_unsandboxed_pull_request_code(monkeypatch):
    """A Codespace follows the same rule as every other host: refuse, unless the opt-in is set."""
    monkeypatch.setenv("CODESPACES", "true")
    monkeypatch.delenv("NEBIUS_API_KEY", raising=False)
    monkeypatch.delenv("NEBIUS_PROJECT_ID", raising=False)
    monkeypatch.delenv("POC_UNSAFE_NO_SANDBOX", raising=False)
    import guardrails.sandbox as sb
    monkeypatch.setattr(sb, "check", lambda: (False, "bwrap missing"))
    monkeypatch.setattr(console_api, "contree_usable", lambda *_a, **_k: False)
    plan = console_api.console_run_flags()
    assert plan.flags == []
    assert plan.refused is True
    assert plan.note and "will not run pull-request code" in plan.note
    with pytest.raises(ValueError, match="No sandbox available"):
        console_api.start_check("https://github.com/me/demo/pull/8", model_provider="recorded")
    monkeypatch.setenv("POC_UNSAFE_NO_SANDBOX", "1")
    opted = console_api.console_run_flags()
    assert opted.flags == ["--unsafe-no-sandbox"]
    assert opted.refused is False
    assert opted.warning and "POC_UNSAFE_NO_SANDBOX=1" in opted.warning


def test_codespace_uses_contree_without_the_unsandboxed_flag(monkeypatch):
    monkeypatch.setenv("CODESPACES", "true")
    monkeypatch.delenv("POC_UNSAFE_NO_SANDBOX", raising=False)
    monkeypatch.setattr(console_api, "contree_usable", lambda *_a, **_k: True)
    plan = console_api.console_run_flags()
    assert plan.flags == ["--sandbox-backend", "contree"]
    assert "--unsafe-no-sandbox" not in plan.flags
    assert plan.warning is None
    assert plan.note and "Contree" in plan.note


def test_worker_command_includes_the_swarm(tmp_path):
    """A requested pull request is checked with the advisory swarm on."""
    url = "https://github.com/me/demo/pull/3"
    argv = request_worker.default_check_argv("python3", tmp_path, url)
    assert "--swarm" in argv
    assert "--related-reports" in argv
    assert argv[-2:] == ["--pr", url]
    assert "--unsafe-no-sandbox" not in argv


def test_codespace_start_turns_the_swarm_on():
    """The Codespace one-command start sets POC_SWARM for the console, which also passes --swarm."""
    root = Path(__file__).resolve().parents[1]
    raw = (root / ".devcontainer" / "devcontainer.json").read_text()
    cfg = json.loads(raw)
    assert cfg["portsAttributes"]["8787"]["visibility"] == "private"
    assert "start-console.sh" in cfg["postStartCommand"]
    script = (root / ".devcontainer" / "start-console.sh").read_text()
    assert "POC_SWARM=1" in script
    assert "POC_SINGLE_USER=1" in script
    assert "poc.console_api" in script
    assert "gh codespace ports" in script
    secret = cfg["secrets"]["TAVILY_API_KEY"]
    assert "Your own Tavily API key" in secret["description"]
    assert "cannot run without the setup lookup" in secret["description"]
    assert "lookup is skipped" not in secret["description"]
    assert secret["documentationUrl"] == "https://app.tavily.com/"
    assert "tvly-" not in raw
    argv = console_api.console_daily_run_argv("https://github.com/me/demo/pull/3", "recorded")
    assert "--swarm" in argv


def _fake_gh(tmp_path: Path, listing: str) -> dict[str, str]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    gh = bin_dir / "gh"
    gh.write_text(f"#!/bin/sh\nprintf '%s\\n' '{listing}'\n")
    gh.chmod(0o755)
    env = os.environ.copy()
    env["PATH"] = f"{bin_dir}{os.pathsep}{env['PATH']}"
    env["POC_CONSOLE_DRY_RUN"] = "1"
    env.pop("POC_SINGLE_USER", None)
    return env


def test_startup_refuses_a_public_console_port(tmp_path):
    root = Path(__file__).resolve().parents[1]
    env = _fake_gh(tmp_path, '[{"port":8787,"visibility":"public"}]')
    proc = subprocess.run(
        ["bash", str(root / ".devcontainer" / "start-console.sh")],
        cwd=root, env=env, capture_output=True, text=True, check=False,
    )
    assert proc.returncode == 1
    assert "Set port 8787 back to private" in proc.stderr
    assert "start" not in proc.stdout


def test_startup_starts_when_the_port_is_private_or_unknown(tmp_path):
    root = Path(__file__).resolve().parents[1]
    private = _fake_gh(tmp_path, '[{"port":8787,"visibility":"private"}]')
    proc = subprocess.run(
        ["bash", str(root / ".devcontainer" / "start-console.sh")],
        cwd=root, env=private, capture_output=True, text=True, check=False,
    )
    assert proc.returncode == 0
    assert proc.stdout.strip() == "start"
    unknown = os.environ.copy()
    unknown["PATH"] = "/usr/bin:/bin"
    unknown["POC_CONSOLE_DRY_RUN"] = "1"
    proc = subprocess.run(
        ["bash", str(root / ".devcontainer" / "start-console.sh")],
        cwd=root, env=unknown, capture_output=True, text=True, check=False,
    )
    assert proc.returncode == 0
    assert proc.stdout.strip() == "start"


def test_request_form_warns_and_names_the_running_label():
    root = Path(__file__).resolve().parents[1]
    warning = "Do not paste an email address, a key, or any private information into the issue. The issue is public."
    template = (root / ".github" / "ISSUE_TEMPLATE" / "request-a-check.yml").read_text()
    readme = (root / "README.md").read_text()
    assert warning in template
    assert warning in readme
    assert "request-a-check" in readme and "request-running" in readme and "request-done" in readme
    assert "Do not make port 8787 public" in readme


def test_tavily_session_key_reaches_the_check_and_is_not_echoed(monkeypatch):
    secret = "tavily-session-secret-value"
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    session_key.clear_key("sess-t")
    session_key.set_tavily_key("sess-t", secret)
    status = session_key.public_status("sess-t")
    assert status["tavily_key"] is True
    assert status["nebius_key"] is False
    assert secret not in json.dumps(status)
    env, secrets = console_api.child_environment({"PATH": "/usr/bin"}, "recorded", "sess-t")
    assert env["TAVILY_API_KEY"] == secret
    assert secret in secrets
    assert secret not in os.environ.get("TAVILY_API_KEY", "")
    assert secret not in session_key.scrub(f"TAVILY_API_KEY={secret}", [secret])
    session_key.clear_key("sess-t")
    assert session_key.get_tavily_key("sess-t") is None


def test_worker_logs_a_missing_tavily_key_and_keeps_the_swarm(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    seen = {}

    def fake_run(argv, **kwargs):
        seen["argv"] = list(argv)
        seen["env"] = kwargs.get("env") or {}

        class Proc:
            stdout = ""
            stderr = ""
            returncode = 0

        return Proc()

    monkeypatch.setattr(request_worker.subprocess, "run", fake_run)
    monkeypatch.setattr(console_api, "find_record_for_pr", lambda *_args, **_kwargs: None)
    url = "https://github.com/me/demo/pull/3"
    result = request_worker.run_check(url, _settings(tmp_path), [])
    err = capsys.readouterr().err
    assert request_worker.TAVILY_MISSING in err
    assert "argv" not in seen
    assert result.ok is False
    assert result.verdict == "could_not_verify"
    assert result.reason == request_worker.TAVILY_MISSING
    assert "--swarm" in request_worker.default_check_argv("python3", tmp_path, url)


def test_requested_check_runs_the_tavily_lookup(tmp_path, monkeypatch):
    """A requested check is not a study, so the helper looks up when the key is set."""
    secret = "tavily-host-secret-value"
    monkeypatch.setenv("TAVILY_API_KEY", secret)
    seen = {}
    real_begin = demo_helper.begin_check

    def begin_check(runner, rec, repo, project, cache_dir, env=None, fetch=None):
        seen["active"] = demo_helper.active(runner)
        real_begin(
            runner, rec, repo, project, cache_dir, env=env,
            fetch=lambda *_args, **_kwargs: {
                "ok": True,
                "query": "setup",
                "results": [{"title": "setup notes", "url": "https://example.test/setup", "content": "install notes"}],
                "answer": "",
            },
        )
        seen["skipped"] = rec["demo_helper"]["tavily"]["skipped"]
        seen["live"] = rec["demo_helper"]["tavily"]["live_call"]
        raise RuntimeError("stop-after-tavily")

    monkeypatch.setattr(demo_helper, "begin_check", begin_check)
    runner = type("Run", (), {})()
    runner.bench = None
    runner.provider = None
    runner.runs = 1
    runner.workers = 1
    runner.test_timeout = 30
    runner.run_timeout = 30
    runner.build_timeout = 30
    runner.python = "python3"
    runner.model_provider = "recorded"
    runner.baseline = "full"
    item = {
        "pr": 9,
        "diff": "",
        "head_sha": "a" * 40,
        "url": "https://example.test/me/demo/pull/9",
        "title": "t",
        "body": "",
        "base_sha": "b" * 40,
        "author": "dev",
        "base_ref": "main",
        "updated_at_utc": "2026-10-21T00:00:00Z",
        "updated_at_ist": "2026-10-21 05:30 IST",
        "ci_state": "unknown",
        "ci_detail": "",
        "files": {"all": ["pkg/__init__.py"], "package_py": ["pkg/__init__.py"], "compiled": []},
    }
    cfg = {"pkg": "pkg", "dist": "pkg"}
    rdir = tmp_path / "run"
    rdir.mkdir()
    with pytest.raises(RuntimeError, match="stop-after-tavily"):
        daily_run.test_pr("me/demo", cfg, item, rdir, tmp_path / "work", runner, {})
    assert seen["active"] is True
    assert seen["skipped"] is False
    assert seen["live"] is True
    assert runner.bench is None


def test_worker_passes_the_tavily_key_without_printing_it(tmp_path, monkeypatch, capsys):
    secret = "tavily-host-secret-value"
    monkeypatch.setenv("TAVILY_API_KEY", secret)
    seen = {}

    def fake_run(argv, **kwargs):
        seen["argv"] = list(argv)
        seen["env"] = kwargs.get("env") or {}

        class Proc:
            stdout = f"saw {secret}"
            stderr = ""
            returncode = 0

        return Proc()

    monkeypatch.setattr(request_worker.subprocess, "run", fake_run)
    monkeypatch.setattr(console_api, "find_record_for_pr", lambda *_args, **_kwargs: None)
    url = "https://github.com/me/demo/pull/4"
    result = request_worker.run_check(url, _settings(tmp_path), [secret])
    err = capsys.readouterr().err
    assert request_worker.TAVILY_MISSING not in err
    assert secret not in err
    assert seen["env"].get("TAVILY_API_KEY") == secret
    assert "--swarm" in seen["argv"]
    assert secret not in result.reason


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


def test_worker_runs_one_sandboxed_check_and_hides_the_token(tmp_path, capsys, monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "worker-tavily-key-not-printed")
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
    assert "--swarm" in calls[0]
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
    counts = {v: sum(1 for row in repo_catalog["checks"] if row["verdict"] == v) for v in verdicts}
    # The page shows only the 30-PR batch on code version 0fa0016.
    assert counts == {"needs_attention": 8, "could_not_verify": 22}
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


def test_codespace_container_is_not_loosened_and_setup_is_robust():
    root = Path(__file__).resolve().parents[1]
    cfg = json.loads((root / ".devcontainer" / "devcontainer.json").read_text())
    assert cfg.get("privileged") is not True and "runArgs" not in cfg and "capAdd" not in cfg
    assert "post-create.sh" in cfg["postCreateCommand"]
    # Console checks use only keys typed into the form, so the Codespace does not ask for Nebius secrets.
    for name in ("NEBIUS_API_KEY", "CONTREE_PROJECT_ID", "NEBIUS_PROJECT_ID"):
        assert name not in cfg["secrets"]
    setup = (root / ".devcontainer" / "post-create.sh").read_text()
    assert "set -Eeuo pipefail" in setup and "npm run build" in setup and "poc-setup.log" in setup
    assert ".[dev,contree]" in setup
    start = (root / ".devcontainer" / "start-console.sh").read_text()
    assert "setsid" in start and "dist/index.html" in start and "listening" in start


def test_sandbox_environment_never_holds_the_model_or_lookup_keys(tmp_path, monkeypatch):
    """Host keys and keys a judge types into the console reach the check process, never untrusted code."""
    from guardrails.isolation import untrusted_env
    from poc import session_key
    monkeypatch.setenv("NEBIUS_API_KEY", "host-nebius-key-123")
    monkeypatch.setenv("TAVILY_API_KEY", "host-tavily-key-123")
    token = "judge-session-token"
    session_key.set_key(token, "typed-nebius-key-456")
    session_key.set_tavily_key(token, "typed-tavily-key-456")
    try:
        for provider in ("nebius", "recorded"):
            child, _ = console_api.child_environment(dict(os.environ), provider, token)
            for install in (False, True):
                env = untrusted_env(tmp_path / f"h-{provider}-{install}", install=install, base=child)
                dumped = json.dumps(env)
                assert "NEBIUS_API_KEY" not in env and "TAVILY_API_KEY" not in env
                for v in ("host-nebius-key-123", "host-tavily-key-123", "typed-nebius-key-456", "typed-tavily-key-456"):
                    assert v not in dumped
    finally:
        session_key.clear_key(token)


def _plan(monkeypatch, bwrap_ok: bool, token=None):
    import sys
    import types

    import guardrails.sandbox as sb
    monkeypatch.delenv("POC_UNSAFE_NO_SANDBOX", raising=False)
    monkeypatch.setattr(sb, "check", lambda: (bwrap_ok, "ok" if bwrap_ok else "bwrap: No permissions"))
    monkeypatch.setitem(sys.modules, "contree_sdk", types.ModuleType("contree_sdk"))
    return console_api.console_run_flags(token)


def test_sandbox_choice_uses_bubblewrap_without_contree_keys(monkeypatch):
    for k in ("NEBIUS_API_KEY", "NEBIUS_PROJECT_ID", "CONTREE_PROJECT_ID"):
        monkeypatch.delenv(k, raising=False)
    plan = _plan(monkeypatch, True)
    assert plan.flags == [] and not plan.refused


def test_sandbox_choice_uses_contree_with_the_judges_own_keys(monkeypatch):
    from poc import session_key
    for k in ("NEBIUS_API_KEY", "NEBIUS_PROJECT_ID", "CONTREE_PROJECT_ID"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("NEBIUS_API_KEY", "secret-nebius-123")
    monkeypatch.setenv("CONTREE_PROJECT_ID", "proj-123")
    # Server environment values are never used for a user check.
    assert _plan(monkeypatch, False).flags != ["--sandbox-backend", "contree"]
    monkeypatch.delenv("NEBIUS_API_KEY")
    monkeypatch.delenv("CONTREE_PROJECT_ID")
    token = "judge-contree"
    session_key.set_key(token, "typed-nebius-123")
    session_key.set_contree_project(token, "typed-proj-1")
    try:
        assert session_key.public_status(token)["contree_project"] is True
        assert _plan(monkeypatch, False, token).flags == ["--sandbox-backend", "contree"]
        env, secrets = console_api.child_environment({"PATH": "/usr/bin"}, "recorded", token, contree=True)
        assert env["NEBIUS_API_KEY"] == "typed-nebius-123" and env["NEBIUS_PROJECT_ID"] == "typed-proj-1"
        assert "typed-nebius-123" in secrets
    finally:
        session_key.clear_key(token)
    assert session_key.get_contree_project(token) is None


def test_sandbox_choice_refuses_without_bubblewrap_or_keys(monkeypatch):
    for k in ("NEBIUS_API_KEY", "NEBIUS_PROJECT_ID", "CONTREE_PROJECT_ID"):
        monkeypatch.delenv(k, raising=False)
    plan = _plan(monkeypatch, False)
    assert plan.refused and plan.flags == []
    assert "own Nebius key and project ID into the start form" in plan.note


def test_contree_keys_never_reach_pull_request_code(tmp_path, monkeypatch):
    from guardrails.isolation import untrusted_env
    from poc import session_key
    monkeypatch.setenv("CONTREE_PROJECT_ID", "proj-xyz-999")
    token = "judge-contree-2"
    session_key.set_key(token, "typed-nebius-789")
    session_key.set_contree_project(token, "typed-proj-789")
    try:
        child, _ = console_api.child_environment(dict(os.environ), "nebius", token, contree=True)
        for install in (False, True):
            env = untrusted_env(tmp_path / f"h{install}", install=install, base=child)
            dumped = json.dumps(env)
            for name in ("NEBIUS_API_KEY", "NEBIUS_PROJECT_ID", "CONTREE_PROJECT_ID", "TAVILY_API_KEY"):
                assert name not in env
            assert "typed-nebius-789" not in dumped and "typed-proj-789" not in dumped
    finally:
        session_key.clear_key(token)
