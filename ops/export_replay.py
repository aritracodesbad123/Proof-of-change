"""Copy finished checks into the replay folder the results page serves.

The page is a static build. It reads only the files this script writes. It does not
install a library and it does not call an API.

    python ops/export_replay.py
    python ops/export_replay.py --out replay --runs ops/runs --reports reports/daily

Curated examples already in the repo are included by default (real pull-request records
and the release-comparison reports). Extra finished runs are picked up from ``--runs``
and ``--reports`` when those folders exist. A run is included when it has a verdict, or
when a sibling report already states one. This script does not compute a verdict.

The output is safe to commit. Values that look like keys are removed.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VERDICT_HEADING = re.compile(r"\b(COULD NOT VERIFY|NEEDS ATTENTION|VERIFIED|NO CODE CHANGE)\b")
VERDICT_MAP = {
    "VERIFIED": "verified",
    "NEEDS ATTENTION": "needs_attention",
    "COULD NOT VERIFY": "could_not_verify",
    "NO CODE CHANGE": "no_code_change",
}
OBSERVED = re.compile(r"\*\*What we observed:\*\*\s*(.+)")
ASSIGNED = re.compile(
    r"(?i)\b(NEBIUS_API_KEY|GITHUB_TOKEN|GH_TOKEN|AUTHORIZATION)\b(\s*[:=]\s*|\s+)\S+"
)
BEARER = re.compile(r"(?i)\bBearer\s+\S+")
TOKEN_SHAPE = re.compile(r"\b(?:sk-|ghp_|github_pat_|xox[baprs]-)[A-Za-z0-9_\-]{8,}\b")

CURATED = (
    {"kind": "jsonl", "path": "evals/fixtures/golden_pr_v1.jsonl"},
    {"kind": "json", "path": "tests/fixtures/day1/pr_run_pandas_70520.json"},
    {"kind": "json", "path": "tests/fixtures/day1/numpy-32910-attempt4-record.json"},
    {
        "kind": "golden",
        "id": "golden-sklearn160rc1-imblearn0124",
        "report": "reports/samples/golden-v1/golden-sklearn160rc1-imblearn0124",
    },
    {
        "kind": "golden",
        "id": "golden-pandas300rc0-upsetplot090",
        "report": "reports/samples/golden-v1/golden-pandas300rc0-upsetplot090",
    },
    {
        "kind": "golden",
        "id": "golden-clean-sklearn151to152-imblearn0124",
        "report": "reports/samples/golden-v1/golden-clean-sklearn151to152-imblearn0124",
    },
)


def scrub_text(text: str) -> str:
    out = BEARER.sub("Bearer [redacted]", text)
    out = ASSIGNED.sub(lambda m: f"{m.group(1)}{m.group(2)}[redacted]", out)
    return TOKEN_SHAPE.sub("[redacted]", out)


def scrub_obj(value):
    if isinstance(value, str):
        return scrub_text(value)
    if isinstance(value, list):
        return [scrub_obj(item) for item in value]
    if isinstance(value, dict):
        return {str(key): scrub_obj(item) for key, item in value.items()}
    return value


def _load_json(path: Path):
    return json.loads(path.read_text())


def _load_jsonl(path: Path) -> list[dict]:
    rows = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def verdict_from_report(markdown: str) -> str | None:
    """The verdict word already printed at the top of a report. Not a new verdict."""
    head = "\n".join(markdown.splitlines()[:40])
    match = VERDICT_HEADING.search(head)
    if not match:
        return None
    return VERDICT_MAP[match.group(1)]


def observed_sentence(markdown: str) -> str | None:
    match = OBSERVED.search(markdown)
    if not match:
        return None
    return match.group(1).strip()


def _pr_number(record: dict) -> int | None:
    pr = record.get("pr")
    if isinstance(pr, int):
        return pr
    if isinstance(pr, dict) and isinstance(pr.get("number"), int):
        return pr["number"]
    return None


def _pr_url(record: dict) -> str | None:
    pr = record.get("pr")
    if isinstance(pr, dict) and isinstance(pr.get("url"), str):
        return pr["url"]
    url = record.get("url")
    return url if isinstance(url, str) else None


def _title(record: dict) -> str:
    pr = record.get("pr")
    if isinstance(pr, dict) and pr.get("title"):
        return str(pr["title"])
    if record.get("title"):
        return str(record["title"])
    old, new = record.get("old_version"), record.get("new_version")
    if old and new:
        dep = record.get("dependent") or ""
        dep_v = record.get("dependent_version") or ""
        tail = f" against {dep} {dep_v}".rstrip()
        return f"{record.get('upstream') or record.get('repo') or 'library'} {old} to {new}{tail}"
    return str(record.get("id") or "finished check")


def console_record(record: dict, *, verdict: str | None = None, reason: str | None = None) -> dict:
    """Shape a copy so the console can show it. The verdict is the one already on the record or the report."""
    out = dict(record)
    if isinstance(out.get("pr"), int):
        out["pr"] = {
            "number": out["pr"],
            "url": out.get("url"),
            "title": out.get("title"),
            "repo": out.get("repo"),
        }
    if verdict and not out.get("verdict"):
        out["verdict"] = verdict
    if reason and not out.get("reason"):
        out["reason"] = reason
    if not out.get("repo"):
        upstream = out.get("upstream")
        if upstream:
            out["repo"] = str(upstream)
    if not out.get("id"):
        number = _pr_number(out)
        repo = str(out.get("repo") or "check").replace("/", "-")
        out["id"] = f"{repo}-{number}" if number is not None else repo
    return scrub_obj(out)


def catalog_row(record: dict, *, record_rel: str, report_html: str | None, kind: str) -> dict:
    return {
        "id": str(record.get("id")),
        "kind": kind,
        "repo": record.get("repo"),
        "pr": _pr_number(record),
        "url": _pr_url(record),
        "title": _title(record),
        "verdict": record.get("verdict"),
        "reason": (str(record.get("reason") or ""))[:500],
        "tested_at_ist": record.get("tested_at_ist") or record.get("date_ist"),
        "record": record_rel,
        "report_html": report_html,
    }


def _write_check(out: Path, record: dict, reports: list[Path]) -> dict:
    rid = str(record["id"])
    folder = out / "checks" / rid
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "record.json").write_text(json.dumps(record, indent=2) + "\n")
    report_rel = None
    for src in reports:
        if src.is_file() and src.stat().st_size > 0 and src.suffix in {".html", ".md"}:
            text = scrub_text(src.read_text(errors="replace"))
            (folder / src.name).write_text(text)
            if src.suffix == ".html":
                report_rel = f"checks/{rid}/{src.name}"
    kind = "pull_request" if _pr_url(record) else "release"
    return catalog_row(record, record_rel=f"checks/{rid}/record.json", report_html=report_rel, kind=kind)


def _golden_record(root: Path, item: dict) -> tuple[dict, list[Path]]:
    report_dir = root / item["report"]
    markdown = (report_dir / "REPORT.md").read_text(errors="replace")
    verdict = verdict_from_report(markdown)
    reason = observed_sentence(markdown)
    found = None
    jsonl = root / "evals" / "fixtures" / "golden_v1.jsonl"
    for row in _load_jsonl(jsonl):
        if row.get("id") == item["id"]:
            found = row
            break
    if found is None:
        raise SystemExit(f"no observation for {item['id']}")
    record = console_record(found, verdict=verdict, reason=reason)
    reports = [report_dir / "REPORT.html", report_dir / "REPORT.md"]
    return record, reports


def collect(root: Path, runs: Path | None, reports: Path | None, curated: bool = True) -> list[tuple[dict, list[Path]]]:
    """Curated repo examples, then any finished records under the run folders."""
    items: list[tuple[dict, list[Path]]] = []
    seen: set[str] = set()

    def add(record: dict, report_files: list[Path]) -> None:
        rid = str(record.get("id") or "")
        if not rid or rid in seen:
            return
        if not record.get("verdict"):
            return
        seen.add(rid)
        items.append((record, report_files))

    for item in (CURATED if curated else ()):
        kind = item["kind"]
        if kind == "json":
            path = root / item["path"]
            if path.is_file():
                add(console_record(_load_json(path)), [])
        elif kind == "jsonl":
            path = root / item["path"]
            if path.is_file():
                for row in _load_jsonl(path):
                    add(console_record(row), [])
        elif kind == "golden":
            report_dir = root / item["report"]
            if report_dir.is_dir() and (root / "evals" / "fixtures" / "golden_v1.jsonl").is_file():
                record, files = _golden_record(root, item)
                add(record, files)

    for folder in (runs, reports):
        if folder is None or not folder.is_dir():
            continue
        for path in sorted(folder.rglob("record.json")):
            try:
                raw = _load_json(path)
            except (OSError, json.JSONDecodeError):
                continue
            if not isinstance(raw, dict):
                continue
            sibling_md = path.parent / "REPORT.md"
            verdict = None
            reason = None
            if sibling_md.is_file():
                text = sibling_md.read_text(errors="replace")
                verdict = verdict_from_report(text)
                reason = observed_sentence(text)
            record = console_record(raw, verdict=verdict, reason=reason)
            files = [path.parent / "REPORT.html", path.parent / "REPORT.md"]
            add(record, files)
    return items


def export(root: Path, out: Path, runs: Path | None = None, reports: Path | None = None, curated: bool = True) -> dict:
    """Write ``out/catalog.json`` and one folder per check. Local files only."""
    checks = [_write_check(out, record, files) for record, files in collect(root, runs, reports, curated)]
    catalog = {
        "mode": "replay",
        "note": (
            "30-PR random batch on code version 0fa0016. Older runs are kept in benchmarks/replay-archive/. "
            "The results page does not install code and does not call an API."
        ),
        "checks": checks,
    }
    out.mkdir(parents=True, exist_ok=True)
    (out / "catalog.json").write_text(json.dumps(catalog, indent=2) + "\n")
    return catalog


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Export finished checks for the static results page.")
    ap.add_argument("--root", default=str(ROOT), help="repository root")
    ap.add_argument("--out", default=str(ROOT / "replay"), help="folder to write (default: replay/)")
    ap.add_argument("--runs", default=str(ROOT / "ops" / "runs"), help="finished run folders (record.json)")
    ap.add_argument("--reports", default=str(ROOT / "reports" / "daily"), help="daily report folders")
    ap.add_argument("--no-curated", action="store_true", help="leave out the curated older examples (the page then shows only --runs)")
    args = ap.parse_args(argv)
    catalog = export(Path(args.root), Path(args.out), Path(args.runs), Path(args.reports), not args.no_curated)
    print(f"exported {len(catalog['checks'])} checks to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
