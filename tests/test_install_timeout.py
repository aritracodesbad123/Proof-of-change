"""A hanging install whose child never exits (and one that escapes via setsid) is killed with its whole tree at the
limit, and install_side records it as 'timed out', not as a failed install."""
import os, time
from pathlib import Path
import pytest
from ops import daily_run as d

HANG = "setsid sleep 1000 & echo $! > {pf}; sleep 1000 & echo $! >> {pf}; wait"

def _alive(pid):
    try: return Path(f"/proc/{pid}/stat").read_text().split(")")[-1].split()[0] != "Z"
    except FileNotFoundError: return False

def test_run_kills_whole_tree_at_limit(tmp_path):
    pf = tmp_path / "pids"
    t0 = time.time()
    rc, _ = d.run(["bash", "-c", HANG.format(pf=pf)], tmp_path / "log", env=d.base_env(tmp_path / "h"), timeout=2, sbx=None)
    assert rc == "timeout" and time.time() - t0 < 10
    time.sleep(0.5)
    assert [p for p in map(int, pf.read_text().split()) if _alive(p)] == []
    assert "TIMEOUT after 2s" in (tmp_path / "log").read_text()

def test_install_side_records_timed_out(tmp_path, monkeypatch):
    monkeypatch.setattr(d, "run", lambda *a, **k: ("timeout", 2.0))
    venv, src = tmp_path / "venv-main", tmp_path / "side-main"; src.mkdir()
    ok, why = d.install_side(venv, src, None, tmp_path / "setup-main.log", "3.12", 2, None)
    assert not ok and why.startswith("install timed out after 2s")
    assert "install failed" not in why
