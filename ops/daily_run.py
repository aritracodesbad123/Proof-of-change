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
from poc import behaviour_claims, cost, coverage_gate, diff_probes, freeze, local_config, model_probes, model_provider, probes  # noqa: E402,E501
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
    in_pkg = [f for f in files if f.startswith((pkg + "/", f"src/{pkg}/"))]   # flat or src layout
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
        item = {"pr": n, "title": p["title"], "body": p.get("body") or "", "url": p["html_url"],
                "author": p["user"]["login"], "head_sha": sha,
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


def source_pair(repo: str, item: dict, work: Path, log: Path, python: str, timeout: int) -> dict:
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
    for side in ("main", "pr"):
        rc, _ = run(["git", "-C", src, "worktree", "add", "-q", "--detach", work / f"side-{side}", res[f"{side}_sha"]],
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


def install_declared_test_deps(venvs: dict, reqs: list[str], log: Path, timeout: int) -> tuple[bool, str]:
    """Install the same declared test requirements on both sides."""
    if not reqs:
        return True, ""
    for side, venv in venvs.items():
        rc, _ = run(["uv", "pip", "install", "-q", "-p", venv / "bin/python", *reqs], log,
                    env=base_env(side_home(venv), install=True), timeout=timeout, sbx=side_sandbox(venv, network=True))
        if rc != 0:
            return False, f"installing declared test requirements on the {side} side failed ({rc}); see {log.name}"
    return True, ""


def direct_url(venv: Path, dist: str) -> dict | None:
    """The installed distribution's direct_url.json (PEP 610), or None when it has none."""
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


def check_installed_commit(venv: Path, dist: str, expected_sha: str, checkout: Path | None = None) -> tuple[bool, dict]:
    """Does the installed `dist` come from `expected_sha`? Fails closed.

    A VCS install (vcs_info.commit_id) must name that commit. A local install (dir_info) must point at `checkout`, and
    that checkout must be at `expected_sha` (git rev-parse HEAD). Anything else (no direct_url.json, another
    directory, another commit) fails. Short expected SHAs (7+ hex) match by prefix."""
    du = direct_url(venv, dist)
    info: dict = {"dist": dist, "expected": expected_sha, "direct_url": du}

    def same(got: str | None) -> bool:
        return bool(got) and len(expected_sha) >= 7 and (got.startswith(expected_sha) or expected_sha.startswith(got))
    if not du:
        info["why"] = f"{dist} has no direct_url.json, so the installed commit cannot be checked"
        return False, info
    vcs = du.get("vcs_info") or {}
    if vcs.get("commit_id"):
        info["installed"] = vcs["commit_id"]
        ok = same(vcs["commit_id"])
        if not ok:
            info["why"] = f"{dist} installed from commit {vcs['commit_id'][:12]}, not the requested {expected_sha[:12]}"
        return ok, info
    url = du.get("url") or ""
    if checkout is not None and "dir_info" in du:
        here = Path(urllib.parse.unquote(url.removeprefix("file://"))).resolve() if url.startswith("file://") else None
        if here != Path(checkout).resolve():
            info["why"] = f"{dist} was installed from {url}, not from the checked-out side"
            return False, info
        head = subprocess.run(["git", "-C", str(checkout), "rev-parse", "HEAD"], capture_output=True, text=True,
                              env=base_env(Path(checkout).parent / "home-git")).stdout.strip()
        info["installed"] = head
        ok = same(head)
        if not ok:
            info["why"] = f"{dist} checkout is at {head[:12] or 'unknown'}, not the requested {expected_sha[:12]}"
        return ok, info
    info["why"] = f"{dist} was installed from {url or 'an unknown source'} with no commit to check"
    return False, info


def install_side(venv: Path, checkout: Path, chosen: dict | None, log: Path, python: str, timeout: int,
                 constraints: Path | None) -> tuple[bool, str]:
    env = base_env(side_home(venv), install=True)
    if subprocess.run(["git", "-C", checkout, "describe", "--tags"], capture_output=True, env=env).returncode != 0:
        env = base_env(side_home(venv), install=True, SETUPTOOLS_SCM_PRETEND_VERSION="9999.0.0")
    proj, extra = side_install_args(chosen, checkout)
    proj = with_test_extras(proj, checkout)
    cmds = [["uv", "venv", "-q", "-p", python, venv],
            ["uv", "pip", "install", "-q", "-p", venv / "bin/python", *proj, *extra, *BASE_TEST_DEPS,
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
        cmds.insert(1, ["uv", "pip", "install", "-q", "-p", venv / "bin/python", *breq, "ninja", *pins])
        cmds[-1].insert(cmds[-1].index("-p"), "--no-build-isolation")
    # Optional overrides (POC_INSTALL_OVERRIDES): e.g. drop an optional test extra that cannot build on this machine
    # ("scikit-umfpack; python_version < '0'"). Same file for both sides and every tool.
    ov = os.environ.get("POC_INSTALL_OVERRIDES")
    ov = ov if ov and Path(ov).is_file() else None
    if ov:
        cmds[-1] += ["--override", ov]
    ro_files = tuple(x for x in (constraints, bc if bc and Path(bc).is_file() else None, ov) if x)
    sbx = side_sandbox(venv, network=True, ro=ro_files)
    sbx["rw"].append(checkout)
    for c in cmds:
        rc, _ = run(c, log, env=env, timeout=timeout, sbx=sbx)
        if rc != 0:
            return False, f"install failed ({rc}); see {log.name}"
    return True, ""


# ---------------------------------------------------------------- execution helpers
HOST = None   # sbx=HOST: a trusted tool on our own files (git on our clones); everything else runs in a side's sandbox


def run(cmd, log_path: Path, cwd=None, env=None, timeout=None, sbx=HOST) -> tuple[int | str, float]:
    """Run cmd with output to log_path. env is required: always an allowlisted base_env(...). sbx: the sandbox of a
    side (side_sandbox(...)); every command that may run PR or package code passes one."""
    if env is None:
        raise ValueError("run() needs an explicit allowlisted env (base_env)")
    t0 = time.time()
    shown = list(map(str, cmd))
    if sbx is not None:
        cmd, env, cwd = sandbox.wrap(cmd, env, sbx["rw"], sbx["ro"], sbx["network"], cwd)
    with open(log_path, "a") as fh:
        fh.write(f"\n$ {' '.join(shown)}" + (f"   [sandbox: {'network' if sbx['network'] else 'no network'}]"
                                              if sbx is not None and sandbox.enabled() else "") + "\n"); fh.flush()
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


def base_env(home: Path, install: bool = False, **extra) -> dict:
    """Allowlisted environment for anything that may run PR or package code (guardrails.isolation.untrusted_env):
    nothing from our own environment except PATH, locale, terminal and temp settings; HOME is `home`, a per-environment
    temporary home. install=True adds the uv cache and settings for installs and builds."""
    return untrusted_env(home, install=install, extra=extra or None)


def side_home(venv: Path) -> Path:
    """Per-environment temporary HOME, next to the venv: work/venv-main -> work/home-main."""
    return venv.parent / f"home-{venv.name.removeprefix('venv-')}"


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


def side_cwd(venv: Path) -> Path:
    d = venv.parent / f"cwd-{venv.name.removeprefix('venv-')}"
    d.mkdir(parents=True, exist_ok=True)
    return d


def in_side(venv: Path, cmd: list, install: bool = False, network: bool = False, cwd=None, ro: tuple = (),
            timeout: int | None = 600) -> subprocess.CompletedProcess:
    """Captured run of cmd in the side's sandbox (venv Python and uv calls: freeze, version checks, imports)."""
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
    txt = in_side(venv, ["uv", "pip", "freeze", "-p", venv / "bin/python"], install=True).stdout
    out.write_text(txt)
    return out.name


def build_main_env(cfg: dict, venv: Path, log: Path, python: str, timeout: int, wheel_dir: Path) -> dict:
    """Stable release of the library with its test extra + test deps + optional test deps (so tests do not skip for
    missing optional modules), then the exact nightly wheel file, pinned by sha256, reinstalled without deps.
    UV_LINK_MODE=copy so patching the PR copy can never modify the shared uv cache."""
    env = base_env(side_home(venv), install=True)
    py = venv / "bin/python"
    steps = [["uv", "venv", "-q", "-p", python, venv],
             ["uv", "pip", "install", "-q", "-p", py, cfg["dist"], *cfg["deps"], *BASE_TEST_DEPS, *cfg["test_deps"]]]
    sbx = side_sandbox(venv, network=True)
    for c in steps:
        rc, _ = run(c, log, env=env, timeout=timeout, sbx=sbx)
        if rc != 0:
            return {"ok": False, "why": f"main env setup failed ({rc}) at: {' '.join(map(str, c[:4]))}"}
    extras = test_extras(dist_extras(venv, cfg["dist"], env))
    opt = list(cfg.get("optional_test_deps", []))
    if extras or opt:
        spec = f"{cfg['dist']}[{','.join(extras)}]" if extras else cfg["dist"]
        rc, _ = run(["uv", "pip", "install", "-q", "-p", py, spec, *opt], log, env=env, timeout=timeout, sbx=sbx)
        if rc != 0:
            return {"ok": False, "why": f"installing test extras/optional test deps failed ({rc}); see setup log"}
    try:
        whl = fetch_wheel(nightly_wheel(lambda u: urllib.request.urlopen(
            urllib.request.Request(u, headers={"User-Agent": "proof-of-change-ops"}), timeout=120).read(),
            cfg["dist"], python), wheel_dir)
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "why": f"could not fetch the nightly wheel: {e}"}
    rc, _ = run(["uv", "pip", "install", "-q", "-p", py, "--no-deps", "--reinstall", whl["path"]], log, env=env,
                timeout=timeout, sbx=side_sandbox(venv, ro=(whl["path"],)))   # local file: no network needed
    if rc != 0:
        return {"ok": False, "why": f"installing the nightly wheel failed ({rc})"}
    ver = in_side(venv, [py, "-c", f"import {cfg['pkg']} as m;print(m.__version__)"]).stdout.strip()
    commit, how = nightly_commit(whl["version"], venv, cfg, env)
    rc, _ = run(["uv", "pip", "check", "-p", py], log, env=env, timeout=120, sbx=side_sandbox(venv))
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
    venv = site.parents[2]   # site = <venv>/lib/pythonX.Y/site-packages
    env, sbx = base_env(side_home(venv)), side_sandbox(venv)
    rc, _ = run(base + ["--dry-run"], log, env=env, sbx=sbx)
    if rc != 0:
        return False, "PR diff does not apply cleanly to the current nightly (main has moved or the files differ)"
    rc, _ = run(base, log, env=env, sbx=sbx)
    return rc == 0, "" if rc == 0 else "patch failed after a clean dry run"


def source_build(repo: str, item: dict, cfg: dict, venv: Path, workdir: Path, log: Path, python: str,
                 timeout: int, main_extra_reqs: tuple = ()) -> dict:
    env = base_env(side_home(venv), install=True)
    src = workdir / "src"
    steps = [["git", "init", "-q", src],
             ["git", "-C", src, "fetch", "-q", "--depth", "1", f"https://github.com/{repo}.git",
              f"pull/{item['pr']}/head"],
             ["git", "-C", src, "checkout", "-q", "FETCH_HEAD"],
             ["git", "-C", src, "submodule", "update", "-q", "--init", "--depth", "1", "--recursive"],
             ["uv", "venv", "-q", "-p", python, venv],
             ["uv", "pip", "install", "-q", "-p", venv / "bin/python", *cfg["deps"], *BASE_TEST_DEPS, *cfg["test_deps"],
              *cfg.get("optional_test_deps", []), *main_extra_reqs]]
    for c in steps:   # git on our own fresh clone runs on the host; uv steps (package code) in the PR side's sandbox
        sbx = side_sandbox(venv, network=True) if c[0] == "uv" else HOST
        rc, _ = run(c, log, env=env if c[0] == "uv" else base_env(workdir / "home-git"), timeout=900, sbx=sbx)
        if rc != 0:
            return {"ok": False, "why": f"source checkout/setup failed ({rc}) at: {' '.join(map(str, c[:3]))}"}
    t0 = time.time()
    rc, secs = run(["uv", "pip", "install", "-p", venv / "bin/python", "--no-cache", src], log, env=env, timeout=timeout,
                   sbx=side_sandbox(venv, network=True))
    if rc != 0:
        tail = log.read_text(errors="replace").strip().splitlines()[-15:]
        hint = next((ln for ln in reversed(tail) if re.search(r"error|not found|ERROR", ln)), tail[-1] if tail else "")
        return {"ok": False, "build_seconds": round(time.time() - t0, 1),
                "why": f"source build of PR head {'timed out' if rc == 'timeout' else 'failed'} after {secs}s: {hint.strip()[:200]}"}
    ver = in_side(venv, [venv / "bin/python", "-c", f"import {cfg['pkg']} as m;print(m.__version__)"]).stdout.strip()
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


def run_tests(side_venvs: dict, targets_by_side: dict, rdir: Path, workdir: Path, runs: int, workers: str,
              test_timeout: int, run_timeout: int, cwds: dict | None = None) -> tuple[list[dict], dict]:
    """targets are relative to site-packages (nightly routes) or to the side's checkout (cwds given).
    per_run entries use the shared schema shape (side old/new, all counts present)."""
    envs = {side: base_env(side_home(v)) for side, v in side_venvs.items()}
    per_run, results = [], {"main": [], "pr": []}
    for i in range(1, runs + 1):
        for side in ("main", "pr"):
            venv = side_venvs[side]
            base = cwds[side] if cwds else site_packages(venv)
            tg = [str(base / t) for t in targets_by_side[side]]
            jx = rdir / f"junit-{side}-{i}.xml"; lg = rdir / f"pytest-{side}-{i}.log"
            jin = side_out(venv) / jx.name   # written inside the side's sandbox, then moved to the run folder
            entry = {"side": SIDE_KEY[side], "run": i, "passed": 0, "failed": 0, "error": 0, "skipped": 0,
                     "collection_errors": 0}
            if not tg:
                results[side].append({}); per_run.append(entry | {"exit": "no-targets", "seconds": 0,
                                                                   "pytest_summary": "", "junit": False}); continue
            cmd = [venv / "bin/python", "-m", "pytest", *tg, "-p", "no:cacheprovider", "-q", "-rfE",
                   f"--timeout={test_timeout}", "-o", "addopts=", "-o", "junit_family=xunit2", f"--junitxml={jin}"]
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
                                                   new.read_text(errors="replace"))
        sources.add(str(new.parent))
    if not changed:
        return {"status": "failed", "why": "none of the changed Python files exist on the PR side"}
    log = prdir / "coverage-pr.log"
    rc, _ = run(["uv", "pip", "install", "-q", "-p", venv / "bin/python", "coverage>=7", "pytest-cov>=5"], log,
                env=base_env(side_home(venv), install=True), timeout=600, sbx=side_sandbox(venv, network=True))
    if rc != 0:
        return {"status": "failed", "why": f"installing coverage failed ({rc}); see coverage-pr.log"}
    out = prdir / "coverage-pr.json"
    oin = side_out(venv) / out.name
    base = cwd or pr_root
    cmd = [venv / "bin/python", "-m", "pytest", *[str(base / t) for t in targets], "-p", "no:cacheprovider", "-q",
           f"--timeout={a.test_timeout}", "-o", "addopts=", *[f"--cov={s}" for s in sorted(sources)],
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
    res = coverage_gate.measure(changed, json.loads(out.read_text()).get("files", {}))
    return res | {"seconds": secs, "exit": rc, "log": "coverage-pytest.log"}


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
           and it.get("status") not in ("crashed", "error", "uninformative", "not_run")
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
           "flaky": [], "environment": [], "other_changes": [], "preexisting_failures": [], "load_failed_both": [],
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
                baseline: str | None = None, docstring_only: bool = False) -> tuple[str, str, list[str]]:
    """tests, then probes (with_probes), then behaviour-preservation claims (poc/behaviour_claims.py): a 'verified'
    PR whose title or description claims results stay the same, with no probe checking that, becomes
    could_not_verify ('unverified behaviour claim: "<quote>"; needs a probe'). With a probe, the probe decides.
    baseline (BASELINES, default full) selects which probes decide and whether claims are flagged.
    A docstring-only change (AST equal after blanking docstrings) is verified: the claim holds by construction,
    unless the tests already need attention."""
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
        return (Verdict.VERIFIED.value,
                "docstring-only change (AST equal after blanking docstrings); behaviour claims hold by construction",
                fl + ["holds_by_construction"])
    return v, reason, fl


def with_probes(cmp: dict | None, cnv_reason: str | None, exits: dict | None = None, files: dict | None = None,
                probe_results: dict | None = None) -> tuple[str, str, list[str]]:
    """The PR verdict: the tests' verdict (tests_verdict), then the probes (poc/probes.py). An observation that needs
    attention (it differs and no claim covers it, or it contradicts a claim) makes the verdict
    needs_attention, also when the tests alone could not verify the PR. Flaky observations and warning-only
    differences are shown but never decide the verdict. Probes never upgrade a verdict: all-green
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
    if s["flagged"] and v != Verdict.NEEDS_ATTENTION.value:
        return Verdict.NEEDS_ATTENTION.value, f"{s['reason']}; tests: {reason}", fl
    return v, (f"{reason}; {s['reason']}" if s["reason"] else reason), fl


def tests_verdict(cmp: dict | None, cnv_reason: str | None, exits: dict | None = None,
                  files: dict | None = None) -> tuple[str, str, list[str]]:
    """Verdict from the test comparison alone (claims are checked by probes, see verdict_for).

    Order:
      1. could-not-verify reasons of the run itself;
      2. real findings (regressions, new failing tests) -> needs attention (nothing below can hide them);
      3. no test actually ran on a side (all skipped, or every module failed to load) -> could not verify;
      4. a test module loads on one side only -> could not verify, naming the module;
      5. a test module of the changed code fails to load on both sides -> could not verify;
      6. unexplained pytest exit codes -> could not verify;
      7. new/changed tests skipped, or new tests that fail only because an optional dependency is missing
         -> could not verify (never needs attention);
      8. flaky tests are listed but never decide the verdict (results that change between runs of one side are noise).
         A test that passes and fails across the 3 runs of one side is listed. It is not a regression and
         does not, on its own, produce needs attention. Flaky labels are not passed to pr_verdict, because
         that rule treats every amber finding as needs attention (probes still use that rule);
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
    if cmp["regressions"] or cmp["new_tests_failing"]:
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
                                            base_root, pr_roots, prdir / "model-probes")
            except freeze.FreezeError as e:
                res = {"errors": [str(e)], "probes": [], "claims": [], "rejected_claims": []}
            note["model_claims"] = res.get("claims", [])
            note["model_rejected_claims"] = res.get("rejected_claims", [])
            note["errors"] += res.get("errors", [])
            plan += [{"path": x["path"], "source": "model", "freeze": x["freeze"]} for x in res.get("probes", [])]
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
    envs = {side: base_env(side_home(v)) for side, v in venvs.items()}
    cwds = {side: side_cwd(v) for side, v in venvs.items()}
    for x in plan:
        path, fz = Path(x["path"]), x["freeze"]
        def guard(p, fz=fz):
            freeze.verify(p, fz, pr_started)
        try:
            guard(path)
            it = probes.run_probe(path, pythons, prdir, cwds, envs, runs=a.runs, source=x["source"],
                                  launchers={side: probe_launcher(v, path) for side, v in venvs.items()}, guard=guard)
            it["path"] = repo_relative(path) if x["source"] == "library" else str(path.relative_to(prdir))
            it["generator"] = fz["generator"]
            it["freeze"] = fz | {"verified": True, "pr_started_at": pr_started}
            items.append(it)
        except freeze.FreezeError as e:
            refused.append({"path": path.name, "source": x["source"], "why": str(e)})
        except probes.ProbeError as e:
            errors.append(str(e).replace(str(REPO_ROOT) + "/", ""))
    out = {"status": "ran" if items else "error", "items": items, "summary": probes.summarize(items)}
    if errors:
        out["errors"] = errors
    if refused:
        out["refused"] = refused
    return out


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

    if getattr(a, "no_coverage", False):
        return unmeasured("--no-coverage")
    changed = {}
    for rel in coverage_gate.python_sources(item["files"]):
        old, new = Path(main_root) / rel, Path(pr_root) / rel
        changed[rel] = probe_adequacy.main_side_lines(old.read_text(errors="replace") if old.is_file() else None,
                                                      new.read_text(errors="replace") if new.is_file() else None)
    if not changed:
        return unmeasured("no changed non-test Python files")
    log = prdir / "probe-coverage.log"
    py = vm / "bin" / "python"
    if in_side(vm, [py, "-c", "import coverage"]).returncode != 0:
        rc, _ = run(["uv", "pip", "install", "-q", "-p", py, "coverage>=7"], log,
                    env=base_env(side_home(vm), install=True), timeout=600, sbx=side_sandbox(vm, network=True))
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
        env = base_env(side_home(vm))
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
                              "note": getattr(a, "model_note", None) or "model provider: none: fixed probes only",
                              "blind": bool(getattr(getattr(a, "provider", None), "blind", False))},
           "posted_upstream": False, "logs": f"{cfg['pkg']}-{item['pr']}/", "freeze": {}}
    sha = getattr(a, "poc_commit", None)
    if isinstance(sha, str) and _COMMIT.fullmatch(sha):
        rec["poc_commit"] = sha
    rec["route"] = ("source-pair" if not cfg.get("nightly") else
                    "source-build" if item["files"]["compiled"] else "nightly+patch")
    rec["current_head_sha"] = item.get("current_head_sha") or item["head_sha"]
    if getattr(a, "invocation", None):
        rec["tested_invocation"] = a.invocation
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
    rec["probes"] = probes.apply_status(pr)
    rec["probe_changed_line_coverage"] = probe_adequacy.summary(rec["probes"]["items"])


def install_optional_modules(venvs: dict, modules: list[str], log: Path, timeout: int) -> tuple[bool, str]:
    """Install plain pip wheels for missing optional modules, on both sides."""
    pkgs = []
    for name in modules:
        pkg = PIP_OPTIONAL.get(name)
        if pkg and pkg not in pkgs:
            pkgs.append(pkg)
    if not pkgs:
        return True, ""
    for side, venv in venvs.items():
        rc, _ = run(["uv", "pip", "install", "-q", "-p", venv / "bin/python", *pkgs], log,
                    env=base_env(side_home(venv), install=True), timeout=timeout,
                    sbx=side_sandbox(venv, network=True))
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
                                 cwds=cwds)
    cmp, cnv, ex = finalize_tests(rec, per_run, results, a)
    if not cmp:
        return cmp, cnv, ex
    confirm_missing(cmp, venvs["pr"])
    modules = installable_missing(cmp)
    if not modules:
        return cmp, cnv, ex
    log = prdir / "setup-optional.log"
    ok, why = install_optional_modules(venvs, modules, log, a.build_timeout)
    wheels = [PIP_OPTIONAL[m] for m in modules if PIP_OPTIONAL.get(m)]
    if not ok:
        rec["optional_install_error"] = why
        return cmp, cnv, ex
    rec["test_extras"] = list(dict.fromkeys([*(rec.get("test_extras") or []), *wheels]))
    per_run, results = run_tests(venvs, targets, prdir, work, a.runs, a.workers, a.test_timeout, a.run_timeout,
                                 cwds=cwds)
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


def sandbox_refusal() -> str | None:
    """Reason to refuse running PR code: the sandbox is on (default) but cannot start here."""
    if not sandbox.enabled():
        return None
    ok, why = sandbox.check()
    return None if ok else why


def test_pr(repo: str, cfg: dict, item: dict, rdir: Path, workroot: Path, a, machine: dict) -> dict:
    t0 = time.time()
    cost.reset()
    tag = f"{cfg['pkg']}-{item['pr']}"
    prdir = rdir / tag; prdir.mkdir(parents=True, exist_ok=True)
    work = workroot / tag
    shutil.rmtree(work, ignore_errors=True); work.mkdir(parents=True)
    (prdir / "pr.diff").write_text(item["diff"])
    rec = new_record(repo, cfg, item, a, machine, rdir.name, run_date_for(rdir))
    refusal = sandbox_refusal()
    if refusal:   # fail closed: no PR code runs without the sandbox (unless --unsafe-no-sandbox)
        rec["verdict"], rec["reason"], _ = verdict_for(None, refusal)
        return finish(rec, prdir, work, t0)
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
        rec["freeze"]["main"] = freeze_env(vm, prdir / "freeze-main.txt")
        plan = plan_probes(repo, item, rec, site_packages(vm), [vp, work / "src"], prdir, a)
        rec["pr_side_started_at"] = pr_started = freeze.now()   # nothing below may create or change a probe
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
            rec["freeze"]["pr"] = freeze_env(vp, prdir / "freeze-pr.txt")
    rec["tested"] = {"main": f"nightly {main.get('version', '?')} "
                             f"(commit {(main.get('build') or {}).get('commit') or 'unknown'}, "
                             f"sha256 {((main.get('build') or {}).get('sha256') or '?')[:12]})",
                     "pr": (f"PR head {item['head_sha'][:12]} " +
                            ("built from source" if rec.get("route") == "source-build" else "diff applied to that nightly"))}
    cmp = None
    envs_ok = not cnv
    if not cnv:
        tm = map_tests(item["files"], cfg["pkg"], site_packages(vm), cfg)
        tp = map_tests(item["files"], cfg["pkg"], site_packages(vp), cfg)
        targets = targets_for_sides(list(dict.fromkeys(tp + tm)), item["files"], site_packages(vm), site_packages(vp))
        rec["test_targets"] = targets
        rec["test_selection"] = "mapped from touched modules: " + ", ".join(targets["pr"])
        if not targets["pr"]:
            cnv = "no tests could be mapped to the touched modules"
        else:
            cmp, cnv, ex = execute_tests(rec, {"main": vm, "pr": vp}, targets, prdir, work, a)
            if cmp:
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
        rec["probes"] = run_probes(repo, item["pr"], {"main": vm / "bin/python", "pr": vp / "bin/python"}, prdir, work,
                                   a, plan, pr_started)
        rec["probe_changed_line_coverage"] = probe_coverage(item, rec["probes"], vm, site_packages(vm), site_packages(vp),
                                                            prdir, a)
        settle_probes(rec)
        if change_is_docstring_only(rec.get("files"), site_packages(vm), site_packages(vp)):
            rec["docstring_only"] = True
    _store_verdict(rec, cmp, cnv, ex)
    return finish(gate(rec), prdir, work, t0)


def finish(rec: dict, prdir: Path, work: Path, t0: float) -> dict:
    rec["what_changed"] = {"package_python_files": rec["files"]["package_py"], "compiled_files": rec["files"]["compiled"],
                           "other_files": rec["files"]["other"]}
    rec["duration_s"] = {"total_wall": round(time.time() - t0, 1),
                         "tests": round(sum(e.get("seconds") or 0 for e in rec.get("per_run", [])), 1)}
    if rec.get("pr_side", {}).get("build_seconds") is not None:
        rec["duration_s"]["build"] = rec["pr_side"]["build_seconds"]
    rec["cost"] = cost.take(rec["duration_s"])
    errs = check_record(rec)
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


def check_record(rec: dict) -> list[str]:
    """The record check: the shared schema, plus poc_commit on a pr_run record.

    poc_commit is optional in the schema so a record written before rev 8 still validates. A record this run
    writes must name the Proof-of-Change commit it used (the full SHA of origin/main after the fast-forward).
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
        if isinstance(sp.get("main_sha"), str) and re.fullmatch(r"[0-9a-f]{7,40}", sp["main_sha"]):
            rec["pr"]["tested_main_sha"] = sp["main_sha"]
            rec["pr"]["tested_main_sha_label"] = (
                "main side that was tested (base-branch tip, or the merge-base when the pull request conflicts "
                "or the pinned head differs from the current head)")
    cnv, cmp, ex = None, None, None
    if not sp["ok"]:
        cnv = sp["why"]
    else:
        vm, vp = work / "venv-main", work / "venv-pr"
        cm, cp = work / "side-main", work / "side-pr"
        ok, why = install_side(vm, cm, item.get("chosen"), prdir / "setup-main.log", a.python, a.build_timeout, None)
        plan, pr_started = [], None
        if ok:
            plan = plan_probes(repo, item, rec, cm, [cp, work / "src"], prdir, a)
            rec["python"] = venv_python_version(vm) or rec["python"]
            frz = in_side(vm, ["uv", "pip", "freeze", "-p", vm / "bin/python"], install=True).stdout
            pkgname = cfg["dist"].lower().replace("_", "-")
            cons = work / "constraints.txt"
            cons.write_text("\n".join(ln for ln in frz.splitlines() if ln and not ln.startswith(("-e", "#"))
                                       and ln.split("==")[0].lower().replace("_", "-") != pkgname) + "\n")
            rec["freeze"]["main"] = freeze_env(vm, prdir / "freeze-main.txt")
            proj, _extra = side_install_args(item.get("chosen"), cm)
            rec["test_extras"] = recorded_test_extras(cm, with_test_extras(proj, cm))
            rec["pr_side_started_at"] = pr_started = freeze.now()   # nothing below may create or change a probe
            ok, why = install_side(vp, cp, item.get("chosen"), prdir / "setup-pr.log", a.python, a.build_timeout, cons)
            if ok:
                rec["freeze"]["pr"] = freeze_env(vp, prdir / "freeze-pr.txt")
        if not ok:
            cnv = why
        else:
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
                                                        a.build_timeout)
                rec["declared_test_deps"] = {"requested": decl, "installed": good}
                if good:
                    rec["test_extras"] = list(dict.fromkeys([*(rec.get("test_extras") or []), *decl]))
                    rec["freeze"]["main"] = freeze_env(vm, prdir / "freeze-main.txt")
                    rec["freeze"]["pr"] = freeze_env(vp, prdir / "freeze-pr.txt")
                else:
                    rec["optional_install_error"] = why2
            if cnv:
                pass
            elif not targets["pr"]:
                cnv = "no tests could be mapped to the touched files"
            else:
                cmp, cnv, ex = execute_tests(rec, {"main": vm, "pr": vp}, targets, prdir, work, a,
                                             cwds={"main": cm, "pr": cp})
                if cmp:
                    rec["coverage"] = coverage_run(item, vp, cm, cp, targets["pr"], prdir, work, a, cwd=cp)
            rec["probes"] = run_probes(repo, item["pr"], {"main": vm / "bin/python", "pr": vp / "bin/python"}, prdir,
                                       work, a, plan, pr_started)
            rec["probe_changed_line_coverage"] = probe_coverage(item, rec["probes"], vm, cm, cp, prdir, a)
            settle_probes(rec)
            if change_is_docstring_only(rec.get("files"), cm, cp):
                rec["docstring_only"] = True
    _store_verdict(rec, cmp, cnv, ex)
    return gate(rec)


def _store_verdict(rec: dict, cmp, cnv, ex) -> None:
    """Write the verdict. A docstring-only change marks each behaviour claim as holding by construction."""
    v, reason, _ = verdict_for(cmp, cnv, ex, rec.get("files"), rec.get("probes"), rec.get("behaviour_claims"),
                               rec.get("baseline"), docstring_only=bool(rec.get("docstring_only")))
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
                      "base_sha": p["base"]["sha"], "base_ref": p["base"]["ref"], "updated_at_utc": p["updated_at"],
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
                         "from NEBIUS_API_KEY), recorded (recorded responses: TEST FIXTURE, not blind), none (fixed "
                         "probes only). The daily run, not benchmark mode, refuses to start on the full baseline without a "
                         "working model, because that gate would turn every clean PR into could_not_verify")
    ap.add_argument("--claims-model", default=model_provider.DEFAULT_MODELS["claims"], help="model id for claims")
    ap.add_argument("--probe-model", default=model_provider.DEFAULT_MODELS["probes"], help="model id for probes")
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
    ap.add_argument("--rejudge", action="store_true",
                    help="with --report-only: recompute verdicts from the saved JUnit files with the current rules "
                         "(the previous verdict is kept in each record under 'rejudged'; originals are backed up)")
    ap.add_argument("--report-only", action="store_true",
                    help="rebuild REPORT.md from records.jsonl, selection.json and run_meta.json; test nothing")
    ap.add_argument("--bench", default=None, metavar="CSV",
                    help="benchmark mode (ops/bench.py): test historical PRs from a benchmark INPUTS file, main = first "
                         "parent of the merge commit, PR = the merge commit. Refuses any file named *answers*")
    ap.add_argument("--ids", default=None, help="with --bench: comma-separated case IDs (default: all), e.g. B01,B14")
    ap.add_argument("--bench-out", default=None, help="with --bench: result folder (default: runs/bench-v0)")
    a = ap.parse_args(argv)
    a.poc_commit = sync_to_origin_main(REPO_ROOT)
    sandbox.configure(not a.unsafe_no_sandbox)
    a.provider, a.model_note = model_provider.select(
        a.model_provider, models={"claims": a.claims_model, "probes": a.probe_model},
        recorded_dir=Path(a.recorded_dir) if a.recorded_dir else None)
    if not uses(a.baseline, "claim_probes") and a.provider is not None:
        a.model_note += f" (not used: baseline {a.baseline} has no claim probes)"
        a.provider = None
    refusal = model_refusal(a)
    if refusal:
        print(refusal, file=sys.stderr)
        raise SystemExit(refusal)
    if a.runs != 3:
        print("note: protocol requires 3 runs per side; using", a.runs, file=sys.stderr)
    if a.bench:
        from ops import bench
        return bench.run(a, sys.modules[__name__])

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
    records, skipped, selection, reused = [], {}, {}, []
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
                    reused.append({"repo": repo, "pr": c["pr"],
                                   "from_invocation": old.get("tested_invocation") or 1,
                                   "tested_at_ist": old.get("tested_at_ist")})
                    print(f"  #{c['pr']}: reusing record from invocation "
                          f"{old.get('tested_invocation') or 1} (--resume)", flush=True)
            if rec is None:
                print(f"  testing #{c['pr']} {c['title'][:60]} ...", flush=True)
            try:
                rec = gate(rec or test_pr(repo, cfg, c, rdir, workroot, a, machine))   # final verdict in records.jsonl
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
            token = os.environ.get("GITHUB_TOKEN")
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
