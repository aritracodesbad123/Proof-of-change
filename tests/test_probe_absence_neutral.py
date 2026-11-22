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


def test_unbound_unchanged_claim_does_not_cancel_test_proof():
    cmp = _runs({"tests/test_mod.py::test_new": ("failed", ASSERTION),
                 "tests/test_mod.py::test_old": ("passed", "")},
                {"tests/test_mod.py::test_new": ("passed", ""),
                 "tests/test_mod.py::test_old": ("passed", "")})
    claims = [{"source": "body", "quote": "Existing results are left unchanged.", "pattern": "left unchanged"}]
    v, reason, _ = verdict_for(cmp, None, None, FILES, {"items": []}, claims, baseline="full")
    assert v == "verified"
    assert "unverified behaviour claim" not in reason
    other = [{"source": "body", "quote": "The change is backwards compatible.", "pattern": "backwards compatible"}]
    held, why, _ = verdict_for(cmp, None, None, FILES, {"items": []}, other, baseline="full")
    assert held == "could_not_verify" and "backwards compatible" in why


def test_reference_and_old_behaviour_claims_do_not_need_attention_on_their_own():
    ref = [{"id": "C1", "text": "the parser behaves like the standard formatter", "covers": ["r"], "expect": "same"}]
    item = _model(ref, {"r": "a"}, {"r": "b"})
    assert item["observations"][0]["label"] == FindingLabel.NOT_TESTABLE.value
    assert "PR side only" in item["observations"][0]["note"]
    old = [{"id": "C1", "text": "Previously the parser raised ValueError on a short offset.",
            "covers": ["r"], "expect": "same"}]
    judged = _model(old, {"r": "ValueError"}, {"r": "2020-01-02T03:04:05+05:00"})
    assert judged["observations"][0]["label"] == FindingLabel.NOT_TESTABLE.value
    assert "base side only" in judged["observations"][0]["note"]
    v, _, _ = verdict_for(_runs({"tests/test_mod.py::test_old": ("passed", "")},
                                {"tests/test_mod.py::test_old": ("passed", "")}),
                          None, None, FILES, {"items": [item, judged]}, baseline="full")
    assert v != "needs_attention"


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
