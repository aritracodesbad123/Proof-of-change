#!/usr/bin/env python3
"""Proof-of-Change daily ops run: registry -> new open PRs -> main-vs-PR test -> log + approver report.

    python3 ops/daily_run.py                       # normal daily run
    python3 ops/daily_run.py --select-only         # pick PRs, print them, test nothing
    python3 ops/daily_run.py --max-per-library 3 --libraries numpy,pandas
    python3 ops/daily_run.py --pr https://github.com/pandas-dev/pandas/pull/12345   # check one PR

After the run, reviewer reports (HTML, PDF, Markdown) are written to reports/daily/<run folder>/ (reports/pr_report.py).

Read-only towards GitHub: it only GETs public API/diff URLs. It never comments, reviews or posts.
Uses $GITHUB_TOKEN for read-only API calls if it is set; otherwise unauthenticated (60 requests/hour).

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
import glob
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
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
from harness.machine import detect_machine_type  # noqa: E402
from poc.diff import confirm  # noqa: E402
from poc.verdict import Claim, FindingLabel, RunSummary, Verdict, pr_verdict  # noqa: E402

IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
NIGHTLY = "https://pypi.anaconda.org/scientific-python-nightly-wheels/simple"
PYPI = "https://pypi.org/simple"
THREAD_ENV = {k: "1" for k in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS")}
COMPILED_EXT = (".c", ".h", ".cpp", ".hpp", ".cc", ".cxx", ".pyx", ".pxd", ".pxi", ".tp", ".src", ".f", ".f90", ".cu")
COMPILED_NAMES = ("meson.build", "meson.options", "meson_options.txt", "setup.py", "pyproject.toml")

# Per-library knobs. Unknown libraries fall back to DEFAULT (dist == import name == repo name).
LIBS = {
    "numpy/numpy": {"dist": "numpy", "pkg": "numpy", "deps": [], "test_deps": ["hypothesis", "typing_extensions"],
                    "nightly": True},
    "pandas-dev/pandas": {"dist": "pandas", "pkg": "pandas", "deps": [], "test_deps": ["hypothesis"], "nightly": True,
                          "tests_root": "pandas/tests"},
    "scikit-learn/scikit-learn": {"dist": "scikit-learn", "pkg": "sklearn", "deps": [], "test_deps": [], "nightly": True},
}
# tzdata: the box has no system zoneinfo; pandas/xarray tests need IANA zones.
BASE_TEST_DEPS = ["pytest", "pytest-timeout", "pytest-xdist", "tzdata"]


def now_ist() -> dt.datetime:
    return dt.datetime.now(IST)


def to_ist(iso_utc: str) -> str:
    t = dt.datetime.fromisoformat(iso_utc.replace("Z", "+00:00")).astimezone(IST)
    return t.strftime("%Y-%m-%d %H:%M IST")


# ---------------------------------------------------------------- GitHub (read-only)
class GitHub:
    def __init__(self, log):
        self.token = os.environ.get("GITHUB_TOKEN")
        self.calls = 0
        self.remaining = None
        self.log = log

    def get(self, url: str, accept: str = "application/vnd.github+json", api: bool = True, timeout: int = 60):
        req = urllib.request.Request(url, headers={"Accept": accept, "User-Agent": "proof-of-change-ops"})
        if api and self.token:
            req.add_header("Authorization", f"Bearer {self.token}")
        for attempt in range(3):
            try:
                with urllib.request.urlopen(req, timeout=timeout) as r:
                    if api:
                        self.calls += 1
                        self.remaining = int(r.headers.get("X-RateLimit-Remaining", "-1"))
                    return r.read()
            except urllib.error.HTTPError as e:
                if e.code in (403, 429) and api:
                    raise RuntimeError(f"GitHub rate limit hit at {url} (remaining={self.remaining})") from e
                if attempt == 2 or e.code == 404:
                    raise
            except urllib.error.URLError:
                if attempt == 2:
                    raise
            time.sleep(3 * (attempt + 1))

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
    in_pkg = [f for f in files if f.startswith(pkg + "/")]
    py = [f for f in in_pkg if f.endswith((".py", ".pyi"))]
    compiled = [f for f in in_pkg if f.endswith(COMPILED_EXT) or os.path.basename(f) in COMPILED_NAMES]
    build_cfg = [f for f in files if os.path.basename(f) in COMPILED_NAMES and "/" not in f.strip("/")]
    return {"all": files, "package_py": py, "compiled": compiled + build_cfg,
            "other": [f for f in files if f not in py and f not in compiled and f not in build_cfg]}



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

def select_prs(gh: GitHub, repo: str, cfg: dict, seen: dict, last_run_utc: str | None, max_n: int,
               scan_limit: int, log) -> tuple[list[dict], list[dict]]:
    """Return (selected, skipped). Day 1 (no last run): the max_n most recently updated eligible PRs.
    Later: eligible PRs updated since the last run whose head SHA was not tested yet (capped at max_n).
    Eligible = non-draft, upstream CI not failing (if visible), changes Python code in the package.
    Pure-Python PRs are preferred; compiled ones fill remaining slots."""
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
        in_pkg_compiled = [f for f in fc["compiled"] if f.startswith(cfg["pkg"] + "/")]
        if not fc["package_py"] and not in_pkg_compiled:
            skipped.append(base | {"why": "no Python/compiled code in the package (docs, CI or tooling only)"}); continue
        item = {"pr": n, "title": p["title"], "url": p["html_url"], "author": p["user"]["login"], "head_sha": sha,
                "base_sha": p["base"]["sha"], "base_ref": p["base"]["ref"], "updated_at_utc": p["updated_at"],
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


# ---------------------------------------------------------------- registry picks
def parse_picks(path: Path) -> dict:
    """Jonathan's picks file -> {repo: [ {pr, head_sha, install, test_cmd} ]}.

    Expected verdicts are deliberately NOT read here. They are read by read_expectations() only after every verdict
    of the run has been computed (see main()), so they cannot influence selection, testing or verdicts.
    """
    out: dict = {}
    if not path.exists():
        return out
    for sec in re.split(r"(?m)^## \d+\. ", path.read_text())[1:]:
        repo = re.search(r"https://github\.com/([\w.-]+/[\w.-]+)", sec)
        pr = re.search(r"\*\*Open PR:\*\* #(\d+)", sec)
        if not (repo and pr):
            continue
        head = re.search(r"Head SHA: `([0-9a-f]{40})`", sec)
        inst = re.search(r"- Install: `([^`]+)`", sec)
        test = re.search(r"- Test \(subset[^)]*\): `([^`]+)`", sec)
        out.setdefault(repo.group(1).rstrip("."), []).append({
            "pr": int(pr.group(1)), "head_sha": head.group(1) if head else None,
            "install": inst.group(1) if inst else None, "test_cmd": test.group(1) if test else None})
    return out


def read_expectations(path: Path) -> dict:
    """{(repo, pr): expected_verdict}. Call ONLY after all verdicts are final."""
    exp = {}
    if not path.exists():
        return exp
    for sec in re.split(r"(?m)^## \d+\. ", path.read_text())[1:]:
        repo = re.search(r"https://github\.com/([\w.-]+/[\w.-]+)", sec)
        pr = re.search(r"\*\*Open PR:\*\* #(\d+)", sec)
        v = re.search(r"Expected Proof-of-Change verdict: `([^`]+)`", sec)
        if repo and pr and v:
            exp[(repo.group(1).rstrip("."), int(pr.group(1)))] = v.group(1).strip().replace(" ", "_")
    return exp


def pick_items(gh: GitHub, repo: str, cfg: dict, picks: list[dict]) -> list[dict]:
    items = []
    for pk in picks:
        p = gh.json(f"/repos/{repo}/pulls/{pk['pr']}")
        d = gh.diff(repo, pk["pr"])
        items.append({"pr": p["number"], "title": p["title"], "url": p["html_url"], "author": p["user"]["login"],
                      "head_sha": pk["head_sha"] or p["head"]["sha"], "current_head_sha": p["head"]["sha"],
                      "base_sha": p["base"]["sha"], "base_ref": p["base"]["ref"], "updated_at_utc": p["updated_at"],
                      "updated_at_ist": to_ist(p["updated_at"]), "files": classify_files(diff_files(d), cfg["pkg"]),
                      "diff": d, "mergeable": p.get("mergeable"), "mergeable_state": p.get("mergeable_state"),
                      "draft": p.get("draft"), "state": p.get("state"), "pick": pk, "ci_state": "not checked (registry pick)",
                      "ci_detail": "picked by Jonathan; selection filters not applied"})
    return items


def side_install_args(pick: dict | None, checkout: Path) -> tuple[list[str], list[str]]:
    """'pip install -e ".[a,b]" pytest x' -> (['-e', '<checkout>[a,b]'], ['pytest', 'x'])."""
    if not pick or not pick.get("install"):
        return ["-e", str(checkout)], []
    toks = shlex.split(pick["install"])
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


def pick_test_targets(pick: dict | None) -> list[str]:
    if not pick or not pick.get("test_cmd"):
        return []
    toks = shlex.split(pick["test_cmd"])
    out, skip = [], False
    for t in toks[1:]:
        if skip:
            skip = False; continue
        if t in ("-n", "-k", "-m"):
            skip = True; continue
        if not t.startswith("-"):
            out.append(t)
    return out


def map_repo_tests(files: dict, checkout: Path, max_targets: int = 6) -> list[str]:
    targets: list[str] = []
    for f in files["all"]:
        b = os.path.basename(f)
        if b.startswith("test_") and b.endswith(".py") and (checkout / f).is_file():
            targets.append(f)
    for f in files["package_py"]:
        stem = os.path.splitext(os.path.basename(f))[0].lstrip("_")
        for hit in sorted(glob.glob(str(checkout / "**" / f"test_{stem}.py"), recursive=True))[:2]:
            rel = os.path.relpath(hit, checkout)
            if rel not in targets:
                targets.append(rel)
    return targets[:max_targets]


def source_pair(repo: str, item: dict, work: Path, log: Path, python: str, timeout: int) -> dict:
    """Pure-Python library without nightly wheels: build both sides from git.
    Conflicting PR (mergeable false / state dirty): main = merge-base(PR head, base branch), PR = PR head.
    Mergeable PR: main = current base-branch tip, PR = GitHub's test merge commit (refs/pull/N/merge)."""
    env = base_env()
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
    base_tip = subprocess.run(["git", "-C", src, "rev-parse", f"origin/{item['base_ref']}"], capture_output=True,
                              text=True).stdout.strip()
    if conflicting or head != item.get("current_head_sha", head):
        mb = subprocess.run(["git", "-C", src, "merge-base", head, base_tip], capture_output=True, text=True).stdout.strip()
        if not mb:
            return {"ok": False, "why": "could not compute merge-base of PR head and base branch"}
        res |= {"comparison_basis": "merge-base vs PR head" + (" (PR conflicts with base)" if conflicting else
                                                             " (pinned head differs from current head)"),
                "main_sha": mb, "pr_sha": head}
    else:
        rc, _ = run(["git", "-C", src, "fetch", "-q", "origin", f"pull/{item['pr']}/merge"], log, env=env, timeout=300)
        merge = subprocess.run(["git", "-C", src, "rev-parse", "FETCH_HEAD"], capture_output=True, text=True).stdout.strip()
        if rc != 0 or not merge:
            mb = subprocess.run(["git", "-C", src, "merge-base", head, base_tip], capture_output=True, text=True).stdout.strip()
            res |= {"comparison_basis": "merge-base vs PR head (no merge ref available)", "main_sha": mb, "pr_sha": head}
        else:
            parent1 = subprocess.run(["git", "-C", src, "rev-parse", f"{merge}^1"], capture_output=True, text=True).stdout.strip()
            res |= {"comparison_basis": "base tip vs GitHub test merge (refs/pull/N/merge)", "main_sha": parent1,
                    "pr_sha": merge}
    for side in ("main", "pr"):
        rc, _ = run(["git", "-C", src, "worktree", "add", "-q", "--detach", work / f"side-{side}", res[f"{side}_sha"]],
                    log, env=env, timeout=900)
        if rc != 0:
            return {"ok": False, "why": f"checkout of {side} side failed"}
    res["ok"] = True
    return res


def install_side(venv: Path, checkout: Path, pick: dict | None, log: Path, python: str, timeout: int,
                 constraints: Path | None) -> tuple[bool, str]:
    env = base_env()
    if subprocess.run(["git", "-C", checkout, "describe", "--tags"], capture_output=True).returncode != 0:
        env["SETUPTOOLS_SCM_PRETEND_VERSION"] = "9999.0.0"
    proj, extra = side_install_args(pick, checkout)
    cmds = [["uv", "venv", "-q", "-p", python, venv],
            ["uv", "pip", "install", "-q", "-p", venv / "bin/python", *proj, *extra, *BASE_TEST_DEPS]
            + (["-c", constraints] if constraints else [])]
    for c in cmds:
        rc, _ = run(c, log, env=env, timeout=timeout)
        if rc != 0:
            return False, f"install failed ({rc}); see {log.name}"
    return True, ""


# ---------------------------------------------------------------- execution helpers
def run(cmd, log_path: Path, cwd=None, env=None, timeout=None) -> tuple[int | str, float]:
    t0 = time.time()
    with open(log_path, "a") as fh:
        fh.write(f"\n$ {' '.join(map(str, cmd))}\n"); fh.flush()
        p = subprocess.Popen(list(map(str, cmd)), cwd=cwd, env=env, stdout=fh, stderr=subprocess.STDOUT,
                             start_new_session=True)
        try:
            rc = p.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            os.killpg(p.pid, signal.SIGKILL); p.wait(); rc = "timeout"
            fh.write(f"\n[daily_run] TIMEOUT after {timeout}s\n")
    return rc, round(time.time() - t0, 1)


def site_packages(venv: Path) -> Path:
    return Path(glob.glob(str(venv / "lib" / "python3*" / "site-packages"))[0])


def base_env() -> dict:
    env = dict(os.environ, **THREAD_ENV, MPLBACKEND="Agg", PYTHONDONTWRITEBYTECODE="1", UV_LINK_MODE="copy",
               PYTHONHASHSEED="0")
    env.pop("PYTHONPATH", None)
    env.pop("GITHUB_TOKEN", None)  # never expose the token to PR code
    return env


def build_main_env(cfg: dict, venv: Path, log: Path, python: str, timeout: int) -> dict:
    """Nightly wheel of the library + stable deps from PyPI + test deps. UV_LINK_MODE=copy so patching the PR copy
    can never modify the shared uv cache."""
    env = base_env()
    steps = [
        ["uv", "venv", "-q", "-p", python, venv],
        ["uv", "pip", "install", "-q", "-p", venv / "bin/python", cfg["dist"], *cfg["deps"], *BASE_TEST_DEPS,
         *cfg["test_deps"]],
        ["uv", "pip", "install", "-q", "-p", venv / "bin/python", "--pre", "--no-deps", "--reinstall-package",
         cfg["dist"], "--index-url", NIGHTLY, cfg["dist"]],
    ]
    for c in steps:
        rc, _ = run(c, log, env=env, timeout=timeout)
        if rc != 0:
            return {"ok": False, "why": f"main env setup failed ({rc}) at: {' '.join(map(str, c[:4]))}"}
    ver = subprocess.run([venv / "bin/python", "-c", f"import {cfg['pkg']} as m;print(m.__version__)"],
                         capture_output=True, text=True, env=env).stdout.strip()
    rc, _ = run(["uv", "pip", "check", "-p", venv / "bin/python"], log, env=env, timeout=120)
    return {"ok": bool(ver), "version": ver, "pip_check": "ok" if rc == 0 else "conflicts (see setup log)",
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
    rc, _ = run(base + ["--dry-run"], log)
    if rc != 0:
        return False, "PR diff does not apply cleanly to the current nightly (main has moved or the files differ)"
    rc, _ = run(base, log)
    return rc == 0, "" if rc == 0 else "patch failed after a clean dry run"


def source_build(repo: str, item: dict, cfg: dict, venv: Path, workdir: Path, log: Path, python: str,
                 timeout: int) -> dict:
    env = base_env()
    src = workdir / "src"
    steps = [["git", "init", "-q", src],
             ["git", "-C", src, "fetch", "-q", "--depth", "1", f"https://github.com/{repo}.git",
              f"pull/{item['pr']}/head"],
             ["git", "-C", src, "checkout", "-q", "FETCH_HEAD"],
             ["git", "-C", src, "submodule", "update", "-q", "--init", "--depth", "1", "--recursive"],
             ["uv", "venv", "-q", "-p", python, venv],
             ["uv", "pip", "install", "-q", "-p", venv / "bin/python", *cfg["deps"], *BASE_TEST_DEPS, *cfg["test_deps"]]]
    for c in steps:
        rc, _ = run(c, log, env=env, timeout=900)
        if rc != 0:
            return {"ok": False, "why": f"source checkout/setup failed ({rc}) at: {' '.join(map(str, c[:3]))}"}
    t0 = time.time()
    rc, secs = run(["uv", "pip", "install", "-p", venv / "bin/python", "--no-cache", src], log, env=env, timeout=timeout)
    if rc != 0:
        tail = log.read_text(errors="replace").strip().splitlines()[-15:]
        hint = next((ln for ln in reversed(tail) if re.search(r"error|not found|ERROR", ln)), tail[-1] if tail else "")
        return {"ok": False, "build_seconds": round(time.time() - t0, 1),
                "why": f"source build of PR head {'timed out' if rc == 'timeout' else 'failed'} after {secs}s: {hint.strip()[:200]}"}
    ver = subprocess.run([venv / "bin/python", "-c", f"import {cfg['pkg']} as m;print(m.__version__)"],
                         capture_output=True, text=True, env=env, cwd=workdir).stdout.strip()
    return {"ok": bool(ver), "version": ver, "build_seconds": secs, "why": "" if ver else "built package does not import"}


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
        for cand in (f"{d}/tests/test_{stem}.py", f"{os.path.dirname(d)}/tests/test_{stem}.py"):
            add(cand)
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


def parse_junit(path: Path) -> dict:
    res = {}
    if not path.exists():
        return res
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError:
        return res
    for tc in root.iter("testcase"):
        cls = tc.get("classname") or ""
        # Make ids side-independent: drop the venv/site-packages prefix (nightly routes)
        # so main and PR runs of the same test get the same id.
        if "site-packages." in cls:
            cls = cls.split("site-packages.", 1)[1]
        tid = cls + "::" + (tc.get("name") or "")
        outcome, msg = "passed", ""
        for ch in tc:
            if ch.tag in ("failure", "error"):
                outcome = "failed" if ch.tag == "failure" else "error"
                m = (ch.get("message") or ch.text or "").strip()
                msg = m.splitlines()[0][:200] if m else ch.tag
                break
            if ch.tag == "skipped":
                outcome = "skipped"
        res[tid] = (outcome, msg)
    return res


def run_tests(side_venvs: dict, targets_by_side: dict, rdir: Path, workdir: Path, runs: int, workers: str,
              test_timeout: int, run_timeout: int, cwds: dict | None = None) -> tuple[list[dict], dict]:
    """targets are relative to site-packages (nightly routes) or to the side's checkout (cwds given)."""
    env = base_env()
    per_run, results = [], {"main": [], "pr": []}
    cwd = workdir / "cwd"; cwd.mkdir(exist_ok=True)
    for i in range(1, runs + 1):
        for side in ("main", "pr"):
            venv = side_venvs[side]
            base = cwds[side] if cwds else site_packages(venv)
            tg = [str(base / t) for t in targets_by_side[side]]
            jx = rdir / f"junit-{side}-{i}.xml"; lg = rdir / f"pytest-{side}-{i}.log"
            if not tg:
                results[side].append({}); per_run.append({"side": side, "run": i, "exit": "no-targets"}); continue
            cmd = [venv / "bin/python", "-m", "pytest", *tg, "-p", "no:cacheprovider", "-q", "-rfE",
                   f"--timeout={test_timeout}", "-o", "addopts=", "-o", "junit_family=xunit2", f"--junitxml={jx}"]
            if workers != "0":
                cmd += ["-n", workers]
            rc, secs = run(cmd, lg, cwd=(cwds[side] if cwds else cwd), env=env, timeout=run_timeout)
            parsed = parse_junit(jx)
            results[side].append(parsed)
            counts = {}
            for o, _ in parsed.values():
                counts[o] = counts.get(o, 0) + 1
            tail = (lg.read_text(errors="replace").strip().splitlines() or [""])[-1][:200]
            per_run.append({"side": side, "run": i, "exit": rc, "seconds": secs, **counts, "pytest_summary": tail})
    return per_run, results


def compare_sides(results: dict) -> dict:
    """Plain-code comparison of per-test outcomes over the 3 runs per side (poc.diff.confirm)."""
    ids = set()
    for r in results["main"] + results["pr"]:
        ids |= set(r)
    out = {"same": 0, "regressions": [], "fixed": [], "new_tests_passing": 0, "new_tests_failing": [],
           "removed_tests": [], "flaky": [], "other_changes": []}
    msgs = {}
    for t in sorted(ids):
        m = [{"o": r.get(t, ("absent", ""))[0]} for r in results["main"]]
        p = [{"o": r.get(t, ("absent", ""))[0]} for r in results["pr"]]
        state = confirm(m, p)
        if state == "same":
            out["same"] += 1; continue
        if state == "flaky":
            out["flaky"].append(t); continue
        mo, po = m[0]["o"], p[0]["o"]
        bad = ("failed", "error")
        for r in results["pr"]:
            if t in r and r[t][1]:
                msgs[t] = r[t][1]; break
        if mo == "passed" and po in bad:
            out["regressions"].append(t)
        elif mo in bad and po == "passed":
            out["fixed"].append(t)
        elif mo == "absent" and po == "passed":
            out["new_tests_passing"] += 1
        elif mo == "absent" and po in bad:
            out["new_tests_failing"].append(t)
        elif po == "absent":
            out["removed_tests"].append(t)
        else:
            out["other_changes"].append(f"{t}: {mo} -> {po}")
    out["messages"] = {t: msgs[t] for t in (out["regressions"] + out["new_tests_failing"])[:20] if t in msgs}
    return out


def verdict_for(cmp: dict | None, cnv_reason: str | None) -> tuple[str, str, list[str]]:
    """No Nemotron claim extraction yet: no claims, findings come from test differences only."""
    if cnv_reason:
        return Verdict.COULD_NOT_VERIFY.value, cnv_reason, []
    findings = []
    findings += [FindingLabel.UNMENTIONED_CHANGE] * (len(cmp["regressions"]) + len(cmp["new_tests_failing"]))
    findings += [FindingLabel.FLAKY] * len(cmp["flaky"])
    findings += [FindingLabel.NEEDS_HUMAN] * (len(cmp["removed_tests"]) + len(cmp["other_changes"]))
    findings += [FindingLabel.PROVEN] * len(cmp["fixed"])
    if cmp["same"] or cmp["new_tests_passing"]:
        findings.append(FindingLabel.NO_DIFFERENCE)
    v = pr_verdict(RunSummary(build_ok=True, claims=[Claim("tests", testable=True, probed=True, proven=True)],
                              findings=findings))
    bits = []
    if cmp["regressions"]:
        bits.append(f"{len(cmp['regressions'])} test(s) pass on main but fail on the PR")
    if cmp["new_tests_failing"]:
        bits.append(f"{len(cmp['new_tests_failing'])} new test(s) fail on the PR")
    if cmp["flaky"]:
        bits.append(f"{len(cmp['flaky'])} flaky test(s)")
    if cmp["removed_tests"]:
        bits.append(f"{len(cmp['removed_tests'])} test(s) missing on the PR side")
    if cmp["other_changes"]:
        bits.append(f"{len(cmp['other_changes'])} other outcome change(s)")
    if cmp["fixed"]:
        bits.append(f"{len(cmp['fixed'])} test(s) fail on main and pass on the PR")
    bits.append(f"{cmp['new_tests_passing']} new test(s) pass, {cmp['same']} unchanged")
    return v.value, "; ".join(bits), [f.value for f in findings]


# ---------------------------------------------------------------- per-PR driver
def test_pr(repo: str, cfg: dict, item: dict, rdir: Path, workroot: Path, a, machine: dict) -> dict:
    t0 = time.time()
    tag = f"{cfg['pkg']}-{item['pr']}"
    prdir = rdir / tag; prdir.mkdir(parents=True, exist_ok=True)
    work = workroot / tag
    shutil.rmtree(work, ignore_errors=True); work.mkdir(parents=True)
    (prdir / "pr.diff").write_text(item["diff"])
    rec = {k: item[k] for k in ("pr", "title", "url", "author", "head_sha", "base_sha", "base_ref", "updated_at_utc",
                                "updated_at_ist", "ci_state", "ci_detail")}
    rec |= {"library": cfg["dist"], "repo": repo, "tested_at_ist": now_ist().strftime("%Y-%m-%d %H:%M IST"),
            "files": {k: v for k, v in item["files"].items()}, "machine_type": machine, "thread_env": THREAD_ENV,
            "runs_per_side": a.runs, "workers": a.workers, "test_timeout_s": a.test_timeout,
            "run_timeout_s": a.run_timeout, "build_timeout_s": a.build_timeout, "python": a.python,
            "network": "allowed (installs and PR fetch); tests not network-isolated on the box",
            "posted_upstream": False}
    cnv = None
    vm, vp = work / "venv-main", work / "venv-pr"
    setup_log = prdir / "setup-main.log"
    if not cfg.get("nightly"):
        return finish(test_source_pair(repo, cfg, item, prdir, work, a, rec), prdir, work, t0)
    main = build_main_env(cfg, vm, setup_log, a.python, a.build_timeout)
    rec["main_side"] = {"source": "scientific-python nightly wheel", **{k: v for k, v in main.items() if k != "ok"}}
    if not main["ok"]:
        cnv = f"main side could not be set up: {main['why']}"
    elif item["files"]["compiled"]:
        rec["route"] = "source-build"
        b = source_build(repo, item, cfg, vp, work, prdir / "build-pr.log", a.python, a.build_timeout)
        rec["pr_side"] = {"source": f"source build of {item['head_sha'][:12]}", **{k: v for k, v in b.items() if k != "ok"}}
        rec["notes"] = ("main = nightly wheel, PR = source build of the PR head; differences can include main-branch "
                        "drift between the PR's base and the nightly")
        if not b["ok"]:
            cnv = b["why"] + " (build log: build-pr.log)"
    else:
        rec["route"] = "nightly+patch"
        shutil.copytree(vm, vp, symlinks=True)
        ok, why = apply_patch(package_diff(item["diff"], cfg["pkg"]), site_packages(vp), prdir / "patch.log")
        rec["pr_side"] = {"source": "copy of main side + PR diff applied to the installed package", "patched": ok}
        if not ok:
            cnv = why + " (see patch.log)"
    cmp = None
    if not cnv:
        tm = map_tests(item["files"], cfg["pkg"], site_packages(vm), cfg)
        tp = map_tests(item["files"], cfg["pkg"], site_packages(vp), cfg)
        targets = {"main": [t for t in dict.fromkeys(tp + tm) if (site_packages(vm) / t).exists()],
                   "pr": [t for t in dict.fromkeys(tp + tm) if (site_packages(vp) / t).exists()]}
        rec["test_targets"] = targets
        if not targets["pr"]:
            cnv = "no tests could be mapped to the touched modules"
        else:
            per_run, results = run_tests({"main": vm, "pr": vp}, targets, prdir, work, a.runs, a.workers,
                                         a.test_timeout, a.run_timeout)
            rec["per_run"] = per_run
            if any(r.get("exit") == "timeout" for r in per_run):
                cnv = f"a test run exceeded the {a.run_timeout}s run timeout"
            elif not any(results["pr"]) or not any(results["main"]):
                cnv = "tests produced no results on one side (collection failed; see pytest logs)"
            else:
                cmp = compare_sides(results)
                rec["comparison"] = cmp
    v, reason, _ = verdict_for(cmp, cnv)
    rec["verdict"], rec["reason"] = v, reason
    return finish(rec, prdir, work, t0)


def finish(rec: dict, prdir: Path, work: Path, t0: float) -> dict:
    rec["what_changed"] = {"package_python_files": rec["files"]["package_py"], "compiled_files": rec["files"]["compiled"],
                           "other_files": rec["files"]["other"]}
    rec["duration_s"] = round(time.time() - t0, 1)
    shutil.rmtree(work, ignore_errors=True)
    (prdir / "record.json").write_text(json.dumps(rec, indent=1))
    return rec


def test_source_pair(repo: str, cfg: dict, item: dict, prdir: Path, work: Path, a, rec: dict) -> dict:
    rec["route"] = "source-pair"
    for k in ("mergeable", "mergeable_state", "current_head_sha"):
        if k in item:
            rec[k] = item[k]
    if item.get("pick"):
        rec["pick"] = {k: v for k, v in item["pick"].items()}
    sp = source_pair(repo, item, work, prdir / "git.log", a.python, a.build_timeout)
    rec["sides"] = {k: v for k, v in sp.items() if k != "ok"}
    cnv, cmp = None, None
    if not sp["ok"]:
        cnv = sp["why"]
    else:
        vm, vp = work / "venv-main", work / "venv-pr"
        cm, cp = work / "side-main", work / "side-pr"
        ok, why = install_side(vm, cm, item.get("pick"), prdir / "setup-main.log", a.python, a.build_timeout, None)
        if ok:
            frz = subprocess.run(["uv", "pip", "freeze", "-p", vm / "bin/python"], capture_output=True, text=True).stdout
            pkgname = cfg["dist"].lower().replace("_", "-")
            cons = work / "constraints.txt"
            cons.write_text("\n".join(ln for ln in frz.splitlines() if ln and not ln.startswith(("-e", "#"))
                                       and ln.split("==")[0].lower().replace("_", "-") != pkgname) + "\n")
            (prdir / "freeze-main.txt").write_text(frz)
            ok, why = install_side(vp, cp, item.get("pick"), prdir / "setup-pr.log", a.python, a.build_timeout, cons)
            if ok:
                (prdir / "freeze-pr.txt").write_text(subprocess.run(["uv", "pip", "freeze", "-p", vp / "bin/python"],
                                                                    capture_output=True, text=True).stdout)
        if not ok:
            cnv = why
        else:
            tg = pick_test_targets(item.get("pick")) or map_repo_tests(item["files"], cp)
            targets = {"main": [t for t in tg if (cm / t).exists()], "pr": [t for t in tg if (cp / t).exists()]}
            rec["test_targets"] = targets
            rec["test_selection"] = "registry pick subset" if pick_test_targets(item.get("pick")) else "mapped from touched files"
            if not targets["pr"]:
                cnv = "no tests could be mapped to the touched files"
            else:
                per_run, results = run_tests({"main": vm, "pr": vp}, targets, prdir, work, a.runs, a.workers,
                                             a.test_timeout, a.run_timeout, cwds={"main": cm, "pr": cp})
                rec["per_run"] = per_run
                if any(r.get("exit") == "timeout" for r in per_run):
                    cnv = f"a test run exceeded the {a.run_timeout}s run timeout"
                elif not any(results["pr"]) or not any(results["main"]):
                    cnv = "tests produced no results on one side (collection failed; see pytest logs)"
                else:
                    cmp = compare_sides(results)
                    rec["comparison"] = cmp
    rec["verdict"], rec["reason"], _ = verdict_for(cmp, cnv)
    return rec


# ---------------------------------------------------------------- report
def score_expectation(expected: str, actual: str) -> str:
    if actual == "could_not_verify" or expected == "could_not_verify":
        return "match" if actual == expected else "not scored (could not verify)"
    if actual == expected:
        return "match"
    return "miss" if expected == "needs_attention" else "false alarm"


def write_report(rdir: Path, meta: dict, records: list[dict], skipped: dict, problems: list[str],
                 expectations: dict | None = None) -> Path:
    def line(r):
        return (f"| [{r['repo']}#{r['pr']}]({r['url']}) | {r['title'][:70]} | {r.get('route', '-')} | "
                f"**{r['verdict']}** | {r['reason'][:160]} |")
    right, wrong, fix = [], [], []
    tested = [r for r in records if r.get("per_run")]
    if records:
        right.append(f"{len(records)} PR(s) selected and recorded; every record has machine_type and thread_env.")
    complete = [r for r in tested if sum(1 for x in r["per_run"] if x["side"] == "main") == meta["runs"]
                and sum(1 for x in r["per_run"] if x["side"] == "pr") == meta["runs"]]
    if tested:
        right.append(f"{len(complete)}/{len(tested)} tested PRs have {meta['runs']} alternating runs per side.")
    right.append("Nothing was posted upstream: GitHub was only read (GET), and the token is never passed to PR code.")
    right.append("Comparison and verdicts are plain code (poc/diff.py confirm(), poc/verdict.py pr_verdict()).")
    for r in records:
        if r["verdict"] == "could_not_verify":
            wrong.append(f"{r['repo']}#{r['pr']}: could not verify: {r['reason']}")
            if "build" in r["reason"]:
                fix.append(f"{r['repo']}#{r['pr']}: provide the build toolchain (C++ compiler etc.) or a prebuilt "
                           "PR wheel; build log kept in the run folder.")
            elif "does not apply" in r["reason"]:
                fix.append(f"{r['repo']}#{r['pr']}: rebase is upstream's business; next run: source-build the PR head, "
                           "or wait for a newer nightly.")
            elif "timeout" in r["reason"]:
                fix.append(f"{r['repo']}#{r['pr']}: narrow the mapped tests or raise --run-timeout.")
            else:
                fix.append(f"{r['repo']}#{r['pr']}: inspect setup/pytest logs in the run folder.")
        elif r["verdict"] == "needs_attention":
            wrong.append(f"{r['repo']}#{r['pr']}: needs attention: {r['reason']} (a finding about the PR, not a run failure)")
            fix.append(f"{r['repo']}#{r['pr']}: a human should read the failing tests in record.json/pytest logs; "
                       "if a nightly-drift or environment cause is suspected, rerun.")
        if r.get("main_side", {}).get("pip_check", "ok") != "ok":
            wrong.append(f"{r['repo']}#{r['pr']}: pip check reported conflicts on the main side")
    for p in problems:
        wrong.append(p)
        fix.append("Harness problem: fix ops/daily_run.py and rerun this library.")
    ok_run = not problems and all(("verdict" in r) for r in records) and len(complete) == len(tested)
    rec = "APPROVE" if ok_run else "REJECT"
    md = [f"# Proof-of-Change daily ops run: {meta['date']}", "",
          f"Started {meta['started_ist']}, finished {meta['finished_ist']}, wall time {meta['wall_min']} min. "
          f"Machine: {meta['machine']}. GitHub API calls: {meta['api_calls']} ({meta['auth']}).", "",
          f"## Recommendation: **{rec}**", "",
          "The recommendation is about whether this run can be trusted, not about merging any PR. Verdicts never block merges.", "",
          "| PR | Title | Route | Verdict | Reason |", "|---|---|---|---|---|"] + [line(r) for r in records] + [""]
    md += ["## What went right", ""] + [f"- {x}" for x in right] + [""]
    md += ["## What went wrong", ""] + ([f"- {x}" for x in wrong] or ["- nothing"]) + [""]
    md += ["## How to fix", ""] + ([f"- {x}" for x in fix] or ["- no action needed"]) + [""]
    md += ["## Per PR", ""]
    for r in records:
        c = r.get("comparison") or {}
        md += [f"### {r['repo']}#{r['pr']}: {r['title']}", "",
               f"- Link: {r['url']} | author `{r['author']}` | head `{r['head_sha'][:12]}` | updated {r['updated_at_ist']}",
               f"- Upstream CI: {r['ci_state']} ({r['ci_detail']})",
               f"- Route: {r.get('route', '-')}; main: {r.get('main_side', {}).get('version', '?')} "
               f"({r.get('main_side', {}).get('source', '')}); PR: {r.get('pr_side', {}).get('source', '-')}",
               f"- Touched package files: {', '.join((r['files']['package_py'] + r['files']['compiled'])[:8])}",
               f"- Tests run: {', '.join(r.get('test_targets', {}).get('pr', [])) or '-'}",
               f"- **Verdict: {r['verdict']}**: {r['reason']}"]
        if c:
            for k in ("regressions", "new_tests_failing", "flaky", "removed_tests", "fixed"):
                if c.get(k):
                    md.append(f"  - {k}: " + ", ".join(c[k][:5]) + (f" (+{len(c[k]) - 5})" if len(c[k]) > 5 else ""))
            for t, m in list(c.get("messages", {}).items())[:3]:
                md.append(f"  - `{t}`: `{m[:150]}`")
        if r.get("per_run"):
            md.append("- Runs: " + "; ".join(f"{x['side']}#{x['run']} exit={x['exit']} {x.get('seconds', '-')}s "
                                             f"{x.get('pytest_summary', '')[:60]}" for x in r["per_run"]))
        md.append(f"- Duration: {r['duration_s']}s; logs: `{r.get('_dir', '')}/`")
        md.append("")
    if expectations:
        md += ["## Expected vs actual (registry picks)", "",
               "Expectations were read from the picks file only after all verdicts were computed; they did not influence "
               "testing or verdicts.", "", "| PR | Expected | Actual | Score |", "|---|---|---|---|"]
        for r in records:
            e = expectations.get((r["repo"], r["pr"]))
            if e:
                md.append(f"| {r['repo']}#{r['pr']} | {e} | {r['verdict']} | {score_expectation(e, r['verdict'])} |")
        md.append("")
    md += ["## Skipped while selecting", ""]
    for repo, sk in skipped.items():
        for s in sk[:12]:
            md.append(f"- {repo}#{s['pr']} ({s['updated_at_ist']}): {s['why']}: {s['title'][:70]}")
    md += ["", "## Limits of this run", "",
           "- No Nemotron claim extraction yet: 'verified' means the tests mapped to the touched modules behave the "
           "same or better on the PR than on main (3 runs per side). The PR's own claims were not checked.",
           "- Main side is the latest nightly wheel, not the PR's exact base commit; nightly+patch applies the PR "
           "diff on top of it, so a clean apply is required.",
           "- Tests ran on the box, not in Nebius Sandboxes, and were not network-isolated.", ""]
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


def default_registry() -> str:
    for cand in (os.environ.get("POC_REGISTRY"), "/workspace/blast-radius-research/registry/tracked-libraries.csv",
                 str(REPO_ROOT / "ops" / "tracked-libraries.csv")):
        if cand and Path(cand).exists():
            return cand
    raise SystemExit("no tracked-libraries CSV found; set POC_REGISTRY or pass --registry")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--registry", default=None,
                    help="tracked-libraries CSV (default: $POC_REGISTRY, else Jonathan's registry on the box if present, "
                         "else ops/tracked-libraries.csv)")
    ap.add_argument("--pr", action="append", default=[], metavar="URL",
                    help="check just this PR (https://github.com/OWNER/REPO/pull/N); repeatable. Skips the registry, "
                         "writes to ops/runs/<date>-check-<HHMM> and does not move the daily run's 'seen' state")
    ap.add_argument("--report-dir", default=None,
                    help="where the HTML/PDF reviewer reports go (default: reports/daily/<run folder name>)")
    ap.add_argument("--no-report", action="store_true", help="skip the HTML/PDF reviewer reports")
    ap.add_argument("--ops-dir", default=str(REPO_ROOT / "ops"))
    ap.add_argument("--work-dir", default=None, help="scratch for venvs/builds (default: <ops-dir>/work)")
    ap.add_argument("--date", default=None, help="run folder name (default: today IST)")
    ap.add_argument("--libraries", default=None, help="comma-separated library names to limit the run")
    ap.add_argument("--max-per-library", type=int, default=3)
    ap.add_argument("--scan-limit", type=int, default=15, help="max candidate PRs whose diff is read per library")
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--workers", default="4")
    ap.add_argument("--python", default="3.12")
    ap.add_argument("--test-timeout", type=int, default=120)
    ap.add_argument("--run-timeout", type=int, default=900)
    ap.add_argument("--build-timeout", type=int, default=1800)
    ap.add_argument("--min-free-gb", type=float, default=20)
    ap.add_argument("--picks", default=None, help="picks file (default: <registry dir>/picks/<date>.md)")
    ap.add_argument("--select-only", action="store_true")
    ap.add_argument("--resume", action="store_true", help="reuse record.json of PRs already tested in this run folder "
                                                          "(same head SHA)")
    a = ap.parse_args(argv)
    if a.runs != 3:
        print("note: protocol requires 3 runs per side; using", a.runs, file=sys.stderr)

    started = now_ist()
    single = parse_pr_urls(a.pr)
    default_name = started.strftime("%Y-%m-%d") + (started.strftime("-check-%H%M") if single else "")
    ops = Path(a.ops_dir); rdir = ops / "runs" / (a.date or default_name)
    rdir.mkdir(parents=True, exist_ok=True)
    workroot = Path(a.work_dir or ops / "work")
    seen_path = ops / "seen_prs.json"
    seen = json.loads(seen_path.read_text()) if seen_path.exists() else {"last_run_utc": {}, "prs": {}}
    free_gb = shutil.disk_usage(ops).free / 1e9
    problems = []
    if free_gb < a.min_free_gb:
        print(f"Stopped: only {free_gb:.0f} GB of free disk space; a run needs at least {a.min_free_gb:.0f} GB "
              f"(test environments are large). Free some space, or delete the {ops / 'work'} folder.", file=sys.stderr)
        return 2
    if single:  # one-off check: no registry, no picks file; Jonathan's picks never apply
        rows = [{"library": repo.split("/")[1], "repo": repo, "priority": "1"} for repo in single]
        a.registry = a.picks = str(rdir / "no-picks")
    else:
        a.registry = a.registry or default_registry()
        rows = [r for r in csv.DictReader(open(a.registry)) if r.get("status", "active") == "active"]
    rows.sort(key=lambda r: (int(r.get("priority") or 9), r.get("added_on_ist", "") and -int(r["added_on_ist"].replace("-", ""))))
    if a.libraries:
        want = set(a.libraries.split(","))
        rows = [r for r in rows if r["library"] in want]
    picks_path = Path(a.picks) if a.picks else Path(a.registry).parent / "picks" / f"{rdir.name}.md"
    picks = parse_picks(picks_path)
    gh = GitHub(None)
    machine = detect_machine_type()
    records, skipped, selection = [], {}, {}
    for row in rows:
        repo = row["repo"]
        cfg = LIBS.get(repo) or {"dist": row["library"], "pkg": row["library"].lower().replace("-", "_"), "deps": [],
                                 "test_deps": [], "nightly": False}
        try:
            if single:
                chosen, sk = pick_items(gh, repo, cfg, [{"pr": n, "head_sha": None, "install": None, "test_cmd": None}
                                                        for n in single[repo]]), []
            elif repo in picks:   # registry picks: Jonathan chose the PRs; selection filters do not apply
                chosen, sk = pick_items(gh, repo, cfg, picks[repo]), []
            else:
                sel_seen, sel_since = baseline_for(seen, repo, rdir.name)
                chosen, sk = select_prs(gh, repo, cfg, sel_seen, sel_since, a.max_per_library, a.scan_limit, None)
        except Exception as e:  # noqa: BLE001
            problems.append(f"{repo}: PR selection failed: {e}")
            continue
        skipped[repo] = sk
        selection[repo] = [{k: c[k] for k in ("pr", "title", "url", "author", "head_sha", "updated_at_ist", "ci_state")}
                           | {"route": ("source-pair" if not cfg.get("nightly") else "source-build" if c["files"]["compiled"]
                                         else "nightly+patch")} for c in chosen]
        print(f"[{repo}] priority {row.get('priority')}: selected {[c['pr'] for c in chosen]}", flush=True)
        if a.select_only:
            continue
        for c in chosen:
            prev = rdir / f"{cfg['pkg']}-{c['pr']}" / "record.json"
            if a.resume and prev.exists() and json.loads(prev.read_text()).get("head_sha") == c["head_sha"]:
                rec = json.loads(prev.read_text())
                print(f"  #{c['pr']}: reusing record from this run folder (--resume)", flush=True)
            else:
                rec = None
            print(f"  testing #{c['pr']} {c['title'][:60]} ...", flush=True) if rec is None else None
            try:
                rec = rec or test_pr(repo, cfg, c, rdir, workroot, a, machine)
            except Exception as e:  # noqa: BLE001
                problems.append(f"{repo}#{c['pr']}: harness error: {type(e).__name__}: {e}")
                continue
            rec["_dir"] = f"{cfg['pkg']}-{c['pr']}"
            records.append(rec)
            print(f"    -> {rec['verdict']}: {rec['reason'][:120]} ({rec['duration_s']}s)", flush=True)
            seen["prs"].setdefault(repo, {})[str(c["pr"])] = {"head_sha": c["head_sha"], "tested_at_ist": rec["tested_at_ist"],
                                                              "verdict": rec["verdict"], "run": rdir.name}
        if single:  # a one-off check must not move the daily run's cut-off
            continue
        if run_date_of(seen, repo) != rdir.name:   # keep the previous day's cut-off so same-day re-runs reselect
            seen.setdefault("prior_run_utc", {})[repo] = seen["last_run_utc"].get(repo)
        seen["last_run_utc"][repo] = started.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        seen.setdefault("last_run_date", {})[repo] = rdir.name
    (rdir / "selection.json").write_text(json.dumps({"selected": selection, "skipped": skipped}, indent=1))
    if a.select_only:
        print(json.dumps(selection, indent=1))
        return 0
    with open(rdir / "records.jsonl", "w") as fh:
        for r in records:
            fh.write(json.dumps(r) + "\n")
    seen_path.write_text(json.dumps(seen, indent=1))
    finished = now_ist()
    meta = {"date": rdir.name, "started_ist": started.strftime("%Y-%m-%d %H:%M IST"),
            "finished_ist": finished.strftime("%Y-%m-%d %H:%M IST"),
            "wall_min": round((finished - started).total_seconds() / 60, 1), "runs": a.runs,
            "machine": f"{machine['label']} {machine['arch']} {machine['cpu_count']} cpus",
            "api_calls": gh.calls, "auth": "token" if gh.token else "unauthenticated"}
    # Expectations are read only now, after every verdict above is final.
    expectations = read_expectations(picks_path)
    rp = write_report(rdir, meta, records, skipped, problems, expectations)
    print(f"run log: {rp}")
    if records and not a.no_report:
        from reports.pr_report import render_run
        out = Path(a.report_dir) if a.report_dir else REPO_ROOT / "reports" / "daily" / rdir.name
        render_run(rdir, out, title=f"Proof-of-Change {'check' if single else 'daily summary'}: {rdir.name}")
        print(f"\nDONE. Open this file to read the results:\n  {out / 'SUMMARY.html'}")
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
