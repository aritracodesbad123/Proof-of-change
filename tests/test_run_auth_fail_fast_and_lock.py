"""Product runs stop after three refused GitHub logins, and only one run holds a run folder at a time."""
from __future__ import annotations

import io
import re
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


# ---------------------------------------------------------------- through main()
PR_URL = "https://github.com/example-org/widgets/pull/7"


def _main_env(monkeypatch, tmp_path, seen):
    """main() up to PR selection, with GitHub answering 401 to every API call."""
    monkeypatch.setenv("TAVILY_API_KEY", "test-tavily-key-for-product-checks")
    monkeypatch.setattr(daily_run, "sync_to_origin_main", lambda *_a, **_k: "a" * 40)
    monkeypatch.setattr(daily_run, "resolve_poc_commit", lambda *_a, **_k: "a" * 40)
    monkeypatch.setattr(daily_run, "resolve_python", lambda _p: "python3")
    monkeypatch.setattr(daily_run, "ensure_tools", lambda: {})
    monkeypatch.setattr(daily_run.time, "sleep", lambda s: None)
    monkeypatch.setattr(daily_run.urllib.request, "urlopen", _refuse([]))

    def chosen(gh, _repo, _cfg, _spec):
        seen.append(gh.fail_fast_auth)
        try:
            gh.json("/repos/example-org/widgets/pulls/7")
        except urllib.error.HTTPError as e:
            seen.append(e.code)
            raise
        return []

    monkeypatch.setattr(daily_run, "chosen_items", chosen)
    return ["--pr", PR_URL, "--ops-dir", str(tmp_path / "ops"), "--no-report", "--min-free-gb", "0",
            "--model-provider", "none", "--baseline", "tests"]


def test_non_product_run_keeps_old_401_handling_through_main(monkeypatch, tmp_path, capsys):
    seen = []
    code = daily_run.main(_main_env(monkeypatch, tmp_path, seen) + ["--date", "x-study"])
    assert seen == [False, 401]           # old retries, then the HTTPError is handled as before
    assert code != daily_run.AUTH_FAIL_EXIT
    assert "auth problem" not in capsys.readouterr().err
    assert not (tmp_path / "ops" / "runs" / "x-study" / daily_run.RUN_LOCK_NAME).exists()


def test_product_run_stops_on_401_through_main(monkeypatch, tmp_path, capsys):
    seen = []
    code = daily_run.main(_main_env(monkeypatch, tmp_path, seen) + ["--date", "x-prod", "--product-check"])
    assert code == daily_run.AUTH_FAIL_EXIT and seen == [True]
    assert daily_run.AUTH_FAIL_MESSAGE in capsys.readouterr().err


def test_product_run_exits_4_when_lock_is_held_through_main(monkeypatch, tmp_path, capsys):
    seen = []
    args = _main_env(monkeypatch, tmp_path, seen) + ["--date", "x-locked", "--product-check"]
    holder = daily_run.acquire_run_lock(tmp_path / "ops" / "runs" / "x-locked")
    try:
        assert daily_run.main(args) == daily_run.LOCK_HELD_EXIT
    finally:
        holder.close()
    assert seen == []                     # stopped before any GitHub call
    assert "another run holds the lock" in capsys.readouterr().err


def test_product_check_folder_has_seconds_and_pr(monkeypatch, tmp_path):
    seen = []
    daily_run.main(_main_env(monkeypatch, tmp_path, seen) + ["--product-check"])
    names = [p.name for p in (tmp_path / "ops" / "runs").iterdir()]
    assert len(names) == 1 and re.fullmatch(r"\d{4}-\d{2}-\d{2}-check-\d{6}-pr7", names[0])


def test_lock_is_freed_when_the_holder_is_killed(tmp_path):
    root = Path(daily_run.__file__).resolve().parents[1]
    holder = subprocess.Popen(
        [sys.executable, "-c", textwrap.dedent(f"""
            import sys, time
            sys.path.insert(0, {str(root)!r})
            from pathlib import Path
            from ops import daily_run
            h = daily_run.acquire_run_lock(Path({str(tmp_path)!r}))
            print("held", flush=True)
            time.sleep(600)
        """)],
        stdout=subprocess.PIPE, text=True)
    try:
        assert holder.stdout.readline().strip() == "held"
        with pytest.raises(daily_run.RunLockHeld):
            daily_run.acquire_run_lock(tmp_path)
    finally:
        holder.kill()
        holder.wait(timeout=30)
    assert (tmp_path / daily_run.RUN_LOCK_NAME).exists()   # stale file left behind, but no stale lock
    daily_run.acquire_run_lock(tmp_path).close()
