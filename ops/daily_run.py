#!/usr/bin/env python3
"""Proof-of-Change daily run: tracked libraries -> new open PRs -> main-vs-PR test -> log + approver report.

    python3 ops/daily_run.py                       # normal daily run
    python3 ops/daily_run.py --select-only         # chosen PRs, print them, test nothing
    python3 ops/daily_run.py --max-per-library 3 --libraries numpy,pandas
    python3 ops/daily_run.py --pr https://github.com/pandas-dev/pandas/pull/12345   # check one PR (make check PR=...)
    python3 ops/daily_run.py --report-only --date 2026-10-10                       # rebuild reports, test nothing

After the run, reviewer reports (HTML, PDF, Markdown) are written to reports/daily/<run folder>/ by
reports/pr_report.py; ops/runs/<run folder>/REPORT.md stays as the operator's run log.

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
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
from harness.machine import detect_machine_type  # noqa: E402
from poc import coverage_gate, local_config  # noqa: E402
from poc.diff import confirm  # noqa: E402
from poc.verdict import Claim, FindingLabel, RunSummary, Verdict, pr_verdict  # noqa: E402

IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
NIGHTLY = "https://pypi.anaconda.org/scientific-python-nightly-wheels/simple"
PYPI = "https://pypi.org/simple"
# Same 6 vars as the shared runner (harness/schema thread_env).
THREAD_ENV = {k: "1" for k in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS",
                               "VECLIB_MAXIMUM_THREADS", "BLIS_NUM_THREADS")}
SCHEMA_PATH = REPO_ROOT / "harness" / "schema" / "observation.schema.json"
WHO = "ops/daily_run.py"
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


# ---------------------------------------------------------------- chosen PRs
def parse_chosen(path: Path) -> dict:
    """Chosen-PRs file (<date>.md, written by whoever curates the day's PRs) -> {repo: [ {pr, head_sha, install, test_cmd} ]}.

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


def chosen_items(gh: GitHub, repo: str, cfg: dict, chosen: list[dict]) -> list[dict]:
    items = []
    for pk in chosen:
        p = gh.json(f"/repos/{repo}/pulls/{pk['pr']}")
        d = gh.diff(repo, pk["pr"])
        items.append({"pr": p["number"], "title": p["title"], "url": p["html_url"], "author": p["user"]["login"],
                      "head_sha": pk["head_sha"] or p["head"]["sha"], "current_head_sha": p["head"]["sha"],
                      "base_sha": p["base"]["sha"], "base_ref": p["base"]["ref"], "updated_at_utc": p["updated_at"],
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
            parent2 = subprocess.run(["git", "-C", src, "rev-parse", f"{merge}^2"], capture_output=True,
                                     text=True).stdout.strip()
            res |= {"comparison_basis": "base tip vs GitHub test merge (refs/pull/N/merge)", "main_sha": parent1,
                    "pr_sha": merge, "merge_commit": merge, "merge_parents": [parent1, parent2],
                    "merge_head_matches_pinned_head": parent2 == head}
    for side in ("main", "pr"):
        rc, _ = run(["git", "-C", src, "worktree", "add", "-q", "--detach", work / f"side-{side}", res[f"{side}_sha"]],
                    log, env=env, timeout=900)
        if rc != 0:
            return {"ok": False, "why": f"checkout of {side} side failed"}
    res["ok"] = True
    return res


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


def install_side(venv: Path, checkout: Path, chosen: dict | None, log: Path, python: str, timeout: int,
                 constraints: Path | None) -> tuple[bool, str]:
    env = base_env()
    if subprocess.run(["git", "-C", checkout, "describe", "--tags"], capture_output=True).returncode != 0:
        env["SETUPTOOLS_SCM_PRETEND_VERSION"] = "9999.0.0"
    proj, extra = side_install_args(chosen, checkout)
    proj = with_test_extras(proj, checkout)
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
        out = subprocess.run([venv / "bin/python", "-c", cfg["commit_expr"]], capture_output=True, text=True,
                             env=env, cwd=venv).stdout.strip()
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
    out = subprocess.run([venv / "bin/python", "-c", code], capture_output=True, text=True, env=env, cwd=venv).stdout
    return [x.strip() for x in out.splitlines() if x.strip()]


def freeze(venv: Path, out: Path) -> str:
    txt = subprocess.run(["uv", "pip", "freeze", "-p", venv / "bin/python"], capture_output=True, text=True).stdout
    out.write_text(txt)
    return out.name


def build_main_env(cfg: dict, venv: Path, log: Path, python: str, timeout: int, wheel_dir: Path) -> dict:
    """Stable release of the library with its test extra + test deps + optional test deps (so tests do not skip for
    missing optional modules), then the exact nightly wheel file, pinned by sha256, reinstalled without deps.
    UV_LINK_MODE=copy so patching the PR copy can never modify the shared uv cache."""
    env = base_env()
    py = venv / "bin/python"
    steps = [["uv", "venv", "-q", "-p", python, venv],
             ["uv", "pip", "install", "-q", "-p", py, cfg["dist"], *cfg["deps"], *BASE_TEST_DEPS, *cfg["test_deps"]]]
    for c in steps:
        rc, _ = run(c, log, env=env, timeout=timeout)
        if rc != 0:
            return {"ok": False, "why": f"main env setup failed ({rc}) at: {' '.join(map(str, c[:4]))}"}
    extras = test_extras(dist_extras(venv, cfg["dist"], env))
    opt = list(cfg.get("optional_test_deps", []))
    if extras or opt:
        spec = f"{cfg['dist']}[{','.join(extras)}]" if extras else cfg["dist"]
        rc, _ = run(["uv", "pip", "install", "-q", "-p", py, spec, *opt], log, env=env, timeout=timeout)
        if rc != 0:
            return {"ok": False, "why": f"installing test extras/optional test deps failed ({rc}); see setup log"}
    try:
        whl = fetch_wheel(nightly_wheel(lambda u: urllib.request.urlopen(
            urllib.request.Request(u, headers={"User-Agent": "proof-of-change-ops"}), timeout=120).read(),
            cfg["dist"], python), wheel_dir)
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "why": f"could not fetch the nightly wheel: {e}"}
    rc, _ = run(["uv", "pip", "install", "-q", "-p", py, "--no-deps", "--reinstall", whl["path"]], log, env=env,
                timeout=timeout)
    if rc != 0:
        return {"ok": False, "why": f"installing the nightly wheel failed ({rc})"}
    ver = subprocess.run([py, "-c", f"import {cfg['pkg']} as m;print(m.__version__)"],
                         capture_output=True, text=True, env=env, cwd=venv).stdout.strip()
    commit, how = nightly_commit(whl["version"], venv, cfg, env)
    rc, _ = run(["uv", "pip", "check", "-p", py], log, env=env, timeout=120)
    whl.pop("path")
    return {"ok": bool(ver), "version": ver, "pip_check": "ok" if rc == 0 else "conflicts (see setup log)",
            "build": whl | {"commit": commit, "commit_source": how},
            "test_extras": extras, "optional_test_deps": opt,
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
                 timeout: int, main_extra_reqs: tuple = ()) -> dict:
    env = base_env()
    src = workdir / "src"
    steps = [["git", "init", "-q", src],
             ["git", "-C", src, "fetch", "-q", "--depth", "1", f"https://github.com/{repo}.git",
              f"pull/{item['pr']}/head"],
             ["git", "-C", src, "checkout", "-q", "FETCH_HEAD"],
             ["git", "-C", src, "submodule", "update", "-q", "--init", "--depth", "1", "--recursive"],
             ["uv", "venv", "-q", "-p", python, venv],
             ["uv", "pip", "install", "-q", "-p", venv / "bin/python", *cfg["deps"], *BASE_TEST_DEPS, *cfg["test_deps"],
              *cfg.get("optional_test_deps", []), *main_extra_reqs]]
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
MISSING_DEP_RE = re.compile(
    r"could not import '?([\w.]+)'?|no module named '?([\w.]+)'?|requires? (?:the )?'?([\w.-]+)'?(?: to be installed| is not installed)?$"
    r"|'?([\w.-]+)'? (?:is )?not installed", re.I)


def parse_junit(path: Path) -> dict:
    """{test id: (outcome, message)}. outcome: passed | failed | error | skipped (pytest.skip and xfail).
    Skip messages are kept as '<type>: <message>' so missing-dependency skips can be recognised."""
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


def run_tests(side_venvs: dict, targets_by_side: dict, rdir: Path, workdir: Path, runs: int, workers: str,
              test_timeout: int, run_timeout: int, cwds: dict | None = None) -> tuple[list[dict], dict]:
    """targets are relative to site-packages (nightly routes) or to the side's checkout (cwds given).
    per_run entries use the shared schema shape (side old/new, all counts present)."""
    env = base_env()
    per_run, results = [], {"main": [], "pr": []}
    cwd = workdir / "cwd"; cwd.mkdir(exist_ok=True)
    for i in range(1, runs + 1):
        for side in ("main", "pr"):
            venv = side_venvs[side]
            base = cwds[side] if cwds else site_packages(venv)
            tg = [str(base / t) for t in targets_by_side[side]]
            jx = rdir / f"junit-{side}-{i}.xml"; lg = rdir / f"pytest-{side}-{i}.log"
            entry = {"side": SIDE_KEY[side], "run": i, "passed": 0, "failed": 0, "error": 0, "skipped": 0,
                     "collection_errors": 0}
            if not tg:
                results[side].append({}); per_run.append(entry | {"exit": "no-targets", "seconds": 0,
                                                                   "pytest_summary": "", "junit": False}); continue
            cmd = [venv / "bin/python", "-m", "pytest", *tg, "-p", "no:cacheprovider", "-q", "-rfE",
                   f"--timeout={test_timeout}", "-o", "addopts=", "-o", "junit_family=xunit2", f"--junitxml={jx}"]
            if workers != "0":
                cmd += ["-n", workers]
            rc, secs = run(cmd, lg, cwd=(cwds[side] if cwds else cwd), env=env, timeout=run_timeout)
            parsed = parse_junit(jx)
            results[side].append(parsed)
            for o, _ in parsed.values():
                entry[o] += 1
            text = lg.read_text(errors="replace")
            entry["collection_errors"] = len(re.findall(r"^ERROR collecting ", text, re.M))
            tail = (text.strip().splitlines() or [""])[-1][:200]
            per_run.append(entry | {"exit": rc, "seconds": secs, "pytest_summary": tail, "junit": jx.exists()})
    return per_run, results


def coverage_run(item: dict, venv: Path, main_root: Path, pr_root: Path, targets: list[str], prdir: Path,
                 workdir: Path, a, cwd: Path | None = None) -> dict:
    """Coverage gate measurement: ONE extra, untimed PR-side run of the same test subset under coverage.py
    (pytest-cov, so it also works with -n workers), after the 3 timed runs, so their timings stay clean.

    Changed lines are found by diffing the main-side file against the PR-side file that was actually tested (exact for
    every route, including a diff applied with offsets); executable lines are coverage.py's executed + missing lines.
    main_root / pr_root: the folder the PR's repo-relative paths resolve against on each side (site-packages for the
    nightly routes, the checkout for source-pair)."""
    if getattr(a, "no_coverage", False):
        return {"status": "skipped", "why": "--no-coverage"}
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
                                                   new.read_text(errors="replace"))
        sources.add(str(new.parent))
    if not changed:
        return {"status": "failed", "why": "none of the changed Python files exist on the PR side"}
    log = prdir / "coverage-pr.log"
    rc, _ = run(["uv", "pip", "install", "-q", "-p", venv / "bin/python", "coverage>=7", "pytest-cov>=5"], log,
                timeout=600)
    if rc != 0:
        return {"status": "failed", "why": f"installing coverage failed ({rc}); see coverage-pr.log"}
    out = prdir / "coverage-pr.json"
    base = cwd or pr_root
    cmd = [venv / "bin/python", "-m", "pytest", *[str(base / t) for t in targets], "-p", "no:cacheprovider", "-q",
           f"--timeout={a.test_timeout}", "-o", "addopts=", *[f"--cov={s}" for s in sorted(sources)],
           f"--cov-report=json:{out}"]
    if a.workers != "0":
        cmd += ["-n", a.workers]
    (workdir / "cwd").mkdir(exist_ok=True)
    rc, secs = run(cmd, prdir / "coverage-pytest.log", cwd=cwd or (workdir / "cwd"), env=base_env(),
                   timeout=a.run_timeout)
    if not out.exists():
        return {"status": "failed", "why": f"coverage run produced no data (exit {rc}); see coverage-pytest.log",
                "seconds": secs}
    res = coverage_gate.measure(changed, json.loads(out.read_text()).get("files", {}))
    return res | {"seconds": secs, "exit": rc, "log": "coverage-pytest.log"}


def gate(rec: dict) -> dict:
    """Apply the coverage gate (poc/coverage_gate.py) to a finished record."""
    return coverage_gate.apply(rec)


def base_name(test_id: str) -> str:
    """'mod.Class::test_x[a-1]' -> 'mod.Class::test_x' (the test function, without its parametrize id)."""
    return test_id.split("[", 1)[0]


def compare_sides(results: dict) -> dict:
    """Plain-code comparison of per-test outcomes over the 3 runs per side (poc.diff.confirm).

    Rename-aware: a test id that disappears is only 'removed' if no new id with the same base test name appeared.
    Otherwise it is re-parametrized (its parametrize ids changed); the new ids are judged by their own outcomes.
    New/changed tests that are skipped because an optional dependency is missing are listed separately."""
    ids = set()
    for r in results["main"] + results["pr"]:
        ids |= set(r)
    out = {"same": 0, "regressions": [], "fixed": [], "new_tests_passing": 0, "new_tests_failing": [],
           "removed_tests": [], "reparametrized": [], "skipped_missing_dependency": [], "flaky": [],
           "other_changes": [], "preexisting_failures": []}
    msgs, removed, added = {}, [], []
    bad = ("failed", "error")
    for t in sorted(ids):
        m = [{"o": r.get(t, ("absent", ""))[0]} for r in results["main"]]
        p = [{"o": r.get(t, ("absent", ""))[0]} for r in results["pr"]]
        state = confirm(m, p)
        if state == "same":
            out["same"] += 1
            if m[0]["o"] in bad:
                out["preexisting_failures"].append(t)
            continue
        if state == "flaky":
            out["flaky"].append(t); continue
        mo, po = m[0]["o"], p[0]["o"]
        pmsg = next((r[t][1] for r in results["pr"] if t in r and r[t][1]), "")
        if po in bad and pmsg:
            msgs[t] = pmsg
        if mo == "absent":
            added.append(t)
        if po == "skipped" and mo != "skipped" and missing_dependency(pmsg):
            out["skipped_missing_dependency"].append({"test": t, "module": missing_dependency(pmsg), "main": mo})
        elif mo == "passed" and po in bad:
            out["regressions"].append(t)
        elif mo in bad and po == "passed":
            out["fixed"].append(t)
        elif mo == "absent" and po == "passed":
            out["new_tests_passing"] += 1
        elif mo == "absent" and po in bad:
            out["new_tests_failing"].append(t)
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
    out["messages"] = {t: msgs[t] for t in (out["regressions"] + out["new_tests_failing"])[:20] if t in msgs}
    return out


def failing_ids(run_result: dict) -> set:
    return {t for t, (o, _) in run_result.items() if o in ("failed", "error")}


def exit_check(per_run: list[dict], results: dict, cmp: dict) -> dict:
    """Is every non-zero pytest exit explained? Exit 1 on a run is explained when each failing test of that run fails
    identically on the other side's run with the same index, or is already a reported finding (regression, new
    failing test, flaky). Any other exit code (interrupted, internal or usage error) is never explained."""
    flagged = set(cmp["regressions"]) | set(cmp["new_tests_failing"]) | set(cmp["flaky"])
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


def verdict_for(cmp: dict | None, cnv_reason: str | None, exits: dict | None = None) -> tuple[str, str, list[str]]:
    """No Nemotron claim extraction yet: no claims, findings come from test differences only.

    Order: could-not-verify reasons of the run; real findings (regressions, new failing tests) -> needs attention;
    unexplained pytest exit codes -> could not verify; new/changed tests skipped for a missing optional dependency
    -> could not verify (the change was not exercised; never needs attention); otherwise poc.verdict.pr_verdict."""
    if cnv_reason:
        return Verdict.COULD_NOT_VERIFY.value, cnv_reason, []
    deps = sorted({d["module"] for d in cmp.get("skipped_missing_dependency", [])})
    dep_note = (f"{len(cmp['skipped_missing_dependency'])} new/changed test(s) skipped because optional "
                f"dependenc{'y' if len(deps) == 1 else 'ies'} {', '.join(deps)} not installed") if deps else ""
    findings = []
    findings += [FindingLabel.UNMENTIONED_CHANGE] * (len(cmp["regressions"]) + len(cmp["new_tests_failing"]))
    findings += [FindingLabel.FLAKY] * len(cmp["flaky"])
    findings += [FindingLabel.NEEDS_HUMAN] * (len(cmp["removed_tests"]) + len(cmp["other_changes"]))
    findings += [FindingLabel.PROVEN] * len(cmp["fixed"])
    if cmp["same"] or cmp["new_tests_passing"]:
        findings.append(FindingLabel.NO_DIFFERENCE)
    bits = []
    if cmp["regressions"]:
        bits.append(f"{len(cmp['regressions'])} test(s) pass on main but fail on the PR")
    if cmp["new_tests_failing"]:
        bits.append(f"{len(cmp['new_tests_failing'])} new test(s) fail on the PR")
    if cmp["flaky"]:
        bits.append(f"{len(cmp['flaky'])} flaky test(s)")
    if cmp["removed_tests"]:
        bits.append(f"{len(cmp['removed_tests'])} test(s) removed on the PR side")
    if cmp["other_changes"]:
        bits.append(f"{len(cmp['other_changes'])} other outcome change(s)")
    if cmp["fixed"]:
        bits.append(f"{len(cmp['fixed'])} test(s) fail on main and pass on the PR")
    if cmp.get("reparametrized"):
        n_old = sum(len(x["removed_ids"]) for x in cmp["reparametrized"])
        n_new = sum(len(x["added_ids"]) for x in cmp["reparametrized"])
        bits.append(f"{len(cmp['reparametrized'])} test(s) re-parametrized ({n_old} -> {n_new} ids)")
    bits.append(f"{cmp['new_tests_passing']} new test(s) pass, {cmp['same']} unchanged")
    pre = cmp.get("preexisting_failures", [])
    uncollected = [t[2:] for t in pre if t.startswith("::")]   # JUnit collection errors have an empty classname
    if len(pre) > len(uncollected):
        bits.append(f"{len(pre) - len(uncollected)} test failure(s) pre-existing and identical on both sides")
    if uncollected:
        bits.append(f"{len(uncollected)} test module(s) fail to collect on both sides ({', '.join(uncollected[:3])}), "
                    "so their tests did not run")
    reason = "; ".join(bits)
    if cmp["regressions"] or cmp["new_tests_failing"]:
        v = pr_verdict(RunSummary(build_ok=True, claims=[Claim("tests", testable=True, probed=True, proven=True)],
                                  findings=findings))
        return v.value, reason + (f"; {dep_note}" if dep_note else ""), [f.value for f in findings]
    if exits and not exits["explained"]:
        return (Verdict.COULD_NOT_VERIFY.value,
                "pytest exit code(s) not explained by identical failures on both sides: " + "; ".join(exits["problems"][:3])
                + f" ({reason})", [f.value for f in findings])
    if dep_note:
        return Verdict.COULD_NOT_VERIFY.value, f"not fully verified: {dep_note} ({reason})", [f.value for f in findings]

    v = pr_verdict(RunSummary(build_ok=True, claims=[Claim("tests", testable=True, probed=True, proven=True)],
                              findings=findings))
    return v.value, reason, [f.value for f in findings]


# ---------------------------------------------------------------- per-PR driver
def new_record(repo: str, cfg: dict, item: dict, a, machine: dict, run_date: str) -> dict:
    """PR-run record (record_kind 'pr_run' of the shared observation schema, harness/schema/observation.schema.json)."""
    tested = now_ist()
    rec = {"schema_version": "1", "record_kind": "pr_run",
           "id": f"pr-{repo.replace('/', '-')}-{item['pr']}-{item['head_sha'][:12]}-{run_date}",
           "date_ist": tested.strftime("%Y-%m-%d %H:%M IST"), "run_date": run_date[:10], "who": WHO, "repo": repo, "library": cfg["dist"],
           "pr": {"repo": repo, "number": item["pr"], "url": item["url"], "title": item["title"],
                  "base_sha": item.get("base_sha"), "head_sha": item["head_sha"], "merge_commit": None},
           "author": item["author"], "base_ref": item["base_ref"], "updated_at_utc": item["updated_at_utc"],
           "updated_at_ist": item["updated_at_ist"], "ci_state": item["ci_state"], "ci_detail": item["ci_detail"],
           "tested_at_ist": tested.strftime("%Y-%m-%d %H:%M IST"),
           "files": dict(item["files"]), "machine_type": machine, "thread_env": dict(THREAD_ENV),
           "runs_per_side": 0, "runs_per_side_planned": a.runs, "workers": str(a.workers),
           "test_timeout_s": a.test_timeout, "run_timeout_s": a.run_timeout, "build_timeout_s": a.build_timeout,
           "python": getattr(a, "python_full", None) or a.python, "test_selection": "", "per_run": [], "notes": None,
           "network": "allowed (installs and PR fetch); tests not network-isolated",
           "posted_upstream": False, "logs": f"{cfg['pkg']}-{item['pr']}/", "freeze": {}}
    rec["route"] = ("source-pair" if not cfg.get("nightly") else
                    "source-build" if item["files"]["compiled"] else "nightly+patch")
    for k in ("head_moved", "current_head_sha", "frozen_from", "state", "mergeable", "mergeable_state"):
        if item.get(k) is not None:
            rec[k] = item[k]
    return rec


def venv_python_version(venv: Path) -> str | None:
    out = subprocess.run([venv / "bin/python", "-c", "import platform;print(platform.python_version())"],
                         capture_output=True, text=True).stdout.strip()
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


def confirm_missing(cmp: dict, venv: Path) -> None:
    """Keep a dependency skip only if the module really does not import on the PR side; otherwise it is an ordinary
    outcome change."""
    keep = []
    for d in cmp.get("skipped_missing_dependency", []):
        ok = subprocess.run([venv / "bin/python", "-c", f"import importlib.util as u,sys;"
                             f"sys.exit(0 if u.find_spec({d['module']!r}) is None else 1)"],
                            capture_output=True, cwd=venv).returncode == 0
        if ok:
            keep.append(d)
        else:
            cmp["other_changes"].append(f"{d['test']}: {d['main']} -> skipped (skip names {d['module']}, which is installed)")
    cmp["skipped_missing_dependency"] = keep


def test_pr(repo: str, cfg: dict, item: dict, rdir: Path, workroot: Path, a, machine: dict) -> dict:
    t0 = time.time()
    tag = f"{cfg['pkg']}-{item['pr']}"
    prdir = rdir / tag; prdir.mkdir(parents=True, exist_ok=True)
    work = workroot / tag
    shutil.rmtree(work, ignore_errors=True); work.mkdir(parents=True)
    (prdir / "pr.diff").write_text(item["diff"])
    rec = new_record(repo, cfg, item, a, machine, rdir.name)
    if not cfg.get("nightly"):
        return finish(test_source_pair(repo, cfg, item, prdir, work, a, rec), prdir, work, t0)
    cnv, ex = None, None
    vm, vp = work / "venv-main", work / "venv-pr"
    main = build_main_env(cfg, vm, prdir / "setup-main.log", a.python, a.build_timeout, workroot / "wheels" / rdir.name)
    rec["main_side"] = {"source": "scientific-python nightly wheel (exact file, pinned by sha256)",
                        **{k: v for k, v in main.items() if k not in ("ok",)}}
    if main.get("build"):
        rec["main_build"] = main["build"]
    rec["python"] = venv_python_version(vm) or rec["python"]
    if not main["ok"]:
        cnv = f"main side could not be set up: {main['why']}"
    else:
        rec["freeze"]["main"] = freeze(vm, prdir / "freeze-main.txt")
        if item["files"]["compiled"]:
            rec["route"] = "source-build"
            extra = [f"{cfg['dist']}[{','.join(main['test_extras'])}]"] if main.get("test_extras") else []
            b = source_build(repo, item, cfg, vp, work, prdir / "build-pr.log", a.python, a.build_timeout, tuple(extra))
            rec["pr_side"] = {"source": f"source build of {item['head_sha'][:12]}",
                              **{k: v for k, v in b.items() if k != "ok"}}
            rec["notes"] = ("main = nightly wheel, PR = source build of the PR head; differences can include "
                            "main-branch drift between the PR's base and the nightly")
            if not b["ok"]:
                cnv = b["why"] + " (build log: build-pr.log)"
        else:
            rec["route"] = "nightly+patch"
            shutil.copytree(vm, vp, symlinks=True)
            ok, why = apply_patch(package_diff(item["diff"], cfg["pkg"]), site_packages(vp), prdir / "patch.log")
            rec["pr_side"] = {"source": "copy of main side + PR diff applied to the installed package", "patched": ok}
            if not ok:
                cnv = why + " (see patch.log)"
        if vp.exists():
            rec["freeze"]["pr"] = freeze(vp, prdir / "freeze-pr.txt")
    rec["tested"] = {"main": f"nightly {main.get('version', '?')} "
                             f"(commit {(main.get('build') or {}).get('commit') or 'unknown'}, "
                             f"sha256 {((main.get('build') or {}).get('sha256') or '?')[:12]})",
                     "pr": (f"PR head {item['head_sha'][:12]} " +
                            ("built from source" if rec.get("route") == "source-build" else "diff applied to that nightly"))}
    cmp = None
    if not cnv:
        tm = map_tests(item["files"], cfg["pkg"], site_packages(vm), cfg)
        tp = map_tests(item["files"], cfg["pkg"], site_packages(vp), cfg)
        targets = {"main": [t for t in dict.fromkeys(tp + tm) if (site_packages(vm) / t).exists()],
                   "pr": [t for t in dict.fromkeys(tp + tm) if (site_packages(vp) / t).exists()]}
        rec["test_targets"] = targets
        rec["test_selection"] = "mapped from touched modules: " + ", ".join(targets["pr"])
        if not targets["pr"]:
            cnv = "no tests could be mapped to the touched modules"
        else:
            per_run, results = run_tests({"main": vm, "pr": vp}, targets, prdir, work, a.runs, a.workers,
                                         a.test_timeout, a.run_timeout)
            cmp, cnv, ex = finalize_tests(rec, per_run, results, a)
            if cmp:
                confirm_missing(cmp, vp)
                rec["coverage"] = coverage_run(item, vp, site_packages(vm), site_packages(vp), targets["pr"], prdir,
                                               work, a)
    rec["verdict"], rec["reason"], _ = verdict_for(cmp, cnv, ex)
    return finish(gate(rec), prdir, work, t0)


def finish(rec: dict, prdir: Path, work: Path, t0: float) -> dict:
    rec["what_changed"] = {"package_python_files": rec["files"]["package_py"], "compiled_files": rec["files"]["compiled"],
                           "other_files": rec["files"]["other"]}
    rec["duration_s"] = {"total_wall": round(time.time() - t0, 1),
                         "tests": round(sum(e.get("seconds") or 0 for e in rec.get("per_run", [])), 1)}
    if rec.get("pr_side", {}).get("build_seconds") is not None:
        rec["duration_s"]["build"] = rec["pr_side"]["build_seconds"]
    errs = validate_record(rec)
    if errs:
        rec["schema_errors"] = errs[:20]
    shutil.rmtree(work, ignore_errors=True)
    (prdir / "record.json").write_text(json.dumps(rec, indent=1))
    return rec


def validate_record(rec: dict) -> list[str]:
    try:
        from ops.schema_check import validate
        return validate(rec, json.loads(SCHEMA_PATH.read_text()))
    except FileNotFoundError:
        return [f"schema not found at {SCHEMA_PATH}"]


def test_source_pair(repo: str, cfg: dict, item: dict, prdir: Path, work: Path, a, rec: dict) -> dict:
    rec["route"] = "source-pair"
    if item.get("chosen"):
        rec["chosen"] = {k: v for k, v in item["chosen"].items()}
    sp = source_pair(repo, item, work, prdir / "git.log", a.python, a.build_timeout)
    rec["sides"] = {k: v for k, v in sp.items() if k != "ok"}
    if sp.get("merge_commit"):
        rec["pr"]["merge_commit"] = sp["merge_commit"]
    if sp.get("ok"):
        rec["tested"] = {"main": f"{item['base_ref']} @ {sp['main_sha'][:12]}"
                                 + (" (merge-base with the PR head)" if "merge-base" in sp["comparison_basis"]
                                    else " (base tip = first parent of the merge commit)"),
                         "pr": (f"GitHub test merge commit {sp['merge_commit'][:12]} (refs/pull/{item['pr']}/merge) of head "
                                f"{item['head_sha'][:12]}" if sp.get("merge_commit") else f"PR head {sp['pr_sha'][:12]}")}
    cnv, cmp, ex = None, None, None
    if not sp["ok"]:
        cnv = sp["why"]
    else:
        vm, vp = work / "venv-main", work / "venv-pr"
        cm, cp = work / "side-main", work / "side-pr"
        ok, why = install_side(vm, cm, item.get("chosen"), prdir / "setup-main.log", a.python, a.build_timeout, None)
        if ok:
            rec["python"] = venv_python_version(vm) or rec["python"]
            frz = subprocess.run(["uv", "pip", "freeze", "-p", vm / "bin/python"], capture_output=True, text=True).stdout
            pkgname = cfg["dist"].lower().replace("_", "-")
            cons = work / "constraints.txt"
            cons.write_text("\n".join(ln for ln in frz.splitlines() if ln and not ln.startswith(("-e", "#"))
                                       and ln.split("==")[0].lower().replace("_", "-") != pkgname) + "\n")
            rec["freeze"]["main"] = freeze(vm, prdir / "freeze-main.txt")
            rec["test_extras"] = pyproject_test_extras(cm)
            ok, why = install_side(vp, cp, item.get("chosen"), prdir / "setup-pr.log", a.python, a.build_timeout, cons)
            if ok:
                rec["freeze"]["pr"] = freeze(vp, prdir / "freeze-pr.txt")
        if not ok:
            cnv = why
        else:
            tg = chosen_test_targets(item.get("chosen")) or map_repo_tests(item["files"], cp)
            targets = {"main": [t for t in tg if (cm / t).exists()], "pr": [t for t in tg if (cp / t).exists()]}
            rec["test_targets"] = targets
            rec["test_selection"] = ("chosen-PR subset: " if chosen_test_targets(item.get("chosen"))
                                     else "mapped from touched files: ") + ", ".join(targets["pr"])
            if not targets["pr"]:
                cnv = "no tests could be mapped to the touched files"
            else:
                per_run, results = run_tests({"main": vm, "pr": vp}, targets, prdir, work, a.runs, a.workers,
                                             a.test_timeout, a.run_timeout, cwds={"main": cm, "pr": cp})
                cmp, cnv, ex = finalize_tests(rec, per_run, results, a)
                if cmp:
                    confirm_missing(cmp, vp)
                    rec["coverage"] = coverage_run(item, vp, cm, cp, targets["pr"], prdir, work, a, cwd=cp)
    rec["verdict"], rec["reason"], _ = verdict_for(cmp, cnv, ex)
    return gate(rec)


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
        items.append({"pr": n, "title": p["title"], "url": p["html_url"], "author": p["user"]["login"],
                      "head_sha": pinned, "current_head_sha": p["head"]["sha"], "head_moved": moved,
                      "base_sha": p["base"]["sha"], "base_ref": p["base"]["ref"], "updated_at_utc": p["updated_at"],
                      "updated_at_ist": to_ist(p["updated_at"]), "files": classify_files(diff_files(d), cfg["pkg"]),
                      "diff": d, "state": p.get("state"), "ci_state": state, "ci_detail": detail,
                      "frozen_from": it.get("first_attempt")})
    return items


def read_verification(path: Path) -> dict:
    """Independent verification lines (verification.jsonl): {(repo, pr): (verdict, checker, note)} for entries with a
    verdict. Call ONLY after all verdicts are final."""
    out = {}
    if not path or not path.exists():
        return out
    for ln in path.read_text().splitlines():
        if not ln.strip():
            continue
        v = json.loads(ln)
        verdict = next((v[k] for k in v if k.endswith("_verdict") and v[k]), None) or v.get("verdict")
        if verdict and v.get("status") != "unverified":   # only PRs the checker actually re-checked
            out[(v["repo"], int(v["pr"]))] = (verdict, v.get("checked_by", "?"), v.get("note", ""))
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
    counts: dict = {}
    for r in records:
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


def write_report(rdir: Path, meta: dict, records: list[dict], skipped: dict, problems: list[str],
                 expectations: dict | None = None, verification: dict | None = None,
                 history: list[dict] | None = None) -> Path:
    def line(r):
        return (f"| [{r['repo']}#{prn(r)}]({r['pr']['url']}) | {r['pr']['title'][:70]} | {r.get('route', '-')} | "
                f"**{r['verdict']}** | {r['reason'][:200]} |")
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
        if r["verdict"] == "could_not_verify":
            wrong.append(f"{tag}: could not verify: {r['reason']}")
            if r["reason"].startswith("not fully verified: compiled"):
                fix.append(f"{tag}: compiled change without a test for it; a human should check it, or the PR should "
                           "add a test that calls the changed module.")
            elif r["reason"].startswith("not fully verified"):
                fix.append(f"{tag}: the mapped tests never ran the changed lines; widen the test mapping or ask "
                           "for a test that exercises the change.")
            elif "build" in r["reason"]:
                fix.append(f"{tag}: check build-pr.log (toolchain, build deps) or raise --build-timeout.")
            elif "optional dependenc" in r["reason"]:
                fix.append(f"{tag}: add the named module(s) to optional_test_deps for this library and rerun.")
            elif "exit code" in r["reason"]:
                fix.append(f"{tag}: read the pytest logs; the run did not finish cleanly on one side.")
            elif "does not apply" in r["reason"]:
                fix.append(f"{tag}: next run: source-build the PR head, or wait for a newer nightly.")
            elif "timeout" in r["reason"]:
                fix.append(f"{tag}: narrow the mapped tests or raise --run-timeout.")
            else:
                fix.append(f"{tag}: inspect setup/pytest logs in the run folder.")
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
          f"Runner: ops/daily_run.py @ {meta.get('git', '?')}.", "",
          f"## Recommendation: **{rec}**", "",
          "The recommendation is about whether this run can be trusted, not about merging any PR. Verdicts never block merges.", "",
          "| PR | Title | Route | Verdict | Reason |", "|---|---|---|---|---|"] + [line(r) for r in records] + [""]
    md += ["## What went right", ""] + [f"- {x}" for x in right] + [""]
    md += ["## What went wrong", ""] + ([f"- {x}" for x in wrong] or ["- nothing"]) + [""]
    md += ["## How to fix", ""] + ([f"- {x}" for x in fix] or ["- no action needed"]) + [""]
    if history:
        md += ["## Re-runs", "",
               "Earlier attempts of this run date are kept under `superseded/attempt-N/` (records, logs, NOTE.md). "
               "The day's PR selection is frozen: this attempt re-tests every PR that any earlier attempt selected.", ""]
        final = {(r["repo"], prn(r)): r["verdict"] for r in records}
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
        if r.get("tested"):
            md.append(f"- Tested: main = {r['tested']['main']}; PR = {r['tested']['pr']}")
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
               f"- **Verdict: {r['verdict']}**: {r['reason']}"]
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
                md.append(f"  - skipped for a missing optional dependency: {len(deps)} "
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
    return (Path(d) if d else Path(a.libraries_file).parent / "verification") / rdir.name / "verification.jsonl"


def main(argv=None) -> int:
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
    ap.add_argument("--test-timeout", type=int, default=120)
    ap.add_argument("--run-timeout", type=int, default=900)
    ap.add_argument("--build-timeout", type=int, default=1800)
    ap.add_argument("--min-free-gb", type=float, default=20)
    ap.add_argument("--chosen-prs", default=None,
                    help="file naming the PRs to test today, per library (default: <chosen_prs_dir>/<date>.md, see "
                         "poc/local_config.py)")
    ap.add_argument("--verification", default=None,
                    help="independent verification jsonl, scored after verdicts (default: "
                         "<verification_dir>/<date>/verification.jsonl if it exists)")
    ap.add_argument("--select-only", action="store_true")
    ap.add_argument("--resume", action="store_true", help="reuse record.json of PRs already tested in this run folder "
                                                          "(same head SHA)")
    ap.add_argument("--reselect", action="store_true",
                    help="same-day re-run: select afresh instead of re-testing the frozen selection of earlier attempts")
    ap.add_argument("--rerun-note", default=None, help="why the previous attempt is superseded (kept in its NOTE.md)")
    ap.add_argument("--report-only", action="store_true",
                    help="rebuild REPORT.md from records.jsonl, selection.json and run_meta.json; test nothing")
    a = ap.parse_args(argv)
    if a.runs != 3:
        print("note: protocol requires 3 runs per side; using", a.runs, file=sys.stderr)

    started = now_ist()
    single = parse_pr_urls(a.pr)
    default_name = started.strftime("%Y-%m-%d") + (started.strftime("-check-%H%M") if single else "")
    ops = Path(a.ops_dir); rdir = ops / "runs" / (a.date or default_name)
    if single:  # one-off check: no library list, chosen-PRs or verification file apply
        a.libraries_file = str(rdir / "no-libraries.csv")
        a.chosen_prs = str(rdir / "no-chosen-prs.md")
        a.verification = str(rdir / "no-verification.jsonl")
    else:
        a.libraries_file = a.libraries_file or default_libraries_file()
    if a.report_only:
        return report_only(rdir, a)
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
    gh = GitHub(None)
    a.python_full = resolve_python(a.python)
    machine = dict(detect_machine_type())
    machine.setdefault("cpu_model", cpu_model())
    machine.setdefault("ram_gb", ram_gb())
    records, skipped, selection = [], {}, {}
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
                chosen, sk = select_prs(gh, repo, cfg, sel_seen, sel_since, a.max_per_library, a.scan_limit, None)
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
            prev = rdir / f"{cfg['pkg']}-{c['pr']}" / "record.json"
            rec = None
            if a.resume and prev.exists():
                old = json.loads(prev.read_text())
                if old.get("record_kind") == "pr_run" and old["pr"]["head_sha"] == c["head_sha"]:
                    rec = old
                    print(f"  #{c['pr']}: reusing record from this run folder (--resume)", flush=True)
            if rec is None:
                print(f"  testing #{c['pr']} {c['title'][:60]} ...", flush=True)
            try:
                rec = rec or test_pr(repo, cfg, c, rdir, workroot, a, machine)
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
    (rdir / "selection.json").write_text(json.dumps({"selected": selection, "skipped": skipped}, indent=1))
    if a.select_only:
        print(json.dumps(selection, indent=1))
        return 0
    with open(rdir / "records.jsonl", "w") as fh:
        for r in records:
            fh.write(json.dumps(r) + "\n")
    if not single:  # a one-off check never changes what the daily run selects
        seen_path.write_text(json.dumps(seen, indent=1))
    finished = now_ist()
    git = subprocess.run(["git", "-C", REPO_ROOT, "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
    dirty = subprocess.run(["git", "-C", REPO_ROOT, "status", "--porcelain", "--", "ops", "poc", "harness"],
                           capture_output=True, text=True).stdout.strip()
    meta = {"date": rdir.name, "started_ist": started.strftime("%Y-%m-%d %H:%M IST"),
            "finished_ist": finished.strftime("%Y-%m-%d %H:%M IST"),
            "wall_min": round((finished - started).total_seconds() / 60, 1), "runs": a.runs,
            "machine": f"{machine['label']} {machine['arch']} {machine['cpu_count']} cpus",
            "api_calls": gh.calls, "auth": "token" if gh.token else "unauthenticated",
            "git": git + (" (with uncommitted changes)" if dirty else "")}
    (rdir / "run_meta.json").write_text(json.dumps(meta | {"problems": problems}, indent=1))
    # Expectations and independent verification are read only now, after every verdict above is final.
    rp = write_report(rdir, meta, records, skipped, problems, *scoring_inputs(rdir, a, chosen_path),
                      attempt_history(rdir))
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


def report_only(rdir: Path, a) -> int:
    """Rebuild REPORT.md and the reviewer reports from saved records. The coverage gate is re-applied in memory
    (records written before it existed get the compiled / docs-only rules; Python coverage shows 'not measured');
    records.jsonl and record.json files are never rewritten."""
    records = [gate(json.loads(ln)) for ln in (rdir / "records.jsonl").read_text().splitlines() if ln.strip()]
    meta = json.loads((rdir / "run_meta.json").read_text())
    problems = meta.pop("problems", [])
    skipped = json.loads((rdir / "selection.json").read_text()).get("skipped", {})
    rp = write_report(rdir, meta, records, skipped, problems, *scoring_inputs(rdir, a, chosen_prs_path(a, rdir)),
                      attempt_history(rdir))
    print(f"run log (rebuilt from records, nothing re-tested): {rp}")
    reviewer_reports(rdir, a, records, "daily summary (rebuilt)")
    return 0


def resolve_python(spec: str) -> str:
    """'3.12' -> '3.12.15' (the interpreter uv will use for the venvs)."""
    exe = subprocess.run(["uv", "python", "find", spec], capture_output=True, text=True).stdout.strip()
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
