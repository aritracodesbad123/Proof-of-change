"""Contree-only console checks: when bubblewrap cannot start, nothing that runs PR code runs locally."""
import subprocess
from types import SimpleNamespace

import pytest

from ops import daily_run


@pytest.fixture(autouse=True)
def _reset():
    yield
    daily_run.set_contree_only(False)


def test_contree_only_needs_contree_and_a_broken_local_sandbox(monkeypatch):
    monkeypatch.setattr(daily_run.sandbox, "enabled", lambda: True)
    monkeypatch.setattr(daily_run.sandbox, "check", lambda: (False, "no namespaces"))
    assert daily_run.contree_only_wanted("contree") is True
    assert daily_run.contree_only_wanted("local") is False
    assert daily_run.contree_only_wanted(None) is False
    monkeypatch.setattr(daily_run.sandbox, "check", lambda: (True, ""))
    assert daily_run.contree_only_wanted("contree") is True   # Contree mode never runs PR code locally


def test_local_side_commands_are_refused_in_contree_only_mode(tmp_path, monkeypatch):
    ran = []
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: ran.append(a) or (_ for _ in ()).throw(AssertionError))
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: ran.append(a) or (_ for _ in ()).throw(AssertionError))
    daily_run.set_contree_only(True)
    venv = tmp_path / "venv-pr"
    log = tmp_path / "log.txt"
    rc, _ = daily_run.run(["uv", "pip", "install", "x"], log, env={"PATH": "/usr/bin"},
                          sbx=daily_run.side_sandbox(venv, network=True))
    assert daily_run.is_refused(rc) and "Contree mode" in log.read_text()
    cp = daily_run.in_side(venv, ["python", "-c", "print(1)"])
    assert daily_run.is_refused(cp)
    # The installs behind install_optional_backends / install_declared_test_deps go through run(): refused too.
    got = daily_run.install_optional_backends({"main": tmp_path / "venv-main", "pr": venv}, ["foo"], log, 10)
    assert got["installed"] == [] and got["skipped"]
    assert ran == []


def test_contree_only_routes_declared_and_optional_installs_into_the_checkpoints():
    shell = daily_run.contree_only_extra_shell(["hypothesis>=6"], ["numpy"], "apt-get install -y -qq libfoo")
    assert "python -m pip install -q 'hypothesis>=6'" in shell
    assert "python -m pip install -q numpy || echo" in shell
    assert shell.startswith("apt-get install")


def _failing_prepare(*a, **k):
    from poc import contree_sandboxes
    raise contree_sandboxes.ContreeError("quota exceeded")


def test_failed_checkpoint_refuses_when_bubblewrap_cannot_start(monkeypatch):
    from poc import contree_sandboxes
    monkeypatch.setattr(contree_sandboxes, "prepare_source_pair", _failing_prepare)
    monkeypatch.setattr(daily_run.sandbox, "enabled", lambda: True)
    monkeypatch.setattr(daily_run.sandbox, "check", lambda: (False, "no namespaces"))
    a, rec = SimpleNamespace(sandbox_backend="contree"), {}
    why = daily_run._maybe_prepare_contree(a, "o/r", "a" * 40, "b" * 40, rec, 10)
    assert why and "will not run pull-request code" in why and "quota exceeded" in why
    assert a.sandbox_backend == "contree" and rec["contree"]["fallback"] is None


def test_failed_checkpoint_refuses_even_when_bubblewrap_works(monkeypatch):
    from poc import contree_sandboxes
    monkeypatch.setattr(contree_sandboxes, "prepare_source_pair", _failing_prepare)
    monkeypatch.setattr(daily_run.sandbox, "enabled", lambda: True)
    monkeypatch.setattr(daily_run.sandbox, "check", lambda: (True, ""))
    a, rec = SimpleNamespace(sandbox_backend="contree"), {}
    why = daily_run._maybe_prepare_contree(a, "o/r", "a" * 40, "b" * 40, rec, 10)
    assert why and "will not run pull-request code" in why
    assert a.sandbox_backend == "contree" and rec["contree"]["fallback"] is None


def test_contree_never_falls_back_to_unsandboxed_local_code(monkeypatch):
    from poc import contree_sandboxes
    monkeypatch.setattr(daily_run.sandbox, "enabled", lambda: False)   # --unsafe-no-sandbox
    assert daily_run.contree_only_wanted("contree") is True
    monkeypatch.setattr(contree_sandboxes, "prepare_source_pair", _failing_prepare)
    a, rec = SimpleNamespace(sandbox_backend="contree"), {}
    assert "will not run pull-request code" in daily_run._maybe_prepare_contree(a, "o/r", "a" * 40, "b" * 40, rec, 10)


def test_coverage_is_not_run_locally_in_contree_only_mode(tmp_path):
    daily_run.set_contree_only(True)
    log = tmp_path / "cov.log"
    rc, _ = daily_run.run(["python", "-m", "coverage", "run", "-m", "pytest"], log, env={"PATH": "/usr/bin"},
                          sbx=daily_run.side_sandbox(tmp_path / "venv-pr"))
    assert daily_run.is_refused(rc)


def _sides(tmp_path):
    main = tmp_path / "side-main" / "widget"
    pr = tmp_path / "side-pr" / "widget"
    main.mkdir(parents=True)
    pr.mkdir(parents=True)
    (main / "core.py").write_text("def f():\n    return 1\n")
    (pr / "core.py").write_text("def f():\n    return 2\n")
    item = {"files": {"all": ["widget/core.py"]}}
    a = SimpleNamespace(no_coverage=False, baseline="full", test_timeout=30, workers="0", run_timeout=60)
    return main.parent, pr.parent, item, a


def _gate(cov):
    from poc import coverage_gate
    rec = {"verdict": "verified", "reason": "1 new test(s) pass, 0 unchanged", "product_check": True,
           "files": {"all": ["widget/core.py"]}, "coverage": cov}
    return coverage_gate.apply(rec)


def test_contree_only_measured_coverage_can_reach_verified(tmp_path, monkeypatch):
    main_root, pr_root, item, a = _sides(tmp_path)
    body = {"files": {"/work/src/widget/core.py": {"executed_lines": [1, 2], "missing_lines": []}}}
    seen = {}

    class Sess:
        pr_uuid = "pr-1"

        def run_op(self, side, shell, **k):
            seen["side"] = side
            seen["shell"] = shell
            text = __import__("json").dumps(body)
            return {"exit_code": 0, "stdout": f"___POC_EXIT___0\n___POC_COV_START___\n{text}\n___POC_COV_END___\n",
                    "stderr": ""}

    monkeypatch.setattr("poc.contree_sandboxes.session", lambda: Sess())
    got = daily_run.contree_coverage_run(item, main_root, pr_root, ["tests/test_widget.py"], tmp_path, a)
    assert got["status"] == "measured" and got["where"] == "contree"
    assert got["changed_lines_covered"] >= 1
    assert seen["side"] == "pr" and "--cov=/work/src/widget" in seen["shell"] and "pytest" in seen["shell"]
    assert "NEBIUS" not in seen["shell"] and "API_KEY" not in seen["shell"]
    assert _gate(got)["verdict"] == "verified"
    assert (tmp_path / "coverage-pr.json").is_file()


def test_contree_only_missing_coverage_file_still_caps(tmp_path, monkeypatch):
    main_root, pr_root, item, a = _sides(tmp_path)

    class Sess:
        pr_uuid = "pr-1"

        def run_op(self, side, shell, **k):
            return {"exit_code": 1, "stdout": "___POC_EXIT___1\n___POC_LOG___\nno report\n", "stderr": ""}

    monkeypatch.setattr("poc.contree_sandboxes.session", lambda: Sess())
    got = daily_run.contree_coverage_run(item, main_root, pr_root, ["tests/test_widget.py"], tmp_path, a)
    assert got["status"] == "not measured" and "no data" in got["why"]
    assert not (tmp_path / "coverage-pr.json").exists()
    gated = _gate(got)
    assert gated["verdict"] == "could_not_verify"
    assert gated["reason"].startswith("Coverage wasn't measured")


# --- Contree mode never installs or runs PR code locally (PR #87 follow-up) ---

def test_contree_mode_is_always_contree_only_even_when_bubblewrap_works(monkeypatch):
    monkeypatch.setattr(daily_run.sandbox, "enabled", lambda: True)
    monkeypatch.setattr(daily_run.sandbox, "check", lambda: (True, ""))
    assert daily_run.contree_only_wanted("contree") is True


def test_machine_is_contree_only_when_the_checkpoints_were_built(monkeypatch):
    from poc import contree_sandboxes

    class _Sess:
        def describe(self):
            return {"main_uuid": "m-1", "pr_uuid": "p-1"}

    monkeypatch.setattr(contree_sandboxes, "prepare_source_pair", lambda *a, **k: _Sess())
    rec = {"machine": "contree (not run)"}
    assert daily_run._maybe_prepare_contree(SimpleNamespace(sandbox_backend="contree"), "o/r", "a" * 40, "b" * 40,
                                            rec, 10) is None
    assert rec["machine"] == "contree" and rec["contree"]["pr_uuid"] == "p-1"


def test_machine_is_not_contree_when_contree_never_ran(monkeypatch):
    from poc import contree_sandboxes
    monkeypatch.setattr(contree_sandboxes, "prepare_source_pair", _failing_prepare)
    rec = {"machine": "contree (not run)"}
    why = daily_run._maybe_prepare_contree(SimpleNamespace(sandbox_backend="contree"), "o/r", "a" * 40, "b" * 40,
                                           rec, 10)
    assert why and rec["machine"] != "contree" and rec["contree"]["fallback"] is None
