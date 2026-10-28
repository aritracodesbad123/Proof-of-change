"""Stalled git downloads: only `git clone` gets the low-speed limit, a stalled clone is retried (bounded, with a last
attempt without the limit), and fetches - including the pull/N/merge fetch whose failure changes the comparison
basis - never get the limit, so a silent wait while GitHub packs a large repo is not cut short. No network: a fake
`git` on PATH stands in for the server."""
import os
import stat
import sys
import time
from pathlib import Path

from ops import daily_run as dr


def test_clone_gets_low_speed_limits():
    out = dr.with_stall_limit(["git", "clone", "-q", "https://example.invalid/r.git", Path("src")])
    assert out[:5] == ["git", "-c", "http.lowSpeedLimit=1000", "-c", "http.lowSpeedTime=60"]
    assert out[5:7] == ["clone", "-q"]


def test_fetches_never_get_limits():
    for cmd in (["git", "-C", Path("src"), "fetch", "-q", "origin", "pull/5/merge"],
                ["git", "-C", "src", "fetch", "-q", "origin", "pull/5/head", "main"], ["git", "pull"],
                ["git", "ls-remote", "origin"]):
        assert dr.with_stall_limit(cmd) == cmd


def test_local_git_and_other_commands_unchanged():
    for cmd in (["git", "-C", "src", "worktree", "add", "x", "abc"], ["git", "rev-parse", "HEAD"], ["python", "-V"], []):
        assert dr.with_stall_limit(cmd) == cmd


def test_run_itself_adds_no_limits(tmp_path, monkeypatch):
    seen = {}

    class P:
        def __init__(self, cmd, **kw):
            seen["cmd"] = cmd
            raise RuntimeError("stop")

    monkeypatch.setattr(dr.subprocess, "Popen", P)
    try:
        dr.run(["git", "clone", "x", "y"], tmp_path / "log", env={"PATH": "/usr/bin"})
    except RuntimeError:
        pass
    assert seen["cmd"] == ["git", "clone", "x", "y"]


FAKE_GIT = r'''#!{py}
import os, sys, time
args = sys.argv[1:]
calls = os.path.join(os.environ["FAKE_DIR"], "calls")
with open(calls, "a") as fh:
    fh.write(" ".join(args) + "\n")
limited = "http.lowSpeedTime=1" in args
sub = [a for a in args if not a.startswith("http.") and a not in ("-c",)]
if "clone" in sub:
    n = sum(1 for line in open(calls) if " clone " in " " + line)
    stall = int(os.environ.get("FAKE_CLONE_STALLS", "0"))
    if n <= stall:
        # a stalled transfer: silent, then curl's low-speed abort when the limit is set
        time.sleep(1.5)
        if limited:
            sys.stderr.write("error: RPC failed; curl 28 Operation too slow\n")
            sys.exit(128)
    os.makedirs(sub[-1], exist_ok=True)
    open(os.path.join(sub[-1], "HEAD"), "w").close()
    sys.exit(0)
if "fetch" in sub:
    # GitHub packing a large repo: no bytes for a while, then success
    time.sleep(float(os.environ.get("FAKE_FETCH_SILENT_S", "0")))
    sys.exit(0)
sys.exit(0)
'''


def _fake_git(tmp_path, monkeypatch, **env):
    bindir = tmp_path / "bin"
    bindir.mkdir()
    g = bindir / "git"
    g.write_text(FAKE_GIT.replace("{py}", sys.executable))
    g.chmod(g.stat().st_mode | stat.S_IEXEC)
    e = {"PATH": f"{bindir}:{os.environ.get('PATH', '/usr/bin')}", "FAKE_DIR": str(tmp_path)}
    e.update({k: str(v) for k, v in env.items()})
    monkeypatch.setattr(dr, "GIT_LOW_SPEED_TIME", 1)
    return e


def _calls(tmp_path):
    return (tmp_path / "calls").read_text().splitlines()


def test_a_stalled_clone_is_retried_and_succeeds(tmp_path, monkeypatch):
    env = _fake_git(tmp_path, monkeypatch, FAKE_CLONE_STALLS=1)
    dest = tmp_path / "src"
    rc, _ = dr.clone_with_retry(["git", "clone", "-q", "https://example.invalid/r.git", dest], dest,
                                tmp_path / "log", env, timeout=30)
    assert rc == 0 and (dest / "HEAD").exists()
    clones = [c for c in _calls(tmp_path) if "clone" in c.split()]
    assert len(clones) == 2 and all("http.lowSpeedTime=1" in c for c in clones)
    assert "attempt 2 of" in (tmp_path / "log").read_text()


def test_retries_are_bounded_and_the_last_attempt_has_no_limit(tmp_path, monkeypatch):
    env = _fake_git(tmp_path, monkeypatch, FAKE_CLONE_STALLS=99)
    dest = tmp_path / "src"
    rc, _ = dr.clone_with_retry(["git", "clone", "-q", "https://example.invalid/r.git", dest], dest,
                                tmp_path / "log", env, timeout=30, attempts=2)
    clones = [c for c in _calls(tmp_path) if "clone" in c.split()]
    assert len(clones) == 3   # two limited attempts, then one without the limit
    assert "http.lowSpeedTime" in clones[0] and "http.lowSpeedTime" in clones[1]
    assert "http.lowSpeedTime" not in clones[2]
    assert rc == 0   # a slow but working server (a large repo being packed) still clones


def test_a_silent_merge_ref_fetch_on_a_large_repo_is_not_cut_short(tmp_path, monkeypatch):
    """The silent pack wait (longer than the 1 s test limit) must not fail the pull/N/merge fetch."""
    env = _fake_git(tmp_path, monkeypatch, FAKE_FETCH_SILENT_S=2)
    t0 = time.time()
    rc, _ = dr.run(["git", "-C", tmp_path, "fetch", "-q", "origin", "pull/7/merge"], tmp_path / "log", env=env,
                   timeout=30)
    assert rc == 0 and time.time() - t0 >= 2
    assert all("lowSpeed" not in c for c in _calls(tmp_path))


def test_merge_ref_fetch_is_retried_before_the_merge_base_fallback(tmp_path, monkeypatch):
    seen = []

    def fake_run(cmd, log, env=None, timeout=None, **kw):
        seen.append([str(c) for c in cmd])
        return (1 if "pull/9/merge" in map(str, cmd) else 0), 0.0

    class CP:
        stdout = ""
        returncode = 0
    monkeypatch.setattr(dr, "run", fake_run)
    monkeypatch.setattr(dr, "clone_with_retry", lambda c, d, log, env, timeout=900: fake_run(c, log))
    monkeypatch.setattr(dr.subprocess, "run", lambda *a, **k: CP())
    item = {"pr": 9, "base_ref": "main", "head_sha": "h" * 40}
    dr.source_pair("o/r", item, tmp_path, tmp_path / "log", sys.executable, 60)
    assert sum(1 for c in seen if "pull/9/merge" in c) == 2
