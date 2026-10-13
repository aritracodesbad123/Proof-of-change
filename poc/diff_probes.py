"""Differential probes for the tests+diff baseline: generic, model-free, derived from the public API a PR touches.

    derive(diff, files, base_root, pr_roots, target) -> {"targets": [(module, function)], "inputs": {...}}
    write(targets, path, target) -> probe file (poc/probes.py format, no claims)

Which functions: the PR's changed non-test Python files of the package, read on the BASE side; module-level public
functions (no leading underscore, in a public module) whose base-side lines intersect the diff's OLD-side line
ranges. Only base-side code and old-side line numbers are used (poc/freeze.py rules); new functions that exist only
on the PR side are not probed.

What it observes: each function is called with the same deterministic inputs on both sides. A parameter whose name
or annotation asks for a graph, an array, labels or a fitted estimator gets one of those (a 4-node path graph, a
small numeric array, labels 0/1, or a fitted logistic regression). A function whose parameters have no such hint is
called with the small scalar set (1, 0, -1, 2.5, "abc", [1, 2, 3], None). If a required domain object cannot be
built, that function is not called: the observation is {"skipped": "no type-aware input"} and the probe does not
count as having run. Random and NumPy are seeded before each call. Each result is reduced to a canonical JSON
summary; an exception becomes {"raises": "<type name>"}. Observations are named <module>.<function>.input<k>. The
probe has no claims, so any difference is "unmentioned". It is a deliberately simple baseline: it finds behaviour
changes on inputs of the right kind, not whether a change was intended.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

from poc import coverage_gate, freeze

MAX_FUNCTIONS = 12
HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+\d+(?:,\d+)? @@", re.M)


def old_ranges(diff: str) -> dict:
    """{path: [(start, end)]} of the OLD-side lines each hunk touches (a pure insertion touches its anchor line)."""
    out: dict = {}
    for block in re.split(r"(?m)^diff --git ", diff or ""):
        m = re.search(r"(?m)^--- (?:a/)?(\S+)", block)
        if not m or m.group(1) == "/dev/null":
            continue
        for h in HUNK.finditer(block):
            a, b = int(h.group(1)), int(h.group(2) if h.group(2) is not None else 1)
            out.setdefault(m.group(1), []).append((a, a + max(b, 1) - 1))
    return out


def module_name(rel: str) -> str | None:
    parts = rel[:-3].split("/") if rel.endswith(".py") else None
    if not parts:
        return None
    if parts[-1] == "__init__":
        parts = parts[:-1]
    if parts and parts[0] == "src":   # src layout: src/<pkg>/...
        parts = parts[1:]
    if not parts or any(p.startswith("_") for p in parts) or any(not p.isidentifier() for p in parts):
        return None
    return ".".join(parts)


def touched_functions(src: str, ranges: list) -> list[str]:
    names = []
    for node in ast.parse(src).body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and not node.name.startswith("_"):
            lo = min([d.lineno for d in node.decorator_list] + [node.lineno])
            hi = node.end_lineno or node.lineno
            if any(a <= hi and b >= lo for a, b in ranges):
                names.append(node.name)
    return names


def derive(diff: str, py_files: list, base_root: Path, pr_roots: list, rel_prefix: str = "") -> dict:
    """py_files: repo-relative changed Python files. Paths are resolved under base_root (rel_prefix stripped for
    installed packages is not needed: base_root is the folder the repo-relative paths resolve against)."""
    ranges = old_ranges(diff)
    files, targets = {}, []
    for rel in py_files:
        if coverage_gate.is_test(rel) or rel not in ranges:
            continue
        mod = module_name(rel)
        p = Path(base_root) / rel
        if not mod or not p.is_file():
            continue
        files[rel] = p
        try:
            fns = touched_functions(p.read_text(errors="replace"), ranges[rel])
        except SyntaxError:
            continue
        targets += [(mod, f) for f in fns]
    inputs = freeze.base_inputs("", "", files, base_root, pr_roots)
    inputs["old_ranges"] = {k: v for k, v in sorted(ranges.items()) if k in files}
    return {"targets": targets[:MAX_FUNCTIONS], "inputs": inputs}


PROBE_BODY = r'''
import copy
import importlib
import inspect
import json
import math
import random
import re

CANDIDATES = [1, 0, -1, 2.5, "abc", [1, 2, 3], None]
GRAPH_NAMES = {"g", "g1", "g2", "h", "graph"}
ARRAY_NAMES = {"x_train", "x_test", "data", "features"}
LABEL_NAMES = {"y", "y_train", "y_test", "labels", "target"}
EST_NAMES = {"clf", "estimator", "model", "classifier", "regressor"}
SKIPPED = {"skipped": "no type-aware input"}


def canon(x, depth=0):
    if depth > 3:
        return {"type": type(x).__name__}
    if x is None or isinstance(x, (bool, int, str)):
        return x if not isinstance(x, str) else x[:200]
    if isinstance(x, float):
        return "nan" if math.isnan(x) else repr(x) if math.isinf(x) else round(x, 10)
    if isinstance(x, (list, tuple)):
        return [canon(v, depth + 1) for v in list(x)[:20]]
    if isinstance(x, dict):
        return {str(k): canon(v, depth + 1) for k, v in list(x.items())[:20]}
    if hasattr(x, "shape") and hasattr(x, "tolist"):
        try:
            flat = list(getattr(x, "ravel")().tolist())[:20]
            return {"type": type(x).__name__, "shape": list(x.shape), "values": canon(flat, depth + 1)}
        except Exception:  # noqa: BLE001
            pass
    return {"type": type(x).__name__, "repr": re.sub(r" at 0x[0-9a-fA-F]+", "", repr(x))[:200]}


def seed():
    random.seed(0)
    try:
        import numpy
        numpy.random.seed(0)
    except Exception:  # noqa: BLE001
        pass


def annotation_text(p):
    ann = p.annotation
    if ann is inspect.Signature.empty:
        return ""
    return getattr(ann, "__name__", str(ann)).lower()


def domain_kind(name, ann):
    n = (name or "").lower()
    if n in GRAPH_NAMES or n.endswith("graph") or "graph" in ann:
        return "graph"
    if n in EST_NAMES or "estimator" in ann or "classifier" in ann:
        return "estimator"
    if n in LABEL_NAMES:
        return "labels"
    if n in ARRAY_NAMES or "ndarray" in ann or ann == "array":
        return "array"
    return None


def build_graph():
    try:
        import networkx as nx
        return nx.path_graph(4)
    except Exception:  # noqa: BLE001
        return None


def build_array():
    try:
        import numpy as np
        return np.array([[0.0, 0.0], [1.0, 1.0], [0.0, 1.0], [1.0, 0.0]])
    except Exception:  # noqa: BLE001
        return [[0.0, 0.0], [1.0, 1.0], [0.0, 1.0], [1.0, 0.0]]


def build_labels():
    return [0, 1, 0, 1]


def build_estimator():
    try:
        from sklearn.linear_model import LogisticRegression
        return LogisticRegression().fit(build_array(), build_labels())
    except Exception:  # noqa: BLE001
        return None


BUILDERS = {"graph": build_graph, "array": build_array, "labels": build_labels, "estimator": build_estimator}


def positional(f):
    try:
        return [p for p in inspect.signature(f).parameters.values()
                if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)]
    except (TypeError, ValueError):
        return []


def call_plan(params):
    """'candidates' for an untyped function, 'skip' when a required domain object cannot be built, else one arg list."""
    if not any(domain_kind(p.name, annotation_text(p)) for p in params):
        return "candidates"
    args = []
    for p in params:
        kind = domain_kind(p.name, annotation_text(p))
        if kind:
            value = BUILDERS[kind]()
            if value is None:
                if p.default is inspect.Parameter.empty:
                    return "skip"
                continue
            args.append(value)
        elif p.default is inspect.Parameter.empty:
            args.append(1)
    return [args]


obs = {}
for mod, fn in TARGETS:
    try:
        f = getattr(importlib.import_module(mod), fn)
    except Exception as e:  # noqa: BLE001
        obs[f"{mod}.{fn}.import"] = {"raises": type(e).__name__}
        continue
    params = positional(f)
    plan = call_plan(params)
    if plan == "skip":
        obs[f"{mod}.{fn}.input0"] = dict(SKIPPED)
        continue
    if plan == "candidates":
        n = sum(1 for p in params if p.default is inspect.Parameter.empty)
        calls = [[copy.deepcopy(c) for _ in range(n)] for c in (CANDIDATES if n else CANDIDATES[:1])]
    else:
        calls = plan
    for k, args in enumerate(calls):
        seed()
        try:
            r = canon(f(*[copy.deepcopy(a) for a in args]))
        except Exception as e:  # noqa: BLE001
            r = {"raises": type(e).__name__}
        obs[f"{mod}.{fn}.input{k}"] = r
print(json.dumps({"observations": obs}, sort_keys=True, default=str))
'''


def write(targets: list, path: Path, target: str) -> Path:
    spec = {"id": "diff-api", "target": target,
            "about": "Public functions touched by the PR, called with type-appropriate inputs on both sides.",
            "claims": [], "timeout_s": 60, "generator": freeze.DIFF}
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text('"""Differential probe (model-free baseline, poc/diff_probes.py)."""\n'
                          f"PROBE = {spec!r}\nTARGETS = {[list(t) for t in targets]!r}\n" + PROBE_BODY)
    return Path(path)
