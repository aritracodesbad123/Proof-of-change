"""Seeded "behaviour kept" claim for inputs just past an edited pattern's old match boundary (product checks only).

When a pull request edits an existing pattern (poc/boundary_probes.modified_patterns, recorded under
probe_plan.model_boundary_rule) and one of its testable claims says existing behaviour is preserved, that sentence
is a promise about inputs the PR did not set out to change. This module turns it into one more claim with
expect "same", scoped to inputs just past the old match boundary:

1. seed(claims, rule, test_names): the seeded claims. A source claim must be testable, must not only re-run the PR's
   own test (boundary_probes.reruns_pr_test), and must say existing behaviour is kept (PRESERVE). One seeded claim
   per source claim, id "<source id>-kept".
2. past_boundary(text, old_patterns): an input is just past the boundary when an old pattern matches it and some of
   the input is left outside every match, other than a single trailing newline (a pattern's $ also matches before
   a final newline, so "<Widget>\\n" alone tests nothing).
3. apply(pr_probes, rec, prdir): reads each probe's own input table from its frozen source (a dict literal of string
   names to string inputs) and, for an observation named "<anything>.<input name>" whose input is past the
   boundary and that DIFFERS between base and PR, labels it false_claim under the seeded claim. An observation that
   is the same on both sides is left exactly as it was.

It only ever flags: it never marks anything proven, never removes a red label, and never raises a verdict. It reads
inputs only from code frozen before the PR side ran. Nothing here names a project or package."""
from __future__ import annotations

import ast
import re
from pathlib import Path

from poc.boundary_probes import pr_test_names, reruns_pr_test

PRESERVE = re.compile(
    r"(?ix)\bpreserv\w*\s+(?:the\s+|all\s+)?(?:existing|current|previous|prior|original|old)\s+behaviou?rs?\b"
    r"|\b(?:existing|current|previous|prior|original|old)\s+behaviou?rs?\s+(?:is\s+|are\s+)?"
    r"(?:preserved|kept|unchanged|retained|maintained)\b"
    r"|\bwithout\s+(?:changing|breaking|altering|affecting)\s+(?:the\s+)?(?:existing|current|other)\b"
    r"|\bkeep(?:s|ing)?\s+(?:the\s+)?(?:existing|current)\s+behaviou?rs?\b")
SUFFIX = "-kept"
FALSE_CLAIM = "false_claim"


def says_preserved(text: str) -> bool:
    return bool(PRESERVE.search(text or ""))


def seed(claims: list | None, rule: list | None, test_names: set | None = None) -> list[dict]:
    """Seeded expect-same claims (empty unless an existing pattern was edited and a claim says behaviour is kept)."""
    if not rule:
        return []
    names = test_names or set()
    where = "; ".join(f"{m.get('file')} line {m.get('line')}" for m in rule[:4])
    out = []
    for c in claims or []:
        if not isinstance(c, dict) or not c.get("id") or not c.get("testable", True):
            continue
        text = " ".join(str(c.get(k) or "") for k in ("text", "source_quote"))
        if not says_preserved(text) or reruns_pr_test(c, names):
            continue
        out.append({"id": f"{c['id']}{SUFFIX}", "expect": "same", "testable": True, "seeded_from": c["id"],
                    "source_quote": c.get("source_quote") or c.get("text"),
                    "text": f"Inputs just past the old match boundary of the edited pattern ({where}) give the same "
                            f"result as before (from {c['id']}: existing behaviour preserved)."})
    return out


def past_boundary(text: str, old_patterns: list[str]) -> bool:
    for pat in old_patterns:
        try:
            rx = re.compile(pat)
        except re.error:
            continue
        spans = [m.span() for m in rx.finditer(text) if m.end() > m.start()]
        if not spans:
            continue
        keep = [True] * len(text)
        for a, b in spans:
            for i in range(a, b):
                keep[i] = False
        outside = "".join(ch for ch, k in zip(text, keep) if k)
        if outside.endswith("\n") and text.endswith("\n"):
            outside = outside[:-1]
        if outside:
            return True
    return False


TAILS = (("_pb_space", " tail"), ("_pb_text", "tail"), ("_pb_newline", "\ntail"))


def force_inputs(code: str, old_patterns: list[str]) -> tuple[str, list[str]]:
    """Probe code with past-boundary inputs added, and the names added.

    For every dict literal of string names to string inputs (the probe's input table), each input that an old
    pattern matches with nothing left outside the match gets three siblings: the same input followed by a space and
    text, by text, and by a newline and text (never a bare trailing newline). Names already present are not touched.
    Code with no such table, or no old pattern, comes back unchanged: the model's own probe is never weakened, and
    the base side stays the reference because the added inputs only feed the same calls the model wrote."""
    if not old_patterns or not code:
        return code, []
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return code, []
    added: list[str] = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Dict) and node.keys and all(
                isinstance(k, ast.Constant) and isinstance(k.value, str) for k in node.keys) and all(
                isinstance(v, ast.Constant) and isinstance(v.value, str) for v in node.values)):
            continue
        have = {k.value for k in node.keys}
        for k, v in list(zip(node.keys, node.values)):
            if not _matches(v.value, old_patterns) or past_boundary(v.value, old_patterns):
                continue
            for suf, tail in TAILS:
                name = k.value + suf
                if name in have:
                    continue
                node.keys.append(ast.Constant(name))
                node.values.append(ast.Constant(v.value + tail))
                have.add(name)
                added.append(name)
    if not added:
        return code, []
    return ast.unparse(ast.fix_missing_locations(tree)) + "\n", added


def _matches(text: str, old_patterns: list[str]) -> bool:
    for pat in old_patterns:
        try:
            if any(m.end() > m.start() for m in re.finditer(pat, text)):
                return True
        except re.error:
            continue
    return False


def input_for(name: str, inputs: dict) -> str | None:
    """The input an observation reads: its last dotted part is an input name, or starts or ends with one joined by
    "_" ("adjacent_pb_text_span_count" reads "adjacent_pb_text"). The longest such name wins."""
    key = str(name or "").rsplit(".", 1)[-1]
    if key in inputs:
        return key
    hits = [k for k in inputs if key.startswith(k + "_") or key.endswith("_" + k)]
    return max(hits, key=len) if hits else None


def probe_inputs(source: str) -> dict[str, str]:
    """{input name: input text} from dict literals whose keys and values are all string constants."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return {}
    out: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Dict) and node.keys and all(
                isinstance(k, ast.Constant) and isinstance(k.value, str) for k in node.keys) and all(
                isinstance(v, ast.Constant) and isinstance(v.value, str) for v in node.values):
            for k, v in zip(node.keys, node.values):
                out.setdefault(k.value, v.value)
    return out


def apply(pr_probes: dict | None, rec: dict, prdir: Path | str | None) -> dict | None:
    """pr_probes with past-boundary differences labelled false_claim under a seeded claim, and a fresh summary."""
    if not pr_probes or not pr_probes.get("items") or not rec.get("product_check", True):
        return pr_probes
    plan = rec.get("probe_plan") or {}
    rule = plan.get("model_boundary_rule") or []
    diff = ""
    if prdir and (Path(prdir) / "pr.diff").is_file():
        diff = (Path(prdir) / "pr.diff").read_text(errors="replace")
    seeded = seed(plan.get("model_claims"), rule, pr_test_names(diff))
    if not seeded:
        return pr_probes
    olds = [m["old"] for m in rule if m.get("old")]
    cid = seeded[0]["id"]
    from poc import probes
    items, hits = [], []
    for it in pr_probes["items"]:
        src = Path(prdir) / it["path"] if prdir and it.get("path") else None
        inputs = probe_inputs(src.read_text(errors="replace")) if src and src.is_file() else {}
        new_obs = []
        for o in it.get("observations") or []:
            key = input_for(o.get("name"), inputs)
            if (o.get("state") == "differs" and key is not None and past_boundary(inputs[key], olds)
                    and o.get("label") != FALSE_CLAIM):
                o = dict(o, label=FALSE_CLAIM, claim=cid, linked_by="boundary", advisory=False,
                         note="input just past the edited pattern's old match boundary")
                hits.append(f"{it.get('id')} {o['name']}")
            new_obs.append(o)
        items.append(dict(it, observations=new_obs))
    out = dict(pr_probes, items=items, boundary_claims={"seeded": seeded, "flagged": hits})
    out["summary"] = probes.summarize(items)
    return out
