"""Product runs stop after three refused GitHub logins, and only one run holds a run folder at a time."""
from __future__ import annotations

import io
import subprocess
import sys
import textwrap
import urllib.error
from pathlib import Path

import pytest

from ops import daily_run

SECRET = "ghp_should_never_be_printed_0123456789"


def _refuse(calls):
    def opener(req, timeout=None):
        calls.append(req.full_url)
        raise urllib.error.HTTPError(req.full_url, 401, "Bad credentials", {}, io.BytesIO(b"{}"))
    return opener


@pytest.fixture
def no_sleep(monkeypatch):
    monkeypatch.setattr(daily_run.time, "sleep", lambda s: None)


def test_three_401s_raise_auth_error_without_token(monkeypatch, no_sleep, capsys):
    calls = []
    monkeypatch.setattr(daily_run.urllib.request, "urlopen", _refuse(calls))
    gh = daily_run.GitHub(None, fail_fast_auth=True)
    gh.token = SECRET
    with pytest.raises(daily_run.GitHubAuthError) as exc:
        gh.json("/repos/o/r/pulls/1")
    assert len(calls) == 3 and len(set(calls)) == 1
    assert str(exc.value) == daily_run.AUTH_FAIL_MESSAGE
    assert SECRET not in str(exc.value)
    out = capsys.readouterr()
    assert SECRET not in out.out + out.err


def test_auth_error_passes_through_except_exception(monkeypatch, no_sleep):
    monkeypatch.setattr(daily_run.urllib.request, "urlopen", _refuse([]))
    gh = daily_run.GitHub(None, fail_fast_auth=True)
    with pytest.raises(daily_run.GitHubAuthError):
        try:
            gh.json("/repos/o/r/pulls/1")
        except Exception:  # noqa: BLE001 - the per-repository handlers look like this
            pytest.fail("a refused login must not be swallowed as an ordinary error")


def test_default_client_keeps_old_behaviour(monkeypatch, no_sleep):
    """Study runs build GitHub(None) without the flag: a 401 is still raised as an HTTPError after the retries."""
    calls = []
    monkeypatch.setattr(daily_run.urllib.request, "urlopen", _refuse(calls))
    with pytest.raises(urllib.error.HTTPError):
        daily_run.GitHub(None).json("/repos/o/r/pulls/1")
    assert len(calls) == 3


def test_main_maps_auth_error_to_distinct_exit(monkeypatch, capsys):
    def boom(argv=None):
        raise daily_run.GitHubAuthError(daily_run.AUTH_FAIL_MESSAGE)
    monkeypatch.setattr(daily_run, "_main", boom)
    assert daily_run.main([]) == daily_run.AUTH_FAIL_EXIT
    err = capsys.readouterr().err
    assert "auth problem: GitHub refused the login 3 times" in err
    assert daily_run.AUTH_FAIL_EXIT not in (0, 1, 2, daily_run.LOCK_HELD_EXIT)


def test_lock_contention_two_handles(tmp_path):
    first = daily_run.acquire_run_lock(tmp_path)
    try:
        with pytest.raises(daily_run.RunLockHeld, match="another run holds the lock"):
            daily_run.acquire_run_lock(tmp_path)
    finally:
        first.close()
    daily_run.acquire_run_lock(tmp_path).close()   # free again once the holder is gone


def test_lock_contention_two_processes(tmp_path):
    root = Path(daily_run.__file__).resolve().parents[1]
    holder = subprocess.Popen(
        [sys.executable, "-c", textwrap.dedent(f"""
            import sys, time
            sys.path.insert(0, {str(root)!r})
            from pathlib import Path
            from ops import daily_run
            h = daily_run.acquire_run_lock(Path({str(tmp_path)!r}))
            print("held", flush=True)
            sys.stdin.read()
        """)],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    try:
        assert holder.stdout.readline().strip() == "held"
        with pytest.raises(daily_run.RunLockHeld, match="another run holds the lock"):
            daily_run.acquire_run_lock(tmp_path)
    finally:
        holder.stdin.close()
        holder.wait(timeout=30)
    daily_run.acquire_run_lock(tmp_path).close()
