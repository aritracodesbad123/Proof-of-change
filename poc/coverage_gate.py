"""Coverage gate: 'verified' must mean the PR's changed code was actually exercised by the tests that ran.

Pure functions, shared by ops/daily_run.py (live runs and --report-only rebuilds) and reports/pr_report.py.

Rules (only a 'verified' verdict is ever changed; needs_attention / could_not_verify are kept as they are):
  * compiled sources changed (C/C++/Cython/Fortran) and the PR adds or changes no test for the changed module
      -> could_not_verify ("not fully verified: compiled code changed ..."). coverage.py cannot see compiled code.
  * Python changes, coverage measured, 0 changed executable lines executed
      -> could_not_verify ("not fully verified: changed code never ran ...")
  * Python changes, coverage measured, under 50% -> verdict kept, confidence lowered, the number is reported
  * Python changes, coverage not measured (old records, or the coverage run failed) -> verdict kept, confidence
      lowered, stated as 'not measured'
  * no executable change (docs, tests, config only) -> verdict kept, with a note
The verdict before the gate is kept in the record (verdict_before_coverage_gate), so applying it twice is harmless.
"""
from __future__ import annotations

import ast
import difflib
import re
from pathlib import PurePosixPath

LOW = 0.5
COMPILED_EXT = (".c", ".h", ".cc", ".cpp", ".cxx", ".hpp", ".hh", ".pyx", ".pxd", ".pxi", ".f", ".f90", ".cu",
                ".src", ".inc")
NOT_SHIPPED = ("doc", "docs", "benchmarks", "asv_bench", "bench", "examples", "ci", "tools", "scripts", ".github",
               "tests", "test", "testing")


def is_test(path: str) -> bool:
    p = PurePosixPath(path)
    return (any(part in ("tests", "test") for part in p.parts[:-1]) or p.name.startswith("test_")
            or p.name.endswith("_test.py") or p.name == "conftest.py")


def _shipped(path: str) -> bool:
    p = PurePosixPath(path)
    return not is_test(path) and not (p.parts and p.parts[0] in NOT_SHIPPED) and p.name != "setup.py"


def python_sources(files: dict) -> list[str]:
    """Changed non-test Python files that ship with the library (what coverage should see)."""
    return [f for f in files.get("all", []) if f.endswith(".py") and _shipped(f)]


def compiled_sources(files: dict) -> list[str]:
    """Changed compiled sources (not build config such as meson.build/pyproject.toml)."""
    return [f for f in files.get("all", []) if f.lower().endswith(COMPILED_EXT) and _shipped(f)]


def test_files(files: dict) -> list[str]:
    return [f for f in files.get("all", []) if is_test(f) and f.endswith(".py")]


def _stem(path: str) -> str:
    s = PurePosixPath(path).name.split(".")[0]
    return re.sub(r"^_+|module$", "", s).lower()


def tests_for_compiled(files: dict) -> dict:
    """{compiled file: [changed test files that target it]}. A test targets the module when its file name contains
    the compiled file's stem (item_selection.c -> test_item_selection.py) or the stem of its directory."""
    tests = test_files(files)
    out = {}
    for c in compiled_sources(files):
        keys = {_stem(c), PurePosixPath(c).parent.name.lstrip("_").lower()} - {"", "src", "include", "core", "lib"}
        out[c] = [t for t in tests if any(k in PurePosixPath(t).name.lower() for k in keys)]
    return out


def _strip_docstrings(node: ast.AST) -> None:
    """Drop a module, class or function docstring so two files that differ only there compare equal."""
    for child in ast.walk(node):
        body = getattr(child, "body", None)
        if not body or not isinstance(body, list):
            continue
        first = body[0]
        if isinstance(first, ast.Expr) and isinstance(getattr(first, "value", None), ast.Constant):
            if isinstance(first.value.value, str):
                del body[0]


def ast_equal_ignoring_docstrings(old_text: str, new_text: str) -> bool:
    """True when the two Python sources have the same AST once docstrings are removed.

    A change that only rewrites a docstring (the text of a function, class or module string) does not change
    behaviour. Syntax that does not parse is not treated as docstring-only."""
    try:
        old, new = ast.parse(old_text), ast.parse(new_text)
    except SyntaxError:
        return False
    _strip_docstrings(old)
    _strip_docstrings(new)
    return ast.dump(old) == ast.dump(new)


def changed_lines(old_text: str | None, new_text: str) -> set[int]:
    """1-based line numbers of new_text that are added or changed relative to old_text (whole file if new)."""
    new = new_text.splitlines()
    if old_text is None:
        return set(range(1, len(new) + 1))
    out: set[int] = set()
    for tag, _i1, _i2, j1, j2 in difflib.SequenceMatcher(None, old_text.splitlines(), new, autojunk=False).get_opcodes():
        if tag in ("replace", "insert"):
            out.update(range(j1 + 1, j2 + 1))
    return out


def measure(changed: dict, cov_files: dict) -> dict:
    """changed: {relative path: set(changed line numbers)}; cov_files: coverage.py JSON 'files' mapping.
    Executable lines are coverage's executed + missing lines. Returns the record's coverage block."""
    per_file, tot, hit = [], 0, 0
    for rel, lines in sorted(changed.items()):
        key = next((k for k in cov_files if k == rel or k.replace("\\", "/").endswith("/" + rel)), None)
        if key is None:
            per_file.append({"file": rel, "changed_lines_total": None, "changed_lines_covered": None,
                             "note": "file not measured by coverage"})
            continue
        f = cov_files[key]
        execd = set(f.get("executed_lines", []))
        exe = execd | set(f.get("missing_lines", []))
        t, h = len(lines & exe), len(lines & execd)
        tot, hit = tot + t, hit + h
        per_file.append({"file": rel, "changed_lines_total": t, "changed_lines_covered": h})
    return {"status": "measured", "changed_lines_total": tot, "changed_lines_covered": hit, "files": per_file}


def _fmt(cov: dict) -> str:
    t, h = cov.get("changed_lines_total"), cov.get("changed_lines_covered")
    return f"{h} of {t} changed executable line(s) ran ({round(100 * h / t)}%)" if t else "no changed executable lines"


PRODUCT_NOT_MEASURED = "Coverage wasn't measured, so this can't be marked verified"
PRODUCT_COMPILED_ONLY = "This change touches compiled code that coverage can't measure, so it can't be marked verified"
MEASUREMENTS = ("measured", "not measured: predates gate", "not measured", "not needed")


def measurement(rec: dict, has_python: bool = True) -> str:
    """Where the coverage numbers come from: 'measured' (a real coverage.py run of the PR side), 'not measured:
    predates gate' (the record was made before the coverage gate existed; there is no run at all), 'not measured'
    (the run was skipped or failed; see coverage.why), 'not needed' (no changed Python lines)."""
    cov = rec.get("coverage")
    if cov and cov.get("status") == "measured":
        return "measured"
    if not has_python or (cov or {}).get("status") == "not needed":
        return "not needed"
    return "not measured" if cov else "not measured: predates gate"


def assess(rec: dict) -> dict:
    """The gate's view of one record: kind, measured numbers, verdict to use, note, confidence."""
    files = rec.get("files")
    base = rec.get("verdict_before_coverage_gate", rec.get("verdict"))
    base_reason = rec.get("reason_before_coverage_gate", rec.get("reason", ""))
    if not isinstance(files, dict) or "all" not in files:
        return {"kind": "unknown", "verdict": base, "reason": base_reason, "changed": False, "confidence": "normal",
                "measurement": measurement(rec),
                "changed_lines_total": None, "changed_lines_covered": None, "python_files": [], "compiled_files": [],
                "note": "the record does not list the changed files, so the coverage gate could not be applied"}
    py, comp = python_sources(files), compiled_sources(files)
    cov = rec.get("coverage") or {}
    measured = cov.get("status") == "measured"
    g = {"python_files": py, "compiled_files": comp, "verdict": base, "reason": base_reason, "changed": False,
         "confidence": "normal", "changed_lines_total": cov.get("changed_lines_total") if measured else None,
         "changed_lines_covered": cov.get("changed_lines_covered") if measured else None}
    notes = []
    untested_compiled = [c for c, ts in tests_for_compiled(files).items() if not ts]
    if comp:
        g["kind"] = "compiled" if not py else "compiled+python"
        if untested_compiled:
            notes.append(f"compiled code changed ({', '.join(untested_compiled)}); coverage.py cannot see compiled "
                         "code and the PR adds or changes no test for it")
    elif py:
        g["kind"] = "python"
    else:
        g["kind"] = "no-executable-change"
        notes.append("no executable code changed (docs, tests or config only), so there was nothing to cover")
    g["measurement"] = measurement(rec, bool(py))
    if py:
        if not measured:
            notes.append("coverage of the changed Python lines was NOT MEASURED"
                         + (f" ({cov['why']})" if cov.get("why") else
                            " (record predates the coverage gate: no coverage run exists for it, so this is not a "
                            "measurement result)"))
            g["confidence"] = "lower"
        elif not cov.get("changed_lines_total"):
            notes.append("the changed Python lines are not executable (comments, docstrings, blank lines)")
        else:
            frac = cov["changed_lines_covered"] / cov["changed_lines_total"]
            notes.append(_fmt(cov))
            if 0 < frac < LOW:
                g["confidence"] = "lower"
    g["note"] = "; ".join(notes)
    if base != "verified":
        return g
    if rec.get("product_check") and comp:
        # Product checks only: coverage.py cannot see compiled code, so any change touching compiled code
        # (even mixed with Python) cannot be verified. Study runs never set product_check, so they are unchanged.
        g.update(verdict="could_not_verify", changed=True, confidence="none",
                 reason=f"{PRODUCT_COMPILED_ONLY} (compiled files: {', '.join(comp)}) (tests: {base_reason})")
        return g
    if rec.get("product_check") and py and not measured:
        # Product checks only: a verified result needs coverage that was actually measured. Study runs never set
        # product_check, so their verdicts are unchanged.
        g.update(verdict="could_not_verify", changed=True, confidence="none",
                 reason=f"{PRODUCT_NOT_MEASURED}" + (f" ({cov['why']})" if cov.get("why") else "")
                        + f" (tests: {base_reason})")
        return g
    never_ran = py and measured and cov.get("changed_lines_total") and cov.get("changed_lines_covered") == 0
    if untested_compiled or never_ran:
        why = ("changed code never ran: " + _fmt(cov)) if never_ran else notes[0]
        if never_ran and untested_compiled:
            why += "; " + notes[0]
        g.update(verdict="could_not_verify", changed=True, confidence="none",
                 reason=f"not fully verified: {why} (tests: {base_reason})")
    return g


def apply(rec: dict) -> dict:
    """Return a copy of rec with the gate applied (idempotent)."""
    g = assess(rec)
    out = dict(rec)
    out.setdefault("verdict_before_coverage_gate", rec.get("verdict"))
    out.setdefault("reason_before_coverage_gate", rec.get("reason", ""))
    out["verdict"], out["reason"] = g["verdict"], g["reason"]
    out["changed_lines_total"], out["changed_lines_covered"] = g["changed_lines_total"], g["changed_lines_covered"]
    out["coverage_gate"] = {k: g[k] for k in ("kind", "changed", "confidence", "note", "measurement")}
    return out
