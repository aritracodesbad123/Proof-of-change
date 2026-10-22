# ruff: noqa: E501, E701  (long Markdown template lines in a one-off publishing script)
"""Publish the 30-PR batch from the folder the batch runner wrote.

    python benchmarks/batch30-0fa0016/publish.py --src <batch run folder>

For each run, copies record.json, REPORT.md and REPORT.html exactly as the tool wrote them.
The only change is replacing local machine paths with placeholders (see PLACEHOLDERS);
no verdict, reason or other field is touched. MANIFEST.json stores the sha256 of each raw
file and of the published file so the copy can be checked against the originals.
labels.json is published with every PR set to "unlabelled": the GitHub search found no
revert, follow-up bug report or maintainer confirmation, and passing CI is not proof.
The PR table, SCORING.md and the timing figures are generated from the published records.
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import re
import statistics
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
PLACEHOLDERS = [
    (re.compile(r"/" + r"workspace/batch30-work/runs/[^/\s\"'<]+/(ops/runs/[^/\s\"'<]+/)?"), "<run>/"),
    (re.compile(r"/home/[^\s\"'<]*"), "<home>"),
    (re.compile(r"/" + r"workspace\b[^\s\"'<]*"), "<work>"),
]
VLABEL = {"needs_attention": "Needs attention", "could_not_verify": "Could not verify", "verified": "Verified"}


def placeholder(text: str) -> str:
    for pat, rep in PLACEHOLDERS:
        text = pat.sub(rep, text)
    return text


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def mins(s: float) -> str:
    s = round(s)
    return f"{s // 60} min {s % 60} s" if s >= 60 else f"{s} s"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    src = Path(ap.parse_args().src)
    manifest, rows = {}, []
    drawn = {d["url"]: d for d in json.loads((src / "drawn.json").read_text())["drawn"]}
    for run in sorted(p for p in (src / "runs").iterdir() if p.is_dir()):
        rec_path = Path(glob.glob(str(run / "ops/runs/*/*/record.json"))[0])
        report_dir = Path(glob.glob(str(run / "report/*/"))[0])
        out = HERE / "runs" / run.name
        out.mkdir(parents=True, exist_ok=True)
        for raw in (rec_path, report_dir / "REPORT.md", report_dir / "REPORT.html"):
            data = raw.read_bytes()
            pub = placeholder(data.decode()).encode()
            (out / raw.name).write_bytes(pub)
            manifest[f"runs/{run.name}/{raw.name}"] = {"raw_sha256": sha(data), "published_sha256": sha(pub)}
        rec = json.loads(rec_path.read_text())
        summary = (run / "report" / "SUMMARY.md").read_text()
        conf = re.search(r"\((\w+) confidence\)", summary).group(1)
        report_verdict = re.search(r"\*\*(COULD NOT VERIFY|NEEDS ATTENTION|VERIFIED)\*\*", summary).group(1)
        dur = rec.get("duration_s")
        rows.append({
            "name": run.name, "repo": rec["repo"], "url": rec["pr"]["url"], "title": drawn[rec["pr"]["url"]]["title"],
            "verdict": rec["verdict"], "reason": rec["reason"], "confidence": conf, "report_verdict": report_verdict,
            "seconds": dur.get("total_wall") if isinstance(dur, dict) else dur,
        })
    (HERE / "MANIFEST.json").write_text(json.dumps(manifest, indent=1, sort_keys=True) + "\n")
    (HERE / "drawn.json").write_bytes((src / "drawn.json").read_bytes())
    labels = json.loads((src / "labels.json").read_text())
    for x in labels:
        x["search_result"] = x.pop("label")
        x["label"] = "unlabelled"
        x["why_unlabelled"] = "no revert, follow-up bug report or maintainer confirmation found; passing CI is not proof"
    (HERE / "labels.json").write_text(json.dumps(labels, indent=1) + "\n")
    write_docs(rows)
    return 0


def write_docs(rows: list[dict]) -> None:
    vc = Counter(r["verdict"] for r in rows)
    untrusted = [r for r in rows if r["verdict"] == "needs_attention" and r["report_verdict"] != "NEEDS ATTENTION"]
    def cat(r):
        w = r["reason"]
        if r["verdict"] == "needs_attention": return "Difference found between main and PR"
        if w.startswith("install failed"): return "Setup failure: install failed"
        if "setup gap" in w: return "Setup failure: setup gap"
        if "no results on one side" in w or "no test actually ran" in w: return "Tests did not run or collect"
        return "Changed code not exercised (incl. docstring-only)"
    cc = Counter(cat(r) for r in rows)
    secs = sorted(rows, key=lambda r: r["seconds"])
    med = statistics.median(r["seconds"] for r in rows)
    slow = secs[::-1][:3]
    def num(r): return r["url"].rsplit("/", 1)[1]
    trust = ", ".join(f"[{r['repo']} #{num(r)}](runs/{r['name']}/REPORT.md)" for r in untrusted)
    score = f"""## Scoring: 30-PR random batch (code version 0fa0016)

30 merged pull requests from public Python projects, drawn at random with a fixed seed (20261022; list in `drawn.json`). Every check ran on Proof-of-Change at commit `0fa0016`, finishing on 22 Oct 2026 at 11:03 IST. All 30 runs completed; none crashed. Verdicts are the ones in each run's own `record.json`.

### Verdicts

| Verdict | Count |
|---|---|
| Verified | {vc['verified']} |
| Needs attention | {vc['needs_attention']} |
| Could not verify | {vc['could_not_verify']} |

The trust check in the report flags {trust} as untrustworthy (the run failed its own checks), so treat those two needs-attention verdicts with caution.

### Why: breakdown of reasons

| Reason | Runs |
|---|---|
""" + "".join(f"| {k} | {v} |\n" for k, v in cc.most_common()) + f"""
Setup failures (install failed or setup gap) total {cc['Setup failure: install failed'] + cc['Setup failure: setup gap']} of 30. This is the biggest weakness the batch shows.

### Timing

From each record's `duration_s.total_wall`. Median run: {mins(med)}. Fastest: {secs[0]['repo']} #{num(secs[0])} ({mins(secs[0]['seconds'])}). Slowest: {', '.join(f"{r['repo']} #{num(r)} ({mins(r['seconds'])})" for r in slow)}. The MACS #784 run is the outlier.

### Accuracy: not measured for this batch

Catches, misses and false alarms count only where there is outside proof of the right answer: a later revert, a follow-up bug report blaming the PR, or a maintainer's explicit confirmation. Passing maintainer CI or closing a linked issue is not proof. We searched GitHub for reverts and follow-up fixes for all 30 PRs and found none, so **all 30 PRs are unlabelled** (`labels.json`) and no accuracy, false-alarm or miss rate is reported. No labels were invented.
"""
    (HERE / "SCORING.md").write_text(score)
    tbl = "| # | Repo | PR | Verdict | Confidence | Reason (one line) | Report |\n|---|---|---|---|---|---|---|\n"
    for i, r in enumerate(rows, 1):
        why = r["reason"].replace("|", "/")
        why = why[:160] + ("…" if len(why) > 160 else "")
        flag = " (report trust check failed)" if r in untrusted else ""
        tbl += f"| {i} | {r['repo']} | [#{num(r)}]({r['url']}) | {VLABEL[r['verdict']]}{flag} | {r['confidence']} | {why} | [report](runs/{r['name']}/REPORT.md) |\n"
    (HERE / "README.md").write_text(
        "# 30-PR random batch, code version 0fa0016\n\n"
        "Results of 30 random merged PRs checked on Proof-of-Change commit `0fa0016` (22 Oct 2026). "
        "Each run's `record.json`, `REPORT.md` and `REPORT.html` are in `runs/<repo>-<pr>/`, as the tool wrote them; "
        "the only change is local machine paths replaced with placeholders by `publish.py`. "
        "`MANIFEST.json` lists the sha256 of each raw and published file.\n\n"
        "- [Scoring](SCORING.md)\n- [Needs-attention notes](NEEDS_ATTENTION_NOTES.md)\n"
        "- `drawn.json`: the seed and the PRs drawn\n- `labels.json`: all 30 unlabelled, with what the GitHub search found\n"
        "- `publish.py`: rebuilds this folder from the batch run folder\n\n## Results\n\n" + tbl)
    notes = (f"# Needs-attention notes for joint review (batch 0fa0016)\n\n{vc['needs_attention']} runs found a difference between main and the PR. "
             "None has outside proof either way.\n\n")
    for r in rows:
        if r["verdict"] != "needs_attention":
            continue
        flags = ""
        if r in untrusted:
            flags += "\n- **Flag:** the report's trust check marks this run untrustworthy (the run failed its own checks)."
        if "194 test(s) pass on main but fail on the PR" in r["reason"]:
            flags += "\n- **Flag: possible environment issue.** 194 tests passed on main and failed on the PR, while 200 went the other way. Swings that large in both directions point to the test environment, not the change."
        if "removed on the PR side" in r["reason"]:
            flags += "\n- **Flag:** tests removed on the PR side can be a deliberate cleanup; check before counting it as a problem."
        notes += (f"## {r['repo']} #{num(r)}: {r['title']}\n\n- Verdict: {VLABEL[r['verdict']]} ({r['confidence']} confidence)\n"
                  f"- Claim (PR title): {r['title']}\n- What differed: {r['reason'][:500]}\n"
                  f"- Evidence: [PR]({r['url']}) · [report](runs/{r['name']}/REPORT.md) · [record](runs/{r['name']}/record.json){flags}\n\n")
    (HERE / "NEEDS_ATTENTION_NOTES.md").write_text(notes)


if __name__ == "__main__":
    raise SystemExit(main())
