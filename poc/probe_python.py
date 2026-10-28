"""Which Python a Contree check runs on, and whether code parses with that Python's grammar.

The orchestrator may run a newer Python than the sandbox image. Code that parses here (for example a t-string on
3.14) can be a SyntaxError inside the sandbox, so syntax is checked with the grammar of the version that will run it.

The image is picked from the project's own metadata (requires-python and the version classifiers), never from a
per-repository setting: the default image is kept whenever it fits, so checks that already ran keep their Python."""
from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
import sys

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


_CHECK = ("import sys\n"
          "src = sys.stdin.read()\n"
          "try:\n"
          "    compile(src, '<probe>', 'exec', dont_inherit=True)\n"
          "except SyntaxError as e:\n"
          "    print(f'{e.lineno or 0}\\t{e.msg}')\n")
_INTERPRETERS: dict[str, str | None] = {}
_RESULTS: dict[tuple[str, str], str | None] = {}


def interpreter_for(version: str) -> str | None:
    """Path of a real CPython X.Y on this machine, found (or fetched) with uv; None when there is none.
    POC_PYTHON_X_Y overrides the lookup. Only used to compile text, never to run it."""
    if version in _INTERPRETERS:
        return _INTERPRETERS[version]
    path = os.environ.get("POC_PYTHON_" + version.replace(".", "_"))
    if not path:
        if sys.version_info[:2] == _minor(version):
            path = sys.executable
        else:
            uv = shutil.which("uv")
            for cmd in (["python", "find", version], ["python", "install", "-q", version], ["python", "find", version]):
                if not uv:
                    break
                try:
                    r = subprocess.run([uv, *cmd], capture_output=True, text=True, timeout=300)
                except (OSError, subprocess.TimeoutExpired):
                    break
                if cmd[1] == "find" and r.returncode == 0 and r.stdout.strip():
                    path = r.stdout.strip().splitlines()[-1]
                    break
    _INTERPRETERS[version] = path or None
    return _INTERPRETERS[version]


def grammar_error(code: str, version: str | None) -> str | None:
    """None when code compiles with the real Python `version`, else a one-line reason. The text is compiled (never
    run) by that interpreter itself, so grammar changes that ast's feature_version does not model (for example the
    3.12 f-string rules) are caught. No version: the running interpreter. When no interpreter of that version can be
    found, the check cannot be made and None is returned (the sandbox run still reports a SyntaxError)."""
    v = version if version and _minor(version) else f"{sys.version_info[0]}.{sys.version_info[1]}"
    key = (v, hashlib.sha256(code.encode("utf-8", "surrogatepass")).hexdigest())
    if key in _RESULTS:
        return _RESULTS[key]
    exe = interpreter_for(v)
    out = None
    if exe:
        try:
            r = subprocess.run([exe, "-I", "-S", "-c", _CHECK], input=code, capture_output=True, text=True,
                               timeout=60)
            line = r.stdout.strip()
            if line:
                ln, _, msg = line.partition("\t")
                where = f" (line {ln})" if ln not in ("", "0") else ""
                out = f"not valid Python {version or v}{where}: {msg}"
        except (OSError, subprocess.TimeoutExpired):
            out = None
    _RESULTS[key] = out
    return out


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
