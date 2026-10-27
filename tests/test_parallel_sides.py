"""Product checks: Contree setup overlaps probe planning, and main and PR run at the same time (mocked sandbox)."""
import argparse
import json
import threading
import time

import pytest

from ops import daily_run
from poc import contree_sandboxes

JUNIT = ('<?xml version="1.0"?><testsuite><testcase classname="t" name="test_{side}_{n}"/>'
         '<testcase classname="t" name="test_shared"/></testsuite>')


class Sess:
    """Fake Contree session: each side is its own checkpoint; records how many ops run at once."""

    def __init__(self, delay=0.2):
        self.delay, self.lock, self.live, self.peak, self.calls = delay, threading.Lock(), 0, 0, []

    def run_op(self, side, shell, **k):
        with self.lock:
            self.live += 1
            self.peak = max(self.peak, self.live)
            n = sum(1 for c in self.calls if c == side) + 1
            self.calls.append(side)
        time.sleep(self.delay)
        with self.lock:
            self.live -= 1
        if "pytest" in shell:
            out = (f"___POC_EXIT___0\n___POC_JUNIT___\n{JUNIT.format(side=side, n=n)}\n"
                   f"___POC_LOG___\n1 passed on {side}\n")
        else:
            out = json.dumps({"side": side, "value": 42}) + "\n"
        return {"exit_code": 0, "stdout": out, "stderr": ""}


@pytest.fixture
def sess(monkeypatch):
    s = Sess()
    monkeypatch.setattr(contree_sandboxes, "session", lambda: s)
    monkeypatch.setattr(daily_run, "_contree_ready", lambda: True)
    return s


def _args(**kw):
    return argparse.Namespace(**({"pr": "https://github.com/o/r/pull/1", "bench": None, "product_check": True} | kw))


def test_flag_on_for_product_checks_off_for_study_and_switchable(monkeypatch):
    monkeypatch.delenv(daily_run.PARALLEL_ENV, raising=False)
    assert daily_run.parallel_sides(_args())
    assert not daily_run.parallel_sides(_args(product_check=False))
    assert not daily_run.parallel_sides(_args(bench="study.json"))
    assert not daily_run.parallel_sides(_args(no_parallel_sides=True))
    monkeypatch.setenv(daily_run.PARALLEL_ENV, "0")
    assert not daily_run.parallel_sides(_args())


def _tests(tmp_path, parallel, name):
    rdir = tmp_path / name
    rdir.mkdir()
    targets = {"main": ["tests/test_a.py"], "pr": ["tests/test_a.py"]}
    per_run, results = daily_run.run_tests({"main": tmp_path / "vm", "pr": tmp_path / "vp"}, targets, rdir, tmp_path,
                                           3, "0", 60, 120, cwds={"main": tmp_path, "pr": tmp_path},
                                           keep_addopts=True, parallel=parallel)
    for r in per_run:
        r.pop("seconds")
    files = sorted((p.name, p.read_text()) for p in rdir.iterdir())
    return per_run, results, files


def test_parallel_tests_match_sequential_and_overlap(tmp_path, sess):
    seq = _tests(tmp_path, False, "seq")
    assert sess.peak == 1
    sess.calls.clear()
    par = _tests(tmp_path, True, "par")
    assert sess.peak == 2   # main and PR really ran at the same time
    assert par == seq       # same per-run order, same results, same files
    assert [r["side"] for r in par[0]] == [daily_run.SIDE_KEY[s] for s in ("main", "pr")] * 3


def test_parallel_tests_side_error_surfaces(tmp_path, sess, monkeypatch):
    real = sess.run_op
    def boom(side, shell, **k):
        if side == "pr":
            raise contree_sandboxes.ContreeError("transport down")
        return real(side, shell)
    sess.run_op = boom
    with pytest.raises(contree_sandboxes.ContreeError, match="transport down"):
        _tests(tmp_path, True, "err")


def _probe(tmp_path):
    p = tmp_path / "probe_x.py"
    p.write_text('"""\n---\nid: x\ntimeout_s: 30\n---\n"""\nprint(1)\n')
    return p


def test_parallel_probes_match_sequential_and_guard_runs_first(tmp_path, sess, monkeypatch):
    spec = {"id": "x", "timeout_s": 30}
    monkeypatch.setattr(daily_run.probes, "read_spec", lambda p: spec)
    monkeypatch.setattr(daily_run.probes, "entry",
                        lambda spec, got, files, per_run, source, path: {"got": got, "files": files,
                                                                         "per_run": [r | {"seconds": 0} for r in per_run]})
    path = _probe(tmp_path)
    guards = []
    out_s = tmp_path / "s"; out_s.mkdir()
    out_p = tmp_path / "p"; out_p.mkdir()
    seq = daily_run._contree_run_probe(path, out_s, 3, "model", lambda p: guards.append(p), True)
    n_seq = len(guards)
    sess.peak = 0
    par = daily_run._contree_run_probe(path, out_p, 3, "model", lambda p: guards.append(p), True, parallel=True)
    assert sess.peak == 2
    assert par == seq
    assert n_seq == 3 and len(guards) == 6
    assert sorted(x.name for x in out_s.iterdir()) == sorted(x.name for x in out_p.iterdir())


def test_parallel_probe_guard_refusal_stops_before_pr_runs(tmp_path, sess, monkeypatch):
    monkeypatch.setattr(daily_run.probes, "read_spec", lambda p: {"id": "x"})
    def guard(p):
        raise daily_run.freeze.FreezeError("changed after freeze")
    with pytest.raises(daily_run.freeze.FreezeError):
        daily_run._contree_run_probe(_probe(tmp_path), tmp_path, 3, "model", guard, parallel=True)
    assert sess.calls == []


def test_setup_runs_while_planning_and_merges_record():
    rec = {"parallel_sides": {"enabled": True}, "pr": {"n": 1}}
    started = threading.Event()

    def prepare(target):
        started.set()
        time.sleep(0.3)
        target["contree"] = {"main_uuid": "m"}
        target["machine"] = "contree"
        return None

    def plan():
        assert started.wait(2)   # setup is already running while the probes are planned
        time.sleep(0.3)
        rec["probe_plan"] = {"frozen": []}
        return ["p"]
    t0 = time.time()
    cnv, plan_out = daily_run._prepare_while_planning(rec, prepare, plan)
    assert time.time() - t0 < 0.55
    assert cnv is None and plan_out == ["p"]
    assert rec["contree"] == {"main_uuid": "m"} and rec["machine"] == "contree" and rec["probe_plan"]
    assert set(rec["parallel_sides"]["steps"]) == {"plan_probes", "setup_and_plan"}


def test_setup_refusal_comes_back_unchanged():
    cnv, plan = daily_run._prepare_while_planning({}, lambda t: "Contree setup failed: x", lambda: [])
    assert cnv == "Contree setup failed: x" and plan == []


def test_planning_error_wins_and_setup_still_finishes():
    done = []
    def prepare(t):
        time.sleep(0.1); done.append(1); raise RuntimeError("setup crash")
    def plan():
        raise ValueError("model crash")
    with pytest.raises(ValueError, match="model crash"):
        daily_run._prepare_while_planning({}, prepare, plan)
    assert done == [1]


def test_setup_error_surfaces_after_planning():
    def prepare(t):
        raise RuntimeError("setup crash")
    with pytest.raises(RuntimeError, match="setup crash"):
        daily_run._prepare_while_planning({}, prepare, lambda: [])
