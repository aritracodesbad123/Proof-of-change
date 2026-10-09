"""Per-environment isolation and timeout helpers."""
from __future__ import annotations

import os
import signal
import subprocess
import time
from pathlib import Path

from guardrails.schema import SINGLE_THREAD_VARS

SINGLE_THREAD_ENV = {v: "1" for v in SINGLE_THREAD_VARS} | {"NUMEXPR_NUM_THREADS": "1"}
DEFAULT_TEST_TIMEOUT_S = 120     # per test (pytest-timeout), matches br_run.py default
DEFAULT_RUN_TIMEOUT_S = 1200     # per pytest invocation, matches br_run.py default


def single_thread_env(base: dict | None = None) -> dict:
    """Copy of `base` (default os.environ) with the single-thread settings forced and PYTHONPATH removed."""
    env = dict(os.environ if base is None else base)
    env.update(SINGLE_THREAD_ENV)
    env.pop("PYTHONPATH", None)
    return env


def assert_single_thread(env: dict) -> list[str]:
    return [f"{k} must be '1' (got {env.get(k)!r})" for k in SINGLE_THREAD_ENV if env.get(k) != "1"]


def check_env_isolation(run_dir: str | Path, venv_old: str | Path, venv_new: str | Path) -> list[str]:
    """Each side must have its own venv, inside its own run directory."""
    run_dir, vo, vn = Path(run_dir).resolve(), Path(venv_old).resolve(), Path(venv_new).resolve()
    errs = []
    if vo == vn:
        errs.append("old and new sides share one venv")
    for side, v in (("old", vo), ("new", vn)):
        if run_dir not in v.parents:
            errs.append(f"{side} venv {v} is outside run dir {run_dir}")
    return errs


def run_with_timeout(cmd: list[str], timeout_s: float, env: dict | None = None, cwd: str | None = None) -> dict:
    """Run cmd in its own process group; kill the whole group on timeout."""
    t0 = time.time()
    p = subprocess.Popen(cmd, env=env, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                         text=True, start_new_session=True)
    try:
        out, _ = p.communicate(timeout=timeout_s)
        rc = p.returncode
    except subprocess.TimeoutExpired:
        os.killpg(p.pid, signal.SIGKILL)
        out, _ = p.communicate()
        rc = "timeout"
    return {"rc": rc, "seconds": round(time.time() - t0, 2), "output": out}
