"""Contree-only console checks: when bubblewrap cannot start, nothing that runs PR code runs locally."""
import subprocess
from pathlib import Path
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
    assert daily_run.contree_only_wanted("contree") is False


def test_local_side_commands_are_refused_in_contree_only_mode(tmp_path, monkeypatch):
    ran = []
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: ran.append(a) or (_ for _ in ()).throw(AssertionError))
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: ran.append(a) or (_ for _ in ()).throw(AssertionError))
    daily_run.set_contree_only(True)
    venv = tmp_path / "venv-pr"
    log = tmp_path / "log.txt"
    rc, _ = daily_run.run(["uv", "pip", "install", "x"], log, env={"PATH": "/usr/bin"},
                          sbx=daily_run.side_sandbox(venv, network=True))
    assert rc == daily_run.LOCAL_REFUSED and "Contree-only" in log.read_text()
    cp = daily_run.in_side(venv, ["python", "-c", "print(1)"])
    assert cp.returncode == daily_run.LOCAL_REFUSED
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


def test_failed_checkpoint_falls_back_only_when_bubblewrap_works(monkeypatch):
    from poc import contree_sandboxes
    monkeypatch.setattr(contree_sandboxes, "prepare_source_pair", _failing_prepare)
    monkeypatch.setattr(contree_sandboxes, "select", lambda *a, **k: ("local", ""))
    monkeypatch.setattr(daily_run.sandbox, "enabled", lambda: True)
    monkeypatch.setattr(daily_run.sandbox, "check", lambda: (True, ""))
    a, rec = SimpleNamespace(sandbox_backend="contree"), {}
    assert daily_run._maybe_prepare_contree(a, "o/r", "a" * 40, "b" * 40, rec, 10) is None
    assert a.sandbox_backend == "local" and "using local bubblewrap" in rec["sandbox_backend_note"]


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
    assert rc == daily_run.LOCAL_REFUSED
