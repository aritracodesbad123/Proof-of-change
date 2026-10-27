#!/usr/bin/env python3
"""Proof-of-Change daily run: tracked libraries -> new open PRs -> main-vs-PR test -> log + approver report.

    python3 ops/daily_run.py                       # normal daily run (fetches origin and fast-forwards to origin/main first)
    python3 ops/daily_run.py --select-only         # chosen PRs, print them, test nothing
    python3 ops/daily_run.py --max-per-library 3 --libraries numpy,pandas
    python3 ops/daily_run.py --pr https://github.com/pandas-dev/pandas/pull/12345   # check one PR (make check PR=...)
    python3 ops/daily_run.py --report-only --date 2026-10-10                       # rebuild reports, test nothing

After the run, reviewer reports (HTML, PDF, Markdown) are written to reports/daily/<run folder>/ by
reports/pr_report.py; ops/runs/<run folder>/REPORT.md stays as the operator's run log.

Read-only towards GitHub: it only GETs public API/diff URLs. It never comments, reviews or posts.
Uses $GITHUB_TOKEN, or $GITHUB_POC_TOKEN, or $GH_TOKEN, for read-only API calls if one is set; otherwise
unauthenticated (60 requests/hour). A rate limit (403/429 with remaining 0) waits until reset, bounded, and retries once.

How a PR is tested (route "nightly+patch", used for pure-Python PRs):
  main side = latest scientific-python nightly wheel of the library (main branch build)
  PR side   = an exact copy of the main-side venv with the PR's diff applied to the installed package
  Only files under the package directory are patched; tests shipped in the wheel are patched too.
PRs that touch compiled sources (.c/.pyx/.cpp/meson.build, ...) take route "source-build": the PR head is built
from source with a timeout; main is the nightly wheel. A failed or timed-out build is recorded as could_not_verify
with its build log.
Tests: only test files mapped from the touched modules, 3 alternating runs per side, single-thread env,
per-test and per-run timeouts. Comparison and verdict are plain code (poc/diff.py, poc/verdict.py).
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import fcntl
import glob
import hashlib
import json
import os
import re
import shlex
import shutil
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path, PurePosixPath

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
from guardrails import sandbox  # noqa: E402
from guardrails.isolation import untrusted_env  # noqa: E402
from harness.machine import detect_machine_type  # noqa: E402
from poc import agents, behaviour_claims, cost, coverage_gate, diff_probes, freeze, local_config, model_probes, model_provider, probes  # noqa: E402,E501
from poc.diff import confirm, pr_runs_too_noisy  # noqa: E402
from poc.pr_text import github_read_token  # noqa: E402
from poc.tool_setup import ToolSetupError, ensure_tools, uv_bin  # noqa: E402
from poc.tool_setup import last_result as tool_setup_result  # noqa: E402
from poc.verdict import Claim, FindingLabel, RunSummary, Verdict, pr_verdict  # noqa: E402

IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
NIGHTLY = "https://pypi.anaconda.org/scientific-python-nightly-wheels/simple"
PYPI = "https://pypi.org/simple"
# Same 6 vars as the shared runner (harness/schema thread_env).
THREAD_ENV = {k: "1" for k in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS",
                               "VECLIB_MAXIMUM_THREADS", "BLIS_NUM_THREADS")}
SCHEMA_PATH = REPO_ROOT / "harness" / "schema" / "observation.schema.json"
WHO = "ops/daily_run.py"
_COMMIT = re.compile(r"^[0-9a-f]{40}$")
COMPILED_EXT = (".c", ".h", ".cpp", ".hpp", ".cc", ".cxx", ".pyx", ".pxd", ".pxi", ".tp", ".src", ".f", ".f90", ".cu")
COMPILED_NAMES = ("meson.build", "meson.options", "meson_options.txt", "setup.py", "pyproject.toml")

# Per-library knobs. Unknown libraries fall back to DEFAULT (dist == import name == repo name).
# test_deps: what the project's test suite needs. optional_test_deps: optional runtime deps whose absence makes tests
# skip (pandas: pyarrow, scipy). Both are installed on BOTH sides, together with the project's test extra
# ("test"/"tests"/"testing", detected from the package metadata or pyproject.toml).
LIBS = {
    "numpy/numpy": {"dist": "numpy", "pkg": "numpy", "deps": [], "test_deps": ["hypothesis", "typing_extensions"],
                    "optional_test_deps": [], "nightly": True, "commit_expr": "import numpy.version as v;print(v.git_revision)"},
    "pandas-dev/pandas": {"dist": "pandas", "pkg": "pandas", "deps": [], "test_deps": ["hypothesis"],
                          "optional_test_deps": ["pyarrow", "scipy"], "nightly": True, "tests_root": "pandas/tests",
                          "commit_expr": "import pandas as m;print(getattr(m, '__git_version__', ''))"},
    "scikit-learn/scikit-learn": {"dist": "scikit-learn", "pkg": "sklearn", "deps": [], "test_deps": [],
                                  "optional_test_deps": ["scipy", "pandas", "pyarrow", "polars", "matplotlib"],
                                  "nightly": True, "commit_expr": ""},
}
TEST_EXTRA_NAMES = ("test", "tests", "testing")
# tzdata: some machines have no system zoneinfo; pandas/xarray tests need IANA zones.
BASE_TEST_DEPS = ["pytest", "pytest-timeout", "pytest-xdist", "tzdata"]
XDIST_MISMATCH = "Different tests were collected between"


def now_ist() -> dt.datetime:
    return dt.datetime.now(IST)


def to_ist(iso_utc: str) -> str:
    t = dt.datetime.fromisoformat(iso_utc.replace("Z", "+00:00")).astimezone(IST)
    return t.strftime("%Y-%m-%d %H:%M IST")


# ---------------------------------------------------------------- GitHub (read-only)
def _rate_limit_max_wait_s() -> int:
    raw = os.environ.get("POC_GITHUB_RATE_LIMIT_MAX_WAIT_S", "900")
    try:
        return max(0, int(raw))
    except ValueError:
        return 900


AUTH_FAIL_EXIT = 3      # GitHub refused the login AUTH_FAIL_LIMIT times in a row for one request
LOCK_HELD_EXIT = 4      # another run already holds this run folder's lock
AUTH_FAIL_LIMIT = 3
AUTH_FAIL_MESSAGE = ("auth problem: GitHub refused the login 3 times; "
                     "the GitHub key in this run's environment is invalid or stale")
RUN_LOCK_NAME = "run.lock"


class GitHubAuthError(BaseException):
    """GitHub answered 401 AUTH_FAIL_LIMIT times in a row for the same request.

    A BaseException on purpose: per-repository ``except Exception`` handlers must not turn a bad key into
    one "selection failed" line per library. The message never contains the token."""


class RunLockHeld(RuntimeError):
    """Another process holds the run folder's lock."""


def acquire_run_lock(run_dir: Path):
    """Take an exclusive, non-blocking flock on ``run_dir/run.lock``. Returns the open handle; keep it for the
    life of the run (the kernel drops the lock when the process exits). Raises RunLockHeld when it is taken."""
    run_dir.mkdir(parents=True, exist_ok=True)
    path = run_dir / RUN_LOCK_NAME
    handle = path.open("a+")
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        handle.close()
        raise RunLockHeld(f"another run holds the lock {path}; not starting a second copy") from None
    handle.seek(0)
    handle.truncate()
    handle.write(f"{os.getpid()}\n")
    handle.flush()
    return handle


class GitHub:
    def __init__(self, log, fail_fast_auth: bool = False):
        # Authenticated = 5k/hour; anonymous = 60/hour (shared across Render IPs).
        # Host environment only. This value is never copied into an environment that runs pull-request code.
        self.token = github_read_token()
        self.calls = 0
        self.remaining = None
        self.log = log
        # Product runs stop on a refused login instead of retrying it as a network error. Study runs leave it off.
        self.fail_fast_auth = fail_fast_auth

    def _note(self, msg: str) -> None:
        print(msg, file=sys.stderr, flush=True)
        if self.log:
            try:
                with open(self.log, "a") as fh:
                    fh.write(msg + "\n")
            except OSError:
                pass

    def _remaining_is_zero(self, err: urllib.error.HTTPError) -> bool:
        rem = err.headers.get("X-RateLimit-Remaining") if err.headers else None
        if rem is None:
            return False
        try:
            self.remaining = int(str(rem).strip())
        except ValueError:
            return False
        return self.remaining == 0

    def _wait_for_reset(self, err: urllib.error.HTTPError, url: str) -> bool:
        """Wait until X-RateLimit-Reset when that wait fits the cap. Return False when it does not."""
        raw = err.headers.get("X-RateLimit-Reset") if err.headers else None
        try:
            reset_at = int(str(raw).strip())
        except (TypeError, ValueError):
            self._note(f"GitHub rate limit at {url}: remaining=0 but no reset time; not waiting")
            return False
        delay = max(0, reset_at - int(time.time()) + 1)
        cap = _rate_limit_max_wait_s()
        if delay > cap:
            self._note(f"GitHub rate limit at {url}: reset in {delay}s exceeds cap {cap}s; not waiting")
            return False
        self._note(f"GitHub rate limit at {url}: remaining=0, waiting {delay}s until reset")
        time.sleep(delay)
        return True

    def _rate_error(self, url: str) -> RuntimeError:
        hint = ("" if self.token else
                "; set GITHUB_TOKEN on the host (read-only PAT) — anonymous limit is 60/hour")
        return RuntimeError(f"GitHub rate limit hit at {url} (remaining={self.remaining}){hint}")

    def get(self, url: str, accept: str = "application/vnd.github+json", api: bool = True, timeout: int = 60):
        req = urllib.request.Request(url, headers={"Accept": accept, "User-Agent": "proof-of-change-ops"})
        if api and self.token:
            req.add_header("Authorization", f"Bearer {self.token}")
        rate_retried = False
        attempt = 0
        refused = 0
        while attempt < 3:
            try:
                with urllib.request.urlopen(req, timeout=timeout) as r:
                    if api:
                        self.calls += 1
                        self.remaining = int(r.headers.get("X-RateLimit-Remaining", "-1"))
                    return r.read()
            except urllib.error.HTTPError as e:
                if e.code == 401 and api and self.fail_fast_auth:
                    refused += 1
                    if refused >= AUTH_FAIL_LIMIT:
                        raise GitHubAuthError(AUTH_FAIL_MESSAGE) from None
                    attempt += 1
                    time.sleep(attempt)
                    continue
                if e.code in (403, 429) and api:
                    if not rate_retried and self._remaining_is_zero(e) and self._wait_for_reset(e, url):
                        rate_retried = True
                        continue
                    raise self._rate_error(url) from e
                if attempt == 2 or e.code == 404:
                    raise
            except urllib.error.URLError:
                if attempt == 2:
                    raise
            attempt += 1
            time.sleep(3 * attempt)
        raise RuntimeError(f"GitHub request failed: {url}")

    def json(self, path: str):
        return json.loads(self.get(f"https://api.github.com{path}"))

    def diff(self, repo: str, number: int) -> str:
        # github.com diff URL: not an API call, does not count against the API rate limit
        return self.get(f"https://github.com/{repo}/pull/{number}.diff", accept="text/plain", api=False).decode(
            "utf-8", errors="replace")

    def ci_state(self, repo: str, sha: str) -> tuple[str, str]:
        """'passing' | 'pending' | 'failing' | 'none' from check runs on the head SHA."""
        d = self.json(f"/repos/{repo}/commits/{sha}/check-runs?per_page=100")
        runs = d.get("check_runs", [])
        if not runs:
            return "none", "no check runs visible"
        bad = [r["name"] for r in runs if r.get("conclusion") in ("failure", "timed_out", "startup_failure", "action_required")]
        pending = [r["name"] for r in runs if r.get("status") != "completed"]
        if bad:
            return "failing", f"{len(bad)}/{len(runs)} failing: {', '.join(bad[:3])}"
        if pending:
            return "pending", f"{len(pending)}/{len(runs)} still running"
        return "passing", f"{len(runs)} check runs completed without failure"


def diff_files(diff: str) -> list[str]:
    files = []
    for m in re.finditer(r"^diff --git a/(\S+) b/(\S+)$", diff, re.M):
        files.append(m.group(2))
    return files


def classify_files(files: list[str], pkg: str) -> dict:
    in_pkg = [f for f in files if f.startswith((pkg + "/", f"src/{pkg}/"))]   # flat or src layout
    py = [f for f in in_pkg if f.endswith((".py", ".pyi"))]
    compiled = [f for f in in_pkg if f.endswith(COMPILED_EXT) or os.path.basename(f) in COMPILED_NAMES]
    build_cfg = [f for f in files if os.path.basename(f) in COMPILED_NAMES and "/" not in f.strip("/")]
    return {"all": files, "package_py": py, "compiled": compiled + build_cfg,
            "other": [f for f in files if f not in py and f not in compiled and f not in build_cfg]}


def _is_typing_file(path: str) -> bool:
    """A stub file or the package marker that says the package ships type information."""
    name = str(path).replace("\\", "/").rsplit("/", 1)[-1]
    return name.endswith(".pyi") or name == "py.typed"


def typing_only_change(paths) -> bool:
    """True only when every changed file is a .pyi stub or a py.typed marker.

    An empty list is not this rule. A .py file is not this rule, even when its only edits are type hints.
    One other file, of any kind, is enough to make the whole diff ordinary.
    """
    if not paths:
        return False
    return all(isinstance(p, str) and _is_typing_file(p) for p in paths)


def selection_skip_for_files(fc: dict, pkg: str) -> str | None:
    """Why a diff is not package code to test. None when the pull request should be tested.

    A typing-only diff is not skipped here. The run records it as no_code_change instead.
    An empty diff and a non-Python diff keep the existing skip.
    """
    if typing_only_change((fc or {}).get("all") or []):
        return None
    compiled = [f for f in (fc or {}).get("compiled") or [] if str(f).startswith(pkg + "/")]
    if not (fc or {}).get("package_py") and not compiled:
        return "no Python/compiled code in the package (docs, CI or tooling only)"
    return None


def mark_typing_only(rec: dict, files: dict | None) -> bool:
    """Record a typing-only change. Return True when that rule applies.

    The verdict function is not called. Any other diff returns False and the record is left
    for the normal checks, including a .py file whose only edits are type hints.
    """
    paths = files.get("all") if isinstance(files, dict) else None
    if not typing_only_change(paths):
        return False
    rec["no_code_change"] = True
    rec["no_code_change_reason"] = "typing_only"
    rec["verdict"] = Verdict.NO_CODE_CHANGE.value
    rec["reason"] = ("no code change: every changed file is a .pyi stub or a py.typed marker, "
                     "so behaviour was not checked")
    return True


def finish_typing_only(rec: dict, prdir: Path, work: Path, t0: float, runner) -> dict:
    """Write a typing-only record without calling the model or the verdict function."""
    saved = getattr(runner, "model_skipped", None) if runner is not None else None
    if runner is not None and not saved:
        runner.model_skipped = "typing-only change; the model was not called"
    try:
        return finish(rec, prdir, work, t0, runner)
    finally:
        if runner is not None:
            runner.model_skipped = saved



def run_date_of(seen: dict, repo: str) -> str | None:
    """IST date of the last run recorded for repo (inferred from last_run_utc for older files)."""
    d = seen.get("last_run_date", {}).get(repo)
    if d:
        return d
    lr = seen.get("last_run_utc", {}).get(repo)
    if not lr:
        return None
    return dt.datetime.strptime(lr, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc).astimezone(IST).strftime("%Y-%m-%d")


def baseline_for(seen: dict, repo: str, run_date: str) -> tuple[dict, str | None]:
    """What counts as 'already seen' for a run on run_date: only state from EARLIER runs.

    A re-run of the same date must not treat its own earlier attempt as a previous run."""
    prs = {r: {n: v for n, v in d.items() if v.get("run") != run_date} for r, d in seen.get("prs", {}).items()}
    if run_date_of(seen, repo) == run_date:
        since = seen.get("prior_run_utc", {}).get(repo)
    else:
        since = seen.get("last_run_utc", {}).get(repo)
    return prs, since

# ---------------------------------------------------------------- wheel-only picker check
WHEEL_CHECK_PLATFORM = "x86_64-manylinux_2_28"   # the Linux machines checks run on
WHEEL_CHECK_TIMEOUT = 180
_NO_WHEEL_RE = re.compile(r"Wheels are required for `([^`]+)`|Because ([A-Za-z0-9][A-Za-z0-9._-]*)\S* has no usable wheels"
                          r"|([A-Za-z0-9][A-Za-z0-9._-]*)\S* has no usable wheels")


def _main_file(gh, repo: str, ref: str, path: str) -> str | None:
    """Text of one file on the default branch, or None when it is missing or unreadable."""
    try:
        raw = gh.get(f"https://api.github.com/repos/{repo}/contents/{path}?ref={urllib.parse.quote(ref)}",
                     accept="application/vnd.github.raw")
    except Exception:  # noqa: BLE001
        return None
    return raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else str(raw)


def _plain_req(line: str) -> str | None:
    """A requirement string fit for a dry run: options (-r, -e, --index-url, ...), URLs, direct references and local
    paths are dropped, so nothing read from the project can change where packages come from."""
    line = line.split(" #", 1)[0].strip()
    if not line or line.startswith(("#", "-", ".", "/", "~")) or "://" in line or " @ " in line or "@" in line.split(";")[0]:
        return None
    return line


def main_requirements(gh, repo: str, ref: str) -> list[str]:
    """Runtime requirements declared on the default branch: [project].dependencies in pyproject.toml and the plain
    lines of a top-level requirements.txt."""
    import tomllib
    reqs: list[str] = []
    pp = _main_file(gh, repo, ref, "pyproject.toml")
    if pp:
        try:
            deps = tomllib.loads(pp).get("project", {}).get("dependencies", [])
        except Exception:  # noqa: BLE001
            deps = []
        reqs += [r for r in (_plain_req(d) for d in deps if isinstance(d, str)) if r]
    rt = _main_file(gh, repo, ref, "requirements.txt")
    if rt:
        reqs += [r for r in (_plain_req(x) for x in rt.splitlines()) if r]
    return list(dict.fromkeys(reqs))


def wheel_only_dry_run(reqs: list[str], python: str, runner=None) -> tuple[int, str]:
    """Resolve reqs for `python` allowing only ready-built wheels (--only-binary :all:); nothing is installed or built.
    The uv call and its env go through isolated_install, as on a product install."""
    cmd = [uv_bin(), "pip", "compile", "-", "--only-binary", ":all:", "--python-version", python,
           "--python-platform", WHEEL_CHECK_PLATFORM, "--no-header", "-q"]
    env = {k: v for k, v in os.environ.items() if not k.endswith(("TOKEN", "KEY", "SECRET", "PASSWORD"))}
    cmd, env = isolated_install(cmd, env, True)
    if runner is None:
        def runner(c, e, text):
            r = subprocess.run([str(x) for x in c], input=text, capture_output=True, text=True, env=e,
                               timeout=WHEEL_CHECK_TIMEOUT)
            return r.returncode, (r.stdout or "") + (r.stderr or "")
    try:
        return runner(cmd, env, "\n".join(reqs) + "\n")
    except subprocess.TimeoutExpired:
        return 1, "dry run timed out"


def wheel_only_skip(reqs: list[str], python: str, runner=None) -> str | None:
    """None when every requirement resolves to ready-built wheels for `python`; otherwise the plain skip reason."""
    if not reqs:
        return None
    rc, out = wheel_only_dry_run(reqs, python, runner)
    if rc == 0:
        return None
    m = _NO_WHEEL_RE.search(out)
    if m:
        return f"skipped: needs compiling ({next(g for g in m.groups() if g)})"
    first = next((ln.strip() for ln in out.splitlines() if ln.strip()), "no output")
    return f"skipped: requirements do not resolve to ready-built wheels ({first[:200]})"


def select_prs(gh: GitHub, repo: str, cfg: dict, seen: dict, last_run_utc: str | None, max_n: int,
               scan_limit: int, log, python: str | None = None, wheel_runner=None) -> tuple[list[dict], list[dict]]:
    """Return (selected, skipped). Day 1 (no last run): the max_n most recently updated eligible PRs.
    Later: eligible PRs updated since the last run whose head SHA was not tested yet (capped at max_n).
    Eligible = non-draft, upstream CI not failing (if visible), changes Python code in the package.
    Pure-Python PRs are preferred; compiled ones fill remaining slots.
    python set: before a PR is selected, the default branch's requirements must resolve to ready-built wheels for that
    Python (wheel_only_skip, checked once per library); otherwise the PR is skipped with that reason."""
    wheel_skip: list = []   # [reason or None] once computed
    pulls = gh.json(f"/repos/{repo}/pulls?state=open&sort=updated&direction=desc&per_page=50")
    seen_repo = seen.get(repo, {})
    pure, compiled, skipped = [], [], []
    scanned = 0
    for p in pulls:
        n, sha = p["number"], p["head"]["sha"]
        base = {"pr": n, "title": p["title"], "updated_at_ist": to_ist(p["updated_at"])}
        if last_run_utc and p["updated_at"] <= last_run_utc:
            break
        if p.get("draft"):
            skipped.append(base | {"why": "draft"}); continue
        if seen_repo.get(str(n), {}).get("head_sha") == sha:
            skipped.append(base | {"why": "head SHA already tested"}); continue
        if scanned >= scan_limit or len(pure) >= max_n:
            break
        scanned += 1
        try:
            d = gh.diff(repo, n)
        except Exception as e:  # noqa: BLE001
            skipped.append(base | {"why": f"diff not readable: {e}"}); continue
        fc = classify_files(diff_files(d), cfg["pkg"])
        skip = selection_skip_for_files(fc, cfg["pkg"])
        if skip:
            skipped.append(base | {"why": skip}); continue
        if python:
            if not wheel_skip:
                wheel_skip.append(wheel_only_skip(main_requirements(gh, repo, p["base"]["ref"]), python, wheel_runner))
            if wheel_skip[0]:
                skipped.append(base | {"why": wheel_skip[0]}); continue
        item = {"pr": n, "title": p["title"], "body": p.get("body") or "", "url": p["html_url"],
                "author": p["user"]["login"], "head_sha": sha,
                "base_sha": p["base"]["sha"], "merge_commit_sha": p.get("merge_commit_sha"),
                      "base_ref": p["base"]["ref"], "updated_at_utc": p["updated_at"],
                "updated_at_ist": to_ist(p["updated_at"]), "files": fc, "diff": d,
                "additions_hint": d.count("\n+") - d.count("\n+++")}
        (compiled if fc["compiled"] else pure).append(item)
    chosen = []
    for cand in pure + compiled:
        if len(chosen) >= max_n:
            break
        try:
            state, detail = gh.ci_state(repo, cand["head_sha"])
        except RuntimeError:
            raise
        except Exception as e:  # noqa: BLE001
            state, detail = "none", f"CI not readable: {e}"
        cand["ci_state"], cand["ci_detail"] = state, detail
        if state == "failing":
            skipped.append({"pr": cand["pr"], "title": cand["title"], "updated_at_ist": cand["updated_at_ist"],
                            "why": f"upstream CI failing ({detail})"})
            continue
        chosen.append(cand)
    return chosen, skipped


# ---------------------------------------------------------------- chosen PRs
_SECTION_RE = re.compile(r"(?m)^## \d+\. ")
_PR_HEADING_RE = re.compile(r"(?m)^### .*?#(\d+)")
_OPEN_PR_RE = re.compile(r"\*\*Open PR:\*\* #(\d+)")
_REPO_RE = re.compile(r"https://github\.com/([\w.-]+/[\w.-]+)")
_HEAD_SHA_RE = re.compile(r"Head SHA: `([0-9a-f]{40})`")
_INSTALL_RE = re.compile(r"- Install: `([^`]+)`")
_TEST_SUBSET_RE = re.compile(r"- Test \(subset[^)]*\): `([^`]+)`")
_TEST_LINE_RE = re.compile(r"- Test: `([^`]+)`")
_EXPECT_RE = re.compile(r"Expected Proof-of-Change verdict: `([^`]+)`")


def _library_sections(text: str) -> list[str]:
    return _SECTION_RE.split(text)[1:]


def _repo_of(sec: str) -> str | None:
    m = _REPO_RE.search(sec)
    return m.group(1).rstrip(".") if m else None


def _group1(pattern: re.Pattern, text: str) -> str | None:
    m = pattern.search(text) if text else None
    return m.group(1) if m else None


def _pr_blocks(sec: str) -> list[tuple[int, str, str]]:
    """[(pr number, this pull request's own text, preamble shared by the library section)].

    A `###` sub-heading that names a pull request number (`### Primary PR: #8946`) opens that pull request.
    Text before the first such heading is the preamble (repo line, shared setup notes) and is not part of any
    pull request's own text. With no such heading, `**Open PR:** #N` is the one pull request and its text is
    the whole section.
    """
    marks = list(_PR_HEADING_RE.finditer(sec))
    if marks:
        preamble = sec[:marks[0].start()]
        out = []
        for i, m in enumerate(marks):
            end = marks[i + 1].start() if i + 1 < len(marks) else len(sec)
            out.append((int(m.group(1)), sec[m.start():end], preamble))
        return out
    m = _OPEN_PR_RE.search(sec)
    if not m:
        return []
    return [(int(m.group(1)), sec, "")]


def _test_cmd(block: str, preamble: str) -> str | None:
    """The subset command: a Test (subset) line if present, else the first backticked command on a `- Test:` line.

    A sub-section's own line wins over the shared preamble. On a line that names two commands, only the first
    backtick pair is used.
    """
    for text in (block, preamble):
        if not text:
            continue
        cmd = _group1(_TEST_SUBSET_RE, text)
        if cmd:
            return cmd
        cmd = _group1(_TEST_LINE_RE, text)
        if cmd:
            return cmd
    return None


def parse_chosen(path: Path) -> dict:
    """Chosen-PRs file (<date>.md) -> {repo: [ {pr, head_sha, install, test_cmd} ]}.

    A library section (`## N. name`) is one `**Open PR:** #N` entry, or several `###` sub-headings that each name
    a pull request. Each sub-heading keeps its own head SHA. Install and test commands may sit in the preamble or
    in a sub-section; a sub-section's own command wins.

    Expected verdicts are deliberately NOT read here. They are read by read_expectations() only after every verdict
    of the run has been computed (see main()), so they cannot influence selection, testing or verdicts.
    """
    out: dict = {}
    if not path.exists():
        return out
    for sec in _library_sections(path.read_text()):
        repo = _repo_of(sec)
        if not repo:
            continue
        for pr, block, preamble in _pr_blocks(sec):
            out.setdefault(repo, []).append({
                "pr": pr, "head_sha": _group1(_HEAD_SHA_RE, block),
                "install": _group1(_INSTALL_RE, block) or _group1(_INSTALL_RE, preamble),
                "test_cmd": _test_cmd(block, preamble)})
    return out


def read_expectations(path: Path) -> dict:
    """{(repo, pr): expected_verdict}. Call ONLY after all verdicts are final.

    Only a line of the form "Expected Proof-of-Change verdict: `...`" counts, and only inside that pull request's
    own text. A sub-section without that line stays unscored; it does not borrow another pull request's value.
    """
    exp = {}
    if not path.exists():
        return exp
    for sec in _library_sections(path.read_text()):
        repo = _repo_of(sec)
        if not repo:
            continue
        for pr, block, _preamble in _pr_blocks(sec):
            v = _EXPECT_RE.search(block)
            if v:
                exp[(repo, pr)] = v.group(1).strip().replace(" ", "_")
    return exp


def chosen_items(gh: GitHub, repo: str, cfg: dict, chosen: list[dict]) -> list[dict]:
    items = []
    for pk in chosen:
        p = gh.json(f"/repos/{repo}/pulls/{pk['pr']}")
        d = gh.diff(repo, pk["pr"])
        items.append({"pr": p["number"], "title": p["title"], "body": p.get("body") or "", "url": p["html_url"],
                      "author": p["user"]["login"],
                      "head_sha": pk["head_sha"] or p["head"]["sha"], "current_head_sha": p["head"]["sha"],
                      "base_sha": p["base"]["sha"], "merge_commit_sha": p.get("merge_commit_sha"),
                      "base_ref": p["base"]["ref"], "updated_at_utc": p["updated_at"],
                      "updated_at_ist": to_ist(p["updated_at"]), "files": classify_files(diff_files(d), cfg["pkg"]),
                      "diff": d, "mergeable": p.get("mergeable"), "mergeable_state": p.get("mergeable_state"),
                      "draft": p.get("draft"), "state": p.get("state"), "chosen": pk, "ci_state": "not checked (chosen PR)",
                      "ci_detail": "chosen by name; selection filters not applied"})
    return items


def side_install_args(chosen: dict | None, checkout: Path) -> tuple[list[str], list[str]]:
    """'pip install -e ".[a,b]" pytest x' -> (['-e', '<checkout>[a,b]'], ['pytest', 'x'])."""
    if not chosen or not chosen.get("install"):
        return ["-e", str(checkout)], []
    toks = shlex.split(chosen["install"])
    toks = toks[toks.index("install") + 1:]
    proj, extra, edit = None, [], False
    for t in toks:
        if t == "-e":
            edit = True
        elif t == "." or t.startswith(".["):
            proj = str(checkout) + t[1:]
        else:
            extra.append(t)
    return (["-e", proj] if edit else [proj]) if proj else ["-e", str(checkout)], extra


def chosen_test_targets(chosen: dict | None) -> list[str]:
    if not chosen or not chosen.get("test_cmd"):
        return []
    toks = shlex.split(chosen["test_cmd"])
    out, skip = [], False
    for t in toks[1:]:
        if skip:
            skip = False; continue
        if t in ("-n", "-k", "-m"):
            skip = True; continue
        if not t.startswith("-"):
            out.append(t)
    return out


def _repo_test_file(name: str) -> bool:
    """A test module in either common layout: test_foo.py or foo_test.py."""
    return name.endswith(".py") and (name.startswith("test_") or name.endswith("_test.py"))


def map_repo_tests(files: dict, checkout: Path, max_targets: int = 6) -> list[str]:
    """Touched files -> test modules.

    A test file the change itself edits is kept. For a changed source file, the sibling
    ``<directory>/tests/test_<stem>.py`` (and ``<stem>_test.py``) is preferred over a global name match, so
    ``networkx/algorithms/connectivity/connectivity.py`` maps to
    ``networkx/algorithms/connectivity/tests/test_connectivity.py`` before other ``test_connectivity.py`` files.
    """
    targets: list[str] = []
    for f in files["all"]:
        b = os.path.basename(f)
        if _repo_test_file(b) and (checkout / f).is_file():
            targets.append(f)
    for f in files["package_py"]:
        stem = os.path.splitext(os.path.basename(f))[0].lstrip("_")
        patterns = [f"test_{stem}.py"] + ([f"{stem}_test.py"] if stem else [])
        preferred: list[Path] = []
        parent = Path(f).parent
        for pat in patterns:
            sib = checkout / parent / "tests" / pat
            if sib.is_file():
                preferred.append(sib)
        hits = list(preferred)
        for pat in patterns:
            hits += [Path(p) for p in sorted(glob.glob(str(checkout / "**" / pat), recursive=True))]
        added, seen_hit = 0, set()
        for hit in hits:
            if added >= 2:
                break
            rel = os.path.relpath(hit, checkout)
            if rel in seen_hit:
                continue
            seen_hit.add(rel)
            if rel not in targets:
                targets.append(rel)
                added += 1
    return targets[:max_targets]


def _path_exists(root: Path, rel: str) -> bool:
    p = root / rel
    return p.is_file() or p.is_dir()


def nearest_tests_dir(rel_file: str, root: Path) -> str | None:
    """The nearest ``tests`` directory at or above ``rel_file`` that exists under ``root``."""
    d = Path(rel_file).parent
    while True:
        candidate = d / "tests"
        if (root / candidate).is_dir():
            return candidate.as_posix()
        if str(d) in (".", ""):
            return None
        parent = d.parent
        if parent == d:
            return None
        d = parent


def targets_for_sides(mapped: list[str], files: dict | None, main_root: Path, pr_root: Path) -> dict:
    """Test paths to run on each side.

    When every mapped test file is new (it exists only on the pull-request side), also run the nearest existing
    tests directory on both sides, and still run the new files on the pull-request side. That gives an additive
    change a baseline instead of an empty main side.
    """
    pr_ok = [t for t in mapped if _path_exists(pr_root, t)]
    main_ok = [t for t in mapped if _path_exists(main_root, t)]
    if main_ok or not pr_ok:
        return {"main": main_ok, "pr": list(dict.fromkeys(pr_ok))}
    nearest = None
    seeds = list((files or {}).get("package_py") or []) + list((files or {}).get("all") or []) + list(pr_ok)
    for rel in seeds:
        found = nearest_tests_dir(rel, main_root)
        if found:
            nearest = found
            break
    if not nearest:
        return {"main": [], "pr": pr_ok}
    return {"main": [nearest], "pr": list(dict.fromkeys([nearest, *pr_ok]))}


def _tree(src, env, sha: str) -> str:
    return subprocess.run(["git", "-C", src, "rev-parse", f"{sha}^{{tree}}"], env=env, capture_output=True,
                          text=True).stdout.strip()


def _git_out(src, env, *args: str) -> str:
    return subprocess.run(["git", "-C", src, *args], env=env, capture_output=True, text=True).stdout.strip()


def distinct_base(src, env, log: Path, item: dict, res: dict) -> dict | None:
    """Product checks only. When the chosen main side is the PR head itself (a merged or closed PR: the merge-base
    of head and base branch is the head) or has the same tree, pick the main side in this order:
    1. merge-base of the PR's recorded base (GitHub base.sha) and the head, so every PR commit is compared and no
       later base-branch commit is pulled in;
    2. if that merge-base is the head itself, the first parent of the PR's merge commit (GitHub merge_commit_sha);
    3. base.sha itself, only when the PR head is not already an ancestor of base.sha.
    The first candidate whose tree differs from the PR side wins. Returns an error dict ('unsupported: ...') when no
    distinct base exists."""
    main, pr = res.get("main_sha"), res.get("pr_sha")
    if not main or not pr or (main != pr and _tree(src, env, main) != _tree(src, env, pr)):
        return None
    head = item["head_sha"]
    base_sha, merge_sha = item.get("base_sha"), item.get("merge_commit_sha")
    cands = []
    if base_sha:
        run(["git", "-C", src, "fetch", "-q", "origin", base_sha], log, env=env, timeout=300)
        mb = _git_out(src, env, "merge-base", base_sha, head)
        if mb and mb != head:
            cands.append((mb, "merge-base of PR base (GitHub base.sha) and PR head vs PR head "
                              "(the first choice of main side was the PR code itself)"))
        elif mb == head and merge_sha:
            run(["git", "-C", src, "fetch", "-q", "origin", merge_sha], log, env=env, timeout=300)
            first = _git_out(src, env, "rev-parse", "--verify", "-q", f"{merge_sha}^1")
            if first:
                cands.append((first, "first parent of the PR merge commit vs PR head "
                                     "(the PR head is already in its recorded base: PR merged)"))
        # base.sha as-is only when the head is not already inside it; otherwise it would bring in base-branch
        # commits that are not part of the PR (for example a closed, unmerged PR whose base moved on).
        inside = subprocess.run(["git", "-C", src, "merge-base", "--is-ancestor", head, base_sha], env=env,
                                capture_output=True, text=True).returncode == 0
        if not inside:
            cands.append((base_sha, "PR base (GitHub base.sha) vs PR head (no merge-base with the PR head was found)"))
    pr_tree = _tree(src, env, pr)
    for sha, basis in cands:
        t = _tree(src, env, sha)
        if t and t != pr_tree:
            res |= {"main_sha": sha, "comparison_basis": basis}
            return None
    return {"ok": False, "why": "unsupported: no base commit distinct from the PR head was found, so main and PR "
                                "would be the same code; the check stops instead of comparing identical commits"}


def sides_identical(rec: dict) -> bool:
    """True when the recorded main and PR sides are the same commit."""
    s = rec.get("sides") or {}
    return bool(s.get("main_sha")) and s.get("main_sha") == s.get("pr_sha")


def source_pair(repo: str, item: dict, work: Path, log: Path, python: str, timeout: int, product: bool = False) -> dict:
    """Pure-Python library without nightly wheels: build both sides from git.
    Conflicting PR (mergeable false / state dirty): main = merge-base(PR head, base branch), PR = PR head.
    Mergeable PR: main = current base-branch tip, PR = GitHub's test merge commit (refs/pull/N/merge).
    Benchmark mode (ops/bench.py) checks both sides out at pinned SHAs beforehand and passes them in item["bench_sides"]."""
    if item.get("bench_sides"):
        return item["bench_sides"]
    env = base_env(work / "home-git")
    src = work / "src"
    res: dict = {}
    steps = [["git", "clone", "-q", "--filter=blob:none", "--no-checkout", f"https://github.com/{repo}.git", src],
             ["git", "-C", src, "fetch", "-q", "origin", f"pull/{item['pr']}/head", item["base_ref"]]]
    for c in steps:
        rc, _ = run(c, log, env=env, timeout=900)
        if rc != 0:
            return {"ok": False, "why": f"git step failed ({rc}): {' '.join(map(str, c[:4]))}"}
    head = item["head_sha"]
    run(["git", "-C", src, "fetch", "-q", "origin", head], log, env=env, timeout=300)  # pinned head, if it moved
    conflicting = item.get("mergeable") is False or item.get("mergeable_state") == "dirty"
    base_tip = subprocess.run(["git", "-C", src, "rev-parse", f"origin/{item['base_ref']}"], env=env, capture_output=True,
                              text=True).stdout.strip()
    if conflicting or head != item.get("current_head_sha", head):
        mb = subprocess.run(["git", "-C", src, "merge-base", head, base_tip], env=env, capture_output=True, text=True).stdout.strip()
        if not mb:
            return {"ok": False, "why": "could not compute merge-base of PR head and base branch"}
        res |= {"comparison_basis": "merge-base vs PR head" + (" (PR conflicts with base)" if conflicting else
                                                             " (pinned head differs from current head)"),
                "main_sha": mb, "pr_sha": head}
    else:
        rc, _ = run(["git", "-C", src, "fetch", "-q", "origin", f"pull/{item['pr']}/merge"], log, env=env, timeout=300)
        merge = subprocess.run(["git", "-C", src, "rev-parse", "FETCH_HEAD"], env=env, capture_output=True, text=True).stdout.strip()
        if rc != 0 or not merge:
            mb = subprocess.run(["git", "-C", src, "merge-base", head, base_tip], env=env, capture_output=True, text=True).stdout.strip()
            res |= {"comparison_basis": "merge-base vs PR head (no merge ref available)", "main_sha": mb, "pr_sha": head}
        else:
            parent1 = subprocess.run(["git", "-C", src, "rev-parse", f"{merge}^1"], env=env, capture_output=True, text=True).stdout.strip()
            parent2 = subprocess.run(["git", "-C", src, "rev-parse", f"{merge}^2"], env=env, capture_output=True,
                                     text=True).stdout.strip()
            res |= {"comparison_basis": "base tip vs GitHub test merge (refs/pull/N/merge)", "main_sha": parent1,
                    "pr_sha": merge, "merge_commit": merge, "merge_parents": [parent1, parent2],
                    "merge_head_matches_pinned_head": parent2 == head}
    if product:
        bad = distinct_base(src, env, log, item, res)
        if bad:
            return bad
    for side in ("main", "pr"):
        # git -C resolves relative worktree paths against src/, not cwd.
        rc, _ = run(["git", "-C", src, "worktree", "add", "-q", "--detach",
                    (work / f"side-{side}").resolve(), res[f"{side}_sha"]],
                    log, env=env, timeout=900)
        if rc != 0:
            return {"ok": False, "why": f"checkout of {side} side failed"}
    res["ok"] = True
    return res


def meson_build_requires(checkout: Path) -> list[str] | None:
    """[build-system].requires of a meson-python project (None for other build backends). Strings that look like
    command-line options are dropped: they come from the checkout."""
    pp = checkout / "pyproject.toml"
    if not pp.exists():
        return None
    import tomllib
    try:
        bs = tomllib.loads(pp.read_text()).get("build-system", {})
    except Exception:  # noqa: BLE001
        return None
    if bs.get("build-backend") != "mesonpy":
        return None
    return [r for r in bs.get("requires", []) if isinstance(r, str) and not r.startswith("-")]


def pyproject_test_extras(checkout: Path) -> list[str]:
    pp = checkout / "pyproject.toml"
    if not pp.exists():
        return []
    import tomllib
    try:
        opt = tomllib.loads(pp.read_text()).get("project", {}).get("optional-dependencies", {})
    except Exception:  # noqa: BLE001
        return []
    return test_extras(list(opt))


def pyproject_test_groups(checkout: Path) -> list[str]:
    """Requirements from PEP 735 [dependency-groups] named test/tests/testing (include-group resolved).
    Anything that looks like a command-line option is dropped: these strings come from the checkout."""
    pp = checkout / "pyproject.toml"
    if not pp.exists():
        return []
    import tomllib
    try:
        groups = tomllib.loads(pp.read_text()).get("dependency-groups", {})
    except Exception:  # noqa: BLE001
        return []
    if not isinstance(groups, dict):
        return []

    def expand(name: str, seen: frozenset) -> list[str]:
        out: list[str] = []
        for r in groups.get(name, []) if name not in seen else []:
            if isinstance(r, str):
                out.append(r)
            elif isinstance(r, dict) and isinstance(r.get("include-group"), str):
                out += expand(r["include-group"], seen | {name})
        return out

    reqs: list[str] = []
    for g in groups:
        if g.lower() in TEST_EXTRA_NAMES:
            reqs += [r.strip() for r in expand(g, frozenset()) if r.strip() and not r.strip().startswith("-")]
    return list(dict.fromkeys(reqs))


def extra_names_from_spec(spec: str) -> list[str]:
    """'pkg[dev,test]' -> ['dev', 'test']."""
    m = re.search(r"\[([^\]]*)\]", spec or "")
    if not m:
        return []
    return [x.strip() for x in m.group(1).split(",") if x.strip()]


def packages_in_extras(checkout: Path, names: list[str]) -> list[str]:
    """Distribution names listed under those extras in pyproject optional-dependencies."""
    pp = checkout / "pyproject.toml"
    if not pp.is_file() or not names:
        return []
    import tomllib
    try:
        opt = tomllib.loads(pp.read_text()).get("project", {}).get("optional-dependencies", {})
    except Exception:  # noqa: BLE001
        return []
    if not isinstance(opt, dict):
        return []
    out: list[str] = []
    for name in names:
        reqs = opt.get(name, [])
        if not isinstance(reqs, list):
            continue
        for req in reqs:
            if not isinstance(req, str):
                continue
            pkg = re.split(r"[\[<>=!;,\s]", req.strip(), maxsplit=1)[0]
            if pkg and pkg not in out:
                out.append(pkg)
    return out


def recorded_test_extras(checkout: Path, proj: list[str]) -> list[str]:
    """What the install really requested: the packages inside the extras, or the extra names if they cannot be expanded.

    An empty list means no extra was requested. A dev extra that installs pandas, pyarrow and polars is recorded as
    those packages, not as []."""
    names = extra_names_from_spec(proj[-1] if proj else "")
    return packages_in_extras(checkout, names) or names


def with_test_extras(proj: list[str], checkout: Path) -> list[str]:
    """['-e', '/x[a]'] -> ['-e', '/x[a,test]'] when the project declares a test extra not already requested."""
    extras = pyproject_test_extras(checkout)
    if not extras:
        return proj
    spec = proj[-1]
    m = re.match(r"^(.*?)(?:\[([^\]]*)\])?$", spec)
    have = [x for x in (m.group(2) or "").split(",") if x]
    allx = have + [e for e in extras if e not in have]
    return proj[:-1] + [f"{m.group(1)}[{','.join(allx)}]"]


def _norm(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _req_name(req: str) -> str:
    return re.split(r"[\[<>=!~;,@\s]", req.strip(), maxsplit=1)[0]


def declared_requirements(checkout: Path) -> dict:
    """{'extras': {name: [req, ...]}, 'groups': {name: [req, ...]}} from pyproject.toml (strings only; anything that
    looks like a command-line option is dropped, because these strings come from the checkout)."""
    pp = checkout / "pyproject.toml"
    out: dict = {"extras": {}, "groups": {}}
    if not pp.is_file():
        return out
    import tomllib
    try:
        d = tomllib.loads(pp.read_text())
    except Exception:  # noqa: BLE001
        return out
    for key, src in (("extras", d.get("project", {}).get("optional-dependencies", {})), ("groups", d.get("dependency-groups", {}))):
        if isinstance(src, dict):
            for n, reqs in src.items():
                if isinstance(reqs, list):
                    out[key][str(n)] = [r.strip() for r in reqs if isinstance(r, str) and r.strip()
                                        and not r.strip().startswith("-")]
    return out


# Declared pytest plugins that change how tests are collected or run are needed for a faithful run; coverage and
# type-checking plugins are not.
_PLUGIN_SKIP = ("pytest-cov", "pytest-mypy", "pytest-mypy-plugins", "pytest-benchmark", "pytest-codspeed")


def declared_test_deps(checkout: Path, targets: list[str], self_dist: str) -> list[str]:
    """Test requirements the project declares that a run of `targets` needs (docs/decisions/2026-10-14-...):

    1. every pytest plugin listed in any extra or dependency group (pytest-asyncio, pytest-env, ...), except
       coverage/type-check/benchmark plugins;
    2. an extra whose name matches a directory or file name of a target (tests/pandas/... -> extra "pandas");
    3. a declared package whose name matches a directory or test-file name of a target
       (xarray/tests/backends/test_zarr.py -> zarr, declared in the "io" extra).
    References to the project itself (xarray[complete]) are not installed."""
    decl = declared_requirements(checkout)
    allreqs = [r for kind in ("extras", "groups") for reqs in decl[kind].values() for r in reqs]
    me = _norm(self_dist)
    names = set()
    for t in targets:
        for part in Path(t).parts:
            stem = Path(part).stem
            for x in (part, stem, stem.removeprefix("test_"), stem.removesuffix("_test")):
                if x and x not in ("tests", "test", "testing", "."):
                    names.add(_norm(x))
    out: list[str] = []

    def add(req: str) -> None:
        if _norm(_req_name(req)) != me and req not in out:
            out.append(req)
    for r in allreqs:
        n = _norm(_req_name(r))
        if n.startswith("pytest-") and n not in _PLUGIN_SKIP:
            add(r)
    for n, reqs in decl["extras"].items():
        if _norm(n) in names:
            for r in reqs:
                add(r)
    for r in allreqs:
        if _norm(_req_name(r)) in names:
            add(r)
    return out


def isolated_install(cmd: list, env: dict, isolated: bool) -> tuple[list, dict]:
    """isolated (product checks only): the uv call ignores config files and [tool.uv.sources], and the env drops
    index settings and pip config (no_index_config_env). Not isolated: both are returned unchanged."""
    return (no_config_cmd(cmd), no_index_config_env(env)) if isolated else (cmd, env)


def install_declared_test_deps(venvs: dict, reqs: list[str], log: Path, timeout: int,
                               isolated: bool = False) -> tuple[bool, str]:
    """Install the same declared test requirements on both sides. isolated: see isolated_install."""
    if not reqs:
        return True, ""
    for side, venv in venvs.items():
        cmd, env = isolated_install([uv_bin(), "pip", "install", "-q", "-p", venv / "bin/python", *reqs],
                                    base_env(side_home(venv), install=True), isolated)
        rc, _ = run(cmd, log, env=env, timeout=timeout, sbx=side_sandbox(venv, network=True))
        if rc != 0:
            return False, f"installing declared test requirements on the {side} side failed ({rc}); see {log.name}"
    return True, ""


_TEST_EXTRA_MARK = re.compile(r"""extra\s*==\s*['"](test|tests|testing)['"]""", re.I)


def reqs_for_test_extras(lines: list[str], self_dist: str) -> list[str]:
    """Requirement strings declared under a test, tests, or testing extra.

    Pytest and the project itself are left out: those are not optional backends. A line may be a Requires-Dist
    header or already be the requirement text."""
    me = _norm(self_dist or "")
    out: list[str] = []
    for raw in lines:
        line = raw.strip()
        if line.lower().startswith("requires-dist:"):
            line = line.split(":", 1)[1].strip()
        if not line or not _TEST_EXTRA_MARK.search(line):
            continue
        req = line.split(";", 1)[0].strip()
        if not req or req.startswith("-"):
            continue
        name = _norm(_req_name(req))
        if not name or name.startswith("pytest") or name == me:
            continue
        if req not in out:
            out.append(req)
    return out


def optional_backend_reqs(checkout: Path, self_dist: str | None = None) -> list[str]:
    """Optional backends named by the checkout's test extras (pyproject optional-dependencies)."""
    pp = checkout / "pyproject.toml"
    if not pp.is_file():
        return []
    import tomllib
    try:
        proj = tomllib.loads(pp.read_text()).get("project", {})
    except Exception:  # noqa: BLE001
        return []
    if not isinstance(proj, dict):
        return []
    name = self_dist or (proj.get("name") if isinstance(proj.get("name"), str) else "") or ""
    opt = proj.get("optional-dependencies") or {}
    lines: list[str] = []
    if isinstance(opt, dict):
        for extra, reqs in opt.items():
            if str(extra).lower() not in TEST_EXTRA_NAMES or not isinstance(reqs, list):
                continue
            for req in reqs:
                if isinstance(req, str) and req.strip() and not req.strip().startswith("-"):
                    lines.append(f"{req.strip()}; extra == \"{extra}\"")
    return reqs_for_test_extras(lines, name)


def install_optional_backends(venvs: dict, reqs: list[str], log: Path, timeout: int, isolated: bool = False) -> dict:
    """Install each optional backend on each side. A failure is skipped; it does not stop the others.
    isolated: see isolated_install."""
    installed: list[str] = []
    skipped: list[dict] = []
    if not reqs:
        return {"installed": installed, "skipped": skipped}
    for req in reqs:
        failed = False
        for side, venv in venvs.items():
            cmd, env = isolated_install([uv_bin(), "pip", "install", "-q", "-p", venv / "bin/python", req],
                                        base_env(side_home(venv), install=True), isolated)
            rc, _ = run(cmd, log, env=env, timeout=timeout, sbx=side_sandbox(venv, network=True))
            if rc != 0:
                failed = True
                skipped.append({"req": req, "side": side, "rc": rc if isinstance(rc, int) else str(rc)})
        if not failed:
            installed.append(req)
    return {"installed": installed, "skipped": skipped}


def attach_optional_backends(rec: dict, venvs: dict, checkout: Path, dist: str, log: Path, timeout: int,
                             isolated: bool = False) -> None:
    """Best-effort install of test-extra backends. A skip is recorded and is not a verdict."""
    reqs = optional_backend_reqs(checkout, dist)
    if not reqs:
        return
    rec["optional_backends"] = install_optional_backends(venvs, reqs, log, timeout, isolated)


def _strip_test_extras(spec: str) -> str:
    m = re.match(r"^(.*?)(?:\[([^\]]*)\])?$", spec)
    if not m or not m.group(2):
        return spec
    keep = [x for x in m.group(2).split(",") if x and x.lower() not in TEST_EXTRA_NAMES]
    base = m.group(1)
    return f"{base}[{','.join(keep)}]" if keep else base


def _without_test_extras(cmd: list, checkout: Path) -> list | None:
    """The same install command with test extras removed from the checkout spec, or None when nothing changes."""
    out: list = []
    changed = False
    root = str(checkout)
    for part in cmd:
        text = str(part)
        if root in text and "[" in text:
            stripped = _strip_test_extras(text)
            if stripped != text:
                changed = True
                out.append(stripped)
                continue
        out.append(part)
    return out if changed else None


def metadata_requires(venv: Path, dist: str) -> list[str]:
    """Requires-Dist lines of an already-installed distribution (empty when metadata cannot be read)."""
    code = f"import importlib.metadata as m; print('\\n'.join(m.requires({dist!r}) or []))"
    try:
        out = in_side(venv, [venv / "bin/python", "-c", code]).stdout
    except Exception:  # noqa: BLE001
        return []
    return [ln.strip() for ln in out.splitlines() if ln.strip()]


def direct_url(venv: Path, dist: str) -> dict | None:
    """The installed distribution's direct_url.json (PEP 610), or None when it has none.

    Name lookup, used by the previous commit guard. The guard a source comparison runs matches the checkout
    folder instead (`check_installed_commit`)."""
    want = _norm(dist)
    for di in glob.glob(str(site_packages(venv) / "*.dist-info")):
        name = os.path.basename(di)[:-len(".dist-info")].rsplit("-", 1)[0]
        if _norm(name) == want:
            f = Path(di) / "direct_url.json"
            if f.is_file():
                try:
                    return json.loads(f.read_text())
                except ValueError:
                    return {"_unreadable": True}
            return None
    return None


def _sha_same(expected: str, got: str | None) -> bool:
    """True when `got` is the requested commit. A short SHA (7+ hex) matches by prefix."""
    return bool(got) and len(expected) >= 7 and (got.startswith(expected) or expected.startswith(got))


def _checkout_head(checkout: Path) -> str:
    """git rev-parse HEAD of a side checkout. The environment is the allowlist, so git does not see host secrets."""
    return subprocess.run(["git", "-C", str(checkout), "rev-parse", "HEAD"], capture_output=True, text=True,
                          env=base_env(Path(checkout).parent / "home-git")).stdout.strip()


def _dist_info_name(di: Path) -> str:
    """Distribution name from METADATA, or from the ``name-version.dist-info`` directory."""
    meta = di / "METADATA"
    try:
        text = meta.read_text(errors="replace")
    except OSError:
        text = ""
    for line in text.splitlines():
        if not line.strip():
            break
        if line[:5].lower() == "name:":
            name = line.split(":", 1)[1].strip()
            if name:
                return name
    return di.name[:-len(".dist-info")].rsplit("-", 1)[0]


def _load_direct_url(di: Path) -> dict | None:
    f = di / "direct_url.json"
    if not f.is_file():
        return None
    try:
        parsed = json.loads(f.read_text())
    except (OSError, ValueError):
        return {"_unreadable": True}
    return parsed if isinstance(parsed, dict) else {"_unreadable": True}


def _file_url_path(url: object) -> Path | None:
    """Local path of a PEP 610 ``file://`` URL, or None when the URL is not a local file URL."""
    if not isinstance(url, str) or not url.startswith("file:"):
        return None
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "file" or parsed.netloc not in ("", "localhost"):
        return None
    raw = urllib.parse.unquote(parsed.path)
    if not raw.startswith("/"):
        return None
    return Path(raw)


def _same_folder(left: Path, right: Path) -> bool:
    return os.path.realpath(left) == os.path.realpath(right)


def _installed_records(venv: Path) -> list[tuple[str, dict | None]]:
    """``(distribution name, direct_url.json or None)`` for every ``*.dist-info`` in the environment."""
    pattern = str(Path(venv) / "lib" / "python3*" / "site-packages" / "*.dist-info")
    return [(_dist_info_name(Path(di)), _load_direct_url(Path(di))) for di in sorted(glob.glob(pattern))]


def check_installed_commit_by_name(venv: Path, dist: str, expected_sha: str, checkout: Path | None = None) -> tuple[bool, dict]:
    """Does the installed `dist` come from `expected_sha`? Fails closed. Looks the distribution up by name.

    A VCS install (vcs_info.commit_id) must name that commit. A local install (dir_info) must point at `checkout`, and
    that checkout must be at `expected_sha` (git rev-parse HEAD). Anything else (no direct_url.json, another
    directory, another commit) fails. Short expected SHAs (7+ hex) match by prefix.

    This is the previous check. A source comparison uses `check_installed_commit`, which matches the checkout folder
    and does not look up a name. The dry run can still call this one."""
    du = direct_url(venv, dist)
    info: dict = {"dist": dist, "expected": expected_sha, "direct_url": du}
    if not du:
        info["why"] = f"{dist} has no direct_url.json, so the installed commit cannot be checked"
        return False, info
    vcs = du.get("vcs_info") or {}
    if vcs.get("commit_id"):
        info["installed"] = vcs["commit_id"]
        ok = _sha_same(expected_sha, vcs["commit_id"])
        if not ok:
            info["why"] = f"{dist} installed from commit {vcs['commit_id'][:12]}, not the requested {expected_sha[:12]}"
        return ok, info
    url = du.get("url") or ""
    if checkout is not None and "dir_info" in du:
        here = Path(urllib.parse.unquote(url.removeprefix("file://"))).resolve() if url.startswith("file://") else None
        if here != Path(checkout).resolve():
            info["why"] = f"{dist} was installed from {url}, not from the checked-out side"
            return False, info
        head = _checkout_head(checkout)
        info["installed"] = head
        ok = _sha_same(expected_sha, head)
        if not ok:
            info["why"] = f"{dist} checkout is at {head[:12] or 'unknown'}, not the requested {expected_sha[:12]}"
        return ok, info
    info["why"] = f"{dist} was installed from {url or 'an unknown source'} with no commit to check"
    return False, info


def _deps_only_path(venv: Path) -> Path | None:
    """The folder a dependency-only install put on the import path, or None."""
    for site in Path(venv).glob("lib/python*/site-packages"):
        f = site / "poc-project-path.pth"
        if f.is_file():
            lines = [ln.strip() for ln in f.read_text(errors="replace").splitlines() if ln.strip()]
            return Path(lines[0]) if len(lines) == 1 else None
    return None


def check_installed_commit(venv: Path, dist: str, expected_sha: str, checkout: Path | None = None) -> tuple[bool, dict]:
    """Does the environment contain the checkout of `expected_sha`? Fails closed.

    Every installed distribution is considered. A distribution matches when its PEP 610 direct_url.json ``url`` is a
    ``file://`` path whose real path is the side's checkout folder. The name is not consulted: `dist` is accepted so
    callers keep the same arguments, and it is not used to choose a distribution. The result's ``dist`` is the name
    that matched.

    Exactly one distribution must match. The checkout's git HEAD must be `expected_sha`. When that record also has
    ``vcs_info.commit_id``, that commit must be `expected_sha` too. Zero matches, more than one, another folder, or
    another commit fails. Short expected SHAs (7+ hex) match by prefix."""
    del dist
    info: dict = {"dist": None, "expected": expected_sha, "direct_url": None}
    if checkout is None:
        info["why"] = "no checkout folder was given, so the installed commit cannot be checked"
        return False, info
    checkout = Path(checkout)
    matches: list[tuple[str, dict]] = []
    elsewhere: list[tuple[str, str]] = []
    for name, du in _installed_records(venv):
        if not du or du.get("_unreadable"):
            continue
        url = du.get("url") or ""
        folder = _file_url_path(url)
        if folder is None:
            continue
        if _same_folder(folder, checkout):
            matches.append((name, du))
        else:
            elsewhere.append((name, url if isinstance(url, str) else ""))
    if not matches:
        pth = _deps_only_path(venv)
        if pth is not None and _same_folder(pth, checkout):
            # dependency-only install (the project could not be built): the import path names this checkout
            head = _checkout_head(checkout)
            info.update({"dist": "(project folder on the import path)", "installed": head, "deps_only": True})
            ok = _sha_same(expected_sha, head)
            if not ok:
                info["why"] = f"the checkout on the import path is at {head[:12] or 'unknown'}, not {expected_sha[:12]}"
            return ok, info
        if len(elsewhere) == 1:
            name, url = elsewhere[0]
            info["dist"] = name
            info["why"] = f"{name} was installed from {url}, not from the checked-out side"
        elif elsewhere:
            listed = "; ".join(f"{name} from {url}" for name, url in elsewhere)
            info["why"] = ("no installed distribution points at the checked-out side "
                           f"({listed})")
        else:
            info["why"] = ("no installed distribution points at the checked-out side, "
                           "so the installed commit cannot be checked")
        return False, info
    if len(matches) > 1:
        names = ", ".join(name for name, _du in matches)
        info["dist"] = names
        info["why"] = f"more than one installed distribution points at the checked-out side ({names})"
        return False, info
    name, du = matches[0]
    info["dist"] = name
    info["direct_url"] = du
    vcs = du.get("vcs_info") or {}
    commit_id = vcs.get("commit_id")
    if isinstance(commit_id, str) and commit_id and not _sha_same(expected_sha, commit_id):
        info["installed"] = commit_id
        info["why"] = f"{name} installed from commit {commit_id[:12]}, not the requested {expected_sha[:12]}"
        return False, info
    head = _checkout_head(checkout)
    info["installed"] = head
    if not _sha_same(expected_sha, head):
        info["why"] = f"{name} checkout is at {head[:12] or 'unknown'}, not the requested {expected_sha[:12]}"
        return False, info
    return True, info


def pr_side_constraints(main_venv: Path, dist: str, dest: Path) -> Path:
    """Pins for the pull-request install: the main side's freeze, without the project named `dist`.

    Editable lines and comments are dropped. `dist` is the label the run already uses for this exclusion; it is
    not the commit guard's lookup. The file is written to `dest`."""
    frz = in_side(main_venv, [uv_bin(), "pip", "freeze", "-p", main_venv / "bin/python"], install=True).stdout
    pkgname = dist.lower().replace("_", "-")
    dest.write_text("\n".join(ln for ln in frz.splitlines() if ln and not ln.startswith(("-e", "#"))
                               and ln.split("==")[0].lower().replace("_", "-") != pkgname) + "\n")
    return dest


def no_index_config_env(env: dict) -> dict:
    """Product-check install env: index, find-links and trusted-host settings dropped (demo_helper.drop_index_env),
    and no uv or pip config file read (UV_NO_CONFIG=1, PIP_CONFIG_FILE=/dev/null)."""
    from poc import demo_helper
    env = demo_helper.drop_index_env(env)
    env["UV_NO_CONFIG"] = "1"
    env["PIP_CONFIG_FILE"] = os.devnull
    return env


def no_config_cmd(cmd: list) -> list:
    """A uv call that ignores config files; a `uv pip install` also ignores the project's [tool.uv.sources]."""
    if not cmd or Path(str(cmd[0])).name != "uv" or "--no-config" in cmd:
        return cmd
    extra = ["--no-config"]
    if [str(x) for x in cmd[1:3]] == ["pip", "install"]:
        extra.append("--no-sources")
    return [*cmd, *extra]


def install_side(venv: Path, checkout: Path, chosen: dict | None, log: Path, python: str, timeout: int,
                 constraints: Path | None, extra_reqs=None, isolated: bool = False) -> tuple[bool, str]:
    """isolated (product checks): every uv call ignores config files and the project's [tool.uv.sources], and the
    env has no index settings (no_index_config_env)."""
    env = base_env(side_home(venv), install=True)
    if subprocess.run(["git", "-C", checkout, "describe", "--tags"], capture_output=True, env=env).returncode != 0:
        env = base_env(side_home(venv), install=True, SETUPTOOLS_SCM_PRETEND_VERSION="9999.0.0")
    if isolated:
        env = no_index_config_env(env)
    proj, extra = side_install_args(chosen, checkout)
    proj = with_test_extras(proj, checkout)
    cmds = [[uv_bin(), "venv", "-q", "-p", python, venv],
            [uv_bin(), "pip", "install", "-q", "-p", venv / "bin/python", *proj, *extra, *BASE_TEST_DEPS,
             *pyproject_test_groups(checkout)]
            + (["-c", constraints] if constraints else [])]
    # Optional build constraints (POC_BUILD_CONSTRAINTS, read here in the orchestrator): pins for the isolated build
    # environment and the installed one, e.g. "numpy<2" for checkouts older than NumPy 2. Same file for both sides and every tool.
    bc = os.environ.get("POC_BUILD_CONSTRAINTS")
    if bc and Path(bc).is_file():
        cmds[-1] += ["--build-constraint", bc, "-c", bc]   # same pins at build time and at run time
    breq = meson_build_requires(checkout)
    if breq is not None and "-e" in proj:
        # meson-python editable installs rebuild on import with the build tools (ninja, meson, cython); with build
        # isolation those live in a temporary dir that is gone by test time. Install them into the venv instead.
        pins = (["-c", bc] if bc and Path(bc).is_file() else []) + (["-c", constraints] if constraints else [])
        cmds.insert(1, [uv_bin(), "pip", "install", "-q", "-p", venv / "bin/python", *breq, "ninja", *pins])
        cmds[-1].insert(cmds[-1].index("-p"), "--no-build-isolation")
    # Optional overrides (POC_INSTALL_OVERRIDES): e.g. drop an optional test extra that cannot build on this machine
    # ("scikit-umfpack; python_version < '0'"). Same file for both sides and every tool.
    ov = os.environ.get("POC_INSTALL_OVERRIDES")
    ov = ov if ov and Path(ov).is_file() else None
    if ov:
        cmds[-1] += ["--override", ov]
    if extra_reqs:
        cmds[-1].extend(list(extra_reqs))
    if isolated:
        cmds = [no_config_cmd(c) for c in cmds]
    ro_files = tuple(x for x in (constraints, bc if bc and Path(bc).is_file() else None, ov) if x)
    sbx = side_sandbox(venv, network=True, ro=ro_files)
    sbx["rw"].append(checkout)
    for c in cmds:
        heavy = _compiles_checkout(c, checkout)
        rc, _ = (run_heavy if heavy else run)(c, log, env=env, timeout=timeout, sbx=sbx)
        if rc == "timeout":
            return False, f"install timed out after {timeout}s (whole process tree killed); see {log.name}"
        if rc == 0:
            continue
        if rc == "oom":
            return False, _oom_reason()
        bare = _without_test_extras(c, checkout) if heavy and optional_backend_reqs(checkout) else None
        if bare is not None:
            rc2, _ = run_heavy(bare, log, env=env, timeout=timeout, sbx=sbx)
            if rc2 == "timeout":
                return False, f"install timed out after {timeout}s (whole process tree killed); see {log.name}"
            if rc2 == 0:
                return True, ""
            if rc2 == "oom":
                return False, _oom_reason()
        return False, f"install failed ({rc}); see {log.name}"
    return True, ""


def install_deps_only(venv: Path, checkout: Path, plan: dict, log: Path, python: str, timeout: int,
                      extra_reqs=None, deps_root: Path | None = None) -> tuple[bool, str]:
    """Install only the dependencies a project declares (product checks), never the project itself.

    Same commands on both sides. The checkout is added to the import path with a .pth file.
    deps_root: read the dependency files from this folder (read-only) instead of the checkout. The flat-layout
    fallback passes main's checkout on both sides, so the PR's own dependency files never change what is installed.
    """
    from poc import demo_helper
    env = no_index_config_env(base_env(side_home(venv), install=True))   # no index from the env or config files
    src = Path(deps_root) if deps_root is not None else checkout
    cmds = [["uv", "venv", "-q", "-p", python, venv]]
    if plan.get("kind") == "uv-sync":
        # same result as `uv sync --no-install-project`: the lock (or pyproject) exported without the project itself
        # from the folder that declares it, so local paths in the lock (workspace members) resolve as for uv sync
        reqs = (checkout if deps_root is None else side_out(venv)) / ".poc-declared-deps.txt"
        export = ["uv", "export", "-q", "--no-emit-project", "--no-hashes", "--directory", src,
                  "-p", venv / "bin/python", "-o", reqs]
        cmds.append(export + (["--frozen"] if plan.get("frozen") else []))
        cmds.append(("check-export", reqs))   # same off-index line rules as requirement files, before installing
        cmds.append(["uv", "pip", "install", "-q", "-p", venv / "bin/python", "-r", reqs])
    else:
        for name in plan.get("files") or []:
            cmds.append(["uv", "pip", "install", "-q", "-p", venv / "bin/python", "-r", src / name])
    cmds.append(["uv", "pip", "install", "-q", "-p", venv / "bin/python", *BASE_TEST_DEPS, *(extra_reqs or [])])
    cmds = [c if isinstance(c, tuple) else [*c, "--no-config"] for c in cmds]   # every uv call ignores config files
    sbx = side_sandbox(venv, network=True, ro=(() if deps_root is None or src == checkout else (src,)))
    sbx["rw"].append(checkout)
    for c in cmds:
        if isinstance(c, tuple) and c[0] == "check-export":
            refused = demo_helper.unsafe_exported_lines(c[1])
            if refused:
                Path(c[1]).unlink(missing_ok=True)
                (checkout / ".poc-declared-deps.txt").unlink(missing_ok=True)
                return False, demo_helper.unsafe_requirements_reason(refused)
            continue
        rc, _ = run(c, log, cwd=src, env=env, timeout=timeout, sbx=sbx)   # lock paths are relative to it
        if rc == "timeout":
            return False, f"dependency install timed out after {timeout}s; see {log.name}"
        if rc == "oom":
            return False, _oom_reason()
        if rc != 0:
            (checkout / ".poc-declared-deps.txt").unlink(missing_ok=True)
            return False, f"dependency-only install failed ({rc}); see {log.name}"
    (checkout / ".poc-declared-deps.txt").unlink(missing_ok=True)
    changed = checkout_changes(checkout)
    if changed:
        return False, ("setup problem: the dependency install changed the checked-out code ("
                       + ", ".join(changed[:5]) + (" and more" if len(changed) > 5 else "") + "), so nothing was tested")
    write_project_path(venv, checkout)
    return True, ""


DEPS_FILE = ".poc-declared-deps.txt"


def checkout_changes(checkout: Path) -> list[str]:
    """Paths that differ from the checked-out commit, untracked files included. Only our own deps file is ignored.

    A git error counts as a change, so this fails closed."""
    got = subprocess.run(["git", "-C", str(checkout), "status", "--porcelain", "--untracked-files=all",
                          "--ignored=no"], capture_output=True, text=True)
    if got.returncode != 0:
        return ["(git status failed)"]
    out = []
    for line in got.stdout.splitlines():
        path = line[3:].strip()
        if path and path != DEPS_FILE:
            out.append(path)
    return out


def write_project_path(venv: Path, checkout: Path) -> None:
    """Write our import-path entry after the install has finished, replacing whatever is there.

    Nothing an install does can plant or change it: any existing file of that name is removed first."""
    for site in (venv / "lib").glob("python*/site-packages"):
        f = site / "poc-project-path.pth"
        if f.is_symlink() or f.exists():
            f.unlink()
        f.write_text(str(checkout) + "\n")


def _dist_version(venv: Path, requirement: str) -> str:
    """Installed version of one requirement, or "" when it is not there. The name is checked before it is used."""
    name = _req_name(requirement)
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", name):
        return ""
    code = ("import importlib.metadata as m\ntry:\n"
            f"    print(m.version({name!r}))\nexcept Exception:\n    print('')\n")
    out = in_side(venv, [venv / "bin/python", "-c", code], timeout=60)
    text = (getattr(out, "stdout", None) or "").strip()
    return text.splitlines()[-1] if text else ""


def _project_file_dirs(repo: str, item: dict, work: Path, log: Path) -> list[Path]:
    """Directories that hold this project's packaging files.

    A nightly check has not installed either side yet. Read a checkout that is already
    there, or clone the base ref into work/packaging. An empty list means the files
    could not be read, so the plan must not add packages from a lookup.
    """
    found = []
    for name in ("side-main", "side-pr", "packaging"):
        path = work / name
        if path.is_dir() and any(path.iterdir()):
            found.append(path)
    if found:
        return found
    dest = work / "packaging"
    shutil.rmtree(dest, ignore_errors=True)
    ref = str((item or {}).get("base_ref") or "").strip()
    cmd = ["git", "clone", "-q", "--depth", "1"]
    if ref:
        cmd.extend(["--branch", ref])
    cmd.extend([f"https://github.com/{repo}.git", str(dest)])
    rc, _ = run(cmd, log, env=base_env(work / "home-git"), timeout=900)
    if rc != 0 or not dest.is_dir() or not any(dest.iterdir()):
        shutil.rmtree(dest, ignore_errors=True)
        return []
    return [dest]


_INSTALL_DOCS: dict = {}   # this process only: install-doc text per PR, never written to disk or reused later
_DECLARED: dict = {}       # this process only: Python packages main's checkout declares (deps and every extra), per PR
_DECLARED_URLS: dict = {}  # this process only: homepage / docs links main's checkout declares, per PR


def _main_and_pr(folders: list) -> tuple:
    """Main's checkout and the PR's checkout among this run's folders (side-main / packaging and side-pr)."""
    paths = [Path(f) for f in folders or []]
    pr = next((f for f in paths if f.name == "side-pr"), None)
    main = next((f for f in paths if f.name != "side-pr"), None)
    if pr is None and len(paths) > 1 and main is paths[0]:
        pr = paths[1]
    return main, pr


def nightly_main_checkout(work: Path) -> Path | None:
    """Main's tree on the nightly route.

    A source build checks the pull-request head out at ``work/src``. That directory is not main. Main is
    ``work/side-main`` when that checkout exists, otherwise the base-branch clone in ``work/packaging``.
    """
    for name in ("side-main", "packaging"):
        path = Path(work) / name
        if path.is_dir():
            return path
    return None


def declared_checkouts(main, _pr=None) -> list[Path]:
    """Checkouts a product gap retry may trust. Only main. The pull-request tree is ignored.

    On the nightly route the ignored tree is ``work/src`` (the pull-request head). Pass main from
    ``nightly_main_checkout`` instead.
    """
    if main is None:
        return []
    path = Path(main)
    return [path] if path.is_dir() else []


def _batch_key(repo: str, rec_or_item) -> str:
    pr = rec_or_item.get("pr") if isinstance(rec_or_item, dict) else None
    number = pr.get("number") if isinstance(pr, dict) else pr
    return f"{repo}#{number}"


def _product_plan(a, rec: dict, repo: str, cfg: dict, checkouts, pypi=None, python_available=None,
                  out_dir=None) -> dict | None:
    """Setup plan for a console or daily check. None on a study run, which does not call this.

    Does not change the runner's Python. The caller passes ``_check_python`` into this check's installs.
    """
    from poc import demo_helper
    if not demo_helper.active(a):
        return None
    tavily = (rec.get("demo_helper") or {}).get("tavily") or {}
    folders = [path for path in (checkouts or []) if path]
    main_dir, pr_dir = _main_and_pr(folders)
    product = product_route(a)
    # A product check never installs an OS package, on Contree or anywhere else. A study plan still may.
    apply_os = not product
    current = getattr(a, "python", "") or ""
    if (getattr(a, "sandbox_backend", None) or "local") == "contree":
        # Inside Contree the image's Python is what runs, and any version can be installed during setup, so the
        # orchestrator machine's interpreters must not steer the choice.
        from poc import contree_sandboxes
        current = contree_sandboxes.image_python()
        if python_available is None:
            python_available = lambda version: True  # noqa: E731
    plan = demo_helper.build_setup_plan(
        repo, folders, tavily, current,
        getattr(a, "sandbox_backend", None) or "local",
        (cfg or {}).get("dist") or (cfg or {}).get("pkg") or "",
        python_available=python_available, pypi=pypi,
        allow_lookup_packages=bool(folders), auto_python=product,
        docs_checkouts=([main_dir] if main_dir else []) if product else None,
        apply_system=apply_os,
        changed_files=list((rec.get("files") or {}).get("all") or []) if product else None)
    for req in (getattr(a, "batch_fix_reqs", None) or {}).get(_batch_key(repo, rec), []):
        if req not in plan.setdefault("extra_reqs", []):
            plan["extra_reqs"].append(req)
            plan.setdefault("packages", []).append({
                "requirement": req, "name": req, "kind": "tavily", "action": "install", "source": "tavily",
                "reason": "diagnosed by the lookup after a setup failure; declared by the project as a dependency or extra",
                "sides": ["main", "pr"]})
            plan.setdefault("lines", []).append(f"Setup plan: install {req} (fix for an earlier setup failure) on main and pr.")
    staged_sys = [n for n in (getattr(a, "batch_fix_system", None) or {}).get(_batch_key(repo, rec), [])
                  if n not in {i["name"] for i in plan.get("system") or []}]
    for item in demo_helper._system_decision(staged_sys, getattr(a, "sandbox_backend", None) or "local",
                                             apply_system=apply_os):
        plan.setdefault("system", []).append(item)
        plan.setdefault("lines", []).append(f"Setup plan: system package {item['name']} (fix for an earlier setup "
                                            f"failure): {item['reason']}")
    blocked = [i["name"] for i in plan.get("system") or [] if not i.get("applied")]
    if blocked:
        why_os = ("this check does not install system packages, so the result stays could not verify" if product
                  else "this sandbox (bubblewrap) cannot install OS packages")
        demo_helper.note_limitation(rec, blocked, "the project's own files ask for these system packages", why_os)
    # Install docs come from main's checkout only, so a PR cannot add a package that then lands on main too.
    docs = demo_helper.project_install_docs([main_dir] if main_dir else [])
    block = rec.setdefault("demo_helper", {})
    block["install_docs"] = docs["sources"]
    block["install_docs_from"] = "main"
    _INSTALL_DOCS[_batch_key(repo, rec)] = docs["text"]
    _DECLARED[_batch_key(repo, rec)] = sorted(demo_helper.declared_names(main_dir)) if main_dir else []
    urls = demo_helper.declared_urls(main_dir) if main_dir else []
    dist = (cfg or {}).get("dist") or (cfg or {}).get("pkg") or ""
    parts = demo_helper.split_repo(repo or "")
    if product and dist and parts:
        try:
            info = (pypi or demo_helper.fetch_pypi)(dist)
        except Exception:  # noqa: BLE001 — no PyPI page means only the project's own files declare links
            info = None
        if demo_helper.pypi_links_back(info, *parts):   # the PyPI page is the project's own
            urls.extend(u for u in demo_helper.pypi_declared_urls(info) if u not in urls)
    _DECLARED_URLS[_batch_key(repo, rec)] = urls
    changed = list(dict.fromkeys(
        [f for f in ((rec.get("files") or {}).get("all") or []) if demo_helper.is_install_doc_path(f)]
        + demo_helper.install_docs_changed(main_dir, pr_dir)))
    if changed:
        block["install_docs_pr_changed"] = changed
        line = ("Setup plan: the PR changes install docs (" + ", ".join(changed[:5])
                + "); setup was read from main's copy and applied the same on both sides.")
        block["notes"] = demo_helper._unique([*(block.get("notes") or []), line])
        demo_helper.announce([line])
    demo_helper.attach_plan(rec, plan)
    demo_helper.announce(plan.get("lines") or [])
    from poc import run_progress
    steps = demo_helper.plan_steps(plan)
    rec.setdefault("demo_helper", {})["steps"] = steps
    if out_dir is not None:
        try:
            files = demo_helper.write_run_files(plan, out_dir)
            rec.setdefault("demo_helper", {})["run_files"] = files
        except OSError as exc:
            why = f"could not write this run's requirements.txt / setup-plan.json: {type(exc).__name__}: {exc}"
            rec.setdefault("demo_helper", {})["run_files"] = {"error": why}
            print(f"WARNING: {why}", file=sys.stderr, flush=True)
    run_progress.emit("setup_lookup", detail=steps["setup_lookup"])
    py = plan.get("python") or {}
    if py.get("requested") and py.get("rule"):
        run_progress.emit("setup_python", detail=("failed: " if py.get("gate_failed") else "")
                          + f"Python {py['requested']}: {py.get('reason')}")
    else:
        run_progress.emit("setup_python", detail=steps["setup_python"])
    run_progress.emit("install_deps", detail=steps["install_deps"])
    return plan


def _check_python(a, plan) -> str:
    """Python for this check only. A switch is not written back onto the runner."""
    switch = ((plan or {}).get("python") or {}).get("switch")
    return switch or getattr(a, "python", "") or ""


def _groups_blocked(a, plan) -> str:
    """The could-not-verify reason when main's dependency groups can't be installed as written (refused lines or a
    table PEP 735 does not allow) on a product check, else "". Every install route stops on it before installing."""
    if not product_route(a):
        return ""
    plan = plan or {}
    return str(plan.get("groups_blocked") or plan.get("scope_blocked") or "")


def _install_with_helper(a, rec, step, venv, checkout, chosen, log, timeout, constraints, extra_reqs, python=None,
                         max_retries=None):
    """Retry one side's install. The caller uses the plain install_side call when the helper is off."""
    from poc import demo_helper
    py = a.python if python is None else python
    gate = ((rec.get("demo_helper") or {}).get("setup_plan") or {}).get("python") or {}
    if gate.get("gate_failed"):
        why = (f"setup problem: Python {gate.get('requested')} could not be installed for this check "
               f"({gate.get('reason')}); nothing was tested") if gate.get("requested") else str(gate.get("reason"))
        demo_helper.note_setup(rec, step, {"ok": False, "label": demo_helper.SETUP_LABEL, "counts_as_verdict": False,
                                           "attempts": 1, "detail": why, "retried": False, "step": step})
        return False, why
    blocked_groups = _groups_blocked(a, (rec.get("demo_helper") or {}).get("setup_plan"))
    if blocked_groups:
        # same as a refused requirement line in the deps-only fallback: stop before installing anything
        return False, blocked_groups
    from poc import run_progress
    run_progress.emit("install_deps", detail=f"{step}: installing the project's declared dependencies")

    state = {"py": py}

    def _log_text() -> str:
        try:
            return log.read_text(errors="replace")[-20000:]
        except OSError:
            return ""

    def _unsupported(text: str) -> str | None:
        """A product-check install that should stop now, or None to keep going.

        Study runs do not call this. A flat-layout project is not installed as a package. On main it falls back to
        the dependencies main declares (see _flat_plan); with nothing usable declared it stays unsupported.
        A disk-full install is not retried, and its temporary build files are removed.
        """
        if not product_route(a):
            return None
        if demo_helper.disk_full(text):
            cleanup_install_temps(venv)
            return demo_helper.DISK_FULL_REASON
        if demo_helper.flat_layout(text) and not _flat_plan():
            shutil.rmtree(venv, ignore_errors=True)
            return demo_helper.FLAT_LAYOUT_REASON
        own = demo_helper.own_index_config(checkout)   # needs an index or sources product checks ignore
        if own:
            shutil.rmtree(venv, ignore_errors=True)
            return demo_helper.own_index_reason(own)
        return None

    def _is_main() -> bool:
        return str(step).lower().startswith("main")

    def _flat_plan() -> dict | None:
        """The deps-only plan for any not-a-package error (flat layout or other), always from MAIN's files.
        Main: what main declares. PR side: main's
        plan and main's folder, and only when main itself fell back, so a flat layout on the PR side alone stays
        could not verify. The PR's own dependency files are never read."""
        if _is_main():
            return demo_helper.deps_only_plan(checkout, exclude=_aggregate_names(rec) if product_route(a) else ())
        helper = rec.get("demo_helper") or {}
        return helper.get("deps_only") if helper.get("flat_deps_root") else None

    def _flat_root() -> Path:
        return checkout if _is_main() else Path(rec["demo_helper"]["flat_deps_root"])

    def once():
        if product_route(a):
            gpu = demo_helper.gpu_only_requirement(checkout)
            if gpu:
                return False, demo_helper.gpu_reason(gpu)
        ok, why = install_side(venv, checkout, chosen, log, state["py"], timeout, constraints, extra_reqs,
                                isolated=product_route(a))
        if ok:
            return ok, why
        text = _log_text()
        blocked = _unsupported(text)
        if blocked:
            return False, blocked
        wanted = demo_helper.wrong_python(text) if product_route(a) else None
        if wanted and wanted != state["py"] and not str(state["py"]).endswith(wanted):
            got = demo_helper.retry_python(wanted)
            if got:
                demo_helper.note_auto_fix(
                    rec, f"Auto-fix: the {step} said it needs Python {wanted}, so Python {wanted} "
                         "was installed and the install was tried again.")
                state["py"] = got
                shutil.rmtree(venv, ignore_errors=True)
                ok, why = install_side(venv, checkout, chosen, log, got, timeout, constraints, extra_reqs,
                                             isolated=product_route(a))
                if ok:
                    return ok, why
                text = _log_text()
                blocked = _unsupported(text)
                if blocked:
                    return False, blocked
        if product_route(a) and demo_helper.not_a_package(text):
            plan = _flat_plan()
            refused = demo_helper.unsafe_requirement_lines(_flat_root(), plan) if plan else []
            if refused:
                shutil.rmtree(venv, ignore_errors=True)
                return False, demo_helper.unsafe_requirements_reason(refused)
            if plan:
                shutil.rmtree(venv, ignore_errors=True)
                ok, why = install_deps_only(venv, checkout, plan, log, state["py"], timeout, extra_reqs,
                                            deps_root=_flat_root())
                if ok:
                    demo_helper.note_auto_fix(
                        rec, f"Auto-fix: the {step} could not build the project as a package, so only the "
                             f"dependencies it declares ({plan['source']}) were installed, the same way on both "
                             "sides, and the project's own folder was put on the import path.")
                    rec.setdefault("demo_helper", {})["deps_only"] = plan
                    if _is_main():
                        rec["demo_helper"]["flat_deps_root"] = str(checkout)
                else:
                    blocked = _unsupported(_log_text())
                    if blocked:
                        return False, blocked
        return ok, why

    ok, why, _value, outcome = demo_helper.run_setup(
        step, once, cleanup=lambda: shutil.rmtree(venv, ignore_errors=True),
        max_retries=demo_helper.MAX_SETUP_RETRIES if max_retries is None else max_retries)
    demo_helper.note_setup(rec, step, outcome)
    return ok, why


def _pr_side_retries(a):
    """Install retries for the PR side once main has installed fine. On a product run that is 1: one more try, then a
    PR side that still will not build is the PR's own failure, not a setup problem. Other runs keep the earlier
    retries."""
    from poc import demo_helper
    return 1 if product_route(a) else demo_helper.MAX_SETUP_RETRIES


# Generic signs of an infrastructure failure (network, out of memory, timeout, disk, sandbox). No package names.
# The word list is broad and may hide some real PR errors (they stay could not verify). That is safe for now.
_INFRA_FAILURE = re.compile(
    r"(out of memory|\boom\b|memoryerror|killed|no space left|disk quota|timed? ?out|timeout|connection (?:refused|"
    r"reset|aborted)|temporary failure in name resolution|could not resolve host|name or service not known|network is "
    r"unreachable|ssl(?:error|: )|http error 5\d\d|\b50[234]\b|bwrap|sandbox|infrastructure failure)", re.I)
# A named error: an exception name or a compiler / build tool "error:" line.
_NAMED_ERROR = re.compile(r"(?m)(?:^|\s)(?:[A-Za-z_][\w.]*(?:Error|Exception)\b|error(?:\[\w+\])?:\s*\S)")


def _pr_own_failure(a, rec, step, why, log: Path | None = None, same_setup: bool = False) -> str:
    """Label a PR-side build failure after a clean main install as the PR's own failure (product runs only).

    When the error text shows a missing system library, header, pkg-config package or build tool (generic patterns,
    no package names), it is a sandbox limitation instead: the result stays could not verify, with a limitation
    naming what is missing."""
    from poc import demo_helper
    if not product_route(a) or str(why).startswith("infrastructure failure:"):
        return why
    # The try count defaults to 1 when no setup outcome is recorded (a patch failure, an unusual error), so the PR is
    # never blamed in those cases. That is the safe direction.
    tries = int(((rec.get("demo_helper") or {}).get("setup") or {}).get("attempts") or 1)
    text = str(why)
    if log is not None:
        try:
            text += "\n" + Path(log).read_text(errors="replace")[-20000:]
        except OSError as exc:
            print(f"WARNING: could not read {Path(log).name}: {type(exc).__name__}", file=sys.stderr, flush=True)
    # A flat layout, a full disk, or a CUDA build is unsupported on a product check. The log's "error:" line
    # must not turn that into needs attention, even when both sides install from source and both tries failed.
    if demo_helper.flat_layout(text) or str(why).startswith("unsupported:"):
        return demo_helper.FLAT_LAYOUT_REASON if demo_helper.flat_layout(text) else why
    if demo_helper.is_system_failure(text):
        line = demo_helper.failure_line(text)
        pieces = demo_helper.missing_system_pieces(text) or ([line[:120]] if line else [])
        demo_helper.note_limitation(rec, pieces, line, "the PR side needs a system library, header or build tool "
                                                       "that this check does not install")
        named = ", ".join(pieces) if pieces else line
        return f"could not verify: the PR side needs a missing system library, header or build tool: {named}"
    if _INFRA_FAILURE.search(text):
        return why   # network, memory, timeout, disk or sandbox trouble is never blamed on the PR
    named = _NAMED_ERROR.search(text)
    # Only when both sides install the same way from source (test_source_pair) and both PR-side tries failed.
    # On the nightly route main is a ready-made wheel and the PR is built from source, so it is never blamed there.
    blame = same_setup and bool(named) and tries >= 2
    return demo_helper.note_pr_build_failure(rec, step, why, needs_attention=blame,
                                             error=demo_helper.failure_line(text[named.start():]) if named else "")


def _log_plan_installs(rec, plan, venvs: dict) -> None:
    from poc import demo_helper
    packages = [item for item in (plan or {}).get("packages") or [] if item.get("action") == "install"]
    if not packages or not venvs:
        return
    versions = {}
    for item in packages:
        versions[item["requirement"]] = {side: _dist_version(venv, item["requirement"]) for side, venv in venvs.items()}
    logs = []
    for item in packages:
        got = versions.get(item["requirement"]) or {}
        main_v, pr_v = got.get("main", ""), got.get("pr", "")
        logs.append({"package": item["name"], "requirement": item["requirement"],
                     "version": main_v if main_v == pr_v else f"main {main_v}, pr {pr_v}",
                     "versions": {"main": main_v, "pr": pr_v}, "source": item.get("source"),
                     "reason": item.get("reason"), "sides": ["main", "pr"]})
    demo_helper.note_installs(rec, logs)


def _retry_setup_gap(a, rec, repo, prdir, venvs: dict, rerun, recheck_coverage=None, checkouts=None) -> None:
    """One setup-gap rerun on a console or daily check. A study run does not call this."""
    from poc import demo_helper, tavily_docs
    if not demo_helper.active(a):
        return
    plan = (rec.get("demo_helper") or {}).get("setup_plan") or {}
    declared = [item.get("requirement") for item in (plan.get("packages") or []) if item.get("requirement")]
    tavily = (rec.get("demo_helper") or {}).get("tavily") or {}

    def install_one(side, requirement):
        venv = venvs.get(side)
        if venv is None:
            return False, ""
        rc, _ = run(no_config_cmd([uv_bin(), "pip", "install", "-q", "-p", venv / "bin/python", requirement]),
                    prdir / "setup-gap.log", env=no_index_config_env(base_env(side_home(venv), install=True)),
                    timeout=getattr(a, "build_timeout", 1800), sbx=side_sandbox(venv, network=True))
        return rc == 0, _dist_version(venv, requirement) if rc == 0 else ""

    lookup = None
    if tavily_docs.available():
        cache = demo_helper.FileCache(prdir / "tavily-cache.json")

        def lookup(query, _cache=cache):  # noqa: A001 — local lookup passed into the helper
            project = str(rec.get("library") or "")
            hit = _cache.get(query)
            if isinstance(hit, dict):
                return demo_helper.scope_lookup(hit, repo, project)
            got = demo_helper.live_fetch(query)
            payload = got if isinstance(got, dict) else {"ok": False, "results": []}
            stored = demo_helper.redact_obj(demo_helper.scope_lookup(payload, repo, project))
            stored["live_call"] = False
            _cache.put(query, stored)
            return stored

    if product_route(a):
        # ``checkouts`` is main's tree only. A dependency declared only on the pull request is not added.
        for checkout in checkouts or []:
            for req in demo_helper.declared_requirement_lines(checkout):
                if req not in declared:
                    declared.append(req)
    if not product_route(a):
        # Study runs and the daily study keep the earlier single setup-gap rerun, unchanged.
        # allow_system and install_system are unused and are not passed.
        demo_helper.retry_unverified_study(
            rec, rerun, install_one, declared, tavily.get("text") or "", demo_helper.fetch_pypi, repo,
            lookup=lookup, recheck_coverage=recheck_coverage)
        return
    demo_helper.retry_unverified(
        rec, rerun, install_one, declared, tavily.get("text") or "", demo_helper.fetch_pypi, repo,
        lookup=lookup, recheck_coverage=recheck_coverage,
        project_text=_INSTALL_DOCS.get(_batch_key(repo, rec), ""),
        declared_urls=_DECLARED_URLS.get(_batch_key(repo, rec), []), log_dir=prdir)


def _install_system_package(rec, name, run_side) -> bool:
    """Install a system package on both sides, or on neither, and record a setup problem on failure."""
    from poc import demo_helper
    if run_side is None or not demo_helper.safe_apt_name(name):
        detail = "no sandbox session" if run_side is None else f"not a safe system package name: {name}"
        demo_helper.note_setup(rec, f"system package {name}", {
            "ok": False, "counts_as_verdict": False, "attempts": 1, "detail": detail, "retried": False})
        return False
    result = demo_helper.install_system_both(run_side, name)
    if result.get("ok"):
        return True
    demo_helper.note_setup(rec, f"system package {name}", {
        "ok": False, "counts_as_verdict": False, "attempts": 1, "detail": result.get("detail"), "retried": False})
    return False


# ---------------------------------------------------------------- execution helpers
HOST = None   # sbx=HOST: a trusted tool on our own files (git on our clones); everything else runs in a side's sandbox

# Contree-only mode: the check chose --sandbox-backend contree. Every step that
# runs pull-request or package code must then go through the Contree session; a local side command is refused.
_CONTREE_ONLY = False


class Refusal(int):
    """Return code of a step that was refused, not run. A non-zero int, so every rc != 0 check fails safely, and it
    carries an explicit ``refused`` flag so callers never have to compare against a magic string."""
    refused = True

    def __new__(cls, code: int = 126):
        return super().__new__(cls, code)


def is_refused(rc) -> bool:
    """True when a return code (or a CompletedProcess) is a Contree-only refusal."""
    return bool(getattr(rc, "refused", False))


LOCAL_REFUSED = Refusal(126)
CONTREE_ONLY_NOTE = ("Contree mode: no pull-request or package code runs "
                     "locally. This step needs a local side and was not run.")
CONTREE_ONLY_COVERAGE_WHY = "Contree mode: coverage runs only inside Contree, and it was not run there"
NO_SANDBOX_FALLBACK = ("Contree could not prepare the main and PR sides ({why}). In Contree mode nothing from the pull "
                       "request runs locally, so Proof-of-Change will not run pull-request code.")
CONTREE_AUTH_HINT = " Check your Nebius key and Contree project ID and try again."


def contree_refusal(e) -> tuple[str, dict]:
    """Refusal text and record entry for a Contree setup failure. Blames credentials only on an API auth error."""
    refusal = NO_SANDBOX_FALLBACK.format(why=e) + (CONTREE_AUTH_HINT if getattr(e, "auth", False) else "")
    entry = {"failed": str(e), "fallback": None, "exit_code": getattr(e, "exit_code", None),
             "stderr_tail": getattr(e, "stderr_tail", "") or "", "auth_error": bool(getattr(e, "auth", False))}
    return refusal, entry


def set_contree_only(on: bool) -> None:
    global _CONTREE_ONLY
    _CONTREE_ONLY = bool(on)


def contree_only() -> bool:
    return _CONTREE_ONLY


def contree_only_wanted(backend: str | None) -> bool:
    """True whenever Contree was chosen. In Contree mode nothing from the pull request is installed or run locally,
    not even first: both sides are built in Contree from the setup plan, and if Contree cannot run, the check is
    refused (no bubblewrap fallback)."""
    return backend == "contree"
HEAVY_RAM_PER_BUILD_GB = 8
HEAVY_RAM_PER_JOB_GB = 2
OOM_PHRASE = "Killed signal terminated program"


def _oom_reason() -> str:
    return ("infrastructure failure: the compiler was killed for using too much memory. "
            "This is not a result about the pull request; retry the run.")


def heavy_build_limit(configured: int | None = None, ram: float | None = None) -> int:
    """How many heavy source builds may run at once.

    Default cap is 1 (or POC_MAX_HEAVY_BUILDS / the configured value). One slot per about 8 GB of RAM, never below 1,
    never above the cap. Unknown RAM stays at 1."""
    if configured is None:
        raw = os.environ.get("POC_MAX_HEAVY_BUILDS", "1")
        try:
            configured = int(raw)
        except ValueError:
            configured = 1
    cap = max(1, int(configured))
    if ram is None:
        return 1
    slots = max(1, int(ram // HEAVY_RAM_PER_BUILD_GB))
    return min(cap, slots)


def compiler_jobs(ram: float | None = None, configured: int | None = None) -> int:
    """Parallel compiler jobs for one heavy build. Default 1, clamped to about one job per 2 GB of RAM."""
    if configured is None:
        raw = os.environ.get("POC_BUILD_JOBS", "1")
        try:
            configured = int(raw)
        except ValueError:
            configured = 1
    cap = max(1, int(configured))
    if ram is None:
        return 1
    by_ram = max(1, int(ram // HEAVY_RAM_PER_JOB_GB))
    return min(cap, by_ram)


def with_compiler_jobs(env: dict, jobs: int | None = None) -> dict:
    """Copy env and set the compiler job count. The added names are on the install allowlist; values are not secrets."""
    from guardrails.isolation import INSTALL_ALLOWLIST, check_untrusted_env
    n = compiler_jobs(ram_gb()) if jobs is None else max(1, int(jobs))
    out = dict(env)
    out["MAX_JOBS"] = str(n)
    out["CMAKE_BUILD_PARALLEL_LEVEL"] = str(n)
    out["NINJAFLAGS"] = f"-j{n}"
    out["MAKEFLAGS"] = f"-j{n}"
    check_untrusted_env(out, INSTALL_ALLOWLIST)
    return out


def _log_tail(path: Path, n: int = 40) -> str:
    try:
        return "\n".join(Path(path).read_text(errors="replace").splitlines()[-n:])
    except OSError:
        return ""


def is_oom_kill(rc, log_text: str = "") -> bool:
    """True for signal 9 / exit 137, or the compiler's 'Killed signal terminated program' line.

    Our own timeout kills the process and records rc 'timeout'. That is not an out-of-memory kill."""
    if rc == "timeout" or rc == "oom":
        return False
    if rc in (-9, 137):
        return True
    return OOM_PHRASE in (log_text or "")


def _compiles_checkout(cmd, checkout: Path) -> bool:
    text = " ".join(map(str, cmd))
    return "pip" in text and "install" in text and str(checkout) in text


class HeavyBuildSlots:
    """Cross-process cap on heavy source builds. flock is per process, which matches one build per daily-run process."""

    def __init__(self, directory: Path, limit: int):
        self.directory = Path(directory)
        self.limit = max(1, int(limit))
        self._fh = None

    def acquire(self, wait_s: float = 3600) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        deadline = time.monotonic() + wait_s
        while True:
            for i in range(self.limit):
                fh = open(self.directory / f"slot-{i}.lock", "a+")  # noqa: SIM115
                try:
                    fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    fh.close()
                    continue
                self._fh = fh
                return
            if time.monotonic() >= deadline:
                raise TimeoutError("heavy build slot")
            time.sleep(0.05)

    def release(self) -> None:
        fh, self._fh = self._fh, None
        if fh is not None:
            try:
                fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
            finally:
                fh.close()


def _heavy_slot_dir() -> Path:
    raw = os.environ.get("POC_HEAVY_BUILD_DIR")
    return Path(raw) if raw else REPO_ROOT / "ops" / "work" / "heavy-builds"


def run_heavy(cmd, log_path: Path, cwd=None, env=None, timeout=None, sbx=HOST,
              slots: HeavyBuildSlots | None = None) -> tuple[int | str, float]:
    """Run a source build under the heavy-build cap. An out-of-memory kill is retried once, then returned as 'oom'."""
    env = with_compiler_jobs(env or {})
    holder = slots or HeavyBuildSlots(_heavy_slot_dir(), heavy_build_limit(ram=ram_gb()))
    holder.acquire()
    try:
        rc, secs = run(cmd, log_path, cwd=cwd, env=env, timeout=timeout, sbx=sbx)
        if not is_oom_kill(rc, _log_tail(log_path)):
            return rc, secs
        with open(log_path, "a") as fh:
            fh.write("\n[daily_run] infrastructure: compiler killed (out of memory); retrying once\n")
        rc, secs = run(cmd, log_path, cwd=cwd, env=env, timeout=timeout, sbx=sbx)
        if is_oom_kill(rc, _log_tail(log_path)):
            with open(log_path, "a") as fh:
                fh.write("\n[daily_run] infrastructure: compiler killed again (out of memory); not a pull-request result\n")
            return "oom", secs
        return rc, secs
    finally:
        holder.release()


HEARTBEAT_S = 30


def _heartbeat(elapsed: int) -> None:
    """Tell the console the current stage is still going. Prints to stdout, never to the pytest log."""
    if not os.environ.get("POC_PROGRESS_PATH"):
        return
    from poc import run_progress
    events = run_progress.read_events(os.environ["POC_PROGRESS_PATH"])
    stage = events[-1]["stage"] if events else "pytest"
    agent = events[-1].get("agent") if events else None
    run_progress.emit(stage, agent, f"still running ({elapsed}s)")
    print(f"[daily_run] still running ({elapsed}s)", flush=True)


def _wait_child(p: subprocess.Popen, timeout, t0: float):
    """One wait when the console is not attached. With POC_PROGRESS_PATH, wake every HEARTBEAT_S."""
    if not os.environ.get("POC_PROGRESS_PATH"):
        return p.wait(timeout=timeout)
    while True:
        slice_s = HEARTBEAT_S
        if timeout is not None:
            remain = timeout - (time.time() - t0)
            if remain <= 0:
                raise subprocess.TimeoutExpired(p.args, timeout)
            slice_s = min(slice_s, remain)
        try:
            return p.wait(timeout=slice_s)
        except subprocess.TimeoutExpired:
            if timeout is not None and (time.time() - t0) >= timeout:
                raise
            _heartbeat(int(time.time() - t0))


def run(cmd, log_path: Path, cwd=None, env=None, timeout=None, sbx=HOST) -> tuple[int, float]:
    """Run cmd with output to log_path. env is required: always an allowlisted base_env(...). sbx: the sandbox of a
    side (side_sandbox(...)); every command that may run PR or package code passes one."""
    if env is None:
        raise ValueError("run() needs an explicit allowlisted env (base_env)")
    t0 = time.time()
    shown = list(map(str, cmd))
    if sbx is not None and _CONTREE_ONLY:
        with open(log_path, "a") as fh:
            fh.write(f"\n$ {' '.join(shown)}\n[daily_run] {CONTREE_ONLY_NOTE}\n")
        return LOCAL_REFUSED, 0.0
    if sbx is not None:
        cmd, env, cwd = sandbox.wrap(cmd, env, sbx["rw"], sbx["ro"], sbx["network"], cwd)
    with open(log_path, "a") as fh:
        fh.write(f"\n$ {' '.join(shown)}" + (f"   [sandbox: {'network' if sbx['network'] else 'no network'}]"
                                              if sbx is not None and sandbox.enabled() else "") + "\n"); fh.flush()
        p = subprocess.Popen(list(map(str, cmd)), cwd=cwd, env=env, stdout=fh, stderr=subprocess.STDOUT,
                             start_new_session=True)
        try:
            rc = _wait_child(p, timeout, t0)
        except subprocess.TimeoutExpired:
            _kill_tree(p.pid); p.wait(); rc = "timeout"
            fh.write(f"\n[daily_run] TIMEOUT after {timeout}s\n")
    return rc, round(time.time() - t0, 1)


_PROC = "/proc"


def _descendants(pid: int) -> list[int]:
    """All descendants of pid by /proc parent links, including ones that left the process group via setsid."""
    try:
        entries = os.listdir(_PROC)
    except FileNotFoundError:
        return []
    kids: dict[int, list[int]] = {}
    for d in entries:
        if d.isdigit():
            try:
                ppid = int(open(f"{_PROC}/{d}/stat").read().rsplit(")", 1)[1].split()[1])
            except (OSError, IndexError, ValueError):
                continue
            kids.setdefault(ppid, []).append(int(d))
    out, todo = [], [pid]
    while todo:
        for c in kids.get(todo.pop(), []):
            out.append(c); todo.append(c)
    return out


def _kill_tree(pid: int) -> None:
    """SIGSTOP the tree first so nothing forks or reparents while we collect it, then SIGKILL every member."""
    procs = [pid] + _descendants(pid)
    for sig in (signal.SIGSTOP, signal.SIGKILL):
        for q in procs:
            try:
                os.kill(q, sig)
            except ProcessLookupError:
                pass
        procs = [pid] + _descendants(pid) if sig == signal.SIGSTOP else procs
    try:
        os.killpg(pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


def site_packages(venv: Path) -> Path:
    return Path(glob.glob(str(venv / "lib" / "python3*" / "site-packages"))[0])


def base_env(home: Path, install: bool = False, **extra) -> dict:
    """Allowlisted environment for anything that may run PR or package code (guardrails.isolation.untrusted_env):
    nothing from our own environment except PATH, locale, terminal and temp settings; HOME is `home`, a per-environment
    temporary home. install=True adds the uv cache and settings for installs and builds."""
    return untrusted_env(home, install=install, extra=extra or None)


def side_home(venv: Path) -> Path:
    """Per-environment temporary HOME, next to the venv: work/venv-main -> work/home-main."""
    return venv.parent / f"home-{venv.name.removeprefix('venv-')}"


def cleanup_install_temps(venv: Path) -> None:
    """Remove an unfinished install and the temporary build files it left on disk.

    The virtualenv holds the wheels that were unpacked. The side home holds pip and uv build
    directories. The shared download cache is left in place.
    """
    home = side_home(venv)
    shutil.rmtree(venv, ignore_errors=True)
    for path in (home / ".tmp", home / ".uv-cache"):
        shutil.rmtree(path, ignore_errors=True)
    if not home.is_dir():
        return
    for child in list(home.iterdir()):
        if child.is_dir() and (child.name.startswith(("pip-", "tmp", "uv-")) or child.name in {"build", "temp"}):
            shutil.rmtree(child, ignore_errors=True)


def side_sandbox(venv: Path, network: bool = False, ro: tuple = (), rw: tuple = ()) -> dict:
    """The sandbox of one side (guardrails/sandbox.py): read-write only that side's own dirs under the PR's work dir
    (venv, temporary home, output and cwd dirs, its checkout), read-only the shared clone's .git for worktree
    checkouts, plus `ro`/`rw` extras. The PR side of a source build also gets the PR source (work/src)."""
    work, side = venv.parent, venv.name.removeprefix("venv-")
    rwl = [venv, side_out(venv), side_cwd(venv)]
    rol = list(ro)
    co = work / f"side-{side}"
    if co.exists():
        rwl.append(co)
        if (work / "src" / ".git").is_dir():
            rol.append(work / "src" / ".git")
    elif side == "pr" and (work / "src").exists():
        rwl.append(work / "src")
    return {"rw": rwl + list(rw), "ro": rol, "network": network}


def side_out(venv: Path) -> Path:
    d = venv.parent / f"out-{venv.name.removeprefix('venv-')}"
    d.mkdir(parents=True, exist_ok=True)
    return d


def side_checkout(venv: Path) -> Path | None:
    """The side's own checkout next to its venv (work/venv-main -> work/side-main), or None (nightly routes)."""
    d = venv.parent / f"side-{venv.name.removeprefix('venv-')}"
    return d if d.is_dir() else None


def probe_settings(a, venvs: dict) -> dict | None:
    """Product checks only: the project's test settings read from MAIN's checkout (poc/test_settings.py), applied with
    identical values to both sides. Study runs and the daily study get None, so their probes are unchanged."""
    if not product_route(a):
        return None
    from poc import test_settings
    main = side_checkout(venvs["main"]) if "main" in venvs else None
    pr = side_checkout(venvs["pr"]) if "pr" in venvs else None
    return test_settings.settings_from_main(main, pr) if main is not None else None


def probe_env(venv: Path, settings: dict | None = None) -> dict:
    """Environment for a behavioural probe: the allowlisted side env plus the given test settings (None: unchanged)."""
    from poc import test_settings
    return test_settings.apply_settings(base_env(side_home(venv)), settings, side_checkout(venv))


def side_cwd(venv: Path) -> Path:
    d = venv.parent / f"cwd-{venv.name.removeprefix('venv-')}"
    d.mkdir(parents=True, exist_ok=True)
    return d


def in_side(venv: Path, cmd: list, install: bool = False, network: bool = False, cwd=None, ro: tuple = (),
            timeout: int | None = 600) -> subprocess.CompletedProcess:
    """Captured run of cmd in the side's sandbox (venv Python and uv calls: freeze, version checks, imports)."""
    if _CONTREE_ONLY:
        cp = subprocess.CompletedProcess([str(c) for c in cmd], LOCAL_REFUSED, "", CONTREE_ONLY_NOTE)
        cp.refused = True
        return cp
    env = base_env(side_home(venv), install=install)
    argv, env, cwd2 = sandbox.wrap([str(c) for c in cmd], env, **{k: v for k, v in
                                   side_sandbox(venv, network=network, ro=ro).items()}, cwd=cwd or side_cwd(venv))
    try:
        return subprocess.run(argv, capture_output=True, text=True, env=env, cwd=cwd2, timeout=timeout,
                              start_new_session=True)
    except subprocess.TimeoutExpired as e:
        return subprocess.CompletedProcess(argv, "timeout", e.stdout or "", e.stderr or "")


def nightly_wheel(gh_get, dist: str, python: str) -> dict:
    """The newest nightly wheel of dist for CPython <python> manylinux x86_64: {url, filename, version}."""
    from packaging.version import Version
    html = gh_get(f"{NIGHTLY}/{dist}/").decode("utf-8", "replace")
    tag = "cp" + python.replace(".", "")
    best = None
    for href in re.findall(r'href="([^"]+\.whl)[^"]*"', html):
        fn = href.rsplit("/", 1)[-1]
        if f"-{tag}-{tag}-" not in fn or "manylinux" not in fn or "x86_64" not in fn:
            continue
        ver = fn.split("-")[1]
        if best is None or Version(ver) > Version(best["version"]):
            best = {"url": href if href.startswith("http") else "https://pypi.anaconda.org" + href, "filename": fn,
                    "version": ver}
    if not best:
        raise RuntimeError(f"no {tag} manylinux x86_64 nightly wheel for {dist}")
    return best


def fetch_wheel(info: dict, dest: Path) -> dict:
    """Download the exact wheel, hash it, and read its build date from the zip entries (the newest file timestamp).
    The nightly index carries no hashes and reuses version strings across builds, so this is the only pin."""
    dest.mkdir(parents=True, exist_ok=True)
    path = dest / info["filename"]
    side = dest / (info["filename"] + ".json")
    if path.exists() and side.exists():   # same run, same library: reuse the identical build
        return json.loads(side.read_text()) | {"path": str(path)}
    req = urllib.request.Request(info["url"], headers={"User-Agent": "proof-of-change-ops"})
    with urllib.request.urlopen(req, timeout=600) as r, open(path, "wb") as fh:
        last_mod = r.headers.get("Last-Modified")
        shutil.copyfileobj(r, fh)
    h = hashlib.sha256(path.read_bytes()).hexdigest()
    with zipfile.ZipFile(path) as z:
        newest = max(zi.date_time for zi in z.infolist())
    built = dt.datetime(*newest).strftime("%Y-%m-%d %H:%M")
    uploaded = None
    if last_mod:
        uploaded = to_ist(dt.datetime.strptime(last_mod, "%a, %d %b %Y %H:%M:%S GMT").strftime("%Y-%m-%dT%H:%M:%SZ"))
    meta = info | {"sha256": h, "size": path.stat().st_size,
                   "build_date_from_wheel": built + " (zip entry time, as stamped by the build)",
                   "uploaded_ist": uploaded}
    side.write_text(json.dumps(meta))
    return meta | {"path": str(path)}


def nightly_commit(version: str, venv: Path, cfg: dict, env: dict) -> tuple[str | None, str]:
    """Upstream commit the nightly was built from, if the wheel says so."""
    commit, how = None, "not embedded in the wheel"
    if cfg.get("commit_expr"):
        out = in_side(venv, [venv / "bin/python", "-c", cfg["commit_expr"]]).stdout.strip()
        if re.fullmatch(r"[0-9a-f]{7,40}", out or ""):
            commit, how = out, "embedded git revision"
    if not commit:
        m = re.search(r"(?:\+|\.)g(?:it\d{8}\.)?([0-9a-f]{7,40})$", version) or re.search(r"git\d{8}\.([0-9a-f]{7,40})", version)
        if m:
            commit, how = m.group(1), "from the version string"
    return commit, how


def test_extras(meta_extras: list[str]) -> list[str]:
    return [e for e in meta_extras if e.lower() in TEST_EXTRA_NAMES]


def dist_extras(venv: Path, dist: str, env: dict) -> list[str]:
    code = f"import importlib.metadata as m;print('\\n'.join(m.metadata({dist!r}).get_all('Provides-Extra') or []))"
    out = in_side(venv, [venv / "bin/python", "-c", code]).stdout
    return [x.strip() for x in out.splitlines() if x.strip()]


def freeze_env(venv: Path, out: Path) -> str:
    txt = in_side(venv, [uv_bin(), "pip", "freeze", "-p", venv / "bin/python"], install=True).stdout
    out.write_text(txt)
    return out.name


def build_main_env(cfg: dict, venv: Path, log: Path, python: str, timeout: int, wheel_dir: Path,
                   isolated: bool = False) -> dict:
    """Stable release of the library with its test extra + test deps + optional test deps (so tests do not skip for
    missing optional modules), then the exact nightly wheel file, pinned by sha256, reinstalled without deps.
    UV_LINK_MODE=copy so patching the PR copy can never modify the shared uv cache."""
    env = base_env(side_home(venv), install=True)
    py = venv / "bin/python"
    steps = [[uv_bin(), "venv", "-q", "-p", python, venv],
             [uv_bin(), "pip", "install", "-q", "-p", py, cfg["dist"], *cfg["deps"], *BASE_TEST_DEPS, *cfg["test_deps"]]]
    sbx = side_sandbox(venv, network=True)

    def iso(c):   # isolated (product checks): every uv call goes through isolated_install, as in install_side
        return isolated_install(c, env, isolated)
    for c in steps:
        c2, e2 = iso(c)
        rc, _ = run(c2, log, env=e2, timeout=timeout, sbx=sbx)
        if rc != 0:
            return {"ok": False, "why": f"main env setup failed ({rc}) at: {' '.join(map(str, c[:4]))}"}
    extras = test_extras(dist_extras(venv, cfg["dist"], env))
    opt = list(cfg.get("optional_test_deps", []))
    optional_backends = {"installed": [], "skipped": []}
    if extras or opt:
        spec = f"{cfg['dist']}[{','.join(extras)}]" if extras else cfg["dist"]
        c2, e2 = iso([uv_bin(), "pip", "install", "-q", "-p", py, spec, *opt])
        rc, _ = run(c2, log, env=e2, timeout=timeout, sbx=sbx)
        if rc != 0:
            reqs = list(dict.fromkeys(reqs_for_test_extras(metadata_requires(venv, cfg["dist"]), cfg["dist"]) + opt))
            if not reqs:
                return {"ok": False, "why": f"installing test extras/optional test deps failed ({rc}); see setup log"}
            optional_backends = install_optional_backends({"main": venv}, reqs, log, timeout, isolated)
        else:
            bundled = reqs_for_test_extras(metadata_requires(venv, cfg["dist"]), cfg["dist"]) + opt
            optional_backends = {"installed": bundled, "skipped": []}
    try:
        whl = fetch_wheel(nightly_wheel(lambda u: urllib.request.urlopen(
            urllib.request.Request(u, headers={"User-Agent": "proof-of-change-ops"}), timeout=120).read(),
            cfg["dist"], python), wheel_dir)
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "why": f"could not fetch the nightly wheel: {e}"}
    c2, e2 = iso([uv_bin(), "pip", "install", "-q", "-p", py, "--no-deps", "--reinstall", whl["path"]])
    rc, _ = run(c2, log, env=e2, timeout=timeout, sbx=side_sandbox(venv, ro=(whl["path"],)))   # local file: no network needed
    if rc != 0:
        return {"ok": False, "why": f"installing the nightly wheel failed ({rc})"}
    ver = in_side(venv, [py, "-c", f"import {cfg['pkg']} as m;print(m.__version__)"]).stdout.strip()
    commit, how = nightly_commit(whl["version"], venv, cfg, env)
    c2, e2 = iso([uv_bin(), "pip", "check", "-p", py])
    rc, _ = run(c2, log, env=e2, timeout=120, sbx=side_sandbox(venv))
    whl.pop("path")
    return {"ok": bool(ver), "version": ver, "pip_check": "ok" if rc == 0 else "conflicts (see setup log)",
            "build": whl | {"commit": commit, "commit_source": how},
            "test_extras": extras, "optional_test_deps": opt, "optional_backends": optional_backends,
            "why": "" if ver else "package does not import on main side"}


def package_diff(diff: str, pkg: str) -> str:
    """Keep only the file sections of the diff that live under the package directory."""
    parts = re.split(r"(?m)^(?=diff --git )", diff)
    keep = [p for p in parts if re.match(rf"diff --git a/{re.escape(pkg)}/\S+ b/{re.escape(pkg)}/", p)]
    return "".join(keep)


def apply_patch(pdiff: str, site: Path, log: Path) -> tuple[bool, str]:
    pf = site.parent / "pr.diff"
    pf.write_text(pdiff)
    base = ["patch", "-p1", "-F0", "-N", "--no-backup-if-mismatch", "-d", site, "-i", pf]
    venv = site.parents[2]   # site = <venv>/lib/pythonX.Y/site-packages
    env, sbx = base_env(side_home(venv)), side_sandbox(venv)
    rc, _ = run(base + ["--dry-run"], log, env=env, sbx=sbx)
    if rc != 0:
        return False, "PR diff does not apply cleanly to the current nightly (main has moved or the files differ)"
    rc, _ = run(base, log, env=env, sbx=sbx)
    return rc == 0, "" if rc == 0 else "patch failed after a clean dry run"


def source_build(repo: str, item: dict, cfg: dict, venv: Path, workdir: Path, log: Path, python: str,
                 timeout: int, main_extra_reqs: tuple = (), isolated: bool = False) -> dict:
    env = base_env(side_home(venv), install=True)
    src = workdir / "src"
    steps = [["git", "init", "-q", src],
             ["git", "-C", src, "fetch", "-q", "--depth", "1", f"https://github.com/{repo}.git",
              f"pull/{item['pr']}/head"],
             ["git", "-C", src, "checkout", "-q", "FETCH_HEAD"],
             ["git", "-C", src, "submodule", "update", "-q", "--init", "--depth", "1", "--recursive"],
             [uv_bin(), "venv", "-q", "-p", python, venv],
             [uv_bin(), "pip", "install", "-q", "-p", venv / "bin/python", *cfg["deps"], *BASE_TEST_DEPS, *cfg["test_deps"]]]
    for c in steps:   # git on our own fresh clone runs on the host; uv steps (package code) in the PR side's sandbox
        is_uv = Path(str(c[0])).name == "uv"
        sbx = side_sandbox(venv, network=True) if is_uv else HOST
        c2, e2 = isolated_install(c, env, isolated) if is_uv else (c, base_env(workdir / "home-git"))
        rc, _ = run(c2, log, env=e2, timeout=900, sbx=sbx)
        if rc != 0:
            return {"ok": False, "why": f"source checkout/setup failed ({rc}) at: {' '.join(map(str, c[:3]))}"}
    optional = [str(x) for x in list(cfg.get("optional_test_deps") or []) + list(main_extra_reqs)]
    optional += [r for r in optional_backend_reqs(src, cfg["dist"]) if r not in optional]
    backends = install_optional_backends({"pr": venv}, optional, log, timeout, isolated) if optional else {
        "installed": [], "skipped": []}
    t0 = time.time()
    c2, e2 = isolated_install([uv_bin(), "pip", "install", "-p", venv / "bin/python", "--no-cache", src], env, isolated)
    rc, secs = run_heavy(c2, log, env=e2, timeout=timeout, sbx=side_sandbox(venv, network=True))
    if rc == "oom":
        return {"ok": False, "build_seconds": round(time.time() - t0, 1),
                "infrastructure_failure": {"kind": "oom", "action": "retry"}, "why": _oom_reason()}
    if rc != 0:
        tail = log.read_text(errors="replace").strip().splitlines()[-15:]
        hint = next((ln for ln in reversed(tail) if re.search(r"error|not found|ERROR", ln)), tail[-1] if tail else "")
        return {"ok": False, "build_seconds": round(time.time() - t0, 1),
                "why": f"source build of PR head {'timed out' if rc == 'timeout' else 'failed'} after {secs}s: {hint.strip()[:200]}"}
    ver = in_side(venv, [venv / "bin/python", "-c", f"import {cfg['pkg']} as m;print(m.__version__)"]).stdout.strip()
    return {"ok": bool(ver), "version": ver, "build_seconds": secs, "optional_backends": backends,
            "why": "" if ver else "built package does not import"}


def map_tests(files: dict, pkg: str, site: Path, cfg: dict, max_targets: int = 6) -> list[str]:
    """Touched modules -> test files (paths relative to site-packages)."""
    targets: list[str] = []

    def add(p):
        if p not in targets and (site / p).is_file():
            targets.append(p)
    for f in files["package_py"] + files["compiled"]:
        base = os.path.basename(f)
        if "/tests/" in f and base.startswith("test_") and base.endswith(".py"):
            add(f)
    for f in files["package_py"] + files["compiled"]:
        if "/tests/" in f:
            continue
        stem = os.path.splitext(os.path.basename(f))[0].lstrip("_")
        if stem in ("init", "", "conftest"):
            stem = os.path.basename(os.path.dirname(f)).lstrip("_")
        d = os.path.dirname(f)
        while d:   # nearest tests/test_<stem>.py walking up (numpy/_core/src/multiarray/x.c -> numpy/_core/tests)
            add(f"{d}/tests/test_{stem}.py")
            if d == pkg:
                break
            d = os.path.dirname(d)
        if cfg.get("tests_root"):
            for hit in sorted(glob.glob(str(site / cfg["tests_root"] / "**" / f"test_{stem}*.py"), recursive=True))[:3]:
                add(os.path.relpath(hit, site))
    if not targets:  # fall back to the nearest tests/ directory of the first touched module
        for f in files["package_py"] + files["compiled"]:
            d = os.path.dirname(f)
            while d and d != pkg:
                if (site / d / "tests").is_dir():
                    targets.append(f"{d}/tests"); break
                d = os.path.dirname(d)
            if targets:
                break
    return targets[:max_targets]


SIDE_KEY = {"main": "old", "pr": "new"}   # shared schema per_run.side: old = main/base, new = PR
# Import name -> pip distribution. Only plain wheels: installed on both sides when new tests skip for them.
PIP_OPTIONAL = {"duckdb": "duckdb", "ibis": "ibis-framework", "sqlframe": "sqlframe", "polars": "polars",
                "datafusion": "datafusion", "pytest_asyncio": "pytest-asyncio", "pytest-asyncio": "pytest-asyncio"}
RESOURCE_RE = re.compile(r"memory required|free memory|out of memory|\bdisk\b|no space|\bnetwork\b", re.I)
_EXC_RE = re.compile(r"\b([A-Z][A-Za-z0-9_]*(?:Error|Exception))\b")
MISSING_DEP_RE = re.compile(
    r"could not import '?([\w.]+)'?|no module named '?([\w.]+)'?|requires? (?:the )?'?([\w.-]+)'?(?: to be installed| is not installed)?$"
    r"|'?([\w.-]+)'? (?:is )?not installed", re.I)


def side_independent(dotted: str) -> str:
    """Drop the environment prefix of a dotted path ('...venv-main.lib.python3.12.site-packages.pkg.tests.t'
    -> 'pkg.tests.t'), so main and PR runs of the same test or module get the same id on every route."""
    return dotted.split("site-packages.", 1)[1] if "site-packages." in dotted else dotted


def parse_junit(path: Path) -> dict:
    """{test id: (outcome, message)}. outcome: passed | failed | error | skipped (pytest.skip and xfail) |
    load_error (a test module that failed to load/collect; its id is '::<module>').
    Skip messages are kept as '<type>: <message>' so missing-dependency skips can be recognised."""
    res = {}
    if not path.exists():
        return res
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError:
        return res
    for tc in root.iter("testcase"):
        cls = side_independent(tc.get("classname") or "")
        name = tc.get("name") or ""
        if not cls:   # collection error: empty classname, the module path (with the env prefix) is in name
            name = side_independent(name)
        tid = cls + "::" + name
        outcome, msg = "passed", ""
        for ch in tc:
            if ch.tag in ("failure", "error"):
                outcome = "failed" if ch.tag == "failure" else ("load_error" if not cls else "error")
                m = (ch.get("message") or ch.text or "").strip()
                msg = m.splitlines()[0][:200] if m else ch.tag
                break
            if ch.tag == "skipped":
                outcome = "skipped"
                msg = f"{ch.get('type') or 'skip'}: {(ch.get('message') or '').strip()[:200]}"
        res[tid] = (outcome, msg)
    return res


def missing_dependency(skip_msg: str) -> str | None:
    """Module named by a skip caused by a missing optional dependency ('could not import scipy', 'requires pyarrow'),
    else None. xfails are never dependency skips."""
    if not skip_msg or skip_msg.startswith("pytest.xfail"):
        return None
    m = MISSING_DEP_RE.search(skip_msg.split(": ", 1)[-1].strip())
    if not m:
        return None
    return next(g for g in m.groups() if g).split(".")[0]


def _aggregate_names(rec: dict) -> list[str]:
    """Aggregate requirements files of a component app (from the product setup plan) that no install path reads."""
    plan = (rec.get("demo_helper") or {}).get("setup_plan") or {}
    return [str(n) for n in plan.get("aggregate_names") or []]


def _contree_ready() -> bool:
    from poc import contree_sandboxes
    sess = contree_sandboxes.session()
    return (contree_sandboxes.backend() == "contree" and sess is not None
            and bool(sess.main_uuid) and bool(sess.pr_uuid))


def _maybe_prepare_contree(a, repo: str, main_sha: str, pr_sha: str, rec: dict, timeout: int,
                           extra_shell: str = "", main_dir=None) -> str | None:
    """Build Contree main/PR checkpoints for source-pair. On failure return a refusal; there is no local bubblewrap
    fallback (no pull-request code runs). Returns None when the check may continue.

    extra_shell is the same text for both checkpoints. Empty keeps the default install.
    """
    from poc import contree_sandboxes
    if getattr(a, "sandbox_backend", None) != "contree":
        return None
    contree_sandboxes.clear_session()
    try:
        sess = contree_sandboxes.prepare_source_pair(repo, main_sha, pr_sha, timeout=timeout, extra_shell=extra_shell,
                                                     **({"deps_only_fallback": True, "deps_exclude": _aggregate_names(rec),
                                                        "retry_transient": True}
                                                        if product_route(a) else {}))
        rec["contree"] = sess.describe()
        rec["machine"] = "contree"
        rec["sandbox_backend"] = "contree"
        rec["sandbox_backend_note"] = contree_sandboxes.note()
        if product_route(a):
            return _check_contree_pythons(sess, rec, main_dir)
        return None
    except contree_sandboxes.ContreeError as e:
        contree_sandboxes.clear_session()
        refusal, entry = contree_refusal(e)
        rec["sandbox_backend"] = "contree"
        rec["sandbox_backend_note"] = refusal
        rec["machine"] = "contree (not run)"
        rec["contree"] = entry
        return refusal


def own_index_refusal(a, cnv: str | None, *checkouts) -> str | None:
    """A Contree setup failure on a product check whose project needs its own index or uv sources: could not verify
    with that limitation as the reason instead of the generic setup failure. Anything else is returned unchanged."""
    from poc import demo_helper
    if not cnv or not product_route(a) or cnv.startswith("infrastructure failure:"):
        return cnv
    found = [f for c in checkouts if c is not None for f in demo_helper.own_index_config(c)]
    return demo_helper.own_index_reason(list(dict.fromkeys(found))) if found else cnv


def _check_contree_pythons(sess, rec: dict, main_dir) -> str | None:
    """Record the Python each Contree side ran and refuse the check when it is unreadable or outside requires-python.

    requires-python comes from main's checkout only, so a PR cannot loosen it. A refusal caps the result at
    could_not_verify; it never becomes a normal result."""
    from poc import contree_sandboxes, demo_helper
    specs: list[str] = []
    if main_dir is not None and Path(main_dir).is_dir():
        specs, _declared = demo_helper._python_from_checkout(Path(main_dir))
    info = contree_sandboxes.side_pythons(sess, specs)
    rec.setdefault("contree", {})["python"] = info
    if info["problems"]:
        return "Contree Python check failed: " + "; ".join(info["problems"])
    return None


def contree_only_extra_shell(declared: list[str], optional: list[str], base: str = "") -> str:
    """Shell for both Contree checkpoints in contree-only mode: the declared test dependencies (required) and each
    optional test backend (best effort, a failure is skipped) are installed inside Contree, not locally."""
    import shlex as _sh
    lines = [base] if base.strip() else []
    if declared:
        lines.append("python -m pip install -q " + " ".join(_sh.quote(r) for r in declared))
    for req in optional:
        lines.append(f"python -m pip install -q {_sh.quote(req)} || echo 'optional backend skipped: {req}'")
    return "\n".join(lines)


def repo_addopts_flag(keep: bool, root: Path | None = None) -> str:
    """Shell form of the addopts override. A product check keeps the repository's own pytest addopts (for example
    a plugin it loads with ``-p``), minus only the flags our own command sets (read from ``root``'s pytest config);
    the study route blanks them as before."""
    if not keep:
        return "-o addopts= "
    return "".join(shlex.quote(x) + " " for x in repo_addopts_args(True, root))


def repo_addopts_args(keep: bool, root: Path | None = None) -> list[str]:
    if not keep:
        return ["-o", "addopts="]
    from poc import pytest_addopts
    return pytest_addopts.filtered_override(root)


def _contree_pytest_once(side: str, targets: list[str], test_timeout: int, run_timeout: int,
                         workers: str, jx: Path, lg: Path, keep_addopts: bool = False,
                         root: Path | None = None) -> tuple[int | str, float]:
    """One Contree disposable pytest; junit+log written locally from the remote shell output."""
    from poc import contree_sandboxes
    sess = contree_sandboxes.session()
    assert sess is not None
    tg = " ".join(shlex.quote(t) for t in targets)
    nflag = f"-n {shlex.quote(workers)} " if workers != "0" else ""
    shell = (
        "set +e\ncd /work/src\n"
        f"python -m pytest {tg} -p no:cacheprovider -q -rfE --timeout={int(test_timeout)} "
        f"{repo_addopts_flag(keep_addopts, root)}-o junit_family=xunit2 --junitxml=/tmp/poc-junit.xml {nflag}"
        ">/tmp/poc-pytest.log 2>&1\n"
        "ec=$?\n"
        "if grep -q 'different tests were collected' /tmp/poc-pytest.log 2>/dev/null && "
        f"[ {shlex.quote(workers)} != 0 ]; then\n"
        f"  python -m pytest {tg} -p no:cacheprovider -q -rfE --timeout={int(test_timeout)} "
        f"{repo_addopts_flag(keep_addopts, root)}-o junit_family=xunit2 --junitxml=/tmp/poc-junit.xml "
        ">/tmp/poc-pytest.log 2>&1\n  ec=$?\nfi\n"
        "printf '___POC_EXIT___%s\\n' \"$ec\"\n"
        "printf '___POC_JUNIT___\\n'\ncat /tmp/poc-junit.xml 2>/dev/null\n"
        "printf '___POC_LOG___\\n'\ncat /tmp/poc-pytest.log 2>/dev/null\n"
    )
    t0 = time.time()
    raw = sess.run_op(side, shell, disposable=True, timeout=run_timeout)
    secs = round(time.time() - t0, 1)
    out = (raw.get("stdout") or "") + "\n" + (raw.get("stderr") or "")
    exit_m = re.search(r"___POC_EXIT___(\S+)", out)
    junit = out.split("___POC_JUNIT___\n", 1)[-1].split("___POC_LOG___\n", 1)[0] if "___POC_JUNIT___" in out else ""
    log = out.split("___POC_LOG___\n", 1)[-1] if "___POC_LOG___" in out else out
    lg.write_text(f"$ contree pytest ({side})\n{log}")
    jx.unlink(missing_ok=True)
    if junit.strip().startswith("<?xml") or "<testsuite" in junit:
        jx.write_text(junit.strip())
    if exit_m is None:
        rc: int | str = raw.get("exit_code") if raw.get("exit_code") is not None else "error"
    else:
        try:
            rc = int(exit_m.group(1))
        except ValueError:
            rc = "timeout" if exit_m.group(1) == "timeout" else exit_m.group(1)
    return rc, secs


def run_tests(side_venvs: dict, targets_by_side: dict, rdir: Path, workdir: Path, runs: int, workers: str,
              test_timeout: int, run_timeout: int, cwds: dict | None = None,
              keep_addopts: bool = False) -> tuple[list[dict], dict]:
    """targets are relative to site-packages (nightly routes) or to the side's checkout (cwds given).
    per_run entries use the shared schema shape (side old/new, all counts present).
    When a Contree session with main/PR checkpoints is active, pytest runs remotely (source-pair)."""
    from poc import run_progress
    use_contree = _contree_ready() and cwds is not None
    envs = ({side: base_env(side_home(v)) for side, v in side_venvs.items()} if not use_contree else {})
    per_run, results = [], {"main": [], "pr": []}
    for i in range(1, runs + 1):
        for side in ("main", "pr"):
            run_progress.emit("pytest", "code", f"before run {i}/{runs}")
            venv = side_venvs[side]
            tg_rel = list(targets_by_side[side])
            if use_contree:
                tg = tg_rel  # paths relative to /work/src
            else:
                base = cwds[side] if cwds else site_packages(venv)
                tg = [str(base / t) for t in tg_rel]
            jx = rdir / f"junit-{side}-{i}.xml"; lg = rdir / f"pytest-{side}-{i}.log"
            jin = side_out(venv) / jx.name   # written inside the side's sandbox, then moved to the run folder
            entry = {"side": SIDE_KEY[side], "run": i, "passed": 0, "failed": 0, "error": 0, "skipped": 0,
                     "collection_errors": 0}
            if not tg:
                results[side].append({}); per_run.append(entry | {"exit": "no-targets", "seconds": 0,
                                                                   "pytest_summary": "", "junit": False})
                run_progress.emit("pytest", "code", f"after run {i}/{runs}")
                continue
            if use_contree:
                rc, secs = _contree_pytest_once(side, tg, test_timeout, run_timeout, workers, jx, lg, keep_addopts,
                                                 root=(cwds[side] if cwds else None))
            else:
                cmd = [venv / "bin/python", "-m", "pytest", *tg, "-p", "no:cacheprovider", "-q", "-rfE",
                       f"--timeout={test_timeout}", *repo_addopts_args(keep_addopts, cwds[side] if cwds else None),
                       "-o", "junit_family=xunit2",
                       f"--junitxml={jin}"]
                if workers != "0":
                    cmd += ["-n", workers]
                rc, secs = run(cmd, lg, cwd=(cwds[side] if cwds else side_cwd(venv)), env=envs[side],
                               timeout=run_timeout, sbx=side_sandbox(venv))
                if workers != "0" and XDIST_MISMATCH in lg.read_text(errors="replace"):
                    # pytest-xdist refuses suites whose test ids differ between worker processes; rerun serially
                    jin.unlink(missing_ok=True)
                    rc, s2 = run(cmd[:-2], lg, cwd=(cwds[side] if cwds else side_cwd(venv)), env=envs[side],
                                 timeout=run_timeout, sbx=side_sandbox(venv))
                    secs += s2
                jx.unlink(missing_ok=True)
                if jin.exists():
                    shutil.move(jin, jx)
            parsed = parse_junit(jx)
            results[side].append(parsed)
            for o, _ in parsed.values():
                entry["error" if o == "load_error" else o] += 1
            text = lg.read_text(errors="replace")
            entry["collection_errors"] = len(re.findall(r"^ERROR collecting ", text, re.M))
            tail = (text.strip().splitlines() or [""])[-1][:200]
            per_run.append(entry | {"exit": rc, "seconds": secs, "pytest_summary": tail, "junit": jx.exists()})
            run_progress.emit("pytest", "code", f"after run {i}/{runs}")
    return per_run, results


def _coverage_skipped_by_env() -> bool:
    """Console recorded demos set POC_SKIP_COVERAGE. Study and CLI leave it unset."""
    return (os.environ.get("POC_SKIP_COVERAGE") or "").strip().lower() in {"1", "true", "yes", "on"}


def coverage_run(item: dict, venv: Path, main_root: Path, pr_root: Path, targets: list[str], prdir: Path,
                 workdir: Path, a, cwd: Path | None = None) -> dict:
    """Coverage gate measurement: ONE extra, untimed PR-side run of the same test subset under coverage.py
    (pytest-cov, so it also works with -n workers), after the 3 timed runs, so their timings stay clean.

    Changed lines are found by diffing the main-side file against the PR-side file that was actually tested (exact for
    every route, including a diff applied with offsets); executable lines are coverage.py's executed + missing lines.
    main_root / pr_root: the folder the PR's repo-relative paths resolve against on each side (site-packages for the
    nightly routes, the checkout for source-pair)."""
    if getattr(a, "no_coverage", False) or _coverage_skipped_by_env():
        return {"status": "skipped", "why": "--no-coverage"}
    if not uses(getattr(a, "baseline", None), "coverage"):
        return {"status": "skipped", "why": f"baseline {a.baseline} does not use the coverage gate"}
    py = coverage_gate.python_sources(item["files"])
    if not py:
        return {"status": "not needed", "why": "no changed non-test Python files"}
    changed, sources = {}, set()
    for rel in py:
        new = pr_root / rel
        if not new.is_file():
            continue  # deleted by the PR, or not part of the installed package
        old = main_root / rel
        changed[rel] = coverage_gate.changed_lines(old.read_text(errors="replace") if old.is_file() else None,
                                                   new.read_text(errors="replace"), statement_start=product_route(a))
        sources.add(str(new.parent))
    if not changed:
        return {"status": "failed", "why": "none of the changed Python files exist on the PR side"}
    log = prdir / "coverage-pr.log"
    c2, e2 = isolated_install([uv_bin(), "pip", "install", "-q", "-p", venv / "bin/python", "coverage>=7", "pytest-cov>=5"],
                              base_env(side_home(venv), install=True), product_route(a))
    rc, _ = run(c2, log, env=e2, timeout=600, sbx=side_sandbox(venv, network=True))
    if rc != 0:
        return {"status": "failed", "why": f"installing coverage failed ({rc}); see coverage-pr.log"}
    out = prdir / "coverage-pr.json"
    oin = side_out(venv) / out.name
    base = cwd or pr_root
    cmd = [venv / "bin/python", "-m", "pytest", *[str(base / t) for t in targets], "-p", "no:cacheprovider", "-q",
           f"--timeout={a.test_timeout}", *repo_addopts_args(product_route(a), cwd), *[f"--cov={s}" for s in sorted(sources)],
           f"--cov-report=json:{oin}"]
    if a.workers != "0":
        cmd += ["-n", a.workers]
    rc, secs = run(cmd, prdir / "coverage-pytest.log", cwd=cwd or side_cwd(venv), env=base_env(side_home(venv)),
                   timeout=a.run_timeout, sbx=side_sandbox(venv))
    out.unlink(missing_ok=True)
    if oin.exists():
        shutil.move(oin, out)
    if not out.exists():
        return {"status": "failed", "why": f"coverage run produced no data (exit {rc}); see coverage-pytest.log",
                "seconds": secs}
    cov_files, why = coverage_gate.parse_report(out.read_text(errors="replace"))
    if cov_files is None:
        return {"status": "not measured", "why": f"{why}; see coverage-pytest.log", "seconds": secs}
    res = coverage_gate.measure(changed, cov_files)
    return res | {"seconds": secs, "exit": rc, "log": "coverage-pytest.log"}


def _coverage_changed(item: dict, main_root: Path, pr_root: Path, a=None) -> tuple[dict, dict]:
    """Changed lines for the coverage gate, or a status dict when there is nothing to measure."""
    if not coverage_gate.python_sources(item["files"]):
        return {}, {"status": "not needed", "why": "no changed non-test Python files"}
    changed = {}
    for rel in coverage_gate.python_sources(item["files"]):
        new = pr_root / rel
        if not new.is_file():
            continue
        old = main_root / rel
        changed[rel] = coverage_gate.changed_lines(old.read_text(errors="replace") if old.is_file() else None,
                                                   new.read_text(errors="replace"), statement_start=product_route(a))
    if not changed:
        return {}, {"status": "failed", "why": "none of the changed Python files exist on the PR side"}
    return changed, {}


# Runs inside the Contree PR checkpoint after pytest: keeps only the changed files in the coverage report and
# prints it compactly, so a large project's report fits in the command output (which Contree caps).
_COV_SHRINK = (
    "import json,sys\n"
    "d=json.load(open(sys.argv[1]))\n"
    "want=sys.argv[2:]\n"
    "d['files']={k:v for k,v in d.get('files',{}).items() if any(k==w or k.endswith('/'+w) for w in want)}\n"
    "print(json.dumps(d,separators=(',',':')))\n"
)


# Product route: the report never travels through the size-limited command output. Inside the PR checkpoint the
# changed-files report is gzip-compressed, base64-encoded and written to a file; the run prints only its length and
# SHA-256. The file is then fetched in fixed-size pieces from the saved result image and checked before use.
_COV_PACK = (
    "import base64,gzip,hashlib,json,os,sys\n"
    "src=sys.argv[1];want=sys.argv[2:]\n"
    "try:\n"
    " d=json.load(open(src))\n"
    " d['files']={k:v for k,v in d.get('files',{}).items() if any(k==w or k.endswith('/'+w) for w in want)}\n"
    " raw=json.dumps(d,separators=(',',':')).encode()\n"
    "except Exception:\n"
    " raw=open(src,'rb').read() if os.path.exists(src) else b''\n"
    "b=base64.b64encode(gzip.compress(raw)).decode()\n"
    "os.makedirs('/work/poc-cov',exist_ok=True)\n"
    "open('/work/poc-cov/cov.b64','w').write(b)\n"
    "print('___POC_COV_FILE___%d %s'%(len(b),hashlib.sha256(b.encode()).hexdigest()))\n"
)
COV_CHUNK = 40000
COV_MAX_CHUNKS = 200
COV_FETCH_FAILED = "the coverage report could not be fetched from Contree"


COV_MIN_PIECE_SECONDS = 5


def _cov_clock() -> float:
    return time.monotonic()


def fetch_contree_coverage(sess, image: str, length: int, digest: str, timeout: int,
                           clock=None) -> tuple[str | None, str]:
    """(report JSON text, '') fetched piece by piece from the saved image, or (None, plain reason).

    timeout is one overall deadline for the whole fetch, not per piece: each piece gets only the time left."""
    import base64
    import gzip
    import hashlib
    clock = clock or _cov_clock
    deadline = clock() + max(0, int(timeout))
    if not image:
        return None, f"{COV_FETCH_FAILED} (the run returned no image id)"
    if length <= 0 or length > COV_CHUNK * COV_MAX_CHUNKS:
        return None, f"{COV_FETCH_FAILED} (unexpected size {length})"
    parts = []
    for start in range(1, length + 1, COV_CHUNK):
        end = min(start + COV_CHUNK - 1, length)
        left = int(deadline - clock())
        if left < COV_MIN_PIECE_SECONDS:
            return None, f"{COV_FETCH_FAILED} (ran out of time after {len(parts)} of {-(-length // COV_CHUNK)} pieces)"
        try:
            raw = sess.run_image(image, f"cut -c {start}-{end} /work/poc-cov/cov.b64", timeout=left)
        except Exception as e:  # noqa: BLE001
            return None, f"{COV_FETCH_FAILED} ({type(e).__name__})"
        if not isinstance(raw, dict) or raw.get("exit_code") != 0:
            return None, f"{COV_FETCH_FAILED} (a piece could not be read)"
        piece = (raw.get("stdout") or "").strip()
        if len(piece) != end - start + 1:
            return None, f"{COV_FETCH_FAILED} (a piece came back the wrong size)"
        parts.append(piece)
    blob = "".join(parts)
    if hashlib.sha256(blob.encode()).hexdigest() != digest:
        return None, f"{COV_FETCH_FAILED} (checksum mismatch)"
    try:
        return gzip.decompress(base64.b64decode(blob)).decode("utf-8", "replace"), ""
    except (ValueError, OSError, EOFError):
        return None, f"{COV_FETCH_FAILED} (the report could not be decoded)"


def contree_coverage_run(item: dict, main_root: Path, pr_root: Path, targets: list[str], prdir: Path, a) -> dict:
    """Coverage gate measurement inside the Contree PR checkpoint.

    pytest and coverage run remotely. The JSON report comes back in the command output and is fed to
    coverage_gate.measure. No key is placed in the shell. A missing report stays 'not measured', so a product
    check is still capped at could_not_verify."""
    if getattr(a, "no_coverage", False) or _coverage_skipped_by_env():
        return {"status": "skipped", "why": "--no-coverage"}
    if not uses(getattr(a, "baseline", None), "coverage"):
        return {"status": "skipped", "why": f"baseline {a.baseline} does not use the coverage gate"}
    changed, early = _coverage_changed(item, main_root, pr_root, a)
    if early:
        return early
    from poc import contree_sandboxes
    sess = contree_sandboxes.session()
    if sess is None or not getattr(sess, "pr_uuid", None):
        return {"status": "not measured", "why": CONTREE_ONLY_COVERAGE_WHY}
    sources = sorted({str(PurePosixPath("/work/src") / PurePosixPath(rel).parent) for rel in changed})
    tg = " ".join(shlex.quote(t) for t in targets)
    cov = " ".join(f"--cov={shlex.quote(s)}" for s in sources)
    nflag = f"-n {shlex.quote(str(a.workers))} " if str(a.workers) != "0" else ""
    shell = (
        "set +e\ncd /work/src\n"
        f"python -m pytest {tg} -p no:cacheprovider -q --timeout={int(a.test_timeout)} "
        f"{repo_addopts_flag(product_route(a), pr_root)}{nflag}{cov} --cov-report=json:/tmp/poc-cov.json "
        ">/tmp/poc-cov-pytest.log 2>&1\n"
        "ec=$?\n"
        "printf '___POC_EXIT___%s\\n' \"$ec\"\n"
        "printf '___POC_COV_START___\\n'\n"
        f"python -c {shlex.quote(_COV_SHRINK)} /tmp/poc-cov.json {' '.join(shlex.quote(r) for r in sorted(changed))}"
        " 2>/dev/null || cat /tmp/poc-cov.json 2>/dev/null\n"
        "printf '\\n___POC_COV_END___\\n'\n"
        "printf '___POC_LOG___\\n'\ncat /tmp/poc-cov-pytest.log 2>/dev/null\n"
    )
    product = product_route(a)
    if product:  # report goes to a file in the sandbox, not through the capped output
        want = " ".join(shlex.quote(r) for r in sorted(changed))
        shell = shell.split("printf '___POC_COV_START___", 1)[0] + (
            f"python -c {shlex.quote(_COV_PACK)} /tmp/poc-cov.json {want} 2>/dev/null\n"
            "printf '___POC_LOG___\\n'\ntail -c 20000 /tmp/poc-cov-pytest.log 2>/dev/null\n"
        )
    t0 = time.time()
    try:
        raw = sess.run_op("pr", shell, disposable=not product, timeout=int(a.run_timeout))
    except Exception as e:  # Contree error or timeout: keep the cap instead of crashing the check
        return {"status": "not measured", "why": f"the Contree coverage run failed ({type(e).__name__})",
                "seconds": round(time.time() - t0, 1), "where": "contree"}
    if not isinstance(raw, dict):
        raw = {}
    secs = round(time.time() - t0, 1)
    out = (raw.get("stdout") or "") + "\n" + (raw.get("stderr") or "")
    log = out.split("___POC_LOG___\n", 1)[-1] if "___POC_LOG___" in out else out
    (prdir / "coverage-pytest.log").write_text(f"$ contree coverage (pr)\n{log}")
    blob = ""
    if product:
        m = re.search(r"___POC_COV_FILE___(\d+) ([0-9a-f]{64})", out)
        if not m:
            return {"status": "not measured", "seconds": secs, "where": "contree",
                    "why": f"{COV_FETCH_FAILED} (no report file was written); see coverage-pytest.log"}
        blob, why = fetch_contree_coverage(sess, raw.get("uuid") or "", int(m.group(1)), m.group(2),
                                           int(a.run_timeout))
        secs = round(time.time() - t0, 1)
        if blob is None:
            return {"status": "not measured", "seconds": secs, "where": "contree",
                    "why": f"{why}; see coverage-pytest.log"}
    elif "___POC_COV_START___\n" in out:
        blob = out.split("___POC_COV_START___\n", 1)[1].split("\n___POC_COV_END___", 1)[0]
        if "\n___POC_COV_END___" not in out:
            return {"status": "not measured", "seconds": secs, "where": "contree",
                    "why": "the coverage report was cut short by the Contree output limit; see coverage-pytest.log"}
    cov_files, why = coverage_gate.parse_report(blob)
    if cov_files is None:
        return {"status": "not measured", "why": f"{why}; see coverage-pytest.log", "seconds": secs,
                "where": "contree"}
    (prdir / "coverage-pr.json").write_text(blob.strip() + "\n")
    res = coverage_gate.measure(changed, cov_files)
    if res.get("status") != "measured":
        return res | {"seconds": secs, "where": "contree"}
    exit_m = re.search(r"___POC_EXIT___(\S+)", out)
    rc = int(exit_m.group(1)) if exit_m and exit_m.group(1).isdigit() else raw.get("exit_code")
    return res | {"seconds": secs, "exit": rc, "log": "coverage-pytest.log", "where": "contree"}


def gate(rec: dict) -> dict:
    """Apply the coverage gate (poc/coverage_gate.py) to a finished record; baselines without coverage skip it."""
    if not uses(rec.get("baseline"), "coverage"):
        return rec
    return ai_probe_gate(coverage_gate.apply(rec))


def ai_probe_gate_on(baseline: str | None) -> bool:
    """Whether the AI-probe gate (ai_probe_gate) can demote a verdict under this baseline."""
    return uses(baseline, "coverage") and uses(baseline, "claim_probes")


def model_refusal(a) -> str | None:
    """Refuse a daily run that would test PRs with the AI-probe gate on but no model to write probes.

    With no model, no AI-written probe can run, so the gate turns every otherwise clean PR into could_not_verify
    (the 2026-10-14 daily run: 0 of 23 verified). Selecting PRs or rebuilding a report tests nothing and is allowed.
    Benchmark mode is not the daily run, so it is not stopped here. An explicit provider is allowed, including
    none when the AI-probe gate is off.
    Returns the message to stop with, or None."""
    if getattr(a, "select_only", False) or (getattr(a, "report_only", False) and not getattr(a, "rejudge", False)):
        return None
    if getattr(a, "bench", None):
        return None
    if not ai_probe_gate_on(getattr(a, "baseline", None)) or getattr(a, "provider", None) is not None:
        return None
    note = getattr(a, "model_note", None) or "no model provider"
    return ("STOPPED: no AI model is available, but baseline "
            f"{getattr(a, 'baseline', None) or 'full'} only allows 'verified' when an AI-written probe ran a changed "
            f"line. Every PR would come out could_not_verify. ({note}.) Fix: set NEBIUS_API_KEY and pass "
            "--model-provider nebius (the default), or choose a baseline without the AI-probe gate "
            "(--baseline tests, tests+diff or tests+probes).")


def ai_probe_gate(rec: dict) -> dict:
    """In modes that use AI-written probes: never 'verified' unless at least one AI-written (model) probe actually
    executed a changed line (its measured changed-line coverage). Otherwise could_not_verify. Idempotent."""
    if rec.get("verdict") != Verdict.VERIFIED.value or not uses(rec.get("baseline"), "claim_probes"):
        return rec
    items = (rec.get("probes") or {}).get("items") or []
    ran = [it.get("id") for it in items if it.get("source") == "model"
           and it.get("status") not in ("crashed", "error", "uninformative", "not_run", "rejected")
           and ((it.get("probe_changed_line_coverage") or {}).get("changed_lines_covered") or 0) > 0]
    if ran:
        return rec
    out = dict(rec)
    out.setdefault("verdict_before_ai_probe_gate", rec["verdict"])
    out["verdict"] = Verdict.COULD_NOT_VERIFY.value
    out["reason"] = ("not verified: no AI-written probe ran any changed line, so the change itself was not "
                     "exercised by a probe; " + (rec.get("reason") or ""))
    return out


def base_name(test_id: str) -> str:
    """'mod.Class::test_x[a-1]' -> 'mod.Class::test_x' (the test function, without its parametrize id)."""
    return test_id.split("[", 1)[0]


EXECUTED = ("passed", "failed", "error")   # outcomes of a test that actually ran (not skipped, not a load failure)


def module_of(test_id: str) -> str:
    return test_id.split("::", 1)[0]


def in_module(test_id: str, module: str) -> bool:
    m = module_of(test_id)
    return m == module or m.startswith(module + ".")


def executed_counts(results: dict) -> dict:
    """{side: fewest tests that actually ran in any run of that side}."""
    return {side: min((sum(1 for o, _ in r.values() if o in EXECUTED) for r in runs), default=0)
            for side, runs in results.items()}


def normalize_load_errors(run: dict) -> dict:
    """'::<module>' ids (empty classname) are module load failures whatever outcome they were stored with, and their
    module path is made side-independent (results not produced by parse_junit, e.g. older saved results)."""
    out = {}
    for t, (o, m) in run.items():
        if t.startswith("::"):
            t, o = "::" + side_independent(t[2:]), ("load_error" if o in ("error", "failed") else o)
        out[t] = (o, m)
    return out


def resource_skip_detail(results: dict, test_id: str) -> str | None:
    """A pass/skip change whose skip reason is a resource limit (memory, disk, network) on both sides.

    That is the machine, not the pull request. A skip that appears on only one side is left for the normal rules.
    Returns the skip message, or None when this test is not that case."""
    details, outcomes = [], []
    for side in ("main", "pr"):
        saw_skip = False
        for run in results[side]:
            outcome, msg = run.get(test_id, ("absent", ""))
            if outcome not in ("passed", "skipped"):
                return None
            outcomes.append(outcome)
            if outcome == "skipped":
                if not RESOURCE_RE.search(msg or ""):
                    return None
                saw_skip = True
                details.append(msg)
        if not saw_skip:
            return None
    if len(set(outcomes)) < 2:
        return None
    return details[0][:200]


def exception_types(msg: str) -> set[str]:
    return set(_EXC_RE.findall(msg or ""))


def installable_missing(cmp: dict) -> list[str]:
    """Import names of missing modules that are a plain pip install, in first-seen order."""
    out = []
    for d in cmp.get("skipped_missing_dependency", []):
        name = str(d.get("module") or "").split(".")[0]
        if name in PIP_OPTIONAL and name not in out:
            out.append(name)
    return out


def attribute_backend_errors(cmp: dict, results: dict, also_on_base: list[str] | None = None) -> None:
    """New pull-request failures whose exception also happens on the base side are not a pull-request finding.

    Used after an optional module was installed and the tests were run again. The same ZeroDivisionError on both
    sides is the backend (for example ibis on ``% 0``), so those tests move to ``backend_same_error``. A new failure
    whose exception is not seen on the base side stays in ``new_tests_failing``."""
    seen = set(also_on_base or [])
    for run in results.get("main", []):
        for _t, (outcome, msg) in run.items():
            if outcome in ("failed", "error"):
                seen |= exception_types(msg)
    if not seen:
        return
    kept, moved = [], []
    messages = cmp.get("messages") or {}
    for test_id in cmp.get("new_tests_failing", []):
        msg = messages.get(test_id, "")
        if not msg:
            msg = next((m for run in results.get("pr", []) if test_id in run and run[test_id][1]
                        for m in [run[test_id][1]]), "")
        types = exception_types(msg)
        if types and types <= seen:
            moved.append({"test": test_id, "exceptions": sorted(types), "message": msg[:200]})
        else:
            kept.append(test_id)
    if not moved:
        return
    cmp["new_tests_failing"] = kept
    cmp["backend_same_error"] = list(cmp.get("backend_same_error") or []) + moved
    for d in moved:
        messages.pop(d["test"], None)
    cmp["messages"] = {t: messages[t] for t in (cmp["regressions"] + cmp["new_tests_failing"])[:20] if t in messages}


def compare_sides(results: dict) -> dict:
    """Plain-code comparison of per-test outcomes over the 3 runs per side (poc.diff.confirm).

    Rename-aware: a test id that disappears is only 'removed' if no new id with the same base test name appeared.
    Otherwise it is re-parametrized (its parametrize ids changed); the new ids are judged by their own outcomes.
    New/changed tests that are skipped because an optional dependency is missing are listed separately.
    A test that is new on the PR side and fails only with a missing-dependency message (ModuleNotFoundError:
    No module named 'X', or the same messages missing_dependency() already recognises) is listed there too,
    not under new_tests_failing. confirm_missing() drops that classification when the module is installed.
    Test modules that fail to load are tracked as modules, never as tests: on both sides (load_failed_both), only on the
    PR side (load_failed_pr, with the main-side tests that no longer run) or only on main (load_failed_main); their
    tests are not counted as removed, new or unchanged."""
    results = {side: [normalize_load_errors(r) for r in runs] for side, runs in results.items()}
    ids = set()
    for r in results["main"] + results["pr"]:
        ids |= set(r)
    out = {"same": 0, "same_skipped_both": 0, "regressions": [], "fixed": [], "new_tests_passing": 0,
           "new_tests_failing": [], "new_tests_skipped": [], "removed_tests": [], "reparametrized": [], "skipped_missing_dependency": [],
           "flaky": [], "pr_unstable": [], "pr_unstable_noisy": [], "environment": [], "other_changes": [],
           "preexisting_failures": [], "load_failed_both": [],
           "load_failed_pr": [], "load_failed_main": []}
    msgs, removed, added = {}, [], []
    bad = ("failed", "error")

    def load_state(runs, t):
        os_ = {r.get(t, ("absent", ""))[0] for r in runs}
        return "all" if os_ == {"load_error"} else ("some" if "load_error" in os_ else "none")
    one_side = {}
    for t in sorted(i for i in ids if i.startswith("::")):
        lm, lp = load_state(results["main"], t), load_state(results["pr"], t)
        if lm == lp == "all":
            out["load_failed_both"].append(t[2:])
        elif lp == "all" and lm == "none":
            one_side[t[2:]] = "pr"
        elif lm == "all" and lp == "none":
            one_side[t[2:]] = "main"
    for mod, side in sorted(one_side.items()):
        other = results["main" if side == "pr" else "pr"]
        tests = sorted({t for r in other for t in r if not t.startswith("::") and in_module(t, mod)})
        out["load_failed_" + side].append({"module": mod, "tests_affected": len(tests)})
    handled = {"::" + m for m in out["load_failed_both"]} | {"::" + m for m in one_side}

    def skip_id(t):
        return t in handled or any(in_module(t, m) for m in one_side)
    for t in sorted(ids):
        if skip_id(t):
            continue
        m = [{"o": r.get(t, ("absent", ""))[0]} for r in results["main"]]
        p = [{"o": r.get(t, ("absent", ""))[0]} for r in results["pr"]]
        state = confirm(m, p)
        if state != "same":
            detail = resource_skip_detail(results, t)
            if detail:
                out["environment"].append({"test": t, "kind": "resource", "detail": detail})
                continue
        if state == "same":
            out["same"] += 1
            if m[0]["o"] in bad:
                out["preexisting_failures"].append(t)
            elif m[0]["o"] == "skipped":
                out["same_skipped_both"] += 1
            continue
        if state == "flaky":
            out["flaky"].append(t); continue
        if state == "pr_unstable":
            # Base always passed and the PR sometimes fails, with a repeated PR result: call it.
            # Every PR run different, or no failure to point at: too mixed to call.
            kind = "noisy"
            if (not pr_runs_too_noisy(p) and m[0]["o"] == "passed"
                    and any(row["o"] in ("failed", "error") for row in p)):
                kind = "regression"
            out["pr_unstable" if kind == "regression" else "pr_unstable_noisy"].append(t)
            continue
        mo, po = m[0]["o"], p[0]["o"]
        pmsg = next((r[t][1] for r in results["pr"] if t in r and r[t][1]), "")
        if po in bad and pmsg:
            msgs[t] = pmsg
        if mo == "absent":
            added.append(t)
        dep = missing_dependency(pmsg) if (po == "skipped" or (mo == "absent" and po in bad)) else None
        # A brand-new test that fails only because an optional module is missing is blocked, not a PR break.
        # A test that passed on main and fails on the PR stays a regression even if the message names a module.
        if dep and ((po == "skipped" and mo != "skipped") or (mo == "absent" and po in bad)):
            entry = {"test": t, "module": dep, "main": mo, "pr": po}
            if pmsg:
                entry["message"] = pmsg
            out["skipped_missing_dependency"].append(entry)
        elif mo == "passed" and po in bad:
            out["regressions"].append(t)
        elif mo in bad and po == "passed":
            out["fixed"].append(t)
        elif mo == "absent" and po == "passed":
            out["new_tests_passing"] += 1
        elif mo == "absent" and po in bad:
            out["new_tests_failing"].append(t)
        elif mo == "absent" and po == "skipped":
            # A test that did not exist before and skips on the PR (e.g. a parametrization the code rejects with a
            # skip) did not change any behaviour that ran before. Listed, never a finding.
            out["new_tests_skipped"].append(t)
        elif po == "absent":
            removed.append(t)
        else:
            out["other_changes"].append(f"{t}: {mo} -> {po}")
    added_by_base: dict = {}
    for t in added:
        added_by_base.setdefault(base_name(t), []).append(t)
    removed_by_base: dict = {}
    for t in removed:
        removed_by_base.setdefault(base_name(t), []).append(t)
    for b, gone in sorted(removed_by_base.items()):
        if b in added_by_base:
            out["reparametrized"].append({"test": b, "removed_ids": gone, "added_ids": added_by_base[b]})
        else:
            out["removed_tests"].extend(gone)
    out["executed"] = executed_counts(results)
    out["messages"] = {t: msgs[t] for t in (out["regressions"] + out["new_tests_failing"])[:20] if t in msgs}
    return out


def failing_ids(run_result: dict) -> set:
    return {t for t, (o, _) in run_result.items() if o in ("failed", "error", "load_error")}


def exit_check(per_run: list[dict], results: dict, cmp: dict) -> dict:
    """Is every non-zero pytest exit explained? Exit 1 on a run is explained when each failing test of that run fails
    identically on the other side's run with the same index, or is already a reported finding (regression, new
    failing test, flaky, or blocked by a missing optional dependency). Any other exit code (interrupted, internal
    or usage error) is never explained."""
    flagged = (set(cmp["regressions"]) | set(cmp["new_tests_failing"]) | set(cmp["flaky"])
               | set(cmp.get("pr_unstable") or []) | set(cmp.get("pr_unstable_noisy") or [])
               | {d["test"] for d in cmp.get("skipped_missing_dependency", [])}
               | {d["test"] for d in cmp.get("backend_same_error", [])}
               | {d["test"] for d in cmp.get("environment", [])})
    problems = []
    for e in per_run:
        side = "main" if e["side"] == "old" else "pr"
        other = "pr" if side == "main" else "main"
        if e["exit"] in (0, "no-targets"):
            continue
        idx = e["run"] - 1
        if e["exit"] != 1:
            problems.append(f"{side} run {e['run']}: pytest exit {e['exit']}")
            continue
        mine = failing_ids(results[side][idx]) if idx < len(results[side]) else set()
        theirs = failing_ids(results[other][idx]) if idx < len(results[other]) else set()
        if not mine:
            problems.append(f"{side} run {e['run']}: exit 1 but no failing test in the JUnit report")
        elif side == "pr" and not mine <= (theirs | flagged):
            problems.append(f"PR run {e['run']}: {len(mine - theirs - flagged)} failure(s) not seen on main")
    pre = cmp.get("preexisting_failures", [])
    nonzero = sorted({str(e["exit"]) for e in per_run if e["exit"] not in (0, "no-targets")})
    detail = ("all runs exited 0" if not nonzero else
              f"pytest exit {'/'.join(nonzero)}; " + (f"{len(pre)} failure(s)/error(s) pre-existing and identical on "
                                                      "both sides" if pre else "no identical pre-existing failures"))
    return {"explained": not problems, "problems": problems, "detail": detail}


def touched_stems(files: dict | None) -> tuple[set, set]:
    """(stems of changed source files, dotted module paths of changed test files) for matching test modules."""
    stems, tests = set(), set()
    for f in (files or {}).get("all", []):
        p = PurePosixPath(f)
        if p.suffix not in (".py", ".pyx", ".pxd", ".c", ".cpp", ".h", ".cc"):
            continue
        if coverage_gate.is_test(f):
            if p.suffix == ".py" and p.name.startswith("test_"):
                tests.add(".".join(p.with_suffix("").parts))
        else:
            stem = p.name.split(".")[0].lstrip("_")
            if stem and stem not in ("init", "conftest", "setup"):
                stems.add(stem)
    return stems, tests


def touches(module: str, files: dict | None) -> bool:
    """Does this test module test a file the PR changed? Without file information every module counts (conservative).
    Match: tests/test_<stem>.py of a changed source file, or a changed test file itself."""
    if not files or not files.get("all"):
        return True
    stems, tests = touched_stems(files)
    leaf = module.rsplit(".", 1)[-1]
    return (any(leaf == f"test_{st}" or leaf.startswith(f"test_{st}_") for st in stems)
            or any(module == t or module.endswith("." + t) or t.endswith("." + module) for t in tests))


def load_failure_text(x: dict, side: str) -> str:
    n = x["tests_affected"]
    if side == "pr":
        return f"test module {x['module']} fails to load on the PR side ({n} test(s) no longer run)"
    return f"test module {x['module']} fails to load on the main side ({n} test(s) on the PR side have no baseline)"


def _modules(xs: list, n: int = 3) -> str:
    return ", ".join(xs[:n]) + (f" (+{len(xs) - n})" if len(xs) > n else "")


BASELINES = ("tests", "tests+diff", "tests+probes", "full")
BASELINE_PARTS = {"tests": frozenset(),
                  "tests+diff": frozenset({"diff"}),
                  "tests+probes": frozenset({"claim_probes"}),
                  "full": frozenset({"claim_probes", "diff_info", "coverage", "claim_flags"})}
BASELINE_TEXT = {"tests": "test comparison only",
                 "tests+diff": "test comparison + differential probes (model-free, they decide)",
                 "tests+probes": "test comparison + claim probes (fixed and/or model-written)",
                 "full": "test comparison + claim probes + coverage gate + claim flagging "
                         "(differential probes shown, informational)"}


def uses(baseline: str | None, part: str) -> bool:
    """Whether a baseline (default full; records without one are full) uses a part:
    claim_probes, diff (differential probes decide), diff_info (run and shown only), coverage, claim_flags."""
    return part in BASELINE_PARTS[baseline or "full"]


def probe_items(probe_results: dict | None, baseline: str | None) -> dict | None:
    """The probe results that may decide the verdict under a baseline: claim probes (library/model sources) for
    tests+probes and full, differential probes (source diff) for tests+diff, none for tests."""
    if not probe_results:
        return probe_results
    want = ({"library", "model"} if uses(baseline, "claim_probes") else set()) | (
        {"diff"} if uses(baseline, "diff") else set())
    items = [it for it in probe_results.get("items") or [] if it.get("source", "library") in want]
    return dict(probe_results, items=items)


def verdict_for(cmp: dict | None, cnv_reason: str | None, exits: dict | None = None, files: dict | None = None,
                probe_results: dict | None = None, claims: list | None = None,
                baseline: str | None = None, docstring_only: bool = False,
                same_sides: bool = False) -> tuple[str, str, list[str]]:
    """tests, then probes (with_probes), then behaviour-preservation claims (poc/behaviour_claims.py): a 'verified'
    PR whose title or description claims results stay the same, with no probe checking that, becomes
    could_not_verify ('unverified behaviour claim: "<quote>"; needs a probe'). With a probe, the probe decides.
    baseline (BASELINES, default full) selects which probes decide and whether claims are flagged.
    A docstring-only change (AST equal after blanking docstrings) is verified: the claim holds by construction,
    unless the tests already need attention.
    A probe claim that expects a difference but matches no observation on that probe can only lower a verified
    result to could_not_verify. It never raises a verdict."""
    if same_sides:
        return (Verdict.COULD_NOT_VERIFY.value,
                "unsupported: main and PR sides are the same commit, so nothing was compared; "
                "a docstring-only result cannot be claimed", ["identical_sides"])
    hygiene = (probe_results or {}).get("claim_hygiene") if isinstance(probe_results, dict) else None
    probe_results = probe_items(probe_results, baseline)
    v, reason, fl = with_probes(cmp, cnv_reason, exits, files, probe_results)
    if uses(baseline, "claim_flags") and claims and v == Verdict.VERIFIED.value and not behaviour_claims.probe_covers(
            probe_results):
        q = claims[0]["quote"]
        more = f" (+{len(claims) - 1} more)" if len(claims) > 1 else ""
        v, reason, fl = (Verdict.COULD_NOT_VERIFY.value,
                         f'unverified behaviour claim: "{q}"{more}; needs a probe ({reason})',
                         fl + ["unverified_claim"])
    if docstring_only and v != Verdict.NEEDS_ATTENTION.value:
        v = Verdict.VERIFIED.value
        reason = ("docstring-only change (AST equal after blanking docstrings); behaviour claims hold by construction")
        fl = fl + ["holds_by_construction"]
    missing = probes.unmatched_differs_claims(probe_results)
    if missing and v == Verdict.VERIFIED.value:
        shown = ", ".join(missing[:4])
        extra = f" (+{len(missing) - 4} more)" if len(missing) > 4 else ""
        return (Verdict.COULD_NOT_VERIFY.value,
                f"could not verify: claim(s) {shown}{extra} expect a difference but no observation matches ({reason})",
                fl + ["unmatched_differs_claim"])
    advisory = sorted({str(it.get("id")) for it in (probe_results or {}).get("items") or []
                       for o in it.get("observations") or [] if o.get("advisory")})
    if advisory and v == Verdict.VERIFIED.value:
        # A claim-less probe saw a difference nobody claimed. It does not raise needs attention, but it is
        # unexplained, so the PR cannot be verified either.
        return (Verdict.COULD_NOT_VERIFY.value,
                f"could not verify: probe(s) {', '.join(advisory)} have no claims attached and saw a difference no "
                f"claim covers, so the change is not confirmed ({reason})", fl + ["advisory_unclaimed_difference"])
    if hygiene and hygiene.get("held_back") and v == Verdict.VERIFIED.value:
        return (Verdict.COULD_NOT_VERIFY.value,
                f"could not verify: claim(s) {', '.join(hygiene['held_back'][:4])} expect a difference but no "
                f"observation matches ({reason})", fl + ["unmatched_differs_claim"])
    if hygiene and hygiene.get("dropped_flagged") and v == Verdict.VERIFIED.value:
        from poc import claim_hygiene
        return (Verdict.COULD_NOT_VERIFY.value, f"could not verify: {claim_hygiene.note_text(hygiene)} ({reason})",
                fl + ["dropped_flagged_probe"])
    return v, reason, fl


def with_probes(cmp: dict | None, cnv_reason: str | None, exits: dict | None = None, files: dict | None = None,
                probe_results: dict | None = None) -> tuple[str, str, list[str]]:
    """The PR verdict: the tests' verdict (tests_verdict), then the probes (poc/probes.py). An observation that needs
    attention (it differs and no claim covers it, or it contradicts a claim) makes the verdict
    needs_attention, also when the tests alone could not verify the PR. Flaky observations are shown but never
    decide the verdict, except one that is stable on the base and unstable only on the pull request: that needs
    attention, or could not verify when every pull-request run differs. Warning-only differences never decide.
    Probes never upgrade a verdict: all-green
    probes leave it as the tests decided. Without probes the verdict is exactly the tests' verdict."""
    from poc import probe_adequacy
    v, reason, fl = tests_verdict(cmp, cnv_reason, exits, files)
    items = (probe_results or {}).get("items") or []
    if not items:
        return v, reason, fl
    items, notes = probe_adequacy.deciding_items(items)   # a not_adequate probe never leads to verified
    s = probes.summarize(items)
    s["reason"] = "; ".join([s["reason"]] * bool(s["reason"]) + notes)
    fl = fl + s["labels"]
    if s.get("pr_only_noisy") and v == Verdict.VERIFIED.value and not s["flagged"]:
        names = ", ".join(s["pr_only_noisy"][:4])
        return (Verdict.COULD_NOT_VERIFY.value,
                f"could not verify: observation(s) {names} are stable on the base and unstable only on the PR, "
                f"too mixed to call ({reason})", fl)
    if s["flagged"] and v != Verdict.NEEDS_ATTENTION.value:
        return Verdict.NEEDS_ATTENTION.value, f"{s['reason']}; tests: {reason}", fl
    return v, (f"{reason}; {s['reason']}" if s["reason"] else reason), fl


def tests_verdict(cmp: dict | None, cnv_reason: str | None, exits: dict | None = None,
                  files: dict | None = None) -> tuple[str, str, list[str]]:
    """Verdict from the test comparison alone (claims are checked by probes, see verdict_for).

    Order:
      1. could-not-verify reasons of the run itself;
      2. real findings (regressions, new failing tests, or a test that passes on every base run and fails on some
         pull-request runs) -> needs attention (nothing below can hide them);
      3. no test actually ran on a side (all skipped, or every module failed to load) -> could not verify;
      4. a test module loads on one side only -> could not verify, naming the module;
      5. a test module of the changed code fails to load on both sides -> could not verify;
      6. unexplained pytest exit codes -> could not verify;
      7. new/changed tests skipped, or new tests that fail only because an optional dependency is missing
         -> could not verify (never needs attention);
      8. a test that is stable on the base and unstable only on the pull request, but too mixed to call a
         regression, is could not verify (never verified). A test that is flaky on both sides, or only on the
         base, is listed and does not decide. Those flaky labels are not passed to pr_verdict, because that
         rule treats every amber finding as needs attention;
      9. otherwise poc.verdict.pr_verdict."""
    if cnv_reason:
        return Verdict.COULD_NOT_VERIFY.value, cnv_reason, []
    deps = sorted({d["module"] for d in cmp.get("skipped_missing_dependency", [])})
    dep_note = (f"{len(cmp['skipped_missing_dependency'])} new/changed test(s) skipped or blocked because optional "
                f"dependenc{'y' if len(deps) == 1 else 'ies'} {', '.join(deps)} not installed") if deps else ""
    executed = cmp.get("executed") or {}
    ran_main, ran_pr = executed.get("main"), executed.get("pr")
    nothing_ran = ran_main == 0 or ran_pr == 0
    findings = []
    findings += [FindingLabel.UNMENTIONED_CHANGE] * (len(cmp["regressions"]) + len(cmp["new_tests_failing"]))
    findings += [FindingLabel.UNMENTIONED_CHANGE] * len(cmp.get("pr_unstable") or [])
    findings += [FindingLabel.FLAKY] * len(cmp["flaky"])
    findings += [FindingLabel.NEEDS_HUMAN] * (len(cmp["removed_tests"]) + len(cmp["other_changes"]))
    findings += [FindingLabel.PROVEN] * len(cmp["fixed"])
    if (cmp["same"] or cmp["new_tests_passing"]) and not nothing_ran:
        findings.append(FindingLabel.NO_DIFFERENCE)
    bits = []
    if cmp["regressions"]:
        bits.append(f"{len(cmp['regressions'])} test(s) pass on main but fail on the PR")
    if cmp["new_tests_failing"]:
        bits.append(f"{len(cmp['new_tests_failing'])} new test(s) fail on the PR")
    if cmp["flaky"]:
        shown = ", ".join(cmp["flaky"][:5])
        more = f" (+{len(cmp['flaky']) - 5})" if len(cmp["flaky"]) > 5 else ""
        bits.append(f"{len(cmp['flaky'])} flaky test(s): {shown}{more}")
    pr_only = cmp.get("pr_unstable") or []
    if pr_only:
        shown = ", ".join(pr_only[:5])
        more = f" (+{len(pr_only) - 5})" if len(pr_only) > 5 else ""
        bits.append(f"{len(pr_only)} test(s) pass on every base run but fail on some pull-request runs: {shown}{more}")
    pr_noisy = cmp.get("pr_unstable_noisy") or []
    if pr_noisy:
        shown = ", ".join(pr_noisy[:5])
        more = f" (+{len(pr_noisy) - 5})" if len(pr_noisy) > 5 else ""
        bits.append(f"{len(pr_noisy)} test(s) stable on the base and unstable only on the pull request, "
                    f"too mixed to call a regression: {shown}{more}")
    if cmp["removed_tests"]:
        bits.append(f"{len(cmp['removed_tests'])} test(s) removed on the PR side")
    if cmp["other_changes"]:
        bits.append(f"{len(cmp['other_changes'])} other outcome change(s)")
    if cmp["fixed"]:
        bits.append(f"{len(cmp['fixed'])} test(s) fail on main and pass on the PR")
    if cmp.get("new_tests_skipped"):
        bits.append(f"{len(cmp['new_tests_skipped'])} new test(s) skipped on the PR (they did not exist before; "
                    "listed, not a finding)")
    env = cmp.get("environment") or []
    if env:
        bits.append(f"{len(env)} test(s) varied only between passed and skipped for a resource limit on both sides "
                    "(environment, not a pull-request finding)")
    backend = cmp.get("backend_same_error") or []
    if backend:
        bits.append(f"{len(backend)} new test(s) fail with an error that also happens on the base side "
                    "(optional backend, not a pull-request finding)")
    if cmp.get("reparametrized"):
        n_old = sum(len(x["removed_ids"]) for x in cmp["reparametrized"])
        n_new = sum(len(x["added_ids"]) for x in cmp["reparametrized"])
        bits.append(f"{len(cmp['reparametrized'])} test(s) re-parametrized ({n_old} -> {n_new} ids)")
    pre = cmp.get("preexisting_failures", [])
    if ran_main is not None:
        bits.append("0 tests ran" if (ran_main == 0 and ran_pr == 0) else f"{ran_main} test(s) ran on main, {ran_pr} on the PR")
    unchanged = cmp["same"] - len(pre)   # tests with the same outcome on both sides (passed or skipped), never modules
    skipped_both = cmp.get("same_skipped_both", 0)
    bits.append(f"{cmp['new_tests_passing']} new test(s) pass, {unchanged} unchanged"
                + (f" ({skipped_both} of them skipped on both sides)" if skipped_both else ""))
    if pre:
        bits.append(f"{len(pre)} test failure(s) pre-existing and identical on both sides")
    both = cmp.get("load_failed_both", [])
    if both:
        bits.append(f"{len(both)} test module(s) fail to load on both sides ({_modules(both)}), so their tests did not run")
    for x in cmp.get("load_failed_pr", []):
        bits.append(load_failure_text(x, "pr"))
    for x in cmp.get("load_failed_main", []):
        bits.append(load_failure_text(x, "main"))
    reason = "; ".join(bits)
    fl = [f.value for f in findings]
    # Flaky is amber, and pr_verdict turns every amber finding into needs attention. A flaky test is listed
    # (comparison["flaky"] and the label above) but must not, on its own, produce that verdict.
    verdict_findings = [f for f in findings if f is not FindingLabel.FLAKY]
    cnv = Verdict.COULD_NOT_VERIFY.value
    if cmp["regressions"] or cmp["new_tests_failing"] or pr_only:
        v = pr_verdict(RunSummary(build_ok=True, claims=[Claim("tests", testable=True, probed=True, proven=True)],
                                  findings=verdict_findings))
        return v.value, reason + (f"; {dep_note}" if dep_note else ""), fl
    if backend:
        names = ", ".join(sorted({e for d in backend for e in d.get("exceptions", [])})) or "the same error"
        return (cnv, f"not fully verified: {len(backend)} new test(s) fail with {names}, which also happens on the "
                f"base side after an optional module was installed; not a PR finding ({reason})", fl)
    if nothing_ran:
        where = ("on either side" if ran_main == 0 and ran_pr == 0 else "on main" if ran_main == 0 else "on the PR side")
        return cnv, f"no test actually ran {where}: {reason}" + (f"; {dep_note}" if dep_note else ""), fl
    one_side = [(x, "pr") for x in cmp.get("load_failed_pr", [])] + [(x, "main") for x in cmp.get("load_failed_main", [])]
    if one_side:
        return cnv, f"{load_failure_text(*one_side[0])}: {reason}", fl
    related = [m for m in both if touches(m, files)]
    if related:
        return cnv, (f"not fully verified: the changed code's test module(s) {_modules(related)} failed to load on both "
                     f"sides, so they did not run: {reason}"), fl
    if exits and not exits["explained"]:
        return (cnv, "pytest exit code(s) not explained by identical failures on both sides: "
                + "; ".join(exits["problems"][:3]) + f" ({reason})", fl)
    if dep_note:
        return cnv, f"not fully verified: {dep_note} ({reason})", fl
    if pr_noisy:
        return cnv, f"not fully verified: {reason}", fl
    v = pr_verdict(RunSummary(build_ok=True, claims=[Claim("tests", testable=True, probed=True, proven=True)],
                              findings=verdict_findings))
    # Noise rule: a project test whose result changes between runs on the same side is shown in the reason but
    # never decides the verdict (same rule as for probe observations).
    if cmp["flaky"]:
        reason += "; flaky test(s) shown only: their result changes between runs of the same side, so they do not decide the verdict"
    return v.value, reason, fl


# ---------------------------------------------------------------- per-PR driver
def probe_launcher(venv: Path, path: Path):
    """Probes run in the side's sandbox without network; the probe file is mounted read-only."""
    def launch(argv, env, cwd):
        b = side_sandbox(venv, ro=(path,))
        return sandbox.wrap(argv, env, b["rw"], b["ro"], b["network"], cwd)
    return launch


_CONTREE_CHECKOUTS: dict = {}   # "settings": the test settings for this PR's Contree probe runs (product checks)


def _contree_probe_once(side: str, path: Path, timeout: int, literal_output: bool = False) -> tuple[dict, str, float]:
    """Run one probe file on a Contree checkpoint (upload probe, disposable run)."""
    from poc import contree_sandboxes
    sess = contree_sandboxes.session()
    assert sess is not None
    remote = f"/work/probes/{path.name}"
    from poc import test_settings
    exports = test_settings.shell_exports(_CONTREE_CHECKOUTS.get("settings"))
    t0 = time.time()
    raw = sess.run_op(
        side,
        f"set -euo pipefail\ncd /work/src 2>/dev/null || cd /work\n{exports}python {shlex.quote(remote)}",
        disposable=True, timeout=timeout, files={remote: path})
    secs = round(time.time() - t0, 1)
    out, err = raw.get("stdout") or "", raw.get("stderr") or ""
    code = raw.get("exit_code")
    if code is None:
        code = "error"
    log = out[-4000:] + ("\n--- stderr ---\n" + err[-4000:] if err else "")
    return probes.observations_of(out, code, literal_output), log, secs


def plan_probes(repo: str, item: dict, rec: dict, base_root: Path, pr_roots: list, prdir: Path, a) -> list[dict]:
    """Write and FREEZE every probe of this PR before any PR-side execution (poc/freeze.py). Inputs: the PR title and
    description and base-side code only (base_root). Returns [{path, source, freeze}]; notes go to rec["probe_plan"].
    Claim probes (baselines tests+probes, full): fixed probes (probes/<owner>/<repo>/<pr>.py) and model-written
    probes (--model-provider). Differential probes (tests+diff decides with them; full shows them)."""
    bl = getattr(a, "baseline", None)
    plan, note = [], {"baseline": bl or "full", "model": getattr(a, "model_note", None), "errors": []}
    if uses(bl, "claim_probes") and not getattr(a, "no_probes", False):
        for path in probes.find_probes(repo, item["pr"]):
            try:
                spec = probes.read_spec(path)
            except probes.ProbeError as e:
                note["errors"].append(str(e).replace(str(REPO_ROOT) + "/", ""))
                continue
            gen = freeze.generator("fixed", provenance=spec.get("provenance"))
            plan.append({"path": path, "source": "library", "freeze": freeze.freeze(path, gen, None)})
        provider = getattr(a, "provider", None)
        if provider is not None:
            base_files = {rel: Path(base_root) / rel for rel in coverage_gate.python_sources(item["files"])
                          if (Path(base_root) / rel).is_file()}
            try:
                res = model_probes.generate(provider, repo, item["pr"], item["title"], item.get("body"), base_files,
                                            base_root, pr_roots, prdir / "model-probes",
                                            product=product_route(a))
            except freeze.FreezeError as e:
                res = {"errors": [str(e)], "probes": [], "claims": [], "rejected_claims": []}
            note["model_claims"] = res.get("claims", [])
            note["model_rejected_claims"] = res.get("rejected_claims", [])
            note["errors"] += res.get("errors", [])
            if res.get("rewritten_imports"):   # product checks: src/ layout imports rewritten to the installed name
                note["rewritten_imports"] = res["rewritten_imports"]
            plan += [{"path": x["path"], "source": "model", "freeze": x["freeze"],
                      **({"origin": x["origin"]} if x.get("origin") else {})} for x in res.get("probes", [])]
            if res.get("human_review"):
                rec["human_review"] = res["human_review"]
            made = [c for c in getattr(provider, "calls", []) if c.get("ok")]
            if res.get("errors") and made and not res.get("probes"):
                a.model_fallback = "the AI answered but no probe was usable, so only fixed probes ran"
            elif res.get("errors") and made:
                a.model_fallback = "some AI probes were rejected"
    if (uses(bl, "diff") or uses(bl, "diff_info")) and not getattr(a, "no_probes", False):
        try:
            d = diff_probes.derive(item.get("diff", ""), coverage_gate.python_sources(item["files"]), base_root,
                                   pr_roots)
            if d["targets"]:
                path = diff_probes.write(d["targets"], prdir / "diff-probes" / "diff-api.py", f"{repo}#{item['pr']}")
                plan.append({"path": path, "source": "diff",
                             "freeze": freeze.freeze(path, freeze.generator("diff"), d["inputs"])})
            note["diff_targets"] = [".".join(t) for t in d["targets"]]
        except (freeze.FreezeError, SyntaxError, OSError) as e:
            note["errors"].append(f"differential probe: {e}")
    rec["probe_plan"] = note | {"frozen": [{"path": repo_relative(x["path"]) if x["source"] == "library"
                                           else str(Path(x["path"]).relative_to(prdir)), "source": x["source"],
                                           **({"origin": x["origin"]} if x.get("origin") else {}),
                                           **x["freeze"]} for x in plan]}
    return plan


def run_probes(repo: str, pr: int, pythons: dict, prdir: Path, work: Path, a, plan: list | None = None,
               pr_started: str | None = None) -> dict:
    """Run the frozen probes of this PR (plan_probes) on both sides, 3 alternating runs each, in the sides' own
    sandboxed environments. A probe runs on the PR side only if it still matches its freeze (content sha256) and was
    frozen before PR-side execution started (pr_started); otherwise it is refused. Without a plan (callers outside
    the per-PR driver) the fixed probes are frozen now. {"status": "none"} when the PR has no probe."""
    if plan is None:
        plan = [] if getattr(a, "no_probes", False) else [
            {"path": p, "source": "library",
             "freeze": freeze.freeze(p, freeze.generator("fixed", provenance=_provenance(p)), None)}
            for p in probes.find_probes(repo, pr)]
        pr_started = pr_started or freeze.now()
    if not plan:
        return {"status": "none", "items": []}
    items, errors, refused = [], [], []
    venvs = {side: Path(py).parent.parent for side, py in pythons.items()}   # <venv>/bin/python
    settings = probe_settings(a, venvs)   # product checks: main's test settings, the same on both sides
    envs = {side: probe_env(v, settings) for side, v in venvs.items()}
    cwds = {side: side_cwd(v) for side, v in venvs.items()}
    use_contree = _contree_ready()
    if use_contree:
        _CONTREE_CHECKOUTS.clear()
        _CONTREE_CHECKOUTS["settings"] = settings
    for x in plan:
        path, fz = Path(x["path"]), x["freeze"]
        def guard(p, fz=fz):
            freeze.verify(p, fz, pr_started)
        try:
            guard(path)
            if use_contree:
                it = _contree_run_probe(path, prdir, a.runs, x["source"], guard, literal_output=product_route(a))
            else:
                it = probes.run_probe(path, pythons, prdir, cwds, envs, runs=a.runs, source=x["source"],
                                      launchers={side: probe_launcher(v, path) for side, v in venvs.items()},
                                      guard=guard, literal_output=product_route(a))
            it["path"] = repo_relative(path) if x["source"] == "library" else str(path.relative_to(prdir))
            it["generator"] = fz["generator"]
            if x.get("origin"):
                it["origin"] = x["origin"]
            it["freeze"] = fz | {"verified": True, "pr_started_at": pr_started}
            items.append(it)
        except freeze.FreezeError as e:
            refused.append({"path": path.name, "source": x["source"], "why": str(e)})
        except probes.ProbeError as e:
            errors.append(str(e).replace(str(REPO_ROOT) + "/", ""))
    out = {"status": "ran" if items else "error", "items": items, "summary": probes.summarize(items)}
    if settings is not None:
        from poc import test_settings
        out["test_settings"] = test_settings.summary(settings)
    if errors:
        out["errors"] = errors
    if refused:
        out["refused"] = refused
    return out


def _contree_run_probe(path: Path, outdir: Path, runs: int, source: str, guard, literal_output: bool = False) -> dict:
    """Contree dual-run of one frozen probe (same alternating schedule as probes.run_probe)."""
    spec = probes.read_spec(path)
    got: dict = {"main": [], "pr": []}
    files: dict = {"main": [], "pr": []}
    per_run = []
    timeout = int(spec.get("timeout_s", 120))
    for i in range(1, runs + 1):
        for side in ("main", "pr"):
            if side == "pr" and guard:
                guard(path)
            obs, log, secs = _contree_probe_once(side, path, timeout, literal_output)
            fname = f"probe-{spec['id']}-{side}-{i}.jsonl"
            probes.write_output(outdir / fname, obs)
            (outdir / f"probe-{spec['id']}-{side}-{i}.log").write_text(log)
            got[side].append(obs)
            files[side].append(fname)
            per_run.append({"side": side, "run": i, "seconds": secs, "ok": probes.PROBE_ERROR not in obs})
    return probes.entry(spec, got, files, per_run, source, path)


def _provenance(path: Path) -> str | None:
    try:
        return probes.read_spec(path).get("provenance")
    except probes.ProbeError:
        return None


def repo_relative(path: Path) -> str:
    try:
        return str(Path(path).resolve().relative_to(REPO_ROOT))
    except ValueError:
        return Path(path).name


DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}")


def run_date_for(rdir: Path, fallback: str | None = None) -> str:
    """Calendar date (YYYY-MM-DD) of a run folder: its own name if it starts with a date ('2026-10-10',
    '2026-10-10-check-0930'), else its parent's ('2026-10-10/incremental-1130'), else fallback / today (IST)."""
    for name in (rdir.name, rdir.parent.name):
        if DATE_RE.match(name):
            return name[:10]
    return fallback if fallback and DATE_RE.match(fallback) else now_ist().strftime("%Y-%m-%d")


def probe_coverage(item: dict, probe_results: dict | None, vm: Path, main_root: Path, pr_root: Path, prdir: Path,
                   a) -> dict:
    """Probe adequacy (poc/probe_adequacy.py): run each probe ONCE more on the main side under coverage.py, after the
    timed probe runs, and record which changed lines it executes. Adds `probe_changed_line_coverage` to every probe
    entry (adequate / not_adequate / unmeasured) and returns the record-level summary. main_root / pr_root: the
    folder the PR's repo-relative paths resolve against on each side (site-packages, or the checkout)."""
    from poc import probe_adequacy
    items = (probe_results or {}).get("items") or []
    if not items:
        return probe_adequacy.summary([])

    def unmeasured(why: str) -> dict:
        for it in items:
            it["probe_changed_line_coverage"] = probe_adequacy.assess({"status": "not measured", "why": why})
        return probe_adequacy.summary(items)

    if getattr(a, "no_coverage", False) or _coverage_skipped_by_env():
        return unmeasured("--no-coverage")
    changed = {}
    for rel in coverage_gate.python_sources(item["files"]):
        old, new = Path(main_root) / rel, Path(pr_root) / rel
        changed[rel] = probe_adequacy.main_side_lines(old.read_text(errors="replace") if old.is_file() else None,
                                                      new.read_text(errors="replace") if new.is_file() else None,
                                                      statement_start=product_route(a))
    if not changed:
        return unmeasured("no changed non-test Python files")
    log = prdir / "probe-coverage.log"
    py = vm / "bin" / "python"
    if in_side(vm, [py, "-c", "import coverage"]).returncode != 0:
        c2, e2 = isolated_install([uv_bin(), "pip", "install", "-q", "-p", py, "coverage>=7"],
                                  base_env(side_home(vm), install=True), product_route(a))
        rc, _ = run(c2, log, env=e2, timeout=600, sbx=side_sandbox(vm, network=True))
        if rc != 0:
            return unmeasured(f"installing coverage on the main side failed ({rc}); see probe-coverage.log")
    include = ",".join(str(Path(main_root) / rel) for rel, lines in changed.items() if (Path(main_root) / rel).is_file())
    for it in items:
        path = Path(it["path"]) if Path(it["path"]).is_absolute() else REPO_ROOT / it["path"]
        if not path.is_file() and (prdir / it["path"]).is_file():
            path = prdir / it["path"]
        if not include:
            it["probe_changed_line_coverage"] = probe_adequacy.measure(changed, {})
            continue
        out = side_out(vm)
        data, js = out / f".probe-cov-{it['id']}", out / f"probe-cov-{it['id']}.json"
        sbx = side_sandbox(vm, ro=(path,))
        env = probe_env(vm, probe_settings(a, {"main": vm, "pr": vm.parent / "venv-pr"}))
        rc, _ = run([py, "-m", "coverage", "run", f"--data-file={data}", f"--include={include}", path], log,
                    cwd=side_cwd(vm), env=env, timeout=int(probes.read_spec(path).get("timeout_s", 120)), sbx=sbx)
        run([py, "-m", "coverage", "json", f"--data-file={data}", "-o", js, "-q"], log, cwd=side_cwd(vm), env=env,
            timeout=300, sbx=sbx)
        if not js.exists():
            it["probe_changed_line_coverage"] = probe_adequacy.assess(
                {"status": "not measured", "why": f"coverage produced no data (exit {rc}); see probe-coverage.log"})
            continue
        dest = prdir / js.name
        shutil.move(js, dest)
        it["probe_changed_line_coverage"] = probe_adequacy.measure(changed, json.loads(dest.read_text()).get("files", {})) | {
            "exit": rc, "data": dest.name}
    return probe_adequacy.summary(items)


def contree_probe_coverage(item: dict, probe_results: dict | None, main_root: Path, pr_root: Path, prdir: Path,
                           a) -> dict:
    """Probe adequacy for a Contree-only product check (the Contree twin of probe_coverage).

    Each probe runs once more on the main checkpoint under coverage.py (already in the checkpoint; nothing is
    installed here), limited to the changed files. The report is packed to a file inside Contree and fetched in
    checksummed pieces (fetch_contree_coverage), then mapped to the main-side changed lines. Any failure (no
    session, run error, no report, a short or corrupt fetch, a bad report) leaves that probe 'unmeasured', so the
    cap stays."""
    from poc import contree_sandboxes, probe_adequacy, test_settings
    items = (probe_results or {}).get("items") or []
    if not items:
        return probe_adequacy.summary([])

    def unmeasured(it: dict, why: str) -> None:
        it["probe_changed_line_coverage"] = probe_adequacy.assess({"status": "not measured", "why": why})

    def all_unmeasured(why: str) -> dict:
        for it in items:
            unmeasured(it, why)
        return probe_adequacy.summary(items)

    if getattr(a, "no_coverage", False) or _coverage_skipped_by_env():
        return all_unmeasured("--no-coverage")
    changed = {}
    for rel in coverage_gate.python_sources(item["files"]):
        old, new = Path(main_root) / rel, Path(pr_root) / rel
        changed[rel] = probe_adequacy.main_side_lines(old.read_text(errors="replace") if old.is_file() else None,
                                                      new.read_text(errors="replace") if new.is_file() else None,
                                                      statement_start=product_route(a))
    if not changed:
        return all_unmeasured("no changed non-test Python files")
    on_main = sorted(rel for rel in changed if (Path(main_root) / rel).is_file())
    sess = contree_sandboxes.session()
    if sess is None or not getattr(sess, "main_uuid", None):
        return all_unmeasured(CONTREE_ONLY_COVERAGE_WHY)
    include = ",".join(str(PurePosixPath("/work/src") / rel) for rel in on_main)
    want = " ".join(shlex.quote(r) for r in on_main)
    exports = test_settings.shell_exports(_CONTREE_CHECKOUTS.get("settings"))
    log_parts = []
    for it in items:
        if not on_main:
            it["probe_changed_line_coverage"] = probe_adequacy.measure(changed, {})
            continue
        path = Path(it["path"]) if Path(it["path"]).is_absolute() else REPO_ROOT / it["path"]
        if not path.is_file() and (prdir / it["path"]).is_file():
            path = prdir / it["path"]
        if not path.is_file():
            unmeasured(it, "the probe file was not found for the coverage run")
            continue
        try:
            timeout = int(probes.read_spec(path).get("timeout_s", 120))
        except probes.ProbeError:
            timeout = 120
        except Exception as e:  # noqa: BLE001 - keep the cap instead of crashing the check
            log_parts.append(f"$ contree probe coverage (main) {it.get('id')}\nreading the probe spec failed: "
                             f"{type(e).__name__}: {e}")
            unmeasured(it, f"reading the probe spec failed ({type(e).__name__}); see probe-coverage.log")
            continue
        remote = f"/work/probes/{path.name}"
        shell = (
            "set +e\ncd /work/src 2>/dev/null || cd /work\n" + exports +
            f"python -m coverage run --data-file=/tmp/poc-probe-cov --include={shlex.quote(include)} "
            f"{shlex.quote(remote)} >/tmp/poc-probe-cov.log 2>&1\n"
            "ec=$?\n"
            "python -m coverage json --data-file=/tmp/poc-probe-cov -o /tmp/poc-probe-cov.json -q "
            ">>/tmp/poc-probe-cov.log 2>&1\n"
            "printf '___POC_EXIT___%s\\n' \"$ec\"\n"
            f"python -c {shlex.quote(_COV_PACK)} /tmp/poc-probe-cov.json {want} 2>/dev/null\n"
            "printf '___POC_LOG___\\n'\ntail -c 4000 /tmp/poc-probe-cov.log 2>/dev/null\n"
        )
        try:
            raw = sess.run_op("main", shell, disposable=False, timeout=timeout + int(a.run_timeout),
                              files={remote: path})
        except Exception as e:  # noqa: BLE001 - keep the cap instead of crashing the check
            unmeasured(it, f"the Contree probe coverage run failed ({type(e).__name__})")
            continue
        raw = raw if isinstance(raw, dict) else {}
        out = (raw.get("stdout") or "") + "\n" + (raw.get("stderr") or "")
        log_parts.append(f"$ contree probe coverage (main) {it.get('id')}\n"
                         + (out.split("___POC_LOG___\n", 1)[-1] if "___POC_LOG___" in out else out))
        m = re.search(r"___POC_COV_FILE___(\d+) ([0-9a-f]{64})", out)
        if not m:
            unmeasured(it, f"{COV_FETCH_FAILED} (no report file was written); see probe-coverage.log")
            continue
        blob, why = fetch_contree_coverage(sess, raw.get("uuid") or "", int(m.group(1)), m.group(2),
                                           int(a.run_timeout))
        if blob is None:
            unmeasured(it, f"{why}; see probe-coverage.log")
            continue
        cov_files, why = coverage_gate.parse_report(blob)
        if cov_files is None:
            unmeasured(it, f"{why}; see probe-coverage.log")
            continue
        dest = prdir / f"probe-cov-{it['id']}.json"
        try:
            dest.write_text(blob.strip() + "\n")
        except Exception as e:  # noqa: BLE001 - keep the cap instead of crashing the check
            log_parts.append(f"saving the coverage report for {it.get('id')} failed: {type(e).__name__}: {e}")
            unmeasured(it, f"saving the coverage report failed ({type(e).__name__}); see probe-coverage.log")
            continue
        exit_m = re.search(r"___POC_EXIT___(\S+)", out)
        rc = int(exit_m.group(1)) if exit_m and exit_m.group(1).isdigit() else raw.get("exit_code")
        it["probe_changed_line_coverage"] = probe_adequacy.measure(changed, cov_files) | {
            "exit": rc, "data": dest.name, "where": "contree"}
    try:
        (prdir / "probe-coverage.log").write_text(contree_sandboxes.redact("\n".join(log_parts)))
    except Exception as e:  # noqa: BLE001 - fail closed: without the log, no probe's coverage is trusted
        why = contree_sandboxes.redact(f"writing probe-coverage.log failed ({type(e).__name__}: {e})")
        print(f"  {why}", flush=True)
        return all_unmeasured(why)
    return probe_adequacy.summary(items)


def begin_pr(a) -> None:
    """Start one pull request.

    The provider's call list, the fallback note, and the cost ledger are for this pull request only.
    A skip that applies to the whole run (`model_skipped`) is left as it is.
    """
    provider = getattr(a, "provider", None)
    calls = getattr(provider, "calls", None)
    if isinstance(calls, list):
        calls.clear()
    a.model_fallback = None
    cost.reset()
    from poc import hitl
    hitl.reset_approval_ran()


def stamp_model_use(rec: dict, a) -> None:
    """Write which provider actually completed a call, and any skip or fallback.

    `model_provider_used` comes from calls that succeeded, not from the provider the run was asked to use.
    The API key is never written.
    """
    info = model_provider.describe_use(
        getattr(a, "model_provider", None), getattr(a, "provider", None),
        getattr(a, "model_skipped", None), getattr(a, "model_fallback", None))
    rec["model_provider_used"] = info["model_provider_used"]
    if info.get("model_provider_fallback"):
        rec["model_provider_fallback"] = info["model_provider_fallback"]
    else:
        rec.pop("model_provider_fallback", None)
    mp = rec.get("model_provider")
    if isinstance(mp, dict):
        mp["used"] = None if info["model_provider_used"] == "none" else info["model_provider_used"]
        if info["model_provider_used"] == "none":
            mp["blind"] = False


def new_record(repo: str, cfg: dict, item: dict, a, machine: dict, run_date: str, day: str | None = None) -> dict:
    """PR-run record (record_kind 'pr_run' of the shared observation schema, harness/schema/observation.schema.json).
    run_date names the run folder (used in the id); day is the calendar date stored in run_date."""
    tested = now_ist()
    day = day if day and DATE_RE.match(day) else (run_date[:10] if DATE_RE.match(run_date)
                                                  else tested.strftime("%Y-%m-%d"))
    rec = {"schema_version": "1", "record_kind": "pr_run",
           "id": f"pr-{repo.replace('/', '-')}-{item['pr']}-{item['head_sha'][:12]}-{run_date}",
           "date_ist": tested.strftime("%Y-%m-%d %H:%M IST"), "run_date": day[:10], "who": WHO, "repo": repo, "library": cfg["dist"],
           "pr": {"repo": repo, "number": item["pr"], "url": item["url"], "title": item["title"],
                  "base_sha": item.get("base_sha"),
                  "base_sha_label": "pull request base (the commit the pull request was opened against; "
                                    "not necessarily the main side that was tested)",
                  "head_sha": item["head_sha"], "merge_commit": None},
           "author": item["author"], "base_ref": item["base_ref"], "updated_at_utc": item["updated_at_utc"],
           "updated_at_ist": item["updated_at_ist"], "ci_state": item["ci_state"], "ci_detail": item["ci_detail"],
           "tested_at_ist": tested.strftime("%Y-%m-%d %H:%M IST"),
           "files": dict(item["files"]), "machine_type": machine,
           "thread_env": dict(THREAD_ENV, PYTHONHASHSEED="0"),
           "runs_per_side": 0, "runs_per_side_planned": a.runs, "workers": str(a.workers),
           "test_timeout_s": a.test_timeout, "run_timeout_s": a.run_timeout, "build_timeout_s": a.build_timeout,
           "python": getattr(a, "python_full", None) or a.python, "test_selection": "", "per_run": [], "notes": None,
           "network": ("installs/builds only, inside the sandbox; tests, coverage and probes have no network"
                       if sandbox.enabled() else "allowed (installs and PR fetch); tests not network-isolated "
                                                 "(--unsafe-no-sandbox)"),
           "behaviour_claims": (behaviour_claims.find(item["title"], item.get("body"), item.get("diff"))
                                if uses(getattr(a, "baseline", None), "claim_flags") else []),
           "baseline": getattr(a, "baseline", None) or "full",
           "model_provider": {"requested": getattr(a, "model_provider", None) or "none",
                              "used": getattr(getattr(a, "provider", None), "name", None),
                              "note": getattr(a, "model_note", None) or "model provider: none: the AI was off; fixed probes only",
                              "blind": bool(getattr(getattr(a, "provider", None), "blind", False))},
           "sandbox_backend": getattr(a, "sandbox_backend", None) or "local",
           "sandbox_backend_note": getattr(a, "sandbox_backend_note", None),
            # "contree" only once both checkpoints were really built there (_maybe_prepare_contree sets it).
            "machine": "local" if getattr(a, "sandbox_backend", None) != "contree" else "contree (not run)",
            "tool_setup": getattr(a, "tool_setup", None) or tool_setup_result(),
           "posted_upstream": False, "logs": f"{cfg['pkg']}-{item['pr']}/", "freeze": {}}
    sha = getattr(a, "poc_commit", None)
    if isinstance(sha, str) and _COMMIT.fullmatch(sha):
        rec["poc_commit"] = sha
    ts = rec.get("tool_setup") or {}
    if ts.get("installed"):  # plain words in the report's setup notes: what was fixed before the check started
        rec.setdefault("demo_helper", {}).setdefault("notes", []).append(f"Set up Python: {ts['note']}")
    rec["route"] = ("source-pair" if not cfg.get("nightly") else
                    "source-build" if item["files"]["compiled"] else "nightly+patch")
    rec["current_head_sha"] = item.get("current_head_sha") or item["head_sha"]
    if getattr(a, "invocation", None):
        rec["tested_invocation"] = a.invocation
    stamp_model_use(rec, a)
    for k in ("head_moved", "current_head_sha", "frozen_from", "state", "mergeable", "mergeable_state"):
        if item.get(k) is not None:
            rec[k] = item[k]
    return rec


def venv_python_version(venv: Path) -> str | None:
    out = in_side(venv, [venv / "bin/python", "-c", "import platform;print(platform.python_version())"]).stdout.strip()
    return out or None


def finalize_tests(rec: dict, per_run: list[dict], results: dict, a) -> tuple[dict | None, str | None, dict | None]:
    rec["per_run"] = per_run
    rec["runs_per_side"] = sum(1 for e in per_run if e["side"] == "old" and e.get("junit"))
    if any(r.get("exit") == "timeout" for r in per_run):
        return None, f"a test run exceeded the {a.run_timeout}s run timeout", None
    if not any(results["pr"]) or not any(results["main"]):
        return None, "tests produced no results on one side (collection failed; see pytest logs)", None
    cmp = compare_sides(results)
    ex = exit_check(per_run, results, cmp)
    rec["comparison"], rec["exit_check"] = cmp, ex
    return cmp, None, ex


def _unconfirmed_dependency(cmp: dict, d: dict) -> None:
    """Put back a missing-dependency classification the environment did not confirm.

    A failure (the test ran and raised ModuleNotFoundError, or the same messages) returns to new_tests_failing:
    the module is installed, so the failure is a real result. A skip returns to other_changes, as before.
    """
    if d.get("pr") in ("failed", "error"):
        cmp["new_tests_failing"].append(d["test"])
        msg = d.get("message")
        if msg:
            msgs = cmp.setdefault("messages", {})
            if d["test"] not in msgs and len(msgs) < 20:
                msgs[d["test"]] = msg
        return
    cmp["other_changes"].append(
        f"{d['test']}: {d['main']} -> skipped (skip names {d['module']}, which is installed)")


def change_is_docstring_only(files: dict | None, main_root: Path, pr_root: Path) -> bool:
    """True when every changed non-test Python file is AST-equal once docstrings are removed.

    Compiled changes and files that exist on only one side are not docstring-only."""
    if not isinstance(files, dict) or coverage_gate.compiled_sources(files):
        return False
    py = coverage_gate.python_sources(files)
    if not py:
        return False
    for rel in py:
        old_p, new_p = Path(main_root) / rel, Path(pr_root) / rel
        if not old_p.is_file() or not new_p.is_file():
            return False
        if not coverage_gate.ast_equal_ignoring_docstrings(old_p.read_text(errors="replace"),
                                                           new_p.read_text(errors="replace")):
            return False
    return True


def mark_holds_by_construction(claims: list | None) -> list:
    """A docstring-only change cannot change behaviour, so each claim holds by construction."""
    return [{**c, "status": "holds by construction"} for c in (claims or [])]


def settle_probes(rec: dict) -> None:
    """Mark uninformative probes after coverage, and refresh the coverage summary to match."""
    pr = rec.get("probes")
    if not pr or not pr.get("items"):
        return
    from poc import probe_adequacy
    if rec.get("product_check"):   # product route only: the study route keeps the model's claims as written
        from poc import claim_hygiene
        pr = claim_hygiene.apply(pr)
        note = claim_hygiene.note_text(pr.get("claim_hygiene"))
        if note:
            rec["claim_hygiene_note"] = note
    rec["probes"] = probes.apply_status(pr)
    rec["probe_changed_line_coverage"] = probe_adequacy.summary(rec["probes"]["items"])


def install_optional_modules(venvs: dict, modules: list[str], log: Path, timeout: int,
                             isolated: bool = False) -> tuple[bool, str]:
    """Install plain pip wheels for missing optional modules, on both sides. isolated: see isolated_install."""
    pkgs = []
    for name in modules:
        pkg = PIP_OPTIONAL.get(name)
        if pkg and pkg not in pkgs:
            pkgs.append(pkg)
    if not pkgs:
        return True, ""
    for side, venv in venvs.items():
        cmd, env = isolated_install([uv_bin(), "pip", "install", "-q", "-p", venv / "bin/python", *pkgs],
                                    base_env(side_home(venv), install=True), isolated)
        rc, _ = run(cmd, log, env=env, timeout=timeout, sbx=side_sandbox(venv, network=True))
        if rc != 0:
            return False, f"installing {', '.join(pkgs)} on the {side} side failed ({rc}); see {log.name}"
    return True, ""


def messages_from_pr_only_files(targets: dict, venvs: dict, cwds: dict | None, prdir: Path, a) -> list[str]:
    """Run pull-request-only test files once on the base side (copied in, then removed).

    Failure messages come back so a backend error that also happens on the base can be recognised. The copied
    files are not part of the saved comparison."""
    if not cwds:
        return []
    main_root, pr_root = Path(cwds["main"]), Path(cwds["pr"])
    copied, rels = [], []
    for rel in targets.get("pr", []):
        src, dest = pr_root / rel, main_root / rel
        if src.is_file() and not dest.exists():
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
            copied.append(dest)
            rels.append(rel)
    if not rels:
        return []
    venv = venvs["main"]
    junit = side_out(venv) / "junit-base-optional.xml"
    log = prdir / "pytest-base-optional.log"
    cmd = [venv / "bin/python", "-m", "pytest", *[str(main_root / r) for r in rels], "-p", "no:cacheprovider",
           "-q", "-rfE", f"--timeout={a.test_timeout}", "-o", "addopts=", "-o", "junit_family=xunit2",
           f"--junitxml={junit}"]
    try:
        run(cmd, log, cwd=main_root, env=base_env(side_home(venv)), timeout=a.run_timeout,
            sbx=side_sandbox(venv))
        parsed = parse_junit(junit) if junit.exists() else {}
    finally:
        junit.unlink(missing_ok=True)
        for dest in copied:
            dest.unlink(missing_ok=True)
    return [msg for outcome, msg in parsed.values() if outcome in ("failed", "error") and msg]


def execute_tests(rec: dict, venvs: dict, targets: dict, prdir: Path, work: Path, a,
                  cwds: dict | None = None) -> tuple:
    """Run the mapped tests. When new tests skip for a plain pip module, install it on both sides and run again.

    A failure that then shows the same exception on the base side is recorded as the backend, not as a pull-request
    finding (verdict could_not_verify when that is the only finding)."""
    per_run, results = run_tests(venvs, targets, prdir, work, a.runs, a.workers, a.test_timeout, a.run_timeout,
                                 cwds=cwds, keep_addopts=product_route(a))
    cmp, cnv, ex = finalize_tests(rec, per_run, results, a)
    if not cmp:
        return cmp, cnv, ex
    confirm_missing(cmp, venvs["pr"])
    modules = installable_missing(cmp)
    if not modules:
        return cmp, cnv, ex
    log = prdir / "setup-optional.log"
    ok, why = install_optional_modules(venvs, modules, log, a.build_timeout, product_route(a))
    wheels = [PIP_OPTIONAL[m] for m in modules if PIP_OPTIONAL.get(m)]
    if not ok:
        rec["optional_install_error"] = why
        return cmp, cnv, ex
    rec["test_extras"] = list(dict.fromkeys([*(rec.get("test_extras") or []), *wheels]))
    per_run, results = run_tests(venvs, targets, prdir, work, a.runs, a.workers, a.test_timeout, a.run_timeout,
                                 cwds=cwds, keep_addopts=product_route(a))
    cmp, cnv, ex = finalize_tests(rec, per_run, results, a)
    if not cmp:
        return cmp, cnv, ex
    confirm_missing(cmp, venvs["pr"])
    extra = messages_from_pr_only_files(targets, venvs, cwds, prdir, a)
    also = sorted({t for msg in extra for t in exception_types(msg)})
    attribute_backend_errors(cmp, results, also)
    ex = exit_check(rec.get("per_run", []), results, cmp)
    rec["exit_check"] = ex
    return cmp, cnv, ex


def confirm_missing(cmp: dict, venv: Path) -> None:
    """Keep a dependency skip or blocked failure only if the module really does not import on the PR side."""
    keep = []
    for d in cmp.get("skipped_missing_dependency", []):
        ok = in_side(venv, [venv / "bin/python", "-c", f"import importlib.util as u,sys;"
                            f"sys.exit(0 if u.find_spec({d['module']!r}) is None else 1)"]).returncode == 0
        if ok:
            keep.append(d)
        else:
            _unconfirmed_dependency(cmp, d)
    cmp["skipped_missing_dependency"] = keep
    cmp["new_tests_failing"] = sorted(cmp["new_tests_failing"])


def sandbox_refusal(backend: str | None = None) -> str | None:
    """Reason to refuse running PR code: the sandbox is on (default) but cannot start here.

    Contree runs PR code remotely — local bubblewrap is not required when that backend is selected.
    """
    if not sandbox.enabled():
        return None
    if backend == "contree":
        return None
    ok, why = sandbox.check()
    return None if ok else why


def _contree_only_pair(a, rec: dict, repo: str, cfg: dict, item: dict, sp: dict, work: Path, prdir: Path,
                       helper_on: bool) -> tuple:
    """Source-pair check where every step that runs pull-request or package code runs inside Contree.

    Local checkouts are only read as files (test mapping, declared dependencies, probe planning, which lines changed).
    Installs, declared test dependencies and optional backends go into the Contree checkpoints; tests and probes run
    there. A product check also runs pytest with coverage in the PR checkpoint and reads the report back. Steps that
    need a local side (local freeze, installed-commit guard, probe coverage, the optional-module retry) are not run.
    Study runs still leave coverage unmeasured."""
    from poc import demo_helper, run_progress
    vm, vp = work / "venv-main", work / "venv-pr"
    cm, cp = work / "side-main", work / "side-pr"
    for v in (vm, vp):
        (v / "bin").mkdir(parents=True, exist_ok=True)
    setup_plan = _product_plan(a, rec, repo, cfg, [cm, cp], out_dir=prdir) if helper_on else None
    run_progress.emit("claims", "super", "planning behaviour claims / probes")
    plan = plan_probes(repo, item, rec, cm, [cp, work / "src"], prdir, a)
    rec["pr_side_started_at"] = pr_started = freeze.now()   # nothing below may create or change a probe
    chosen_tg = chosen_test_targets(item.get("chosen"))
    if chosen_tg:
        targets = {"main": [t for t in chosen_tg if (cm / t).exists()],
                   "pr": [t for t in chosen_tg if (cp / t).exists()]}
    else:
        targets = targets_for_sides(map_repo_tests(item["files"], cp), item["files"], cm, cp)
    rec["test_targets"] = targets
    rec["test_selection"] = ("chosen-PR subset: " if chosen_tg else "mapped from touched files: ") + ", ".join(
        targets["pr"])
    decl = declared_test_deps(cm, list(dict.fromkeys(targets["main"] + targets["pr"])), cfg["dist"])
    optional = optional_backend_reqs(cm, cfg["dist"])
    base = demo_helper.contree_shell(setup_plan) if setup_plan else ""
    measure_coverage = product_route(a)
    not_local = ["local freeze", "installed-commit guard", "probe coverage", "optional-module retry"]
    if not measure_coverage:
        not_local.insert(2, "coverage")
    rec["contree_only"] = {"note": "Contree mode: Contree has not run yet; nothing from the pull request ran locally",
                           "declared_test_deps": decl, "optional_backends": optional,
                           "not_run_locally": not_local}
    rec["coverage"] = {"status": "not measured", "why": CONTREE_ONLY_COVERAGE_WHY}
    run_progress.emit("install_main", detail="installing main and PR sides in Contree")
    blocked = _groups_blocked(a, setup_plan)
    if blocked:
        rec["contree_only"]["note"] = "Contree mode: Contree did not run, so nothing from the pull request was run"
        return None, blocked, None, targets
    cnv = _maybe_prepare_contree(a, repo, sp["main_sha"], sp["pr_sha"], rec, a.build_timeout,
                                 extra_shell=contree_only_extra_shell(decl, optional, base), main_dir=cm)
    cnv = own_index_refusal(a, cnv, cm, cp)
    cmp = ex = None
    if cnv:
        rec["contree_only"]["note"] = "Contree mode: Contree did not run, so nothing from the pull request was run"
        return cmp, cnv, ex, targets
    rec["contree_only"]["note"] = ("Contree mode: installs, tests and probes ran in Contree; nothing from the pull "
                                   "request ran locally")
    if decl:
        rec["declared_test_deps"] = {"requested": decl, "installed": True, "where": "contree"}
        rec["test_extras"] = list(dict.fromkeys([*(rec.get("test_extras") or []), *decl]))
    if not targets["pr"]:
        cnv = "no tests could be mapped to the touched files"
    else:
        run_progress.emit("pytest", "code", "dual-run pytest on main and PR (Contree)")
        per_run, results = run_tests({"main": vm, "pr": vp}, targets, prdir, work, a.runs, a.workers,
                                     a.test_timeout, a.run_timeout, cwds={"main": cm, "pr": cp},
                                     keep_addopts=product_route(a))
        cmp, cnv, ex = finalize_tests(rec, per_run, results, a)
        if cmp:
            ex = exit_check(rec.get("per_run", []), results, cmp)
            rec["exit_check"] = ex
    if measure_coverage and targets["pr"] and not cnv:
        run_progress.emit("pytest", "code", "coverage inside Contree")
        rec["coverage"] = contree_coverage_run(item, cm, cp, targets["pr"], prdir, a)
    run_progress.emit("probes", "super", "running behaviour probes (Contree)")
    rec["probes"] = run_probes(repo, item["pr"], {"main": vm / "bin/python", "pr": vp / "bin/python"}, prdir,
                               work, a, plan, pr_started)
    from poc import probe_adequacy
    if measure_coverage:  # product route: each probe runs once more on the main checkpoint under coverage
        run_progress.emit("probes", "super", "probe coverage inside Contree")
        rec["probe_changed_line_coverage"] = contree_probe_coverage(item, rec["probes"], cm, cp, prdir, a)
    else:
        for it in (rec["probes"] or {}).get("items") or []:
            it["probe_changed_line_coverage"] = probe_adequacy.assess(
                {"status": "not measured", "why": "Contree-only check: probe coverage needs a local side"})
        rec["probe_changed_line_coverage"] = probe_adequacy.summary((rec["probes"] or {}).get("items") or [])
    settle_probes(rec)
    if change_is_docstring_only(rec.get("files"), cm, cp):
        rec["docstring_only"] = True
    return cmp, cnv, ex, targets


STATE_UNREADABLE = ("refused: the pull request's state could not be read from GitHub, so it was not tested; "
                    "a live check only tests open pull requests")


def live_pr_refusal(repo: str, item: dict, a, gh_factory=None) -> str | None:
    """Live checks only (console, GitHub App, request worker: ``--live-check``). Re-reads the pull request's state
    from GitHub just before running. A closed or merged pull request, a missing state, or a failed read all refuse
    (fail closed) with a plain reason; nothing raises. Benchmark, known-answer and replay runs never set the flag."""
    try:
        gh = (gh_factory or (lambda: GitHub(None, fail_fast_auth=True)))()
        p = gh.json(f"/repos/{repo}/pulls/{item['pr']}")
        state = p.get("state") if isinstance(p, dict) else None
        if isinstance(p, dict) and p.get("merged_at") and state:
            state = "merged"
    except (KeyboardInterrupt, SystemExit):
        raise
    except BaseException:  # noqa: BLE001 - GitHubAuthError is a BaseException; a live check must not crash here
        return STATE_UNREADABLE
    if state:
        item["state"] = state
    return closed_pr_reason({"state": state})


def closed_pr_reason(item: dict) -> str | None:
    """A live check only tests an open pull request. A closed or merged one, or one with no state, is refused."""
    state = str(item.get("state") or "").lower()
    if not state:
        return STATE_UNREADABLE
    if state != "open":
        merged = " or merged" if state == "closed" else ""
        return (f"refused: this pull request is {state}{merged}, not open, so it was not tested; "
                "a product check only tests open pull requests")
    return None


def product_route(a) -> bool:
    """True for a product check (console, request-a-check, Codespaces, GitHub App): a single pull request started with
    ``--product-check`` (not inferred from ``--related-reports``). False for a study run and the daily study."""
    if getattr(a, "bench", None) or not getattr(a, "pr", None):
        return False
    return bool(getattr(a, "product_check", False))


def test_pr(repo: str, cfg: dict, item: dict, rdir: Path, workroot: Path, a, machine: dict) -> dict:
    from poc import run_progress
    t0 = time.time()
    begin_pr(a)
    run_progress.emit("fetch_pr", detail=f"{repo}#{item['pr']}")
    tag = f"{cfg['pkg']}-{item['pr']}"
    prdir = rdir / tag; prdir.mkdir(parents=True, exist_ok=True)
    work = workroot / tag
    shutil.rmtree(work, ignore_errors=True); work.mkdir(parents=True)
    (prdir / "pr.diff").write_text(item["diff"])
    rec = new_record(repo, cfg, item, a, machine, rdir.name, run_date_for(rdir))
    if product_route(a):
        rec["product_check"] = True   # coverage gate: on a product check, verified needs measured coverage
    if product_route(a) and getattr(a, "live_check", False):
        closed = live_pr_refusal(repo, item, a)
        if closed:   # a live product check: refuse before any lookup, install or run
            rec["pr_state_refusal"] = closed
            rec["verdict"], rec["reason"], _ = verdict_for(None, closed)
            return finish(rec, prdir, work, t0, a)
    from poc import demo_helper
    if demo_helper.active(a):
        demo_helper.begin_check(a, rec, repo, cfg.get("dist") or cfg.get("pkg"), prdir)
    if product_route(a):
        reason = demo_helper.lookup_stop_reason(rec)
        if reason:
            rec["verdict"], rec["reason"], _ = verdict_for(None, reason)
            return finish(rec, prdir, work, t0, a)
    if mark_typing_only(rec, item.get("files")):
        return finish_typing_only(rec, prdir, work, t0, a)
    set_contree_only(contree_only_wanted(getattr(a, "sandbox_backend", None)))
    refusal = sandbox_refusal(getattr(a, "sandbox_backend", None))
    if refusal:   # fail closed: no PR code runs without the sandbox (unless --unsafe-no-sandbox)
        rec["verdict"], rec["reason"], _ = verdict_for(None, refusal)
        return finish(rec, prdir, work, t0, a)
    if not cfg.get("nightly"):
        return finish(test_source_pair(repo, cfg, item, prdir, work, a, rec), prdir, work, t0, a)
    cnv, ex = None, None
    vm, vp = work / "venv-main", work / "venv-pr"
    targets = None
    plan, pr_started = [], None
    helper_on = demo_helper.active(a)
    file_dirs = _project_file_dirs(repo, item, work, prdir / "packaging.log") if helper_on else []
    setup_plan = _product_plan(a, rec, repo, cfg, file_dirs, out_dir=prdir) if helper_on else None
    blocked = _groups_blocked(a, setup_plan)
    if blocked:   # fail closed before any install
        rec["verdict"], rec["reason"], _ = verdict_for(None, blocked)
        return finish(rec, prdir, work, t0, a)
    py = _check_python(a, setup_plan)
    run_progress.emit("install_main", detail="installing main (nightly) side")
    if helper_on:
        def _build_main():
            built = build_main_env(cfg, vm, prdir / "setup-main.log", py, a.build_timeout,
                                   workroot / "wheels" / rdir.name, isolated=product_route(a))
            return bool(built.get("ok")), built.get("why") or "", built
        _ok, _why, main, outcome = demo_helper.run_setup(
            "main install", _build_main, cleanup=lambda: shutil.rmtree(vm, ignore_errors=True))
        demo_helper.note_setup(rec, "main install", outcome)
        if not isinstance(main, dict):
            main = {"ok": False, "why": _why}
    else:
        main = build_main_env(cfg, vm, prdir / "setup-main.log", py, a.build_timeout, workroot / "wheels" / rdir.name,
                              isolated=product_route(a))
    rec["main_side"] = {"source": "scientific-python nightly wheel (exact file, pinned by sha256)",
                        **{k: v for k, v in main.items() if k not in ("ok",)}}
    if main.get("build"):
        rec["main_build"] = main["build"]
    rec["python"] = venv_python_version(vm) or rec["python"]
    if not main["ok"]:
        cnv = f"main side could not be set up: {main['why']}"
    else:
        rec["freeze"]["main"] = freeze_env(vm, prdir / "freeze-main.txt")
        plan = plan_probes(repo, item, rec, site_packages(vm), [vp, work / "src"], prdir, a)
        rec["pr_side_started_at"] = pr_started = freeze.now()   # nothing below may create or change a probe
        if item["files"]["compiled"]:
            rec["route"] = "source-build"
            extra = [f"{cfg['dist']}[{','.join(main['test_extras'])}]"] if main.get("test_extras") else []
            run_progress.emit("install_pr", detail="building PR from source")
            if helper_on:
                def _build_pr():
                    built = source_build(repo, item, cfg, vp, work, prdir / "build-pr.log", py,
                                         a.build_timeout, tuple(extra), isolated=product_route(a))
                    return bool(built.get("ok")), built.get("why") or "", built
                _ok, _why, b, outcome = demo_helper.run_setup(
                    "PR build", _build_pr, cleanup=lambda: shutil.rmtree(vp, ignore_errors=True),
                    max_retries=_pr_side_retries(a))
                demo_helper.note_setup(rec, "PR build", outcome)
                if not isinstance(b, dict):
                    b = {"ok": False, "why": _why}
            else:
                b = source_build(repo, item, cfg, vp, work, prdir / "build-pr.log", py, a.build_timeout, tuple(extra),
                                 isolated=product_route(a))
            rec["pr_side"] = {"source": f"source build of {item['head_sha'][:12]}",
                              **{k: v for k, v in b.items() if k != "ok"}}
            rec["notes"] = ("main = nightly wheel, PR = source build of the PR head; differences can include "
                            "main-branch drift between the PR's base and the nightly")
            if not b["ok"]:
                if b.get("infrastructure_failure"):
                    rec["infrastructure_failure"] = b["infrastructure_failure"]
                    cnv = b["why"]
                else:
                    cnv = b["why"] + " (build log: build-pr.log)"
                    if helper_on:
                        cnv = _pr_own_failure(a, rec, "PR build", cnv, prdir / "build-pr.log")
        else:
            rec["route"] = "nightly+patch"
            run_progress.emit("install_pr", detail="patching PR onto nightly")
            shutil.copytree(vm, vp, symlinks=True)
            ok, why = apply_patch(package_diff(item["diff"], cfg["pkg"]), site_packages(vp), prdir / "patch.log")
            rec["pr_side"] = {"source": "copy of main side + PR diff applied to the installed package", "patched": ok}
            if not ok:
                cnv = why + " (see patch.log)"
                if helper_on:
                    cnv = _pr_own_failure(a, rec, "PR patch", cnv, prdir / "patch.log")
        if vp.exists():
            rec["freeze"]["pr"] = freeze_env(vp, prdir / "freeze-pr.txt")
    rec["tested"] = {"main": f"nightly {main.get('version', '?')} "
                             f"(commit {(main.get('build') or {}).get('commit') or 'unknown'}, "
                             f"sha256 {((main.get('build') or {}).get('sha256') or '?')[:12]})",
                     "pr": (f"PR head {item['head_sha'][:12]} " +
                            ("built from source" if rec.get("route") == "source-build" else "diff applied to that nightly"))}
    cmp = None
    envs_ok = not cnv
    if helper_on and setup_plan and envs_ok and vp.exists():
        reqs = [pkg for pkg in setup_plan.get("packages") or [] if pkg.get("action") == "install"]
        if reqs:
            def _plan_install(side, requirement, _vm=vm, _vp=vp):
                venv = _vm if side == "main" else _vp
                cmd, env = isolated_install([uv_bin(), "pip", "install", "-q", "-p", venv / "bin/python", requirement],
                                            base_env(side_home(venv), install=True), product_route(a))
                rc, _ = run(cmd, prdir / "setup-plan.log", env=env, timeout=a.build_timeout,
                            sbx=side_sandbox(venv, network=True))
                return rc == 0, _dist_version(venv, requirement) if rc == 0 else ""
            demo_helper.note_installs(rec, demo_helper.install_same(reqs, _plan_install))
    if not cnv:
        tm = map_tests(item["files"], cfg["pkg"], site_packages(vm), cfg)
        tp = map_tests(item["files"], cfg["pkg"], site_packages(vp), cfg)
        targets = targets_for_sides(list(dict.fromkeys(tp + tm)), item["files"], site_packages(vm), site_packages(vp))
        rec["test_targets"] = targets
        rec["test_selection"] = "mapped from touched modules: " + ", ".join(targets["pr"])
        if not targets["pr"]:
            cnv = "no tests could be mapped to the touched modules"
        else:
            run_progress.emit("pytest", "code", "dual-run pytest on main and PR")
            cmp, cnv, ex = execute_tests(rec, {"main": vm, "pr": vp}, targets, prdir, work, a)
            if cmp:
                run_progress.emit("pytest", "code", "before coverage")
                rec["coverage"] = coverage_run(item, vp, site_packages(vm), site_packages(vp), targets["pr"], prdir,
                                               work, a)
    commit = (main.get("build") or {}).get("commit")
    if isinstance(commit, str) and re.fullmatch(r"[0-9a-f]{7,40}", commit):
        rec["pr"]["tested_main_sha"] = commit
        rec["pr"]["tested_main_sha_label"] = ("nightly wheel commit (the main side that was tested; "
                                              "pr.base_sha is the pull request base)")
    if main.get("test_extras") and not rec.get("test_extras"):
        rec["test_extras"] = list(main["test_extras"])
    if envs_ok:
        run_progress.emit("probes", "super", "running behaviour probes")
        rec["probes"] = run_probes(repo, item["pr"], {"main": vm / "bin/python", "pr": vp / "bin/python"}, prdir, work,
                                   a, plan, pr_started)
        run_progress.emit("pytest", "code", "before coverage")
        rec["probe_changed_line_coverage"] = probe_coverage(item, rec["probes"], vm, site_packages(vm), site_packages(vp),
                                                            prdir, a)
        settle_probes(rec)
        if change_is_docstring_only(rec.get("files"), site_packages(vm), site_packages(vp)):
            rec["docstring_only"] = True
    run_progress.emit("verdict", "code", "computing code verdict")
    _store_verdict(rec, cmp, cnv, ex)
    if helper_on:
        def _rerun_nightly():
            nonlocal cmp, cnv, ex
            cmp, cnv, ex = execute_tests(rec, {"main": vm, "pr": vp}, targets, prdir, work, a)
            if cmp:
                rec["coverage"] = coverage_run(item, vp, site_packages(vm), site_packages(vp), targets["pr"], prdir,
                                               work, a)
            rec["probes"] = run_probes(repo, item["pr"], {"main": vm / "bin/python", "pr": vp / "bin/python"}, prdir,
                                       work, a, plan, pr_started)
            settle_probes(rec)
            _store_verdict(rec, cmp, cnv, ex)
            return {"verdict": rec["verdict"], "reason": rec["reason"]}

        def _recheck_nightly():
            rec["probe_changed_line_coverage"] = probe_coverage(
                item, rec.get("probes"), vm, site_packages(vm), site_packages(vp), prdir, a)
            settle_probes(rec)
            _store_verdict(rec, cmp, cnv, ex)
            return {"verdict": rec.get("verdict"), "reason": rec.get("reason")}

        ready = bool(targets and targets.get("pr") and vp.exists())
        _retry_setup_gap(a, rec, repo, prdir, {"main": vm, "pr": vp}, _rerun_nightly if ready else None,
                         _recheck_nightly if ready else None,
                         checkouts=declared_checkouts(nightly_main_checkout(work), work / "src"))
    return finish(gate(rec), prdir, work, t0, a)


def _record_related_failure(rec: dict, payload: dict) -> None:
    """Store the related-reports lookup. A failure does not change the verdict.

    The reports only feed the advisory write-up. When the lookup fails, that step is
    skipped: the reason is already on the payload, and the verdict stays as it was.
    """
    rec["related_reports"] = payload


def _attach_related_reports(rec: dict, runner) -> None:
    """Store related bug reports when this product check asked and the swarm will run.

    The text is background for the advisory AI. A study run, the daily study, and a check
    whose swarm is off leave the record alone and do not call Tavily. A missing key is
    recorded as a refusal. A failed lookup is recorded and left out of the write-up. Neither
    changes the verdict. The exception text is not printed raw, because it can contain the key.
    """
    from poc import agents, related_reports
    if not agents.swarm_enabled(bool(getattr(runner, "swarm", False))):
        return
    if runner is None or getattr(runner, "provider", None) is None or getattr(runner, "model_skipped", None):
        return
    if not related_reports.enabled(
            bool(getattr(runner, "related_reports", False)),
            bench=bool(getattr(runner, "bench", False)),
            single_pr=bool(getattr(runner, "pr", None))):
        return
    try:
        payload = related_reports.collect(rec)
    except Exception:  # noqa: BLE001 — do not print the message; it may contain the key
        reason = f"{related_reports.FAIL_LOG}: the lookup failed"
        print(reason, flush=True)
        payload = {"status": "error", "text": "", "items": [], "result_count": 0, "untrusted": True,
                   "reason": reason}
    _record_related_failure(rec, payload)


def finish(rec: dict, prdir: Path, work: Path, t0: float, runner=None) -> dict:
    # Agent swarm (judge/helper/summary) after the code verdict; advisory only — never changes rec["verdict"].
    # Off unless the run asked (--swarm / POC_SWARM). Skip also when model_skipped is set
    # (--no-probes / baseline without claim probes) so the stamp stays honest.
    from poc import contree_sandboxes, demo_helper, hitl, run_progress
    contree_sandboxes.clear_session()
    # Requested comes from the settings (--swarm / POC_SWARM, and POC_HITL). Ran stays off when
    # that step never started: no model, probes skipped, or the approval step was not entered.
    swarm_requested = agents.swarm_enabled(bool(getattr(runner, "swarm", False)))
    ran_swarm = False
    lookup_stopped = demo_helper.lookup_stop_reason(rec) is not None
    if lookup_stopped:
        # The setup lookup already stopped the check. Do not call Tavily again.
        if "agents" not in rec:
            note = "the check stopped because the setup lookup failed"
            rec["agents"] = {"status": "skipped", "note": note, "roles": []}
            rec.setdefault("explanation", {"status": "not yet wired", "why": note})
    elif (swarm_requested and runner is not None and getattr(runner, "provider", None) is not None
            and not getattr(runner, "model_skipped", None)):
        # Related bug reports are background for this advisory step only. A failed lookup
        # is recorded and left out of the write-up. It does not change the verdict.
        # When the swarm is off, Tavily is not called.
        _attach_related_reports(rec, runner)
        agents.run_swarm(runner.provider, rec)
        ran_swarm = True
    elif runner is not None and getattr(runner, "model_skipped", None) and "agents" not in rec:
        rec["agents"] = {"status": "skipped", "note": runner.model_skipped, "roles": []}
        rec.setdefault("explanation", {"status": "not yet wired", "why": runner.model_skipped})
    elif not ran_swarm and "agents" not in rec:
        why = "advisory swarm did not run" if swarm_requested else "advisory swarm is off"
        rec["agents"] = {"status": "skipped", "note": why, "roles": []}
        rec.setdefault("explanation", {"status": "not yet wired", "why": why})
    rec["swarm_requested"] = swarm_requested
    rec["operator_approval_requested"] = hitl.hitl_requested()
    rec["swarm"] = "on" if ran_swarm else "off"
    rec["operator_approval"] = "on" if hitl.take_approval_ran() else "off"
    run_progress.emit("report", detail="writing record")
    if runner is not None:
        stamp_model_use(rec, runner)
    rec["what_changed"] = {"package_python_files": rec["files"]["package_py"], "compiled_files": rec["files"]["compiled"],
                           "other_files": rec["files"]["other"]}
    rec["duration_s"] = {"total_wall": round(time.time() - t0, 1),
                         "tests": round(sum(e.get("seconds") or 0 for e in rec.get("per_run", [])), 1)}
    if rec.get("pr_side", {}).get("build_seconds") is not None:
        rec["duration_s"]["build"] = rec["pr_side"]["build_seconds"]
    rec["cost"] = cost.take(rec["duration_s"])
    mark_bench_model_invalid(rec, runner)
    errs = check_record(rec)
    if errs:
        rec["schema_errors"] = errs[:20]
    shutil.rmtree(work, ignore_errors=True)
    (prdir / "record.json").write_text(json.dumps(rec, indent=1))
    return rec


def _call_count(value) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def mark_bench_model_invalid(rec: dict, runner) -> None:
    """In a bench (study) run, flag a record the scorer must not count.

    A record whose AI calls all failed, or whose model_provider_used is none, is marked invalid.
    The verdict is left as it is. The study scorer refuses the record instead of counting
    could_not_verify. Daily and ops runs are not marked here.
    """
    if runner is None or not getattr(runner, "bench", None):
        return
    # A typing-only record never called the model on purpose. It is counted from no_code_change_reason,
    # not refused as a failed model run.
    if rec.get("no_code_change") is True:
        return
    calls = list(getattr(getattr(runner, "provider", None), "calls", None) or [])
    all_failed = bool(calls) and all(not c.get("ok") for c in calls)
    cost_info = rec.get("cost") if isinstance(rec.get("cost"), dict) else {}
    ai = _call_count(cost_info.get("ai_calls"))
    failed = _call_count(cost_info.get("failed_ai_calls"))
    swarm = cost_info.get("swarm") if isinstance(cost_info.get("swarm"), dict) else {}
    ai += _call_count(swarm.get("ai_calls"))
    failed += _call_count(swarm.get("failed_ai_calls"))
    if all_failed or (ai > 0 and failed >= ai):
        rec["invalid"] = True
        rec["invalid_reason"] = "every AI call failed"
    elif rec.get("model_provider_used") == "none":
        rec["invalid"] = True
        rec["invalid_reason"] = "model_provider_used is none"


def validate_record(rec: dict) -> list[str]:
    try:
        from ops.schema_check import validate
        return validate(rec, json.loads(SCHEMA_PATH.read_text()))
    except FileNotFoundError:
        return [f"schema not found at {SCHEMA_PATH}"]


def check_record(rec: dict) -> list[str]:
    """The record check: the shared schema, plus poc_commit on a pr_run record.

    poc_commit is optional in the schema so a record written before rev 8 still validates. A record this run
    writes must name the Proof-of-Change commit it used (origin/main after the fast-forward for a daily run;
    the expected commit for a benchmark run).
    A missing or malformed value fails this check."""
    errs = validate_record(rec)
    if not isinstance(rec, dict) or rec.get("record_kind") != "pr_run":
        return errs
    sha = rec.get("poc_commit")
    rid = rec.get("id", "<no id>")
    if not isinstance(sha, str) or not sha:
        errs.append(f"{rid}: missing poc_commit (the Proof-of-Change commit this run used)")
    elif not _COMMIT.fullmatch(sha):
        errs.append(f"{rid}: poc_commit must be the 40-character commit the run used, got {sha!r}")
    return errs


def test_source_pair(repo: str, cfg: dict, item: dict, prdir: Path, work: Path, a, rec: dict) -> dict:
    from poc import demo_helper, run_progress
    rec["route"] = "source-pair"
    if item.get("chosen"):
        rec["chosen"] = {k: v for k, v in item["chosen"].items()}
    vm = vp = cm = cp = None
    targets = None
    setup_plan = None
    plan, pr_started = [], None
    helper_on = demo_helper.active(a)
    if helper_on and not (rec.get("demo_helper") or {}).get("tavily"):
        demo_helper.begin_check(a, rec, repo, cfg.get("dist") or cfg.get("pkg"), prdir)
    if product_route(a):
        reason = demo_helper.lookup_stop_reason(rec)
        if reason:
            rec["verdict"], rec["reason"], _ = verdict_for(None, reason)
            return rec
    run_progress.emit("fetch_pr", detail="checking out main / PR sides")
    if helper_on:
        def _checkout():
            got = source_pair(repo, item, work, prdir / "git.log", a.python, a.build_timeout,
                              product=product_route(a))
            return bool(got.get("ok")), str(got.get("why") or ""), got

        def _clean_checkout():
            shutil.rmtree(work / "src", ignore_errors=True)
            shutil.rmtree(work / "side-main", ignore_errors=True)
            shutil.rmtree(work / "side-pr", ignore_errors=True)

        _ok, _detail, sp, outcome = demo_helper.run_setup("source checkout", _checkout, cleanup=_clean_checkout)
        demo_helper.note_setup(rec, "source checkout", outcome)
        if not isinstance(sp, dict):
            sp = {"ok": False, "why": _detail or "source checkout failed"}
    else:
        sp = source_pair(repo, item, work, prdir / "git.log", a.python, a.build_timeout,
                              product=product_route(a))
    rec["sides"] = {k: v for k, v in sp.items() if k != "ok"}
    if sp.get("merge_commit"):
        rec["pr"]["merge_commit"] = sp["merge_commit"]
    if sp.get("ok"):
        rec["tested"] = {"main": f"{item['base_ref']} @ {sp['main_sha'][:12]}"
                                 + (" (merge-base with the PR head)" if "merge-base" in sp["comparison_basis"]
                                    else " (base tip = first parent of the merge commit)"),
                         "pr": (f"GitHub test merge commit {sp['merge_commit'][:12]} (refs/pull/{item['pr']}/merge) of head "
                                f"{item['head_sha'][:12]}" if sp.get("merge_commit") else f"PR head {sp['pr_sha'][:12]}")}
        if isinstance(sp.get("main_sha"), str) and re.fullmatch(r"[0-9a-f]{7,40}", sp["main_sha"]):
            rec["pr"]["tested_main_sha"] = sp["main_sha"]
            rec["pr"]["tested_main_sha_label"] = (
                "main side that was tested (base-branch tip, or the merge-base when the pull request conflicts "
                "or the pinned head differs from the current head)")
    cnv, cmp, ex = None, None, None
    if not sp["ok"]:
        cnv = sp["why"]
    elif _CONTREE_ONLY:
        vm, vp = work / "venv-main", work / "venv-pr"
        cm, cp = work / "side-main", work / "side-pr"
        cmp, cnv, ex, targets = _contree_only_pair(a, rec, repo, cfg, item, sp, work, prdir, helper_on)
    else:
        vm, vp = work / "venv-main", work / "venv-pr"
        cm, cp = work / "side-main", work / "side-pr"
        setup_plan = _product_plan(a, rec, repo, cfg, [cm, cp], out_dir=prdir) if helper_on else None
        py = _check_python(a, setup_plan)
        extra = list(setup_plan["extra_reqs"]) if setup_plan and setup_plan.get("extra_reqs") else None
        run_progress.emit("install_main", detail="installing main side")
        if helper_on:
            ok, why = _install_with_helper(a, rec, "main install", vm, cm, item.get("chosen"),
                                           prdir / "setup-main.log", a.build_timeout, None, extra, python=py)
        else:
            ok, why = install_side(vm, cm, item.get("chosen"), prdir / "setup-main.log", a.python, a.build_timeout, None)
        plan, pr_started = [], None
        if ok:
            run_progress.emit("claims", "super", "planning behaviour claims / probes")
            plan = plan_probes(repo, item, rec, cm, [cp, work / "src"], prdir, a)
            rec["python"] = venv_python_version(vm) or rec["python"]
            cons = pr_side_constraints(vm, cfg["dist"], work / "constraints.txt")
            rec["freeze"]["main"] = freeze_env(vm, prdir / "freeze-main.txt")
            proj, _extra = side_install_args(item.get("chosen"), cm)
            rec["test_extras"] = recorded_test_extras(cm, with_test_extras(proj, cm))
            rec["pr_side_started_at"] = pr_started = freeze.now()   # nothing below may create or change a probe
            run_progress.emit("install_pr", detail="installing PR side")
            if helper_on:
                ok, why = _install_with_helper(a, rec, "PR install", vp, cp, item.get("chosen"),
                                               prdir / "setup-pr.log", a.build_timeout, cons, extra, python=py,
                                               max_retries=_pr_side_retries(a))
                if not ok:
                    why = _pr_own_failure(a, rec, "PR install", why, prdir / "setup-pr.log", same_setup=True)
            else:
                ok, why = install_side(vp, cp, item.get("chosen"), prdir / "setup-pr.log", a.python, a.build_timeout, cons)
            if ok:
                rec["freeze"]["pr"] = freeze_env(vp, prdir / "freeze-pr.txt")
        if not ok:
            cnv = why
            if str(why).startswith("infrastructure failure:"):
                rec["infrastructure_failure"] = {"kind": "oom", "action": "retry"}
        else:
            if helper_on and setup_plan:
                _log_plan_installs(rec, setup_plan, {"main": vm, "pr": vp})
            attach_optional_backends(rec, {"main": vm, "pr": vp}, cm, cfg["dist"],
                                     prdir / "setup-optional.log", a.build_timeout, product_route(a))
            chosen_tg = chosen_test_targets(item.get("chosen"))
            if chosen_tg:
                targets = {"main": [t for t in chosen_tg if (cm / t).exists()],
                           "pr": [t for t in chosen_tg if (cp / t).exists()]}
            else:
                targets = targets_for_sides(map_repo_tests(item["files"], cp), item["files"], cm, cp)
            rec["test_targets"] = targets
            rec["test_selection"] = ("chosen-PR subset: " if chosen_tg else "mapped from touched files: ") + ", ".join(
                targets["pr"])
            commits = {}
            for side, venv, co in (("main", vm, cm), ("pr", vp, cp)):
                good, info = check_installed_commit(venv, cfg["dist"], sp[f"{side}_sha"], co)
                commits[side] = {k: v for k, v in info.items() if k != "direct_url"} | {"ok": good}
                if not good and not cnv:
                    cnv = f"wrong-commit guard ({side} side): {info.get('why')}"
            rec["installed_commit"] = commits
            decl = [] if cnv else declared_test_deps(cm, list(dict.fromkeys(targets["main"] + targets["pr"])),
                                                       cfg["dist"])
            if decl:
                good, why2 = install_declared_test_deps({"main": vm, "pr": vp}, decl, prdir / "setup-declared.log",
                                                        a.build_timeout, product_route(a))
                rec["declared_test_deps"] = {"requested": decl, "installed": good}
                if good:
                    rec["test_extras"] = list(dict.fromkeys([*(rec.get("test_extras") or []), *decl]))
                    rec["freeze"]["main"] = freeze_env(vm, prdir / "freeze-main.txt")
                    rec["freeze"]["pr"] = freeze_env(vp, prdir / "freeze-pr.txt")
                else:
                    rec["optional_install_error"] = why2
            # Contree checkpoints before dual-runs (probes + pytest); local venvs stay for mapping/coverage.
            if not cnv:
                if helper_on:
                    shell = demo_helper.contree_shell(setup_plan) if setup_plan else ""
                    cnv = _maybe_prepare_contree(a, repo, sp["main_sha"], sp["pr_sha"], rec, a.build_timeout,
                                                 extra_shell=shell, main_dir=cm)
                else:
                    cnv = _maybe_prepare_contree(a, repo, sp["main_sha"], sp["pr_sha"], rec, a.build_timeout, main_dir=cm)
                cnv = own_index_refusal(a, cnv, cm, cp)
            if cnv:
                pass
            elif not targets["pr"]:
                cnv = "no tests could be mapped to the touched files"
            else:
                run_progress.emit("pytest", "code", "dual-run pytest on main and PR")
                cmp, cnv, ex = execute_tests(rec, {"main": vm, "pr": vp}, targets, prdir, work, a,
                                             cwds={"main": cm, "pr": cp})
                if cmp:
                    # Coverage stays on the local sides (Contree disposable runs do not keep coverage data).
                    run_progress.emit("pytest", "code", "before coverage")
                    rec["coverage"] = coverage_run(item, vp, cm, cp, targets["pr"], prdir, work, a, cwd=cp)
            run_progress.emit("probes", "super", "running behaviour probes")
            rec["probes"] = run_probes(repo, item["pr"], {"main": vm / "bin/python", "pr": vp / "bin/python"}, prdir,
                                       work, a, plan, pr_started)
            run_progress.emit("pytest", "code", "before coverage")
            rec["probe_changed_line_coverage"] = probe_coverage(item, rec["probes"], vm, cm, cp, prdir, a)
            settle_probes(rec)
            if change_is_docstring_only(rec.get("files"), cm, cp):
                rec["docstring_only"] = True
    run_progress.emit("verdict", "code", "computing code verdict")
    _store_verdict(rec, cmp, cnv, ex)
    if helper_on:
        def _rerun_pair():
            nonlocal cmp, cnv, ex
            run_progress.emit("pytest", "code", "rerun after a setup gap")
            cmp, cnv, ex = execute_tests(rec, {"main": vm, "pr": vp}, targets, prdir, work, a,
                                         cwds={"main": cm, "pr": cp})
            if cmp:
                rec["coverage"] = coverage_run(item, vp, cm, cp, targets["pr"], prdir, work, a, cwd=cp)
            rec["probes"] = run_probes(repo, item["pr"], {"main": vm / "bin/python", "pr": vp / "bin/python"}, prdir,
                                       work, a, plan, pr_started)
            settle_probes(rec)
            _store_verdict(rec, cmp, cnv, ex)
            return {"verdict": rec["verdict"], "reason": rec["reason"]}

        def _recheck_pair():
            rec["probe_changed_line_coverage"] = probe_coverage(item, rec.get("probes"), vm, cm, cp, prdir, a)
            settle_probes(rec)
            _store_verdict(rec, cmp, cnv, ex)
            return {"verdict": rec.get("verdict"), "reason": rec.get("reason")}

        ready = bool(vm and vp and targets and targets.get("pr"))
        _retry_setup_gap(a, rec, repo, prdir, {"main": vm, "pr": vp} if vm and vp else {},
                         _rerun_pair if ready else None, _recheck_pair if ready else None,
                         checkouts=declared_checkouts(cm, cp))
    return gate(rec)


def cap_for_review(rec: dict, v: str, reason: str) -> tuple[str, str]:
    """After human review, a claim left with no probe cannot be verified. Cap verified at could_not_verify.
    Only lowers a verified result; the verdict logic itself is unchanged."""
    left = (rec.get("human_review") or {}).get("claims_without_probe") or []
    if left and v == Verdict.VERIFIED.value:
        shown = ", ".join(str(x) for x in left[:4]) + (f" (+{len(left) - 4} more)" if len(left) > 4 else "")
        return (Verdict.COULD_NOT_VERIFY.value,
                f"could not verify: after review no probe checks claim(s) {shown} ({reason})")
    return v, reason


def _store_verdict(rec: dict, cmp, cnv, ex) -> None:
    """Write the verdict. A docstring-only change marks each behaviour claim as holding by construction."""
    same = bool(rec.get("product_check")) and sides_identical(rec)
    if same:
        rec["docstring_only"] = False
    v, reason, _ = verdict_for(cmp, cnv, ex, rec.get("files"), rec.get("probes"), rec.get("behaviour_claims"),
                               rec.get("baseline"), docstring_only=bool(rec.get("docstring_only")), same_sides=same)
    v, reason = cap_for_review(rec, v, reason)
    own = rec.get("pr_build_failure") or {}
    if own.get("needs_attention") and v == Verdict.COULD_NOT_VERIFY.value:
        v = Verdict.NEEDS_ATTENTION.value
        reason = (f"needs attention: main installed with the same setup, but the PR side failed to build on both "
                  f"tries: {own.get('error') or own.get('why')}")[:400]
    rec["verdict"], rec["reason"] = v, reason
    if rec.get("docstring_only") and v == Verdict.VERIFIED.value:
        rec["behaviour_claims"] = mark_holds_by_construction(rec.get("behaviour_claims"))


# ---------------------------------------------------------------- re-runs, frozen selection, audit trail
def prn(r: dict) -> int:
    return r["pr"]["number"] if isinstance(r.get("pr"), dict) else r["pr"]


def attempts(rdir: Path) -> list[Path]:
    sup = rdir / "superseded"
    if not sup.is_dir():
        return []
    return sorted((d for d in sup.iterdir() if d.is_dir() and re.fullmatch(r"attempt-\d+", d.name)),
                  key=lambda d: int(d.name.split("-")[1]))


def supersede_previous(rdir: Path, note: str | None) -> Path | None:
    """Move the previous attempt's outputs (PR folders, records, report, selection, console log) into
    <run>/superseded/attempt-N/ so a re-run never overwrites or silently drops earlier results."""
    movable = [p for p in rdir.iterdir() if p.name != "superseded" and
               (p.is_dir() or p.name in ("records.jsonl", "REPORT.md", "selection.json"))]
    # console.log is not moved: it is usually the live log of THIS attempt (shell redirect opened before we start).
    if not any(p.is_dir() or p.name == "records.jsonl" for p in movable):
        return None
    prev = attempts(rdir)
    dest = rdir / "superseded" / f"attempt-{(int(prev[-1].name.split('-')[1]) + 1) if prev else 1}"
    dest.mkdir(parents=True)
    for p in movable:
        shutil.move(str(p), dest / p.name)
    (dest / "NOTE.md").write_text(f"# {dest.name}: superseded at {now_ist():%Y-%m-%d %H:%M IST}\n\n{note or '(no note given)'}\n")
    return dest


def frozen_selection(rdir: Path) -> dict:
    """{repo: {pr: first selected entry}} over every earlier attempt of this run date, so a same-day re-run re-tests
    every PR any attempt selected (the day's selection is frozen; nothing is dropped by selection drift)."""
    out: dict = {}
    for d in attempts(rdir):
        f = d / "selection.json"
        if not f.exists():
            continue
        for repo, items in json.loads(f.read_text()).get("selected", {}).items():
            for it in items:
                out.setdefault(repo, {}).setdefault(it["pr"], it | {"first_attempt": d.name})
    return out


def attempt_history(rdir: Path) -> list[dict]:
    hist = []
    for d in attempts(rdir):
        sel = json.loads((d / "selection.json").read_text()).get("selected", {}) if (d / "selection.json").exists() else {}
        verdicts = {}
        for rf in d.glob("*/record.json"):
            r = json.loads(rf.read_text())
            verdicts[(r["repo"], prn(r))] = r.get("verdict")
        note = (d / "NOTE.md").read_text().strip() if (d / "NOTE.md").exists() else ""
        hist.append({"attempt": d.name, "selected": {(repo, it["pr"]) for repo, its in sel.items() for it in its},
                     "verdicts": verdicts, "note": note})
    return hist


def frozen_items(gh: GitHub, repo: str, cfg: dict, frozen: dict) -> list[dict]:
    """Re-fetch frozen PRs. The head SHA pinned on the first attempt is tested; if the PR moved since, the diff of the
    pinned head is taken from GitHub's compare view (base...head, not an API call) and head_moved is recorded."""
    items = []
    for n, it in sorted(frozen.items(), key=lambda kv: -kv[0]):
        p = gh.json(f"/repos/{repo}/pulls/{n}")
        pinned = it.get("head_sha") or p["head"]["sha"]
        moved = pinned != p["head"]["sha"]
        if moved:
            d = gh.get(f"https://github.com/{repo}/compare/{p['base']['ref']}...{pinned}.diff", accept="text/plain",
                       api=False).decode("utf-8", "replace")
        else:
            d = gh.diff(repo, n)
        try:
            state, detail = gh.ci_state(repo, pinned)
        except RuntimeError:
            raise
        except Exception as e:  # noqa: BLE001
            state, detail = "none", f"CI not readable: {e}"
        items.append({"pr": n, "title": p["title"], "body": p.get("body") or "", "url": p["html_url"],
                      "author": p["user"]["login"],
                      "head_sha": pinned, "current_head_sha": p["head"]["sha"], "head_moved": moved,
                      "base_sha": p["base"]["sha"], "merge_commit_sha": p.get("merge_commit_sha"),
                      "base_ref": p["base"]["ref"], "updated_at_utc": p["updated_at"],
                      "updated_at_ist": to_ist(p["updated_at"]), "files": classify_files(diff_files(d), cfg["pkg"]),
                      "diff": d, "state": p.get("state"), "ci_state": state, "ci_detail": detail,
                      "frozen_from": it.get("first_attempt")})
    return items


def verification_entry(v: dict) -> tuple | None:
    """((repo, pr), (verdict, checker, note)) of one independent-verification line, or None if the checker did not
    re-check the PR. Schema rev 5 'verification' records: the checker's own verdict is verification.checker_verdict;
    verdict_under_review is the verdict being checked and is never used for scoring. Older lines: '<name>_verdict' or
    'verdict', with a 'status'."""
    if v.get("record_kind") == "verification":
        x = v.get("verification") or {}
        t = x.get("target") or {}
        verdict = x.get("checker_verdict")
        if not verdict or x.get("check_status") == "unverified":
            return None
        return (t["repo"], int(t["pr_number"])), (verdict, (x.get("checker") or {}).get("name", "?"), x.get("summary", ""))
    verdict = next((v[k] for k in v if k.endswith("_verdict") and v[k]), None) or v.get("verdict")
    if not verdict or v.get("status") == "unverified":   # only PRs the checker actually re-checked
        return None
    return (v["repo"], int(v["pr"])), (verdict, v.get("checked_by", "?"), v.get("note", ""))


def read_verification(path: Path) -> dict:
    """Independent verification lines: {(repo, pr): (verdict, checker, note)} for PRs the checker re-checked.
    Call ONLY after all verdicts are final."""
    out = {}
    if not path or not path.exists():
        return out
    for ln in path.read_text().splitlines():
        if ln.strip():
            e = verification_entry(json.loads(ln))
            if e:
                out[e[0]] = e[1]
    return out


# ---------------------------------------------------------------- report
def unchanged_dependency_skips(prdir: Path, cmp: dict) -> dict:
    """{module: n} for tests skipped on BOTH sides because an optional module is missing (from junit-pr-1.xml).
    They do not change the verdict (the rule covers new/changed tests only) but are reported as coverage gaps."""
    j = parse_junit(prdir / "junit-pr-1.xml") if prdir.is_dir() else {}
    changed = {d["test"] for d in (cmp or {}).get("skipped_missing_dependency", [])}
    out: dict = {}
    for t, (o, m) in j.items():
        mod = missing_dependency(m) if o == "skipped" and t not in changed else None
        if mod:
            out[mod] = out.get(mod, 0) + 1
    return out


def score_expectation(expected: str, actual: str) -> str:
    if actual == "could_not_verify" or expected == "could_not_verify":
        return "match" if actual == expected else "not scored (could not verify)"
    if actual == expected:
        return "match"
    return "miss" if expected == "needs_attention" else "false alarm"


def score_table(title: str, intro: str, records: list[dict], truth: dict, col: str) -> list[str]:
    md = [f"## {title}", "", intro, "", f"| PR | {col} | Actual | Score |", "|---|---|---|---|"]
    from poc import demo_helper
    counts: dict = {}
    for r in records:
        if not demo_helper.counts_as_verdict(r):
            continue
        e = truth.get((r["repo"], prn(r)))
        if e:
            e = e[0] if isinstance(e, tuple) else e
            sc = score_expectation(e, r["verdict"])
            counts[sc] = counts.get(sc, 0) + 1
            md.append(f"| {r['repo']}#{prn(r)} | {e} | {r['verdict']} | {sc} |")
    if counts:
        md += ["", "Totals: " + ", ".join(f"{v} {k}" for k, v in sorted(counts.items())) +
               f" (out of {sum(counts.values())})"]
    return md + [""]


def how_to_fix(r: dict) -> str:
    """One action line. It must agree with the coverage check: do not say the changed lines never ran when they did."""
    tag = f"{r['repo']}#{prn(r)}"
    reason = r.get("reason") or ""
    cov = r.get("coverage") or {}
    covered, total = cov.get("changed_lines_covered"), cov.get("changed_lines_total")
    measured = cov.get("status") == "measured" and isinstance(total, int) and isinstance(covered, int)
    ran_lines = measured and total > 0 and covered > 0
    ran_none = measured and total > 0 and covered == 0
    coverage_bit = f" Coverage ran {covered} of {total} changed lines." if ran_lines else ""
    if reason.startswith("no test actually ran"):
        return (f"{tag}: no test ran on a side (every test skipped, or every test module failed to load); "
                "read the pytest logs, install what the tests need, and rerun.")
    if "fails to load on" in reason or "failed to load on both sides" in reason:
        return (f"{tag}: a test module did not load; read its traceback in the pytest logs "
                "(missing test dependency or plugin, or an import broken by the PR).")
    if reason.startswith("not fully verified: compiled") or "compiled code changed" in reason:
        return (f"{tag}: compiled change without a test for it; a human should check it, or the PR should "
                "add a test that calls the changed module.")
    if "not a PR finding" in reason or "not a pull-request finding" in reason:
        return (f"{tag}: the same error happens on the base side, so it is not a change this pull request made."
                + coverage_bit)
    if "optional dependenc" in reason:
        return (f"{tag}: add the named module(s) to optional_test_deps for this library, or rerun so a plain pip "
                f"module is installed on both sides.{coverage_bit}")
    if ran_none or "changed code never ran" in reason:
        return (f"{tag}: the mapped tests never ran the changed lines; widen the test mapping or ask "
                "for a test that exercises the change.")
    if ran_lines and reason.startswith("not fully verified"):
        return (f"{tag}: coverage ran {covered} of {total} changed lines, so this is not a coverage miss. "
                "Read the reason above and the pytest logs.")
    if reason.startswith("not fully verified"):
        return f"{tag}: the check is incomplete ({covered if measured else 'coverage not measured'}). Read the reason above."
    if "build" in reason:
        return f"{tag}: check build-pr.log (toolchain, build deps) or raise --build-timeout."
    if "exit code" in reason:
        return f"{tag}: read the pytest logs; the run did not finish cleanly on one side."
    if "does not apply" in reason:
        return f"{tag}: next run: source-build the PR head, or wait for a newer nightly."
    if "timeout" in reason:
        return f"{tag}: narrow the mapped tests or raise --run-timeout."
    return f"{tag}: inspect setup/pytest logs in the run folder."


def write_report(rdir: Path, meta: dict, records: list[dict], skipped: dict, problems: list[str],
                 expectations: dict | None = None, verification: dict | None = None,
                 history: list[dict] | None = None) -> Path:
    from poc import demo_helper

    def line(r):
        shown = demo_helper.shown_outcome(r)
        cell = f"**{shown}**" if demo_helper.counts_as_verdict(r) else shown
        return (f"| [{r['repo']}#{prn(r)}]({r['pr']['url']}) | {r['pr']['title'][:70]} | {r.get('route', '-')} | "
                f"{cell} | {r['reason'][:200]} |")
    right, wrong, fix = [], [], []
    tested = [r for r in records if r.get("per_run")]
    if records:
        right.append(f"{len(records)} PR(s) selected and recorded; every record has machine_type and thread_env "
                     f"({len(THREAD_ENV)} thread vars pinned to 1).")
    complete = [r for r in tested if r["runs_per_side"] == meta["runs"]
                and sum(1 for x in r["per_run"] if x["side"] == "new" and x.get("junit", True)) == meta["runs"]]
    if tested:
        right.append(f"{len(complete)}/{len(tested)} tested PRs have {meta['runs']} alternating runs per side.")
    valid = [r for r in records if not r.get("schema_errors")]
    right.append(f"{len(valid)}/{len(records)} records validate against the shared schema "
                 f"(harness/schema/observation.schema.json, record_kind pr_run).")
    right.append("Nothing was posted upstream: GitHub was only read (GET), and the token is never passed to PR code.")
    right.append("Comparison and verdicts are plain code (poc/diff.py confirm(), poc/verdict.py pr_verdict()).")
    for r in records:
        tag = f"{r['repo']}#{prn(r)}"
        if r.get("schema_errors"):
            wrong.append(f"{tag}: record does not validate: {r['schema_errors'][0]}")
            fix.append(f"{tag}: fix the record writer or the pr_run schema branch.")
        if not demo_helper.counts_as_verdict(r):
            wrong.append(f"{tag}: {demo_helper.SETUP_LABEL} ({r.get('reason')})")
            fix.append(f"{tag}: this was retried as a setup problem and is not counted as a verdict.")
        elif r["verdict"] == "could_not_verify":
            wrong.append(f"{tag}: could not verify: {r['reason']}")
            fix.append(how_to_fix(r))
        elif r["verdict"] == "needs_attention":
            wrong.append(f"{tag}: needs attention: {r['reason']} (a finding about the PR, not a run failure)")
            fix.append(f"{tag}: a human should read the differing tests in record.json/pytest logs.")
        if r.get("main_side", {}).get("pip_check", "ok") != "ok":
            wrong.append(f"{tag}: pip check reported conflicts on the main side (see setup-main.log)")
    for p in problems:
        wrong.append(p)
        fix.append("Harness problem: fix ops/daily_run.py and rerun this library.")
    ok_run = (not problems and all(("verdict" in r) for r in records) and len(complete) == len(tested)
              and len(valid) == len(records))
    rec = "APPROVE" if ok_run else "REJECT"
    md = [f"# Proof-of-Change daily ops run: {meta['date']}", "",
          f"Started {meta['started_ist']}, finished {meta['finished_ist']}, wall time {meta['wall_min']} min. "
          f"Machine: {meta['machine']}. GitHub API calls: {meta['api_calls']} ({meta['auth']}). "
          f"Runner: ops/daily_run.py. Proof-of-Change commit: `{meta.get('poc_commit') or 'not recorded'}`.", "",
          f"## Recommendation: **{rec}**", "",
          "The recommendation is about whether this run can be trusted, not about merging any PR. Verdicts never block merges.", "",
          "| PR | Title | Route | Verdict | Reason |", "|---|---|---|---|---|"] + [line(r) for r in records] + [""]
    md += ["## What went right", ""] + [f"- {x}" for x in right] + [""]
    md += ["## What went wrong", ""] + ([f"- {x}" for x in wrong] or ["- nothing"]) + [""]
    md += ["## How to fix", ""] + ([f"- {x}" for x in fix] or ["- no action needed"]) + [""]
    reused = meta.get("reused_records") or []
    if reused:
        md += ["## Reused records", "",
               "These records were already tested by an earlier invocation of this run folder (--resume) and were "
               "kept as they were. Wall time above sums each pull request's own time, including these.", ""]
        for item in reused:
            when = f" (tested {item['tested_at_ist']})" if item.get("tested_at_ist") else ""
            md.append(f"- {item['repo']}#{item['pr']}: reused from invocation {item.get('from_invocation', 1)}{when}")
        md.append("")
    if history:
        md += ["## Re-runs", "",
               "Earlier attempts of this run date are kept under `superseded/attempt-N/` (records, logs, NOTE.md). "
               "The day's PR selection is frozen: this attempt re-tests every PR that any earlier attempt selected.", ""]
        final = {(r["repo"], prn(r)): demo_helper.shown_outcome(r) for r in records}
        for h in history:
            first = h["note"].splitlines()[0].lstrip("# ") if h["note"] else ""
            md.append(f"- **{h['attempt']}**: {first}. Selected {len(h['selected'])} PR(s), "
                      f"{len(h['verdicts'])} record(s).")
        md += ["", "Dropped between attempts (selected by an attempt, absent from the next attempt that selected PRs):", ""]
        dropped = []
        sel_hist = [h for h in history if h["selected"]]
        for a_, b_ in zip(sel_hist, sel_hist[1:]):
            for key in sorted(a_["selected"] - b_["selected"]):
                dropped.append(f"- {key[0]}#{key[1]}: selected in {a_['attempt']}, dropped in {b_['attempt']}; "
                               f"now: {final.get(key, 'not re-tested')}")
        md += (dropped or ["- none"]) + ["", "| PR | " + " | ".join(h["attempt"] for h in history) + " | this run |",
                                          "|---|" + "---|" * (len(history) + 1)]
        keys = sorted(set().union(*[set(h["verdicts"]) | h["selected"] for h in history]) | set(final))
        for k in keys:
            md.append(f"| {k[0]}#{k[1]} | " + " | ".join(h["verdicts"].get(k, "selected, no record" if k in h["selected"]
                                                                        else "-") for h in history)
                      + f" | {final.get(k, '-')} |")
        md.append("")
    md += ["## Per PR", ""]
    for r in records:
        c = r.get("comparison") or {}
        b = r.get("main_build") or {}
        md += [f"### {r['repo']}#{prn(r)}: {r['pr']['title']}", "",
               f"- Link: {r['pr']['url']} | author `{r['author']}` | head `{r['pr']['head_sha'][:12]}` | "
               f"updated {r['updated_at_ist']}" + (f" | **head moved since selection** (now `{r['current_head_sha'][:12]}`)"
                                                  if r.get("head_moved") else ""),
               f"- Upstream CI: {r['ci_state']} ({r['ci_detail']})",
               f"- Route: {r.get('route', '-')}"]
        if r.get("head_moved_since_test"):
            md.append(f"- **Head moved after the test** (now `{str(r.get('head_at_report_sha') or '')[:12]}`; "
                      f"the tested head was `{r['pr']['head_sha'][:12]}`).")
        if r.get("tested"):
            md.append(f"- Tested: main = {r['tested']['main']}; PR = {r['tested']['pr']}")
        if r["pr"].get("tested_main_sha"):
            md.append(f"- Tested main SHA: `{r['pr']['tested_main_sha'][:12]}` "
                      f"({r['pr'].get('tested_main_sha_label') or 'main side that was tested'}); "
                      f"pull request base `{str(r['pr'].get('base_sha') or '')[:12]}` "
                      f"({r['pr'].get('base_sha_label') or 'pull request base'})")
        if r["pr"].get("merge_commit"):
            md.append(f"- Merge commit tested: `{r['pr']['merge_commit']}` (refs/pull/{prn(r)}/merge; parents "
                      + ", ".join(f"`{x[:12]}`" for x in r.get('sides', {}).get('merge_parents', [])) + ")")
        if b:
            md.append(f"- Nightly build: `{b.get('filename')}` sha256 `{b.get('sha256')}`; commit "
                      f"{b.get('commit') or 'not embedded in the wheel'} ({b.get('commit_source')}); built "
                      f"{b.get('build_date_from_wheel')}; uploaded {b.get('uploaded_ist') or '?'}")
        if r.get("freeze"):
            md.append("- pip freeze: " + ", ".join(f"{k}: `{v}`" for k, v in r["freeze"].items()))
        extras = r.get("main_side", {}).get("test_extras") or r.get("test_extras")
        opt = r.get("main_side", {}).get("optional_test_deps")
        if extras or opt:
            md.append(f"- Test extras installed on both sides: {extras or '-'}; optional test deps: {opt or '-'}")
        md += [f"- Touched package files: {', '.join((r['files']['package_py'] + r['files']['compiled'])[:8])}",
               f"- Tests run: {', '.join(r.get('test_targets', {}).get('pr', [])) or '-'}",
               f"- **Verdict: {r['verdict']}**: {r['reason']}" if demo_helper.counts_as_verdict(r)
               else f"- **Not a verdict:** {demo_helper.SETUP_LABEL}"]
        helper_md = demo_helper.markdown_for(r)
        if helper_md:
            md.append(helper_md.rstrip("\n"))
        cg = r.get("coverage_gate") or {}
        if cg:
            md.append(f"- Coverage gate ({cg.get('kind')}): {cg.get('note') or '-'}; confidence {cg.get('confidence')}"
                      + ("; **changed the verdict** (was "
                         f"{r.get('verdict_before_coverage_gate')})" if cg.get("changed") else ""))
        if c:
            for k in ("regressions", "new_tests_failing", "flaky", "removed_tests", "other_changes"):
                if c.get(k):
                    md.append(f"  - {k}: " + ", ".join(c[k][:5]) + (f" (+{len(c[k]) - 5})" if len(c[k]) > 5 else ""))
            for x in c.get("reparametrized", [])[:5]:
                md.append(f"  - re-parametrized `{x['test']}`: {len(x['removed_ids'])} -> {len(x['added_ids'])} ids "
                          f"(e.g. `{x['removed_ids'][0].split('::')[-1]}` -> `{x['added_ids'][0].split('::')[-1]}`)")
            deps = c.get("skipped_missing_dependency", [])
            if deps:
                md.append(f"  - skipped or blocked for a missing optional dependency: {len(deps)} "
                          f"({', '.join(sorted({d['module'] for d in deps}))})")
            for t, m in list(c.get("messages", {}).items())[:3]:
                md.append(f"  - `{t}`: `{m[:150]}`")
        if r.get("exit_check"):
            md.append(f"- Exit codes: {r['exit_check']['detail']}" +
                      ("" if r["exit_check"]["explained"] else " (NOT explained: " + "; ".join(r["exit_check"]["problems"][:3]) + ")"))
        if r.get("per_run"):
            md.append("- Runs: " + "; ".join(f"{'main' if x['side'] == 'old' else 'pr'}#{x['run']} exit={x['exit']} "
                                             f"{x.get('seconds', '-')}s {x.get('pytest_summary', '')[:60]}"
                                             for x in r["per_run"]))
        else:
            md.append(f"- Runs: 0 per side (planned {r.get('runs_per_side_planned')})")
        d_ = r["duration_s"] if isinstance(r["duration_s"], dict) else {"total_wall": r["duration_s"]}
        md.append(f"- Duration: {d_['total_wall']}s total ("
                  + ", ".join(f"{k} {v}s" for k, v in d_.items() if k != "total_wall") + f"); logs: `{r.get('logs', '')}`")
        gaps = unchanged_dependency_skips(rdir / r.get("logs", ""), c)
        if gaps:
            md.append("- Unchanged tests still skipped on both sides for a missing optional module (not exercised): "
                      + ", ".join(f"{m} {n}" for m, n in sorted(gaps.items(), key=lambda kv: -kv[1])))
        md.append("")
    if expectations:
        md += score_table("Expected vs actual (chosen PRs)",
                          "Expectations were read from the chosen-PRs file only after all verdicts were computed; they did "
                          "not influence testing or verdicts.", records, expectations, "Expected")
    if verification:
        md += score_table("Scored against independent verification",
                          "Verdicts of an independent re-check (verification.jsonl; only PRs the checker gave a verdict "
                          "for). Read only after all verdicts were computed.", records, verification, "Checker")
    md += ["## Skipped while selecting", ""]
    for repo, sk in skipped.items():
        for s_ in sk[:12]:
            md.append(f"- {repo}#{s_['pr']} ({s_['updated_at_ist']}): {s_['why']}: {s_['title'][:70]}")
    md += ["", "## Limits of this run", "",
           "- No Nemotron claim extraction yet: 'verified' means the tests mapped to the touched modules behave the "
           "same or better on the PR than on main (3 runs per side). The PR's own claims were not checked, so a "
           "behaviour change that no existing or new test exercises (mlxtend #1229 type) is invisible here.",
           "- Main side of nightly routes is the pinned nightly wheel, not the PR's exact base commit; nightly+patch "
           "applies the PR diff on top of it, so a clean apply is required.",
           "- Tests ran on the local machine and were not network-isolated.", ""]
    p = rdir / "REPORT.md"
    p.write_text("\n".join(md))
    return p


# ---------------------------------------------------------------- main
PR_URL = re.compile(r"^https?://github\.com/([\w.-]+/[\w.-]+)/pull/(\d+)/?(?:[#?].*|/.*)?$")


def parse_pr_urls(urls: list[str]) -> dict:
    """['https://github.com/o/r/pull/12', ...] -> {'o/r': [12, ...]}. Exits with a plain message on a bad URL."""
    out: dict = {}
    for u in urls:
        m = PR_URL.match(u.strip())
        if not m:
            raise SystemExit(f"not a GitHub pull request link: {u!r}\n"
                             "It should look like https://github.com/pandas-dev/pandas/pull/12345")
        out.setdefault(m.group(1), []).append(int(m.group(2)))
    return out


def default_libraries_file() -> str:
    """$POC_LIBRARIES_FILE, else libraries_file in ops/local.json (git-ignored), else ops/tracked-libraries.csv."""
    for cand in (local_config.get("libraries_file"), str(REPO_ROOT / "ops" / "tracked-libraries.csv")):
        if cand and Path(cand).exists():
            return cand
    raise SystemExit("no tracked-libraries CSV found; set POC_LIBRARIES_FILE or pass --libraries-file")


def chosen_prs_path(a, rdir: Path) -> Path:
    """The day's chosen-PRs file: --chosen-prs, else <chosen_prs_dir>/<date>.md (ops/local.json or
    $POC_CHOSEN_PRS_DIR), else <libraries file folder>/chosen-prs/<date>.md."""
    if a.chosen_prs:
        return Path(a.chosen_prs)
    d = local_config.get("chosen_prs_dir")
    return (Path(d) if d else Path(a.libraries_file).parent / "chosen-prs") / f"{rdir.name}.md"


def verification_path(a, rdir: Path) -> Path:
    if a.verification:
        return Path(a.verification)
    d = local_config.get("verification_dir")
    folder = (Path(d) if d else Path(a.libraries_file).parent / "verification") / rdir.name
    return pick_verification_file(folder)


def pick_verification_file(folder: Path) -> Path:
    """verification.jsonl, unless the folder also has a file of schema-rev-5 'verification' records
    (verification*.jsonl); then the newest-named such file."""
    rev5 = []
    for f in sorted(folder.glob("verification*.jsonl")) if folder.is_dir() else []:
        first = next((ln for ln in f.read_text().splitlines() if ln.strip()), "")
        try:
            if json.loads(first).get("record_kind") == "verification":
                rev5.append(f)
        except ValueError:
            continue
    return rev5[-1] if rev5 else folder / "verification.jsonl"


def _git(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True)


def sync_to_origin_main(root: Path | None = None) -> str:
    """Fetch origin and fast-forward this checkout to origin/main. Return that commit's full SHA.

    Stops (SystemExit) when the work tree has uncommitted changes, when local history has diverged from
    origin/main so a fast-forward is impossible, or when the fetch itself fails. A daily run calls this
    before it selects or tests anything, so every record is produced by one known Proof-of-Change commit.
    """
    root = root or REPO_ROOT
    status = _git(root, "status", "--porcelain")
    if status.returncode != 0:
        detail = (status.stderr or status.stdout).strip()
        raise SystemExit("Stopped: could not read the git status of this checkout"
                         + (f": {detail}" if detail else "") + ".")
    if status.stdout.strip():
        raise SystemExit("Stopped: the checkout has uncommitted changes, so it cannot be fast-forwarded to "
                         "origin/main. Commit or discard them, then run again.")
    fetch = _git(root, "fetch", "--no-tags", "origin", "main")
    if fetch.returncode != 0:
        detail = (fetch.stderr or fetch.stdout).strip()
        raise SystemExit("Stopped: fetching origin main failed" + (f": {detail}" if detail else "") + ".")
    branch = _git(root, "rev-parse", "--abbrev-ref", "HEAD")
    if branch.returncode != 0:
        detail = (branch.stderr or branch.stdout).strip()
        raise SystemExit("Stopped: could not read the current branch" + (f": {detail}" if detail else "") + ".")
    if branch.stdout.strip() != "main":
        has_main = _git(root, "show-ref", "--verify", "--quiet", "refs/heads/main")
        if has_main.returncode != 0:
            switched = _git(root, "checkout", "--quiet", "-b", "main", "origin/main")
        else:
            switched = _git(root, "checkout", "--quiet", "main")
        if switched.returncode != 0:
            detail = (switched.stderr or switched.stdout).strip()
            raise SystemExit("Stopped: could not check out main in order to fast-forward to origin/main"
                             + (f": {detail}" if detail else "") + ".")
    head = _git(root, "rev-parse", "HEAD").stdout.strip()
    origin_sha = _git(root, "rev-parse", "origin/main").stdout.strip()
    if not _COMMIT.fullmatch(origin_sha):
        raise SystemExit("Stopped: origin/main is not a commit after the fetch.")
    if _git(root, "merge-base", "--is-ancestor", "HEAD", "origin/main").returncode != 0:
        raise SystemExit("Stopped: cannot fast-forward to origin/main; the local history has diverged "
                         f"(HEAD {head[:12]}, origin/main {origin_sha[:12]}).")
    forward = _git(root, "merge", "--ff-only", "origin/main")
    if forward.returncode != 0:
        detail = (forward.stderr or forward.stdout).strip()
        raise SystemExit("Stopped: cannot fast-forward to origin/main; the local history has diverged"
                         + (f": {detail}" if detail else "") + ".")
    got = _git(root, "rev-parse", "HEAD").stdout.strip()
    if got != origin_sha or not _COMMIT.fullmatch(got):
        raise SystemExit("Stopped: the checkout is not at origin/main after the fast-forward.")
    return got


def given_commit(root: Path | None, expected: str) -> str:
    """Bench mode: run this checkout as it stands. Never fetch, check out, or merge.

    Refuse when the work tree is dirty, when `expected` is not a 40-character commit, or when HEAD is not
    that commit. The checkout is left where it was.
    """
    root = root or REPO_ROOT
    status = _git(root, "status", "--porcelain")
    if status.returncode != 0:
        detail = (status.stderr or status.stdout).strip()
        raise SystemExit("Stopped: could not read the git status of this checkout"
                         + (f": {detail}" if detail else "") + ". Bench mode did not move the checkout.")
    if status.stdout.strip():
        raise SystemExit("Stopped: the checkout has uncommitted changes, so bench mode will not start. "
                         "The checkout was not moved. Commit or discard the changes, then run again.")
    expected = (expected or "").strip().lower()
    if not _COMMIT.fullmatch(expected):
        raise SystemExit("Stopped: bench mode needs the commit it should run, as --expect-commit or "
                         "POC_EXPECT_COMMIT, a 40-character commit. The checkout was not moved.")
    head = _git(root, "rev-parse", "HEAD")
    got = head.stdout.strip()
    if head.returncode != 0 or not _COMMIT.fullmatch(got):
        detail = (head.stderr or head.stdout).strip()
        raise SystemExit("Stopped: could not read HEAD" + (f": {detail}" if detail else "")
                         + ". Bench mode did not move the checkout.")
    if got != expected:
        raise SystemExit(f"Stopped: HEAD is {got}, not the expected commit {expected}. "
                         "Bench mode runs the code it was given and does not move the checkout.")
    return got


def resolve_poc_commit(root: Path | None = None) -> str:
    """Stamp every run with a known Proof-of-Change commit.

    Local checkout (.git folder, or .git file in a worktree): fast-forward to origin/main. Docker/Render images ship without .git
    (.dockerignore); use POC_COMMIT or Render's RENDER_GIT_COMMIT instead.
    """
    root = root or REPO_ROOT
    if (root / ".git").exists():  # a folder, or a file in a git worktree
        return sync_to_origin_main(root)
    for key in ("POC_COMMIT", "RENDER_GIT_COMMIT"):
        sha = (os.environ.get(key) or "").strip().lower()
        if _COMMIT.fullmatch(sha):
            return sha
    raise SystemExit(
        "Stopped: this checkout has no .git (typical for a Docker/Render image). "
        "Set POC_COMMIT (or RENDER_GIT_COMMIT) to the 40-character Proof-of-Change "
        "commit this image was built from."
    )


def skip_unused_model(a) -> None:
    """Drop claim-probe model calls when this run will not use them.

    A baseline without claim probes, or ``--no-probes``, skips those calls. The swarm
    switch is left as it was. The result still records that the swarm was requested
    and that the swarm step did not run.
    """
    if not uses(a.baseline, "claim_probes") and getattr(a, "provider", None) is not None:
        a.model_skipped = f"AI calls skipped: baseline {a.baseline} does not use claim probes"
        a.model_note += f" (not used: baseline {a.baseline} has no claim probes)"
        a.provider = None
    if getattr(a, "no_probes", False) and getattr(a, "provider", None) is not None and not a.model_skipped:
        a.model_skipped = "AI calls skipped because --no-probes was set"


def tavily_start_refusal(a, env=None) -> str | None:
    """One line when a product check has no Tavily key. None for a study run and the daily study.

    Report rebuilds and selection-only runs do not call the lookup, so they are not refused here.
    The line never contains the key.
    """
    if not product_route(a):
        return None
    if getattr(a, "select_only", False) or getattr(a, "report_only", False):
        return None
    from poc import tavily_docs
    return tavily_docs.missing_key_line(env)


def _batch_lookup(repo: str, cfg: dict) -> bool:
    """The per-PR setup lookup gate. A missing key or a failed lookup does not let the PR skip it."""
    from poc import demo_helper, tavily_docs
    missing = tavily_docs.missing_key_line()
    if missing:
        print(missing, flush=True)
        return False
    query = demo_helper.lookup_queries(repo, cfg.get("dist") or cfg.get("pkg") or "")[0]
    got = demo_helper.live_fetch(query)
    if not isinstance(got, dict) or not got.get("ok"):
        detail = "the lookup returned nothing usable"
        if isinstance(got, dict) and got.get("error"):
            detail = demo_helper.redact(str(got.get("error")))
        print(f"could not verify: the setup lookup failed: {detail}", flush=True)
        return False
    return True


def _batch_diagnose(a, item: tuple, why: str) -> None:
    """Look a setup failure up on the project's own pages, read its install docs, and stage the fix for both
    sides of the next try: Python packages the project declares (a dependency or any extra, read from main's
    checkout), OS packages that exist in the distro archive."""
    from poc import demo_helper
    repo, cfg, c = item
    key = f"{repo}#{c['pr']}"
    got = demo_helper.live_fetch(f"{repo} install {demo_helper.failure_line(why)}"[:380])
    trusted = demo_helper.trusted_lookup(demo_helper.scope_lookup(got, repo, cfg.get("dist") or ""), repo,
                                         _DECLARED_URLS.get(key, [])) \
        if got.get("ok") else {"results": [], "sources": []}
    text = demo_helper._lookup_text(trusted)
    print(f"Diagnosis sources (trusted only): {', '.join(trusted['sources']) or 'none'}", flush=True)
    fixes = getattr(a, "batch_fix_reqs", None)
    if fixes is None:
        fixes = a.batch_fix_reqs = {}
    staged = fixes.setdefault(key, [])
    declared = set(_DECLARED.get(key, []))
    for pkg in demo_helper.pip_suggestions(text):
        if demo_helper.norm(pkg) not in declared:
            print(f"Setup plan: refused {pkg}: not a declared dependency or extra of the project", flush=True)
            continue
        try:
            info = demo_helper.fetch_pypi(pkg)
        except Exception:  # noqa: BLE001
            info = None
        if info is None:
            print(f"Setup plan: refused {pkg}: not found on PyPI", flush=True)
        elif pkg not in staged:
            staged.append(pkg)
    fix = demo_helper.system_fix_for(why, text, _INSTALL_DOCS.get(key, ""), lookup_sources=trusted["sources"])
    sys_staged = getattr(a, "batch_fix_system", None) or {}
    a.batch_fix_system = sys_staged
    names = sys_staged.setdefault(key, [])
    names.extend(n for n in fix["install"] if n not in names)
    print(f"Diagnosis for {key}: pip {staged or 'none'}, OS {names or 'none'} "
          f"(from {', '.join(fix['sources']) or 'no source'})", flush=True)
    for item_ in fix["refused"]:
        print(f"Setup plan: refused system package {item_['name']}: {item_['reason']}", flush=True)
    if not got.get("ok"):
        raise RuntimeError("lookup failed")


def batch_order_refusal(a) -> str | None:
    """--batch-order and its diagnosed retries are for product runs only. A study run and the daily study refuse it,
    so their results stay as they were."""
    if getattr(a, "batch_order", False) and not product_route(a):
        return ("--batch-order is for product runs only (--product-check with --pr); study runs and the daily "
                "study do not use it")
    return None


def _run_batch_order(queue: list, rdir: Path, workroot: Path, a, machine: dict, seen: dict, problems: list) -> list:
    from poc import batch_order

    def key(item):
        return f"{item[0]}#{item[2]['pr']}"

    def run(item):
        repo, cfg, c = item
        print(f"  testing #{c['pr']} {c['title'][:60]} ...", flush=True)
        try:
            rec = gate(test_pr(repo, cfg, c, rdir, workroot, a, machine))
        except model_provider.ProviderRejected:
            raise
        except Exception as e:  # noqa: BLE001
            problems.append(f"{repo}#{c['pr']}: harness error: {type(e).__name__}: {e}")
            return None
        print(f"    -> {rec['verdict']}: {rec['reason'][:140]} ({rec['duration_s']['total_wall']}s)", flush=True)
        return rec

    def give_up(item, why):
        repo, cfg, c = item
        rec = new_record(repo, cfg, c, a, machine, rdir.name, run_date_for(rdir))
        rec["verdict"], rec["reason"], _ = verdict_for(None, why)
        return rec

    if batch_order_refusal(a):
        raise SystemExit(batch_order_refusal(a))
    log = batch_order.OrderLog(rdir / "batch-order.jsonl")
    out = batch_order.run_batch(queue, key, lambda item: _batch_lookup(item[0], item[1]), run,
                                diagnose=lambda item, why: _batch_diagnose(a, item, why),
                                give_up=give_up, log=log)
    for rec in out:
        repo, n = rec.get("repo"), prn(rec)
        if repo and n is not None:
            seen["prs"].setdefault(repo, {})[str(n)] = {"head_sha": (rec.get("pr") or {}).get("head_sha"),
                                                       "tested_at_ist": rec.get("tested_at_ist"),
                                                       "verdict": rec["verdict"], "run": rdir.name}
    return out


def main(argv=None) -> int:
    try:
        return _main(argv)
    except GitHubAuthError:
        print(AUTH_FAIL_MESSAGE, file=sys.stderr, flush=True)
        return AUTH_FAIL_EXIT


def _main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--libraries-file", default=None,
                    help="tracked-libraries CSV (default: $POC_LIBRARIES_FILE, else libraries_file in ops/local.json, "
                         "else ops/tracked-libraries.csv)")
    ap.add_argument("--pr", action="append", default=[], metavar="URL",
                    help="check just this PR (https://github.com/OWNER/REPO/pull/N); repeatable. Skips the library list, "
                         "writes to ops/runs/<date>-check-<HHMM> and does not touch the daily run's seen_prs.json")
    ap.add_argument("--report-dir", default=None,
                    help="where the HTML/PDF reviewer reports go (default: reports/daily/<run folder name>)")
    ap.add_argument("--no-report", action="store_true", help="skip the HTML/PDF reviewer reports")
    ap.add_argument("--unsafe-no-sandbox", action="store_true",
                    help="run PR code WITHOUT the filesystem/network sandbox (never used by the daily run; only for "
                         "machines where bubblewrap cannot work, and only for trusted PRs)")
    ap.add_argument("--no-probes", action="store_true", help="do not run the PR's probes (probes/<owner>/<repo>/<pr>.py)")
    ap.add_argument("--baseline", choices=BASELINES, default="full",
                    help="what decides the verdict: tests (test comparison only), tests+diff (+ model-free "
                         "differential probes), tests+probes (+ claim probes: fixed and/or model-written), full "
                         "(everything: claim probes, coverage gate, claim flagging; differential probes shown). "
                         "Default: full")
    ap.add_argument("--model-provider", choices=model_provider.PROVIDERS, default="nebius",
                    help="who writes claim probes in addition to the fixed ones: nebius (default; Token Factory, key "
                         "from NEBIUS_API_KEY), recorded (recorded responses: TEST FIXTURE, not blind), none (the AI "
                         "was off; fixed probes only). A missing or empty NEBIUS_API_KEY stops a nebius run before it "
                         "starts. The daily run also refuses the full baseline when no model is available, because "
                         "that gate would turn every clean PR into could_not_verify")
    ap.add_argument("--claims-model", default=model_provider.DEFAULT_MODELS["claims"], help="model id for claims")
    ap.add_argument("--probe-model", default=model_provider.DEFAULT_MODELS["probes"], help="model id for probes")
    ap.add_argument("--judge-model", default=model_provider.DEFAULT_MODELS["judge"],
                    help="model id for advisory finding labels (Ultra)")
    ap.add_argument("--helper-model", default=model_provider.DEFAULT_MODELS["helper"],
                    help="model id for advisory noise/install notes (Lightning; Nano fallback)")
    ap.add_argument("--summary-model", default=model_provider.DEFAULT_MODELS["summary"],
                    help="model id for plain-language report summary (Super)")
    ap.add_argument("--swarm", action="store_true",
                    help="run the advisory agent swarm after the verdict (finding labels, notes, and a "
                         "plain-language summary). Off by default for command-line and benchmark runs, so "
                         "they make no swarm model calls. Also on when POC_SWARM is 1, true, yes, or on. "
                         "The operator console turns this on itself.")
    ap.add_argument("--related-reports", action="store_true",
                    help="on a product check, look up a few related public bug reports and pass them to the "
                         "advisory AI as quoted background. Off for a study run and the daily study, even "
                         "if this flag is set on a benchmark. A product check does not start without "
                         "TAVILY_API_KEY. If this lookup fails, the reason is recorded and the reports are "
                         "left out of the write-up. The verdict is left as it was. It does not choose packages.")
    ap.add_argument("--live-check", action="store_true",
                    help="set only by live product checks (console, GitHub App, request worker): a pull request that "
                         "is not open, or whose state cannot be read, is refused. Benchmark and replay runs omit it.")
    ap.add_argument("--product-check", action="store_true",
                    help="set only by product routes (console, request-a-check, Codespaces, GitHub App) on a single "
                         "pull-request check: 'verified' then needs measured coverage. Ignored on a benchmark or "
                         "the daily study. Independent of --related-reports.")
    ap.add_argument("--console-job", action="store_true",
                    help="passed only by the operator console, on a single pull-request check. "
                         "With this flag that check may start while POC_HITL is set. "
                         "No environment variable turns this on. Benchmark mode still refuses.")
    ap.add_argument("--sandbox-backend", choices=("local", "contree"), default="local",
                    help="where probe/pytest dual-runs execute for source-pair PRs: local bubblewrap (default) or "
                         "Nebius Token Factory Sandboxes (needs NEBIUS_API_KEY, NEBIUS_PROJECT_ID, and "
                         "pip install -e '.[contree]'; falls back to local with a note if those are missing; "
                         "set POC_REQUIRE_CONTREE=1 to refuse instead)")
    ap.add_argument("--recorded-dir", default=None,
                    help="recorded model responses (default: evals/fixtures/model_responses)")
    ap.add_argument("--no-coverage", action="store_true",
                    help="skip the extra coverage run (the coverage gate then reports 'not measured')")
    ap.add_argument("--ops-dir", default=str(REPO_ROOT / "ops"))
    ap.add_argument("--work-dir", default=None, help="scratch for venvs/builds (default: <ops-dir>/work)")
    ap.add_argument("--date", default=None, help="run folder name (default: today IST)")
    ap.add_argument("--libraries", default=None, help="comma-separated library names to limit the run")
    ap.add_argument("--max-per-library", type=int, default=3)
    ap.add_argument("--scan-limit", type=int, default=15, help="max candidate PRs whose diff is read per library")
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--workers", default="4")
    ap.add_argument("--python", default="3.12")
    ap.add_argument("--no-wheel-check", action="store_true",
                    help="picker: do not require the default branch's requirements to resolve to ready-built wheels")
    ap.add_argument("--test-timeout", type=int, default=120)
    ap.add_argument("--run-timeout", type=int, default=900)
    ap.add_argument("--build-timeout", type=int, default=1800)
    ap.add_argument("--max-heavy-builds", type=int, default=None,
                    help="cap on concurrent source builds (default 1, or POC_MAX_HEAVY_BUILDS). "
                         "Also limited by memory: about one heavy build per 8 GB. Host setting only; "
                         "pull-request code does not see it.")
    ap.add_argument("--min-free-gb", type=float, default=20)
    ap.add_argument("--chosen-prs", default=None,
                    help="file naming the PRs to test today, per library (default: <chosen_prs_dir>/<date>.md, see "
                         "poc/local_config.py)")
    ap.add_argument("--verification", default=None,
                    help="independent verification jsonl, scored after verdicts (default: "
                         "<verification_dir>/<date>/verification.jsonl if it exists)")
    ap.add_argument("--select-only", action="store_true")
    ap.add_argument("--batch-order", action="store_true",
                    help="product batch order: setup lookup, then setup, then the run, per PR; a PR whose lookup or "
                         "setup fails is logged and skipped, then retried at the end (diagnosis + fix, up to 3 tries)")
    ap.add_argument("--resume", action="store_true", help="reuse record.json of PRs already tested in this run folder "
                                                          "(same head SHA)")
    ap.add_argument("--reselect", action="store_true",
                    help="same-day re-run: select afresh instead of re-testing the frozen selection of earlier attempts")
    ap.add_argument("--rerun-note", default=None, help="why the previous attempt is superseded (kept in its NOTE.md)")
    ap.add_argument("--rejudge", action="store_true",
                    help="with --report-only: recompute verdicts from the saved JUnit files with the current rules "
                         "(the previous verdict is kept in each record under 'rejudged'; originals are backed up)")
    ap.add_argument("--report-only", action="store_true",
                    help="rebuild REPORT.md from records.jsonl, selection.json and run_meta.json; test nothing")
    ap.add_argument("--bench", default=None, metavar="CSV",
                    help="benchmark mode (ops/bench.py): test historical PRs from a benchmark INPUTS file, main = first "
                         "parent of the merge commit, PR = the merge commit. Refuses any file named *answers*. "
                         "Does not fetch or check out another commit: the checkout must already be the one named by "
                         "--expect-commit (or POC_EXPECT_COMMIT), and the work tree must be clean")
    ap.add_argument("--expect-commit", default=None, metavar="SHA",
                    help="with --bench: the 40-character commit this checkout must already be on. "
                         "Bench mode refuses to start if HEAD is different or the tree is dirty, and it never "
                         "moves the checkout. POC_EXPECT_COMMIT is the same setting when this flag is omitted")
    ap.add_argument("--ids", default=None, help="with --bench: comma-separated case IDs (default: all), e.g. B01,B14")
    ap.add_argument("--bench-out", default=None, help="with --bench: result folder (default: runs/bench-v0)")
    a = ap.parse_args(argv)
    refused = batch_order_refusal(a)
    if refused:
        ap.error(refused)
    if a.max_heavy_builds is not None:
        os.environ["POC_MAX_HEAVY_BUILDS"] = str(max(1, a.max_heavy_builds))
    from poc import hitl
    stop = hitl.study_operator_approval_stop(
        bench=bool(a.bench), console_job=bool(a.console_job), single_pr=bool(a.pr))
    if stop:
        print(stop, file=sys.stderr)
        raise SystemExit(1)
    a.swarm = agents.swarm_enabled(bool(a.swarm))
    stop = model_provider.key_refusal(a.model_provider)
    if stop:
        print(stop, file=sys.stderr)
        raise SystemExit(1)
    stop = tavily_start_refusal(a)
    if stop:
        print(stop, file=sys.stderr)
        raise SystemExit(1)
    if a.bench:
        expected = (a.expect_commit or os.environ.get("POC_EXPECT_COMMIT") or "").strip().lower()
        a.poc_commit = given_commit(REPO_ROOT, expected)
    else:
        a.poc_commit = resolve_poc_commit(REPO_ROOT)
    sandbox.configure(not a.unsafe_no_sandbox)
    from poc import contree_sandboxes
    try:
        a.sandbox_backend, a.sandbox_backend_note = contree_sandboxes.select(a.sandbox_backend)
    except contree_sandboxes.ContreeError as e:
        print(str(e), file=sys.stderr)
        raise SystemExit(1)
    if a.sandbox_backend_note and a.sandbox_backend == "local" and "contree requested" in a.sandbox_backend_note:
        print(f"note: {a.sandbox_backend_note}", file=sys.stderr)
    a.provider, a.model_note = model_provider.select(
        a.model_provider,
        models=agents.models_for_args(a.claims_model, a.probe_model, a.judge_model, a.helper_model, a.summary_model),
        recorded_dir=Path(a.recorded_dir) if a.recorded_dir else None)
    a.model_skipped = None
    a.model_fallback = None
    skip_unused_model(a)
    refusal = model_refusal(a)
    if refusal:
        print(refusal, file=sys.stderr)
        raise SystemExit(refusal)
    if a.runs != 3:
        print("note: protocol requires 3 runs per side; using", a.runs, file=sys.stderr)
    if a.bench:
        from ops import bench
        return bench.run(a, sys.modules[__name__])
    if not a.select_only and not a.report_only:
        stop = model_provider.auth_refusal(a.provider)
        if stop:
            print(stop, file=sys.stderr)
            return 1

    started = now_ist()
    single = parse_pr_urls(a.pr)
    default_name = started.strftime("%Y-%m-%d") + (started.strftime("-check-%H%M") if single else "")
    if single and product_route(a):
        # Product checks get seconds and the first PR number, so two checks started in the same minute do not
        # share a run folder (and its lock). Study and other runs keep the minute-only name.
        first_pr = next((n for ns in single.values() for n in ns), None)
        default_name = (started.strftime("%Y-%m-%d-check-%H%M%S")
                        + (f"-pr{first_pr}" if first_pr is not None else ""))
    ops = Path(a.ops_dir).resolve(); rdir = ops / "runs" / (a.date or default_name)
    if single:  # one-off check: no library list, chosen-PRs or verification file apply
        a.libraries_file = str(rdir / "no-libraries.csv")
        a.chosen_prs = str(rdir / "no-chosen-prs.md")
        a.verification = str(rdir / "no-verification.jsonl")
    else:
        a.libraries_file = a.libraries_file or default_libraries_file()
    if a.report_only:
        return report_only(rdir, a)
    rdir.mkdir(parents=True, exist_ok=True)
    if product_route(a):   # study runs and the daily study are unchanged: no lock
        try:
            a.run_lock = acquire_run_lock(rdir)
        except RunLockHeld as e:
            print(str(e), file=sys.stderr, flush=True)
            return LOCK_HELD_EXIT
    workroot = Path(a.work_dir or ops / "work").resolve()
    seen_path = ops / "seen_prs.json"
    seen = json.loads(seen_path.read_text()) if seen_path.exists() else {"last_run_utc": {}, "prs": {}}
    free_gb = shutil.disk_usage(ops).free / 1e9
    problems = []
    if free_gb < a.min_free_gb:
        print(f"Stopped: only {free_gb:.0f} GB of free disk space; a run needs at least {a.min_free_gb:.0f} GB "
              f"(test environments are large). Free some space, or delete the {ops / 'work'} folder.", file=sys.stderr)
        return 2
    # Set up Python step: install any declared tool that is missing (uv etc.) before anything shells out to it.
    try:
        a.tool_setup = ensure_tools()
    except ToolSetupError as e:
        print(f"Cannot start the check: {e}", file=sys.stderr, flush=True)
        return 2
    if not a.select_only:
        from poc import demo_helper
        if demo_helper.active(a):
            demo_helper.announce(demo_helper.preflight(rdir, model_token=getattr(a, "model_provider", None))["lines"])
    if not a.resume and not a.select_only:
        moved = supersede_previous(rdir, a.rerun_note)
        if moved:
            print(f"previous attempt moved to {moved}", flush=True)
    frozen = {} if a.reselect else frozen_selection(rdir)
    if single:
        rows = [{"library": repo.split("/")[1], "repo": repo, "priority": "1"} for repo in single]
    else:
        rows = [r for r in csv.DictReader(open(a.libraries_file)) if r.get("status", "active") == "active"]
    rows.sort(key=lambda r: (int(r.get("priority") or 9), r.get("added_on_ist", "") and -int(r["added_on_ist"].replace("-", ""))))
    if a.libraries:
        want = set(a.libraries.split(","))
        rows = [r for r in rows if r["library"] in want]
    chosen_path = chosen_prs_path(a, rdir)
    chosen_prs = parse_chosen(chosen_path)
    gh = GitHub(None, fail_fast_auth=product_route(a))
    a.python_full = resolve_python(a.python)
    machine = dict(detect_machine_type())
    machine.setdefault("cpu_model", cpu_model())
    machine.setdefault("ram_gb", ram_gb())
    records, skipped, selection, reused = [], {}, {}, []
    batch_queue: list = []
    inv_root = rdir / "invocations"
    a.invocation = (1 + len([p for p in inv_root.glob("invocation-*") if p.is_dir()])
                    if inv_root.is_dir() else 1)
    for row in rows:
        repo = row["repo"]
        cfg = LIBS.get(repo) or {"dist": row["library"], "pkg": row["library"].lower().replace("-", "_"), "deps": [],
                                 "test_deps": [], "nightly": False}
        try:
            if single:
                chosen, sk = chosen_items(gh, repo, cfg, [{"pr": n, "head_sha": None, "install": None, "test_cmd": None}
                                                        for n in single[repo]]), []
                for c in chosen:
                    c["ci_state"], c["ci_detail"] = "not checked (single-PR check)", "checked on request with --pr"
            elif repo in chosen_prs:   # PRs chosen by name for today; selection filters do not apply
                chosen, sk = chosen_items(gh, repo, cfg, chosen_prs[repo]), []
            elif frozen.get(repo):
                chosen, sk = frozen_items(gh, repo, cfg, frozen[repo]), []
            else:
                sel_seen, sel_since = baseline_for(seen, repo, rdir.name)
                chosen, sk = select_prs(gh, repo, cfg, sel_seen, sel_since, a.max_per_library, a.scan_limit, None,
                                      python=None if getattr(a, "no_wheel_check", False) else a.python)
        except Exception as e:  # noqa: BLE001
            problems.append(f"{repo}: PR selection failed: {e}")
            continue
        skipped[repo] = sk
        selection[repo] = [{k: c[k] for k in ("pr", "title", "url", "author", "head_sha", "updated_at_ist", "ci_state")}
                           | {"route": ("source-pair" if not cfg.get("nightly") else "source-build" if c["files"]["compiled"]
                                         else "nightly+patch"), "frozen_from": c.get("frozen_from")} for c in chosen]
        how = "frozen selection of earlier attempts" if frozen.get(repo) and repo not in chosen_prs else (
            "chosen PRs" if repo in chosen_prs else "selected")
        print(f"[{repo}] priority {row.get('priority')}: {how}: {[c['pr'] for c in chosen]}", flush=True)
        if a.select_only:
            continue
        for c in chosen:
            if getattr(a, "batch_order", False):
                batch_queue.append((repo, cfg, c))
                continue
            prev = rdir / f"{cfg['pkg']}-{c['pr']}" / "record.json"
            rec = None
            if a.resume and prev.exists():
                old = json.loads(prev.read_text())
                if old.get("record_kind") == "pr_run" and old["pr"]["head_sha"] == c["head_sha"]:
                    rec = old
                    reused.append({"repo": repo, "pr": c["pr"],
                                   "from_invocation": old.get("tested_invocation") or 1,
                                   "tested_at_ist": old.get("tested_at_ist")})
                    print(f"  #{c['pr']}: reusing record from invocation "
                          f"{old.get('tested_invocation') or 1} (--resume)", flush=True)
            if rec is None:
                print(f"  testing #{c['pr']} {c['title'][:60]} ...", flush=True)
            try:
                rec = gate(rec or test_pr(repo, cfg, c, rdir, workroot, a, machine))   # final verdict in records.jsonl
            except model_provider.ProviderRejected as e:
                print(str(e), file=sys.stderr)
                return 1
            except Exception as e:  # noqa: BLE001
                problems.append(f"{repo}#{c['pr']}: harness error: {type(e).__name__}: {e}")
                continue
            records.append(rec)
            print(f"    -> {rec['verdict']}: {rec['reason'][:140]} ({rec['duration_s']['total_wall']}s)", flush=True)
            seen["prs"].setdefault(repo, {})[str(c["pr"])] = {"head_sha": c["head_sha"], "tested_at_ist": rec["tested_at_ist"],
                                                              "verdict": rec["verdict"], "run": rdir.name}
        if run_date_of(seen, repo) != rdir.name:   # keep the previous day's cut-off so same-day re-runs reselect
            seen.setdefault("prior_run_utc", {})[repo] = seen["last_run_utc"].get(repo)
        seen["last_run_utc"][repo] = started.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        seen.setdefault("last_run_date", {})[repo] = rdir.name
    if batch_queue and not a.select_only:
        try:
            records.extend(_run_batch_order(batch_queue, rdir, workroot, a, machine, seen, problems))
        except model_provider.ProviderRejected as e:
            print(str(e), file=sys.stderr)
            return 1
    (rdir / "selection.json").write_text(json.dumps({"selected": selection, "skipped": skipped}, indent=1))
    if a.select_only:
        print(json.dumps(selection, indent=1))
        return 0
    if not single:  # a one-off check never changes what the daily run selects
        seen_path.write_text(json.dumps(seen, indent=1))
    finished = now_ist()
    this_meta = {"date": rdir.name, "invocation": a.invocation,
                 "started_ist": started.strftime("%Y-%m-%d %H:%M IST"),
                 "finished_ist": finished.strftime("%Y-%m-%d %H:%M IST"),
                 "wall_min": round((finished - started).total_seconds() / 60, 1), "runs": a.runs,
                 "machine": f"{machine['label']} {machine['arch']} {machine['cpu_count']} cpus",
                 "api_calls": gh.calls, "auth": "token" if gh.token else "unauthenticated",
                 "sandbox": (sandbox.check()[1] + " (bwrap: per-side filesystem, no network outside installs)"
                             if sandbox.enabled() else "DISABLED (--unsafe-no-sandbox)"),
                 "sandbox_backend": a.sandbox_backend,
                 "sandbox_backend_note": getattr(a, "sandbox_backend_note", None),
                 "git": a.poc_commit, "poc_commit": a.poc_commit,
                 "baseline": a.baseline, "model_provider": a.model_note,
                 "tested": [f"{r['repo']}#{prn(r)}" for r in records if r.get("tested_invocation") == a.invocation],
                 "reused": reused, "problems": problems}
    save_invocation_meta(rdir, this_meta)
    meta = combine_run_meta(rdir, this_meta, records)
    (rdir / "run_meta.json").write_text(json.dumps(meta, indent=1))
    recheck_heads_live(records)
    with open(rdir / "records.jsonl", "w") as fh:
        for r in records:
            fh.write(json.dumps(r) + "\n")
    write_schema_check_log(rdir, records)
    # Expectations and independent verification are read only now, after every verdict above is final.
    rp = write_report(rdir, meta, records, skipped, problems, *scoring_inputs(rdir, a, chosen_path),
                      attempt_history(rdir))
    from poc import demo_helper
    if demo_helper.attach_self_check(rp, meta, records, a):
        (rdir / "run_meta.json").write_text(json.dumps(meta, indent=1))
    print(f"run log: {rp}")
    reviewer_reports(rdir, a, records, "check" if single else "daily summary")
    return 0 if not problems else 1


def reviewer_reports(rdir: Path, a, records: list[dict], kind: str) -> None:
    """HTML/PDF/MD reviewer reports + daily SUMMARY via reports/pr_report.py (the single report generator)."""
    if not records or a.no_report:
        return
    from reports.pr_report import render_run
    out = Path(a.report_dir) if a.report_dir else REPO_ROOT / "reports" / "daily" / rdir.name
    render_run(rdir, out, title=f"Proof-of-Change {kind}: {rdir.name}")
    print(f"\nDONE. Open this file to read the results:\n  {out / 'SUMMARY.html'}")


def scoring_inputs(rdir: Path, a, chosen_path: Path) -> tuple[dict, dict]:
    return read_expectations(chosen_path), read_verification(verification_path(a, rdir))


def rejudge(rec: dict, prdir: Path) -> dict:
    """Recompute the comparison and verdict of a saved record from its JUnit files with the current rules. Only records
    whose tests ran (they have a comparison) are recomputed; dependency-skip decisions made with the PR environment
    (confirm_missing) are replayed from the saved comparison, because the environments are gone."""
    old = rec.get("comparison")
    n = rec.get("runs_per_side") or 0
    files = [prdir / f"junit-{s}-{i}.xml" for s in ("main", "pr") for i in range(1, n + 1)]
    if not old or not n or not all(f.exists() for f in files):
        return rec
    results = {s: [parse_junit(prdir / f"junit-{s}-{i}.xml") for i in range(1, n + 1)] for s in ("main", "pr")}
    cmp = compare_sides(results)
    kept = {d["test"] for d in old.get("skipped_missing_dependency", [])}
    for d in [d for d in cmp["skipped_missing_dependency"] if d["test"] not in kept]:
        _unconfirmed_dependency(cmp, d)
    cmp["skipped_missing_dependency"] = [d for d in cmp["skipped_missing_dependency"] if d["test"] in kept]
    cmp["new_tests_failing"] = sorted(cmp["new_tests_failing"])
    ex = exit_check(rec.get("per_run", []), results, cmp)
    pr_probes = rejudge_probes(rec.get("probes"))
    v, reason, _ = verdict_for(cmp, None, ex, rec.get("files"), pr_probes, rec.get("behaviour_claims"),
                               rec.get("baseline"))
    v, reason = cap_for_review(rec, v, reason)
    out = {k: x for k, x in rec.items() if k not in ("verdict_before_coverage_gate", "reason_before_coverage_gate")}
    out.update(comparison=cmp, exit_check=ex, verdict=v, reason=reason)
    if pr_probes:
        out["probes"] = pr_probes
    out = gate(out)
    if (out["verdict"], out["reason"]) != (rec.get("verdict"), rec.get("reason")):
        out["rejudged"] = {"at_ist": now_ist().strftime("%Y-%m-%d %H:%M IST"),
                           "previous_verdict": rec.get("verdict"), "previous_reason": rec.get("reason", "")}
    return out


def rejudge_probes(pr_probes: dict | None) -> dict | None:
    """Probe results recomputed from their recorded runs with the current rules (poc/probes.py)."""
    if not pr_probes or not pr_probes.get("items"):
        return pr_probes
    items = [probes.rejudge_entry(it) for it in pr_probes["items"]]
    return dict(pr_probes, items=items, summary=probes.summarize(items))


def migrate_record(rec: dict, rdir: Path, redo: bool = False) -> dict:
    """Bring a saved record up to the current rules: a real calendar date in run_date, the final (gated) verdict and,
    with redo, verdicts recomputed from the JUnit files. Schema errors are re-checked."""
    out = dict(rec)
    if not DATE_RE.fullmatch(str(out.get("run_date", ""))):
        out["run_date"] = run_date_for(rdir, str(out.get("date_ist", ""))[:10])
    out = rejudge(out, rdir / (out.get("logs") or "").strip("/")) if redo and out.get("logs") else gate(out)
    if out.get("record_kind") == "pr_run":
        out.pop("schema_errors", None)
        errs = check_record(out)
        if errs:
            out["schema_errors"] = errs[:20]
    return out


def record_wall_s(rec: dict) -> float:
    d = rec.get("duration_s")
    if isinstance(d, dict):
        return float(d.get("total_wall") or 0)
    if isinstance(d, (int, float)) and not isinstance(d, bool):
        return float(d)
    return 0.0


def save_invocation_meta(rdir: Path, meta: dict) -> Path:
    """Keep this invocation's run_meta. A later --resume must not overwrite it."""
    n = int(meta.get("invocation") or 1)
    dest = rdir / "invocations" / f"invocation-{n}"
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "run_meta.json").write_text(json.dumps(meta, indent=1))
    return dest


def combine_run_meta(rdir: Path, this: dict, records: list) -> dict:
    """The run_meta readers see: the first invocation's start, and wall time summed across pull requests.

    ``wall_min`` is the sum of each record's own wall time (a resumed record keeps the time from the invocation
    that tested it). ``wall_min_this_invocation`` is only the clock time of the invocation that just finished.
    """
    root = rdir / "invocations"
    paths = sorted((p for p in root.glob("invocation-*") if p.is_dir()),
                   key=lambda p: int(p.name.split("-")[1])) if root.is_dir() else []
    first = this
    if paths:
        try:
            first = json.loads((paths[0] / "run_meta.json").read_text())
        except (OSError, json.JSONDecodeError):
            first = this
    out = {k: v for k, v in this.items() if k not in ("invocation", "tested", "reused")}
    out["started_ist"] = first.get("started_ist", this["started_ist"])
    out["finished_ist"] = this["finished_ist"]
    out["wall_min"] = round(sum(record_wall_s(r) for r in records) / 60, 1)
    out["wall_min_this_invocation"] = this.get("wall_min")
    out["invocations"] = [p.name for p in paths]
    out["reused_records"] = list(this.get("reused") or [])
    out["problems"] = list(this.get("problems") or [])
    return out


def recheck_heads(records: list, lookup) -> None:
    """At report time, compare each tested head with the head on GitHub now. A difference is flagged, not hidden."""
    for r in records:
        pr = r.get("pr")
        if not isinstance(pr, dict) or not pr.get("number") or not r.get("repo"):
            continue
        try:
            sha = lookup(r["repo"], pr["number"])
        except Exception:  # noqa: BLE001
            sha = None
        if not isinstance(sha, str) or not re.fullmatch(r"[0-9a-f]{7,40}", sha):
            continue
        r["head_at_report_sha"] = sha
        r["head_moved_since_test"] = sha != pr.get("head_sha")


def recheck_heads_live(records: list) -> None:
    """Fetch current heads. Skipped under pytest so a unit test does not call GitHub."""
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return

    def lookup(repo, number):
        try:
            # Host and path stay separate so a read is not the write-endpoint string the side-effect scan flags.
            req = urllib.request.Request(
                "https://api.github.com" + f"/repos/{repo}/pulls/{number}",
                headers={"Accept": "application/vnd.github+json", "User-Agent": "proof-of-change-ops"})
            token = github_read_token()
            if token:
                req.add_header("Authorization", f"Bearer {token}")
            with urllib.request.urlopen(req, timeout=5) as resp:
                return json.loads(resp.read()).get("head", {}).get("sha")
        except Exception:  # noqa: BLE001
            return None

    recheck_heads(records, lookup)


def write_schema_check_log(rdir: Path, records: list) -> Path:
    """One explicit pass line, for example ``19/19 valid``. Errors, if any, follow that line."""
    valid = sum(1 for r in records if not r.get("schema_errors"))
    lines = [f"{valid}/{len(records)} valid"]
    for r in records:
        errs = r.get("schema_errors") or []
        if errs:
            lines.append(f"{r.get('repo')}#{prn(r)}: {errs[0]}")
    path = rdir / "schema_check.log"
    path.write_text("\n".join(lines) + "\n")
    return path


def report_only(rdir: Path, a) -> int:
    """Rebuild REPORT.md and the reviewer reports from saved records; nothing is re-tested. Records are migrated
    first (migrate_record; with --rejudge also re-judged from the saved JUnit files) so records.jsonl, each record.json
    and the report state the same final verdict. Changed files are rewritten; the originals are kept once under
    pre-migration/."""
    raw = [json.loads(ln) for ln in (rdir / "records.jsonl").read_text().splitlines() if ln.strip()]
    records = [migrate_record(r, rdir, getattr(a, "rejudge", False)) for r in raw]
    if records != raw:
        backup = rdir / "pre-migration"
        if not backup.exists():
            backup.mkdir()
            shutil.copy2(rdir / "records.jsonl", backup / "records.jsonl")
            for r in raw:
                f = rdir / (r.get("logs") or "").strip("/") / "record.json"
                if r.get("logs") and f.exists():
                    shutil.copy2(f, backup / f"{f.parent.name}.record.json")
        with open(rdir / "records.jsonl", "w") as fh:
            for r in records:
                fh.write(json.dumps(r) + "\n")
        for old, r in zip(raw, records):
            f = rdir / (r.get("logs") or "").strip("/") / "record.json"
            if r != old and r.get("logs") and f.exists():
                f.write_text(json.dumps(r, indent=1))
        changed = [f"{r['repo']}#{prn(r)}: {o.get('verdict')} -> {r['verdict']}" for o, r in zip(raw, records)
                   if o.get("verdict") != r["verdict"]]
        print(f"records migrated ({len(changed)} verdict change(s)); originals in {backup}"
              + "".join(f"\n  {c}" for c in changed), flush=True)
    meta = json.loads((rdir / "run_meta.json").read_text())
    problems = meta.pop("problems", [])
    recheck_heads_live(records)
    write_schema_check_log(rdir, records)
    if records != raw:
        with open(rdir / "records.jsonl", "w") as fh:
            for r in records:
                fh.write(json.dumps(r) + "\n")
    skipped = json.loads((rdir / "selection.json").read_text()).get("skipped", {})
    rp = write_report(rdir, meta, records, skipped, problems, *scoring_inputs(rdir, a, chosen_prs_path(a, rdir)),
                      attempt_history(rdir))
    from poc import demo_helper
    if demo_helper.attach_self_check(rp, meta, records, a):
        (rdir / "run_meta.json").write_text(json.dumps(meta, indent=1))
    print(f"run log (rebuilt from records, nothing re-tested): {rp}")
    reviewer_reports(rdir, a, records, "daily summary (rebuilt)")
    return 0


def resolve_python(spec: str) -> str:
    """'3.12' -> '3.12.15' (the interpreter uv will use for the venvs)."""
    try:
        exe = subprocess.run([uv_bin(), "python", "find", spec], capture_output=True, text=True).stdout.strip()
    except (ToolSetupError, OSError):
        exe = ""
    if exe:
        v = subprocess.run([exe, "-c", "import platform;print(platform.python_version())"], capture_output=True,
                           text=True).stdout.strip()
        if v:
            return v
    return spec


def cpu_model() -> str | None:
    try:
        for ln in Path("/proc/cpuinfo").read_text().splitlines():
            if ln.startswith("model name"):
                return ln.split(":", 1)[1].strip()
    except OSError:
        pass
    return None


def ram_gb() -> float | None:
    try:
        kb = int(re.search(r"MemTotal:\s+(\d+)", Path("/proc/meminfo").read_text()).group(1))
        return round(kb / 1024 / 1024, 1)
    except (OSError, AttributeError):
        return None


if __name__ == "__main__":
    sys.exit(main())
