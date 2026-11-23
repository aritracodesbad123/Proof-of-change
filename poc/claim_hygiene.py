"""Product-check clean-up of model-written probe claims, applied before the probes are judged for the verdict.

Only the product route calls this (ops/daily_run.settle_probes when the record is a product check). The study route
never does, so its records are unchanged.

First, claim links are repaired in code (rule 0). Then three rules, each fail closed (none of them can turn a run
into verified on its own):

0. A model often writes a claim's covers as the claim id ("C1", "C1*", any case) instead of observation-name
   patterns. Such a cover links the claim to the observation named exactly that id or starting with the id and
   "." or "-", ignoring case, and never to a longer id ("C1" or "C1*" never links "C10.x"). A claim with
   such a cover is always matched this way, even when that leaves it linking nothing. Other patterns are matched ignoring case.
   The covers as written are kept on the claim (covers_as_written) and each repaired link is listed in
   ``relinked``. A link only says which claim an observation belongs to; the claim still has to hold.

1. A claim the pull request does not make is dropped. Claims come from the PR's own text or diff, never from test
   outcomes: "the regression test passes" or "84 tests passed" describes a test run, not the product's behaviour.
   A model probe whose every claim is dropped was planned for a claim the PR does not make, so it is removed from
   the deciding probes. If that probe had flagged anything, the verdict cannot be verified (see
   ``dropped_flagged``), because the flag may still point at something real that nothing else probed.
2. A claim that says something stays the same ("will NOT bypass", "is preserved", "unchanged",
   "continues to", "as before") is typed expect "same", even when the model typed it "differs".
   A sentence that only describes the pre-PR behaviour or the bug being fixed is never that kind of claim:
   words such as "unchanged" or "still" in the problem statement are the old behaviour, not a promise.
3. A model probe with no claims attached cannot say which differences the PR intended. Its "differs and no claim
   covers it" observations are kept and shown, marked advisory: they do not raise needs attention, but a run with
   one is held at could not verify (never verified). The same applies to a model probe whose claims, after rule 0,
   still link none of its observations (``unlinked_probes``).

A claim that expected a difference and matched no observation before the clean-up keeps holding the run back
(``held_back``), whether it was retyped or dropped.
"""
from __future__ import annotations

import copy
import fnmatch
import re

from poc import probes
from poc.verdict import COLOUR, FindingLabel

# Rule 1: sentences about a test run, not about the product. Narrow on purpose: a test word as the subject plus a
# pass word, or a count of tests passed. "parsing results in a list" is a behaviour claim and is kept.
_TEST_OUTCOME = re.compile(
    r"(?ix)"
    r"\b\d+\s+tests?\s+(?:passed|pass|passing|failed)\b"
    r"|\b(?:regression|unit|integration|new|existing|added)\s+tests?\b[^.;:]{0,40}?\b(?:pass|passes|passed)\b"
    r"|\b(?:all|the)\s+tests?\s+(?:now\s+)?(?:pass|passes|passed)\b"
    r"|\btest\s+suite\b[^.;:]{0,40}?\b(?:pass|passes|passed)\b"
    r"|\bci\s+(?:is\s+green|passes|passed)\b"
    # "Two new test cases added for regression coverage fail before the fix", "The control test case passes both
    # before and after the fix": the outcome of the PR's own tests, not a product behaviour.
    r"|\btest\s+cases?\b[^.;:]{0,60}?\b(?:pass|passes|passed|passing|fail|fails|failed|failing)\b")

# Rule 2: the claim says the behaviour is kept. Narrow on purpose: "does not raise", "is not merged" or "still"
# often describe the fix itself, so they are not on this list.
_STAYS_SAME = re.compile(
    r"(?ix)"
    r"\bunchanged\b|\bpreserved\b|\bpreserves\b|\bas\s+before\b|\bunaffected\b|\bnot\s+affected\b"
    r"|\bcontinues?\s+to\b|\bwill\s+not\b|\bwon['’]t\b")
# ... unless it says the old behaviour stops ("no longer", "not ... anymore", "now", "instead").
_SAYS_CHANGE = re.compile(r"(?i)\bno\s+longer\b|\banymore\b|\bany\s+more\b|\binstead\b|\bnow\b|\bfixe[sd]\b"
                          r"|\bused\s+to\b|\bpreviously\b|\bbefore\s+(?:this|the)\s+(?:change|fix|pr)\b"
                          r"|\b(?:raise|crash|fail|error|hang)s?\b")


def is_test_outcome_claim(text: str) -> bool:
    return bool(_TEST_OUTCOME.search(text or ""))


# A sentence that only describes what the code did before this pull request, or the bug being fixed.
# "unchanged" / "still" in that sentence are the defect ("leaves the cache unchanged", "still sized from all
# columns"), not a promise that the pull request keeps behaviour. A genuine promise ("other inputs are
# unaffected", "existing behaviour is preserved", "remains unchanged after the fix") is not this.
_NEW_SIDE = re.compile(
    r"(?i)\b(?:after(?:wards)?|now|instead|"
    r"(?:the|this)\s+(?:fix|change|patch|pr|pull\s+request)|"
    r"with\s+(?:the|this)\s+(?:fix|change|patch))\b")
_PROMISE = re.compile(
    r"(?i)\b(?:unchanged|preserved|preserves|preserving|unaffected|not\s+affected|"
    r"as\s+before|continues?\s+to|will\s+not|won['’]t|"
    r"(?:does|do|doesn['’]t|don['’]t|will)\s+not\s+change|"
    r"no\s+(?:behaviou?r|behavior)\s+change|"
    r"backwards?[-\s]+compatib|"
    r"untouched|without\s+(?:changing|affecting|breaking)|"
    r"remains?|stays?|kept|keeps?|retain(?:s|ed)?|"
    r"the\s+same|identically)\b")
# "keep working" and "still works" are promises even next to "currently" or "previously".
# "still sized" is not: that is the bug persisting.
_KEEP_WORKING = re.compile(r"(?i)\bkeeps?\s+working\b|\bstill\s+works?\b")
# "previously valid/accepted/supported" is a compatibility promise, not a description of the bug.
_PREVIOUSLY_KEPT = re.compile(
    r"(?i)\bpreviously\s+(?:valid|accepted|supported)\b"
    r"|\b(?:were|was)\s+previously\s+(?:valid|accepted|supported)\b")
# "still returns / still raises / still works" continues a behaviour. "still sized from" is the bug persisting.
_STILL_CONTINUES = re.compile(
    r"(?i)\bstill\s+(?:returns?|raises?|works?|passes?|is|are|be|remains?|"
    r"recognis(?:e|ed|es)|recogniz(?:e|ed|es)|accepted|uses?|none|the\s+same|unchanged)\b")
_CONTRAST_LEAVES = re.compile(
    r"(?i)\b(?:but|yet|however)\b.{0,160}?\b(?:leaves?|leaving|left)\b.{0,80}?\bunchanged\b")
_CACHED_UNCHANGED = re.compile(
    r"(?i)\bleaves?\b.{0,60}?\b(?:cached|cache|stale|normali[sz]ed)\b.{0,40}?\bunchanged\b")
_STILL_BUG = re.compile(
    r"(?i)\bstill\s+(?:sized|computed|calculated|counted|measured|derived|based|summed|taken|using)\b"
    r"|\bstill\s+leaves?\b.{0,80}?\b(?:overlong|stale|wrong|incorrect|unescaped|zero|narrow)\b")
_OLD_MARKER = re.compile(
    r"(?i)\b(?:previously|used\s+to|"
    r"in\s+the\s+current\s+(?:code|implementation|version)|"
    r"currently|"
    r"without\s+the\s+(?:fix|change|patch)|"
    r"before\s+(?:the|this)\s+(?:fix|change|patch|pr|pull\s+request)|"
    r"on\s+(?:the\s+)?(?:current\s+)?(?:main|master|base)(?:\s+branch)?|"
    r"returned\b[^.]{0,40}?\bbefore\b|"
    r"\bbefore\b[^.]{0,24}?\b(?:returned|raised))\b")
_FAULT = re.compile(
    r"(?i)\b(?:narrower|wider|wrong|incorrect|fails?|failed|raises?|raised|"
    r"crash(?:es|ed)?|errors?|missing|ignored|unexpected(?:ly)?|broken|"
    r"instead\s+of|rather\s+than|unescaped|not\s+updated|not\s+escaped|"
    r"too\s+(?:far|narrow|wide|small|large|big))\b")
_CAUSE = re.compile(r"(?i)\b(?:because|causing|caused|consequently)\b")
_PAST_CONTRAST = re.compile(
    r"(?i)\b(?:summed|counted|computed|calculated|measured|included)\b.{0,100}?\bwhile\b.{0,80}?\balready\b")
# Words that make the sentence about both sides. "from all columns" is the bug's input, not "in all versions".
_BOTH_SIDES = re.compile(
    r"(?i)\b(?:both|either|each|regardless|versions?|identical|equal)\b|\b(?:in|for)\s+all\b")


def _is_promise(text: str) -> bool:
    """True when the sentence promises that some behaviour is kept.

    "keep", "keep(s) working" and "still work(s)" count, and so does "previously valid/accepted/supported".
    "still sized from all columns" does not."""
    t = text or ""
    return bool(_PROMISE.search(t) or _KEEP_WORKING.search(t) or _PREVIOUSLY_KEPT.search(t))


def _has_new_side(text: str) -> bool:
    """True when the sentence also describes the pull request's new behaviour.

    "before the fix" names the old side, so that phrase is removed before the new-side words are read."""
    return bool(_NEW_SIDE.search(_OLD_MARKER.sub(" ", text or "")))


def describes_old_bug(text: str) -> bool:
    """True when the sentence describes the pre-PR behaviour or the bug being fixed.

    Such a sentence is not a promise that the pull request leaves behaviour unchanged. The decision is the
    wording, the tense and the markers (before, previously, used to, currently, still), not a repository name.
    A promise ("unaffected", "preserved", "remains unchanged after the fix") is false."""
    t = text or ""
    if not t.strip():
        return False
    new = _has_new_side(t)
    # "changes X but leaves Y unchanged" is the defect, unless the sentence is the fix speaking.
    if not new and (_CONTRAST_LEAVES.search(t) or _CACHED_UNCHANGED.search(t)):
        return True
    # A sentence about both sides, or a promise, is not a description of the old behaviour alone.
    # A promise wins over an old-side word in the same sentence ("currently ... keep working").
    if _BOTH_SIDES.search(t) or _is_promise(t) or new:
        return False
    if _STILL_BUG.search(t) and not _STILL_CONTINUES.search(t):
        return True
    if _OLD_MARKER.search(t):
        return True
    if _FAULT.search(t) and _CAUSE.search(t):
        return True
    if _PAST_CONTRAST.search(t):
        return True
    return False


def says_stays_same(text: str) -> bool:
    t = text or ""
    # A description of the bug is not retyped into a no-change promise, even when it says "unchanged".
    if describes_old_bug(t):
        return False
    return bool(_STAYS_SAME.search(t)) and not _SAYS_CHANGE.search(t)


def _sentence_is_old_bug(text: str, quote: str) -> bool:
    """The claim text decides. A quote is used only when the text itself is not a promise."""
    if text and describes_old_bug(text):
        return True
    if quote and quote != text and describes_old_bug(quote) and not _is_promise(text):
        return True
    if not text and quote and describes_old_bug(quote):
        return True
    return False


def correct_extracted_claim(claim: dict) -> dict:
    """A parsed claim typed "same" that only describes the old behaviour is kept as a base-side description.

    It is not testable as a comparison and its expect is "base", so a later probe is not asked to treat it as
    a promise that the two sides stay the same. A claim the model already typed "differs" is left as it is.

    A model answer of "base" is not trusted on its own. It stands only when the sentence is the old bug, or
    when the sentence has no promise word. A promise the model typed "base" ("other inputs are unaffected")
    is put back to "same" so it is still tested."""
    if not isinstance(claim, dict):
        return claim
    text = str(claim.get("text") or "")
    quote = str(claim.get("source_quote") or "")
    old = _sentence_is_old_bug(text, quote)
    expect = claim.get("expect")
    if expect == "base":
        agrees = describes_old_bug(text) if text.strip() else describes_old_bug(quote)
        has_promise = _is_promise(text) or _is_promise(quote)
        # Lean towards "same": a promise word, and the old-bug check does not agree, keeps the claim tested.
        if agrees or not has_promise:
            return dict(claim, expect="base", testable=False, base_description=True)
        restored = {k: v for k, v in claim.items() if k != "base_description"}
        restored["expect"] = "same"
        restored["testable"] = True
        return restored
    if expect == "same" and old:
        return dict(claim, expect="base", testable=False, base_description=True)
    return claim


# What may follow the claim id in an observation name: "C1.a", "C1-a", "c1_a". A digit or a letter never does, so
# "C1" never links "C10" or "C1a".
ID_SEPARATORS = ".-_"


def _has_id_cover(claim: dict) -> bool:
    cid = str(claim.get("id") or "")
    return any(isinstance(p, str) and _is_id_cover(p, cid) for p in claim.get("covers") or [])


def _is_id_cover(pat: str, cid: str) -> bool:
    p = pat.strip()
    if p.endswith("*"):
        p = p[:-1]
    return bool(cid) and p.lower() == cid.lower()


def _escape(name: str) -> str:
    return re.sub(r"([*?\[])", r"[\1]", name)


def linked_names(claim: dict, names: list[str]) -> list[str]:
    """Observation names a claim covers (rule 0): a cover equal to the claim id (optionally ending in *) means the
    name equal to the id or starting with the id and ".", "-" or "_"; any other cover is an fnmatch pattern, compared ignoring case."""
    cid = str(claim.get("id") or "")
    out = []
    for n in names:
        low = n.lower()
        for pat in claim.get("covers") or []:
            if not isinstance(pat, str):
                continue
            if _is_id_cover(pat, cid):
                c = cid.lower()
                hit = low == c or (low.startswith(c) and low[len(c)] in ID_SEPARATORS)
            else:
                hit = fnmatch.fnmatchcase(low, pat.lower())
            if hit:
                out.append(n)
                break
    return out


def relink(item: dict) -> tuple[dict, list]:
    """Rule 0 on one model probe. Returns (item, links repaired). The item is re-judged only when a link changed."""
    if item.get("source") != "model" or not item.get("runs"):
        return item, []
    names = probes._observation_names(item)
    claims, fixed = [], []
    for c in item.get("claims") or []:
        if not isinstance(c, dict):
            claims.append(c)
            continue
        want = linked_names(c, names)
        had = [n for n in names if probes._covers_name(c.get("covers"), n)]
        # A claim with an id cover always uses the new matcher, even when it then links nothing: the old matcher
        # would link "C1*" to "C10.x".
        if (want or _has_id_cover(c)) and sorted(want) != sorted(had):
            fixed.append({"probe": item.get("id"), "claim": c.get("id"), "covers_as_written": c.get("covers"),
                          "linked": sorted(want)})
            c = dict(c, covers=[_escape(n) for n in sorted(want)], covers_as_written=c.get("covers"))
        claims.append(c)
    if not fixed:
        return item, []
    return probes.rejudge_entry(dict(item, claims=claims)), fixed


def _unlinked(item: dict) -> bool:
    """A model probe with claims none of which links any of its observations (after rule 0)."""
    return probes.rejection_reason(item) is not None


def _flagged(item: dict) -> bool:
    return any(COLOUR.get(FindingLabel(o["label"])) in ("red", "amber") for o in item.get("observations") or []
               if o.get("label") in {x.value for x in FindingLabel})


def apply(probe_results: dict | None) -> dict | None:
    """Return a cleaned copy of probe_results (the input is not changed). Adds ``claim_hygiene`` with what changed."""
    if not probe_results or not probe_results.get("items"):
        return probe_results
    out = copy.deepcopy(probe_results)
    relinked = []
    for i, it in enumerate(out["items"]):
        out["items"][i], fixed = relink(it)
        relinked += fixed
    # Claims that expect a difference and match no observation once links are repaired, before any other clean-up.
    # A retyped or dropped claim must never lift that cap, so it is kept and checked again in
    # ops/daily_run.verdict_for.
    held = probes.unmatched_differs_claims(out)
    notes = {"held_back": list(held), "dropped_claims": [], "retyped_same": [], "base_description": [],
             "dropped_probes": [], "dropped_flagged": [],
             "advisory_probes": [], "relinked": relinked, "unlinked_probes": []}
    kept_items = []
    for it in out["items"]:
        if it.get("source") != "model":
            kept_items.append(it)
            continue
        claims = list(it.get("claims") or [])
        had_claims = bool(claims)
        new_claims, changed = [], False
        for c in claims:
            text = str(c.get("text") or "")
            if is_test_outcome_claim(text):
                notes["dropped_claims"].append({"probe": it["id"], "claim": c.get("id"), "text": text})
                changed = True
                continue
            if (c.get("expect") == "same" and describes_old_bug(text)
                    and not probes.is_one_side_claim(c)):
                # Leave expect as stored. Judging reads the text and does not treat this as a no-change promise.
                notes["base_description"].append({"probe": it["id"], "claim": c.get("id"), "text": text})
                changed = True
            elif c.get("expect") == "differs" and says_stays_same(text):
                c = dict(c, expect="same")
                notes["retyped_same"].append({"probe": it["id"], "claim": c.get("id"), "text": text})
                changed = True
            new_claims.append(c)
        if had_claims and not new_claims:
            notes["dropped_probes"].append(it["id"])
            if _flagged(it):
                notes["dropped_flagged"].append(it["id"])
            continue
        if changed and it.get("runs"):
            it = probes.rejudge_entry(dict(it, claims=new_claims))
        unlinked = had_claims and _unlinked(it)
        if not had_claims or unlinked:
            hit = False
            for o in it.get("observations") or []:
                if o.get("label") == FindingLabel.UNMENTIONED_CHANGE.value:
                    o["advisory"] = True
                    hit = True
            if hit:
                notes["unlinked_probes" if unlinked else "advisory_probes"].append(it["id"])
        kept_items.append(it)
    out["items"] = kept_items
    if any(v for k, v in notes.items() if k != "held_back") or (notes["held_back"] and "claim_hygiene" not in out):
        prev = (out.get("claim_hygiene") or {}).get("held_back") or []
        notes["held_back"] = sorted(set(notes["held_back"]) | set(prev))
        out["claim_hygiene"] = notes
    elif out.get("claim_hygiene"):
        out["claim_hygiene"]["held_back"] = sorted(set(out["claim_hygiene"].get("held_back") or []) | set(held))
    return out


def note_text(notes: dict | None) -> str:
    if not notes:
        return ""
    bits = []
    if notes.get("dropped_claims"):
        bits.append("claim(s) " + ", ".join(str(d["claim"]) for d in notes["dropped_claims"])
                    + " dropped: they describe a test run, not something the pull request claims")
    if notes.get("retyped_same"):
        bits.append("claim(s) " + ", ".join(str(d["claim"]) for d in notes["retyped_same"])
                    + " say behaviour stays the same, so they expect no difference")
    if notes.get("base_description"):
        bits.append("claim(s) " + ", ".join(str(d["claim"]) for d in notes["base_description"])
                    + " describe the pre-PR behaviour, so they are not a promise that it stays the same")
    if notes.get("relinked"):
        bits.append("claim(s) " + ", ".join(sorted({str(d["claim"]) for d in notes["relinked"]}))
                    + " linked to observations by claim id")
    if notes.get("unlinked_probes"):
        bits.append("probe(s) " + ", ".join(notes["unlinked_probes"])
                    + " link none of their claims to an observation, so their differences are shown as advisory only")
    if notes.get("advisory_probes"):
        bits.append("probe(s) " + ", ".join(notes["advisory_probes"])
                    + " carry no claims, so their unclaimed differences are shown as advisory only")
    if notes.get("held_back"):
        bits.append("claim(s) " + ", ".join(notes["held_back"]) + " expected a difference that no observation "
                    "showed; cleaning up claims never lifts that")
    if notes.get("dropped_flagged"):
        bits.append("probe(s) " + ", ".join(notes["dropped_flagged"])
                    + " were planned for a claim the pull request does not make and flagged a difference; "
                    "this run cannot be verified")
    return "; ".join(bits)
