"""Which Python a Contree check runs on, and whether code parses with that Python's grammar.

The orchestrator may run a newer Python than the sandbox image. Code that parses here (for example a t-string on
3.14) can be a SyntaxError inside the sandbox, so syntax is checked with the grammar of the version that will run it.

The image is picked from the project's own metadata (requires-python and the version classifiers), never from a
per-repository setting: the default image is kept whenever it fits, so checks that already ran keep their Python."""
from __future__ import annotations

import ast
import os
import re
import sys
import warnings

PYTHONS_ENV = "POC_CONTREE_PYTHONS"
DEFAULT_PYTHONS = ("3.10", "3.11", "3.12", "3.13", "3.14")


def _minor(version: str) -> tuple[int, int] | None:
    m = re.fullmatch(r"\s*(\d+)\.(\d+)\s*", version or "")
    return (int(m.group(1)), int(m.group(2))) if m else None


def available_pythons() -> list[str]:
    """Python versions that have a sandbox image (comma-separated POC_CONTREE_PYTHONS, default 3.10 to 3.14)."""
    raw = os.environ.get(PYTHONS_ENV)
    vals = [v.strip() for v in raw.split(",")] if raw else list(DEFAULT_PYTHONS)
    return sorted({v for v in vals if _minor(v)}, key=_minor)


def image_for(version: str, base_image: str) -> str:
    """base_image with its Python X.Y replaced by version (python:3.12-slim-bookworm -> python:3.11-slim-bookworm)."""
    head, _, tag = base_image.rpartition("/")
    new = re.sub(r"^(python:)\d+\.\d+", lambda m: m.group(1) + version, tag, count=1)
    return f"{head}/{new}" if head else new


def grammar_error(code: str, version: str | None) -> str | None:
    """None when code parses with version's grammar, else a one-line reason. ast's feature_version reaches back to
    3.7; a version newer than the running interpreter is parsed with the running grammar."""
    mv = _minor(version or "")
    kw = {}
    if mv and (3, 7) <= mv < sys.version_info[:2]:
        kw["feature_version"] = mv
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            ast.parse(code, **kw)
    except SyntaxError as e:
        where = f" (line {e.lineno})" if e.lineno else ""
        return f"not valid Python {version or 'syntax'}{where}: {e.msg}"
    return None


def choose(specs: list[str], declared: list[str], sources: dict[str, str], base_version: str,
           available: list[str] | None = None) -> dict:
    """Pick the Python the check runs on.

    A version fits when it satisfies every requires-python clause and every changed source file parses with its
    grammar. The base image's version wins when it fits; then the newest fitting classifier version; then the fitting
    version nearest the base. {"version": X.Y or None, "why": plain reason}. version None means no available image
    fits and the check cannot run here."""
    from poc.demo_helper import _py_clauses, _py_satisfies
    available = available if available is not None else available_pythons()
    clauses = [c for s in specs for c in _py_clauses(s)]
    misses: dict[str, str] = {}
    fits = []
    for v in available:
        mv = _minor(v)
        if not _py_satisfies(mv, clauses):
            misses[v] = "outside requires-python " + ", ".join(specs)
            continue
        bad = next(((rel, why) for rel, text in sorted(sources.items()) if (why := grammar_error(text, v))), None)
        if bad:
            misses[v] = f"{bad[0]} is {bad[1]}"
            continue
        fits.append(v)
    if not fits:
        detail = "; ".join(f"{v}: {why}" for v, why in misses.items()) or "no Python image is configured"
        return {"version": None, "why": "not runnable here: no available Python image fits this project ("
                + detail + ")"}
    if base_version in fits:
        return {"version": base_version, "why": f"default image Python {base_version} fits"}
    listed = [v for v in fits if v in {d.strip() for d in declared}]
    if listed:
        v = max(listed, key=_minor)
        return {"version": v, "why": f"Python {v}: newest version the project lists that fits "
                f"(default {base_version}: {misses.get(base_version, 'not available')})"}
    bm = _minor(base_version) or (0, 0)
    v = min(fits, key=lambda x: (abs(_minor(x)[0] * 100 + _minor(x)[1] - bm[0] * 100 - bm[1]), _minor(x)))
    return {"version": v, "why": f"Python {v}: nearest fitting version to the default "
            f"(default {base_version}: {misses.get(base_version, 'not available')})"}
