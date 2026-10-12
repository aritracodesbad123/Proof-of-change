"""Release notes trimmed to ONE version's own section, for release-pair checks (old wheel vs new wheel).

A release-notes page often covers several releases: scikit-learn's whats_new/v1.5.html holds 1.5.0, 1.5.1 and 1.5.2.
When checking 1.4.2 -> 1.5.0, the 1.5.1 and 1.5.2 sections describe fixes made AFTER 1.5.0, often for bugs that 1.5.0
introduced. They are part of the answer, so they must never reach a generator. The trimming is done here, by
structure, before any text is built; the answer-key firewall is only a second line of defence.

The inputs file (release-pairs CSV) says what to keep in its `notes_scope` column:

    "whole page (single-version page)"            keep the page's main content (role="main", <main>, or <body>)
    "ONLY the section id=version-1-5-0; ..."      keep only the HTML element with that id, minus any nested section
                                                  of another version

`read_pairs` refuses any file whose name contains "answers" (the release answer key is for the scorer only).
Standard library only (html.parser).
"""
from __future__ import annotations

import csv
import re
from html.parser import HTMLParser
from pathlib import Path

SECTION_RE = re.compile(r"\bsection\s+id=([A-Za-z0-9_.:-]+)")
SKIP_TAGS = {"script", "style", "nav", "header", "footer", "aside", "noscript", "template"}
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}
BLOCK = {"p", "div", "section", "li", "h1", "h2", "h3", "h4", "h5", "h6", "dt", "dd", "pre", "tr", "br", "ul", "ol"}
VERSION_ID_RE = re.compile(r"^version-\d")


class ScopeError(ValueError):
    pass


def read_pairs(path: str | Path) -> list[dict]:
    p = Path(path)
    for name in (p.name, p.resolve().name):
        if "answers" in name.lower():
            raise PermissionError(f"refusing to read {name}: generator code never reads an answer key")
    with open(p, newline="") as fh:
        rows = list(csv.DictReader(fh))
    for r in rows:
        if "notes_scope" not in r:
            raise ScopeError(f"{p.name}: no notes_scope column")
    return rows


def parse_scope(notes_scope: str) -> dict:
    """{"kind": "section", "id": ...} or {"kind": "page"}. Anything else is refused rather than guessed."""
    s = (notes_scope or "").strip()
    m = SECTION_RE.search(s)
    if m:
        return {"kind": "section", "id": m.group(1).rstrip(".;,")}
    if s.lower().startswith("whole page"):
        return {"kind": "page"}
    raise ScopeError(f"unknown notes_scope {notes_scope!r}: refusing to guess what part of the page to keep")


class _Extract(HTMLParser):
    """Collects text inside the element with id=target (or inside <main>/<article>/<body> for a whole page), skipping
    navigation, scripts, and nested sections whose id names another version."""

    def __init__(self, target: str | None, match=None):
        super().__init__(convert_charrefs=True)
        self.target, self.depth, self.skip, self.found = target, 0, 0, False
        self.match = match or (lambda tag, a: a.get("id") == target)
        self.stack: list[str] = []
        self.parts: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in VOID:
            if self.depth and not self.skip and tag == "br":
                self.parts.append("\n")
            return
        a = dict(attrs)
        self.stack.append(tag)
        if self.depth:
            self.depth += 1
            if self.skip:
                self.skip += 1
            elif tag in SKIP_TAGS or "headerlink" in (a.get("class") or "").split() or (
                    self.target and a.get("id") and VERSION_ID_RE.match(a["id"]) and a["id"] != self.target):
                self.skip = 1
            elif tag in BLOCK:
                self.parts.append("\n")
        elif not self.found and self.match(tag, a):
            self.depth, self.found = 1, True

    def handle_endtag(self, tag):
        if tag in VOID or not self.stack:
            return
        # tolerate unclosed tags: pop up to the matching start tag
        while self.stack:
            top = self.stack.pop()
            if self.depth:
                self.depth -= 1
                if self.skip:
                    self.skip -= 1
            if top == tag:
                break

    def handle_data(self, data):
        if self.depth and not self.skip:
            self.parts.append(data)


def _clean(text: str) -> str:
    lines = [" ".join(ln.split()) for ln in text.replace("¶", "").splitlines()]
    out, blank = [], False
    for ln in lines:
        if ln:
            out.append(ln)
            blank = False
        elif not blank and out:
            out.append("")
            blank = True
    return "\n".join(out).strip() + "\n"


def trim(html: str, notes_scope: str) -> str:
    """Plain text of the part of a release-notes page that notes_scope allows. Raises ScopeError if that part is
    missing (never falls back to the whole page)."""
    scope = parse_scope(notes_scope)
    if scope["kind"] == "section":
        ex = _Extract(scope["id"])
        ex.feed(html)
        ex.close()
        if not ex.found:
            raise ScopeError(f"section id={scope['id']} not found on the page")
        return _clean("".join(ex.parts))
    # whole page: the main content area (role="main", else <main>, else the whole body), minus navigation
    for match in (lambda tag, a: a.get("role") == "main", lambda tag, a: tag == "main", lambda tag, a: tag == "body"):
        ex = _Extract(None, match)
        ex.feed(html)
        ex.close()
        if ex.found:
            return _clean("".join(ex.parts))
    ex = _Extract(None)
    ex.depth, ex.found = 1, True
    ex.feed(html)
    ex.close()
    return _clean("".join(ex.parts))
