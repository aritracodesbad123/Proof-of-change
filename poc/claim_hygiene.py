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
   covers it" observations are kept and shown, but marked advisory and do not decide the verdict. The tests and
   the other probes still decide.
"""
from __future__ import annotations

import copy
import re

from poc import probes
from poc.verdict import COLOUR, FindingLabel

# Rule 1: sentences about a test run, not about the product.
_TEST_OUTCOME = re.compile(
    r"(?ix)"
    r"\b\d+\s+(?:tests?|cases?)\s+(?:passed|pass|passing|failed|fail|ran|run)\b"
    r"|\b(?:regression\s+|unit\s+|new\s+|existing\s+|the\s+)?(?:tests?|test\s+suite|test\s+cases?)\b"
    r"[^.]{0,60}?\b(?:pass|passes|passed|passing|succeed|succeeds|green|results?\s+in)\b"
    r"|\b(?:ci|pytest|tox|nox)\b[^.]{0,40}?\b(?:pass|passes|passed|green)\b")

# Rule 2: the claim says the behaviour is kept.
_STAYS_SAME = re.compile(
    r"(?ix)"
    r"\bunchanged\b|\bpreserved?\b|\bpreserves\b|\bstill\b|\bcontinues?\s+to\b|\bas\s+before\b|\bremains?\b"
    r"|\bstays?\b|\bis\s+kept\b|\bkeeps?\b|\bnot\s+affected\b|\bunaffected\b|\bsame\s+as\s+before\b"
    r"|\b(?:will|does|do|is|are|should)\s+not\b|\b(?:won['’]t|doesn['’]t|don['’]t|isn['’]t|aren['’]t)\b")
# ... unless it says the old behaviour stops ("no longer", "not ... anymore", "now", "instead").
_SAYS_CHANGE = re.compile(r"(?i)\bno\s+longer\b|\banymore\b|\bany\s+more\b|\binstead\b|\bnow\b|\bfixe[sd]\b"
                          r"|\bused\s+to\b|\bpreviously\b|\bbefore\s+(?:this|the)\s+(?:change|fix|pr)\b")


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
    notes = {"dropped_claims": [], "retyped_same": [], "dropped_probes": [], "dropped_flagged": [],
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
    if any(notes.values()):
        out["claim_hygiene"] = notes
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
    if notes.get("dropped_flagged"):
        bits.append("probe(s) " + ", ".join(notes["dropped_flagged"])
                    + " were planned for a claim the pull request does not make and flagged a difference; "
                    "this run cannot be verified")
    return "; ".join(bits)
