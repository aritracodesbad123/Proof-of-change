"""Behaviour-preservation claims in a PR's title or description.

A PR that says its change keeps results the same ("results unchanged", "same output", "same results for a given
seed", "backwards compatible", "no behaviour change", "passed through", "left unchanged", "returned unchanged",
"exactly as before", "untouched", ...) makes a claim the tests usually do not check: they test
the new behaviour, not that everything else stayed put. Such a claim needs a probe (poc/probes.py) with a claim
that expects "same". Without one, the PR cannot be 'verified' (ops/daily_run.verdict_for):

    could_not_verify: unverified behaviour claim: "<quote>"; needs a probe

PATTERNS is the whole list, deliberately small; a match preceded by a negation ("not backwards compatible",
"this breaks backward compatibility") is ignored, and so are Markdown headings ("## Backward compatibility"), HTML
comments, fenced code blocks, unticked checklist items ("- [ ] ...", including a wrapped continuation line) and
template boilerplate (the stock instruction lines a pull-request template pastes in, such as "Please make sure ..."
or "Thanks for contributing"). A ticked item ("- [x]") is the author's own line and can still be a claim."""
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
    # Phrases that do not name "results" or "output" but still say the old behaviour was kept.
    ("passed through", r"\bpassed\s+through\b"),
    ("left unchanged", r"\bleft\s+unchanged\b"),
    ("returned unchanged", r"\breturned\s+unchanged\b"),
    ("exactly as before", r"\bexactly\s+as\s+before\b"),
    ("untouched", r"\buntouched\b"),
]
COMPILED = [(name, re.compile(p, re.I)) for name, p in PATTERNS]
NEGATION = re.compile(r"(?:\bnot|n['’]t|\bno\s+longer|\bbreaks?|\bbreaking|\bwithout)\W+(?:\w+\W+){0,2}$", re.I)
# An unticked task ("- [ ]", "* [ ]", "1. [ ]"). A ticked item is the author speaking, so it stays.
_UNTICKED = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+\[\s\]")
# Stock lines a pull-request template pastes in. Anchored at the start so a real sentence that merely mentions
# the same words later ("Results are unchanged. Please run the tests.") is kept.
_BOILERPLATE = re.compile(
    r"(?i)^\s*(?:#+\s*)?(?:"
    r"(?:thanks|thank you) for (?:contributing|your contribution|submitting|opening)|"
    r"please (?:fill|complete|update|include|describe|make sure|ensure|check|mark|tick|select|delete|replace|"
    r"remove this)|"
    r"(?:delete|replace) (?:this|the) (?:line|text|placeholder|section)|"
    r"(?:code of conduct|pull request checklist)\b"
    r")"
)


def _drop_template(text: str) -> str:
    """Drop unticked checklist items (and their indented continuation) and template boilerplate lines."""
    kept, skip = [], False
    for line in text.splitlines():
        if _UNTICKED.match(line):
            skip = True
            continue
        if skip and line[:1] in (" ", "\t") and line.strip():
            continue
        skip = False
        if _BOILERPLATE.match(line):
            continue
        kept.append(line)
    return "\n".join(kept)


def _clean(text: str) -> str:
    text = re.sub(r"<!--.*?-->", " ", text or "", flags=re.S)
    text = re.sub(r"```.*?```", " ", text, flags=re.S)
    return _drop_template(text)


_BOUNDARY = re.compile(r"[.!?](?=\s)|\n")


def _sentence(text: str, start: int, end: int, width: int = 200) -> str:
    """The sentence around text[start:end]; boundaries are . ! ? followed by whitespace, or a line break (so dots in
    code such as `rng.shuffle` do not split it)."""
    left = max([m.end() for m in _BOUNDARY.finditer(text, 0, start)] or [0])
    r = _BOUNDARY.search(text, end)
    s = " ".join(text[left:(r.end() if r else len(text))].split()).strip(" -*#>")
    return s if len(s) <= width else s[:width - 3].rstrip() + "..."


_SOURCE_ORDER = {"title": 0, "PR description": 1, "changelog": 2, "docstring": 3}
_CHANGELOG_PATH = re.compile(
    r"(?i)(?:^|/)(?:changes|changelog|history|news|whatsnew)(?:[./]|$)|whatsnew")
_TRIPLE = re.compile(r"'''|\"\"\"")


def _doc_state(text: str, in_doc: bool, quote: str | None) -> tuple[bool, bool, str | None]:
    """(line is docstring text, in_doc after the line, quote in force)."""
    was = in_doc or bool(_TRIPLE.search(text))
    for m in _TRIPLE.finditer(text):
        q = m.group(0)
        if not in_doc:
            in_doc, quote = True, q
        elif q == quote:
            in_doc, quote = False, None
    return was, in_doc, quote


def diff_texts(diff: str | None) -> list[tuple[str, str]]:
    """Added changelog lines and added docstring lines from a unified diff.

    A changelog file is one whose path contains CHANGES, changelog, history, news or whatsnew.
    A docstring line is an added line that sits inside a triple-quoted string (one line or several).
    Context lines update the string state but are not claims by themselves."""
    out: list[tuple[str, str]] = []
    for block in re.split(r"(?m)^diff --git ", diff or ""):
        m = re.search(r"(?m)^\+\+\+ (?:b/)?(\S+)", block)
        if not m or m.group(1) == "/dev/null":
            continue
        path = m.group(1)
        added_doc, changelog = [], []
        in_doc, quote = False, None
        for line in block.splitlines():
            if not line or line.startswith(("+++", "---", "@@", "diff ", "index ", "new file", "deleted ")):
                continue
            prefix, text = line[0], line[1:]
            if prefix not in " +-":
                continue
            was, in_doc, quote = _doc_state(text, in_doc, quote)
            if prefix != "+":
                continue
            if _CHANGELOG_PATH.search(path):
                changelog.append(text)
            elif path.endswith(".py") and was:
                added_doc.append(text)
        if changelog:
            out.append(("changelog", _clean("\n".join(changelog))))
        if added_doc:
            out.append(("docstring", _clean("\n".join(added_doc))))
    return out


def find(title: str, body: str | None, diff: str | None = None) -> list[dict]:
    """All behaviour-preservation claims: [{source, quote, pattern}], one per sentence, in text order.

    Sources are the title, the pull-request description, and (when a diff is given) added changelog lines and
    added docstring lines. A match in any of those is a claim."""
    out, seen = [], set()
    texts = [("title", title or ""), ("PR description", _clean(body or "")), *diff_texts(diff)]
    for source, text in texts:
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
                    out.append({"source": source, "quote": q, "pattern": name,
                                "_pos": (_SOURCE_ORDER.get(source, 9), m.start())})
    out.sort(key=lambda c: c.pop("_pos"))
    return out


def probe_covers(probe_results: dict | None) -> bool:
    """A probe that ran and has at least one claim expecting 'same' checks behaviour preservation; its result then
    decides (probes never get overruled by this rule). A probe that ran none of the changed lines on the main side
    (probe_changed_line_coverage adequacy not_adequate, poc/probe_adequacy.py) does not count."""
    for it in (probe_results or {}).get("items") or []:
        if it.get("status") in ("uninformative", "not_run"):
            continue
        if (it.get("probe_changed_line_coverage") or {}).get("adequacy") == "not_adequate":
            continue
        if any(c.get("expect") == "same" for c in it.get("claims") or []):
            return True
    return False
