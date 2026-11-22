"""Inputs that can reach a changed branch, taken from base-side source only.

Two kinds of seed, both read as syntax (the files are not imported and nothing is executed):

* a literal argument of a call the base already makes (a string, number, or bool);
* a formatter round-trip. A call such as ``parser(value.isoformat())`` or
  ``parser(value.strftime("%Y-%m-%d"))`` is recorded, and a fixed aware datetime is
  formatted the same way so a probe can pass that string in. The fixed instant is only
  a stand-in for "whatever the formatter returns"; it is not a project-specific case.

A probe that raises on every input never reached the branch. That is decided when the
probe is judged (poc/probes.py), not here.
"""
from __future__ import annotations

import ast
import datetime as dt

# A fixed aware instant. Its formatted form is deterministic and needs no clock.
_FIXED = dt.datetime(2020, 1, 2, 3, 4, 5, tzinfo=dt.timezone.utc)
_FORMATTERS = {"isoformat", "strftime"}


def _const(node) -> object:
    if isinstance(node, ast.Constant) and isinstance(node.value, (str, int, float, bool)):
        return node.value
    return None


def _formatter_value(node: ast.AST) -> str | None:
    """The string a formatter call would produce for the fixed instant, or None."""
    if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
        return None
    name = node.func.attr
    if name == "isoformat":
        return _FIXED.isoformat()
    if name == "strftime" and node.args:
        fmt = _const(node.args[0])
        if not isinstance(fmt, str):
            return None
        try:
            return _FIXED.strftime(fmt)
        except (TypeError, ValueError):
            return None
    return None


def _is_formatter_call(node: ast.AST) -> bool:
    return (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            and node.func.attr in _FORMATTERS)


def seeds_from_source(source: str) -> dict:
    """Literals and formatter round-trips in one base file.

    ``literals`` are constant arguments of calls, in source order, without duplicates.
    ``round_trips`` are the source of calls whose argument is a formatter call, such as
    ``isoparse(date.isoformat())``. ``round_trip_values`` are the strings those formatters
    produce for the fixed instant, which a probe can pass without running the base file.
    """
    try:
        tree = ast.parse(source or "")
    except SyntaxError:
        return {"literals": [], "round_trips": [], "round_trip_values": []}
    literals: list = []
    trips: list[str] = []
    values: list[str] = []
    for node in ast.walk(tree):
        if _is_formatter_call(node):
            value = _formatter_value(node)
            if isinstance(value, str) and value not in values:
                values.append(value)
        if not isinstance(node, ast.Call):
            continue
        saw_formatter = False
        for arg in list(node.args) + [k.value for k in node.keywords if k.arg]:
            got = _const(arg)
            if isinstance(got, str) and got and got not in literals:
                literals.append(got)
            elif isinstance(got, (int, float, bool)) and got not in literals:
                literals.append(got)
            if _is_formatter_call(arg):
                saw_formatter = True
        if saw_formatter:
            try:
                text = ast.unparse(node)
            except (AttributeError, ValueError):
                text = ""
            if text and text not in trips:
                trips.append(text)
    return {"literals": literals, "round_trips": trips, "round_trip_values": values}


def seed_literals(source: str) -> list:
    """String and number seeds a probe can pass: call literals, then formatter values.

    Capped so one large test file cannot flood a probe. Formatter values come after the
    literals the file already passes, and a value already listed is not repeated."""
    found = seeds_from_source(source)
    out = []
    for item in list(found["literals"]) + list(found["round_trip_values"]):
        if item not in out:
            out.append(item)
        if len(out) >= 12:
            break
    return out


def inject_seeds(code: str, literals: list) -> tuple[str, list[str]]:
    """Add missing literal seeds to a probe's string input table.

    A dict of string names to string inputs gains ``seed0``, ``seed1``, ... Values already
    present are left as they are. A list is not touched: a list of claim ids is not an input
    table. Code that does not parse, or that has no such table, comes back unchanged.
    """
    strings = [s for s in literals if isinstance(s, str) and s]
    if not code or not strings:
        return code, []
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return code, []
    added: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Dict) and node.keys and all(
                isinstance(k, ast.Constant) and isinstance(k.value, str) for k in node.keys) and all(
                isinstance(v, ast.Constant) and isinstance(v.value, str) for v in node.values):
            have = {v.value for v in node.values}
            names = {k.value for k in node.keys}
            for text in strings:
                if text in have:
                    continue
                key = "seed0"
                n = 0
                while key in names:
                    n += 1
                    key = f"seed{n}"
                node.keys.append(ast.Constant(key))
                node.values.append(ast.Constant(text))
                names.add(key)
                have.add(text)
                added.append(key)
    if not added:
        return code, []
    return ast.unparse(ast.fix_missing_locations(tree)) + "\n", added
