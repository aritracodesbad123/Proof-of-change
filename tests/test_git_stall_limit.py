from pathlib import Path

from ops import daily_run as dr


def test_clone_gets_low_speed_limits():
    out = dr.with_stall_limit(["git", "clone", "-q", "https://example.invalid/r.git", Path("src")])
    assert out[:5] == ["git", "-c", "http.lowSpeedLimit=1000", "-c", "http.lowSpeedTime=60"]
    assert out[5:7] == ["clone", "-q"]


def test_fetch_after_dash_c_dir_gets_limits():
    out = dr.with_stall_limit(["git", "-C", Path("src"), "fetch", "-q", "origin", "abc"])
    assert "http.lowSpeedLimit=1000" in out and out[-4:] == ["fetch", "-q", "origin", "abc"]


def test_local_git_and_other_commands_unchanged():
    for cmd in (["git", "-C", "src", "worktree", "add", "x", "abc"], ["git", "rev-parse", "HEAD"], ["python", "-V"], []):
        assert dr.with_stall_limit(cmd) == cmd


def test_run_passes_limits_to_git(tmp_path, monkeypatch):
    seen = {}

    class P:
        def __init__(self, cmd, **kw):
            seen["cmd"] = cmd
            raise RuntimeError("stop")

    monkeypatch.setattr(dr.subprocess, "Popen", P)
    try:
        dr.run(["git", "fetch", "origin"], tmp_path / "log", env={"PATH": "/usr/bin"})
    except RuntimeError:
        pass
    assert seen["cmd"][:3] == ["git", "-c", "http.lowSpeedLimit=1000"]
