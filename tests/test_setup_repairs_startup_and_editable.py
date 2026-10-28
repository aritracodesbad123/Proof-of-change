"""Setup repairs that only let a check run: a crashing auto-loaded pytest plugin the project does not name, and a
failed editable build under set -e (ops/daily_run.py, poc/contree_sandboxes.py)."""
import os
import subprocess
import sys
import textwrap

from ops import daily_run as dr
from poc import contree_sandboxes as cs


def _pick(tmp_path, log, cfg, eps):
    """Run the plugin picker against a fake log, project config and pytest11 entry points."""
    (tmp_path / "pyproject.toml").write_text(cfg)
    (tmp_path / "poc-pytest.log").write_text(log)
    shim = tmp_path / "shim.py"
    shim.write_text(textwrap.dedent(f"""
        import importlib.metadata as md, types, pathlib
        class D:
            def __init__(s, n): s.name = n
        md.entry_points = lambda group=None: [types.SimpleNamespace(name=n, value=v, dist=D(d)) for n, v, d in {eps!r}]
        _rt = pathlib.Path.read_text
        pathlib.Path.read_text = lambda s, *a, **k: _rt(pathlib.Path({str(tmp_path / 'poc-pytest.log')!r})
                                                        if str(s) == '/tmp/poc-pytest.log' else s, *a, **k)
    """))
    code = "exec(open('shim.py').read())\n" + dr.STARTUP_PLUGIN_PY
    return subprocess.run([sys.executable, "-c", code], cwd=tmp_path, capture_output=True, text=True).stdout.strip()


LOG = ('INTERNALERROR>   File "/usr/local/lib/python3.12/site-packages/pluggy/_manager.py", line 1\n'
       'INTERNALERROR>   File "/usr/local/lib/python3.12/site-packages/plugx/plugin.py", line 9, in pytest_configure\n')
EPS = [("px", "plugx.plugin", "pytest-plugx"), ("other", "otherpkg.p", "pytest-other")]


def test_unnamed_crashing_plugin_is_turned_off(tmp_path):
    assert _pick(tmp_path, LOG, "[tool.pytest.ini_options]\nfilterwarnings=['error']\n# plugx_integration.py\n",
                 EPS) == "px"


def test_plugin_the_project_names_is_kept(tmp_path):
    assert _pick(tmp_path, LOG, "[project.optional-dependencies]\ntest=['pytest-plugx>=1']\n", EPS) == ""
    assert _pick(tmp_path, LOG, "[tool.pytest.ini_options]\naddopts='-p px'\n", EPS) == ""


def test_no_internal_error_means_no_repair(tmp_path):
    assert _pick(tmp_path, "1 failed\n", "", EPS) == ""


def test_retry_only_on_exit_3_and_is_noted():
    sh = dr.STARTUP_PLUGIN_RETRY_SHELL
    assert sh.startswith('if [ "$ec" = 3 ]') and "-p no:$n" in sh and "Setup repair:" in sh and "{RERUN}" in sh


def test_editable_failure_reaches_fallback_under_set_e(tmp_path):
    body = cs.EDITABLE_REINSTALL_SHELL.replace("/work/poc-install.txt", str(tmp_path / "r.txt")).replace(
        "/work/poc-editable.log", str(tmp_path / "e.log")).replace("/work/.poc-tmp", str(tmp_path / "t")).replace(
        "/work/src", str(tmp_path / "src"))
    fake = tmp_path / "bin"
    fake.mkdir()
    (fake / "python").write_text('#!/bin/sh\n[ "$2" = pip ] && exit 1\nexec ' + sys.executable + ' "$@"\n')
    (fake / "python").chmod(0o755)
    (tmp_path / "src").mkdir()
    env = dict(os.environ, PATH=f"{fake}:{os.environ['PATH']}")
    r = subprocess.run(["bash", "-c", "set -euo pipefail\n" + body + "echo reached-end"], env=env,
                       capture_output=True, text=True)
    assert r.returncode == 0 and "reached-end" in r.stdout, r.stderr
    rep = (tmp_path / "r.txt").read_text()
    assert "editable_retry=" in rep and "editable_exit=1" in rep and "editable_fallback=source path" in rep


def test_product_install_uses_work_tmpdir_and_study_does_not():
    assert "export TMPDIR=/work/.poc-tmp" in cs.install_shell_source("o/r", "a" * 40, deps_only_fallback=True)
    assert "TMPDIR" not in cs.install_shell_source("o/r", "a" * 40)
