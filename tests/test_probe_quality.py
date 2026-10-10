"""Probe lint gate (poc/probe_quality.py)."""
import pytest

from poc import probe_quality as pq

MLX_CHANGED = ["docs/sources/CHANGELOG.md", "mlxtend/evaluate/feature_importance.py",
               "mlxtend/evaluate/tests/test_feature_importance.py"]
CHANGED = ["src/widgets/adapters.py", "tests/test_adapters.py"]
OK = "import json\nfrom widgets.adapters import Pool\nprint(json.dumps({'observations': {'n': Pool().size}}))\n"


def rules(src, changed=CHANGED):
    return {p["rule"] for p in pq.lint(src, changed)["problems"]}


def test_accepts_the_mlxtend_probe():
    r = pq.lint_file("probes/rasbt/mlxtend/1229.py", MLX_CHANGED)
    assert r["ok"], r["problems"]
    assert r["relevant_imports"] == ["mlxtend.evaluate.feature_importance"]


def test_accepts_a_plain_observing_probe():
    assert pq.lint(OK, CHANGED)["ok"]


@pytest.mark.parametrize("src,rule", [
    ("from widgets.adapters import Pool\nassert Pool().size == 3\n", "assert"),
    ("import pytest\nimport widgets.adapters as a\nwith pytest.raises(ValueError):\n    a.Pool(-1)\n", "pytest.raises"),
    ("import pytest as pt\nimport widgets.adapters as a\nwith pt.raises(ValueError):\n    a.Pool(-1)\n", "pytest.raises"),
    ("from pytest import raises\nimport widgets.adapters\n", "pytest.raises"),
    ("import socket\nimport widgets.adapters\n", "network"),
    ("from socket import create_connection\nimport widgets.adapters\n", "network"),
    ("import urllib.request\nimport widgets.adapters\n", "network"),
    ("import widgets.adapters\n__import__('socket')\n", "network"),
    ("import importlib\nimport widgets.adapters\nimportlib.import_module('subprocess')\n", "process"),
    ("import subprocess\nimport widgets.adapters\n", "process"),
    ("from subprocess import run\nimport widgets.adapters\n", "process"),
    ("import os\nimport widgets.adapters\nos.system('true')\n", "process"),
    ("import os as o\nimport widgets.adapters\no.popen('true')\n", "process"),
    ("from os import execv\nimport widgets.adapters\n", "process"),
    ("import widgets.adapters\nopen('/etc/x', 'w').write('1')\n", "write"),
    ("import widgets.adapters\nopen('/home/u/x', mode='a')\n", "write"),
    ("import json\nprint(json.dumps({'observations': {}}))\n", "relevant"),
    ("import widgets_extra\n", "relevant"),
    ("def f(:\n", "syntax"),
])
def test_rejects(src, rule):
    assert rule in rules(src)


def test_tmp_writes_and_reads_are_fine():
    assert pq.lint("import widgets.adapters\nopen('/tmp/x', 'w')\nopen('/etc/hosts')\nopen('rel.txt', 'w')\n", CHANGED)["ok"]


def test_assert_inside_a_function_is_also_rejected():
    assert "assert" in rules("import widgets.adapters\ndef f():\n    assert 1\n")


def test_library_under_test_may_be_a_network_package():
    # a probe for a requests PR imports requests itself
    assert pq.lint("import requests\nprint(requests.adapters)\n", ["src/requests/adapters.py"])["ok"]
    assert "network" in rules("import requests\nimport widgets.adapters\n")


@pytest.mark.parametrize("src", ["import widgets\n", "import widgets.adapters\n", "from widgets import adapters\n",
                                 "from widgets.adapters import Pool\n", "import widgets.adapters.sub\n"])
def test_relevance_forms(src):
    assert pq.lint(src, CHANGED)["ok"]


def test_module_of():
    assert pq.module_of("src/requests/adapters.py") == "requests.adapters"
    assert pq.module_of("pkg/sub/__init__.py") == "pkg.sub"
    assert pq.module_of("pkg/tests/test_x.py") is None
    assert pq.module_of("README.md") is None
    assert pq.changed_modules(["docs/x.md", "tests/test_a.py"]) == []
    assert "relevant" in rules("import widgets\n", ["docs/x.md"])


def test_reasons_text():
    assert pq.reasons(pq.lint(OK, CHANGED)) == "ok"
    assert pq.reasons(pq.lint("import widgets.adapters\nassert 1\n", CHANGED)).startswith("rejected: assert (line 2)")
