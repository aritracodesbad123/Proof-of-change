"""A missing or unusable AI probe does not demote a fix the tests already proved.

Synthetic fixtures. Nothing here names a repository in the rule under test. The held-out shapes
at the bottom match the records that must stay not verified: a real contradiction, a rename that
is not proof, and changed lines that coverage saw and that never ran.
"""
from ops.daily_run import compare_sides, fail_then_pass_ids, gate, verdict_for
from poc import probes
from poc.probe_inputs import inject_seeds, seeds_from_source
from poc.verdict import FindingLabel

FILES = {"all": ["pkg/mod.py", "tests/test_mod.py"]}
MEASURED = {"status": "measured", "changed_lines_total": 4, "changed_lines_covered": 3,
            "files": [{"file": "pkg/mod.py", "changed_lines_total": 4, "changed_lines_covered": 3}]}
UNCOVERED = {"status": "measured", "changed_lines_total": 4, "changed_lines_covered": 0,
             "files": [{"file": "pkg/mod.py", "changed_lines_total": 4, "changed_lines_covered": 0}]}
ASSERTION = "AssertionError: assert got == want"


def _runs(main, pr):
    return compare_sides({"main": [main] * 3, "pr": [pr] * 3})


def _record(cmp, coverage=None, items=None, claims=None):
    rec = {"verdict": "verified", "reason": "tests", "baseline": "full", "files": FILES,
           "comparison": cmp, "probes": {"items": items or []}}
    if coverage is not None:
        rec["coverage"] = coverage
    if claims is not None:
        rec["behaviour_claims"] = claims
    return rec


def _model(claims, main, pr, covered=2):
    spec = {"id": "model-1", "source": "model", "target": "o/r#1", "about": "x", "claims": claims}
    item = probes.entry(spec, {"main": [main] * 3, "pr": [pr] * 3}, {"main": ["m"], "pr": ["p"]}, [], "model", None)
    item["probe_changed_line_coverage"] = {
        "status": "measured", "changed_lines_total": 4, "changed_lines_covered": covered, "adequacy": "adequate"}
    return item


def test_missing_probe_does_not_demote_fail_then_pass():
    cmp = _runs({"tests/test_mod.py::test_new": ("failed", ASSERTION),
                 "tests/test_mod.py::test_old": ("passed", "")},
                {"tests/test_mod.py::test_new": ("passed", ""),
                 "tests/test_mod.py::test_old": ("passed", "")})
    assert fail_then_pass_ids(cmp, FILES) == ["tests/test_mod.py::test_new"]
    out = gate(_record(cmp, MEASURED))
    assert out["verdict"] == "verified"
    assert "no AI-written probe" not in out["reason"]


def test_new_tests_that_pass_on_the_base_are_not_proof():
    cmp = _runs({"tests/test_mod.py::test_new": ("passed", ""),
                 "tests/test_mod.py::test_old": ("passed", "")},
                {"tests/test_mod.py::test_new": ("passed", ""),
                 "tests/test_mod.py::test_old": ("passed", "")})
    cmp["base_new_tests"] = {"ids": ["tests/test_mod.py::test_new"],
                             "passed_on_base": ["tests/test_mod.py::test_new"],
                             "failed_on_base": [], "not_collected": []}
    assert fail_then_pass_ids(cmp, FILES) == []
    out = gate(_record(cmp, MEASURED))
    assert out["verdict"] == "could_not_verify"
    assert "no AI-written probe" in out["reason"]


def test_environment_and_collection_failures_are_not_proof():
    cmp = _runs({"tests/test_mod.py::test_new": ("failed", "ImportError: No module named 'helper'"),
                 "tests/test_mod.py::test_old": ("passed", "")},
                {"tests/test_mod.py::test_new": ("passed", ""),
                 "tests/test_mod.py::test_old": ("passed", "")})
    assert fail_then_pass_ids(cmp, FILES) == []
    collected = _runs({"tests/test_mod.py::test_new": ("error", "ERROR collecting tests/test_mod.py"),
                       "tests/test_mod.py::test_old": ("passed", "")},
                      {"tests/test_mod.py::test_new": ("passed", ""),
                       "tests/test_mod.py::test_old": ("passed", "")})
    assert fail_then_pass_ids(collected, FILES) == []
    assert gate(_record(cmp, MEASURED))["verdict"] == "could_not_verify"


def test_platform_skips_are_not_visible_and_not_proof():
    cmp = _runs({"tests/test_mod.py::test_new": ("failed", "Skipped: win32 only, not on this platform"),
                 "tests/test_mod.py::test_old": ("passed", "")},
                {"tests/test_mod.py::test_new": ("passed", ""),
                 "tests/test_mod.py::test_old": ("passed", "")})
    assert fail_then_pass_ids(cmp, FILES) == []
    assert gate(_record(cmp, MEASURED))["verdict"] == "could_not_verify"


def test_a_renamed_test_is_not_fail_then_pass_evidence():
    """A rename is not proof. boltons #758-style evidence must not become verified on the rename alone."""
    cmp = _runs({"tests/test_mod.py::test_old_name": ("passed", ""),
                 "tests/test_mod.py::test_new_name": ("failed", ASSERTION),
                 "tests/test_mod.py::test_kept": ("passed", "")},
                {"tests/test_mod.py::test_new_name": ("passed", ""),
                 "tests/test_mod.py::test_kept": ("passed", "")})
    assert "tests/test_mod.py::test_new_name" not in fail_then_pass_ids(cmp, FILES)
    assert gate(_record(cmp, MEASURED))["verdict"] == "could_not_verify"


def test_an_adequate_contradicting_probe_stays_not_verified():
    """Held-out shape of boltons #751 and #758: tests look like proof, but an adequate probe shows a real break."""
    cmp = _runs({"tests/test_mod.py::test_new": ("failed", ASSERTION),
                 "tests/test_mod.py::test_old": ("passed", "")},
                {"tests/test_mod.py::test_new": ("passed", ""),
                 "tests/test_mod.py::test_old": ("passed", "")})
    claims = [{"id": "C1", "text": "existing offsets stay the same", "covers": ["r"], "expect": "same"}]
    item = _model(claims, {"r": "offset-00"}, {"r": "offset-05"})
    v, reason, _ = verdict_for(cmp, None, None, FILES, {"items": [item]}, baseline="full")
    assert v == "needs_attention"
    assert "does not" in reason or "differs" in reason
    rec = _record(cmp, MEASURED, [item])
    rec["verdict"], rec["reason"] = v, reason
    assert gate(rec)["verdict"] == "needs_attention"


def test_uncovered_changed_lines_stay_could_not_verify():
    """Held-out shape of sqlparse #669: tests look like proof, and only uncovered changed lines keep it unverified."""
    cmp = _runs({"tests/test_mod.py::test_new": ("failed", ASSERTION),
                 "tests/test_mod.py::test_old": ("passed", "")},
                {"tests/test_mod.py::test_new": ("passed", ""),
                 "tests/test_mod.py::test_old": ("passed", "")})
    out = gate(_record(cmp, UNCOVERED))
    assert out["verdict"] == "could_not_verify"
    assert "changed code never ran" in out["reason"]


def test_every_input_raising_is_not_unchanged_or_adequate():
    claims = [{"id": "C1", "text": "the result stays the same", "covers": ["r"], "expect": "same"}]
    item = _model(claims, {"r": {"raises": "TypeError"}}, {"r": {"raises": "TypeError"}}, covered=2)
    (obs,) = item["observations"]
    assert obs["label"] == FindingLabel.NOT_TESTABLE.value
    assert obs["label"] != FindingLabel.NO_DIFFERENCE.value
    assert obs["label"] != FindingLabel.PROVEN.value
    assert "not unchanged" in obs["probe_broken"]
    classified = probes.classify_item(item)
    assert classified["status"] == "uninformative"
    assert classified["probe_changed_line_coverage"]["adequacy"] == "not_adequate"
    assert classified["probe_changed_line_coverage"]["changed_lines_covered"] == 0


def test_raises_do_not_hide_a_real_regression():
    """Held-out shape of boltons #751/#758: an all-raise probe is not 'unchanged' and does not hide a regression."""
    cmp = _runs({"tests/test_mod.py::test_new": ("failed", ASSERTION),
                 "tests/test_mod.py::test_old": ("passed", "")},
                {"tests/test_mod.py::test_new": ("passed", ""),
                 "tests/test_mod.py::test_old": ("failed", "AssertionError: round trip broke")})
    dead = _model([{"id": "C1", "text": "hour offsets change", "covers": ["r"], "expect": "differs"}],
                  {"r": {"raises": "ValueError"}}, {"r": {"raises": "ValueError"}})
    v, _, _ = verdict_for(cmp, None, None, FILES, {"items": [dead]}, baseline="full")
    assert v == "needs_attention"


def test_97_same_as_claim_is_checked_on_the_pr_side_only():
    """Fix 97: 'same as' / 'behaves like' is not a base-versus-PR finding and never needs attention alone."""
    for text in ("the result is the same as the standard formatter",
                 "the parser behaves like the standard formatter"):
        claims = [{"id": "C1", "text": text, "covers": ["r"], "expect": "same"}]
        item = _model(claims, {"r": "base-value"}, {"r": "pr-value"})
        obs = item["observations"][0]
        assert obs["label"] == FindingLabel.NOT_TESTABLE.value
        assert obs["label"] not in (FindingLabel.FALSE_CLAIM.value, FindingLabel.NEEDS_HUMAN.value)
        assert "PR side only" in obs["note"]
        v, _, _ = verdict_for(_runs({"tests/test_mod.py::test_old": ("passed", "")},
                                    {"tests/test_mod.py::test_old": ("passed", "")}),
                              None, None, FILES, {"items": [item]}, baseline="full")
        assert v != "needs_attention"


def test_75_old_behaviour_claim_is_never_typed_same():
    """Fix 75: a claim that only describes the base is not typed 'same' and is checked on the base side only."""
    from poc import claim_hygiene
    text = "Previously the parser raised ValueError on a short offset."
    assert probes.describes_old_behaviour({"text": text})
    kept = claim_hygiene.apply({"items": [{
        "id": "model-1", "source": "model", "target": "o/r#1", "about": "old behaviour",
        "claims": [{"id": "C1", "text": text, "covers": ["r"], "expect": "differs"}],
        "runs": {"main": [{"r": "ValueError"}] * 3, "pr": [{"r": "offset"}] * 3},
        "observations": []}]})
    claim = kept["items"][0]["claims"][0]
    assert claim["expect"] != "same"
    assert "retyped_same" not in (kept.get("claim_hygiene") or {}) or not kept["claim_hygiene"].get("retyped_same")
    judged = _model([{"id": "C1", "text": text, "covers": ["r"], "expect": "same"}],
                    {"r": "ValueError"}, {"r": "short-offset"})
    obs = judged["observations"][0]
    assert obs["label"] == FindingLabel.NOT_TESTABLE.value
    assert obs["label"] != FindingLabel.PROVEN.value
    assert "base side only" in obs["note"]
    v, _, _ = verdict_for(_runs({"tests/test_mod.py::test_old": ("passed", "")},
                                {"tests/test_mod.py::test_old": ("passed", "")}),
                          None, None, FILES, {"items": [judged]}, baseline="full")
    assert v != "needs_attention"


def test_113_unbound_unchanged_claim_does_not_cancel_fail_then_pass():
    """Fix 113: an unbound untouched/unchanged claim does not cancel fail-then-pass proof."""
    cmp = _runs({"tests/test_mod.py::test_new": ("failed", ASSERTION),
                 "tests/test_mod.py::test_old": ("passed", "")},
                {"tests/test_mod.py::test_new": ("passed", ""),
                 "tests/test_mod.py::test_old": ("passed", "")})
    assert fail_then_pass_ids(cmp, FILES) == ["tests/test_mod.py::test_new"]
    claims = [{"source": "body", "quote": "Existing results are left unchanged.", "pattern": "left unchanged"}]
    v, reason, _ = verdict_for(cmp, None, None, FILES, {"items": []}, claims, baseline="full")
    assert v == "verified"
    assert "unverified behaviour claim" not in reason
    contradicted = _model(
        [{"id": "C1", "text": "existing results stay unchanged", "covers": ["r"], "expect": "same"}],
        {"r": "old"}, {"r": "new"})
    blocked, why, _ = verdict_for(cmp, None, None, FILES, {"items": [contradicted]}, claims, baseline="full")
    assert blocked == "needs_attention"
    assert "differs although the claim says it does not" in why
    other = [{"source": "body", "quote": "The change is backwards compatible.", "pattern": "backwards compatible"}]
    held, why, _ = verdict_for(cmp, None, None, FILES, {"items": []}, other, baseline="full")
    assert held == "could_not_verify" and "backwards compatible" in why


def test_tests_only_verified_says_so_and_a_probe_keeps_the_old_wording(tmp_path, monkeypatch):
    """A verified result with only fail-then-pass tests says so. An adequate probe keeps the old sentence."""
    monkeypatch.setattr("reports.reviewer.latest_replay", lambda: None)
    from ops.daily_run import TESTS_ONLY_NOTE, combined_run_summary_md
    from reports.pr_report import build
    from reports.reviewer import to_html, to_pdf, write_summary

    old = "The PR's tests behave the same or better than on main"
    common = {
        "repo": "acme/widget", "library": "widget", "pr": 7, "title": "Fix the widget",
        "url": "https://github.com/acme/widget/pull/7", "head_sha": "a" * 40, "route": "source-pair",
        "tested_at_ist": "2026-01-01 12:00 IST", "verdict": "verified",
        "reason": "1 test(s) fail on main and pass on the PR", "baseline": "full",
        "runs_per_side": 3, "posted_upstream": False,
        "machine_type": {"label": "test", "arch": "x86_64", "cpu_count": 4},
        "thread_env": {k: "1" for k in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
                                        "NUMEXPR_NUM_THREADS")},
        "per_run": [{"side": s, "run": i, "exit": 0} for i in (1, 2, 3) for s in ("main", "pr")],
        "files": {"all": ["pkg/mod.py", "tests/test_mod.py"], "package_py": ["pkg/mod.py"],
                  "compiled": [], "other": []},
        "comparison": {"same": 1, "new_tests_passing": 0,
                       "fixed": ["tests/test_mod.py::test_new"],
                       "base_messages": {"tests/test_mod.py::test_new": "AssertionError: assert got == want"},
                       "regressions": [], "new_tests_failing": [], "flaky": []},
    }
    adequate = {"id": "model-1", "source": "model", "status": "ran", "observations": [],
                "probe_changed_line_coverage": {"status": "measured", "changed_lines_total": 2,
                                                "changed_lines_covered": 2, "adequacy": "adequate"}}
    backed = {**common, "pr": 8, "title": "Fix the widget, probed",
              "probes": {"status": "ran", "items": [adequate]}}
    cases = (("tests-only", dict(common), True),
             ("probe-backed", backed, False))
    rows = []
    for name, rec, tests_only in cases:
        report, row = build(rec, tmp_path / name, tmp_path / "out" / name)
        assert row["verdict"] == "VERIFIED"
        assert rec["verdict"] == "verified"
        banner = next(block for block in report.blocks if block[0] == "banner")
        blob = "\n".join(str(part) for part in report.blocks)
        if tests_only:
            assert TESTS_ONLY_NOTE in banner[4]
            assert TESTS_ONLY_NOTE in blob
            assert old not in banner[4]
        else:
            assert TESTS_ONLY_NOTE not in blob
            assert old in banner[4]
        rows.append(row)
    out = tmp_path / "summary"
    write_summary(rows, str(out), "Proof-of-Change daily summary", ("md", "html", "pdf"))
    summary = (out / "SUMMARY.md").read_text()
    tests_lines = [line for line in summary.splitlines() if "widget#7" in line]
    probe_lines = [line for line in summary.splitlines() if "widget#8" in line]
    assert tests_lines and all(TESTS_ONLY_NOTE in line for line in tests_lines)
    assert probe_lines and all(TESTS_ONLY_NOTE not in line for line in probe_lines)
    folder = combined_run_summary_md(
        [{**common, "_pr_id": "widget-7"}, {**backed, "_pr_id": "widget-8"}],
        "go/no-go")
    assert folder.count(TESTS_ONLY_NOTE) == 1
    html = out / "one.html"
    pdf = out / "one.pdf"
    html.write_text(to_html(build(dict(common), tmp_path / "pdf", out)[0], "report"))
    assert to_pdf(str(html), str(pdf)) is None
    from tests.test_relaxed_class_cross_run import _pdf_strings
    assert TESTS_ONLY_NOTE in _pdf_strings(pdf)


def test_formatter_round_trip_and_literal_args_are_seeded():
    source = (
        "def isoparse(text):\n"
        "    return text\n"
        "def check():\n"
        "    isoparse('2020-01-02T03:04:05Z')\n"
        "    isoparse(date.isoformat())\n"
        "    stamp.strftime('%Y-%m-%d')\n"
    )
    found = seeds_from_source(source)
    assert "2020-01-02T03:04:05Z" in found["literals"]
    assert any("isoformat" in trip for trip in found["round_trips"])
    assert any(value.startswith("2020-01-02T03:04:05") for value in found["round_trip_values"])
    assert any(value == "2020-01-02" for value in found["round_trip_values"])
    code = "CASES = {'plain': 'abc'}\n"
    seeded, added = inject_seeds(code, found["literals"] + found["round_trip_values"])
    assert added
    assert "2020-01-02T03:04:05Z" in seeded
    assert "seed0" in seeded
