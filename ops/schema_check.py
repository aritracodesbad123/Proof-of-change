"""Minimal stdlib JSON Schema (2020-12 subset) validator for harness/schema/observation.schema.json.

Supports exactly the keywords the shared schema uses: type, required, properties, items, enum, const, pattern,
minimum, minLength, if/then/else. Annotation keywords ($schema, $id, title, description, x-*) are ignored. Any other
keyword raises, so the schema cannot silently grow beyond what is checked. JSON booleans never count as numbers.
"""
from __future__ import annotations

import re

_TYPES = {"object": dict, "array": list, "string": str, "integer": int, "number": (int, float), "boolean": bool,
          "null": type(None)}
_CHECKED = {"type", "required", "properties", "items", "enum", "const", "pattern", "minimum", "minLength",
            "if", "then", "else"}
_ANNOTATIONS = {"$schema", "$id", "title", "description"}


def _is(v, t: str) -> bool:
    if t in ("integer", "number") and isinstance(v, bool):
        return False
    return isinstance(v, _TYPES[t])


def _errors(v, sch: dict, path: str) -> list[str]:
    unknown = {k for k in sch if k not in _CHECKED and k not in _ANNOTATIONS and not k.startswith("x-")}
    if unknown:
        raise ValueError(f"unsupported schema keyword(s) at {path}: {sorted(unknown)}")
    errs: list[str] = []
    if "type" in sch:
        ts = sch["type"] if isinstance(sch["type"], list) else [sch["type"]]
        if not any(_is(v, t) for t in ts):
            return [f"{path}: expected {'/'.join(ts)}, got {type(v).__name__}"]
    if "enum" in sch and v not in sch["enum"]:
        errs.append(f"{path}: {v!r} not in {sch['enum']}")
    if "const" in sch and v != sch["const"]:
        errs.append(f"{path}: {v!r} != {sch['const']!r}")
    if isinstance(v, str):
        if "pattern" in sch and not re.search(sch["pattern"], v):
            errs.append(f"{path}: {v!r} does not match {sch['pattern']}")
        if "minLength" in sch and len(v) < sch["minLength"]:
            errs.append(f"{path}: shorter than {sch['minLength']}")
    if "minimum" in sch and isinstance(v, (int, float)) and not isinstance(v, bool) and v < sch["minimum"]:
        errs.append(f"{path}: {v} < {sch['minimum']}")
    if isinstance(v, dict):
        for k in sch.get("required", []):
            if k not in v:
                errs.append(f"{path}: missing required field {k!r}")
        for k, sub in sch.get("properties", {}).items():
            if k in v:
                errs += _errors(v[k], sub, f"{path}.{k}")
    if isinstance(v, list) and "items" in sch:
        for i, x in enumerate(v):
            errs += _errors(x, sch["items"], f"{path}[{i}]")
    if "if" in sch:
        branch = "then" if not _errors(v, sch["if"], path) else "else"
        if branch in sch:
            errs += _errors(v, sch[branch], path)
    return errs


def validate(record: dict, schema: dict) -> list[str]:
    """List of validation errors (empty = valid)."""
    return _errors(record, schema, "$")
