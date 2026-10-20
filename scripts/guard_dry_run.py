#!/usr/bin/env python3
"""Install each side of a study pair and run the commit guard. Nothing else.

Reads a pairs file (repo, agent_pr, human_pr). For each pull request it checks
out the main side and the pull-request side, then installs them the same way a
source comparison does: the same install command, the same sandbox, and the
same allowlisted environment. It then runs the commit guard on each side and
writes a CSV:

    pair,pr,side,ok,dist,why

It does not run tests, probes, or model calls, and it does not produce a verdict.
A host token used to read the pull request stays in this process. It is not
placed in the environment that installs the checkout.

    python scripts/guard_dry_run.py --pairs evals/study_pairs/main-study-pairs.json --guard new --out guard.csv
    python scripts/guard_dry_run.py --pairs evals/study_pairs/main-study-pairs.json --guard old --out guard-old.csv

``--guard new`` matches the installed distribution by the checkout folder.
``--guard old`` looks the distribution up by the repository name.
"""
from __future__ import annotations

import argparse
import csv
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from guardrails import sandbox  # noqa: E402
from ops import daily_run  # noqa: E402

GUARDS = {
    "new": daily_run.check_installed_commit,
    "old": daily_run.check_installed_commit_by_name,
}
COLUMNS = ("pair", "pr", "side", "ok", "dist", "why")


def load_pairs(path: Path) -> list[dict]:
    data = json.loads(path.read_text())
    if not isinstance(data, list):
        raise SystemExit(f"{path} must be a list of pairs")
    out = []
    for i, row in enumerate(data, 1):
        if not isinstance(row, dict) or not {"repo", "agent_pr", "human_pr"} <= set(row):
            raise SystemExit(f"{path}: pair {i} needs repo, agent_pr, and human_pr")
        out.append(row)
    return out


def pair_label(row: dict) -> str:
    return f"{row['repo']}#{row['agent_pr']}/{row['human_pr']}"


def repo_dist(repo: str) -> str:
    """The distribution name a source comparison used to derive from the repository name."""
    return repo.split("/")[-1]


def fetch_item(repo: str, number: int) -> dict:
    """The fields source_pair reads. The diff is not fetched: this run does not test."""
    p = daily_run.GitHub(None).json(f"/repos/{repo}/pulls/{number}")
    return {
        "pr": p["number"],
        "head_sha": p["head"]["sha"],
        "current_head_sha": p["head"]["sha"],
        "base_ref": p["base"]["ref"],
        "mergeable": p.get("mergeable"),
        "mergeable_state": p.get("mergeable_state"),
        "chosen": None,
    }


def _row(pair: str, number: int, side: str, ok: bool, dist: str, why: str) -> dict:
    return {"pair": pair, "pr": number, "side": side, "ok": "true" if ok else "false", "dist": dist or "", "why": why or ""}


def guard_side(guard, venv: Path, dist: str, sha: str, checkout: Path) -> tuple[bool, str, str]:
    good, info = guard(venv, dist, sha, checkout)
    found = info.get("dist") or ""
    why = "" if good else (info.get("why") or "the commit guard failed")
    return bool(good), str(found), why


def one_pr(repo: str, number: int, dist: str, guard, work: Path, python: str, timeout: int) -> list[dict]:
    """Checkout and install both sides, then run the guard. Failures become CSV rows.

    The pair column is filled in by the caller. Rows from this function carry the pull request and the side.
    """
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    logs = work / "logs"
    logs.mkdir()
    try:
        item = fetch_item(repo, number)
    except Exception as e:  # noqa: BLE001
        why = f"could not read the pull request: {type(e).__name__}: {e}"
        return [_row("", number, side, False, "", why) for side in ("main", "pr")]
    try:
        sp = daily_run.source_pair(repo, item, work, logs / "git.log", python, timeout)
    except Exception as e:  # noqa: BLE001
        why = f"checkout failed: {type(e).__name__}: {e}"
        return [_row("", number, side, False, "", why) for side in ("main", "pr")]
    if not sp.get("ok"):
        why = sp.get("why") or "checkout failed"
        return [_row("", number, side, False, "", why) for side in ("main", "pr")]
    vm, vp = work / "venv-main", work / "venv-pr"
    cm, cp = work / "side-main", work / "side-pr"
    try:
        ok_main, why_main = daily_run.install_side(vm, cm, item.get("chosen"), logs / "setup-main.log", python, timeout, None)
    except Exception as e:  # noqa: BLE001
        ok_main, why_main = False, f"main-side install failed: {type(e).__name__}: {e}"
    if ok_main:
        try:
            cons = daily_run.pr_side_constraints(vm, dist, work / "constraints.txt")
            ok_pr, why_pr = daily_run.install_side(vp, cp, item.get("chosen"), logs / "setup-pr.log", python, timeout, cons)
        except Exception as e:  # noqa: BLE001
            ok_pr, why_pr = False, f"pull-request-side install failed: {type(e).__name__}: {e}"
    else:
        ok_pr, why_pr = False, "pull-request side was not installed because the main-side install failed"
    rows = []
    for side, installed, why, venv, checkout in (
            ("main", ok_main, why_main, vm, cm),
            ("pr", ok_pr, why_pr, vp, cp)):
        if not installed:
            rows.append(_row("", number, side, False, "", why))
            continue
        try:
            good, found, guard_why = guard_side(guard, venv, dist, sp[f"{side}_sha"], checkout)
        except Exception as e:  # noqa: BLE001
            good, found, guard_why = False, "", f"commit guard failed: {type(e).__name__}: {e}"
        rows.append(_row("", number, side, good, found, guard_why))
    return rows


def run(pairs: list[dict], guard_name: str, out: Path, work_root: Path, python: str, timeout: int) -> int:
    guard = GUARDS[guard_name]
    sandbox.configure(True)
    refusal = daily_run.sandbox_refusal()
    if refusal:
        raise SystemExit(refusal)
    out.parent.mkdir(parents=True, exist_ok=True)
    work_root.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=COLUMNS)
        writer.writeheader()
        for row in pairs:
            label = pair_label(row)
            dist = repo_dist(str(row["repo"]))
            for number in (int(row["agent_pr"]), int(row["human_pr"])):
                slot = work_root / f"{str(row['repo']).replace('/', '-')}-{number}"
                print(f"{label} pr {number} ({guard_name})", flush=True)
                for result in one_pr(str(row["repo"]), number, dist, guard, slot, python, timeout):
                    result["pair"] = label
                    writer.writerow(result)
                    fh.flush()
                    print(f"  {result['side']}: ok={result['ok']} dist={result['dist'] or '-'} {result['why']}", flush=True)
    print(f"wrote {out}", flush=True)
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pairs", type=Path, required=True,
                    help="pairs JSON: repo, agent_pr, human_pr (evals/study_pairs/main-study-pairs.json)")
    ap.add_argument("--guard", choices=tuple(GUARDS), default="new",
                    help="new matches the checkout folder; old looks up the repository name (default: new)")
    ap.add_argument("--out", type=Path, required=True, help="CSV to write: pair, pr, side, ok, dist, why")
    ap.add_argument("--work-dir", type=Path, default=None,
                    help="scratch for checkouts and environments (default: ops/work/guard-dry-run)")
    ap.add_argument("--python", default="3.12", help="interpreter passed to the install (default: 3.12)")
    ap.add_argument("--build-timeout", type=int, default=1800, help="seconds for checkout and install (default: 1800)")
    args = ap.parse_args(argv)
    pairs = load_pairs(args.pairs)
    work = args.work_dir or (ROOT / "ops" / "work" / "guard-dry-run")
    return run(pairs, args.guard, args.out, work, args.python, args.build_timeout)


if __name__ == "__main__":
    sys.exit(main())
