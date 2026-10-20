"""Differential probes call a function with more than one kind of value.

Synthetic package only. The mix is integers, a float, bool, None, empty values, and numpy or pandas when installed.
"""
import importlib.util
import json
import subprocess
import sys

from poc import diff_probes

BODY = '''
def kind(x):
    if x is None:
        return "none"
    if isinstance(x, bool):
        return "bool"
    name = type(x).__name__
    if name == "ndarray":
        return "numpy"
    if type(x).__module__.split(".", 1)[0] == "pandas":
        return "pandas"
    if isinstance(x, int):
        return "int"
    if isinstance(x, float):
        return "float"
    if x == "" or x == [] or x == {}:
        return "empty"
    return "other"
'''


def test_probe_source_names_the_mixed_types():
    text = diff_probes.PROBE_BODY
    for piece in ("True", "False", '""', "[]", "{}", "numpy", "pandas", "None"):
        assert piece in text


def test_a_type_specific_function_is_called_with_each_kind(tmp_path):
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "m.py").write_text(BODY)
    path = diff_probes.write([("pkg.m", "kind")], tmp_path / "diff-api.py", "o/r#1")
    env = {"PATH": "/usr/bin:/bin", "PYTHONPATH": str(tmp_path)}
    out = subprocess.run([sys.executable, str(path)], capture_output=True, text=True, cwd=tmp_path, env=env)
    assert out.returncode == 0, out.stderr
    seen = set(json.loads(out.stdout)["observations"].values())
    assert {"int", "float", "bool", "none", "empty"} <= seen
    assert "numpy" in seen or importlib.util.find_spec("numpy") is None
    assert "pandas" in seen or importlib.util.find_spec("pandas") is None


def test_the_same_probe_file_lists_the_same_inputs(tmp_path):
    first = diff_probes.write([("pkg.m", "kind")], tmp_path / "a.py", "o/r#1").read_text()
    second = diff_probes.write([("pkg.m", "kind")], tmp_path / "b.py", "o/r#1").read_text()
    assert first == second
