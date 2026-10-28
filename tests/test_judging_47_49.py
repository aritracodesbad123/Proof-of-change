"""Judging fixes 47, 48, 49 and how-it-works claims. Each fix has a test next to it showing a real bug still comes out
needs_attention."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "ops"))

import daily_run as dr  # noqa: E402

from poc import claim_hygiene, probe_adequacy, probes  # noqa: E402
from poc.verdict import FindingLabel  # noqa: E402

NA, VER = "needs_attention", "verified"
ADEQ = {"status": "measured", "changed_lines_total": 1, "changed_lines_covered": 1}


def _cmp():
    return dr.compare_sides({"main": [{"t::a": ("passed", "")}] * 3, "pr": [{"t::a": ("passed", "")}] * 3})


def _item(claims, main, pr, cov=ADEQ, source="model", pid="model-p"):
    it = {"id": pid, "source": source, "target": "t", "about": "a", "claims": claims,
          "runs": {"main": [main] * 3, "pr": [pr] * 3}, "probe_changed_line_coverage": dict(cov)}
    it = probes.rejudge_entry(it)
    it["probe_changed_line_coverage"] = probe_adequacy.assess(cov)
    return it


def _verdict(*items):
    pr = probes.apply_status(claim_hygiene.apply({"status": "ran", "items": list(items)}))
    return dr.verdict_for(_cmp(), None, probe_results=pr)


# ------------------------------------------------------------------ 47
def test_47_not_adequate_false_claim_does_not_flag():
    na = {"status": "measured", "changed_lines_total": 1, "changed_lines_covered": 0}
    it = _item([{"id": "C1", "covers": ["C1*"], "expect": "differs", "text": "x now differs"}],
               {"C1.v": 1}, {"C1.v": 1}, cov=na)
    v, reason, _ = _verdict(it)
    assert v != NA and "either way" in reason


def test_47_real_bug_on_an_adequate_probe_still_flags():
    it = _item([{"id": "C1", "covers": ["C1*"], "expect": "same", "text": "x stays the same"}],
               {"C1.v": 1}, {"C1.v": 2})
    assert _verdict(it)[0] == NA


# ------------------------------------------------------------------ 48
MAIN = "def f(v, d):\n    if d is None:\n        continue_ = 1\n\n    out = type(d)(v)\n    return out\n"
PR = MAIN.replace("\n\n    out", "\n    if isinstance(v, str):\n        v = [v]\n\n    out")


def test_48_insertion_after_blank_anchors_on_executable_lines():
    lines = probe_adequacy.main_side_lines(MAIN, PR, statement_start=True)
    text = MAIN.splitlines()
    assert lines and all(text[n - 1].strip() for n in lines)       # never the blank line
    assert 5 in lines                                               # the line the new code runs before


def test_48_probe_that_misses_the_function_is_still_not_adequate():
    lines = probe_adequacy.main_side_lines(MAIN, PR, statement_start=True)
    cov = probe_adequacy.measure({"m.py": lines}, {"m.py": {"executed_lines": [1], "missing_lines": [2, 3, 5, 6]}})
    assert cov["adequacy"] == probe_adequacy.NOT_ADEQUATE


# ------------------------------------------------------------------ 49
def test_49_id_cover_links_underscore_and_any_case():
    c = {"id": "C2", "covers": ["C2"], "expect": "differs", "text": "x"}
    assert claim_hygiene.linked_names(c, ["c2_a", "c2.b", "C2-c", "c20_a", "c2a"]) == ["c2_a", "c2.b", "C2-c"]


def test_49_difference_matching_no_cover_is_advisory_linked_by_id():
    it = _item([{"id": "C1", "covers": ["c1.ok"], "expect": "differs", "text": "param accepted"},
                {"id": "C2", "covers": ["c2.other"], "expect": "differs", "text": "colour set"}],
               {"c1.ok": 1, "c2.color_set": "TypeError"}, {"c1.ok": 2, "c2.color_set": True})
    obs = {o["name"]: o for o in it["observations"]}
    assert obs["c2.color_set"]["advisory"] and obs["c2.color_set"]["linked_by"] == "id"
    v, _, _ = _verdict(it)
    assert v not in (NA, VER)


def test_49_shared_word_or_other_id_form_still_flags():
    # A word shared with a claim's text, or a prefix like "claim1" next to claims "C1", is not a link.
    for name in ("flag_value", "claim1.result", "c9.x", "c10.x"):
        it = _item([{"id": "C1", "covers": ["C1"], "expect": "differs", "text": "the flag value is accepted"}],
                   {"C1.ok": 1, name: 1}, {"C1.ok": 2, name: 2})
        assert _verdict(it)[0] == NA, name


def test_49_real_bug_unclaimed_change_tied_to_no_claim_still_flags():
    it = _item([{"id": "C1", "covers": ["C1"], "expect": "differs", "text": "one"}],
               {"C1.x": 1, "other": 1}, {"C1.x": 2, "other": 2})
    assert _verdict(it)[0] == NA


# ------------------------------------------------------------------ how-it-works claims
HOW = {"id": "C2", "covers": ["C2*"], "expect": "differs",
       "text": "After the change, a string value is processed by `_as_list()` like values from config files."}


def test_how_claim_needs_no_difference():
    it = _item([HOW], {"C2.v": ["a"]}, {"C2.v": ["a"]})
    assert it["observations"][0]["label"] == FindingLabel.NOT_TESTABLE.value
    assert it["observations"][0]["how_claim"]
    assert _verdict(it)[0] != NA
    assert probes.unmatched_differs_claims({"items": [dict(it, observations=[], runs={})]}) in ([], ["C2"])


def test_behaviour_claim_showing_no_difference_still_flags():
    beh = {"id": "C1", "covers": ["C1*"], "expect": "differs",
           "text": "A string value is now parsed into its items instead of characters."}
    assert not probes.is_how_claim(beh)
    it = _item([beh], {"C1.v": ["a"]}, {"C1.v": ["a"]})
    assert _verdict(it)[0] == NA


def test_47_real_flag_from_a_probe_that_reaches_the_change_survives():
    # The probe ran the changed line (adequate): its unclaimed difference still raises attention.
    it = _item([{"id": "C1", "covers": ["C1*"], "expect": "differs", "text": "x"}],
               {"C1.v": 1, "other": 1}, {"C1.v": 2, "other": 2})
    from poc.probe_adequacy import deciding_items
    kept, _ = deciding_items([it])
    assert any(o["name"] == "other" for o in kept[0]["observations"])
    assert _verdict(it)[0] == NA


def test_no_evidence_any_changed_line_ran_caps_at_could_not_verify():
    # Shaped like click #3878: tests pass, coverage gate skipped, two model probes each ran 0 of 5 changed lines,
    # their only flags were the same exception on both sides.
    from evals.checks import derive_verdict
    na = {"status": "measured", "changed_lines_total": 5, "changed_lines_covered": 0}
    p1 = _item([{"id": "C1", "covers": ["C1.*"], "expect": "differs", "text": "echoes ^D"}],
               {"C1.stdout": {"raises": "AttributeError"}}, {"C1.stdout": {"raises": "AttributeError"}}, cov=na)
    p2 = _item([{"id": "C3", "covers": ["C3.*"], "expect": "differs", "text": "no longer passes the bytes"}],
               {"C3.len": {"raises": "AttributeError"}}, {"C3.len": {"raises": "AttributeError"}}, cov=na)
    rec = {"comparison": _cmp(), "baseline": "tests+probes", "reason": "",
           "coverage": {"status": "skipped", "why": "baseline tests+probes does not use the coverage gate"},
           "probes": {"status": "ran", "items": [p1, p2]}}
    assert derive_verdict(rec, "tests+probes") == "could_not_verify"
    live = dr.gate({**rec, "verdict": VER, "reason": "tests pass"})
    assert live["verdict"] == "could_not_verify"
    # the no-evidence rule on its own: probes that are not broken but ran 0 changed lines still cannot verify
    unbroken = {**rec, "verdict": VER, "reason": "tests pass",
                "probes": {"status": "ran", "items": [{**p1, "observations": [{"name": "C1.stdout", "state": "same"}]}]}}
    only = dr.no_evidence_gate(unbroken)
    assert only["verdict"] == "could_not_verify" and "no evidence any changed line ran" in only["reason"]
    # with the tests' coverage showing a changed line ran, the cap does not apply
    ran = {**rec, "coverage": {"status": "measured", "changed_lines_covered": 1, "changed_lines_total": 5}}
    assert dr.no_evidence_gate({**ran, "verdict": VER})["verdict"] == VER


def test_unclaimed_difference_shaped_like_a_proven_sibling_is_advisory():
    from poc import probes as pr
    spec = {"id": "model-p1", "source": "model",
            "claims": [{"id": "C1", "covers": ["c1.*"], "expect": "differs", "text": "accepts the new setting"},
                       {"id": "C3", "covers": ["c3.*"], "expect": "differs", "text": "setting can be false"}]}
    main = {"c1.accepted": "TypeError", "c2.set_true": "TypeError", "c3.set_false": "TypeError", "c9.other": 1}
    prs = {"c1.accepted": None, "c2.set_true": True, "c3.set_false": False, "c9.other": 2}
    obs = {o["name"]: o for o in pr.judge(spec, {"main": [main] * 3, "pr": [prs] * 3})}
    assert obs["c1.accepted"]["label"] == "proven"
    c2 = obs["c2.set_true"]
    assert c2["label"] == "unmentioned" and c2["advisory"] and c2["linked_by"] == "shape"
    assert c2["note"] == "probably the claimed change, check"
    # a real unclaimed change of another shape (value -> other value) still flags
    assert obs["c9.other"]["label"] == "unmentioned" and not obs["c9.other"].get("advisory")
    # without a proven sibling, the same difference is not advisory
    lone = {o["name"]: o for o in pr.judge({**spec, "claims": []},
                                           {"main": [main] * 3, "pr": [prs] * 3})}
    assert not lone["c2.set_true"].get("advisory")


def test_advisory_difference_alone_caps_at_could_not_verify():
    # Everything passes: tests clean, the probe is adequate and proves its claim. The only flag is an advisory
    # difference, linked by shape (c2) or by id (c1.extra). It must be could_not_verify, never verified.
    from evals.checks import derive_verdict
    claims = [{"id": "C1", "covers": ["c1.accepted"], "expect": "differs", "text": "accepts the new setting"}]
    shape = _item(claims, {"c1.accepted": "TypeError", "c2.set_true": "TypeError"},
                  {"c1.accepted": None, "c2.set_true": True})
    by_id = _item(claims, {"c1.accepted": "TypeError", "c1.extra": 1}, {"c1.accepted": None, "c1.extra": 2})
    for it, how in ((shape, "probably the claimed change, check"), (by_id, "linked by claim id, check")):
        adv = [o for o in it["observations"] if o.get("advisory")]
        assert len(adv) == 1 and all(o["label"] != "proven" for o in adv)
        rec = {"comparison": _cmp(), "baseline": "tests+probes", "reason": "",
               "coverage": {"status": "measured", "changed_lines_covered": 1, "changed_lines_total": 1},
               "probes": {"status": "ran", "items": [it]}}
        assert derive_verdict(rec, "tests+probes") == "could_not_verify"
        live = dr.gate({**rec, "verdict": VER, "reason": "tests pass"})
        assert live["verdict"] == "could_not_verify" and how in live["reason"]
        assert dr.advisory_gate({**rec, "verdict": "needs_attention"})["verdict"] == "needs_attention"


def test_combined_name_links_only_when_every_id_is_this_probes_claim():
    claims = [{"id": "C1", "covers": ["C1.ok"], "expect": "differs", "text": "one"},
              {"id": "C2", "covers": ["C2.ok"], "expect": "differs", "text": "two"}]
    for name in ("c1_c2.result", "probe1.c1_c2.result", "C1-C2.x"):
        it = _item(claims, {"C1.ok": 1, name: 1}, {"C1.ok": 2, name: 2}, pid="model-probe1")
        obs = {o["name"]: o for o in it["observations"]}
        assert obs[name].get("linked_by") == "id", name
        assert _verdict(it)[0] != NA, name
    for name in ("c1_c9.x", "c9_c1.x", "probe1.c1_c9.result", "c1_c2_c3.x"):
        it = _item(claims, {"C1.ok": 1, name: 1}, {"C1.ok": 2, name: 2}, pid="model-probe1")
        obs = {o["name"]: o for o in it["observations"]}
        assert not obs[name].get("advisory"), name
        assert _verdict(it)[0] == NA, name


def test_other_probes_name_prefix_is_not_skipped():
    claims = [{"id": "C1", "covers": ["C1.ok"], "expect": "differs", "text": "one"}]
    it = _item(claims, {"C1.ok": 1, "probe7.c1.x": 1}, {"C1.ok": 2, "probe7.c1.x": 2}, pid="model-probe1")
    assert _verdict(it)[0] == NA
