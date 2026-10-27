"""Product route only: spot a pull request that changes comments or documentation and no code.

The decision is made from the code alone (base and head file contents plus the diff), never from the PR text.

A changed file qualifies when it is
  (a) a Python file whose syntax tree is identical on both sides (comments are not part of the tree, so only
      comments differ), or
  (b) a documentation file that is not Python: *.md, *.rst, *.txt, or any non-.py file under a docs/ folder.

A .py file anywhere (docs/conf.py included) is code. Docstrings are code too, because a program can read them
through __doc__: a Python file that differs only in docstrings is "docstring_only", which the caller checks by
running the project's doc tests. Anything else (other file types, a file that does not parse, a binary file,
a new, deleted or renamed code file) returns None, and the normal check runs unchanged.
"""
from __future__ import annotations

import ast
import re
from typing import Callable

DOC_EXTS = (".md", ".rst", ".txt")
_DIFF_HEAD = re.compile(r"^diff --git a/(\S+) b/(\S+)$", re.M)
_HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")

# PR text that says the code behaves differently. Used only to lower a comment-only result, never to raise one.
BEHAVIOUR_CLAIM = re.compile(
    r"\b(fix(?:es|ed|ing)?|bug(?:fix)?s?|crash(?:es|ed|ing)?|regression|"
    r"adds?|added|adding|implement(?:s|ed)?|introduc(?:e|es|ed)|"
    r"(?:changes?|changed|changing|alters?|altered)\s+(?:the\s+)?(?:behaviou?r|output|result|default)s?|"
    r"behaviou?r\s+change|now\s+(?:returns?|raises?|handles?|supports?)|resolves?|closes?\s+#\d+)\b",
    re.I)


def is_doc_file(path: str) -> bool:
    p = path.replace("\\", "/").lower()
    if p.endswith(".py") or p.endswith(".pyi"):
        return False
    return p.endswith(DOC_EXTS) or p.startswith("docs/") or "/docs/" in p


def split_diff(diff: str) -> dict:
    """{path: {"lines": [head line numbers added or changed], "status": "modified"|"added"|"deleted"|"renamed"|"binary"}}"""
    out: dict = {}
    blocks = list(_DIFF_HEAD.finditer(diff or ""))
    for i, m in enumerate(blocks):
        a, b = m.group(1), m.group(2)
        body = diff[m.end(): blocks[i + 1].start() if i + 1 < len(blocks) else len(diff)]
        status = "modified"
        if a != b or re.search(r"^rename (from|to) ", body, re.M):
            status = "renamed"
        elif re.search(r"^new file mode", body, re.M):
            status = "added"
        elif re.search(r"^deleted file mode", body, re.M):
            status = "deleted"
        if re.search(r"^(Binary files|GIT binary patch)", body, re.M):
            status = "binary"
        lines, cur = [], None
        for ln in body.splitlines():
            h = _HUNK.match(ln)
            if h:
                cur = int(h.group(1))
                continue
            if cur is None or ln.startswith(("+++", "---")):
                continue
            if ln.startswith("+"):
                lines.append(cur); cur += 1
            elif ln.startswith(" "):
                cur += 1
        out[b] = {"lines": lines, "status": status}
    return out


def ranges(nums: list) -> str:
    nums = sorted(set(nums))
    parts, i = [], 0
    while i < len(nums):
        j = i
        while j + 1 < len(nums) and nums[j + 1] == nums[j] + 1:
            j += 1
        parts.append(str(nums[i]) if i == j else f"{nums[i]}\u2013{nums[j]}")
        i = j + 1
    return ", ".join(parts) or "none (only removals)"


def _strip_docstrings(tree: ast.AST) -> ast.AST:
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = node.body
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
                    and isinstance(body[0].value.value, str):
                node.body = body[1:] or [ast.Pass()]
    return tree


def compare_python(base: str, head: str) -> str | None:
    """"comment" when only comments differ, "docstring" when only docstrings (and comments) differ, else None."""
    try:
        tb, th = ast.parse(base), ast.parse(head)
    except (SyntaxError, ValueError):
        return None
    if ast.dump(tb) == ast.dump(th):
        return "comment"
    if ast.dump(_strip_docstrings(tb)) == ast.dump(_strip_docstrings(th)):
        return "docstring"
    return None


def classify(diff: str, read: Callable[[str, str], str | None]) -> dict | None:
    """read(side, path) returns the file text on "base" or "head", or None when it cannot be read.

    Returns {"kind": "comment_only"|"docstring_only", "comments": {path: lines}, "docstrings": {...},
    "docs": {...}, "py_files": [...]} or None for the normal check."""
    files = split_diff(diff)
    if not files:
        return None
    comments, docstrings, docs = {}, {}, {}
    for path, info in files.items():
        if info["status"] == "binary":
            return None
        if is_doc_file(path):
            if info["status"] == "renamed":
                return None
            docs[path] = info["lines"]
            continue
        if not path.endswith(".py") or info["status"] != "modified":
            return None
        base, head = read("base", path), read("head", path)
        if base is None or head is None:
            return None
        kind = compare_python(base, head)
        if kind is None:
            return None
        (comments if kind == "comment" else docstrings)[path] = info["lines"]
    return {"kind": "docstring_only" if docstrings else "comment_only", "comments": comments,
            "docstrings": docstrings, "docs": docs, "py_files": sorted([*comments, *docstrings])}


def describe(result: dict) -> str:
    parts = []
    for label, key in (("comments changed in", "comments"), ("docstrings changed in", "docstrings"),
                       ("docs changed in", "docs")):
        for path, lines in sorted(result[key].items()):
            parts.append(f"{label} {path} lines {ranges(lines)}")
    return "; ".join(parts)


def claimed_behaviour_change(title: str | None, body: str | None) -> str | None:
    """The first phrase in the PR text that says behaviour changed, or None."""
    for text in (title or "", body or ""):
        for m in BEHAVIOUR_CLAIM.finditer(text):
            near = text[m.end(): m.end() + 40]
            if _DOC_TALK.match(near):   # "fix typo in comment", "add docstring": about the text itself
                continue
            return m.group(0)
    return None


_DOC_TALK = re.compile(r"^[\s\w,'-]{0,25}?\b(comments?|docstrings?|docs?|documentation|typos?|readme|"
                       r"wording|spelling|grammar|links?)\b", re.I)


def modules_for(py_files: list) -> list:
    """Dotted module names for the changed files (a src/ prefix is dropped)."""
    out = []
    for f in py_files:
        p = f[4:] if f.startswith("src/") else f
        p = p[:-3]
        if p.endswith("/__init__"):
            p = p[: -len("/__init__")]
        out.append(p.replace("/", "."))
    return out


def doc_test_shell(py_files: list) -> str:
    """Shell run in the sandbox at /work/src: doctests in the changed modules plus tests that import them.

    Exit 5 (nothing collected) means the doc text could not be checked."""
    import shlex
    mods = modules_for(py_files)
    pat = "|".join(re.escape(m) for m in mods)
    files = " ".join(shlex.quote(f) for f in py_files)
    return (
        "set -uo pipefail\ncd /work/src\n"
        f"TESTS=$(grep -rlE --include='test_*.py' --include='*_test.py' "
        f"'(import|from)[[:space:]]+({pat})([[:space:].]|$)' . 2>/dev/null | head -50 | tr '\\n' ' ')\n"
        f"python -m pytest -q -p no:cacheprovider --timeout=300 --doctest-modules {files} $TESTS"
    )
