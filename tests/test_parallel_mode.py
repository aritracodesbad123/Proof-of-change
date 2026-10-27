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


# --- review follow-ups: versions per side, locks, main failure, planning errors, full on/off records -------------

class _ArgvSess:
    def __init__(self, main, pr):
        self.out = {"main": main, "pr": pr}

    def run_argv(self, side, argv, timeout=120, cwd="/work"):
        v = self.out[side]
        if v is None:
            return {"exit_code": 1, "stdout": "", "stderr": "x"}
        import json
        return {"exit_code": 0, "stdout": json.dumps([{"name": k, "version": x} for k, x in v.items()])}


def test_side_packages_same_versions_pass():
    info = cs.side_packages(_ArgvSess({"attrs": "24.1"}, {"Attrs": "24.1"}))
    assert info["problems"] == [] and info["differs"] == []


def test_side_packages_differ_caps_check(monkeypatch):
    sess = _ArgvSess({"attrs": "24.1", "six": "1.16"}, {"attrs": "24.2"})
    rec = {}
    why = dr._check_contree_packages(sess, rec)
    assert why and "attrs: main 24.1, PR 24.2" in why and "six: main 1.16, PR not installed" in why
    assert rec["contree"]["packages"]["main"]["attrs"] == "24.1"
    v, _, _ = dr.verdict_for(None, why)
    assert v == "could_not_verify"


def test_side_packages_unreadable_is_a_problem():
    assert cs.side_packages(_ArgvSess({"a": "1"}, None))["problems"]


def test_client_sync_creates_one_client_under_threads(monkeypatch):
    import sys
    made = []

    class Slow:
        def __init__(self):
            time.sleep(0.05)
            made.append(self)
    monkeypatch.setitem(sys.modules, "contree_sdk", SimpleNamespace(ContreeSync=Slow))
    sess = cs.ContreeSession()
    ts = [threading.Thread(target=sess._client_sync) for _ in range(8)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    assert len(made) == 1


def test_started_map_is_lock_guarded():
    assert isinstance(cs._STATE_LOCK, type(threading.Lock()))


def test_parallel_main_failure_does_not_wait_for_pr_build():
    done = threading.Event()

    def run(shell, disposable, image_ref, timeout, files):
        if "deadbeefpr" in shell:
            time.sleep(0.6)
            done.set()
            return {"exit_code": 0, "stdout": "", "stderr": "", "uuid": "img-pr"}
        return {"exit_code": 1, "stdout": "", "stderr": "boom", "uuid": None}
    t0 = time.time()
    with pytest.raises(cs.ContreeError) as ei:
        cs.prepare_source_pair("o/r", "deadbeefmain", "deadbeefpr", runner=run, parallel=True)
    assert time.time() - t0 < 0.4
    assert ei.value.pr_build == cs.PR_BUILD_ABANDONED
    sess = cs.session()
    done.wait(2)
    time.sleep(0.05)
    assert sess.pr_uuid is None   # the late PR image is never used


def test_maybe_prepare_records_abandoned_pr_build(monkeypatch):
    def boom(*a, **k):
        e = cs.ContreeError("main checkpoint install failed")
        e.pr_build = cs.PR_BUILD_ABANDONED
        raise e
    monkeypatch.setattr(cs, "prepare_source_pair", boom)
    monkeypatch.setenv("POC_PARALLEL", "1")
    a = SimpleNamespace(pr="u", product_check=True, bench=None, sandbox_backend="contree")
    rec = {}
    assert dr._maybe_prepare_contree(a, "o/r", "m", "p", rec, 60)
    assert rec["contree"]["pr_build"] == cs.PR_BUILD_ABANDONED


def test_planning_error_not_hidden_by_prep_error(monkeypatch):
    monkeypatch.setattr(dr, "_maybe_prepare_contree", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("prep")))

    def plan(*a, **k):
        raise ValueError("planning")
    monkeypatch.setattr(dr, "plan_probes", plan)
    a = SimpleNamespace(build_timeout=60)
    with pytest.raises(ValueError, match="planning"):
        dr._prepare_while_planning(a, "o/r", {}, {}, {"main_sha": "m", "pr_sha": "p"}, None, None,
                                   __import__("pathlib").Path("."), None, "")


JUNIT = ('<?xml version="1.0"?><testsuites><testsuite name="s" tests="2">'
         '<testcase classname="t" name="test_a"/>{b}</testsuite></testsuites>')


def _junit_pytest(fail_pr=False, die_pr=False):
    def once(side, targets, tt, rt, workers, jx, lg, keep):
        if side == "pr" and die_pr:
            lg.write_text("ERROR collecting t.py\n")
            return 2, 0.1
        b = ('<testcase classname="t" name="test_b"><failure message="x"/></testcase>' if side == "pr" and fail_pr
             else '<testcase classname="t" name="test_b"/>')
        jx.write_text(JUNIT.format(b=b))
        lg.write_text(f"{side} done\n")
        return (1 if side == "pr" and fail_pr else 0), 0.1
    return once


def _pair(monkeypatch, tmp_path, parallel, **kw):
    """Run the whole Contree-only pair with every Contree/model step stubbed; return (record, result, verdict)."""
    (tmp_path / "side-main").mkdir(exist_ok=True)
    (tmp_path / "side-pr").mkdir(exist_ok=True)
    if parallel:
        monkeypatch.setenv("POC_PARALLEL", "1")
    else:
        monkeypatch.delenv("POC_PARALLEL", raising=False)
    stub = {"chosen_test_targets": lambda c: ["t.py"], "declared_test_deps": lambda *a: [],
            "optional_backend_reqs": lambda *a: [], "_groups_blocked": lambda *a: None,
            "_maybe_prepare_contree": lambda *a, **k: None, "own_index_refusal": lambda a, cnv, *x: cnv,
            "plan_probes": lambda *a, **k: {"probes": []}, "_contree_ready": lambda: True,
            "_contree_pytest_once": _junit_pytest(**kw),
            "contree_coverage_run": lambda *a, **k: {"status": "stub"},
            "run_probes": lambda *a, **k: {"items": []}, "contree_probe_coverage": lambda *a, **k: {"status": "stub"},
            "settle_probes": lambda rec: None, "change_is_docstring_only": lambda *a: False}
    for k, v in stub.items():
        monkeypatch.setattr(dr, k, v)
    monkeypatch.setattr(dr.freeze, "now", lambda: "T")
    (tmp_path / "side-main" / "t.py").write_text("")
    (tmp_path / "side-pr" / "t.py").write_text("")
    a = SimpleNamespace(pr="https://github.com/o/r/pull/1", product_check=True, bench=None, runs=3, workers="0",
                        test_timeout=60, run_timeout=600, build_timeout=60, sandbox_backend="contree")
    prdir = tmp_path / ("on" if parallel else "off")
    prdir.mkdir(exist_ok=True)
    rec = {"files": ["src/x.py"]}
    item = {"files": ["src/x.py"], "pr": 1, "chosen": None}
    out = dr._contree_only_pair(a, rec, "o/r", {"dist": "x"}, item, {"main_sha": "m", "pr_sha": "p"}, tmp_path,
                                prdir, False)
    cmp, cnv, ex, _ = out
    v = dr.verdict_for(cmp, cnv, ex)
    for r in rec.get("per_run", []):
        r.pop("seconds", None)
    return rec, out, v


@pytest.mark.parametrize("kw", [{}, {"fail_pr": True}, {"die_pr": True}])
def test_full_record_and_verdict_same_on_and_off(monkeypatch, tmp_path, kw):
    off = _pair(monkeypatch, tmp_path, False, **kw)
    on = _pair(monkeypatch, tmp_path, True, **kw)
    assert on[0] == off[0]
    assert on[1] == off[1]
    assert on[2] == off[2]


def test_only_pr_side_fails(monkeypatch, tmp_path):
    rec, (cmp, cnv, ex, _), v = _pair(monkeypatch, tmp_path, True, fail_pr=True)
    assert [r["exit"] for r in rec["per_run"]] == [0, 1] * 3
    assert cmp and "t::test_b" in " ".join(cmp["regressions"])
    assert v[0] == "needs_attention"
