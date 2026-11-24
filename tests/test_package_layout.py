"""Src layouts and private package directories are package code, so their changes get tests mapped.

A directory named testing, tests, or fixtures is not a package, including under src/ and when the name
starts with an underscore. A python_files pattern that names a directory matches the relative path, so
the stem of a changed package file can find that test module. No repository is special-cased.
"""
from pathlib import Path

from ops import daily_run as dr


def _write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def test_src_layout_and_private_package_are_package_code():
    files = [
        "src/_impl/fixtures.py",
        "src/public/__init__.py",
        "src/_impl/speed.c",
        "_private/mod.py",
        "testing/check.py",
        "src/testing/helper.py",
        "src/fixtures/data.py",
        "src/_fixtures/sample.py",
        "src/public/fixtures.py",
        "README.md",
    ]
    got = dr.classify_files(files, "public")
    assert got["package_py"] == [
        "src/_impl/fixtures.py",
        "src/public/__init__.py",
        "_private/mod.py",
        "src/public/fixtures.py",
    ]
    assert got["compiled"] == ["src/_impl/speed.c"]
    assert "testing/check.py" in got["other"]
    assert "src/testing/helper.py" in got["other"]
    assert "src/fixtures/data.py" in got["other"]
    assert "src/_fixtures/sample.py" in got["other"]
    assert "README.md" in got["other"]


def test_a_testing_directory_is_not_mapped_as_the_package(tmp_path):
    """The changed private module maps to the test file the project's python_files pattern names.

    The testing directory and a fixtures directory are not package code, so they are not what the
    mapper searches from.
    """
    _write(tmp_path, "pyproject.toml",
           '[tool.pytest.ini_options]\npython_files = ["test_*.py", "*_test.py", "testing/python/*.py"]\n')
    _write(tmp_path, "src/_impl/__init__.py", "")
    _write(tmp_path, "src/_impl/fixtures.py", "def use():\n    return 1\n")
    _write(tmp_path, "src/public/__init__.py", "")
    _write(tmp_path, "src/testing/helper.py", "def helper():\n    return 1\n")
    _write(tmp_path, "src/fixtures/data.py", "VALUE = 1\n")
    _write(tmp_path, "testing/check.py", "def test_check():\n    assert True\n")
    _write(tmp_path, "testing/python/fixtures.py", "def test_use():\n    assert True\n")
    changed = [
        "src/_impl/fixtures.py",
        "src/public/__init__.py",
        "src/testing/helper.py",
        "src/fixtures/data.py",
        "testing/check.py",
    ]
    files = dr.classify_files(changed, "public")
    assert files["package_py"] == ["src/_impl/fixtures.py", "src/public/__init__.py"]
    mapped = dr.map_repo_tests(files, tmp_path)
    assert mapped == ["testing/python/fixtures.py"]
    assert "testing/check.py" not in mapped
    assert "src/testing/helper.py" not in mapped
    assert "src/fixtures/data.py" not in mapped


def test_named_package_outside_src_is_unchanged():
    got = dr.classify_files(
        ["numpy/lib/_x.py", "numpy/_core/src/a.c", "doc/x.rst", "pyproject.toml"], "numpy")
    assert got["package_py"] == ["numpy/lib/_x.py"]
    assert "numpy/_core/src/a.c" in got["compiled"]
    assert "doc/x.rst" in got["other"]
