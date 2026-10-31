"""Both live routes call settle_boundary_claims after settle_probes: dropping either call fails a test here."""
from pathlib import Path
from types import SimpleNamespace

from ops import daily_run as dr
from tests.test_parallel_mode import _pair


class _Reached(Exception):
    pass


def _spy(monkeypatch):
    calls = []

    def settle(rec, prdir):
        calls.append((rec.get("_settled_probes"), Path(prdir)))
    monkeypatch.setattr(dr, "settle_boundary_claims", settle)
    return calls


def test_contree_only_pair_settles_boundary_claims(monkeypatch, tmp_path):
    calls = _spy(monkeypatch)
    _pair(monkeypatch, tmp_path, False)
    assert len(calls) == 1 and calls[0][1] == tmp_path / "off"


def test_test_pr_local_route_settles_boundary_claims(monkeypatch, tmp_path):
    calls = _spy(monkeypatch)
    monkeypatch.setattr(dr, "settle_probes", lambda rec, prdir=None: rec.update(_settled_probes=True))

    def stop(*a, **k):   # first step after the probe settle: stop here, nothing more needs to run
        raise _Reached
    vm_ok = {"ok": True, "version": "1", "build": {}}

    def build_main(cfg, vm, *a, **k):
        Path(vm).mkdir(parents=True, exist_ok=True)
        return vm_ok
    stubs = {"new_record": lambda *a, **k: {"freeze": {}, "python": "3"}, "begin_pr": lambda a: None,
             "refuses_pr_state": lambda a, item: False, "mark_typing_only": lambda *a: False,
             "sandbox_refusal": lambda *a: None, "set_contree_only": lambda *a: None,
             "_groups_blocked": lambda *a: None, "_check_python": lambda *a: "3",
             "build_main_env": build_main, "venv_python_version": lambda *a: None,
             "freeze_env": lambda *a: {}, "plan_probes": lambda *a, **k: [],
             "apply_patch": lambda *a: (True, ""), "package_diff": lambda *a: "",
             "map_tests": lambda *a: ["t.py"], "targets_for_sides": lambda *a: {"pr": ["t.py"], "main": ["t.py"]},
             "execute_tests": lambda *a: (None, None, None), "run_probes": lambda *a, **k: {"items": []},
             "probe_coverage": lambda *a, **k: {}, "change_is_docstring_only": stop,
             "site_packages": lambda v: Path(v)}
    for k, v in stubs.items():
        monkeypatch.setattr(dr, k, v)
    from poc import demo_helper
    monkeypatch.setattr(demo_helper, "active", lambda a: False)
    a = SimpleNamespace(pr="https://github.com/o/r/pull/1", product_check=False, bench=None, no_report=True,
                        build_timeout=60, sandbox_backend=None)
    item = {"pr": 1, "diff": "", "title": "t", "head_sha": "a" * 40, "files": {"all": ["r/x.py"], "compiled": []}}
    try:
        dr.test_pr("o/r", {"pkg": "r", "dist": "r", "nightly": True}, item, tmp_path / "run", tmp_path / "w", a, {})
    except _Reached:
        pass
    assert calls == [(True, tmp_path / "run" / "r-1")]
