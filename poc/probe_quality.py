"""Probe lint gate: static checks a probe must pass before it is frozen and run (research strategy 5.3).

A probe reports what it sees; plain code compares the two sides (poc/probes.py). So a probe must not judge, must
not reach the network or start processes, must not write outside its temporary folder, and must actually touch
the code the PR changed. Checked on the parsed AST (the probe is never imported or run here):

    non-asserting   no `assert` statement; no `pytest.raises` (attribute, `from pytest import raises`, or alias)
    no network      no import of socket, ssl, http, urllib, ftplib, mail clients, telnetlib, requests, httpx, aiohttp,
                    urllib3 (also through __import__ / importlib.import_module with a literal name), unless that
                    package is the library under test (a probe for a requests PR imports requests; the sandbox
                    still has no network)
    no processes    no import of subprocess, multiprocessing, pty; no os.system / os.popen / os.exec* / os.spawn* /
                    os.fork* / os.posix_spawn*
    no writes out   no open(<absolute literal path outside /tmp>, <write mode>)
    relevant        imports at least one changed module, or a package on the path to one (changed_files is any
                    list of paths that differ between the old and new side: a PR diff, or two releases)
                    (`from mlxtend.evaluate import x` is relevant to mlxtend/evaluate/feature_importance.py)

`lint(src, changed_files)` returns {"ok", "problems": [{"rule", "line", "detail"}], "imports",
"changed_modules", "relevant_imports"}. Executing a changed line is checked separately, by running the probe on
the main side under coverage.
"""
from __future__ import annotations

import ast
from pathlib import Path, PurePosixPath

NETWORK = frozenset({"socket", "ssl", "http", "urllib", "ftplib", "telnetlib", "requests", "httpx", "aiohttp",
                     "urllib3", "websocket", "websockets", "paramiko",
                     "smtplib"})  # br-allow-external: a module a probe may NOT import
PROCESS = frozenset({"subprocess", "multiprocessing", "pty"})
OS_PROCESS = ("system", "popen", "exec", "spawn", "fork", "posix_spawn", "kill")
SRC_PREFIXES = ("src", "lib", "python")
WRITE_MODES = set("wax+")


def module_of(path: str) -> str | None:
    """Dotted module of a repo-relative Python file: src/requests/adapters.py -> requests.adapters,
    pkg/sub/__init__.py -> pkg.sub. Tests and non-Python files -> None."""
    p = PurePosixPath(path)
    if p.suffix not in (".py", ".pyi"):
        return None
    parts = list(p.with_suffix("").parts)
    if parts and parts[0] in SRC_PREFIXES and len(parts) > 1:
        parts = parts[1:]
    if parts[-1] == "__init__":
        parts = parts[:-1]
    if not parts or any(x in ("tests", "test") for x in parts) or parts[-1].startswith("test_") or parts[-1] == "conftest":
        return None
    return ".".join(parts)


def changed_modules(changed_files: list[str]) -> list[str]:
    return sorted({m for f in changed_files if (m := module_of(f))})


def _root(name: str) -> str:
    return name.split(".")[0]


def _imports(tree: ast.AST) -> list[tuple[str, list[str], int]]:
    """[(module, [imported names], line)] for import, from-import, __import__('x') and import_module('x')."""
    out = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            out += [(a.name, [], n.lineno) for a in n.names]
        elif isinstance(n, ast.ImportFrom) and n.module and not n.level:
            out.append((n.module, [a.name for a in n.names], n.lineno))
        elif isinstance(n, ast.Call) and n.args and isinstance(n.args[0], ast.Constant) and isinstance(n.args[0].value, str):
            f = n.func
            fname = f.id if isinstance(f, ast.Name) else f.attr if isinstance(f, ast.Attribute) else ""
            if fname in ("__import__", "import_module"):
                out.append((n.args[0].value, [], n.lineno))
    return out


def _relevant(mod: str, names: list[str], changed: list[str]) -> list[str]:
    hits = []
    for c in changed:
        cands = [mod] + [f"{mod}.{x}" for x in names]
        if any(x == c or c.startswith(x + ".") or x.startswith(c + ".") for x in cands):
            hits.append(c)
    return hits


def _write_mode(call: ast.Call) -> bool:
    mode = call.args[1] if len(call.args) > 1 else next((k.value for k in call.keywords if k.arg == "mode"), None)
    return isinstance(mode, ast.Constant) and isinstance(mode.value, str) and bool(WRITE_MODES & set(mode.value))


def lint(src: str, changed_files: list[str]) -> dict:
    problems: list[dict] = []

    def bad(rule, node, detail):
        problems.append({"rule": rule, "line": getattr(node, "lineno", 0), "detail": detail})

    try:
        tree = ast.parse(src)
    except SyntaxError as e:
        return {"ok": False, "problems": [{"rule": "syntax", "line": e.lineno or 0, "detail": str(e.msg)}],
                "imports": [], "changed_modules": changed_modules(changed_files), "relevant_imports": []}
    imports = _imports(tree)
    pytest_names = {"pytest"}
    raises_names = set()
    os_names = {"os"}
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            for a in n.names:
                if a.name == "pytest":
                    pytest_names.add(a.asname or "pytest")
                if a.name == "os":
                    os_names.add(a.asname or "os")
        elif isinstance(n, ast.ImportFrom) and n.module == "pytest":
            for a in n.names:
                if a.name == "raises":
                    raises_names.add(a.asname or "raises")
                    bad("pytest.raises", n, "imports pytest.raises")
        elif isinstance(n, ast.ImportFrom) and n.module == "os":
            for a in n.names:
                if a.name.startswith(OS_PROCESS):
                    bad("process", n, f"imports os.{a.name}")
    under_test = {_root(c) for c in changed_modules(changed_files)}   # probing `requests` itself is allowed
    for mod, _names, line in imports:
        node = ast.Constant(value=None, lineno=line)
        if _root(mod) in under_test:
            continue
        if _root(mod) in NETWORK:
            bad("network", node, f"imports {mod}")
        if _root(mod) in PROCESS:
            bad("process", node, f"imports {mod}")
    for n in ast.walk(tree):
        if isinstance(n, ast.Assert):
            bad("assert", n, "assert statement (a probe reports, it does not judge)")
        elif isinstance(n, ast.Attribute) and n.attr == "raises" and isinstance(n.value, ast.Name) \
                and n.value.id in pytest_names:
            bad("pytest.raises", n, f"{n.value.id}.raises")
        elif isinstance(n, ast.Name) and n.id in raises_names and isinstance(n.ctx, ast.Load):
            bad("pytest.raises", n, f"{n.id} (pytest.raises)")
        elif isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name) and n.value.id in os_names \
                and n.attr.startswith(OS_PROCESS):
            bad("process", n, f"{n.value.id}.{n.attr}")
        elif isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "open" and n.args \
                and isinstance(n.args[0], ast.Constant) and isinstance(n.args[0].value, str) and _write_mode(n):
            p = n.args[0].value
            if p.startswith("/") and not (p == "/tmp" or p.startswith("/tmp/")):
                bad("write", n, f"writes to {p} (outside the temporary folder)")
    changed = changed_modules(changed_files)
    relevant = sorted({c for mod, names, _ in imports for c in _relevant(mod, names, changed)})
    if not changed:
        bad("relevant", tree, "the PR changes no importable Python module, so no probe can be relevant")
    elif not relevant:
        bad("relevant", tree, "imports none of the changed modules (" + ", ".join(changed[:5]) + ")")
    problems.sort(key=lambda p: (p["line"], p["rule"]))
    return {"ok": not problems, "problems": problems, "imports": sorted({m for m, _, _ in imports}),
            "changed_modules": changed, "relevant_imports": relevant}


def lint_file(path: str | Path, changed_files: list[str]) -> dict:
    return lint(Path(path).read_text(), changed_files) | {"path": str(path)}


def reasons(result: dict) -> str:
    """One line for a report: 'ok' or 'rejected: assert (line 3); relevant (...)'."""
    if result["ok"]:
        return "ok"
    return "rejected: " + "; ".join(f"{p['rule']} (line {p['line']}): {p['detail']}" for p in result["problems"][:5])
