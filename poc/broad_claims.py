"""Broad "nothing else changes" claims need several varied inputs (product checks only).

A claim such as "existing behaviour is preserved", "nothing else changes" or "no other behaviour changes" is about
every input the changed code accepts, not about the one example the PR shows. A single probe input that comes out the
same on both sides says little about it. Two rules follow:

1. probe_rule(claims): an extra paragraph for the probes prompt that names the broad claims and asks for at least
   MIN_INPUTS varied inputs per broad claim, each recorded as its own observation, so base and head are compared on
   each input by plain code.
2. apply(probe_results): a broad claim that expects "same" and is linked to fewer than MIN_INPUTS distinct
   observations is held back. ops/daily_run.verdict_for then lowers a verified result to could_not_verify. A
   difference on any of the inputs is decided as usual by the probes (needs attention). The rule never raises a
   verdict.

Study runs never call this module, so their prompts and records are unchanged. The phrase list is generic: it names
no project and no package."""
from __future__ import annotations

import copy
import re

MIN_INPUTS = 3
_B = r"behaviou?r(?:s|al)?"
BROAD = re.compile(
    r"(?i)\b(?:"
    rf"preserv(?:e|es|ed|ing)\s+(?:the\s+)?(?:existing|current|previous|old|original|other)\s+{_B}|"
    rf"(?:existing|current|previous|other|all\s+other|original)\s+{_B}\s+(?:[^\s.!?]+\s+){{0,5}}?(?:is|are|remains?|stays?|will\s+be)\s+"
    r"(?:preserved|unchanged|the\s+same|kept|intact|unaffected)|"
    r"nothing\s+else\s+(?:changes|changed|is\s+changed|is\s+affected)|"
    rf"no\s+other\s+(?:{_B}\s+|functional\s+|user[-\s]facing\s+)?changes?|"
    r"no\s+regressions?|"
    r"everything\s+else\s+(?:stays|remains|is)\s+(?:the\s+same|unchanged|as\s+before)|"
    r"otherwise\s+unchanged|"
    r"(?:does\s+not|doesn['’]t|won['’]t|will\s+not)\s+(?:affect|change)\s+(?:any\s+)?other|"
    r"without\s+(?:affecting|changing|breaking)\s+(?:any\s+)?(?:other|existing)"
    r")\b")


def is_broad(text: str | None) -> bool:
    """True when a claim's text says nothing else changes."""
    return bool(BROAD.search(text or ""))


def broad_ids(claims: list | None) -> list[str]:
    """Ids of testable claims that expect 'same' and say nothing else changes."""
    out = []
    for c in claims or []:
        txt = " ".join(str(c.get(k) or "") for k in ("text", "source_quote"))
        if c.get("expect", "same") == "same" and is_broad(txt) and c.get("id"):
            out.append(str(c["id"]))
    return out


def probe_rule(claims: list | None) -> str:
    """Extra probes-prompt text for the broad claims ('' when there are none)."""
    ids = broad_ids(claims)
    if not ids:
        return ""
    return (f"\n\nBroad claims: {', '.join(ids)} say that nothing else changes. One example input cannot check that. "
            f"For each of them record at least {MIN_INPUTS} (better 6 or more) separate observations, each on a "
            "different input to the changed code, named '<claim id>.<short input name>'. Choose the inputs "
            "generically from the BASE-side code, and do not only reuse the PR's own example: vary the shape of the "
            "input, what comes before and after the part the change is about, empty and minimal inputs, nested and "
            "repeated parts, other accepted types, and inputs the changed code handled before the change. Record "
            "the full result for each input (not only a count or a true/false), so plain code can compare base "
            "and PR on every input.")


def _linked(probe_results: dict) -> dict[str, set]:
    seen: dict[str, set] = {}
    for it in probe_results.get("items") or []:
        for o in it.get("observations") or []:
            if o.get("claim"):
                seen.setdefault(str(o["claim"]), set()).add((str(it.get("id")), str(o.get("name"))))
    return seen


def apply(probe_results: dict | None) -> dict | None:
    """A copy of probe_results with a 'broad_claims' summary. The input is never changed."""
    if not probe_results or not probe_results.get("items"):
        return probe_results
    out = copy.deepcopy(probe_results)
    claims = [c for it in out.get("items") or [] for c in it.get("claims") or []]
    ids = sorted(set(broad_ids(claims)))
    if not ids:
        out.pop("broad_claims", None)
        return out
    seen = _linked(out)
    counts = {i: len(seen.get(i, ())) for i in ids}
    out["broad_claims"] = {"min_inputs": MIN_INPUTS, "claims": ids, "inputs": counts,
                           "held_back": [i for i in ids if counts[i] < MIN_INPUTS]}
    return out


def note_text(summary: dict | None) -> str:
    if not summary or not summary.get("held_back"):
        return ""
    parts = ", ".join(f"{i} ({summary['inputs'].get(i, 0)} input(s))" for i in summary["held_back"])
    return (f"broad 'nothing else changes' claim(s) {parts} were checked on fewer than "
            f"{summary.get('min_inputs', MIN_INPUTS)} varied inputs")
