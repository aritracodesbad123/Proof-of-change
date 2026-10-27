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
        return {"exit_code": 0, "stdout": "[]" if "pip list" in shell else "", "stderr": "", "uuid": uid}
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
    assert time.time() - t0 < 0.39 + 0.45   # builds overlap (0.2 s), then two 0.2 s version reads
    assert live["max"] == 2
    assert sess.main_uuid == "img-main" and sess.pr_uuid == "img-pr" and sess.parallel_fallback is None
    builds = [(disp, img) for _, disp, img in log if not disp]
    assert builds == [(False, None), (False, None)]   # separate sandboxes from the base image


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


def test_package_drift_none_when_same():
    assert cs.package_drift(_ArgvSess({"attrs": "24.1"}, {"Attrs": "24.1"})) is None


def test_package_drift_reasons():
    why = cs.package_drift(_ArgvSess({"attrs": "24.1", "six": "1.16"}, {"attrs": "24.2"}))
    assert "attrs: main 24.1, PR 24.2" in why and "six: main 1.16, PR not installed" in why
    assert "could not be read" in cs.package_drift(_ArgvSess({"a": "1"}, None))


def test_no_could_not_verify_on_drift_code_left():
    assert not hasattr(dr, "_check_contree_packages") and not hasattr(cs, "side_packages")


@pytest.mark.parametrize("files,hit", [(["requirements-dev.txt"], True), (["pyproject.toml"], True),
                                       ({"all": ["sub/setup.cfg"]}, True), (["constraints.txt"], True),
                                       (["src/x.py", "docs/requirements.md"], False)])
def test_touches_dependency_files(files, hit):
    assert cs.touches_dependency_files(files) is hit


def test_client_sync_creates_one_client_under_threads(monkeypatch):
    import sys
    made, inside, peak = [], {"n": 0}, {"n": 0}
    gate = threading.Barrier(2)

    class Slow:
        def __init__(self):
            inside["n"] += 1
            peak["n"] = max(peak["n"], inside["n"])
            time.sleep(0.1)
            made.append(self)
            inside["n"] -= 1
    monkeypatch.setitem(sys.modules, "contree_sdk", SimpleNamespace(ContreeSync=Slow))
    sess = cs.ContreeSession()
    got = []

    def go():
        gate.wait()   # both threads call _client_sync at the same moment
        got.append(sess._client_sync())
    ts = [threading.Thread(target=go) for _ in range(2)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    assert len(got) == 2 and got[0] is got[1] and len(made) == 1 and peak["n"] == 1


def test_started_map_two_threads_never_lose_entries():
    keys = list(range(2000))

    def put(off):
        for k in keys[off::2]:
            with cs._STATE_LOCK:
                cs._STARTED[-1 - k] = False
    ts = [threading.Thread(target=put, args=(o,)) for o in (0, 1)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    with cs._STATE_LOCK:
        n = sum(1 for k in keys if cs._STARTED.pop(-1 - k, None) is False)
    assert n == len(keys)


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
    seen = []
    from poc import run_progress
    monkeypatch.setattr(run_progress, "emit", lambda *a, **k: seen.append(" ".join(map(str, a))))
    a = SimpleNamespace(build_timeout=60)
    with pytest.raises(ValueError, match="planning"):
        dr._prepare_while_planning(a, "o/r", {}, {}, {"main_sha": "m", "pr_sha": "p"}, None, None,
                                   __import__("pathlib").Path("."), None, "")
    assert any("probe planning failed (ValueError); waiting" in m for m in seen)


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


def _contree_runner(drift=False, outside=False):
    """Fake Contree API under a real session: installs, python --version, pip list and the own-checkout import."""
    import json

    def run(shell, disposable, image_ref, timeout, files):
        r = {"exit_code": 0, "stdout": "", "stderr": "", "uuid": None}
        if "python --version" in shell:
            r["stdout"] = "Python 3.12.1\n"
        elif "pip list" in shell:
            pr_base = image_ref == "img-pr-base"
            r["stdout"] = json.dumps([{"name": "attrs", "version": "24.2" if drift and pr_base else "24.1"}])
        elif "importlib" in shell:
            f = "/usr/lib/python3/site-packages/x/__init__.py" if outside else "/work/src/x/__init__.py"
            r["stdout"] = json.dumps({"root": "/work/src", "file": f, "namespace": False, "paths": []})
        elif not disposable:   # checkpoint builds
            if "origin m\n" in shell:
                r["uuid"] = "img-main"
            elif image_ref == "img-main":
                r["uuid"] = "img-pr"            # forked on main, as flag-off does
            else:
                r["uuid"] = "img-pr-base"       # parallel build from the base image
        return r
    return run


def _pair(monkeypatch, tmp_path, parallel, real_prep=False, blocked="", files=("src/x.py",), drift=False,
          outside=False, **kw):
    """Run the whole Contree-only pair with model/test steps stubbed; return (record, result, verdict).
    real_prep keeps _maybe_prepare_contree and prepare_source_pair real over a fake Contree API."""
    import shutil
    for d in ("side-main", "side-pr", "venv-main", "venv-pr"):
        shutil.rmtree(tmp_path / d, ignore_errors=True)
    (tmp_path / "side-main").mkdir()
    (tmp_path / "side-pr").mkdir()
    if parallel:
        monkeypatch.setenv("POC_PARALLEL", "1")
    else:
        monkeypatch.delenv("POC_PARALLEL", raising=False)
    stub = {"chosen_test_targets": lambda c: ["t.py"], "declared_test_deps": lambda *a: [],
            "optional_backend_reqs": lambda *a: [], "own_index_refusal": lambda a, cnv, *x: cnv,
            "plan_probes": lambda *a, **k: {"probes": []}, "_contree_ready": lambda: True,
            "_contree_pytest_once": _junit_pytest(**kw),
            "contree_coverage_run": lambda *a, **k: {"status": "stub"},
            "run_probes": lambda *a, **k: {"items": []}, "contree_probe_coverage": lambda *a, **k: {"status": "stub"},
            "settle_probes": lambda rec: None, "change_is_docstring_only": lambda *a: False,
            "_product_plan": lambda *a, **k: ({"groups_blocked": blocked} if blocked else {})}
    if real_prep:
        run = _contree_runner(drift=drift, outside=outside)
        real_new = cs.new_session
        monkeypatch.setattr(cs, "new_session", lambda **k: real_new(runner=run, **{x: v for x, v in k.items()
                                                                                    if x != "runner"}))
    else:
        stub["_maybe_prepare_contree"] = lambda *a, **k: None
    for k, v in stub.items():
        monkeypatch.setattr(dr, k, v)
    monkeypatch.setattr(dr.freeze, "now", lambda: "T")
    (tmp_path / "side-main" / "t.py").write_text("")
    (tmp_path / "side-pr" / "t.py").write_text("")
    a = SimpleNamespace(pr="https://github.com/o/r/pull/1", product_check=True, bench=None, runs=3, workers="0",
                        test_timeout=60, run_timeout=600, build_timeout=60, sandbox_backend="contree")
    prdir = tmp_path / ("on" if parallel else "off")
    prdir.mkdir(exist_ok=True)
    rec = {"files": {"all": list(files)}}
    item = {"files": {"all": list(files)}, "pr": 1, "chosen": None}
    out = dr._contree_only_pair(a, rec, "o/r", {"dist": "x", "pkg": "x"}, item, {"main_sha": "m", "pr_sha": "p"},
                                tmp_path, prdir, True)
    cs.clear_session()
    cmp, cnv, ex, _ = out
    v = dr.verdict_for(cmp, cnv, ex)
    for r in rec.get("per_run", []):
        r.pop("seconds", None)
    return rec, out, v


def _same(off, on):
    fb = (on[0].get("contree") or {}).pop("parallel_fallback", None)
    assert on[0] == off[0]
    assert on[1] == off[1]
    assert on[2] == off[2]
    return fb


def test_on_off_same_when_pr_changes_dependencies(monkeypatch, tmp_path):
    files = ("src/x.py", "requirements.txt")
    off = _pair(monkeypatch, tmp_path, False, real_prep=True, files=files)
    on = _pair(monkeypatch, tmp_path, True, real_prep=True, files=files)
    assert _same(off, on) == "the pull request changes a dependency file"
    assert on[0]["contree"]["pr_uuid"] == "img-pr"   # built on main's image


def test_on_off_same_with_version_drift(monkeypatch, tmp_path):
    off = _pair(monkeypatch, tmp_path, False, real_prep=True, drift=True)
    on = _pair(monkeypatch, tmp_path, True, real_prep=True, drift=True)
    fb = _same(off, on)
    assert fb.startswith("main and PR installed different package versions: attrs: main 24.1, PR 24.2")
    assert on[2][0] == off[2][0] != "could_not_verify"


def test_parallel_without_drift_keeps_base_build(monkeypatch, tmp_path):
    on = _pair(monkeypatch, tmp_path, True, real_prep=True)
    assert on[0]["contree"]["pr_uuid"] == "img-pr-base" and "parallel_fallback" not in on[0]["contree"]
    assert on[0]["contree"]["own_checkout"]["status"] == "ok" and on[0]["contree"]["python"]["problems"] == []


@pytest.mark.parametrize("drift", [False, True])
def test_own_checkout_check_fires_on_and_off(monkeypatch, tmp_path, drift):
    off = _pair(monkeypatch, tmp_path, False, real_prep=True, outside=True, drift=drift)
    on = _pair(monkeypatch, tmp_path, True, real_prep=True, outside=True, drift=drift)
    for r in (off, on):
        assert r[0]["contree"]["own_checkout"]["status"] == "outside the checkout"
        assert "separately installed copy" in r[1][1] and r[2][0] == "could_not_verify"
    assert on[0]["contree"]["own_checkout"] == off[0]["contree"]["own_checkout"]
    assert on[2] == off[2]


def test_on_off_same_when_blocked(monkeypatch, tmp_path):
    off = _pair(monkeypatch, tmp_path, False, real_prep=True, blocked="dependency groups refused")
    on = _pair(monkeypatch, tmp_path, True, real_prep=True, blocked="dependency groups refused")
    assert on[0].get("pr_side_started_at") == off[0].get("pr_side_started_at") == "T"
    assert _same(off, on) is None
    assert on[1][1] == "dependency groups refused"


def test_plan_probes_never_writes_contree_record():
    import ast
    import inspect
    src = inspect.getsource(dr.plan_probes)
    names = {n.value for n in ast.walk(ast.parse(src)) if isinstance(n, ast.Constant) and n.value == "contree"}
    assert not names, "plan_probes must not touch rec['contree'] (it runs while the checkpoints are built)"


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
