"""Per-environment isolation and timeout helpers."""
from __future__ import annotations

import os
import re
import signal
import subprocess
import time
from pathlib import Path

from guardrails.schema import SINGLE_THREAD_VARS

SINGLE_THREAD_ENV = {v: "1" for v in SINGLE_THREAD_VARS} | {"NUMEXPR_NUM_THREADS": "1"}
# ---------------------------------------------------------------- environment for untrusted code
# Every subprocess that runs code from a PR or a package (installs and builds, pytest, probes, any start of a venv
# Python, which executes installed .pth files) gets an environment built from this ALLOWLIST and nothing else.
# Values are either passed through from the parent (only if set) or fixed here.
UNTRUSTED_THREAD_ENV = {k: "1" for k in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
                                         "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "BLIS_NUM_THREADS")}
PASS_THROUGH = ("PATH", "LANG", "LC_ALL", "TERM", "TMPDIR", "SOURCE_DATE_EPOCH", "SSL_CERT_FILE")
FIXED_ENV = UNTRUSTED_THREAD_ENV | {"PYTHONHASHSEED": "0", "PYTHONDONTWRITEBYTECODE": "1", "MPLBACKEND": "Agg"}
# Installs only: where uv keeps its download cache and its managed Pythons (so a per-env HOME does not force a
# fresh download of everything), copy-not-link from that cache, and no uv config files (user or project).
INSTALL_DIRS = ("UV_CACHE_DIR", "UV_PYTHON_INSTALL_DIR")
INSTALL_FIXED = {"UV_LINK_MODE": "copy", "UV_NO_CONFIG": "1"}
INSTALL_EXTRA = ("SETUPTOOLS_SCM_PRETEND_VERSION",)   # set per call for checkouts without tags
RUN_ALLOWLIST = frozenset(PASS_THROUGH) | {"HOME"} | set(FIXED_ENV)
INSTALL_ALLOWLIST = RUN_ALLOWLIST | set(INSTALL_DIRS) | set(INSTALL_FIXED) | set(INSTALL_EXTRA)
# Second, independent check: names that look like credentials. It must never match an allowlisted name.
SECRET_NAME = re.compile(r"TOKEN|SECRET|PASSW|CREDENTIAL|API_?KEY|ACCESS_?KEY|PRIVATE|(^|_)KEY($|_)|_KEY|KEY_|AUTH"
                         r"|(^|_)PAT($|_)|DATABASE_URL|_DSN|^DSN|COOKIE|SESSION|SIGNING|WEBHOOK", re.I)
URL_USERINFO = re.compile(r"[a-z][a-z0-9+.-]*://[^/\s:@]+:[^/\s@]+@", re.I)


class UnsafeEnv(RuntimeError):
    """An environment for untrusted code contains something it must not."""


def check_untrusted_env(env: dict, allowlist: frozenset | set = INSTALL_ALLOWLIST) -> None:
    """Fail loudly if env has a name outside the allowlist, a credential-looking name, or a URL with a password."""
    extra = sorted(set(env) - set(allowlist))
    secret = sorted(k for k in env if SECRET_NAME.search(k))
    userinfo = sorted(k for k, v in env.items() if URL_USERINFO.search(str(v)))
    if extra or secret or userinfo:
        raise UnsafeEnv(f"refusing to run untrusted code with this environment: not allowlisted {extra}, "
                        f"credential-like names {secret}, URLs with credentials in {userinfo}")


def _uv_dirs(src: dict) -> dict:
    home = Path(src.get("HOME") or Path.home())
    cache = src.get("UV_CACHE_DIR") or str(Path(src.get("XDG_CACHE_HOME") or home / ".cache") / "uv")
    py = src.get("UV_PYTHON_INSTALL_DIR") or str(Path(src.get("XDG_DATA_HOME") or home / ".local" / "share") / "uv"
                                                 / "python")
    return {"UV_CACHE_DIR": cache, "UV_PYTHON_INSTALL_DIR": py}


def untrusted_env(home: str | Path, install: bool = False, extra: dict | None = None,
                  base: dict | None = None) -> dict:
    """The only environment untrusted code gets: allowlisted pass-through values from `base` (default os.environ),
    HOME = `home` (a per-environment temporary home, created here; never the real one), fixed thread and hash
    settings; with install=True also the uv cache/Python dirs and uv settings. `extra` may only add
    INSTALL_EXTRA names. Checked by check_untrusted_env before it is returned."""
    src = os.environ if base is None else base
    home = Path(home)
    home.mkdir(parents=True, exist_ok=True)
    env = {k: src[k] for k in PASS_THROUGH if src.get(k)}
    env.setdefault("PATH", os.defpath)
    env["HOME"] = str(home)
    env.update(FIXED_ENV)
    if install:
        env.update(_uv_dirs(src))
        env.update(INSTALL_FIXED)
    for k, v in (extra or {}).items():
        if k not in INSTALL_EXTRA or not install:
            raise UnsafeEnv(f"{k} is not an allowed extra variable")
        env[k] = v
    check_untrusted_env(env, INSTALL_ALLOWLIST if install else RUN_ALLOWLIST)
    return env


def check_allowlist(names) -> None:
    """The allowlist itself must never contain a credential-looking name (checked at import time)."""
    bad = sorted(k for k in names if SECRET_NAME.search(k))
    if bad:
        raise UnsafeEnv(f"allowlisted variable(s) {bad} look like credentials")


check_allowlist(INSTALL_ALLOWLIST)


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
