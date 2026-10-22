"""Which Python ran on each Contree side is recorded and checked against requires-python."""
from types import SimpleNamespace

from ops import daily_run
from poc import contree_sandboxes as cs


def _session(versions):
    calls = []

    def runner(shell, disposable, image_ref, timeout, files):
        calls.append((image_ref, shell))
        out = versions.get(image_ref)
        if out is None:
            return {"exit_code": 127, "stdout": "", "stderr": "python: not found", "uuid": None}
        return {"exit_code": 0, "stdout": out, "stderr": "", "uuid": None}

    sess = cs.ContreeSession(runner=runner)
    sess.main_uuid, sess.pr_uuid = "img-main", "img-pr"
    return sess, calls


def test_parse_python_version():
    assert cs.parse_python_version({"exit_code": 0, "stdout": "Python 3.14.0\n"}) == "3.14.0"
    assert cs.parse_python_version({"exit_code": 0, "stdout": "", "stderr": "Python 3.12.7"}) == "3.12.7"
    assert cs.parse_python_version({"exit_code": 0, "stdout": "Python 3.14.0rc1"}) == "3.14.0"
    assert cs.parse_python_version({"exit_code": 0, "stdout": "garbage"}) == ""
    assert cs.parse_python_version({"exit_code": 1, "stdout": "Python 3.12.7"}) == ""
    assert cs.parse_python_version(None) == ""


def test_runs_python_version_on_each_checkpoint():
    sess, calls = _session({"img-main": "Python 3.14.0", "img-pr": "Python 3.14.0"})
    info = cs.side_pythons(sess, [">=3.14"])
    assert info["main"] == info["pr"] == "3.14.0"
    assert info["problems"] == []
    assert [c[0] for c in calls] == ["img-main", "img-pr"]
    assert all("python --version" in c[1] for c in calls)


def test_mismatch_is_a_problem():
    sess, _ = _session({"img-main": "Python 3.12.7", "img-pr": "Python 3.14.0"})
    info = cs.side_pythons(sess, [">=3.14"])
    assert info["main"] == "3.12.7"
    assert info["problems"][0].startswith("main:")
    assert info["problems"][1] == "main ran 3.12.7, PR ran 3.14.0"


def test_unreadable_version_is_a_problem():
    sess, _ = _session({"img-main": "Python 3.14.1"})
    info = cs.side_pythons(sess, [">=3.14"])
    assert info["pr"] == ""
    assert any(p.startswith("pr:") and "could not be read" in p for p in info["problems"])


def test_no_requires_python_only_needs_readable_versions():
    sess, _ = _session({"img-main": "Python 3.12.7", "img-pr": "Python 3.12.7"})
    assert cs.side_pythons(sess, [])["problems"] == []


def test_check_refuses_and_records(tmp_path):
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "x"\nrequires-python = ">=3.14"\n')
    sess, _ = _session({"img-main": "Python 3.12.7", "img-pr": "Python 3.12.7"})
    rec = {"contree": {}}
    refusal = daily_run._check_contree_pythons(sess, rec, tmp_path)
    assert refusal and "requires-python" in refusal
    assert rec["contree"]["python"]["main"] == "3.12.7"
    assert rec["contree"]["python"]["requires_python"] == [">=3.14"]


def test_check_passes_when_versions_fit(tmp_path):
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "x"\nrequires-python = ">=3.14"\n')
    sess, _ = _session({"img-main": "Python 3.14.0", "img-pr": "Python 3.14.0"})
    rec = {}
    assert daily_run._check_contree_pythons(sess, rec, tmp_path) is None
    assert rec["contree"]["python"]["pr"] == "3.14.0"


def test_prepare_runs_the_check_on_product_route(monkeypatch, tmp_path):
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "x"\nrequires-python = ">=3.14"\n')
    sess, _ = _session({"img-main": "Python 3.12.7", "img-pr": "Python 3.12.7"})
    monkeypatch.setattr(cs, "prepare_source_pair", lambda *a, **k: sess)
    monkeypatch.setattr(daily_run, "product_route", lambda a: True)
    rec = {}
    a = SimpleNamespace(sandbox_backend="contree")
    out = daily_run._maybe_prepare_contree(a, "o/r", "a" * 40, "b" * 40, rec, 60, main_dir=tmp_path)
    assert out and out.startswith("Contree Python check failed")
    assert rec["contree"]["python"]["problems"]


def test_sides_differ_without_requires_python(tmp_path):
    sess, _ = _session({"img-main": "Python 3.12.7", "img-pr": "Python 3.12.8"})
    rec = {}
    refusal = daily_run._check_contree_pythons(sess, rec, tmp_path)
    assert refusal == "Contree Python check failed: main ran 3.12.7, PR ran 3.12.8"


def test_sides_differ_with_requires_python():
    sess, _ = _session({"img-main": "Python 3.14.0", "img-pr": "Python 3.14.1"})
    info = cs.side_pythons(sess, [">=3.14"])
    assert info["problems"] == ["main ran 3.14.0, PR ran 3.14.1"]


def test_equal_sides_pass_without_requires_python(tmp_path):
    sess, _ = _session({"img-main": "Python 3.13.2", "img-pr": "Python 3.13.2"})
    assert daily_run._check_contree_pythons(sess, {}, tmp_path) is None


def test_patch_level_spec_is_enforced():
    sess, _ = _session({"img-main": "Python 3.12.1", "img-pr": "Python 3.12.1"})
    info = cs.side_pythons(sess, [">=3.12.4"])
    assert len(info["problems"]) == 2 and all("does not satisfy" in p for p in info["problems"])
    sess, _ = _session({"img-main": "Python 3.12.4", "img-pr": "Python 3.12.4"})
    assert cs.side_pythons(sess, [">=3.12.4"])["problems"] == []


def test_malformed_spec_cannot_pass(tmp_path):
    sess, _ = _session({"img-main": "Python 3.12.7", "img-pr": "Python 3.12.7"})
    info = cs.side_pythons(sess, [">=3.1o"])
    assert info["problems"] == ["requires-python could not be read: '>=3.1o'"]
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "x"\nrequires-python = ">=3.1o"\n')
    refusal = daily_run._check_contree_pythons(sess, {}, tmp_path)
    assert refusal and "requires-python could not be read" in refusal


def test_upper_bound_clause_is_kept():
    sess, _ = _session({"img-main": "Python 3.12.7", "img-pr": "Python 3.12.7"})
    assert cs.side_pythons(sess, [">=3.8,<4"])["problems"] == []
    sess, _ = _session({"img-main": "Python 4.0.0", "img-pr": "Python 4.0.0"})
    info = cs.side_pythons(sess, [">=3.8,<4"])
    assert len(info["problems"]) == 2


def test_missing_requires_python_is_recorded(tmp_path):
    sess, _ = _session({"img-main": "Python 3.12.7", "img-pr": "Python 3.12.7"})
    rec = {}
    assert daily_run._check_contree_pythons(sess, rec, tmp_path) is None
    assert rec["contree"]["python"]["requires_python_found"] is False
    assert rec["contree"]["python"]["requires_python"] == []


import pytest  # noqa: E402


@pytest.mark.parametrize("spec,version,ok", [
    ("==3.12.7", (3, 12, 7), True), ("==3.12.7", (3, 12, 8), False), ("==3.12", (3, 12, 0), True),
    ("!=3.12.7", (3, 12, 7), False), ("!=3.12.7", (3, 12, 8), True),
    (">=3.12.4", (3, 12, 4), True), (">=3.12.4", (3, 12, 1), False),
    ("<=3.12", (3, 12, 0), True), ("<=3.12", (3, 12, 1), False),
    (">3.12", (3, 12, 1), True), (">3.12", (3, 12, 0), False),
    ("<3.13", (3, 12, 9), True), ("<3.13", (3, 13, 0), False),
    ("~=3.12", (3, 14, 0), True), ("~=3.12", (4, 0, 0), False), ("~=3.12", (3, 11, 9), False),
    ("~=3.12.4", (3, 12, 9), True), ("~=3.12.4", (3, 13, 0), False), ("~=3.12.4", (3, 12, 3), False),
    ("==3.12.*", (3, 12, 5), True), ("==3.12.*", (3, 13, 0), False),
    ("!=3.12.*", (3, 12, 5), False), ("!=3.12.*", (3, 13, 0), True),
    (">=3.8,<4", (3, 12, 7), True), (">=3.8,<4", (4, 0, 0), False), (">=3.8, <4, !=3.9.*", (3, 9, 1), False),
])
def test_each_operator(spec, version, ok):
    clauses = cs.parse_requires_python(spec)
    assert clauses is not None
    assert cs.requires_python_ok(version, clauses) is ok


@pytest.mark.parametrize("spec", [">=3.1o", ">=3.8,", "3.12", "~=3", ">=3.*", "===3.12", ">=3.8,<4,junk", "^3.12"])
def test_unreadable_specs(spec):
    assert cs.parse_requires_python(spec) is None
