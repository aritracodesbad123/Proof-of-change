"""Behaviour-preservation claims (poc/behaviour_claims.py) and the verdict rule: a PR that claims results stay the
same cannot be 'verified' unless a probe checks that claim. Also: the report tells 'coverage not measured because the
record predates the gate' apart from a real measurement."""
import copy
import json
import shutil
from pathlib import Path

import pytest

from evals.checks import GOLDEN_PR_BATCH
from ops.daily_run import compare_sides, verdict_for
from poc import behaviour_claims as bc
from poc import coverage_gate, probes

GOLDEN = json.loads(GOLDEN_PR_BATCH.read_text().splitlines()[0])
FIX = Path(__file__).parent / "fixtures" / "probes" / "mlxtend-1229"


@pytest.mark.parametrize("text", [
    "For integer groups the results don't change for a given seed.",
    "Other output is unchanged.",
    "Existing values and ordinary coercion behavior remain unchanged.",
    "This keeps the same output as before.",
    "Predictions are identical to the previous implementation.",
    "The change is fully backwards compatible.",
    "No behaviour change; this only adds a docstring.",
    "No functional changes.",
    "Results will not change.",
    "No change in the results for existing users.",
])
def test_claims_found(text):
    assert bc.find("Some title", text), text


@pytest.mark.parametrize("text", [
    "This is not backwards compatible.",
    "This breaks backward compatibility for callers.",
    "## Backward compatibility\n\nA migration is needed.",
    "<!-- Please make sure results are unchanged -->\nFixes the dtype.",
    "```python\n# results are unchanged\n```\nFixes the dtype.",
    "Results now differ from the old version.",
    "BUG: fix nanquantile dtype for all-NaN first slice",
    "- [x] closes #123\n- [x] Tests added and passed\n- [x] Added an entry in the latest whatsnew file",
])
def test_not_claims(text):
    assert bc.find("A title", text) == [], bc.find("A title", text)


def test_claim_in_title_and_quote_is_the_whole_sentence():
    c = bc.find("MAINT: refactor loop, no behavior change", "Uses `rng.permutation(n)`. So the results don't change.")
    assert [x["source"] for x in c] == ["title", "PR description"]
    assert c[1]["quote"] == "So the results don't change."   # the dot in `rng.permutation` does not split it


def _cmp_verified():
    same = {"t::a": ("passed", ""), "t::b": ("passed", "")}
    return compare_sides({"main": [same] * 3, "pr": [same] * 3})


CLAIM = [{"source": "PR description", "quote": "Results are unchanged.", "pattern": "unchanged"}]


def _probe(claims, main, pr):
    spec = {"id": "p", "target": "o/r#1", "about": "x", "claims": claims}
    return {"status": "ran", "items": [probes.entry(spec, {"main": [main] * 3, "pr": [pr] * 3},
                                                    {"main": ["m"], "pr": ["p"]}, [], "library", None)]}


def test_unprobed_claim_blocks_verified():
    v, reason, fl = verdict_for(_cmp_verified(), None, claims=CLAIM)
    assert v == "could_not_verify"
    assert reason.startswith('unverified behaviour claim: "Results are unchanged."; needs a probe (')
    assert "unverified_claim" in fl
    assert verdict_for(_cmp_verified(), None)[0] == "verified"            # no claim: unchanged rule
    assert verdict_for(_cmp_verified(), None, claims=[])[0] == "verified"


def test_claim_never_upgrades_or_hides_other_verdicts():
    v, reason, _ = verdict_for(None, "source build failed", claims=CLAIM)
    assert (v, reason) == ("could_not_verify", "source build failed")
    flagged = _probe([], {"c": 1}, {"c": 2})
    assert verdict_for(_cmp_verified(), None, probe_results=flagged, claims=CLAIM)[0] == "needs_attention"


def test_a_probe_with_a_same_claim_decides():
    same = [{"id": "C1", "text": "results unchanged", "covers": ["r"], "expect": "same"}]
    assert verdict_for(_cmp_verified(), None, probe_results=_probe(same, {"r": 1}, {"r": 1}), claims=CLAIM)[0] == "verified"
    assert verdict_for(_cmp_verified(), None, probe_results=_probe(same, {"r": 1}, {"r": 2}),
                       claims=CLAIM)[0] == "needs_attention"                 # the probe contradicts the claim
    differs_only = [{"id": "C1", "text": "x changes", "covers": ["r"], "expect": "differs"}]
    assert verdict_for(_cmp_verified(), None, probe_results=_probe(differs_only, {"r": 1}, {"r": 2}),
                       claims=CLAIM)[0] == "could_not_verify"                # that probe does not check the claim


def test_mlxtend_1229_without_its_probe_is_not_verified():
    rec = GOLDEN
    assert rec["behaviour_claims"] and "for a given seed" in rec["behaviour_claims"][0]["quote"]
    v, reason, _ = verdict_for(rec["comparison"], None, rec["exit_check"], rec["files"], None, rec["behaviour_claims"])
    assert v == "could_not_verify" and reason.startswith("unverified behaviour claim:") and "needs a probe" in reason
    v, *_ = verdict_for(rec["comparison"], None, rec["exit_check"], rec["files"], rec["probes"], rec["behaviour_claims"])
    assert v == "needs_attention"                                            # with its probe: the probe decides
    unprobed = {k: x for k, x in rec.items() if k not in ("verdict_before_coverage_gate", "reason_before_coverage_gate")}
    assert coverage_gate.apply(dict(unprobed, verdict="could_not_verify"))["verdict"] == "could_not_verify"


# ---------------------------------------------------------------- coverage: not measured vs measured
def test_measurement_states():
    py = {"all": ["pkg/a.py"], "package_py": ["pkg/a.py"], "compiled": [], "other": []}
    assert coverage_gate.measurement({"files": py}) == "not measured: predates gate"
    assert coverage_gate.measurement({"files": py, "coverage": {"status": "failed", "why": "x"}}) == "not measured"
    assert coverage_gate.measurement({"files": py, "coverage": {"status": "measured"}}) == "measured"
    assert coverage_gate.measurement({"files": py, "coverage": {"status": "not needed"}}) == "not needed"


def _render(tmp_path, rec):
    from reports.pr_report import render_run
    d = tmp_path / "run" / "x-1"
    d.mkdir(parents=True)
    for f in FIX.glob("*.jsonl"):
        shutil.copy(f, d)
    (d / "record.json").write_text(json.dumps(rec))
    render_run(tmp_path / "run", tmp_path / "out", formats=("md",))
    return (tmp_path / "out" / "x-1" / "REPORT.md").read_text()


def test_report_distinguishes_predates_gate_from_measured(tmp_path):
    old = copy.deepcopy(GOLDEN)
    old.pop("coverage", None)
    for k in ("coverage_gate", "verdict_before_coverage_gate", "reason_before_coverage_gate"):
        old.pop(k, None)
    md = _render(tmp_path / "a", old)
    assert "**Coverage: NOT MEASURED, record predates the coverage gate.**" in md
    assert "Not a measurement: this record is older than the coverage gate" in md
    new = copy.deepcopy(old)
    new["coverage"] = {"status": "measured", "changed_lines_total": 12, "changed_lines_covered": 12, "seconds": 15.5,
                       "files": [{"file": "mlxtend/evaluate/feature_importance.py", "changed_lines_total": 12,
                                  "changed_lines_covered": 12}]}
    md = _render(tmp_path / "b", new)
    assert "**Coverage: MEASURED** by coverage.py on the PR side (15.5 s run)." in md
    assert "predates" not in md
