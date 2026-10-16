"""Contree bridge in ops/daily_run: mock session drives pytest + probe dual-run helpers."""
from __future__ import annotations

from pathlib import Path

from poc import contree_sandboxes


def test_contree_pytest_once_parses_markers(tmp_path, monkeypatch):
    monkeypatch.setenv("NEBIUS_API_KEY", "fake")
    monkeypatch.setenv("NEBIUS_PROJECT_ID", "proj")
    import sys, types
    sys.modules.setdefault("contree_sdk", types.ModuleType("contree_sdk"))
    contree_sandboxes.select("contree")

    junit = '<?xml version="1.0"?><testsuites><testsuite tests="1" failures="0" errors="0" skipped="0">'
    junit += '<testcase classname="t" name="a"/></testsuite></testsuites>'

    def runner(shell, disposable, image_ref, timeout, files=None):
        assert disposable and image_ref == "main-uuid"
        body = f"___POC_EXIT___0\n___POC_JUNIT___\n{junit}\n___POC_LOG___\n1 passed\n"
        return {"exit_code": 0, "stdout": body, "stderr": "", "uuid": None}

    sess = contree_sandboxes.new_session(runner=runner)
    sess.main_uuid, sess.pr_uuid = "main-uuid", "pr-uuid"

    from ops import daily_run
    jx, lg = tmp_path / "j.xml", tmp_path / "p.log"
    rc, secs = daily_run._contree_pytest_once("main", ["tests/test_a.py"], 30, 60, "0", jx, lg)
    assert rc == 0 and secs >= 0
    assert jx.is_file() and "testcase" in jx.read_text()
    assert "1 passed" in lg.read_text()


def test_contree_probe_once_uploads(tmp_path, monkeypatch):
    monkeypatch.setenv("NEBIUS_API_KEY", "fake")
    monkeypatch.setenv("NEBIUS_PROJECT_ID", "proj")
    import sys, types
    sys.modules.setdefault("contree_sdk", types.ModuleType("contree_sdk"))
    contree_sandboxes.select("contree")

    probe = tmp_path / "probe.py"
    probe.write_text('print(\'{"observations": {"x": 1}}\')\n')

    seen = {}

    def runner(shell, disposable, image_ref, timeout, files=None):
        seen["files"] = files
        seen["shell"] = shell
        return {"exit_code": 0, "stdout": '{"observations": {"x": 1}}\n', "stderr": "", "uuid": None}

    sess = contree_sandboxes.new_session(runner=runner)
    sess.main_uuid, sess.pr_uuid = "main-uuid", "pr-uuid"

    from ops import daily_run
    obs, log, secs = daily_run._contree_probe_once("pr", probe, 30)
    assert obs.get("x") == 1 and secs >= 0
    assert seen["files"] and probe.name in str(list(seen["files"].keys())[0])
