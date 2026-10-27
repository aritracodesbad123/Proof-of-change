"""POC_PARALLEL=1: Contree checkpoints built at once, prep alongside probe writing, main and PR pytest together.
Off by default; study runs never use it."""
import threading
import time
from types import SimpleNamespace

import pytest

from ops import daily_run as dr
from poc import contree_sandboxes as cs


def _runner(log, delay=0.2):
    lock = threading.Lock()
    live = {"n": 0, "max": 0}

    def run(shell, disposable, image_ref, timeout, files):
        with lock:
            live["n"] += 1
            live["max"] = max(live["max"], live["n"])
            log.append((shell, disposable, image_ref))
        time.sleep(delay)
        with lock:
            live["n"] -= 1
        uid = "img-pr" if "deadbeefpr" in shell else "img-main"
        return {"exit_code": 0, "stdout": "", "stderr": "", "uuid": uid}
    return run, live


def test_parallel_off_by_default(monkeypatch):
    monkeypatch.delenv("POC_PARALLEL", raising=False)
    a = SimpleNamespace(pr="https://github.com/o/r/pull/1", product_check=True, bench=None)
    assert dr.parallel_on(a) is False
    monkeypatch.setenv("POC_PARALLEL", "1")
    assert dr.parallel_on(a) is True


def test_parallel_never_on_study(monkeypatch):
    monkeypatch.setenv("POC_PARALLEL", "1")
    assert dr.parallel_on(SimpleNamespace(pr=None, product_check=False, bench=None)) is False
    assert dr.parallel_on(SimpleNamespace(pr="u", product_check=False, bench=None)) is False


def test_serial_prepare_forks_pr_from_main():
    log = []
    run, live = _runner(log, 0)
    sess = cs.prepare_source_pair("o/r", "deadbeefmain", "deadbeefpr", runner=run)
    assert sess.main_uuid == "img-main" and sess.pr_uuid == "img-pr"
    assert log[1][2] == "img-main"   # PR install forked from the main checkpoint


def test_parallel_prepare_builds_both_from_base_at_once():
    log = []
    run, live = _runner(log)
    t0 = time.time()
    sess = cs.prepare_source_pair("o/r", "deadbeefmain", "deadbeefpr", runner=run, parallel=True)
    assert time.time() - t0 < 0.39
    assert live["max"] == 2
    assert sess.main_uuid == "img-main" and sess.pr_uuid == "img-pr"
    assert all(img is None and not disp for _, disp, img in log)   # separate sandboxes from the base image


def test_parallel_prepare_main_failure_raises():
    def run(shell, disposable, image_ref, timeout, files):
        ok = "deadbeefpr" in shell
        return {"exit_code": 0 if ok else 1, "stdout": "", "stderr": "boom", "uuid": "x"}
    with pytest.raises(cs.ContreeError):
        cs.prepare_source_pair("o/r", "deadbeefmain", "deadbeefpr", runner=run, parallel=True)


def _fake_pytest(calls, live, lock):
    def once(side, targets, tt, rt, workers, jx, lg, keep):
        with lock:
            live["n"] += 1
            live["max"] = max(live["max"], live["n"])
        time.sleep(0.1)
        lg.write_text(f"{side} ok\n")
        with lock:
            live["n"] -= 1
            calls.append((side, jx.name))
        return 0, 0.1
    return once


@pytest.mark.parametrize("parallel", [False, True])
def test_run_tests_same_records_on_and_off(monkeypatch, tmp_path, parallel):
    calls, live, lock = [], {"n": 0, "max": 0}, threading.Lock()
    monkeypatch.setattr(dr, "_contree_ready", lambda: True)
    monkeypatch.setattr(dr, "_contree_pytest_once", _fake_pytest(calls, live, lock))
    per_run, results = dr.run_tests({"main": tmp_path / "vm", "pr": tmp_path / "vp"},
                                    {"main": ["t.py"], "pr": ["t.py"]}, tmp_path, tmp_path, 3, "0", 60, 600,
                                    cwds={"main": tmp_path, "pr": tmp_path}, parallel=parallel)
    assert [(r["side"], r["run"]) for r in per_run] == [(dr.SIDE_KEY[s], i) for i in (1, 2, 3) for s in ("main", "pr")]
    assert len(calls) == 6
    assert live["max"] == (2 if parallel else 1)


def test_run_tests_parallel_empty_main_runs_pr_alone(monkeypatch, tmp_path):
    calls, live, lock = [], {"n": 0, "max": 0}, threading.Lock()
    monkeypatch.setattr(dr, "_contree_ready", lambda: True)
    monkeypatch.setattr(dr, "_contree_pytest_once", _fake_pytest(calls, live, lock))
    per_run, _ = dr.run_tests({"main": tmp_path / "vm", "pr": tmp_path / "vp"}, {"main": [], "pr": ["t.py"]},
                              tmp_path, tmp_path, 1, "0", 60, 600, cwds={"main": tmp_path, "pr": tmp_path},
                              parallel=True)
    assert per_run[0]["exit"] == "no-targets" and [c[0] for c in calls] == ["pr"]
