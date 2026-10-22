import subprocess

import pytest

from poc import tool_setup


def _cp(rc=0, err=""):
    return subprocess.CompletedProcess([], rc, "", err)


def test_missing_tool_is_installed_from_declared_list_and_continues(monkeypatch):
    state = {"installed": False}
    monkeypatch.setattr(tool_setup, "_satisfied", lambda r: state["installed"])
    calls = []

    def installer(reqs):
        calls.append(list(reqs)); state["installed"] = True; return _cp()

    out = tool_setup.ensure_tools(["uv==9.9.9", "other==1"], installer=installer, sleep=lambda s: None, log=lambda m: None)
    assert calls == [["uv==9.9.9", "other==1"]]  # one pip call, everything missing together
    assert out["installed"] == ["uv==9.9.9", "other==1"]
    assert "Installed missing tools" in out["note"]


def test_retries_then_plain_error(monkeypatch):
    monkeypatch.setattr(tool_setup, "_satisfied", lambda r: False)
    calls = []
    with pytest.raises(tool_setup.ToolSetupError) as e:
        tool_setup.ensure_tools(["uv==9.9.9"], installer=lambda r: calls.append(r) or _cp(1, "no network"),
                                sleep=lambda s: None, log=lambda m: None)
    assert len(calls) == 3
    msg = str(e.value)
    assert "could not install it after 3 tries" in msg and "Traceback" not in msg


def test_declared_requirements_come_from_pyproject():
    reqs = tool_setup.declared_requirements()
    assert any(tool_setup._name(r) == "uv" for r in reqs)


def test_resolve_python_without_uv_does_not_crash(monkeypatch):
    from ops import daily_run as dr

    def boom():
        raise tool_setup.ToolSetupError("no uv")
    monkeypatch.setattr(dr, "uv_bin", boom)
    assert dr.resolve_python("3.12") == "3.12"
