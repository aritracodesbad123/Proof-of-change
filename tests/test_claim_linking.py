"""Product-check fixes 41 to 43: claim ids link observations in code, unlinked probes are advisory only, and claim
quotes are grounded after removing Markdown marks. Fixtures are the probe sections of six records from the 27 Oct
run (tests/fixtures/claim_linking). Every test that touches the shared code also checks the study route."""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "ops"))

import daily_run as dr  # noqa: E402

from poc import claim_hygiene, model_probes, probes  # noqa: E402
from poc.verdict import FindingLabel  # noqa: E402

FX = ROOT / "tests/fixtures/claim_linking"
NA, CNV, VER = "needs_attention", "could_not_verify", "verified"


def _rec(name):
    return json.loads((FX / f"{name}.json").read_text())


def _cmp(fail=False):
    pr = ("failed", "boom") if fail else ("passed", "")
    return dr.compare_sides({"main": [{"t::a": ("passed", ""), "t::b": ("passed", "")}] * 3,
                             "pr": [{"t::a": pr, "t::b": ("passed", "")}] * 3})


def _product(name):
    """The fixture's probes through the product route, re-judged from their recorded runs first."""
    pr = copy.deepcopy(_rec(name)["probes"])
    pr["items"] = [probes.rejudge_entry(it) for it in pr["items"]]
    return probes.apply_status(claim_hygiene.apply(pr))


def _study(name):
    pr = copy.deepcopy(_rec(name)["probes"])
    pr["items"] = [probes.rejudge_entry(it) for it in pr["items"]]
    return probes.apply_status(pr)


def _labels(pr, item_id):
    it = next(i for i in pr["items"] if i["id"] == item_id)
    return {o["name"]: (o["label"], o.get("claim"), bool(o.get("advisory"))) for o in it["observations"]}


# ---- 41: a cover equal to the claim id links "<id>" and "<id>.*", ignoring case --------------------------------

def test_41_id_cover_links_prefixed_names_attrs_1647():
    pr = _product("attrs-1647")
    assert _labels(pr, "model-p1")["C1.leftover_count"] == (FindingLabel.PROVEN.value, "C1", False)
    assert _labels(pr, "model-p3")["C3.inner_string_count"] == (FindingLabel.PROVEN.value, "C3", False)
    assert all(it["status"] != "rejected" for it in pr["items"])
    fixed = {d["claim"] for d in pr["claim_hygiene"]["relinked"]}
    assert fixed == {"C1", "C2", "C3", "C4"}
    c1 = next(i for i in pr["items"] if i["id"] == "model-p1")["claims"][0]
    assert c1["covers_as_written"] == ["C1"]


def test_41_id_cover_is_case_insensitive_toolz_650():
    pr = _product("toolz-650")
    labels = _labels(pr, "model-probe-c1-reusable-nolen")
    assert {v[1] for v in labels.values()} == {"C1"}
    assert {v[0] for v in labels.values()} == {FindingLabel.PROVEN.value}


def test_41_star_cover_isort_2737_and_pytest_15265():
    pr = _product("isort-2737")
    labels = _labels(pr, "model-p1")
    assert labels["C1.output"][1] == "C1" and labels["C2.output"][1] == "C2"
    # "C3a.output" is not "C3" or "C3.<x>", and there is no C3 claim on this probe anyway
    assert labels["C3a.output"][1] is None
    # pytest: covers "C1*" / "C2*" but the observation is named after the behaviour, not the id: still unlinked
    pr = _product("pytest-15265")
    assert pr["items"][0]["status"] == "rejected"
    assert pr["claim_hygiene"]["relinked"] == []


def test_41_c1_never_links_c10():
    claim = {"id": "C1", "covers": ["C1"], "expect": "differs", "text": "x"}
    names = ["C1", "c1.a", "C10", "C10.a", "c11.b", "C1a.x"]
    assert claim_hygiene.linked_names(claim, names) == ["C1", "c1.a"]
    assert claim_hygiene.linked_names(dict(claim, covers=["c1*"]), names) == ["C1", "c1.a"]
    item = {"id": "model-p", "source": "model", "target": "t", "about": "a",
            "claims": [{"id": "C1", "covers": ["C1"], "expect": "differs", "text": "one"},
                       {"id": "C10", "covers": ["C10*"], "expect": "same", "text": "ten"}],
            "runs": {"main": [{"C1.x": 1, "C10.x": 5}] * 3, "pr": [{"C1.x": 2, "C10.x": 5}] * 3}}
    item = probes.rejudge_entry(item)
    out = claim_hygiene.apply({"items": [item]})
    got = {o["name"]: (o["claim"], o["label"]) for o in out["items"][0]["observations"]}
    assert got == {"C1.x": ("C1", FindingLabel.PROVEN.value), "C10.x": ("C10", FindingLabel.PROVEN.value)}
    # a C10 change is never counted for C1
    item["runs"]["pr"] = [{"C1.x": 1, "C10.x": 6}] * 3
    item["claims"][1]["expect"] = "same"
    out = claim_hygiene.apply({"items": [probes.rejudge_entry(item)]})
    got = {o["name"]: (o["claim"], o["label"]) for o in out["items"][0]["observations"]}
    assert got["C10.x"] == ("C10", FindingLabel.FALSE_CLAIM.value)
    assert got["C1.x"] == ("C1", FindingLabel.NEEDS_HUMAN.value)


def test_41_relinked_claim_must_still_hold():
    """Linking only says which claim an observation belongs to: an unmet claim still needs attention."""
    pr = _product("attrs-1647")
    assert _labels(pr, "model-p4")["C4.nested_astuple_eq_expected"][0] == FindingLabel.NEEDS_HUMAN.value
    assert dr.verdict_for(_cmp(), None, probe_results=pr)[0] == NA


def test_41_study_route_unchanged():
    for name in ("attrs-1647", "toolz-650", "isort-2737", "pytest-15265"):
        pr = _study(name)
        assert all(it["status"] == "rejected" for it in pr["items"] if it["source"] == "model" and it["claims"])
        assert probes._covers_name(["C1"], "c1.empty") is False   # shared matcher is untouched


# ---- 42: a rejected or unlinked probe is advisory only -----------------------------------------------------------

def test_42_unlinked_probe_is_advisory_pytest_like(monkeypatch):
    """With linking off, every one of today's rejected probes only gives advisory differences."""
    monkeypatch.setattr(claim_hygiene, "relink", lambda it: (it, []))
    for name in ("attrs-1647", "toolz-650", "isort-2737"):
        pr = _product(name)
        v, reason, _ = dr.verdict_for(_cmp(), None, probe_results=pr)
        assert v == CNV, (name, reason)
        assert pr["claim_hygiene"]["unlinked_probes"]


def test_42_claimless_and_unlinked_never_needs_attention_requests_urllib3():
    for name in ("requests-7520", "urllib3-5328"):
        pr = _product(name)
        assert dr.verdict_for(_cmp(), None, probe_results=pr)[0] == CNV
        assert _study(name)["summary"]["flagged"]   # study route still flags them


def test_42_advisory_never_verified_and_failing_tests_still_need_attention(monkeypatch):
    monkeypatch.setattr(claim_hygiene, "relink", lambda it: (it, []))
    pr = _product("toolz-650")
    assert dr.verdict_for(_cmp(), None, probe_results=pr)[0] != VER
    assert dr.verdict_for(_cmp(fail=True), None, probe_results=pr)[0] == NA


def test_42_linked_probe_still_flags_unclaimed_difference():
    item = {"id": "model-p", "source": "model", "target": "t", "about": "a",
            "claims": [{"id": "C1", "covers": ["C1"], "expect": "differs", "text": "one"}],
            "runs": {"main": [{"C1.x": 1, "other": 1}] * 3, "pr": [{"C1.x": 2, "other": 2}] * 3}}
    pr = probes.apply_status(claim_hygiene.apply({"items": [probes.rejudge_entry(item)]}))
    assert dr.verdict_for(_cmp(), None, probe_results=pr)[0] == NA


def test_41_42_today_records_combined():
    want = {"attrs-1647": NA, "toolz-650": VER, "isort-2737": VER, "pytest-15265": CNV,
            "requests-7520": CNV, "urllib3-5328": CNV}
    got = {n: dr.verdict_for(_cmp(), None, probe_results=_product(n))[0] for n in want}
    assert got == want


# ---- 43: claim quotes grounded after removing Markdown marks -----------------------------------------------------

def test_43_markdown_quotes_grounded_requests_7520():
    rec = _rec("requests-7520")
    body = (FX / "requests-7520-body.md").read_text()
    raw = {"claims": [{k: v for k, v in c.items() if k != "rejected"} for c in rec["model_rejected_claims"]]}
    title = "Keep Link header parameter values that contain '='"
    kept, _ = model_probes.grounded_claims(raw, title, body)
    assert kept == []                                   # study route: exact match, unchanged
    kept, rejected = model_probes.grounded_claims(raw, title, body, loose=True)
    assert {c["id"] for c in kept} == {"C1", "C2"}
    assert all(c["quote_match"] == "loose" for c in kept)
    assert [c["id"] for c in rejected] == ["C3"]        # reworded, not only unformatted: still rejected


def test_43_loose_rules():
    n = model_probes.loose_norm
    assert n("`a=b` **and** _x_") == n("a=b and x")
    assert n("a \u2014 b \u2192 c \u201cq\u201d \u2019s") == n('a - b -> c "q" \'s')
    raw = {"claims": [{"id": "C1", "expect": "differs", "source_quote": "foo now returns 2"}]}
    kept, _ = model_probes.grounded_claims(raw, "t", "foo now returns `3`", loose=True)
    assert kept == []                                   # different words are never matched
    kept, _ = model_probes.grounded_claims(raw, "t", "foo now returns 2", loose=True)
    assert "quote_match" not in kept[0]                 # exact matches are not marked loose


def test_43_generate_logs_loose_matches(tmp_path):
    body = "`param.split(\"=\")` keeps **every parameter**"

    class P:
        calls = []

        def describe(self):
            return "fake"

        def complete_json(self, kind, *a, **k):
            if kind == "claims":
                return {"claims": [{"id": "C1", "expect": "differs", "testable": False,
                                    "source_quote": 'param.split("=") keeps every parameter', "text": "x"}]}
            return {"probes": []}

    out = model_probes.generate(P(), "o/r", 1, "t", body, {}, tmp_path, [], tmp_path / "o", product=True)
    assert out["loose_quote_matches"] == [{"claim": "C1", "source_quote": 'param.split("=") keeps every parameter'}]
    out = model_probes.generate(P(), "o/r", 1, "t", body, {}, tmp_path, [], tmp_path / "o2", product=False)
    assert "loose_quote_matches" not in out and out["claims"] == []


# ---- 44 (fixed in 36): the repository's addopts are kept on product checks ---------------------------------------

def test_44_confirmed_by_36():
    rec = _rec("pytest-15265")
    assert rec["verdict_at_fcc3c08"] == CNV            # both sides failed to collect with the blanked addopts
    assert dr.repo_addopts_args(True) == [] and dr.repo_addopts_flag(True) == ""
    assert dr.repo_addopts_args(False) == ["-o", "addopts="]   # study route unchanged
