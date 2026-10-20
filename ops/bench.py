"""Benchmark mode: run the normal per-PR pipeline on historical, already-merged PRs from a benchmark INPUTS file.

    python3 ops/daily_run.py --bench bench/benchmark-v0.csv --ids B01,B14 [--bench-out runs/bench-v0]

bench/benchmark-v0.csv is a copy of the v0 inputs file (19 cases). Any other inputs file with the same columns works.

For each case: main side = `main_sha_merge_first_parent`, PR side = `pr_side_sha_merge_commit` (what actually
landed). Both are fetched by SHA, the first parent is checked (`git rev-parse <merge>^1` must equal the main SHA,
otherwise the case is refused as inconsistent), both sides are checked out, and the case goes through the same
route as a live source-pair PR (install, mapped tests 3x per side, coverage gate, probes, verdict).

Output: one result JSON per case and baseline, `<out>/<ID>-<baseline>.json` (the full PR record plus a `bench`
block); logs go to `<out>/logs/<ID>-<baseline>/`.

The answer key is never read here: any path whose file name contains "answers" is refused (also through a
symlink), and an inputs file with answer-key columns (label, ground_truth_links, what_broke, ...) is refused too.
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path, PurePosixPath

REQUIRED = ("id", "repo", "pr", "pr_url", "pr_title", "main_sha_merge_first_parent", "pr_side_sha_merge_commit")
ANSWER_COLUMNS = ("label", "ground_truth_links", "what_broke", "attribution_strength", "category",
                  "overlap_with_testora")
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]*$")   # any case ID (B01, R-numpy-2.3, ...)
DEFAULT_OUT = "runs/bench-v0"
SWARM_ON_SUFFIX = "-swarm-on"
CLONE_URL = "https://github.com/{repo}.git"
SRC_DIRS = ("src", "lib", "python")
# Extra test-time packages a project needs that its pyproject does not declare as a test extra (pip names).
EXTRA_TEST_DEPS = {"psf/requests": ["pytest-httpbin", "pytest-mock", "trustme", "werkzeug<3"],
                   "marshmallow-code/marshmallow": ["simplejson"]}


class AnswerKeyRefused(PermissionError):
    """Runner modes never read an answer key."""


class BenchInputError(ValueError):
    pass


def guard_path(path: str | Path) -> Path:
    """Refuse ANY file whose name (or symlink target's name) contains 'answers', whatever the benchmark. Reusable by
    any mode that reads inputs for a generator or runner."""
    p = Path(path)
    for name in (p.name, p.resolve().name):
        if "answers" in name.lower():
            raise AnswerKeyRefused(f"refusing to read {name}: runner modes never read an answer key "
                                   "(only evals/score_bench.py does)")
    return p


def read_inputs(path: str | Path) -> list[dict]:
    p = guard_path(path)
    with open(p, newline="") as fh:
        rd = csv.DictReader(fh)
        cols = rd.fieldnames or []
        leak = [c for c in cols if c.strip().lower() in ANSWER_COLUMNS]
        if leak:
            raise AnswerKeyRefused(f"{p.name} has answer-key columns ({', '.join(leak)}); give the inputs file")
        missing = [c for c in REQUIRED if c not in cols]
        if missing:
            raise BenchInputError(f"{p.name}: missing column(s) {', '.join(missing)}")
        rows = list(rd)
    seen = set()
    for r in rows:
        if not ID_RE.match(r["id"]) or r["id"] in seen:
            raise BenchInputError(f"{p.name}: bad or duplicate id {r['id']!r}")
        seen.add(r["id"])
        for k in ("main_sha_merge_first_parent", "pr_side_sha_merge_commit"):
            if not SHA_RE.match(r[k]):
                raise BenchInputError(f"{p.name}: {r['id']}: {k} is not a full commit SHA")
        if not re.match(r"^[\w.-]+/[\w.-]+$", r["repo"]) or not r["pr"].isdigit():
            raise BenchInputError(f"{p.name}: {r['id']}: bad repo or PR number")
    return rows


def select(rows: list[dict], ids: str | list[str] | None) -> list[dict]:
    if not ids:
        return rows
    want = [x.strip() for x in (ids.split(",") if isinstance(ids, str) else ids) if x.strip()]
    by = {r["id"]: r for r in rows}
    unknown = [x for x in want if x not in by]
    if unknown:
        raise BenchInputError(f"unknown case id(s): {', '.join(unknown)}")
    return [by[x] for x in want]


def sides(row: dict) -> dict:
    return {"main": row["main_sha_merge_first_parent"], "pr": row["pr_side_sha_merge_commit"]}


def package_path(row: dict) -> str:
    """Folder of the shipped package, from shipped_source_files: 'src/requests/adapters.py' -> 'src/requests'."""
    for f in (row.get("shipped_source_files") or "").split(";"):
        parts = PurePosixPath(f.strip()).parts
        if len(parts) >= 2:
            return "/".join(parts[:2]) if parts[0] in SRC_DIRS and len(parts) > 2 else parts[0]
    return row["repo"].split("/")[1].replace("-", "_")


def result_name(rid: str, baseline: str | None) -> str:
    return f"{rid}-{(baseline or 'full').replace('+', '_')}.json"


def git_ok(dr, cmd: list, log: Path, env: dict, timeout: int = 900) -> bool:
    rc, _ = dr.run(cmd, log, env=env, timeout=timeout)
    return rc == 0


def checkout(dr, row: dict, work: Path, log: Path) -> dict:
    """Clone, fetch both pinned SHAs, verify the first parent, check out work/side-main and work/side-pr (the layout
    the source-pair route and its sandboxes expect). Returns the sides dict for item["bench_sides"] plus files/diff."""
    env = dr.base_env(work / "home-git")
    src = work / "src"
    s = sides(row)
    steps = [["git", "clone", "-q", "--filter=blob:none", "--no-checkout", CLONE_URL.format(repo=row["repo"]), src],
             ["git", "-C", src, "fetch", "-q", "origin", s["main"], s["pr"]]]
    for c in steps:
        if not git_ok(dr, c, log, env):
            return {"ok": False, "why": f"git step failed: {' '.join(map(str, c[:4]))} (see git.log)"}

    def rev(x):
        return subprocess.run(["git", "-C", src, "rev-parse", x], env=env, capture_output=True, text=True).stdout.strip()
    parent1 = rev(f"{s['pr']}^1")
    if parent1 != s["main"]:
        return {"ok": False, "why": f"inputs file inconsistent: first parent of {s['pr'][:12]} is {parent1[:12] or '?'}, "
                                    f"not {s['main'][:12]}"}
    for side in ("main", "pr"):
        co = (work / f"side-{side}").resolve()
        if not git_ok(dr, ["git", "-C", src, "worktree", "add", "-q", "--detach", co, s[side]], log, env):
            return {"ok": False, "why": f"checkout of {side} side failed"}
        # Projects such as SciPy keep parts of their source in git submodules; without them the build fails.
        # Both sides get them the same way, at the versions each commit records. A no-op without submodules.
        if not git_ok(dr, ["git", "-C", co, "submodule", "update", "--init", "--recursive"],
                      log, env, timeout=1800):
            return {"ok": False, "why": f"git submodules of the {side} side could not be fetched (see git.log)"}
    names = subprocess.run(["git", "-C", src, "diff", "--name-only", s["main"], s["pr"]], env=env, capture_output=True,
                           text=True).stdout.split()
    diff = subprocess.run(["git", "-C", src, "diff", s["main"], s["pr"]], env=env, capture_output=True,
                          text=True).stdout
    return {"ok": True, "comparison_basis": "benchmark: first parent of the merge commit vs the merge commit",
            "main_sha": s["main"], "pr_sha": s["pr"], "merge_parents": [parent1, rev(f"{s['pr']}^2") or None],
            "first_parent_verified": True, "files": names, "diff": diff}


def pr_text(dr, row: dict) -> dict:
    """PR title, description and author from the GitHub API (read-only); the inputs file's title if offline. The PR
    text is a permitted generator input; review comments and later issues are not fetched. The description is the one
    in force at merge time when GitHub's edit history can be read (poc/pr_text.py); otherwise the current one, and
    pr_text_source says "current, may be edited after merge"."""
    from poc import pr_text as prt
    try:
        p = dr.GitHub(None).json(f"/repos/{row['repo']}/pulls/{row['pr']}")
    except Exception as e:  # noqa: BLE001
        return {"title": row["pr_title"], "body": "", "author": "unknown", "base_ref": "",
                "source": f"inputs file title only (GitHub API unavailable: {type(e).__name__})",
                "pr_text_source": "none: inputs file title only"}
    body, src = prt.description_at_merge(row["repo"], int(row["pr"]), p.get("body") or "")
    return {"title": p.get("title") or row["pr_title"], "body": body,
            "author": (p.get("user") or {}).get("login") or "unknown", "base_ref": (p.get("base") or {}).get("ref") or "",
            "source": "GitHub API (title, author); description " + src, "pr_text_source": src}


def make_item(dr, row: dict, co: dict, text: dict) -> tuple[dict, dict]:
    repo = row["repo"]
    pkg_path = package_path(row)
    pkg = PurePosixPath(pkg_path).name
    cfg = {"dist": repo.split("/")[1], "pkg": pkg, "deps": [], "test_deps": [], "nightly": False}
    files = dr.classify_files(co.get("files") or [], pkg_path)
    extra = EXTRA_TEST_DEPS.get(repo)
    item = {"pr": int(row["pr"]), "title": text["title"], "body": text["body"], "url": row["pr_url"],
            "author": text["author"], "head_sha": row.get("pr_head_sha") or row["pr_side_sha_merge_commit"],
            "current_head_sha": row.get("pr_head_sha") or row["pr_side_sha_merge_commit"],
            "base_sha": row["main_sha_merge_first_parent"], "base_ref": text["base_ref"] or "(merge first parent)",
            "updated_at_utc": "", "updated_at_ist": row.get("merged_at_ist", ""), "files": files,
            "diff": co.get("diff", ""), "ci_state": "not checked (merged PR; CI assumed from the merged state)",
            "ci_detail": "benchmark case", "state": "merged",
            "chosen": {"install": "pip install -e . " + " ".join(extra), "test_cmd": None} if extra else None,
            "bench_sides": {k: v for k, v in co.items() if k not in ("files", "diff")}}
    return item, cfg


def labelled_study_out(out: str | Path, swarm: bool) -> Path:
    """Folder for one study run.

    A swarm-on study writes beside the main folder, with ``-swarm-on`` on the name.
    The main study scorer reads the other folder and does not see these files.
    """
    path = Path(out)
    if not swarm or path.name.endswith(SWARM_ON_SUFFIX):
        return path
    return path.with_name(path.name + SWARM_ON_SUFFIX)


def write_result(out: Path, rid: str, rec: dict) -> Path:
    out.mkdir(parents=True, exist_ok=True)
    p = out / result_name(rid, rec.get("baseline"))
    p.write_text(json.dumps(rec, indent=1))
    return p


def run_case(dr, a, row: dict, inputs_meta: dict, out: Path, workroot: Path, machine: dict) -> dict:
    t0 = time.time()
    dr.begin_pr(a)
    rid = row["id"]
    tag = result_name(rid, getattr(a, "baseline", None))[:-5]
    prdir = out / "logs" / tag
    shutil.rmtree(prdir, ignore_errors=True)
    prdir.mkdir(parents=True)
    work = workroot / "bench" / tag
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True)
    text = pr_text(dr, row)
    refusal = dr.sandbox_refusal()
    co = {"ok": False, "why": refusal} if refusal else checkout(dr, row, work, prdir / "git.log")
    item, cfg = make_item(dr, row, co, text)
    (prdir / "pr.diff").write_text(item["diff"])
    rec = dr.new_record(row["repo"], cfg, item, a, machine, out.name, dr.now_ist().strftime("%Y-%m-%d"))
    rec["id"] = f"bench-{rid}-{row['repo'].replace('/', '-')}-{row['pr']}-{rec.get('baseline') or 'full'}"
    rec["case_id"] = rid
    rec["bench"] = {"id": rid, **inputs_meta, "main_sha_merge_first_parent": row["main_sha_merge_first_parent"],
                    "pr_side_sha_merge_commit": row["pr_side_sha_merge_commit"],
                    "first_parent_verified": bool(co.get("first_parent_verified")),
                    "pr_text_source": text.get("pr_text_source", text["source"]),
                    "pr_text_detail": text["source"],
                    "answer_key_read": False}
    if dr.mark_typing_only(rec, item.get("files")):
        rec = dr.finish_typing_only(rec, prdir, work, t0, a)
        write_result(out, rid, rec)
        return rec
    if not co.get("ok"):
        rec["verdict"], rec["reason"], _ = dr.verdict_for(None, co["why"])
        rec["sides"] = {k: v for k, v in co.items() if k != "ok"}
    else:
        rec = dr.test_source_pair(row["repo"], cfg, item, prdir, work, a, rec)
        rec["tested"] = {"main": f"first parent of the merge commit @ {co['main_sha'][:12]}",
                         "pr": f"merge commit @ {co['pr_sha'][:12]} (what landed)"}
        rec["pr"]["merge_commit"] = co["pr_sha"]
    rec = dr.finish(rec, prdir, work, t0, a)
    write_result(out, rid, rec)
    return rec


def run(a, dr) -> int:
    """Entry point from ops/daily_run.py main() (dr is that module)."""
    from poc import hitl
    stop = hitl.study_operator_approval_stop(
        bench=True, console_job=bool(getattr(a, "console_job", False)), single_pr=bool(getattr(a, "pr", None)))
    if stop:
        print(stop, file=sys.stderr)
        return 2
    try:
        rows = select(read_inputs(a.bench), a.ids)
    except (AnswerKeyRefused, BenchInputError, OSError) as e:
        print(f"Stopped: {e}", file=sys.stderr)
        return 2
    from poc import model_provider
    stop = model_provider.auth_refusal(getattr(a, "provider", None))
    if stop:
        print(stop, file=sys.stderr)
        return 1
    raw = Path(a.bench).read_bytes()
    meta = {"inputs_file": Path(a.bench).name, "inputs_sha256": hashlib.sha256(raw).hexdigest()}
    out = labelled_study_out(a.bench_out or dr.REPO_ROOT / DEFAULT_OUT, bool(getattr(a, "swarm", False)))
    workroot = Path(a.work_dir or Path(a.ops_dir) / "work")
    a.python_full = dr.resolve_python(a.python)
    machine = dict(dr.detect_machine_type())
    problems = 0
    for row in rows:
        print(f"[{row['id']}] {row['repo']}#{row['pr']} {row['pr_title'][:60]} ...", flush=True)
        try:
            rec = run_case(dr, a, row, meta, out, workroot, machine)
            print(f"    -> {rec['verdict']}: {rec['reason'][:160]}", flush=True)
        except model_provider.ProviderRejected as e:
            print(str(e), file=sys.stderr)
            return 1
        except Exception as e:  # noqa: BLE001
            problems += 1
            print(f"    -> harness error: {type(e).__name__}: {e}", flush=True)
    print(f"results: {out}")
    return 1 if problems else 0
