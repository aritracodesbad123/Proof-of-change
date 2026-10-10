"""Probe freeze rule: a probe is fixed BEFORE any PR-side code runs, and only frozen probes run on the PR side.

Generation inputs. A probe may be generated only from (a) the PR title and description and (b) BASE-side code (the base
checkout, or the main side's installed package): never PR-head files, never results of a run. `check_inputs` rejects
any input path that is not under the base root or that lies under a PR-side root. The list of changed paths (names
only) may be used to choose which base files to read.

Freezing. Before the PR side is set up (the first PR-side execution: its install or build), every probe is frozen:

    {"sha256": <content sha256>, "generator": {...}, "frozen_at": <ISO time, UTC offset>,
     "inputs_sha256": <sha256 of the canonical generation inputs, or null for hand-written probes>, "inputs": {...}}

Running. `verify` is called before every PR-side run of a probe. It refuses (FreezeError) when the file's sha256 no
longer matches the frozen one, or when the probe was frozen (or the file last written) after PR-side execution started.

Generators and blindness. Only a live model probe (provider nebius) that passes the freeze rule is BLIND and may count
in blind-eval scoring. Fixed probes are hand-written, and the existing ones were written after the results were known
(post-hoc); recorded model responses are test fixtures. Both are kept as known-answer regression cases and never count
as blind (see `generator`, `is_blind`, and evals/pr_metrics.py).
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
from pathlib import Path

FIXED_POST_HOC = "fixed (post-hoc, written after results were known)"
FIXED = "fixed (hand-written)"
RECORDED = "model (recorded fixture, not blind)"
DIFF = "diff (auto-derived from base-side code, model-free)"


class FreezeError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="microseconds")


def _ts(iso: str) -> float:
    return dt.datetime.fromisoformat(iso).timestamp()


def generator(kind: str, model: str | None = None, provider: str | None = None, provenance: str | None = None) -> dict:
    """kind fixed | model | diff. label is what records and reports print; blind is decided here, once."""
    if kind == "fixed":
        post_hoc = provenance != "pre-registered"
        return {"kind": "fixed", "label": FIXED_POST_HOC if post_hoc else FIXED, "model": None, "provider": None,
                "provenance": "post-hoc" if post_hoc else "pre-registered", "blind": False}
    if kind == "model":
        live = provider == "nebius"
        return {"kind": "model", "label": f"model ({model}, live)" if live else RECORDED, "model": model,
                "provider": provider, "provenance": "live" if live else "recorded fixture", "blind": live}
    if kind == "diff":
        return {"kind": "diff", "label": DIFF, "model": None, "provider": None, "provenance": "auto-derived",
                "blind": False}
    raise ValueError(f"unknown generator kind {kind!r}")


def inputs_hash(inputs: dict) -> str:
    return hashlib.sha256(json.dumps(inputs, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _under(p: Path, root: Path) -> bool:
    try:
        p.relative_to(root)
        return True
    except ValueError:
        return False


def check_inputs(paths: list, base_root: Path, pr_roots: list) -> None:
    """Every generation input file must be base-side: under base_root and under none of the PR-side roots."""
    base = Path(base_root).resolve()
    prs = [Path(r).resolve() for r in pr_roots if r]
    for p in paths:
        rp = Path(p).resolve()
        if any(_under(rp, r) for r in prs):
            raise FreezeError(f"probe generation input {p} is a PR-side path; probes may read base-side code only")
        if not _under(rp, base):
            raise FreezeError(f"probe generation input {p} is not under the base-side root {base_root}")


def base_inputs(title: str, body: str | None, files: dict, base_root: Path, pr_roots: list) -> dict:
    """Canonical generation inputs: PR title and description, and {relative path: sha256} of the base-side files read.
    files: {relative path: absolute path}; every absolute path is checked with check_inputs."""
    check_inputs(list(files.values()), base_root, pr_roots)
    return {"title": title or "", "body": body or "",
            "base_files": {rel: sha256_file(p) for rel, p in sorted(files.items()) if Path(p).is_file()}}


def freeze(path: Path, gen: dict, inputs: dict | None) -> dict:
    return {"sha256": sha256_file(path), "generator": gen, "frozen_at": now(),
            "inputs_sha256": inputs_hash(inputs) if inputs is not None else None,
            "inputs": ({"title_chars": len(inputs.get("title", "")), "body_chars": len(inputs.get("body", "")),
                        "base_files": inputs.get("base_files", {})} if inputs is not None else None)}


def verify(path: Path, frozen: dict | None, pr_started_at: str | None) -> None:
    """Raise FreezeError unless the probe file is exactly the frozen one and was frozen before PR-side execution."""
    if not frozen:
        raise FreezeError(f"{Path(path).name}: probe was never frozen")
    got = sha256_file(path)
    if got != frozen["sha256"]:
        raise FreezeError(f"{Path(path).name}: content changed after freezing (sha256 {got[:12]} != frozen "
                          f"{frozen['sha256'][:12]})")
    if not pr_started_at:
        raise FreezeError(f"{Path(path).name}: PR-side start time unknown; refusing to run")
    start = _ts(pr_started_at)
    if _ts(frozen["frozen_at"]) > start:
        raise FreezeError(f"{Path(path).name}: frozen at {frozen['frozen_at']}, after PR-side execution started "
                          f"({pr_started_at})")
    if os.stat(path).st_mtime > start:
        raise FreezeError(f"{Path(path).name}: file written after PR-side execution started")


def is_blind(item: dict) -> bool:
    """A probe result counts as blind only if a live model wrote it and it passed the freeze rule."""
    g = (item.get("freeze") or {}).get("generator") or item.get("generator") or {}
    return bool(g.get("blind")) and g.get("kind") == "model" and g.get("provider") == "nebius" \
        and (item.get("freeze") or {}).get("verified") is True
