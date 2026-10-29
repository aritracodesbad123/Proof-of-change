"""Modified patterns need probes on inputs just past the old match boundary (product checks only).

A pull request that edits an existing regular expression (a lazy quantifier, a lookahead, an anchor, a narrower
class) can fix the example it was written for and still stop matching text the old pattern matched. The PR's own
test and an "expected: the example now splits" claim are both confirmed in that case, so neither can catch it. What
catches it is the same input with something just past the edge of the old match: a space, other text, or a newline
followed by text. On those inputs the base side is the reference, and the PR side should give the same result.

Rules:

1. modified_patterns(diff): the trigger. It fires only when the diff REPLACES an existing pattern in a source file:
   a removed line and an added line of the same hunk each hold a pattern literal, and the two patterns are close
   enough to be the same pattern edited. A brand-new pattern (an added line with no removed pattern it replaces)
   never fires, and neither does a re-wrap: adjacent string literals are joined first, so a pattern only split
   across literals or lines is the same pattern. Test files (by name or by folder) and non-Python files are ignored.
2. probe_rule(modified, claims): the extra probes-prompt paragraph. It names each modified pattern by its BASE-side
   file, line and old text only (never the new text: probes are written from the PR text and base-side code), and
   asks for observations on inputs just past the old match boundary, including the "<Widget>\\nnext" form (text
   after the newline: a pattern's "$" also matches before a bare trailing newline, so "<Widget>\\n" alone tests
   nothing). Base is the reference: the full result is recorded so plain code compares base and PR.
3. eligible_claims(claims, diff): the claims the paragraph may suggest for those observations: testable claims
   that expect "same" and do not only re-run the PR's own test (a test-outcome sentence, or one naming a test the
   diff adds). A re-run of the PR's test is confirmed by design and says nothing about nearby inputs.

The paragraph only suggests: the model still links each probe to claims itself, and nothing here links a probe to a
claim (no auto-linking). The rule changes the prompt only; judging and the verdict are unchanged. Study runs never
call this module. Nothing here names a project or package."""
from __future__ import annotations

import difflib
import re

from poc import claim_hygiene

# String literals. Adjacent literals (only spaces, newlines, comments or a line continuation between them) are one
# string to Python, so they are joined before anything is compared: splitting a pattern across two literals is a
# re-wrap, not an edit.
_LIT = re.compile(r"""(?P<p>[rRbBuU]{0,2})(?P<q>['"])(?P<s>(?:\\.|(?!(?P=q)).)*)(?P=q)""")
_GAP = re.compile(r"(?:\s|\\\n|#[^\n]*)*\Z")
_RE_CALL = re.compile(r"\bre\.(?:compile|match|search|fullmatch|findall|finditer|sub|subn|split)\(\s*\Z")
_REGEX_TOKEN = re.compile(r"\\[wdsbWDSBAZ]|\(\?|[*+?]\)?|\[[^\]]*\]|\|")
SIMILAR = 0.6
_HUNK = re.compile(r"^@@ -(\d+)(?:,\d+)? \+\d+(?:,\d+)? @@")
_TEST_NAME = re.compile(r"^\+\s*(?:async\s+)?def\s+(test\w*)\s*\(", re.M)


def _patterns(lines: list[str]) -> list[tuple[int, str]]:
    """Pattern literals in some lines of code, adjacent literals joined: [(index of the first line, text)]. A pattern
    is a joined literal holding a regex token that is raw, or passed straight to a re function."""
    text = "\n".join(lines)
    runs: list[list] = []   # [start, end, text, raw]
    for m in _LIT.finditer(text):
        raw = "r" in m.group("p").lower()
        if runs and _GAP.match(text[runs[-1][1]:m.start()]):
            runs[-1][1:] = [m.end(), runs[-1][2] + m.group("s"), runs[-1][3] or raw]
        else:
            runs.append([m.start(), m.end(), m.group("s"), raw])
    out = []
    for start, _end, s, raw in runs:
        if (raw or _RE_CALL.search(text[:start])) and _REGEX_TOKEN.search(s) and s not in [x for _, x in out]:
            out.append((text.count("\n", 0, start), s))
    return out


def _is_source(path: str | None) -> bool:
    if not path or not path.endswith(".py"):
        return False
    parts = path.split("/")
    name = parts[-1]
    return not (name.startswith("test_") or name.endswith("_test.py") or name == "conftest.py"
                or any(p in ("tests", "test", "testing") for p in parts[:-1]))


def _hunks(diff: str):
    """Yield (path, [(base line, removed text)], [added text]) per hunk of a unified diff."""
    path, base_no, removed, added = None, 0, [], []
    for raw in (diff or "").splitlines():
        if raw.startswith("diff --git") or raw.startswith("--- "):
            if removed or added:
                yield path, removed, added
            removed, added = [], []
            if raw.startswith("diff --git"):
                path = None
            continue
        if raw.startswith("+++ "):
            p = raw[4:].strip()
            path = p[2:] if p.startswith("b/") else (None if p == "/dev/null" else p)
            continue
        m = _HUNK.match(raw)
        if m:
            if removed or added:
                yield path, removed, added
            removed, added, base_no = [], [], int(m.group(1))
            continue
        if raw.startswith("-"):
            removed.append((base_no, raw[1:]))
            base_no += 1
        elif raw.startswith("+"):
            added.append(raw[1:])
        else:
            base_no += 1
    if removed or added:
        yield path, removed, added


def modified_patterns(diff: str | None) -> list[dict]:
    """Existing patterns the diff edits: [{file, line, old}] (base side only). Brand-new patterns are not listed."""
    out = []
    for path, removed, added in _hunks(diff or ""):
        if not _is_source(path):
            continue
        new = [x for _, x in _patterns(added)]
        if not new:
            continue
        for i, old in _patterns([t for _, t in removed]):
            if old in new:   # the same pattern, only re-indented, re-wrapped or split across literals
                continue
            if any(difflib.SequenceMatcher(None, old, n).ratio() >= SIMILAR for n in new):
                out.append({"file": path, "line": removed[i][0], "old": old})
    return out


def pr_test_names(diff: str | None) -> set[str]:
    """Names of test functions the diff adds."""
    return set(_TEST_NAME.findall(diff or ""))


def reruns_pr_test(claim: dict, test_names: set[str]) -> bool:
    """A claim that only says a test passes, or names a test the PR adds."""
    text = " ".join(str(claim.get(k) or "") for k in ("text", "source_quote"))
    return claim_hygiene.is_test_outcome_claim(text) or any(t in text for t in test_names)


def eligible_claims(claims: list | None, diff: str | None) -> list[str]:
    """Ids of testable claims that expect 'same' and do not only re-run the PR's own test."""
    names = pr_test_names(diff)
    return [str(c["id"]) for c in claims or [] if isinstance(c, dict) and c.get("id") and c.get("testable", True)
            and c.get("expect", "same") == "same" and not reruns_pr_test(c, names)]


def probe_rule(diff: str | None, claims: list | None) -> str:
    """Extra probes-prompt text when the PR edits an existing pattern ('' otherwise)."""
    mods = modified_patterns(diff)
    if not mods:
        return ""
    where = "; ".join(f"{m['file']} line {m['line']}: {m['old']!r}" for m in mods[:4])
    ids = eligible_claims(claims, diff)
    link = (f" Link these observations to the claim(s) among {', '.join(ids)} that say behaviour is kept, if one does."
            if ids else " If no claim says behaviour is kept, give the probe an empty claims list.")
    return ("\n\nModified pattern: this pull request edits an existing pattern in the BASE-side code (" + where + "). "
            "An edited pattern can stop matching text it matched before. Write at least one probe that records the "
            "full result on inputs just past the boundary of the old match, where the base side is the reference "
            "and the PR side should give the same result: a match followed by a space, by other text, by a newline "
            "with text after it (the form \"<Widget>\\nnext\", not a bare trailing newline, because a pattern's $ "
            "also matches before a final newline), and preceded by text. Name each observation "
            "'<claim id or probe id>.<short input name>'. Do not re-run or copy the PR's own tests: they are not "
            "nearby inputs." + link)
