"""Hugging Face Spaces: no unsandboxed pull-request code; the vetted sample still finishes."""
import json
import time

import pytest

from poc import console_api, spaces_host


def test_provider_names_accept_the_space_secret_names():
    from poc import console_auth
    flags = console_auth.provider_config({
        "GITHUB_OAUTH_CLIENT_ID": "id",
        "GITHUB_OAUTH_CLIENT_SECRET": "secret",
    })
    assert flags["github"] is True
    assert console_auth.smtp_configured({
        "SMTP_HOST": "smtp.example",
        "SMTP_USER": "u",
        "SMTP_PASSWORD": "p",
        "SMTP_FROM": "a@b.c",
    })


def test_a_space_without_a_sandbox_only_plays_the_vetted_sample(tmp_path, monkeypatch):
    monkeypatch.setenv("SPACE_ID", "demo-space")
    monkeypatch.delenv("NEBIUS_API_KEY", raising=False)
    monkeypatch.delenv("NEBIUS_PROJECT_ID", raising=False)
    import guardrails.sandbox as sb
    monkeypatch.setattr(sb, "check", lambda: (False, "bwrap: user namespaces are not available"))
    monkeypatch.setattr(console_api, "RUNS_ROOT", tmp_path)
    monkeypatch.setattr(console_api, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(spaces_host.time, "sleep", lambda _s: None)

    def refuse_process(*_args, **_kwargs):
        raise AssertionError("pull-request code must not start without a sandbox")

    monkeypatch.setattr(console_api.subprocess, "Popen", refuse_process)
    with pytest.raises(ValueError, match="cannot start a sandbox"):
        console_api.start_check("https://github.com/me/demo/pull/9", model_provider="nebius")
    with pytest.raises(ValueError, match="secret keys and the network"):
        console_api.start_check(spaces_host.VETTED_URL, model_provider="nebius")

    job = console_api.start_check(spaces_host.VETTED_URL, model_provider="recorded", owner="ada")
    assert job["run_flags"] == []
    assert "unsafe" not in (job.get("run_note") or "")
    deadline = spaces_host.time.time() + 5
    while spaces_host.time.time() < deadline:
        got = console_api.get_job(job["id"], owner="ada")
        if got and got["status"] in {"done", "failed", "timed out"}:
            break
        spaces_host.time.sleep(0.01)
    # sleep is patched, so poll the thread by joining the non-daemon... the worker is daemon.
    # Run the playback inline if the thread has not been scheduled yet.
    if console_api.get_job(job["id"], owner="ada")["status"] == "queued":
        # The worker is already started. Give the real clock a moment via the unpatched wait.
        import time as real_time
        for _ in range(50):
            real_time.sleep(0.02)
            if console_api.get_job(job["id"], owner="ada")["status"] != "queued":
                break
    got = console_api.get_job(job["id"], owner="ada")
    assert got["status"] == "done"
    assert got["record"]["playback"] is True
    assert got["record"]["verdict"] == "needs_attention"
    assert console_api.get_job(job["id"], owner="someone-else") is None
    saved = json.loads((tmp_path / "playback" / "mlxtend-1229" / "record.json").read_text())
    assert saved["playback"] is True
    assert "owner" not in saved


def test_recorded_playback_finishes_on_any_host_without_a_sandbox(tmp_path, monkeypatch):
    """The vetted sample plays back wherever the sandbox is closed. No child process starts."""
    monkeypatch.delenv("SPACE_ID", raising=False)
    monkeypatch.delenv("NEBIUS_API_KEY", raising=False)
    monkeypatch.delenv("NEBIUS_PROJECT_ID", raising=False)
    monkeypatch.delenv("POC_UNSAFE_NO_SANDBOX", raising=False)
    import guardrails.sandbox as sb
    monkeypatch.setattr(sb, "check", lambda: (False, "bwrap down"))
    monkeypatch.setattr(console_api, "RUNS_ROOT", tmp_path)
    monkeypatch.setattr(console_api, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(spaces_host.time, "sleep", lambda _s: None)
    assert spaces_host.playback_only(spaces_host.VETTED_URL, "recorded") is True
    assert spaces_host.playback_only("https://github.com/me/demo/pull/9", "recorded") is False

    def refuse_process(*_args, **_kwargs):
        raise AssertionError("pull-request code must not start without a sandbox")

    monkeypatch.setattr(console_api.subprocess, "Popen", refuse_process)
    with pytest.raises(ValueError, match="No sandbox available"):
        console_api.start_check("https://github.com/me/demo/pull/9", model_provider="recorded")

    job = console_api.start_check(spaces_host.VETTED_URL, model_provider="recorded")
    assert job["run_flags"] == []
    assert job["refused"] is False
    deadline = time.time() + 5
    while time.time() < deadline:
        got = console_api.get_job(job["id"])
        if got and got["status"] in {"done", "failed", "timed out"}:
            break
        time.sleep(0.02)
    got = console_api.get_job(job["id"])
    assert got["status"] == "done"
    assert got["record"]["playback"] is True
    assert "No pull-request code ran" in (got.get("log_tail") or "")


def test_unsafe_opt_in_still_plays_back_the_vetted_sample(tmp_path, monkeypatch):
    """With POC_UNSAFE_NO_SANDBOX=1 and no sandbox, the vetted sample still plays back.

    A real check would run unsandboxed. This sample does not start a process.
    """
    monkeypatch.delenv("SPACE_ID", raising=False)
    monkeypatch.delenv("NEBIUS_API_KEY", raising=False)
    monkeypatch.delenv("NEBIUS_PROJECT_ID", raising=False)
    monkeypatch.setenv("POC_UNSAFE_NO_SANDBOX", "1")
    import guardrails.sandbox as sb
    monkeypatch.setattr(sb, "check", lambda: (False, "bwrap down"))
    monkeypatch.setattr(console_api, "RUNS_ROOT", tmp_path)
    monkeypatch.setattr(console_api, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(spaces_host.time, "sleep", lambda _s: None)

    plan = console_api.console_run_flags()
    assert plan.refused is False
    assert "--unsafe-no-sandbox" in plan.flags
    assert spaces_host.playback_only(spaces_host.VETTED_URL, "recorded") is True

    started: list[object] = []

    def refuse_process(*args, **kwargs):
        started.append((args, kwargs))
        raise AssertionError("the vetted sample must play back and must not start a process")

    monkeypatch.setattr(console_api.subprocess, "Popen", refuse_process)
    job = console_api.start_check(spaces_host.VETTED_URL, model_provider="recorded")
    assert job["playback"] is True
    assert job["run_flags"] == []
    assert job["refused"] is False
    deadline = time.time() + 5
    while time.time() < deadline:
        got = console_api.get_job(job["id"])
        if got and got["status"] in {"done", "failed", "timed out"}:
            break
        time.sleep(0.02)
    got = console_api.get_job(job["id"])
    assert got["status"] == "done"
    assert got["record"]["playback"] is True
    assert "No pull-request code ran" in (got.get("log_tail") or "")
    assert started == []


def test_without_space_id_the_block_does_not_apply(monkeypatch):
    monkeypatch.delenv("SPACE_ID", raising=False)
    assert spaces_host.block_reason("https://github.com/me/demo/pull/3", "nebius") is None


def test_recorded_demo_flags_are_not_the_study_defaults():
    assert console_api.recorded_demo_flags("recorded") == ["--runs", "1", "--run-timeout", "300", "--workers", "1"]
    assert console_api.recorded_demo_flags("none") == []
    argv = console_api.console_daily_run_argv("https://github.com/me/demo/pull/3", "none", [])
    assert "--swarm" in argv and "--console-job" in argv
    assert "--runs" not in argv
