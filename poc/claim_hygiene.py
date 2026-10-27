"""Product-check clean-up of model-written probe claims, applied before the probes are judged for the verdict.

Only the product route calls this (ops/daily_run.settle_probes when the record is a product check). The study route
never does, so its records are unchanged.

Three rules, each fail closed (none of them can turn a run into verified on its own):

1. A claim the pull request does not make is dropped. Claims come from the PR's own text or diff, never from test
   outcomes: "the regression test passes" or "84 tests passed" describes a test run, not the product's behaviour.
   A model probe whose every claim is dropped was planned for a claim the PR does not make, so it is removed from
   the deciding probes. If that probe had flagged anything, the verdict cannot be verified (see
   ``dropped_flagged``), because the flag may still point at something real that nothing else probed.
2. A claim that says something stays the same ("will NOT bypass", "is preserved", "unchanged", "still",
   "continues to", "as before") is typed expect "same", even when the model typed it "differs".
3. A model probe with no claims attached cannot say which differences the PR intended. Its "differs and no claim
   covers it" observations are kept and shown, marked advisory: they do not raise needs attention, but a run with
   one is held at could not verify (never verified).

A claim that expected a difference and matched no observation before the clean-up keeps holding the run back
(``held_back``), whether it was retyped or dropped.
"""
from __future__ import annotations

import copy
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
    r"|\bci\s+(?:is\s+green|passes|passed)\b")

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


def says_stays_same(text: str) -> bool:
    t = text or ""
    return bool(_STAYS_SAME.search(t)) and not _SAYS_CHANGE.search(t)


def _flagged(item: dict) -> bool:
    return any(COLOUR.get(FindingLabel(o["label"])) in ("red", "amber") for o in item.get("observations") or []
               if o.get("label") in {x.value for x in FindingLabel})


def apply(probe_results: dict | None) -> dict | None:
    """Return a cleaned copy of probe_results (the input is not changed). Adds ``claim_hygiene`` with what changed."""
    if not probe_results or not probe_results.get("items"):
        return probe_results
    out = copy.deepcopy(probe_results)
    # Claims that expect a difference and match no observation, before any clean-up. A retyped or dropped claim must
    # never lift that cap, so it is kept and checked again in ops/daily_run.verdict_for.
    held = probes.unmatched_differs_claims(probe_results)
    notes = {"held_back": list(held), "dropped_claims": [], "retyped_same": [], "dropped_probes": [], "dropped_flagged": [],
             "advisory_probes": []}
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
            if c.get("expect") == "differs" and says_stays_same(text):
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
        if not had_claims:
            hit = False
            for o in it.get("observations") or []:
                if o.get("label") == FindingLabel.UNMENTIONED_CHANGE.value:
                    o["advisory"] = True
                    hit = True
            if hit:
                notes["advisory_probes"].append(it["id"])
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
