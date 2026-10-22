"""Summary of a benchmark results folder written by bench/run.py.

    python -m bench.summarize bench/results/<date> [--out DIR]     # writes summary.json and summary.md

Per arm, over the cases that arm was asked to run (n shown with every rate; small n: read the counts):
  wrong approvals      verified on a known regression (rate over regression cases)
  bugs caught          needs_attention on a known regression; recall overall and on tests-miss cases.
                       A case that did not run, or ended could_not_verify, is a miss, never a catch.
  false alarms         needs_attention on a known-safe case (rate over safe cases)
  verification coverage   cases with a decided verdict (verified or needs_attention) over all cases
  could not verify     could_not_verify or not run, over all cases (both counts also shown apart)
  setup failures       install stage failed, over all cases
  runtime, model calls and cost   sums over the runs that reported them (missing values are counted, not guessed)
Probe uplift = regression cases caught by tests+probes but not by tests-only (and the reverse, shown too), counted
only when both arms ran on the same commits, both installs succeeded, tests-only reached a decided verdict, and the
tests+probes flag comes from a probe finding that held on all 3 runs. Every other case is listed as excluded, with why.
n comes from the case list in run_meta.json: a case with no result file counts as not run.
No significance testing is done or claimed.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from bench.manifest import REGRESSION

DECIDED = ("verified", "needs_attention")


def rate(k: int, n: int) -> dict:
    return {"count": k, "n": n, "rate": round(k / n, 4) if n else None}


def arm_metrics(results: list[dict]) -> dict:
    reg = [r for r in results if r["category"] in REGRESSION]
    miss_cases = [r for r in results if r["category"] == "known_regression_tests_miss"]
    safe = [r for r in results if r["category"] == "known_safe"]
    v = lambda r: r["verdict"] if r.get("outcome") == "ran" else None  # noqa: E731
    caught = lambda rs: [r["case_id"] for r in rs if v(r) == "needs_attention"]  # noqa: E731
    n = len(results)
    secs = [r["wall_seconds"] for r in results if isinstance(r.get("wall_seconds"), (int, float))]
    calls = [r["model"]["ai_calls"] for r in results if isinstance((r.get("model") or {}).get("ai_calls"), int)]
    usd = [r["model"]["cost_usd"] for r in results if isinstance((r.get("model") or {}).get("cost_usd"), (int, float))]
    return {
        "n_cases": n,
        "wrong_approvals": rate(sum(1 for r in reg if v(r) == "verified"), len(reg)),
        "bugs_caught": rate(len(caught(reg)), len(reg)),
        "bugs_caught_tests_miss": rate(len(caught(miss_cases)), len(miss_cases)),
        "false_alarms": rate(sum(1 for r in safe if v(r) == "needs_attention"), len(safe)),
        "verification_coverage": rate(sum(1 for r in results if v(r) in DECIDED), n),
        "could_not_verify_or_not_run": rate(sum(1 for r in results if v(r) in (None, "could_not_verify")), n),
        "could_not_verify": sum(1 for r in results if v(r) == "could_not_verify"),
        "not_run": sum(1 for r in results if r.get("outcome") != "ran"),
        "setup_failures": rate(sum(1 for r in results if (r.get("stages") or {}).get("install") == "failed"), n),
        "matches_expected": rate(sum(1 for r in results if v(r) == r["expected_verdict"]), n),
        "runtime_s": {"total": round(sum(secs), 1), "n": len(secs)},
        "model_calls": {"total": sum(calls), "n_reported": len(calls)},
        "cost_usd": {"total": round(sum(usd), 6), "n_reported": len(usd)},
        "caught_ids": caught(reg),
    }


def _excluded_why(t: dict | None, p: dict | None) -> str | None:
    """Why a regression case cannot count toward probe uplift (None: it can)."""
    if t is None or p is None or t.get("outcome") != "ran" or p.get("outcome") != "ran":
        return "did not run in both arms"
    if t.get("tested") != p.get("tested"):
        return "the two arms tested different commits"
    if (t.get("stages") or {}).get("install") != "ok" or (p.get("stages") or {}).get("install") != "ok":
        return "install did not succeed in both arms"
    if t.get("verdict") not in DECIDED:
        return f"tests-only arm did not reach a decided verdict ({t.get('verdict')})"
    if p.get("verdict") != "needs_attention" or t.get("verdict") == "needs_attention":
        return None
    held = p.get("probe_held_all_runs")
    if held is None:
        return "record does not expose whether the probe result held on all runs"
    if held is not True:
        return "no probe finding held on all runs"
    return None


def uplift(tests: list[dict], probes: list[dict]) -> dict:
    """Planted regressions caught by tests+probes (a probe finding that held on every run) but not by tests-only,
    counted only where both arms ran on the same commits, both installs succeeded and tests-only decided."""
    t_by = {r["case_id"]: r for r in tests}
    p_by = {r["case_id"]: r for r in probes}
    ids = sorted({cid for cid, r in {**t_by, **p_by}.items() if r["category"] in REGRESSION})
    gained, lost, excluded, eligible = [], [], {}, 0
    for cid in ids:
        t, p = t_by.get(cid), p_by.get(cid)
        why = _excluded_why(t, p)
        if why:
            excluded[cid] = why
            continue
        eligible += 1
        t_hit, p_hit = t["verdict"] == "needs_attention", p["verdict"] == "needs_attention"
        if p_hit and not t_hit:
            gained.append(cid)
        elif t_hit and not p_hit:
            lost.append(cid)
    return {"caught_by_probes_not_tests": gained, "caught_by_tests_not_probes": lost,
            "regression_cases_compared": eligible, "excluded": excluded}


def _not_run(case: dict, arm: str) -> dict:
    return {"schema": "poc-bench-result/1", "case_id": case["id"], "arm": arm, "fixture": bool(case.get("fixture")),
            "category": case["category"], "expected_verdict": case["expected_verdict"], "outcome": "not_run",
            "verdict": None, "not_run_why": ["no result file"], "stages": {}, "wall_seconds": None, "model": {}}


def load(root: Path) -> dict[str, list[dict]]:
    """Results per arm. The case list and arms come from run_meta.json; a missing result counts as not run."""
    path = root / "run_meta.json"
    if not path.is_file():
        raise SystemExit(f"{path} is missing: summarize needs the run_meta.json that bench/run.py writes "
                         "(it holds the case list that n is counted from)")
    meta = json.loads(path.read_text())
    arms = {}
    for arm in meta["arms"]:
        d = root / arm.replace("+", "_")
        got = {}
        for f in sorted(d.glob("*.json")) if d.is_dir() else []:
            r = json.loads(f.read_text())
            if r.get("schema") == "poc-bench-result/1" and r.get("arm") == arm:
                got[r["case_id"]] = r
        arms[arm] = [got.get(c["id"]) or _not_run(c, arm) for c in meta["cases"]]
    return arms


def summarize(arms: dict[str, list[dict]]) -> dict:
    out = {"arms": {a: arm_metrics(rs) for a, rs in arms.items()},
           "fixture_results": any(r.get("fixture") for rs in arms.values() for r in rs)}
    if "tests" in arms and "tests+probes" in arms:
        out["probe_uplift"] = uplift(arms["tests"], arms["tests+probes"])
    return out


def _fmt(m: dict) -> str:
    return f"{m['count']}/{m['n']}" if m["n"] else "n/a (n=0)"


def markdown(s: dict) -> str:
    rows = ["| Arm | n | Wrong approvals | Bugs caught | Caught, tests-miss | False alarms | Decided | CNV or not run "
            "| Setup failures | Runtime s | Model calls | Cost USD |", "|" + "---|" * 12]
    for a, m in s["arms"].items():
        rows.append(f"| {a} | {m['n_cases']} | {_fmt(m['wrong_approvals'])} | {_fmt(m['bugs_caught'])} | "
                    f"{_fmt(m['bugs_caught_tests_miss'])} | {_fmt(m['false_alarms'])} | {_fmt(m['verification_coverage'])} | "
                    f"{_fmt(m['could_not_verify_or_not_run'])} ({m['not_run']} not run) | {_fmt(m['setup_failures'])} | "
                    f"{m['runtime_s']['total']} | {m['model_calls']['total']} ({m['model_calls']['n_reported']} reported) | "
                    f"{m['cost_usd']['total']} |")
    head = "# Benchmark summary\n\n"
    if s.get("fixture_results"):
        head += "**FIXTURE DATA: these are unit-test fixtures, not benchmark results.**\n\n"
    tail = ""
    if "probe_uplift" in s:
        u = s["probe_uplift"]
        tail = (f"\nProbe uplift: {len(u['caught_by_probes_not_tests'])} planted regression(s) caught by tests+probes but "
                f"not by tests-only ({', '.join(u['caught_by_probes_not_tests']) or 'none'}); "
                f"{len(u['caught_by_tests_not_probes'])} the other way; over {u['regression_cases_compared']} "
                "comparable regression case(s).\n")
        tail += "".join(f"- excluded {cid}: {why}\n" for cid, why in u["excluded"].items())
    note = ("\nA case that did not run or ended could_not_verify counts as a miss, never a catch. Counts, not "
            "significance: no statistical test is claimed.\n")
    return head + "\n".join(rows) + "\n" + tail + note


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("results")
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)
    root = Path(a.results)
    s = summarize(load(root))
    out = Path(a.out or root)
    out.mkdir(parents=True, exist_ok=True)
    (out / "summary.json").write_text(json.dumps(s, indent=1))
    md = markdown(s)
    (out / "summary.md").write_text(md)
    print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
