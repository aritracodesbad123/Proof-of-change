"""Benchmark harness: manifest schema, runner bookkeeping (no real check runs), metric maths and summary.

Every case here is a FIXTURE (tests/fixtures/bench_cases, "fixture": true), not a benchmark result.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from bench import manifest, run, summarize

FIX = Path(__file__).parent / "fixtures" / "bench_cases"


@pytest.fixture(autouse=True)
def _no_keys(monkeypatch):
    for k in run.SECRET_NAMES:
        monkeypatch.delenv(k, raising=False)


def cases():
    cs, problems = manifest.load_cases(FIX)
    assert not problems
    return {c["id"]: c for c in cs}


def test_fixture_cases_are_valid_and_marked():
    cs = cases()
    assert set(cs) == {"fx-safe", "fx-catch", "fx-miss"}
    assert all(c["fixture"] is True for c in cs.values())


@pytest.mark.parametrize("change, problem", [
    ({"repo": "numpy/numpy"}, "not in the benchmark repo list"),
    ({"head_sha": "abc"}, "head_sha must be a full"),
    ({"head_sha": "1" * 40}, "same commit"),
    ({"category": "nope"}, "category must be one of"),
    ({"expected_verdict": "verified"}, "expects verdict needs_attention"),
    ({"pr_url": "https://github.com/psf/requests/pull/1"}, "pr_url is not in repo"),
    ({"rationale": " "}, "rationale must be"),
    ({"patch": "x.txt"}, "patch must be"),
])
def test_schema_rejects(change, problem):
    c = dict(cases()["fx-catch"], **change)
    if "head_sha" in change and change["head_sha"] == "1" * 40:
        c["base_sha"] = "1" * 40
    assert any(problem in p for p in manifest.validate(c)), manifest.validate(c)


def test_schema_missing_field_and_duplicate_id(tmp_path):
    c = cases()["fx-safe"]
    assert manifest.validate({k: v for k, v in c.items() if k != "source"}) == ["missing field: source"]
    for n in ("a", "b"):
        (tmp_path / f"{n}.json").write_text(json.dumps(c))
    cs, problems = manifest.load_cases(tmp_path)
    assert len(cs) == 1 and any("duplicate id" in p for ps in problems.values() for p in ps)


def record(case, verdict, base=None, head=None, install_ok=True, ai_calls=0, usd=0.0):
    return {"id": "r", "verdict": verdict, "reason": "x", "sides": {"main_sha": base or case["base_sha"], "pr_sha": "f" * 40},
            "chosen": {"head_sha": head or case["head_sha"]}, "installed_commit": {"main": {"ok": install_ok}, "pr": {"ok": True}},
            "per_run": [{"passed": 3, "failed": 0}], "probes": {"status": "ran"},
            "cost": {"ai_calls": ai_calls, "cost_usd": usd}}


def fake_exec(rec, code=0, stderr=""):
    def execute(cmd, env, **kw):
        assert env["POC_REQUIRE_CONTREE"] == "1"
        assert cmd[cmd.index("--sandbox-backend") + 1] == "contree" and "--product-check" in cmd
        if rec is not None:
            ops, name = Path(cmd[cmd.index("--ops-dir") + 1]), cmd[cmd.index("--date") + 1]
            d = ops / "runs" / name / "toolz-1"
            d.mkdir(parents=True)
            (d / "record.json").write_text(json.dumps(rec))
        return type("P", (), {"returncode": code, "stderr": stderr})()
    return execute


def test_arms_differ_only_in_verdict_inputs(tmp_path):
    c = cases()["fx-safe"]
    a, b = (run.command(c, arm, tmp_path, "n") for arm in ("tests", "tests+probes"))
    strip = lambda cmd: [x for x in cmd if x not in ("tests", "tests+probes", "none", "nebius")]  # noqa: E731
    assert strip(a) == strip(b)
    assert "--swarm" in run.command(c, "tests+probes+swarm", tmp_path, "n")


def test_runner_records_a_run(tmp_path):
    c = cases()["fx-catch"]
    r = run.run_one(c, "tests+probes", tmp_path, fake_exec(record(c, "needs_attention", ai_calls=4, usd=0.01)))
    assert r["outcome"] == "ran" and r["verdict"] == "needs_attention" and r["model"]["ai_calls"] == 4
    assert r["stages"] == {"infra": "ok", "install": "ok", "tests": "ran", "probes": "ran"}
    assert json.loads((tmp_path / "tests_probes" / "fx-catch.json").read_text())["case_id"] == "fx-catch"


@pytest.mark.parametrize("rec_kw, code", [({"head": "9" * 40}, 0), ({"base": "9" * 40}, 0), (None, 3)])
def test_wrong_commits_or_no_record_is_not_run(tmp_path, rec_kw, code):
    c = cases()["fx-safe"]
    rec = None if rec_kw is None else record(c, "verified", **rec_kw)
    r = run.run_one(c, "tests", tmp_path, fake_exec(rec, code))
    assert r["outcome"] == "not_run" and r["verdict"] is None and r["not_run_why"]
    if rec is None:
        assert r["stages"]["infra"] == "failed"


def test_install_failure_stage_and_secret_redaction(tmp_path, monkeypatch):
    monkeypatch.setenv("NEBIUS_API_KEY", "sekrit-value-123")
    c = cases()["fx-safe"]
    r = run.run_one(c, "tests", tmp_path, fake_exec(record(c, "could_not_verify", install_ok=False), 0, "boom sekrit-value-123"))
    assert r["stages"]["install"] == "failed"
    assert "sekrit" not in json.dumps(r)


def test_runner_refuses_fixtures(tmp_path):
    assert run.main(["--cases", str(FIX), "--out", str(tmp_path)]) == 1
    assert not (tmp_path / "run_meta.json").exists()


def res(cid, cat, arm, verdict, outcome="ran", install="ok", secs=10.0, calls=None, usd=None):
    exp = manifest.EXPECTED_FOR[cat] or "verified"
    return {"schema": "poc-bench-result/1", "case_id": cid, "arm": arm, "fixture": True, "category": cat,
            "expected_verdict": exp, "outcome": outcome, "verdict": verdict if outcome == "ran" else None,
            "stages": {"install": install}, "wall_seconds": secs, "model": {"ai_calls": calls, "cost_usd": usd}}


def test_metric_maths():
    rs = [res("s1", "known_safe", "t", "verified"), res("s2", "known_safe", "t", "needs_attention"),
          res("c1", "known_regression_tests_catch", "t", "needs_attention", calls=2, usd=0.5),
          res("c2", "known_regression_tests_catch", "t", "verified"),
          res("m1", "known_regression_tests_miss", "t", "could_not_verify"),
          res("m2", "known_regression_tests_miss", "t", None, outcome="not_run", install="failed", secs=None)]
    m = summarize.arm_metrics(rs)
    assert m["wrong_approvals"] == {"count": 1, "n": 4, "rate": 0.25}
    assert m["bugs_caught"] == {"count": 1, "n": 4, "rate": 0.25}       # CNV and not-run are misses
    assert m["bugs_caught_tests_miss"] == {"count": 0, "n": 2, "rate": 0.0}
    assert m["false_alarms"] == {"count": 1, "n": 2, "rate": 0.5}
    assert m["verification_coverage"]["count"] == 4
    assert m["could_not_verify_or_not_run"]["count"] == 2 and m["not_run"] == 1 and m["could_not_verify"] == 1
    assert m["setup_failures"]["count"] == 1
    assert m["runtime_s"] == {"total": 50.0, "n": 5}
    assert m["model_calls"] == {"total": 2, "n_reported": 1} and m["cost_usd"]["total"] == 0.5


def test_empty_denominators_have_no_rate():
    m = summarize.arm_metrics([res("s1", "known_safe", "t", "verified")])
    assert m["bugs_caught"] == {"count": 0, "n": 0, "rate": None}


def test_uplift_and_summary_files(tmp_path):
    t = [res("m1", "known_regression_tests_miss", "tests", "verified"),
         res("c1", "known_regression_tests_catch", "tests", "needs_attention")]
    p = [res("m1", "known_regression_tests_miss", "tests+probes", "needs_attention"),
         res("c1", "known_regression_tests_catch", "tests+probes", "could_not_verify")]
    for arm, rs in (("tests", t), ("tests_probes", p)):
        (tmp_path / arm).mkdir()
        for r in rs:
            (tmp_path / arm / f"{r['case_id']}.json").write_text(json.dumps(r))
    assert summarize.main([str(tmp_path)]) == 0
    s = json.loads((tmp_path / "summary.json").read_text())
    assert s["probe_uplift"] == {"caught_by_probes_not_tests": ["m1"], "caught_by_tests_not_probes": ["c1"],
                                 "regression_cases_in_both_arms": 2}
    md = (tmp_path / "summary.md").read_text()
    assert "FIXTURE DATA" in md and "1 planted regression(s) caught by tests+probes but not by tests-only (m1)" in md
