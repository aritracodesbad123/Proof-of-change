# ruff: noqa: E501
"""Publish the finished Contree checks from ops/runs/contree30.

    python benchmarks/contree30-2026-10-23/publish.py

Copies each finished record.json and the run REPORT.md. The only edit is replacing
local machine paths with <home>. Verdicts and reasons are copied, not rewritten.
A check with no record.json keeps the harness line from its REPORT.md.
"""
from __future__ import annotations

import ast
import hashlib
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SRC = ROOT / "ops" / "runs" / "contree30"
HOME = re.compile(r"/Users/[^/\s\"'<]+")
VLABEL = {
    "needs_attention": "Needs attention",
    "could_not_verify": "Could not verify",
    "verified": "Verified",
    "no_code_change": "No code change",
    "no-record": "No verdict file",
    "not_run": "Not run",
}


def redact(text: str) -> str:
    return HOME.sub("<home>", text)


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def prs() -> list[tuple[str, int, str]]:
    text = (SRC / "run_batch.py").read_text()
    block = text.split("PRS = ", 1)[1].split("]\n", 1)[0] + "]"
    return [(r, int(n), u) for r, n, u in ast.literal_eval(block)]


def plain(verdict: str, reason: str) -> str:
    """One sentence for the table. The record's own reason is stored unchanged beside it."""
    if "ApiTimeoutError" in reason or "ContreeTransportError" in reason:
        if verdict == "no-record":
            return ("Contree's HTTP call timed out (the SDK allows 10 seconds for one poll) and the check "
                    "exited with no verdict file. Pull-request code was not run locally.")
        return ("Contree could not prepare the main and pull-request sides: one HTTP call exceeded the SDK's "
                "10 second timeout, so the sandbox was cancelled. Pull-request code was not run locally.")
    if reason.startswith("git step failed"):
        return ("Cloning the repository from GitHub failed on the machine running the check (the connection "
                "was reset, then a later fetch timed out). Contree did not run.")
    if reason.startswith("no tests could be mapped"):
        return "No project test could be mapped to the files the pull request changed, so the change cannot be verified."
    if "collection failed" in reason or "no results on one side" in reason:
        return "Pytest produced no results on one side, so the two sides could not be compared."
    if "Coverage wasn't measured" in reason:
        return "The tests ran, but coverage produced no data, so the check is not allowed to say verified."
    if "setup gap" in reason:
        return "A test module failed to import during setup, so the check stopped before a comparison."
    if "not_adequate" in reason or "no observation matches" in reason:
        return ("The project's tests ran, but a probe was not adequate or a claim had no matching observation, "
                "so the change stays could not verify.")
    if verdict == "needs_attention":
        return "The check found a difference between main and the pull request."
    return reason


def pick_record(folder: Path, verdict: str) -> Path | None:
    found = sorted(folder.rglob("record.json"), key=lambda p: p.stat().st_mtime)
    matched = []
    for path in found:
        try:
            rec = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        if rec.get("verdict") == verdict:
            matched.append(path)
    if matched:
        return matched[-1]
    return found[-1] if found else None


def harness_reason(report: Path) -> str:
    text = report.read_text() if report.exists() else ""
    for line in text.splitlines():
        if "harness error:" in line:
            return line.split("harness error:", 1)[1].strip()
    return ""


def confidence(repo: str, num: int) -> str:
    slug = repo.split("/")[-1]
    summary = ROOT / "reports" / "daily" / f"{slug}-{num}" / "SUMMARY.md"
    if not summary.exists():
        return ""
    m = re.search(r"\((\w+) confidence\)", summary.read_text())
    return m.group(1) if m else ""


def main() -> int:
    status = {}
    for line in (SRC / "status.jsonl").read_text().splitlines():
        if line.strip():
            row = json.loads(line)
            status[(row["repo"], row["pr"])] = row
    meta = {(x["repo"], x["pr"]): x for x in json.loads((SRC / "pr_meta.json").read_text())}
    manifest, rows, labels = {}, [], []
    runs = HERE / "runs"
    if runs.exists():
        for old in runs.rglob("*"):
            if old.is_file():
                old.unlink()
    for repo, num, url in prs():
        slug = f"{repo.split('/')[-1]}-{num}"
        row = status.get((repo, num))
        info = meta.get((repo, num), {})
        title = info.get("title") or ""
        refs = info.get("fix_refs") or []
        links = info.get("linked_issue_urls") or []
        labels.append({
            "url": url, "title": title, "label": "unlabelled",
            "named_by_pr": [f"#{n}" for n in refs] + links,
            "why_unlabelled": ("the pull request text names an issue; that is not proof of a bug in the change. "
                               "No revert, follow-up bug report, or maintainer confirmation was recorded."),
        })
        if row is None:
            rows.append({
                "slug": slug, "repo": repo, "pr": num, "url": url, "title": title,
                "verdict": "not_run", "reason": "",
                "plain": "The batch was stopped before this check finished.",
                "seconds": None, "confidence": "", "exit": None,
            })
            continue
        folder = SRC / "runs" / slug
        verdict = row.get("verdict") or "no-record"
        rec_path = pick_record(folder, verdict) if folder.exists() else None
        reason = ""
        if rec_path is not None:
            raw = rec_path.read_bytes()
            rec = json.loads(raw)
            verdict = rec.get("verdict") or verdict
            reason = rec.get("reason") or ""
            out = runs / slug
            out.mkdir(parents=True, exist_ok=True)
            pub = redact(raw.decode()).encode()
            (out / "record.json").write_bytes(pub)
            manifest[f"runs/{slug}/record.json"] = {"raw_sha256": sha(raw), "published_sha256": sha(pub)}
        else:
            reason = harness_reason(folder / "REPORT.md")
            verdict = "no-record"
        report = folder / "REPORT.md"
        if report.exists():
            out = runs / slug
            out.mkdir(parents=True, exist_ok=True)
            data = report.read_bytes()
            pub = redact(data.decode()).encode()
            (out / "REPORT.md").write_bytes(pub)
            manifest[f"runs/{slug}/REPORT.md"] = {"raw_sha256": sha(data), "published_sha256": sha(pub)}
        if reason.startswith("git step failed"):
            reason = redact(reason)
        rows.append({
            "slug": slug, "repo": repo, "pr": num, "url": url, "title": title,
            "verdict": verdict, "reason": reason, "plain": plain(verdict, reason),
            "seconds": row.get("seconds"), "confidence": confidence(repo, num), "exit": row.get("exit"),
        })
    (HERE / "MANIFEST.json").write_text(json.dumps(manifest, indent=1, sort_keys=True) + "\n")
    (HERE / "labels.json").write_text(json.dumps(labels, indent=1) + "\n")
    write_docs(rows)
    return 0


def mins(s: float) -> str:
    s = round(s)
    if s >= 3600:
        return f"{s // 3600} h {(s % 3600) // 60} min"
    if s >= 60:
        return f"{s // 60} min {s % 60} s"
    return f"{s} s"


def write_docs(rows: list[dict]) -> None:
    done = [r for r in rows if r["verdict"] != "not_run"]
    counts: dict[str, int] = {}
    for r in done:
        counts[r["verdict"]] = counts.get(r["verdict"], 0) + 1
    groups: dict[str, list[str]] = {}
    for r in done:
        if r["verdict"] != "could_not_verify" and r["verdict"] != "no-record":
            continue
        groups.setdefault(r["plain"], []).append(f"{r['repo']} #{r['pr']}")
    why_rows = "".join(f"| {len(v)} | {k} | {', '.join(v)} |\n" for k, v in groups.items())
    named = [x for x in json.loads((HERE / "labels.json").read_text()) if x["named_by_pr"]]
    def pr_name(url: str) -> str:
        parts = url.rstrip("/").split("/")
        return f"{parts[-4]}/{parts[-3]} #{parts[-1]}"

    named_rows = "".join(f"| {pr_name(x['url'])} | {', '.join(x['named_by_pr'])} |\n" for x in named)
    score = f"""## Scoring: 20 finished Contree checks (stopped early)

Open pull requests from 20 Python projects, checked in Contree on Proof-of-Change commit `863751e` (23 Oct 2026). The batch was stopped on 24 Oct 2026 while it was still running. 20 checks had finished. 10 had not, and they are listed as not run. Verdicts are the ones in each run's own `record.json`. Two checks exited with a harness error and have no verdict file; their reason is the line in `REPORT.md`.

The 120 second HTTP timeout is not in commit `863751e`. Each check fast-forwards to main before it starts, so these runs used the Contree SDK's 10 second HTTP timeout.

### Verdicts

| Verdict | Count |
|---|---|
| Verified | {counts.get('verified', 0)} |
| Needs attention | {counts.get('needs_attention', 0)} |
| Could not verify | {counts.get('could_not_verify', 0)} |
| No verdict file | {counts.get('no-record', 0)} |
| Not run | {sum(1 for r in rows if r['verdict'] == 'not_run')} |

### Why a check could not verify

The sentence is a reading of the record's reason. The record text is in the results table and is unchanged.

| Runs | Why | Pull requests |
|---|---|---|
{why_rows}
### Known bugs named by the pull request

A number in this table is an issue the pull request text says it fixes, or a linked issue URL from that text. Naming an issue is not proof the change is wrong or right, so every pull request stays `unlabelled` in `labels.json`. No catch rate, miss rate, or false-alarm rate is reported.

| Pull request | Named by the pull request |
|---|---|
{named_rows if named_rows else "| none | |\n"}
"""
    (HERE / "SCORING.md").write_text(score)
    tbl = ("| # | Repo | PR | Verdict | Why | Record reason |\n"
           "|---|---|---|---|---|---|\n")
    for i, r in enumerate(rows, 1):
        why = r["plain"].replace("|", "/")
        raw = (r["reason"] or "").replace("|", "/").replace("\n", " ")
        if len(raw) > 220:
            raw = raw[:220] + "…"
        link = f"[#{r['pr']}]({r['url']})"
        report = f" [report](runs/{r['slug']}/REPORT.md)" if (HERE / "runs" / r["slug"] / "REPORT.md").exists() else ""
        tbl += f"| {i} | {r['repo']} | {link} | {VLABEL.get(r['verdict'], r['verdict'])}{report} | {why} | {raw} |\n"
    secs = [r for r in done if isinstance(r["seconds"], (int, float))]
    timing = ""
    if secs:
        ordered = sorted(secs, key=lambda r: r["seconds"])
        mid = ordered[len(ordered) // 2]
        timing = (f"\nMedian finished check: {mins(mid['seconds'])}. "
                  f"Fastest: {ordered[0]['repo']} #{ordered[0]['pr']} ({mins(ordered[0]['seconds'])}). "
                  f"Slowest: {ordered[-1]['repo']} #{ordered[-1]['pr']} ({mins(ordered[-1]['seconds'])}).\n")
    (HERE / "README.md").write_text(
        "# Contree checks of 30 open pull requests, stopped after 20\n\n"
        "Product checks in Contree (`--sandbox-backend contree --product-check --swarm`) on Proof-of-Change "
        "commit `863751e`. The batch was stopped on 24 Oct 2026. Twenty checks had finished. "
        "Ten had not, including pytoolz/toolz #210, which was in progress when the batch was stopped and has no record.\n\n"
        "Each finished run's `record.json` and `REPORT.md` are under `runs/`. Local machine paths are replaced with `<home>`. "
        "No verdict or reason field was edited.\n\n"
        "- [Scoring](SCORING.md)\n"
        "- `labels.json`: issues named by the pull request text. Every row is unlabelled.\n"
        "- `publish.py`: rebuilds this folder from `ops/runs/contree30`.\n"
        f"{timing}\n## Results\n\n" + tbl)


if __name__ == "__main__":
    raise SystemExit(main())
