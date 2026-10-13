"""Recompute cost from saved run folders (raw model replies + review records) and write a plain summary.

usage: python ops/cost_report.py OUT.md RUN_DIR [RUN_DIR ...]
Every attempt counts toward spend, also could-not-verify ones. Copies made for scoring (folders named score*)
are skipped so nothing is counted twice. AI cost is tied to a run as follows: PatchGuru keeps its replies per case;
Proof-of-Change keeps one reply folder per mode, so a reply is tied to the run whose time window contains it
(window = record start time to start + wall time). Replies no run window contains are still counted in the tool's
total spend, as "not tied to a run".
"""
from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from poc import cost  # noqa: E402

TOOLS = (("ours", "Proof-of-Change"), ("patchguru", "PatchGuru"))


def _skip(p: Path) -> bool:
    return any(part.startswith("score") for part in p.parts)


def _hms(name: str) -> int | None:
    h = name.split("-")[0]
    return int(h[:2]) * 3600 + int(h[2:4]) * 60 + int(h[4:6]) if len(h) == 6 and h.isdigit() else None


def _start(r: dict) -> int | None:
    t = r.get("tested_at_ist") or ""
    try:
        x = dt.datetime.strptime(t[:16], "%Y-%m-%d %H:%M")
    except ValueError:
        return None
    return x.hour * 3600 + x.minute * 60


def _ours_call(d: dict) -> dict:
    return {"model": d.get("server_model") or d.get("requested_model"), "usage": d.get("usage"), "ok": not d.get("error")}


def _pg_call(d: dict) -> dict:
    resp = d.get("response") or {}
    return {"model": resp.get("model") or (d.get("request") or {}).get("model"), "usage": resp.get("usage")}


def collect(run_dirs: list[Path]) -> dict:
    tools = {k: {"records": [], "pre": [], "calls": [], "untied": [], "no_raw": [], "tests_only": []} for k, _ in TOOLS}
    for rd in run_dirs:
        for f in sorted(rd.rglob("*.json")):
            if _skip(f.relative_to(rd)) or f.parent.name == "raw" or "logs" in f.parts:
                continue
            n = f.name
            kind = ("ours" if n.endswith(("-full.json", "-tests.json")) else
                    "patchguru" if n.endswith("-patchguru_post_review.json") else
                    "pre" if n.endswith("-patchguru_pre_review.json") else None)
            if kind is None:
                continue
            r = json.loads(f.read_text())
            item = {"file": str(f.relative_to(rd.parent)), "case": n.split("-")[0], "verdict": r.get("verdict"),
                    "calls": []}
            if kind == "pre":
                tools["patchguru"]["pre"].append(item)
                continue
            wall = (r.get("duration_s") or {}).get("total_wall", 0) if kind == "ours" else r.get("elapsed_s", 0)
            item["wall"], item["start"], item["dir"] = wall or 0, _start(r), f.parent
            if kind == "patchguru":
                raw = f.parent / "logs" / item["case"] / "patchguru" / "raw"
                item["calls"] = [_pg_call(json.loads(x.read_text())) for x in sorted(raw.glob("*.json"))] \
                    if raw.is_dir() else []
                if not item["calls"]:
                    tools["patchguru"]["no_raw"].append(item["file"])
            elif n.endswith("-tests.json"):
                tools["ours"]["tests_only"].append(item["file"])   # tests-only mode makes no AI calls by design
            tools[kind]["records"].append(item)
    # Proof-of-Change: tie each saved reply to the run whose time window contains it.
    for rd in run_dirs:
        for raw in sorted(rd.rglob("raw")):
            if _skip(raw.relative_to(rd)) or "patchguru" in raw.parts or not raw.is_dir():
                continue
            runs = [x for x in tools["ours"]["records"] if x["dir"] == raw.parent and x["start"] is not None]
            for x in sorted(raw.glob("*.json")):
                c, t = _ours_call(json.loads(x.read_text())), _hms(x.name)
                hit = [r for r in runs if t is not None and r["start"] - 60 <= t <= r["start"] + r["wall"] + 120]
                (hit[0]["calls"] if hit else tools["ours"]["untied"]).append(c)
    for r in tools["ours"]["records"]:
        if not r["calls"] and r["file"] not in tools["ours"]["tests_only"]:
            tools["ours"]["no_raw"].append(r["file"])
    for t in tools.values():
        for r in t["records"]:
            s = cost.summarize(r["calls"], {"total_wall": r["wall"]})
            r.update(cost_usd=s["ai_cost_usd"], computer_cost_usd=s["computer_cost_usd"],
                     missing_usage=s["calls_without_usage"])
            t["calls"] += r["calls"]
        t["calls"] += t["untied"]
    return tools


def _f(v):
    return "n/a" if v is None else f"${v:.4f}"


def _pct(v):
    return "n/a" if v is None else f"{v:.0%}"


def _table(rows: list[tuple[str, dict]], untied: dict | None = None) -> list[str]:
    L = ["| tool | PRs attempted | with final verdict | verdict rate | AI $ | computer $ | total $ | "
         "AI $ / PR attempted | computer $ / PR attempted | **total $ / PR attempted** | "
         "AI $ / PR with final verdict | computer $ / PR with final verdict | **total $ / PR with final verdict** "
         "(verdict rate) |", "|" + "---|" * 14]
    for label, p in rows:
        L.append(f"| {label} | {p['attempted']} | {p['with_final_verdict']} | {_pct(p['verdict_rate'])} | "
                 f"{_f(p['ai_usd'])} | {_f(p['computer_usd'])} | {_f(p['total_all_usd'])} | "
                 f"{_f(p['ai_per_attempted'])} | {_f(p['computer_per_attempted'])} | **{_f(p['total_per_attempted'])}** | "
                 f"{_f(p['ai_per_final'])} | {_f(p['computer_per_final'])} | **{_f(p['total_per_final'])}** "
                 f"({_pct(p['verdict_rate'])}) |")
    return L


def _with_untied(t: dict) -> list[dict]:
    """All-runs view: replies not tied to any run still count toward spend (added to the first record)."""
    recs = [dict(r) for r in t["records"]]
    extra = cost.summarize(t["untied"])["ai_cost_usd"]
    if recs:
        recs[0]["cost_usd"] = (recs[0]["cost_usd"] or 0) + extra
    return recs


def render(tools: dict, run_dirs: list[Path]) -> str:
    rate, rsrc = cost.machine_rate()
    common = sorted({r["case"] for r in tools["ours"]["records"]} & {r["case"] for r in tools["patchguru"]["records"]})
    L = ["# Cost for the 2026-10-13 runs: PILOT figures, some data missing", "",
         "> All numbers here are **pilot** figures from today's trial runs, and **some data is missing** (see the "
         "last section), so the real cost is somewhat higher than shown. Do not quote them as final.", "",
         f"- AI prices: {cost.RATE_SOURCE}. Nemotron 3 Super $0.30 / 1M input and $0.90 / 1M output tokens; "
         "Nano $0.06 / $0.24. Thinking tokens are part of output and billed as output.",
         f"- Computer time is priced at **${rate:.3f} per hour**: {rsrc}. The test machine has 8 vCPUs (Intel Xeon) and about "
         "16 GiB RAM; Nebius's smallest 8-vCPU Intel preset has 32 GiB, so this rate slightly over-prices memory. "
         "Change it with POC_MACHINE_USD_PER_HOUR.",
         "- *Per PR attempted* = spend / every run, including could-not-verify runs. *Per PR with a final verdict* = "
         "the same spend / only runs that ended verified or needs_attention. *Verdict rate* = final verdicts / attempts. "
         "Could-not-verify runs still count toward spend.",
         "- PatchGuru: one attempt per case run (its before- and after-self-review results share the same AI calls); "
         "the final verdict is the after-self-review one.",
         "- Run folders: " + ", ".join(p.name for p in run_dirs) + " (score copies skipped).", "",
         "## Matched comparison: only PRs both tools attempted", "",
         f"Cases both tools attempted: {', '.join(common) or 'none'}. Every run of those cases by each tool is "
         "counted. AI spend here includes only replies that could be tied to a run.", ""]
    L += _table([(label, cost.per_pr([r for r in tools[k]["records"] if r["case"] in common])) for k, label in TOOLS])
    L += ["", "## All runs (each tool's full totals, not a like-for-like comparison)", ""]
    L += _table([(label, cost.per_pr(_with_untied(tools[k]))) for k, label in TOOLS])
    for k, label in TOOLS:
        s = cost.summarize(tools[k]["calls"])
        L.append(f"\n{label}: {s['ai_calls']} AI calls, {s['input_tokens']:,} input / {s['output_tokens']:,} output "
                 f"tokens ({s['thinking_tokens']:,} thinking); machine time "
                 f"{sum(r['wall'] for r in tools[k]['records']) / 3600:.2f} h.")
    pre = tools["patchguru"]["pre"]
    L += [f"\nBefore self-review, PatchGuru had a final verdict on "
          f"{sum(1 for r in pre if r['verdict'] in ('verified', 'needs_attention'))} of {len(pre)} runs.", "",
          "## Where data is missing", "",
          f"- Not missing: the {len(tools['ours']['tests_only'])} Proof-of-Change tests-only runs make no AI calls by "
          "design; they carry computer cost only."]
    for k, label in TOOLS:
        s = cost.summarize(tools[k]["calls"])
        if s["calls_without_usage"]:
            L.append(f"- {label}: {s['calls_without_usage']} AI call(s) have no token counts (the call failed before "
                     "the server answered, e.g. a timeout); their AI cost is unknown and counted as $0.")
        if tools[k]["untied"]:
            L.append(f"- {label}: {len(tools[k]['untied'])} saved AI call(s) could not be tied to a specific run "
                     f"(${cost.summarize(tools[k]['untied'])['ai_cost_usd']:.4f}); they are in the all-runs totals but "
                     "not in the matched comparison.")
        if tools[k]["no_raw"]:
            L.append(f"- {label}: {len(tools[k]['no_raw'])} run(s) have no saved AI replies. Either the run stopped "
                     "before any AI call (e.g. the build failed), ran before replies were saved (this morning's first "
                     "live runs), or a later rerun overwrote the folder. Their AI cost is not in the totals (computer "
                     "cost is). Runs: " + ", ".join(tools[k]["no_raw"]))
    L += ["- Computer time is each record's wall-clock time; build and test time are split out only in the newest "
          "records. Waiting between runs, failed setup outside a record, and disk are not priced.",
          "- List prices only; account discounts or credits are not reflected.",
          "- From the next run on, every record carries its own `cost` block (AI, computer and total cost), so this "
          "reconstruction will not be needed."]
    return "\n".join(L) + "\n"


def main(argv: list[str]) -> None:
    out, dirs = Path(argv[0]), [Path(a) for a in argv[1:]]
    out.write_text(render(collect(dirs), dirs))


if __name__ == "__main__":
    main(sys.argv[1:])
