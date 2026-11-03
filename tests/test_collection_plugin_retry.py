"""A third-party pytest plugin that breaks collection the same way on both sides is turned off once.

The fixture is a pair of pytest logs. The plugin name in the logs is not special: the entry-point name comes
from the traceback and the installed pytest11 metadata. Verdict rules are not an input to this retry.
"""
from __future__ import annotations

import inspect
import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

from ops import daily_run as dr

FX = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "collection_plugin"
MAIN = (FX / "main.log").read_text()
PR = (FX / "pr.log").read_text()
EPS = [("px", "plugx.plugin", "pytest-plugx"), ("other", "other.mod", "pytest-other")]
JUNIT = ('<?xml version="1.0" encoding="utf-8"?>'
         '<testsuite tests="1"><testcase classname="tests.test_pool" name="test_ok"/></testsuite>')


def test_fixture_names_the_entry_point_not_the_distribution():
    assert dr.collection_plugins_to_disable(MAIN, PR, EPS) == ["px"]
    note = dr.collection_plugin_note(["px"], dr._collection_error(MAIN))
    assert note.startswith("Setup: pytest plugin px was turned off.")
    assert "missing_stack" in note and "side-main" not in note and "side-pr" not in note
    assert "does not change how the verdict is chosen" in note


def test_a_long_traceback_and_a_distribution_name_still_resolve():
    log = MAIN.replace(
        "/usr/local/side-main/lib/python3.12/site-packages/plugx/plugin.py:9: in pytest_configure",
        '  File "/usr/local/side-main/lib/python3.12/site-packages/plugx/plugin.py", line 9, in pytest_configure')
    assert dr.collection_failed_same_way(log, PR)
    assert dr.plugin_entry_points(dr._collection_frames(log), [("px", "somewhere.else", "plugx")]) == ["px"]


def test_two_entry_points_in_one_package_use_the_file_in_the_traceback():
    hook = MAIN.replace("plugx/plugin.py", "widget_extra/hook.py")
    other = PR.replace("plugx/plugin.py", "widget_extra/hook.py")
    eps = [("widget", "widget_extra.fixture", "widget-extra"),
           ("widget_hook", "widget_extra.hook", "widget-extra")]
    assert dr.collection_plugins_to_disable(hook, other, eps) == ["widget_hook"]


def test_a_different_error_a_project_frame_or_a_ran_test_is_left_alone():
    different = PR.replace("missing_stack", "other_stack")
    assert dr.collection_plugins_to_disable(MAIN, different, EPS) == []
    project = MAIN.replace("site-packages/plugx/plugin.py", "src/pkg/conftest.py")
    assert dr.collection_plugins_to_disable(project, project, EPS) == []
    own = MAIN.replace("plugx/plugin.py", "_pytest/config.py")
    assert dr.collection_plugins_to_disable(own, own, EPS) == []
    assert dr.collection_plugins_to_disable(MAIN, "1 passed\n", EPS) == []
    ran = {"main": [{"t::a": ("passed", "")}], "pr": [{}]}
    assert dr.collection_plugins_to_disable(MAIN, PR, EPS, ran) == []


def test_the_note_does_not_change_the_verdict():
    assert "plugin" not in inspect.signature(dr.verdict_for).parameters
    cmp = dr.compare_sides({"main": [{"t::a": ("passed", "")}], "pr": [{"t::a": ("passed", "")}]})
    exits = {"explained": True, "problems": [], "detail": "all runs exited 0"}
    base = {"files": {"all": []}, "baseline": "tests"}
    noted = dict(base, collection_plugin_note="Setup: pytest plugin px was turned off.")
    dr._store_verdict(base, cmp, None, exits)
    dr._store_verdict(noted, cmp, None, exits)
    assert base["verdict"] == noted["verdict"] == "verified"
    assert base["reason"] == noted["reason"]


def test_retry_once_on_both_sides_and_the_report_says_why(tmp_path, monkeypatch):
    seen = []

    def fake_run(cmd, log, **kw):
        cmd = [str(c) for c in cmd]
        junit = next(c.split("=", 1)[1] for c in cmd if c.startswith("--junitxml="))
        seen.append(cmd)
        if "no:px" in cmd:
            Path(log).write_text("1 passed\n")
            Path(junit).write_text(JUNIT)
            return 0, 0.1
        Path(log).write_text(MAIN if "-main-" in Path(log).name else PR)
        return 2, 0.1

    monkeypatch.setattr(dr, "run", fake_run)
    monkeypatch.setattr(dr, "_contree_ready", lambda: False)
    monkeypatch.setattr(dr, "base_env", lambda *a, **k: {})
    monkeypatch.setattr(dr, "side_home", lambda v: tmp_path)
    monkeypatch.setattr(dr, "side_out", lambda v: tmp_path / "out")
    (tmp_path / "out").mkdir()
    monkeypatch.setattr(dr, "side_sandbox", lambda *a, **k: None)
    monkeypatch.setattr(dr, "installed_pytest_entry_points", lambda venvs: (list(EPS), ""))
    rec = {}
    a = SimpleNamespace(runs=1, workers="0", test_timeout=30, run_timeout=60, pr=None, product_check=False, bench=None)
    rdir = tmp_path / "run"
    rdir.mkdir()
    cmp, cnv, _ex = dr.execute_tests(
        rec, {"main": tmp_path / "vm", "pr": tmp_path / "vp"},
        {"main": ["t.py"], "pr": ["t.py"]}, rdir, tmp_path, a, cwds={"main": tmp_path, "pr": tmp_path})
    assert cnv is None and cmp["same"] == 1
    assert "verdict" not in rec
    assert rec["pytest_plugins_off"] == ["px"]
    attempt = rec["plugin_retry"]
    assert attempt["detection_fired"] is True and attempt["plugin_list_read"] is True
    assert attempt["plugins"] == ["px"] and attempt["flags"] == "-p no:px" and attempt["outcome"] == "worked"
    assert "Detection fired" in rec["collection_plugin_note"] and "Outcome: worked" in rec["collection_plugin_note"]
    assert "1 passed" in (rdir / "pytest-main-retry.log").read_text()
    assert "1 passed" in (rdir / "pytest-pr-retry.log").read_text()
    assert sum("no:px" in c for c in seen) == 2
    assert sum("no:px" not in c for c in seen) == 2
    meta = {"date": "2026-11-03", "started_ist": "s", "finished_ist": "f", "wall_min": 1, "runs": 1,
            "machine": "m", "api_calls": 0, "auth": "none"}
    (tmp_path / "report").mkdir()
    (tmp_path / "out-report").mkdir()
    record = {"schema_version": "1", "record_kind": "pr_run", "id": "pr-acme-widget-1",
              "repo": "acme/widget", "pr": {"repo": "acme/widget", "number": 1, "url": "https://example.test/1",
                                            "title": "t", "head_sha": "a" * 40},
              "author": "a", "route": "source-pair", "verdict": "verified", "reason": "same",
              "files": {"all": [], "package_py": [], "compiled": []},
              "updated_at_ist": "x", "ci_state": "none", "ci_detail": "-",
              "runs_per_side": 1, "runs_per_side_planned": 1, "per_run": [],
              "duration_s": {"total_wall": 1}, "network": "allowed", "posted_upstream": False,
              "logs": "widget-1/", "tested_at_ist": "2026-11-03 00:00 IST",
              "collection_plugin_note": rec["collection_plugin_note"]}
    md = dr.write_report(tmp_path / "report", meta, [record], {}, []).read_text()
    assert rec["collection_plugin_note"] in md
    from reports.pr_report import build
    report, _decision = build(record, rdir, tmp_path / "out-report")
    text = "\n".join(block[1] for block in report.blocks if block[0] == "p")
    assert rec["collection_plugin_note"] in text


def test_a_failed_retry_keeps_the_original_logs(tmp_path, monkeypatch):
    def fake_run(cmd, log, **kw):
        cmd = [str(c) for c in cmd]
        if "no:px" in cmd:
            Path(log).write_text("still broken\nERROR collecting test/test_pool.py\n")
            return 2, 0.1
        Path(log).write_text(MAIN if "-main-" in Path(log).name else PR)
        return 2, 0.1

    monkeypatch.setattr(dr, "run", fake_run)
    monkeypatch.setattr(dr, "_contree_ready", lambda: False)
    monkeypatch.setattr(dr, "base_env", lambda *a, **k: {})
    monkeypatch.setattr(dr, "side_home", lambda v: tmp_path)
    monkeypatch.setattr(dr, "side_out", lambda v: tmp_path / "out")
    (tmp_path / "out").mkdir()
    monkeypatch.setattr(dr, "side_sandbox", lambda *a, **k: None)
    monkeypatch.setattr(dr, "installed_pytest_entry_points", lambda venvs: (list(EPS), ""))
    rec = {}
    a = SimpleNamespace(runs=1, workers="0", test_timeout=30, run_timeout=60, pr=None, product_check=False, bench=None)
    rdir = tmp_path / "run"
    rdir.mkdir()
    _cmp, cnv, _ex = dr.execute_tests(
        rec, {"main": tmp_path / "vm", "pr": tmp_path / "vp"},
        {"main": ["t.py"], "pr": ["t.py"]}, rdir, tmp_path, a, cwds={"main": tmp_path, "pr": tmp_path})
    assert cnv and "collection failed" in cnv
    assert "verdict" not in rec and "pytest_plugins_off" not in rec
    attempt = rec["plugin_retry"]
    assert attempt["detection_fired"] is True and attempt["outcome"] == "failed again"
    assert attempt["plugins"] == ["px"] and attempt["flags"] == "-p no:px" and attempt["plugin_list_read"] is True
    assert "ERROR collecting" in attempt["main_error"] and "ERROR collecting" in attempt["pr_error"]
    assert "failed again" in rec["collection_plugin_note"] and "The first result was kept" in rec["collection_plugin_note"]
    assert "missing_stack" in (rdir / "pytest-main-1.log").read_text()
    assert "still broken" not in (rdir / "pytest-main-1.log").read_text()
    assert "still broken" not in (rdir / "pytest-pr-1.log").read_text()
    assert "still broken" in (rdir / "pytest-main-retry.log").read_text()
    assert "still broken" in (rdir / "pytest-pr-retry.log").read_text()


START = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "startup_plugin"
START_MAIN = (START / "main.log").read_text()
START_PR = (START / "pr.log").read_text()
ASYNCIO = [("asyncio", "pytest_asyncio.plugin", "pytest-asyncio"), ("other", "other.mod", "pytest-other")]


def test_startup_internal_error_resolves_to_the_entry_point():
    assert dr.startup_failed_same_way(START_MAIN, START_PR)
    assert dr.collection_plugins_to_disable(START_MAIN, START_PR, ASYNCIO) == []
    frames = dr._startup_configure_frames(START_MAIN)
    assert dr.plugin_entry_points(frames, ASYNCIO) == ["asyncio"]
    assert "side-main" not in dr._collection_error(START_MAIN)
    assert dr._collection_error(START_MAIN) == dr._collection_error(START_PR)
    assert "PytestDeprecationWarning" in dr._collection_error(START_MAIN)
    note = dr.collection_plugin_note(["asyncio"], dr._collection_error(START_MAIN), startup=True)
    assert note.startswith("Setup: pytest plugin asyncio was turned off.")
    assert "stopped at startup" in note


def test_a_plugin_the_pytest_config_names_is_not_turned_off(tmp_path):
    named = tmp_path / "named"
    named.mkdir()
    (named / "pyproject.toml").write_text((START / "names-the-plugin.toml").read_text())
    assert dr.plugin_named_in_pytest_config([named], "asyncio")
    bare = tmp_path / "bare"
    bare.mkdir()
    (bare / "pyproject.toml").write_text('[project.optional-dependencies]\ndev = ["pytest-asyncio"]\n')
    assert not dr.plugin_named_in_pytest_config([bare], "asyncio", "pytest-asyncio")
    only_p = tmp_path / "flag"
    only_p.mkdir()
    (only_p / "pytest.ini").write_text("[pytest]\naddopts = -p asyncio\n")
    assert dr.plugin_named_in_pytest_config([only_p], "asyncio")
    assert not dr.plugin_named_in_pytest_config([only_p], "other")
    required = tmp_path / "required"
    required.mkdir()
    (required / "pyproject.toml").write_text((START / "required-dist.toml").read_text())
    assert dr.plugin_named_in_pytest_config([required], "asyncio", "pytest-asyncio")
    assert dr.plugin_named_in_pytest_config([required], "asyncio", "pytest_asyncio")
    assert dr.plugin_named_in_pytest_config([required], "asyncio", "Pytest.Asyncio")
    assert not dr.plugin_named_in_pytest_config([required], "asyncio")
    flagged = tmp_path / "addopts"
    flagged.mkdir()
    (flagged / "pyproject.toml").write_text((START / "addopts-dist.toml").read_text())
    assert dr.plugin_named_in_pytest_config([flagged], "asyncio", "pytest-asyncio")


def test_startup_retry_once_unless_the_config_names_the_plugin(tmp_path, monkeypatch):
    seen = []

    def fake_run(cmd, log, **kw):
        cmd = [str(c) for c in cmd]
        junit = next(c.split("=", 1)[1] for c in cmd if c.startswith("--junitxml="))
        seen.append(cmd)
        if "no:asyncio" in cmd:
            Path(log).write_text("1 passed\n")
            Path(junit).write_text(JUNIT)
            return 0, 0.1
        Path(log).write_text(START_MAIN if "-main-" in Path(log).name else START_PR)
        return 3, 0.1

    monkeypatch.setattr(dr, "run", fake_run)
    monkeypatch.setattr(dr, "_contree_ready", lambda: False)
    monkeypatch.setattr(dr, "base_env", lambda *a, **k: {})
    monkeypatch.setattr(dr, "side_home", lambda v: tmp_path)
    monkeypatch.setattr(dr, "side_out", lambda v: tmp_path / "out")
    (tmp_path / "out").mkdir()
    monkeypatch.setattr(dr, "side_sandbox", lambda *a, **k: None)
    monkeypatch.setattr(dr, "installed_pytest_entry_points", lambda venvs: (list(ASYNCIO), ""))
    rec = {}
    a = SimpleNamespace(runs=1, workers="0", test_timeout=30, run_timeout=60, pr=None, product_check=False, bench=None)
    rdir = tmp_path / "run"
    rdir.mkdir()
    checkout = tmp_path / "src"
    checkout.mkdir()
    (checkout / "pyproject.toml").write_text("[tool.pytest]\naddopts = ['-p', 'pytester']\n")
    cmp, cnv, _ex = dr.execute_tests(
        rec, {"main": tmp_path / "vm", "pr": tmp_path / "vp"},
        {"main": ["t.py"], "pr": ["t.py"]}, rdir, tmp_path, a, cwds={"main": checkout, "pr": checkout})
    assert cnv is None and cmp["same"] == 1
    assert "verdict" not in rec
    assert rec["pytest_plugins_off"] == ["asyncio"]
    assert "stopped at startup" in rec["collection_plugin_note"]
    assert sum("no:asyncio" in c for c in seen) == 2

    seen.clear()
    named = tmp_path / "named"
    named.mkdir()
    (named / "pyproject.toml").write_text((START / "names-the-plugin.toml").read_text())
    rec2 = {}
    rdir2 = tmp_path / "run2"
    rdir2.mkdir()
    _cmp, cnv2, _ex = dr.execute_tests(
        rec2, {"main": tmp_path / "vm", "pr": tmp_path / "vp"},
        {"main": ["t.py"], "pr": ["t.py"]}, rdir2, tmp_path, a, cwds={"main": named, "pr": named})
    assert cnv2 and "collection failed" in cnv2
    assert "pytest_plugins_off" not in rec2
    assert all("no:asyncio" not in c for c in seen)
    assert "PytestDeprecationWarning" in (rdir2 / "pytest-main-1.log").read_text()

    seen.clear()
    dist_named = tmp_path / "dist"
    dist_named.mkdir()
    (dist_named / "pyproject.toml").write_text((START / "required-dist.toml").read_text())
    rec3 = {}
    rdir3 = tmp_path / "run3"
    rdir3.mkdir()
    _cmp, cnv3, _ex = dr.execute_tests(
        rec3, {"main": tmp_path / "vm", "pr": tmp_path / "vp"},
        {"main": ["t.py"], "pr": ["t.py"]}, rdir3, tmp_path, a, cwds={"main": dist_named, "pr": dist_named})
    assert cnv3 and "collection failed" in cnv3
    assert "pytest_plugins_off" not in rec3
    assert all("no:asyncio" not in c for c in seen)

    seen.clear()
    flag_named = tmp_path / "pflag"
    flag_named.mkdir()
    (flag_named / "pyproject.toml").write_text((START / "addopts-dist.toml").read_text())
    rec4 = {}
    rdir4 = tmp_path / "run4"
    rdir4.mkdir()
    _cmp, cnv4, _ex = dr.execute_tests(
        rec4, {"main": tmp_path / "vm", "pr": tmp_path / "vp"},
        {"main": ["t.py"], "pr": ["t.py"]}, rdir4, tmp_path, a, cwds={"main": flag_named, "pr": flag_named})
    assert cnv4 and "collection failed" in cnv4
    assert "pytest_plugins_off" not in rec4
    assert all("no:asyncio" not in c for c in seen)


def test_an_unreadable_plugin_list_is_recorded(tmp_path, monkeypatch):
    calls = []

    def fake_run(cmd, log, **kw):
        calls.append([str(c) for c in cmd])
        Path(log).write_text(MAIN if "-main-" in Path(log).name else PR)
        return 2, 0.1

    monkeypatch.setattr(dr, "run", fake_run)
    monkeypatch.setattr(dr, "_contree_ready", lambda: False)
    monkeypatch.setattr(dr, "base_env", lambda *a, **k: {})
    monkeypatch.setattr(dr, "side_home", lambda v: tmp_path)
    monkeypatch.setattr(dr, "side_out", lambda v: tmp_path / "out")
    (tmp_path / "out").mkdir()
    monkeypatch.setattr(dr, "side_sandbox", lambda *a, **k: None)
    why = "the main side had no Python interpreter"
    monkeypatch.setattr(dr, "installed_pytest_entry_points", lambda venvs: ([], why))
    rec = {}
    a = SimpleNamespace(runs=1, workers="0", test_timeout=30, run_timeout=60, pr=None, product_check=False, bench=None)
    rdir = tmp_path / "run"
    rdir.mkdir()
    _cmp, cnv, _ex = dr.execute_tests(
        rec, {"main": tmp_path / "vm", "pr": tmp_path / "vp"},
        {"main": ["t.py"], "pr": ["t.py"]}, rdir, tmp_path, a, cwds={"main": tmp_path, "pr": tmp_path})
    assert cnv and "collection failed" in cnv
    assert "verdict" not in rec and "pytest_plugins_off" not in rec
    attempt = rec["plugin_retry"]
    assert attempt["detection_fired"] is True and attempt["plugin_list_read"] is False
    assert attempt["plugins"] == [] and attempt["flags"] == "" and attempt["outcome"] == "not run"
    assert attempt["plugin_list_why"] == why
    assert why in rec["collection_plugin_note"] and "could not be read" in rec["collection_plugin_note"]
    assert len(calls) == 2
    assert all("no:px" not in " ".join(cmd) for cmd in calls)
    assert not (rdir / "pytest-main-retry.log").exists()


def _symlink_side_venv(root: Path, side: str) -> Path:
    """One side's venv: bin/python is a symlink the host does not see as a regular file.

    A bubblewrap install leaves this layout. The symlink names the interpreter the sandbox mounts.
    On the host that target is not a file, so a separate existence check used to skip the plugin list
    after the tests had already run this path.
    """
    from guardrails import sandbox

    venv = root / f"venv-{side}"
    link = venv / "bin" / "python"
    link.parent.mkdir(parents=True)
    link.symlink_to(Path(sandbox.INSIDE_PYTHON) / "not-on-the-host" / "bin" / "python3")
    return venv


def _per_side_symlink_venvs(root: Path) -> dict:
    return {side: _symlink_side_venv(root, side) for side in ("main", "pr")}


def test_a_symlink_venv_python_is_the_one_the_plugin_list_runs(tmp_path, monkeypatch):
    """The list is read by execing each side's venv python, not by a host is_file check."""
    venvs = _per_side_symlink_venvs(tmp_path / "work")
    for side, venv in venvs.items():
        py = Path(dr.venv_python(venv))
        assert py == venv / "bin" / "python"
        assert py.is_symlink() and not py.is_file(), side
    seen = []

    def fake_in_side(venv, cmd, **_kw):
        argv = [str(c) for c in cmd]
        seen.append(argv)
        text = json.dumps([["asyncio", "pytest_asyncio.plugin", "pytest-asyncio"]]) + "\n"
        return subprocess.CompletedProcess(argv, 0, text, "")

    monkeypatch.setattr(dr, "_contree_ready", lambda: False)
    monkeypatch.setattr(dr, "in_side", fake_in_side)
    found, why = dr.installed_pytest_entry_points(venvs)
    assert why == "" and found == [("asyncio", "pytest_asyncio.plugin", "pytest-asyncio")]
    assert seen == [[dr.venv_python(venvs["main"]), "-c", dr.PYTEST_ENTRY_POINTS_PY]]
    assert "no Python interpreter" not in why


def test_the_retry_runs_when_the_venv_python_is_only_a_symlink(tmp_path, monkeypatch):
    venvs = _per_side_symlink_venvs(tmp_path / "work")
    seen = []

    def fake_run(cmd, log, **_kw):
        cmd = [str(c) for c in cmd]
        junit = next(c.split("=", 1)[1] for c in cmd if c.startswith("--junitxml="))
        seen.append(cmd)
        if "no:asyncio" in cmd:
            Path(log).write_text("1 passed\n")
            Path(junit).write_text(JUNIT)
            return 0, 0.1
        Path(log).write_text(START_MAIN if "-main-" in Path(log).name else START_PR)
        return 3, 0.1

    def fake_in_side(venv, cmd, **_kw):
        argv = [str(c) for c in cmd]
        assert argv[0] == dr.venv_python(venv)
        text = json.dumps(list(ASYNCIO)) + "\n"
        return subprocess.CompletedProcess(argv, 0, text, "")

    monkeypatch.setattr(dr, "run", fake_run)
    monkeypatch.setattr(dr, "in_side", fake_in_side)
    monkeypatch.setattr(dr, "_contree_ready", lambda: False)
    monkeypatch.setattr(dr, "base_env", lambda *a, **k: {})
    monkeypatch.setattr(dr, "side_home", lambda v: tmp_path)
    monkeypatch.setattr(dr, "side_out", lambda v: tmp_path / "out")
    (tmp_path / "out").mkdir()
    monkeypatch.setattr(dr, "side_sandbox", lambda *a, **k: None)
    rec = {}
    a = SimpleNamespace(runs=1, workers="0", test_timeout=30, run_timeout=60, pr=None, product_check=False, bench=None)
    rdir = tmp_path / "run"
    rdir.mkdir()
    checkout = tmp_path / "src"
    checkout.mkdir()
    (checkout / "pyproject.toml").write_text("[tool.pytest]\naddopts = ['-p', 'pytester']\n")
    cmp, cnv, _ex = dr.execute_tests(
        rec, venvs, {"main": ["t.py"], "pr": ["t.py"]}, rdir, tmp_path, a,
        cwds={"main": checkout, "pr": checkout})
    assert cnv is None and cmp["same"] == 1
    assert "verdict" not in rec
    assert rec["pytest_plugins_off"] == ["asyncio"]
    attempt = rec["plugin_retry"]
    assert attempt["detection_fired"] is True and attempt["kind"] == "startup"
    assert attempt["plugin_list_read"] is True and attempt["plugins"] == ["asyncio"]
    assert attempt["flags"] == "-p no:asyncio" and attempt["outcome"] == "worked"
    assert "no Python interpreter" not in attempt["plugin_list_why"]
    assert seen[0][0] == dr.venv_python(venvs["main"])
    assert seen[1][0] == dr.venv_python(venvs["pr"])
    assert sum("no:asyncio" in c for c in seen) == 2


def test_the_base_side_pytest_uses_that_same_python(tmp_path, monkeypatch):
    work = tmp_path / "work"
    venvs = _per_side_symlink_venvs(work)
    pr = work / "side-pr"
    main = work / "side-main"
    main.mkdir()
    (pr / "tests").mkdir(parents=True)
    (pr / "tests" / "test_mod.py").write_text("def test_answer():\n    assert False\n")
    cmds = []

    def fake_run(cmd, log, **_kw):
        cmds.append([str(c) for c in cmd])
        Path(log).write_text("1 passed\n")
        return 0, 0.1

    monkeypatch.setattr(dr, "run", fake_run)
    monkeypatch.setattr(dr, "_contree_ready", lambda: False)
    files = {"all": ["pkg/mod.py", "tests/test_mod.py"], "package_py": ["pkg/mod.py"]}
    a = SimpleNamespace(runs=1, workers="0", test_timeout=30, run_timeout=60, pr=None, product_check=False, bench=None)
    (tmp_path / "run").mkdir()
    dr.record_cross_run(
        {"files": files}, venvs, {"main": [], "pr": ["tests/test_mod.py"]}, tmp_path / "run", a,
        {"main": [{}], "pr": [{"tests.test_mod::test_answer": ("passed", "")}]},
        cwds={"main": main, "pr": pr})
    assert cmds and cmds[0][0] == dr.venv_python(venvs["main"])
    assert cmds[0][1:3] == ["-m", "pytest"]
    assert Path(cmds[0][0]).is_symlink() and not Path(cmds[0][0]).is_file()


def test_contree_reads_plugins_with_the_checkpoint_python(tmp_path, monkeypatch):
    """A host symlink that is not a regular file must not hide the checkpoint interpreter."""
    venvs = _per_side_symlink_venvs(tmp_path / "work")
    assert all(not Path(dr.venv_python(v)).is_file() for v in venvs.values())
    calls = []

    class Sess:
        def run_argv(self, side, argv, timeout=60):
            calls.append((side, list(argv)))
            text = json.dumps([["asyncio", "pytest_asyncio.plugin", "pytest-asyncio"]]) + "\n"
            return {"stdout": text, "stderr": "", "exit_code": 0}

    monkeypatch.setattr(dr, "_contree_ready", lambda: True)
    monkeypatch.setattr("poc.contree_sandboxes.session", lambda: Sess())
    found, why = dr.installed_pytest_entry_points(venvs)
    assert why == "" and found[0][0] == "asyncio"
    assert calls[0] == ("main", [dr.venv_python(contree=True), "-c", dr.PYTEST_ENTRY_POINTS_PY])
    assert calls[0][1][0] == "python"


def test_contree_commands_carry_the_same_flag(tmp_path, monkeypatch):
    shells = []

    class Sess:
        pr_uuid = "pr-1"

        def run_op(self, side, shell, **k):
            shells.append(shell)
            return {"exit_code": 0, "stdout": "___POC_EXIT___0\n", "stderr": ""}

    monkeypatch.setattr("poc.contree_sandboxes.session", lambda: Sess())
    dr._contree_pytest_once("main", ["t.py"], 30, 30, "0", tmp_path / "j.xml", tmp_path / "l.log",
                            plugins_off=["px"])
    assert "-p no:px" in shells[0]
    main = tmp_path / "main" / "widget"
    pr = tmp_path / "pr" / "widget"
    main.mkdir(parents=True)
    pr.mkdir(parents=True)
    (main / "core.py").write_text("def f():\n    return 1\n")
    (pr / "core.py").write_text("def f():\n    return 2\n")
    item = {"files": {"all": ["widget/core.py"]}}
    a = SimpleNamespace(no_coverage=False, baseline="full", test_timeout=30, workers="0", run_timeout=60,
                        product_check=False, pr=None, bench=None)
    dr.contree_coverage_run(item, main.parent, pr.parent, ["tests/t.py"], tmp_path, a, plugins_off=["px"])
    assert "-p no:px" in shells[-1]
