"""A sentence that describes the pre-PR behaviour is not a promise that nothing changes.

Faithful claim text from sqlparse #934 and prettytable #557, plus a broken "unaffected" promise that must
still flag. No repository name is special-cased.
"""
from ops import daily_run
from poc import claim_hygiene, model_probes, probes
from poc.model_provider import CLAIMS_PROMPT, CLAIMS_SCHEMA

# sqlparse #934, the sentence the pull request uses to describe the bug.
SQLPARSE_C1 = ("StripWhitespaceFilter changes whitespace token values but leaves their cached "
               "`normalized` values unchanged.")
# prettytable #557, the two sentences that describe the bug.
PRETTY_C1 = ("When only some columns are printed with `fields=`, the title and `min_table_width` "
             "are still sized from all columns:")
PRETTY_C2 = ('With `min_table_width=30` and `fields=["a", "c"]`, the table also comes out narrower '
             "than 30 because the hidden column is counted.")
PRETTY_C3 = ("_compute_widths (title / `min_table_width` block) and `_stringify_title` summed over "
             "every column, while the hrule, header and row code already skip columns that are not in `fields`.")
RETURNED_BEFORE = "the helper returned [] before"
UNAFFECTED = "Other inputs are unaffected."
PRESERVED = "Existing behaviour for the other callers is preserved."


def _judged(text, main, pr, expect="same"):
    claims = [{"id": "C1", "text": text, "covers": ["r"], "expect": expect}]
    spec = {"id": "model-p1", "source": "model", "target": "acme/widget#1", "about": "check", "claims": claims}
    runs = {"main": [{"r": main}] * 3, "pr": [{"r": pr}] * 3}
    return {"id": spec["id"], "source": "model", "target": spec["target"], "about": spec["about"],
            "claims": claims, "runs": runs, "observations": probes.judge(spec, runs)}


def _cmp(main, pr):
    return daily_run.compare_sides({"main": [dict(main)] * 3, "pr": [dict(pr)] * 3})


def test_prompt_and_schema_reject_same_for_old_behaviour():
    expect = CLAIMS_SCHEMA["properties"]["claims"]["items"]["properties"]["expect"]
    assert expect["enum"] == ["same", "differs", "base"]
    assert "base" in CLAIMS_PROMPT and "never" in CLAIMS_PROMPT.lower()
    assert "unaffected" in CLAIMS_PROMPT and "preserved" in CLAIMS_PROMPT


def test_sqlparse_934_and_prettytable_557_are_not_same_promises():
    """The bug sentences are not typed same, and a difference is not a broken promise."""
    for text in (SQLPARSE_C1, PRETTY_C1, PRETTY_C2, PRETTY_C3, RETURNED_BEFORE):
        assert claim_hygiene.describes_old_bug(text), text
        assert not claim_hygiene.says_stays_same(text), text
        item = _judged(text, "old", "new")
        obs = item["observations"][0]
        assert obs["label"] != probes.FindingLabel.FALSE_CLAIM.value, text
        assert obs["label"] != probes.FindingLabel.PROVEN.value, text
        assert obs.get("base_description") is True
        assert not probes.summarize([item])["flagged"], text
        fixed = claim_hygiene.correct_extracted_claim(
            {"id": "C1", "text": text, "source_quote": text, "testable": True, "expect": "same"})
        assert fixed["expect"] == "base" and fixed["testable"] is False and fixed["base_description"] is True


def test_extracted_bug_sentence_is_rewritten_before_probes():
    body = SQLPARSE_C1 + "\n\nUpdate `normalized` when this filter changes the whitespace value."
    raw = {"claims": [{"id": "C1", "text": SQLPARSE_C1, "source_quote": SQLPARSE_C1,
                       "testable": True, "expect": "same"},
                      {"id": "C2", "text": "Update normalized when this filter changes the whitespace value.",
                       "source_quote": "Update `normalized` when this filter changes the whitespace value.",
                       "testable": True, "expect": "differs"}]}
    kept, rejected = model_probes.grounded_claims(raw, "Keep normalized whitespace in sync", body, loose=True)
    by_id = {c["id"]: c for c in kept}
    assert not rejected
    assert by_id["C1"]["expect"] == "base" and by_id["C1"]["testable"] is False
    assert by_id["C2"]["expect"] == "differs" and by_id["C2"]["testable"] is True


def test_broken_unaffected_promise_still_flags():
    """A real no-change promise that the pull request breaks still needs attention."""
    for text in (UNAFFECTED, PRESERVED, "output is unchanged", "continues to work as before"):
        assert not claim_hygiene.describes_old_bug(text), text
        assert claim_hygiene.says_stays_same(text), text
        item = _judged(text, "kept", "changed")
        obs = item["observations"][0]
        assert obs["label"] == probes.FindingLabel.FALSE_CLAIM.value, text
        assert not obs.get("base_description")
        assert probes.summarize([item])["flagged"]
        kept = claim_hygiene.correct_extracted_claim(
            {"id": "C1", "text": text, "source_quote": text, "testable": True, "expect": "same"})
        assert kept["expect"] == "same" and kept["testable"] is True
    cmp = _cmp({"m.t::old": ("passed", "")}, {"m.t::old": ("passed", "")})
    promise = _judged(UNAFFECTED, "kept", "changed")
    v, reason, _ = daily_run.verdict_for(cmp, None, None, None, {"items": [promise]}, baseline="full")
    assert v == "needs_attention"
    assert "although the claim says it does not" in reason
    # The same tests, with only the bug sentence, follow the tests' own verdict. This rule does not pick one.
    bug = _judged(SQLPARSE_C1, "stale", "updated")
    tests_only = daily_run.tests_verdict(cmp, None)[0]
    got, why, _ = daily_run.verdict_for(cmp, None, None, None, {"items": [bug]}, baseline="full")
    assert got == tests_only
    assert "although the claim says it does not" not in why


def test_a_real_test_regression_still_needs_attention():
    cmp = _cmp({"m.t::old": ("passed", "")}, {"m.t::old": ("failed", "AssertionError: broke")})
    bug = _judged(PRETTY_C1, "wide", "narrow")
    v, reason, _ = daily_run.verdict_for(cmp, None, None, None, {"items": [bug]}, baseline="full")
    assert v == "needs_attention"
    assert "fail on the PR" in reason


def test_hygiene_records_the_base_description_and_does_not_retype_it_same():
    item = _judged(SQLPARSE_C1, "stale", "updated")
    # The model typed the bug as a difference. Clean-up must not turn that into "same".
    differs = dict(item)
    differs["claims"] = [dict(item["claims"][0], expect="differs")]
    differs = probes.rejudge_entry(differs)
    cleaned = claim_hygiene.apply({"status": "ran", "items": [differs]})
    assert not (cleaned.get("claim_hygiene") or {}).get("retyped_same")
    assert cleaned["items"][0]["claims"][0]["expect"] == "differs"
    # A mis-typed "same" is still not judged as a broken promise.
    cleaned_same = claim_hygiene.apply({"status": "ran", "items": [item]})
    note = cleaned_same["claim_hygiene"]["base_description"]
    assert note and note[0]["claim"] == "C1"
    assert cleaned_same["items"][0]["observations"][0]["label"] != "false_claim"
    again = claim_hygiene.apply(cleaned_same)
    assert again["items"] == cleaned_same["items"]
