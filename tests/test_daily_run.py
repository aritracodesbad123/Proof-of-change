import importlib.util
from pathlib import Path

ROOT = Path(__file__).parent.parent
spec = importlib.util.spec_from_file_location("daily_run", ROOT / "ops" / "daily_run.py")
dr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dr)

PICKS = """# picks
## 1. demo
- **Repo:** https://github.com/acme/widget (default branch `main`)
- **Open PR:** #12, "Fix thing"
  - Head SHA: `0123456789abcdef0123456789abcdef01234567`
**Expected Proof-of-Change verdict: `needs attention` (low severity)**
- Install: `pip install -e ".[x]" pytest hypothesis`
- Test (subset, fast): `pytest tests/test_a.py tests/test_b.py -n 4 -k "not slow"`
"""


def test_parse_picks_has_no_expectations(tmp_path):
    p = tmp_path / "p.md"; p.write_text(PICKS)
    picks = dr.parse_picks(p)
    pk = picks["acme/widget"][0]
    assert pk["pr"] == 12 and pk["head_sha"].startswith("0123")
    assert "expected" not in str(pk).lower()  # expectations are never part of the test inputs
    assert dr.pick_test_targets(pk) == ["tests/test_a.py", "tests/test_b.py"]
    assert dr.side_install_args(pk, Path("/c")) == (["-e", "/c[x]"], ["pytest", "hypothesis"])
    assert dr.read_expectations(p) == {("acme/widget", 12): "needs_attention"}


def test_score_expectation():
    assert dr.score_expectation("needs_attention", "verified") == "miss"
    assert dr.score_expectation("verified", "needs_attention") == "false alarm"
    assert dr.score_expectation("verified", "verified") == "match"
    assert dr.score_expectation("verified", "could_not_verify").startswith("not scored")


def test_classify_and_package_diff():
    fc = dr.classify_files(["numpy/lib/_x.py", "numpy/_core/src/a.c", "doc/x.rst", "pyproject.toml"], "numpy")
    assert fc["package_py"] == ["numpy/lib/_x.py"] and "numpy/_core/src/a.c" in fc["compiled"]
    diff = ("diff --git a/doc/x.rst b/doc/x.rst\n--- a\n+++ b\n"
            "diff --git a/numpy/lib/_x.py b/numpy/lib/_x.py\n--- a/numpy/lib/_x.py\n+++ b/numpy/lib/_x.py\n")
    assert dr.package_diff(diff, "numpy").startswith("diff --git a/numpy/lib/_x.py")
    assert dr.diff_files(diff) == ["doc/x.rst", "numpy/lib/_x.py"]


def test_compare_and_verdict():
    m = [{"t::a": ("passed", ""), "t::b": ("failed", "E"), "t::c": ("passed", "")}] * 3
    p = [{"t::a": ("failed", "boom"), "t::b": ("passed", ""), "t::c": ("passed", ""), "t::d": ("passed", "")}] * 3
    c = dr.compare_sides({"main": m, "pr": p})
    assert c["regressions"] == ["t::a"] and c["fixed"] == ["t::b"] and c["new_tests_passing"] == 1 and c["same"] == 1
    v, reason, _ = dr.verdict_for(c, None)
    assert v == "needs_attention" and "pass on main but fail on the PR" in reason
    ok = dr.compare_sides({"main": [{"t::c": ("passed", "")}] * 3, "pr": [{"t::c": ("passed", "")}] * 3})
    assert dr.verdict_for(ok, None)[0] == "verified"
    assert dr.verdict_for(None, "build failed")[0] == "could_not_verify"


def test_parse_junit_ids_are_side_independent(tmp_path):
    from ops.daily_run import parse_junit
    for side in ("main", "pr"):
        (tmp_path / f"{side}.xml").write_text(
            f'<testsuite><testcase classname="ops.work.x.venv-{side}.lib.python3.12.site-packages.numpy.tests.T" name="t"/></testsuite>')
    assert parse_junit(tmp_path / "main.xml") == parse_junit(tmp_path / "pr.xml")


def test_same_day_rerun_ignores_own_state():
    from ops.daily_run import baseline_for
    seen = {"last_run_utc": {"a/b": "2026-10-10T00:25:57Z"}, "prs": {"a/b": {"1": {"run": "2026-10-10"}, "2": {"run": "2026-10-09"}}}}
    prs, since = baseline_for(seen, "a/b", "2026-10-10")
    assert since is None and list(prs["a/b"]) == ["2"]
    prs, since = baseline_for(seen, "a/b", "2026-10-11")
    assert since == "2026-10-10T00:25:57Z" and set(prs["a/b"]) == {"1", "2"}
