"""A third-party pytest plugin that breaks collection the same way on both sides is turned off once.

The fixture is a pair of pytest logs. The plugin name in the logs is not special: the entry-point name comes
from the traceback and the installed pytest11 metadata. Verdict rules are not an input to this retry.
"""
from __future__ import annotations

import inspect
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
    monkeypatch.setattr(dr, "installed_pytest_entry_points", lambda venvs: list(EPS))
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
    assert rec["collection_plugin_note"].startswith("Setup: pytest plugin px was turned off.")
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
    monkeypatch.setattr(dr, "installed_pytest_entry_points", lambda venvs: list(EPS))
    rec = {}
    a = SimpleNamespace(runs=1, workers="0", test_timeout=30, run_timeout=60, pr=None, product_check=False, bench=None)
    rdir = tmp_path / "run"
    rdir.mkdir()
    _cmp, cnv, _ex = dr.execute_tests(
        rec, {"main": tmp_path / "vm", "pr": tmp_path / "vp"},
        {"main": ["t.py"], "pr": ["t.py"]}, rdir, tmp_path, a, cwds={"main": tmp_path, "pr": tmp_path})
    assert cnv and "collection failed" in cnv
    assert "collection_plugin_note" not in rec and "pytest_plugins_off" not in rec
    assert "missing_stack" in (rdir / "pytest-main-1.log").read_text()
    assert "still broken" not in (rdir / "pytest-main-1.log").read_text()
    assert "still broken" not in (rdir / "pytest-pr-1.log").read_text()


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
