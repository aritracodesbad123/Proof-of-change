"""Offline checks for requirement sources, the import package, and test mapping.

A requirements file counts whatever sits before the word requirements, and ``-r`` / ``--requirement``
includes are followed, including from tox ``deps``. The import package of a repo that is not a built-in
library comes from the checkout. A changed file with no stem-matched test uses test files in the nearest
tests directory that mention it. With ``python_files = *``, a support file that has no test function and
no test class is not a test. No pull request is contacted.
"""
from pathlib import Path

from ops import daily_run as dr
from poc import demo_helper


def _write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def test_requirement_files_follow_includes_and_tox_deps(tmp_path):
    _write(tmp_path, "nested/more.txt", "freezegun==1.2\n-r a.txt\n")
    _write(tmp_path, "nested/a.txt", "-r b.txt\nalpha==1\n")
    _write(tmp_path, "nested/b.txt", "-r a.txt\nbeta==1\n")
    _write(tmp_path, "outside.txt", "escaped==1\n")
    _write(tmp_path, "nested/escape.txt", "-r ../outside.txt\n")
    _write(tmp_path, "dev-requirements.txt",
           "-r nested/more.txt\n-r nested/escape.txt\npytest-relaxed>=2\n-e .\n")
    _write(tmp_path, "test-requirements.txt", "coverage\n")
    _write(tmp_path, "system-requirements.txt", "libffi-dev\n")
    _write(tmp_path, "notes.txt", "not-a-requirement\n")
    _write(tmp_path, "constraints.txt", "should-not-appear==1\n")
    _write(tmp_path, "extra/pins.txt", "pins-pkg==3\n")
    _write(tmp_path, "tox.ini",
           "[testenv]\ndeps =\n    -r{toxinidir}/test-requirements.txt\n    -r extra/pins.txt\n"
           "    -c constraints.txt\n    pytest-timeout\n"
           "[testenv:docs]\ndeps = sphinx\n")
    lines = demo_helper.declared_requirement_lines(tmp_path)
    names = {demo_helper.req_name(line) for line in lines}
    assert {"pytest-relaxed", "freezegun", "alpha", "beta", "coverage", "pins-pkg",
            "pytest-timeout", "sphinx"} <= names
    assert "escaped" not in names and "should-not-appear" not in names and "not-a-requirement" not in names
    assert "libffi-dev" not in names
    installed = {item["name"]: item for item in demo_helper.declared_packages(tmp_path)}
    assert installed["pytest-relaxed"]["action"] == "install"
    assert installed["pytest-relaxed"]["source"] == "dev-requirements.txt"
    assert installed["pytest-timeout"]["source"] == "tox.ini"
    assert installed["pins-pkg"]["source"] == "pins.txt"
    plan = demo_helper.deps_only_plan(tmp_path)
    assert plan["files"] == ["dev-requirements.txt", "test-requirements.txt"]


def test_package_name_comes_from_the_checkout(tmp_path):
    root = tmp_path / "flat"
    _write(root, "barcode/__init__.py", "")
    _write(root, "tests/__init__.py", "")
    _write(root, "docs/__init__.py", "")
    assert dr.package_from_checkout(root) == "barcode"
    cfg = {"dist": "python-barcode", "pkg": "python_barcode"}
    item = {"files": {"all": ["barcode/codex.py", "docs/index.rst"], "package_py": [], "compiled": [], "other": []}}
    rec = {"files": {"all": list(item["files"]["all"]), "package_py": [], "compiled": [], "other": []}}
    assert dr.use_checkout_package("acme/widget", cfg, root, item, rec) == "barcode"
    assert cfg["pkg"] == "barcode"
    assert item["files"]["package_py"] == ["barcode/codex.py"]
    assert rec["files"]["package_py"] == ["barcode/codex.py"]
    kept = {"pkg": "sklearn"}
    assert dr.use_checkout_package("scikit-learn/scikit-learn", kept, root) == "sklearn"
    assert kept["pkg"] == "sklearn"

    listed = tmp_path / "listed"
    _write(listed, "setup.cfg", "[options]\npackages =\n    barcode\n    barcode.writer\n")
    assert dr.package_from_checkout(listed) == "barcode"

    src = tmp_path / "src-layout"
    _write(src, "pyproject.toml", '[tool.setuptools.package-dir]\n"" = "src"\n')
    _write(src, "src/barcode/__init__.py", "")
    _write(src, "tests/__init__.py", "")
    assert dr.package_from_checkout(src) == "barcode"

    bare = tmp_path / "bare-src"
    _write(bare, "src/widget/__init__.py", "")
    assert dr.package_from_checkout(bare) == "widget"

    many = tmp_path / "many"
    _write(many, "foo/__init__.py", "")
    _write(many, "bar/__init__.py", "")
    assert dr.package_from_checkout(many) is None
    guess = {"pkg": "python_barcode"}
    files = {"files": {"all": ["foo/a.py"], "package_py": [], "compiled": [], "other": []}}
    assert dr.use_checkout_package("acme/widget", guess, many, files) == "python_barcode"
    assert files["files"]["package_py"] == []


def test_nearest_tests_dir_uses_files_that_mention_the_module(tmp_path):
    _write(tmp_path, "pkg/widgets.py", "def build():\n    return 1\n")
    _write(tmp_path, "pkg/tests/test_local.py", "def test_local():\n    assert True\n")
    _write(tmp_path, "tests/test_other.py", "import pkg.widgets\n\ndef test_other():\n    assert True\n")
    _write(tmp_path, "tests/test_noise.py", "def test_noise():\n    assert True\n")
    # The nearer tests directory does not mention the module, so it is not used.
    # Nothing is named test_widgets.py, so the stem match finds nothing.
    files = {"all": ["pkg/widgets.py"], "package_py": ["pkg/widgets.py"]}
    assert dr.map_repo_tests(files, tmp_path) == []
    _write(tmp_path, "pkg/tests/test_local.py", "from pkg.widgets import build\n\ndef test_local():\n    assert build()\n")
    assert dr.map_repo_tests(files, tmp_path) == ["pkg/tests/test_local.py"]


def test_catch_all_skips_support_files_without_tests(tmp_path):
    _write(tmp_path, "pytest.ini", "[pytest]\npython_files = *\n")
    _write(tmp_path, "pkg/tasks.py", "def run():\n    return 1\n")
    _write(tmp_path, "tests/_support/branch/tasks.py", "def foo(c):\n    return c\n\ndef noop(c):\n    return None\n")
    _write(tmp_path, "tests/task.py",
           "import pkg.tasks\n\nclass task_:\n    def runs(self):\n        assert pkg.tasks\n")
    _write(tmp_path, "tests/other.py", "def test_other():\n    assert True\n")
    files = {"all": ["pkg/tasks.py", "tests/_support/branch/tasks.py"], "package_py": ["pkg/tasks.py"]}
    got = dr.map_repo_tests(files, tmp_path)
    assert got == ["tests/task.py"]
    assert "tests/_support/branch/tasks.py" not in got
    assert "tests/other.py" not in got
    _write(tmp_path, "tests/tasks.py", "def test_real():\n    assert True\n")
    got = dr.map_repo_tests(files, tmp_path)
    assert got == ["tests/tasks.py"]
