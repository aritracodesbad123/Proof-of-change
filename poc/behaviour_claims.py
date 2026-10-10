"""Behaviour-preservation claims in a PR's title or description.

A PR that says its change keeps results the same ("results unchanged", "same output", "same results for a given
seed", "backwards compatible", "no behaviour change", ...) makes a claim the tests usually do not check: they test
the new behaviour, not that everything else stayed put. Such a claim needs a probe (poc/probes.py) with a claim
that expects "same". Without one, the PR cannot be 'verified' (ops/daily_run.verdict_for):

    could_not_verify: unverified behaviour claim: "<quote>"; needs a probe

PATTERNS is the whole list, deliberately small; a match preceded by a negation ("not backwards compatible",
"this breaks backward compatibility") is ignored, and so are Markdown headings ("## Backward compatibility"), HTML
comments (PR templates) and code blocks."""
from __future__ import annotations

import re

_R = "(?:results?|outputs?|behaviou?r|values?|predictions?|importances?|scores?)"
PATTERNS: list[tuple[str, str]] = [
    ("unchanged", rf"\b{_R}\s+(?:are|is|remain|remains|stay|stays|will\s+be)?\s*(?:unchanged|identical|preserved)\b"),
    ("does not change", rf"\b{_R}\s+(?:do|does|will|should|would)\s*(?:not|n['’]t)\s+change\b"),
    ("don't change", rf"\b{_R}\s+(?:don['’]t|doesn['’]t|won['’]t|shouldn['’]t|wouldn['’]t)\s+change\b"),
    ("same output", rf"\b(?:the\s+)?same\s+{_R}\b"),
    ("for a given seed", r"\bfor\s+(?:a|the)\s+(?:given|same|fixed)\s+(?:random\s+)?seed\b"),
    ("backwards compatible", r"\bbackwards?[-\s]+compatib(?:le|ility)\b"),
    ("no behaviour change", r"\bno\s+(?:behaviou?ral|behaviou?r|functional|user[-\s]facing|api)\s+changes?\b"),
    ("no change in behaviour", rf"\bno\s+changes?\s+(?:in|to)\s+(?:the\s+)?{_R}\b"),
]
COMPILED = [(name, re.compile(p, re.I)) for name, p in PATTERNS]
NEGATION = re.compile(r"(?:\bnot|n['’]t|\bno\s+longer|\bbreaks?|\bbreaking|\bwithout)\W+(?:\w+\W+){0,2}$", re.I)


def _clean(text: str) -> str:
    text = re.sub(r"<!--.*?-->", " ", text or "", flags=re.S)
    text = re.sub(r"```.*?```", " ", text, flags=re.S)
    return text


_BOUNDARY = re.compile(r"[.!?](?=\s)|\n")


def _sentence(text: str, start: int, end: int, width: int = 200) -> str:
    """The sentence around text[start:end]; boundaries are . ! ? followed by whitespace, or a line break (so dots in
    code such as `rng.shuffle` do not split it)."""
    left = max([m.end() for m in _BOUNDARY.finditer(text, 0, start)] or [0])
    r = _BOUNDARY.search(text, end)
    s = " ".join(text[left:(r.end() if r else len(text))].split()).strip(" -*#>")
    return s if len(s) <= width else s[:width - 3].rstrip() + "..."


def find(title: str, body: str | None) -> list[dict]:
    """All behaviour-preservation claims: [{source, quote, pattern}], one per sentence, in text order."""
    out, seen = [], set()
    for source, text in (("title", title or ""), ("PR description", _clean(body or ""))):
        for name, rx in COMPILED:
            for m in rx.finditer(text):
                if NEGATION.search(text[max(0, m.start() - 40):m.start()]):
                    continue
                line_start = text.rfind("\n", 0, m.start()) + 1
                if text[line_start:].lstrip().startswith("#"):   # a Markdown heading names a topic, not a claim
                    continue
                q = _sentence(text, m.start(), m.end())
                if q and (source, q) not in seen:
                    seen.add((source, q))
                    out.append({"source": source, "quote": q, "pattern": name, "_pos": (source != "title", m.start())})
    out.sort(key=lambda c: c.pop("_pos"))
    return out


def probe_covers(probe_results: dict | None) -> bool:
    """A probe that ran and has at least one claim expecting 'same' checks behaviour preservation; its result then
    decides (probes never get overruled by this rule). A probe that ran none of the changed lines on the main side
    (probe_changed_line_coverage adequacy not_adequate, poc/probe_adequacy.py) does not count."""
    for it in (probe_results or {}).get("items") or []:
        if (it.get("probe_changed_line_coverage") or {}).get("adequacy") == "not_adequate":
            continue
        if any(c.get("expect") == "same" for c in it.get("claims") or []):
            return True
    return False
