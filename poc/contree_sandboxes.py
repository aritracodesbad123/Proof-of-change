"""Contree Token Factory Sandboxes backend (REQUIREMENTS §4 steps 2/3/6).

--sandbox-backend local   bubblewrap via guardrails/sandbox.py (default)
--sandbox-backend contree Contree SDK when CONTREE_API_KEY is set; otherwise falls back to local

Secrets never enter the sandbox env (reuse guardrails/isolation.py). Concurrent Contree ops
are capped at CONTREE_MAX_OPS (default 40, under the 50-op beta limit).
"""
from __future__ import annotations

import os
import threading
from pathlib import Path

KEY_ENV = "CONTREE_API_KEY"
MAX_OPS = int(os.environ.get("CONTREE_MAX_OPS", "40"))
BACKENDS = ("local", "contree")

_sem = threading.Semaphore(MAX_OPS)
_state = {"backend": "local", "note": "local bubblewrap"}


def select(name: str, env: dict | None = None) -> tuple[str, str]:
    """Return (backend, note). contree without a key falls back to local."""
    env = os.environ if env is None else env
    if name == "local":
        _state.update(backend="local", note="local bubblewrap")
        return "local", _state["note"]
    if name != "contree":
        raise ValueError(f"unknown sandbox backend {name!r}; one of {BACKENDS}")
    raw = env.get(KEY_ENV)
    if raw is None or str(raw).strip() == "":
        note = f"contree requested but {KEY_ENV} missing/empty: using local bubblewrap"
        _state.update(backend="local", note=note)
        return "local", note
    # ponytail: Contree SDK not installed yet; record intent and keep local execution until SDK lands
    note = ("contree selected (key present); dual-run still uses local bubblewrap until Contree SDK "
            "checkpoint/fork is wired — machine field records intent")
    _state.update(backend="contree", note=note)
    return "contree", note


def backend() -> str:
    return _state["backend"]


def note() -> str:
    return _state["note"]


def with_slot(fn):
    """Run fn under the Contree concurrency semaphore (≤ MAX_OPS)."""
    with _sem:
        return fn()


def checkpoint_main(base_sha: str, work: Path) -> dict:
    """Build/save the main checkpoint. Contree path is stubbed; local returns a filesystem marker."""
    marker = work / f"checkpoint-main-{base_sha[:12]}"
    marker.mkdir(parents=True, exist_ok=True)
    return {"backend": backend(), "kind": "main", "sha": base_sha, "path": str(marker),
            "disposable": False}


def fork_pr(main_cp: dict, head_sha: str, work: Path) -> dict:
    """Fork main checkpoint for the PR side."""
    marker = work / f"checkpoint-pr-{head_sha[:12]}"
    marker.mkdir(parents=True, exist_ok=True)
    return {"backend": backend(), "kind": "pr", "sha": head_sha, "path": str(marker),
            "from": main_cp.get("path"), "disposable": True}
