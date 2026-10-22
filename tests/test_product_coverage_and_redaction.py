"""Product checks need measured coverage for 'verified'; Contree-only records say why coverage is missing; project IDs
are redacted; refused steps carry an explicit flag."""
from types import SimpleNamespace

from ops import daily_run
from poc import console_api
from poc import coverage_gate as cg

FILES = {"all": ["widget/core.py", "docs/index.rst"], "package_py": ["widget/core.py"], "compiled": [], "other": []}


def _rec(**extra):
    return {"verdict": "verified", "reason": "0 new test(s) pass, 5 unchanged", "files": dict(FILES), **extra}


def test_contree_only_record_reports_why_coverage_was_not_run():
    rec = _rec(coverage={"status": "not measured", "why": daily_run.CONTREE_ONLY_COVERAGE_WHY})
    note = cg.apply(rec)["coverage_gate"]["note"]
    assert daily_run.CONTREE_ONLY_COVERAGE_WHY in note
    assert "predates the coverage gate" not in note


def test_product_check_without_measured_coverage_is_capped():
    rec = _rec(product_check=True, coverage={"status": "not measured", "why": daily_run.CONTREE_ONLY_COVERAGE_WHY})
    g = cg.apply(rec)
    assert g["verdict"] == "could_not_verify"
    assert g["reason"].startswith("Coverage wasn't measured, so this can't be marked verified")
    assert cg.apply(_rec(product_check=True))["verdict"] == "could_not_verify"   # no coverage run at all


def test_product_check_with_measured_coverage_stays_verified():
    rec = _rec(product_check=True, coverage={"status": "measured", "changed_lines_total": 4,
                                             "changed_lines_covered": 4, "files": []})
    assert cg.apply(rec)["verdict"] == "verified"


def test_study_path_is_unaffected_by_the_product_cap():
    rec = _rec(coverage={"status": "not measured", "why": "x"})
    assert cg.apply(rec)["verdict"] == "verified"
    study = SimpleNamespace(bench="pairs.csv", pr="https://github.com/o/r/pull/1", product_check=True)
    daily_sweep = SimpleNamespace(bench=None, pr=None, product_check=True)
    product = SimpleNamespace(bench=None, pr="https://github.com/o/r/pull/1", product_check=True)
    assert not daily_run.product_route(study) and not daily_run.product_route(daily_sweep)
    assert daily_run.product_route(product)


def test_project_ids_are_redacted(monkeypatch):
    monkeypatch.setattr(console_api.session_key, "get_key", lambda *_: None)
    monkeypatch.setattr(console_api.session_key, "get_tavily_key", lambda *_: None)
    base = {"PATH": "/usr/bin", "NEBIUS_PROJECT_ID": "proj-nebius-1234", "CONTREE_PROJECT_ID": "proj-contree-5678"}
    _env, secrets = console_api.child_environment(base, "nebius", None)
    assert "proj-nebius-1234" in secrets and "proj-contree-5678" in secrets


def test_refused_step_has_an_explicit_flag(tmp_path):
    daily_run.set_contree_only(True)
    try:
        rc, _ = daily_run.run(["true"], tmp_path / "l", env={"PATH": "/usr/bin"},
                              sbx=daily_run.side_sandbox(tmp_path / "venv-pr"))
        cp = daily_run.in_side(tmp_path / "venv-pr", ["true"])
    finally:
        daily_run.set_contree_only(False)
    assert isinstance(rc, int) and rc != 0 and daily_run.is_refused(rc)
    assert cp.refused is True and cp.returncode != 0
    assert not daily_run.is_refused(0) and not daily_run.is_refused(126)
