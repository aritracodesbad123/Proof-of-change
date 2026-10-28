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


def test_coverage_run_gets_the_same_startup_repair(tmp_path, monkeypatch):
    """The coverage run is a separate pytest start, so the same unnamed crashing plugin is turned off there too."""
    from types import SimpleNamespace
    (tmp_path / "main" / "widget").mkdir(parents=True)
    (tmp_path / "pr" / "widget").mkdir(parents=True)
    (tmp_path / "main" / "widget" / "core.py").write_text("def f():\n    return 1\n")
    (tmp_path / "pr" / "widget" / "core.py").write_text("def f():\n    return 2\n")
    item = {"files": {"all": ["widget/core.py"]}}
    a = SimpleNamespace(no_coverage=False, baseline="full", test_timeout=30, workers="0", run_timeout=60)
    seen = {}

    class Sess:
        pr_uuid = "pr-1"

        def run_op(self, side, shell, **k):
            seen["shell"] = shell
            return {"exit_code": 1, "stdout": "___POC_EXIT___1\n___POC_LOG___\nno report\n", "stderr": ""}

    monkeypatch.setattr("poc.contree_sandboxes.session", lambda: Sess())
    dr.contree_coverage_run(item, tmp_path / "main", tmp_path / "pr", ["tests/t.py"], tmp_path, a)
    run_part = seen["shell"].split("printf '___POC_EXIT___", 1)[0]
    assert "python -c" in run_part and "/tmp/poc-cov-pytest.log.startup" in run_part
    # Execute the run part with a fake python: pytest crashes at startup (exit 3) unless the plugin is turned off.
    log = tmp_path / "cov.log"
    fake = tmp_path / "bin"
    fake.mkdir()
    (fake / "python").write_text(
        '#!/bin/sh\nif [ "$1" = -c ]; then echo px; exit 0; fi\n'
        'case "$*" in *"-p no:px"*) echo "1 passed"; exit 0;; esac\necho "INTERNALERROR> boom"; exit 3\n')
    (fake / "python").chmod(0o755)
    body = run_part.replace("/tmp/poc-cov-pytest.log", str(log)).replace("cd /work/src\n", "")
    body = body.replace("/tmp/poc-coveragerc", str(tmp_path / "rc"))
    r = subprocess.run(["bash", "-c", body + 'echo "ec=$ec"'], env=dict(os.environ, PATH=f"{fake}:{os.environ['PATH']}"),
                       capture_output=True, text=True)
    assert "ec=0" in r.stdout, r.stdout + r.stderr
    text = log.read_text()
    assert text.startswith("Setup repair:") and "px" in text.splitlines()[0] and "1 passed" in text
