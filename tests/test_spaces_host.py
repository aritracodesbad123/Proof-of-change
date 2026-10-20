"""Hugging Face Spaces: no unsandboxed pull-request code; the vetted sample still finishes."""
import json

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


def test_without_space_id_the_block_does_not_apply(monkeypatch):
    monkeypatch.delenv("SPACE_ID", raising=False)
    assert spaces_host.block_reason("https://github.com/me/demo/pull/3", "nebius") is None


def test_recorded_demo_flags_are_not_the_study_defaults():
    assert console_api.recorded_demo_flags("recorded") == ["--runs", "1", "--run-timeout", "300", "--workers", "1"]
    assert console_api.recorded_demo_flags("none") == []
    argv = console_api.console_daily_run_argv("https://github.com/me/demo/pull/3", "none", [])
    assert "--swarm" in argv and "--console-job" in argv
    assert "--runs" not in argv
