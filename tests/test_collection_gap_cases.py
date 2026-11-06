"""Real environments for a collection gap next to a fix that is already evidenced.

The base interpreter does not see a module that exists only on the pull-request environment.
A changed file that fails to collect is not a new pass. An unchanged file is not reported.
A skipped test is not a pass. Needs attention from a probe is not replaced. A parent path that
is a file does not crash the copy onto the base.
"""
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from ops import daily_run as dr
from poc import probes

INI = "[pytest]\npython_files = *\npython_classes = *\npython_functions = *\n"
OLD = "def test_old():\n    assert True\n"
FIX = "def test_answer():\n    from pkg.mod import answer\n    assert answer() == 2\n"
HOLD = "def test_hold():\n    assert True\n"
SKIP = "import pytest\n\n@pytest.mark.skip(reason='not run')\ndef test_skipped_new():\n    assert False\n"
NEED = "import pr_only\n\ndef test_needs():\n    assert pr_only.value == 1\n"
BLANK = "# no tests in this changed file\n"
PARTIAL_BASE = "# base has no tests yet\n"
PARTIAL_PR = "def test_new():\n    assert True\n"


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _venv(work: Path, name: str) -> Path:
    import pytest as pytest_mod

    venv = work / name
    bindir = venv / "bin"
    bindir.mkdir(parents=True)
    (bindir / "python").symlink_to(sys.executable)
    ver = f"python{sys.version_info.major}.{sys.version_info.minor}"
    sp = venv / "lib" / ver / "site-packages"
    sp.mkdir(parents=True)
    (sp / "runner.pth").write_text(str(Path(pytest_mod.__file__).resolve().parent.parent) + "\n")
    (venv / "pyvenv.cfg").write_text(
        f"home = {Path(sys.executable).resolve().parent}\ninclude-system-site-packages = false\n"
        f"version = {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}\n"
    )
    return venv


def _tree(root: Path, answer: str) -> None:
    _write(root / "pytest.ini", INI)
    _write(root / "pkg" / "__init__.py", "")
    _write(root / "pkg" / "mod.py", f"def answer():\n    return {answer}\n")
    _write(root / "tests" / "__init__.py", "")
    _write(root / "tests" / "test_old.py", OLD)
    _write(root / "tests" / "test_fix.py", FIX)
    _write(root / "tests" / "test_holdout.py", HOLD)
    _write(root / "tests" / "needs_dep.py", NEED)
    _write(root / "tests" / "blank.py", BLANK)
    _write(root / "tests" / "partial.py", PARTIAL_BASE)


def test_parent_file_blocks_the_copy_without_raising(tmp_path):
    main, pr = tmp_path / "main", tmp_path / "pr"
    _write(main / "tests", "not a directory\n")
    _write(pr / "tests" / "checks.py", "def test_x():\n    assert True\n")
    blocked: list[str] = []
    saved = dr._overlay_pr_tests(main, pr, ["tests/checks.py"], blocked)
    assert saved == []
    assert blocked == ["tests/checks.py"]
    assert (main / "tests").is_file()


def test_probe_flag_stays_needs_attention_beside_the_note():
    """A flagged probe is not replaced by the already-on-base note or by the collection cap."""
    passed = {"tests/test_old.py::test_old": ("passed", "")}
    cmp = dr.compare_sides({"main": [passed] * 3, "pr": [passed] * 3})
    gap = {"ids": ["tests/checks.py::test_new"], "passed_on_base": ["tests/checks.py::test_new"],
           "failed_on_base": [], "not_collected": [], "reproduced": False,
           "collection_failed": ["tests/needs_dep.py"]}
    cmp["base_new_tests"] = gap
    spec = {"id": "p", "target": "o/r#1", "about": "x", "claims": [
        {"id": "C1", "text": "a changes", "covers": ["a.*"], "expect": "differs"}]}
    item = probes.entry(spec, {"main": [{"c": 1}] * 3, "pr": [{"c": 2}] * 3},
                        {"main": ["m"], "pr": ["p"]}, [], "library", None)
    found = dr.verdict_for(cmp, None, None, {"all": ["pkg/mod.py"]}, {"status": "ran", "items": [item]})
    assert found[0] == "needs_attention"
    held_v, held_reason = dr.cap_for_uncollected_file(cmp, found[0], found[1])
    assert held_v == "needs_attention" and held_reason == found[1]
    sha = "a" * 40
    rec = {"verdict": held_v, "reason": held_reason, "base_ref": "2.2",
           "pr": {"tested_main_sha": sha}}
    dr._attach_already_on_base(rec, cmp)
    assert rec["verdict"] == "needs_attention"
    assert rec["already_on_base"] == f"fix appears already present on 2.2 at {sha[:12]}"
    assert "tests/needs_dep.py" in rec["collection_limitation"]


def test_base_env_does_not_inherit_pr_deps_and_gaps_are_not_passes(tmp_path):
    """The base collection uses the base interpreter. A missing module is not a new pass.

    Fixed tests stay in ``fixed``. An unchanged file is absent from the collection record.
    A skipped test is not counted as passed. An empty collection is recorded, not skipped silently.
    """
    pytest.importorskip("pytest_timeout")
    from guardrails import sandbox

    work = tmp_path / "work"
    main, pr = work / "side-main", work / "side-pr"
    _tree(main, "1")
    _tree(pr, "2")
    _write(pr / "tests" / "partial.py", PARTIAL_PR)
    _write(pr / "tests" / "test_skip_new.py", SKIP)
    only = work / "pr-only"
    _write(only / "pr_only.py", "value = 1\n")
    venvs = {"main": _venv(work, "venv-main"), "pr": _venv(work, "venv-pr")}
    ver = f"python{sys.version_info.major}.{sys.version_info.minor}"
    (venvs["pr"] / "lib" / ver / "site-packages" / "pr-only.pth").write_text(str(only) + "\n")
    base_py, pr_py = venvs["main"] / "bin" / "python", venvs["pr"] / "bin" / "python"
    changed = ["pkg/mod.py", "tests/test_fix.py", "tests/needs_dep.py", "tests/blank.py",
               "tests/partial.py", "tests/test_skip_new.py"]
    rec = {"files": {"all": changed, "package_py": ["pkg/mod.py"], "compiled": [], "other": changed[1:]},
           "base_ref": "master", "pr": {"tested_main_sha": "09dbe1eec31ed1b3cd05366748865f11ba427d32"}}
    rundir = tmp_path / "run"
    rundir.mkdir()
    a = SimpleNamespace(runs=1, workers="0", test_timeout=60, run_timeout=120, build_timeout=60,
                        pr="https://github.com/o/r/pull/1", product_check=False, bench=None)
    was = sandbox.enabled()
    sandbox.configure(False)
    try:
        base_rc, _ = dr.run([str(base_py), "-c", "import pr_only"], work / "base-import.log", cwd=work,
                            env=dr.base_env(dr.side_home(venvs["main"])))
        pr_rc, _ = dr.run([str(pr_py), "-c", "import pr_only"], work / "pr-import.log", cwd=work,
                          env=dr.base_env(dr.side_home(venvs["pr"])))
        assert base_rc != 0 and pr_rc == 0
        cmp, cnv, _ex = dr.execute_tests(rec, venvs, {"main": ["tests/test_old.py"], "pr": ["tests/test_old.py"]},
                                         rundir, work, a, cwds={"main": main, "pr": pr})
    finally:
        sandbox.configure(was)
    assert cnv is None and cmp is not None
    info = cmp["base_new_tests"]
    assert "tests/needs_dep.py" in info["collection_failed"]
    assert "tests/blank.py" in info["discovery_empty"]
    assert not any("needs_dep" in str(t) or "blank" in str(t) for t in info["passed_on_base"])
    assert not any("needs_dep" in str(t) or "blank" in str(t) or "holdout" in str(t) or "skipped_new" in str(t)
                   for t in cmp.get("new_tests_passing_ids") or [])
    assert "holdout" not in str(info)
    assert any("test_answer" in str(t) for t in cmp["fixed"])
    for node in info["passed_on_base"]:
        assert node.split("::")[-1].split("[")[0] in (rundir / "junit-main-1.xml").read_text()
    before = dr.verdict_for(cmp, None, None, rec["files"])
    assert before[0] == "verified"
    dr._store_verdict(rec, cmp, None, None)
    assert rec["verdict"] == "could_not_verify"
    assert "tests/needs_dep.py" in rec["reason"]
    assert any("test_answer" in str(t) for t in cmp["fixed"])
    assert "tests/needs_dep.py" in rec["collection_limitation"]
    assert "tests/blank.py" in rec["collection_limitation"]
    base_log = next(rundir.glob("collect-cross-main-tests_needs_dep.py.log"))
    assert "pr_only" in base_log.read_text(errors="replace")
