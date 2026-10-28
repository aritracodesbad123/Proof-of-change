"""Probe coverage uses only the check's own coverage settings, never the project's."""
import json
import subprocess
import sys

import pytest

from ops import daily_run as dr

pytest.importorskip("coverage")


def _project(tmp_path):
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "__init__.py").write_text("")
    (tmp_path / "pkg" / "mod.py").write_text("def f(x):\n    if x:\n        return 1\n    return 2\n")
    (tmp_path / "other").mkdir()
    (tmp_path / "other" / "__init__.py").write_text("")
    # hostile project settings: a source that would beat --include, parallel data files, a failing fail_under
    (tmp_path / "pyproject.toml").write_text(
        '[tool.coverage.run]\nsource = ["other"]\nparallel = true\n[tool.coverage.report]\nfail_under = 100\n')
    (tmp_path / ".coveragerc").write_text("[run]\nsource = other\nparallel = True\n[report]\nfail_under = 100\n")
    probe = tmp_path / "probe.py"
    probe.write_text("import sys\nsys.path.insert(0, '.')\nfrom pkg.mod import f\nf(1)\n")
    return probe


def test_own_settings_override_the_project(tmp_path):
    probe = _project(tmp_path)
    rc = tmp_path / "out" / "poc-probe-coveragerc"
    rc.parent.mkdir()
    rc.write_text(dr.PROBE_COVERAGE_RC)
    (tmp_path / "out" / "probe-run.log").write_text("not a database\n")  # shares no prefix with the data file
    data, js = tmp_path / "out" / ".probe-cov-p1", tmp_path / "out" / "probe-cov-p1.json"
    mod = tmp_path / "pkg" / "mod.py"
    r = subprocess.run([sys.executable, "-m", "coverage", "run", f"--rcfile={rc}", f"--data-file={data}",
                        f"--include={mod}", str(probe)], cwd=tmp_path, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert "include is ignored" not in r.stderr and "not a database" not in r.stderr
    assert data.is_file()  # not renamed by parallel mode
    r = subprocess.run([sys.executable, "-m", "coverage", "json", f"--rcfile={rc}", f"--data-file={data}", "-o",
                        str(js), "-q"], cwd=tmp_path, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr  # the project's fail_under does not apply
    files = json.loads(js.read_text())["files"]
    (key,) = files
    assert key.endswith("mod.py") and set(files[key]["executed_lines"]) >= {2, 3}


def test_contree_probe_coverage_passes_own_settings():
    import inspect
    src = inspect.getsource(dr.contree_probe_coverage) + inspect.getsource(dr.probe_coverage)
    assert src.count("--rcfile=") >= 4
    assert "parallel = False" in dr.PROBE_COVERAGE_RC and "fail_under = 0" in dr.PROBE_COVERAGE_RC
