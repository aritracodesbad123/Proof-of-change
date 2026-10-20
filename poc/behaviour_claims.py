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


# A sentence about the PR's own tests or about a tool's output is not a claim about the product's behaviour:
# "Add regressions for ... untouched columns, and unchanged inputs" describes what a test covers, and "mypy's output
# is identical on the unmodified base" describes a type checker. Narrow shapes are dropped:
#   1. the sentence starts by adding/describing tests ("Add tests ...", "Added regression tests ...", "New tests ...");
#   2. the sentence names a checking tool (mypy, ruff, linter, ...) right next to a run/pass/fail word
#      ("ruff check", "linting passes", "mypy output"). A tool word on its own is not enough: "extend linter Fix"
#      describes the product when the product is a linter.
# List items and code lines under a "Test plan" / "Testing" / "Verification" heading are dropped for the same reason.
# Such a section ends at the next heading, the next "**Label**:" line, a <details> block, a "Fixes #" line, or new
# prose, so a summary written after the test list is kept. A "nothing else changes" sentence (unaffected, unchanged,
# without affecting ...) is never dropped by the section or tool rules unless it talks about the tests or a tool themselves.
_TEST_SENTENCE = re.compile(
    r"(?i)^\W*(?:i\s+|we\s+)?(?:add(?:s|ed)?|extend(?:s|ed)?|new|includ(?:e|es|ed)|cover(?:s|ed)?)\s+"
    r"(?:\w+\s+){0,2}?(?:regression\s+tests?|regressions?|tests?|test\s+cases?|unit\s+tests?)\b")
_TOOL = r"(?:mypy|pyright|ruff|flake8|pylint|black|isort|pre-commit|linters?|lint(?:ing)?|type[-\s]?check(?:er|ing)?s?)"
_RESULT = (r"(?:run(?:s|ning)?|ran|pass(?:es|ed|ing)?|fail(?:s|ed|ing|ures?)?|check(?:s|ed)?|outputs?|errors?|"
           r"warnings?|reports?|clean|succeed(?:s|ed)?|green)")
_TOOL_SENTENCE = re.compile(
    rf"(?i)\b{_TOOL}['`’]*(?:s)?\W+(?:\w+\W+){{0,3}}?{_RESULT}\b|"
    rf"\b(?:run(?:s|ning)?|ran|pass(?:es|ed|ing)?|fail(?:s|ed|ing)?)\W+(?:\w+\W+)?{_TOOL}\b")
# A sentence about a CI workflow or a .yml file describes the project's own automation (the change itself),
# so "The lint workflow was running ... twice" is kept.
_WORKFLOW = re.compile(r"(?i)\bworkflows?\b|\.ya?ml\b")
_PRESERVE = re.compile(
    r"(?i)\b(?:unaffected|unchanged|untouched|without\s+(?:affecting|changing|breaking)|"
    r"no\s+(?:other\s+)?(?:behaviou?r(?:al)?\s+)?changes?|nothing\s+else\s+changes|"
    r"(?:remain|remains|stay|stays|continue\s+to\s+work)\s+(?:the\s+same|as\s+before|unchanged))\b")
_ABOUT_TESTS = re.compile(rf"(?i)\b(?:tests?|suite|pytest|ci|{_TOOL})\b")
_QUOTE = re.compile(r"^\s*(?:>\s?)*")
_TEST_HEADING = re.compile(
    r"(?i)^\s*(?:[-*+]\s+)?(?:#+\s*|\*\*)(?:test(?:s|ing)?(?:\s+plan)?|how\s+(?:this\s+was\s+|i\s+)?tested|"
    r"type[-\s]?checking|verification)\b")
_ANY_HEADING = re.compile(r"^\s*(?:#+\s|\*\*[^*]+\*\*\s*:?\s*$)")
_LABEL_LINE = re.compile(r"^\s*(?:[-*+]\s+)?\*\*[^*]+\*\*\s*:")
_SECTION_STOP = re.compile(r"(?i)^\s*(?:<details|<summary|\[!\w+\]|fixes\s+\S*#\d+|(?:closes|resolves)\s+\S*#\d+)")
_ITEM = re.compile(r"^\s*(?:[-*+]\s|\d+[.)]\s|`|\$\s|-{3,}\s*$|\*{3,}\s*$|_{3,}\s*$)")


def keeps_nothing_else_changes(sentence: str) -> bool:
    """True for a 'nothing else changes' sentence that is about the product, not about the tests."""
    return bool(_PRESERVE.search(sentence)) and not _ABOUT_TESTS.search(sentence)


def _drop_test_sections(text: str) -> str:
    # Known limit: a wrapped list item whose continuation line has no indent counts as new prose and ends the
    # section early. That fails safe: the remaining test lines are kept and only reach the claim finder.
    kept, skip, fence, seen_item = [], False, False, False
    for line in text.splitlines():
        bare = _QUOTE.sub("", line, count=1)
        if skip:
            if bare.strip().startswith("```"):
                fence = not fence
                continue
            if fence:
                continue
            if _TEST_HEADING.match(bare):
                continue
            if (_ANY_HEADING.match(bare) or _LABEL_LINE.match(bare) or _SECTION_STOP.match(bare)
                    or (bare.strip() and seen_item and not _ITEM.match(bare) and not bare[:1].isspace())):
                skip = False
            else:
                if bare.strip():
                    seen_item = True
                    if keeps_nothing_else_changes(bare):
                        kept.append(line)
                continue
        if _TEST_HEADING.match(bare):
            skip, fence, seen_item = True, False, False
            continue
        kept.append(line)
    return "\n".join(kept)


def about_tests_or_tools(sentence: str) -> bool:
    """True when a matched sentence describes the PR's tests or a tool's output, not product behaviour."""
    if _TEST_SENTENCE.search(sentence):
        return True
    return (bool(_TOOL_SENTENCE.search(sentence)) and not keeps_nothing_else_changes(sentence)
            and not _WORKFLOW.search(sentence))


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
    texts = [("title", title or ""), ("PR description", _drop_test_sections(_clean(body or ""))), *diff_texts(diff)]
    for source, text in texts:
        for name, rx in COMPILED:
            for m in rx.finditer(text):
                if NEGATION.search(text[max(0, m.start() - 40):m.start()]):
                    continue
                line_start = text.rfind("\n", 0, m.start()) + 1
                if text[line_start:].lstrip().startswith("#"):   # a Markdown heading names a topic, not a claim
                    continue
                q = _sentence(text, m.start(), m.end())
                if q and about_tests_or_tools(_sentence(text, m.start(), m.end(), width=10**6)):
                    continue
                if q and (source, q) not in seen:
                    seen.add((source, q))
                    out.append({"source": source, "quote": q, "pattern": name,
                                "_pos": (_SOURCE_ORDER.get(source, 9), m.start())})
    out.sort(key=lambda c: c.pop("_pos"))
    return out


# A probe in one of these states covered no changed lines (poc/probes.classify_item). A stale coverage block that
# still says "adequate" does not put those lines back.
_NO_COVER_STATUS = frozenset({"crashed", "error", "uninformative", "not_run"})


def probe_covers(probe_results: dict | None) -> bool:
    """A probe that ran and has at least one claim expecting 'same' checks behaviour preservation; its result then
    decides (probes never get overruled by this rule). A probe that ran none of the changed lines on the main side
    does not count: not_adequate, a measured coverage of 0, no measured line coverage at all, a crashed, empty,
    uninformative or not_run probe, or a probe whose claim patterns match none of its own observation names."""
    from poc import probes
    for it in (probe_results or {}).get("items") or []:
        if it.get("status") in _NO_COVER_STATUS or it.get("status") == "rejected":
            continue
        if probes.rejection_reason(it):
            continue
        cov = it.get("probe_changed_line_coverage") or {}
        if cov.get("adequacy") == "not_adequate":
            continue
        if cov.get("status") != "measured" or not (cov.get("changed_lines_covered") or 0):
            continue
        if any(c.get("expect") == "same" for c in it.get("claims") or []):
            return True
    return False
