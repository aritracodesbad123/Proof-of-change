"""Whether a probe's calls can reach a change that adds an argument to an internal helper.

An internal helper is a function whose name starts with a single underscore. When the diff gives that helper a new
parameter, a probe that calls the helper must pass the new parameter, or call a public entry point the diff now uses
to pass it (a function that does not start with a single underscore, or ``__init__`` / the class name). Otherwise
the probe is marked unable to reach the change: the inputs it uses are ones the old and new helper signatures do
not both see.
"""
from __future__ import annotations

import ast
import re

_DEF = re.compile(r"^(?:async\s+)?def\s+(\w+)\s*\((.*)\)\s*(?:->[^:]*)?:\s*(?:#.*)?$")
_CLASS = re.compile(r"^class\s+(\w+)\b")
_HUNK = re.compile(r"^@@ .*@@\s*(.*)$")


def _is_internal(name: str) -> bool:
    return name.startswith("_") and not name.startswith("__")


def _is_public(name: str) -> bool:
    return name == "__init__" or not name.startswith("_")


def _params(sig: str) -> list[str]:
    """Parameter names of a def signature, in order. ``*`` and ``**`` names are kept."""
    parts, buf, depth = [], "", 0
    for ch in sig:
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth = max(0, depth - 1)
        if ch == "," and depth == 0:
            parts.append(buf.strip())
            buf = ""
        else:
            buf += ch
    if buf.strip():
        parts.append(buf.strip())
    names = []
    for part in parts:
        name = part.split(":", 1)[0].split("=", 1)[0].strip().lstrip("*")
        if name and name != "/":
            names.append(name)
    return names


def _header_fn(rest: str) -> tuple[str | None, str | None]:
    """(class, function) named by a hunk header's trailing context, if any."""
    rest = (rest or "").strip()
    if rest.startswith("class "):
        name = rest.split()[1].split("(")[0].split(":")[0]
        return name, None
    if rest.startswith("def ") or rest.startswith("async def "):
        m = re.match(r"(?:async\s+)?def\s+(\w+)", rest)
        return None, m.group(1) if m else None
    return None, None


def signature_changes(diff: str) -> list[dict]:
    """Functions whose parameter list grew: {name, added, public}.

    ``added`` is the new parameter names. ``public`` is the public entry points (function or class names) whose
    added lines pass one of those parameters into something else."""
    removed: dict[str, list[str]] = {}
    added: dict[str, list[str]] = {}
    for raw in (diff or "").splitlines():
        if not raw or raw[0] not in "+-" or raw.startswith(("+++", "---")):
            continue
        m = _DEF.match(raw[1:].strip())
        if not m:
            continue
        (added if raw[0] == "+" else removed)[m.group(1)] = _params(m.group(2))
    grew = []
    for name, new in added.items():
        old = removed.get(name)
        if old is None:
            continue
        extra = [p for p in new if p not in old]
        if extra and _is_internal(name):
            grew.append({"name": name, "old": old, "new": new, "added": extra, "public": set()})
    if not grew:
        return []
    by_name = {c["name"]: c for c in grew}
    current_class, current_fn = None, None
    for raw in (diff or "").splitlines():
        if raw.startswith("@@"):
            current_fn = None
            hm = _HUNK.match(raw)
            cls, fn = _header_fn(hm.group(1) if hm else "")
            if cls:
                current_class, current_fn = cls, None
            elif fn:
                current_fn = fn
            continue
        if not raw or raw[0] == "-" or raw.startswith("+++"):
            continue
        text = raw[1:].strip() if raw[0] in "+ " else raw.strip()
        cm = _CLASS.match(text)
        if cm:
            current_class, current_fn = cm.group(1), None
            continue
        dm = _DEF.match(text)
        if dm:
            current_fn = dm.group(1)
            continue
        if not raw.startswith("+"):
            continue
        for ch in grew:
            if current_fn == ch["name"] or not current_fn or not _is_public(current_fn):
                continue
            if any(re.search(rf"\b{re.escape(p)}\b", text) for p in ch["added"]):
                ch["public"].add(current_fn)
                if current_fn == "__init__" and current_class:
                    ch["public"].add(current_class)
    return list(by_name.values())


def _calls(tree: ast.AST) -> list[dict]:
    out = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = node.func.attr if isinstance(node.func, ast.Attribute) else (node.func.id if isinstance(node.func, ast.Name) else "")
        if not name:
            continue
        out.append({"name": name, "ctor": isinstance(node.func, ast.Name),
                    "npos": len(node.args), "keywords": {k.arg for k in node.keywords if k.arg}})
    return out


def _passes(call: dict, change: dict) -> bool:
    """True when this call supplies every parameter the diff added."""
    params = list(change["new"])
    if not call["ctor"] and params and params[0] in ("self", "cls"):
        params = params[1:]
    added = set(change["added"])
    for i, name in enumerate(params):
        if name not in added:
            continue
        if name in call["keywords"] or call["npos"] > i:
            continue
        return False
    return True


def _uses_public(calls: list[dict], change: dict) -> bool:
    public = change["public"]
    return any(c["name"] in public for c in calls)


def unable_to_reach(code: str, diff: str) -> str | None:
    """A plain reason when the probe calls a changed internal helper without the new arguments and without a
    public entry point, else None."""
    changes = signature_changes(diff)
    if not changes or not (code or "").strip():
        return None
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return None
    calls = _calls(tree)
    missed = []
    for change in changes:
        direct = [c for c in calls if c["name"] == change["name"]]
        if not direct or all(_passes(c, change) for c in direct):
            continue
        if _uses_public(calls, change):
            continue
        missed.append(change)
    if not missed:
        return None
    bits = [f"calls `{c['name']}` without the new argument {', '.join(f'`{p}`' for p in c['added'])}" for c in missed]
    return ("unable to reach the change: " + "; ".join(bits)
            + ", and does not go through a public entry point")
