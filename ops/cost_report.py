"""Recompute AI cost from saved run folders (raw model replies + review records) and write a plain summary.

usage: python ops/cost_report.py OUT.md RUN_DIR [RUN_DIR ...]
Every attempt counts toward spend, also could-not-verify ones. Copies made for scoring (folders named score*)
are skipped so nothing is counted twice.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from poc import cost  # noqa: E402


def _skip(p: Path) -> bool:
    return any(part.startswith("score") for part in p.parts)


def collect(run_dirs: list[Path]) -> dict:
    tools = {"ours": {"records": [], "calls": [], "compute": 0.0, "no_raw": []},
             "patchguru": {"records": [], "pre": [], "calls": [], "compute": 0.0, "no_raw": []}}
    for rd in run_dirs:
        for f in sorted(rd.rglob("*.json")):
            if _skip(f.relative_to(rd)):
                continue
            rel = f.relative_to(rd.parent)
            if f.parent.name == "raw":
                d = json.loads(f.read_text())
                if "/patchguru/" in str(f):
                    resp = d.get("response") or {}
                    tools["patchguru"]["calls"].append({"model": resp.get("model") or d["request"]["model"],
                                                        "usage": resp.get("usage"), "src": str(rel)})
                else:
                    tools["ours"]["calls"].append({"model": d.get("server_model") or d.get("requested_model"),
                                                   "usage": d.get("usage"), "ok": not d.get("error"),
                                                   "src": str(rel)})
                continue
            if "logs" in f.parts:
                continue
            n = f.name
            kind = ("ours" if n.endswith(("-full.json", "-tests.json")) else
                    "patchguru" if n.endswith("-patchguru_post_review.json") else
                    "pre" if n.endswith("-patchguru_pre_review.json") else None)
            if kind is None:
                continue
            r = json.loads(f.read_text())
            item = {"file": str(rel), "case": n.split("-")[0], "verdict": r.get("verdict")}
            if kind == "pre":
                tools["patchguru"]["pre"].append(item)
                continue
            t = tools[kind]
            t["records"].append(item)
            t["compute"] += (r.get("duration_s") or {}).get("total_wall", 0) if kind == "ours" else r.get("elapsed_s", 0)
            raw = (f.parent / "raw") if kind == "ours" else (f.parent / "logs" / item["case"] / "patchguru" / "raw")
            if kind == "ours" and n.endswith("-tests.json"):
                t.setdefault("tests_only", []).append(item["file"])   # tests-only mode makes no AI calls by design
            elif not (raw.is_dir() and any(raw.iterdir())):
                t["no_raw"].append(item["file"])
    return tools


def render(tools: dict, run_dirs: list[Path]) -> str:
    L = ["# AI cost for the 2026-10-13 runs (all pilot)", "",
         f"Prices: {cost.RATE_SOURCE}. Nemotron 3 Super: $0.30 per 1M input tokens, $0.90 per 1M output tokens; "
         "Nano: $0.06 / $0.24. Thinking tokens are part of output and billed as output.", "",
         "How to read the two numbers: *cost per PR attempted* = all AI spend / every run, including runs that "
         "could not verify. *Cost per PR with a final verdict* = the same spend / only the runs that ended "
         "verified or needs_attention. Could-not-verify runs still count toward spend.", "",
         "Run folders: " + ", ".join(p.name for p in run_dirs) + " (score copies skipped).", "",
         "## Headline", "",
         "| tool | runs attempted | with final verdict | AI calls | input tok | output tok | of which thinking | "
         "total $ | $ per PR attempted | $ per PR with final verdict | machine time (h) |",
         "|---|---|---|---|---|---|---|---|---|---|---|"]
    out = {}
    for name, label in (("ours", "Proof-of-Change"), ("patchguru", "PatchGuru")):
        t = tools[name]
        s = cost.summarize(t["calls"])
        recs = [dict(r, cost_usd=0) for r in t["records"]]
        if recs:
            recs[0]["cost_usd"] = s["cost_usd"]
        p = cost.per_pr(recs)
        out[name] = (s, p)
        f = lambda v: "n/a" if v is None else f"${v:.4f}"   # noqa: E731
        L.append(f"| {label} | {p['attempted']} | {p['with_final_verdict']} | {s['ai_calls']} | {s['input_tokens']:,} | "
                 f"{s['output_tokens']:,} | {s['thinking_tokens']:,} | {f(s['cost_usd'])} | "
                 f"{f(p['per_pr_attempted_usd'])} | {f(p['per_pr_with_final_verdict_usd'])} | {t['compute'] / 3600:.2f} |")
    L += ["", "PatchGuru counts one attempt per case run (its before- and after-self-review results come from the same "
          "AI calls); the final verdict is the after-self-review one. "
          f"Before self-review, {sum(1 for r in tools['patchguru']['pre'] if r['verdict'] in ('verified', 'needs_attention'))} "
          f"of {len(tools['patchguru']['pre'])} runs had a final verdict.", "",
          "## Where data is missing", "",
          f"- Not missing: the {len(tools['ours'].get('tests_only', []))} Proof-of-Change tests-only runs make no AI "
          "calls by design, so they cost $0 in AI and are correctly counted as attempts with zero spend."]
    for name, label in (("ours", "Proof-of-Change"), ("patchguru", "PatchGuru")):
        s, _ = out[name]
        if s["calls_without_usage"]:
            L.append(f"- {label}: {s['calls_without_usage']} saved AI call(s) have no token counts (the call failed "
                     "before the server answered, e.g. a timeout), so their cost is unknown and counted as $0.")
        if tools[name]["no_raw"]:
            L.append(f"- {label}: {len(tools[name]['no_raw'])} run(s) have no saved AI replies next to them. Either "
                     "the run stopped before any AI call (for example the build failed), or it ran before raw replies "
                     "were saved (the first live runs this morning), or a later rerun overwrote the same folder. Their "
                     "AI cost is not in the totals. Runs: " + ", ".join(tools[name]["no_raw"]))
    L += ["- Machine time comes from each record's wall-clock duration; separate build and test times exist only in "
          "the newest records, so only the total is summed here.",
          "- Prices are list prices; any discount or free credit on the account is not reflected.",
          "- From the next run on, every record carries its own `cost` block (tokens, calls, price, machine time), "
          "so this reconstruction will not be needed."]
    return "\n".join(L) + "\n"


def main(argv: list[str]) -> None:
    out, dirs = Path(argv[0]), [Path(a) for a in argv[1:]]
    out.write_text(render(collect(dirs), dirs))


if __name__ == "__main__":
    main(sys.argv[1:])
