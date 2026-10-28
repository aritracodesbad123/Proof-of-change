"""A product check requires the Tavily setup lookup. A study run keeps the earlier behaviour."""
from __future__ import annotations

import json
from datetime import datetime
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from ops import daily_run, request_worker
from poc import console_api, demo_helper, github_app, session_key, spaces_host, tavily_docs

SECRET = "tavily-secret-value-zzz"
PR = "https://github.com/acme/widgets/pull/4"


class _Resp:
    def __init__(self, raw: bytes):
        self._raw = raw

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return self._raw


def _urlopen(raw: bytes):
    def opener(_req, timeout=None):
        return _Resp(raw)
    return opener


def _runner(**extra):
    fields = {
        "bench": None,
        "pr": [PR],
        "product_check": True,
        "provider": None,
        "runs": 1,
        "workers": 1,
        "test_timeout": 30,
        "run_timeout": 30,
        "build_timeout": 30,
        "python": "python3",
        "model_provider": "none",
        "baseline": "full",
        "poc_commit": "a" * 40,
    }
    fields.update(extra)
    return SimpleNamespace(**fields)


def _item():
    return {
        "pr": 4,
        "diff": "",
        "head_sha": "a" * 40,
        "url": PR,
        "title": "t",
        "body": "",
        "base_sha": "b" * 40,
        "author": "dev",
        "base_ref": "main",
        "updated_at_utc": "2026-10-27T00:00:00Z",
        "updated_at_ist": "2026-10-27 05:30 IST",
        "ci_state": "unknown",
        "ci_detail": "",
        "files": {"all": ["pkg/__init__.py"], "package_py": ["pkg/__init__.py"], "compiled": [], "other": []},
    }


class _QuietThread:
    def __init__(self, target=None, daemon=None):
        self.target = target

    def start(self):
        pass


class _Queue:
    def __init__(self):
        self.posted = []
        self.labels = []

    def heartbeat(self, _now):
        return None

    def list_open_requests(self):
        return [{
            "number": 4,
            "body": PR,
            "state": "open",
            "created_at": "2026-10-27T01:00:00Z",
            "labels": ["request-a-check"],
        }]

    def comments(self, _number):
        return []

    def comment(self, number, body):
        self.posted.append((number, body))

    def add_labels(self, number, labels):
        self.labels.append((number, list(labels)))

    def repo_facts(self, _owner, _name):
        return {"language": "Python", "private": False}


def test_lookup_refuses_a_missing_or_blank_key(monkeypatch):
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    missing = tavily_docs.lookup("widgets install")
    assert missing["ok"] is False
    assert missing["refused"] is True
    assert missing["error"] == tavily_docs.MISSING_KEY
    assert "skipped" not in missing["error"]
    monkeypatch.setenv("TAVILY_API_KEY", "   ")
    blank = tavily_docs.lookup("widgets install")
    assert blank["error"] == tavily_docs.MISSING_KEY
    assert blank["refused"] is True


def test_lookup_stops_on_an_empty_or_invalid_response(monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", SECRET)
    monkeypatch.setattr(tavily_docs.urllib.request, "urlopen", _urlopen(b""))
    empty = tavily_docs.lookup("widgets install")
    assert empty["ok"] is False
    assert empty["error"] == tavily_docs.EMPTY_RESPONSE
    assert SECRET not in json.dumps(empty)

    monkeypatch.setattr(tavily_docs.urllib.request, "urlopen", _urlopen(b"not-json"))
    bad = tavily_docs.lookup("widgets install")
    assert bad["ok"] is False
    assert bad["error"] == tavily_docs.INVALID_RESPONSE

    monkeypatch.setattr(tavily_docs.urllib.request, "urlopen", _urlopen(b"[]"))
    not_object = tavily_docs.lookup("widgets install")
    assert not_object["error"] == tavily_docs.INVALID_RESPONSE


def test_lookup_failure_never_prints_the_key(monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", SECRET)

    def boom(_req, timeout=None):
        raise TimeoutError(f"timed out with {SECRET}")

    monkeypatch.setattr(tavily_docs.urllib.request, "urlopen", boom)
    out = tavily_docs.lookup("widgets install")
    blob = json.dumps(out)
    assert out["ok"] is False
    assert SECRET not in blob
    assert "[redacted]" in out["error"]


def test_worker_refuses_to_start_without_a_key(tmp_path, monkeypatch, capsys):
    def refuse(*_args, **_kwargs):
        raise AssertionError("the check started")

    monkeypatch.setattr(request_worker.subprocess, "run", refuse)
    for value in (None, "   "):
        if value is None:
            monkeypatch.delenv("TAVILY_API_KEY", raising=False)
        else:
            monkeypatch.setenv("TAVILY_API_KEY", value)
        result = request_worker.run_check(PR, request_worker.Settings(root=tmp_path), [])
        assert result.ok is False
        assert result.verdict == "could_not_verify"
        assert result.reason == request_worker.TAVILY_MISSING
    err = capsys.readouterr().err
    assert request_worker.TAVILY_MISSING in err
    assert SECRET not in err


def test_worker_queue_refuses_before_a_daily_slot(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    calls = []
    client = _Queue()
    state = {"date_ist": "2026-10-27", "started": 0}
    now = datetime(2026, 10, 27, 9, 0, tzinfo=ZoneInfo("Asia/Kolkata"))
    out = request_worker.process_queue(
        client, request_worker.Settings(root=tmp_path, state_path=tmp_path / "state.json"),
        now, state, run=lambda *_a, **_k: calls.append("ran"),
    )
    assert calls == []
    assert out["started"] == 0
    assert client.labels == []
    assert len(client.posted) == 1
    assert "Tavily key missing" in client.posted[0][1]
    assert tavily_docs.MISSING_KEY in capsys.readouterr().err


def test_product_main_refuses_before_any_git(monkeypatch, capsys, tmp_path):
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    called = {"n": 0}

    def boom(*_args, **_kwargs):
        called["n"] += 1
        raise AssertionError("resolve_poc_commit ran")

    monkeypatch.setattr(daily_run, "resolve_poc_commit", boom)
    with pytest.raises(SystemExit) as exc:
        daily_run.main([
            "--pr", PR, "--product-check", "--model-provider", "none",
            "--ops-dir", str(tmp_path / "ops"), "--no-report", "--min-free-gb", "0",
        ])
    assert exc.value.code == 1
    assert called["n"] == 0
    err = capsys.readouterr().err
    assert tavily_docs.MISSING_KEY in err
    assert SECRET not in err


def test_study_paths_are_not_refused(monkeypatch, capsys, tmp_path):
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    study = SimpleNamespace(pr=None, product_check=True, bench=None, select_only=False, report_only=False)
    bench = SimpleNamespace(pr=[PR], product_check=True, bench="bench.csv", select_only=False, report_only=False)
    plain = SimpleNamespace(pr=[PR], product_check=False, bench=None, select_only=False, report_only=False)
    select = SimpleNamespace(pr=[PR], product_check=True, bench=None, select_only=True, report_only=False)
    report = SimpleNamespace(pr=[PR], product_check=True, bench=None, select_only=False, report_only=True)
    for args in (study, bench, plain, select, report):
        assert daily_run.product_keys_start_refusal(args) is None
    product = SimpleNamespace(pr=[PR], product_check=True, bench=None, select_only=False, report_only=False)
    monkeypatch.setenv("NEBIUS_API_KEY", "n-key")
    monkeypatch.setenv("NEBIUS_PROJECT_ID", "n-proj")
    assert daily_run.product_keys_start_refusal(product).endswith(tavily_docs.MISSING_KEY)
    monkeypatch.setenv("TAVILY_API_KEY", SECRET)
    assert daily_run.product_keys_start_refusal(product) is None

    def reached(*_args, **_kwargs):
        raise SystemExit("reached-commit")

    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    monkeypatch.setattr(daily_run, "resolve_poc_commit", reached)
    with pytest.raises(SystemExit) as exc:
        daily_run.main(["--model-provider", "none", "--ops-dir", str(tmp_path / "ops"), "--no-report"])
    assert exc.value.code == "reached-commit"
    assert "Tavily key missing" not in capsys.readouterr().err


def test_github_app_refuses_without_calling_the_runner(capsys):
    called = {"n": 0}

    def runner(_argv):
        called["n"] += 1
        return 0

    plan = {"action": "run", "repo": "me/demo", "pr": 2, "head_sha": "c" * 40}
    out = github_app.apply(plan, dry_run=False, env={
        "POC_DEMO_REPOS": "me/demo", "GITHUB_APP_INSTALLATION_TOKEN": "tok",
    }, runner=runner)
    assert out["ok"] is False
    assert out["error"] == tavily_docs.MISSING_KEY
    assert called["n"] == 0
    err = capsys.readouterr().err
    assert tavily_docs.MISSING_KEY in err
    assert "tok" not in err


@pytest.mark.real_tavily_gate
def test_hosted_console_uses_the_server_key_and_refuses_when_it_is_missing(monkeypatch):
    monkeypatch.delenv("CODESPACES", raising=False)
    monkeypatch.setattr(console_api.threading, "Thread", _QuietThread)
    monkeypatch.setattr(
        console_api, "console_run_flags",
        lambda *_a, **_k: console_api.ConsoleRunPlan(["--unsafe-no-sandbox"], "test", False, None),
    )
    secret = "server-tavily-secret-value"
    monkeypatch.setenv("TAVILY_API_KEY", secret)
    session_key.set_tavily_key("sess-hosted", "typed-tavily-secret-xyz")
    try:
        job = console_api.start_check(PR, model_provider="recorded", session_token="sess-hosted")
    finally:
        session_key.clear_key("sess-hosted")
    assert job["status"] == "queued"
    blob = json.dumps(job)
    assert secret not in blob
    assert "typed-tavily-secret-xyz" not in blob

    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    session_key.set_tavily_key("sess-hosted", "typed-tavily-secret-xyz")
    try:
        with pytest.raises(console_api.CheckRefused, match="This server has no Tavily key set"):
            console_api.start_check(PR, model_provider="recorded", session_token="sess-hosted")
    finally:
        session_key.clear_key("sess-hosted")


@pytest.mark.real_tavily_gate
def test_codespace_still_refuses_without_a_key_and_starts_with_one(monkeypatch):
    monkeypatch.setattr(console_api.threading, "Thread", _QuietThread)
    monkeypatch.setattr(
        console_api, "console_run_flags",
        lambda *_a, **_k: console_api.ConsoleRunPlan(["--unsafe-no-sandbox"], "test", False, None),
    )
    monkeypatch.setenv("CODESPACES", "true")
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    with pytest.raises(console_api.CheckRefused, match="Tavily key missing"):
        console_api.start_check(PR, model_provider="recorded")
    secret = "codespace-tavily-secret"
    monkeypatch.setenv("TAVILY_API_KEY", secret)
    job = console_api.start_check(PR, model_provider="recorded")
    assert job["status"] == "queued"
    assert secret not in json.dumps(job)


@pytest.mark.real_tavily_gate
def test_saved_sample_playback_does_not_need_the_key(monkeypatch):
    monkeypatch.delenv("CODESPACES", raising=False)
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    monkeypatch.setattr(spaces_host, "sandbox_open", lambda: (False, "bwrap down"))
    monkeypatch.setattr(console_api.threading, "Thread", _QuietThread)
    job = console_api.start_check(spaces_host.VETTED_URL, model_provider="recorded", session_token="sess-play")
    assert job["status"] == "queued"
    assert "Tavily key missing" not in json.dumps(job)


def test_lookup_failure_mid_run_stops_with_a_reason(tmp_path, monkeypatch, capsys):
    from ops import daily_run as _dr
    monkeypatch.setattr(_dr, "live_pr_refusal", lambda *a, **k: None)   # an open pull request
    monkeypatch.setenv("TAVILY_API_KEY", SECRET)

    def failed(_query, timeout=None, env=None):
        return {"ok": False, "error": f"timed out {SECRET}", "query": _query, "results": []}

    monkeypatch.setattr(demo_helper, "live_fetch", failed)
    rec = daily_run.test_pr("acme/widgets", {"pkg": "widgets", "dist": "widgets"}, _item(),
                            tmp_path / "run", tmp_path / "work", _runner(), {})
    assert rec["verdict"] == "could_not_verify"
    assert rec["reason"].startswith("could not verify: the setup lookup failed")
    blob = json.dumps(rec) + capsys.readouterr().err
    assert SECRET not in blob
    assert (tmp_path / "run" / "widgets-4" / "record.json").is_file()


def test_zero_hits_do_not_stop_a_product_lookup(monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", SECRET)
    out = demo_helper.lookup_project(
        "acme/widgets", "widgets", None, required=True,
        fetch=lambda *_a, **_k: {"ok": True, "results": [], "query": "q"},
    )
    assert out["ok"] is True
    assert out["stop"] is False
    assert out["result_count"] == 0
    assert out["queries"]


def test_findings_are_stored_on_the_record(tmp_path, monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", SECRET)

    def fetch(query, timeout=None, env=None):
        return {
            "ok": True,
            "query": query,
            "answer": "widgets installs from its own page",
            "results": [{
                "title": "widgets install guide",
                "url": "https://github.com/acme/widgets/blob/main/README.md",
                "content": "Install widgets with pip.",
            }],
        }

    block = demo_helper.begin_check(_runner(), {}, "acme/widgets", "widgets", tmp_path, fetch=fetch)
    found = block["tavily"]
    assert found["queries"]
    assert found["result_count"] == 1
    assert found["results"][0]["title"] == "widgets install guide"
    assert found["results"][0]["url"].startswith("https://github.com/acme/widgets/")
    notes = "\n".join(block["notes"])
    assert "Query: " in notes
    assert "Source: widgets install guide" in notes
    assert SECRET not in json.dumps(block)


def test_related_lookup_failure_leaves_the_verdict(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("TAVILY_API_KEY", SECRET)
    monkeypatch.setattr(daily_run, "check_record", lambda rec: [])
    monkeypatch.setattr(daily_run, "stamp_model_use", lambda rec, runner: None)
    ran = {"n": 0}

    def run_swarm(_provider, rec):
        ran["n"] += 1
        assert rec["verdict"] == "verified"
        block = rec.get("related_reports") or {}
        assert block.get("text", "") == ""

    monkeypatch.setattr(daily_run.agents, "run_swarm", run_swarm)

    def lookup(*_args, **_kwargs):
        raise RuntimeError(f"HTTP 500 {SECRET}")

    monkeypatch.setattr(tavily_docs, "lookup", lookup)
    rec = {
        "files": {"package_py": [], "compiled": [], "other": []},
        "per_run": [],
        "verdict": "verified",
        "reason": "ok",
        "repo": "acme/widgets",
        "pr": {"number": 4, "title": "fix the window", "repo": "acme/widgets"},
    }
    prdir = tmp_path / "related"
    prdir.mkdir()
    daily_run.finish(rec, prdir, tmp_path / "work", 0.0, SimpleNamespace(
        related_reports=True, bench=None, pr=[PR], swarm=True, provider=object(), model_skipped=None,
    ))
    logged = capsys.readouterr()
    assert ran["n"] == 1
    assert rec["verdict"] == "verified"
    assert rec["reason"] == "ok"
    assert rec["related_reports"]["status"] == "error"
    assert "the Tavily lookup failed" in rec["related_reports"]["reason"]
    blob = json.dumps(rec) + logged.out + logged.err
    assert SECRET not in blob
    assert SECRET not in (prdir / "record.json").read_text()


def test_setup_lookup_exception_is_redacted_from_the_record_and_the_console(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("TAVILY_API_KEY", SECRET)

    def fetch(_query, timeout=None, env=None):
        raise RuntimeError(f"timed out while using {SECRET}")

    rec = {}
    block = demo_helper.begin_check(_runner(), rec, "acme/widgets", "widgets", tmp_path, fetch=fetch)
    logged = capsys.readouterr()
    blob = json.dumps(rec) + logged.out + logged.err
    assert SECRET not in blob
    assert block["tavily"]["stop"] is True
    assert "could not verify: the setup lookup failed" in block["tavily"]["stop_reason"]
    assert "[redacted]" in block["tavily"]["stop_reason"]
