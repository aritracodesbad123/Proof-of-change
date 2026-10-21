"""Product checks carry their own --product-check flag, and compiled-only changes cannot be verified on them."""
from pathlib import Path
from types import SimpleNamespace

from ops import daily_run, request_worker
from poc import console_api, github_app, related_reports
from poc import coverage_gate as cg

PR = "https://github.com/acme/widgets/pull/4"
COMPILED = {"all": ["src/fast.c", "widget/_speed.pyx", "tests/test_speed.py", "tests/test_fast.py"], "package_py": [],
            "compiled": ["src/fast.c", "widget/_speed.pyx"], "other": []}


def _rec(**extra):
    return {"verdict": "verified", "reason": "2 new test(s) pass, 5 unchanged", "files": dict(COMPILED), **extra}


def test_compiled_only_change_is_capped_on_a_product_check():
    g = cg.apply(_rec(product_check=True))
    assert g["verdict"] == "could_not_verify"
    assert g["reason"].startswith(cg.PRODUCT_COMPILED_ONLY)
    assert "compiled code that coverage can't measure" in g["reason"]
    assert "src/fast.c" in g["reason"] and "widget/_speed.pyx" in g["reason"]


def test_compiled_only_change_is_unchanged_on_study_and_daily_records():
    assert cg.apply(_rec())["verdict"] == "verified"


def test_cap_applies_without_related_reports():
    assert daily_run.product_route(SimpleNamespace(pr=PR, bench=None, product_check=True, related_reports=False))
    assert daily_run.product_route(SimpleNamespace(pr=PR, bench=None, product_check=True))   # attribute absent


def test_related_reports_alone_is_not_a_product_check():
    assert not daily_run.product_route(SimpleNamespace(pr=PR, bench=None, related_reports=True))


def test_all_product_routes_set_the_flag():
    assert "--product-check" in console_api.console_daily_run_argv(PR, "none", [])
    assert "--product-check" in github_app.check_argv(PR, {})
    assert "--product-check" in request_worker.default_check_argv("python", Path("/r"), PR)
    assert "--product-check" in related_reports.product_flags()


def test_study_and_daily_never_set_the_flag():
    study = SimpleNamespace(pr=PR, bench="pairs.csv", product_check=True)
    daily = SimpleNamespace(pr=None, bench=None, product_check=True)
    assert not daily_run.product_route(study) and not daily_run.product_route(daily)
    root = Path(__file__).resolve().parents[1]
    for path in list((root / "ops").rglob("*")) + list((root / ".github").rglob("*")):
        if path.is_file() and path.suffix in {".py", ".sh", ".yml", ".yaml", ".json", ".toml"} \
                and path.name != "daily_run.py":
            text = path.read_text(errors="ignore")
            if "--bench" in text or "daily" in path.name:
                assert "--product-check" not in text, path


MIXED = {"all": ["src/fast.c", "widget/core.py", "tests/test_fast.py"], "package_py": ["widget/core.py"],
         "compiled": ["src/fast.c"], "other": []}
MEASURED = {"status": "measured", "changed_lines_total": 4, "changed_lines_covered": 4, "files": []}


def test_mixed_compiled_and_python_change_is_capped_on_a_product_check():
    rec = {"verdict": "verified", "reason": "r", "files": dict(MIXED), "coverage": dict(MEASURED)}
    assert cg.apply(rec)["verdict"] == "verified"            # study/daily: unchanged
    g = cg.apply({**rec, "product_check": True})
    assert g["verdict"] == "could_not_verify"
    assert g["reason"].startswith(cg.PRODUCT_COMPILED_ONLY) and "src/fast.c" in g["reason"]


def test_mixed_change_without_coverage_still_names_the_compiled_files():
    g = cg.apply({"verdict": "verified", "reason": "r", "files": dict(MIXED), "product_check": True})
    assert g["verdict"] == "could_not_verify" and "src/fast.c" in g["reason"]
