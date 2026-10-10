"""Generate a Markdown approver report from an eval result JSON.

    python -m reports.generate eval-results.json -o reports/runs/<batch>.md
"""
from __future__ import annotations

import argparse
import datetime
import json
import sys
from pathlib import Path

IST = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
ICON = {"pass": "PASS", "fail": "FAIL", "warn": "WARN", "skip": "SKIP", "todo": "TODO"}



def _schema_mode(ev: dict) -> str:
    if ev.get("require_v1"):
        return "strict v1 (full shared schema harness/schema/observation.schema.json)"
    return "strict (machine_type required)" if ev.get("require_ci_fields") else "legacy (machine_type not required)"

def _machine(mt: dict | None, rec: dict) -> str:
    if not mt:
        return f"NOT RECORDED (legacy field machine={rec.get('machine')!r}, host={rec.get('host')!r}, cpus={rec.get('cpu_count')})"
    bits = [mt.get("label"), mt.get("arch"), mt.get("os"), mt.get("runner_name"), mt.get("image"),
            f"{mt.get('cpu_count')} cpus" if mt.get("cpu_count") else None]
    return ", ".join(str(b) for b in bits if b)


def record_section(entry: dict) -> str:
    rec, results = entry["record"], entry["results"]
    cls = rec.get("classification", {})
    right = [r for r in results if r["status"] == "pass"]
    wrong = [r for r in results if r["status"] in ("fail", "warn")]
    other = [r for r in results if r["status"] in ("skip", "todo")]
    L = [f"## {rec.get('id')}: {entry['recommendation']}", "",
         f"- **Pair:** {rec.get('upstream')} {rec.get('old_version')} -> {rec.get('new_version')} vs "
         f"{rec.get('dependent')} {rec.get('dependent_version')}",
         f"- **Run by:** {rec.get('who')} on {rec.get('date_ist')}; Python {rec.get('python')}",
         f"- **Machine type:** {_machine(rec.get('machine_type'), rec)}",
         f"- **Tests:** {rec.get('test_source')} [{rec.get('test_selection')}]",
         f"- **Prediction (written before the run):** {rec.get('expected')} -> matches: {rec.get('matches_expected')}",
         "", "| real_break | import_failure | already_broken | flaky | fixed_by_new | lost_tests |",
         "|---|---|---|---|---|---|",
         "| " + " | ".join(str(cls.get(k, "?")) for k in
                          ("real_break", "import_failure", "already_broken", "flaky", "fixed_by_new", "lost_tests")) + " |",
         ""]
    sigs = rec.get("top_error_signatures_breaks") or []
    if sigs:
        L += ["Top break signatures:", ""] + [f"- `{s}` x{n}" for s, n in sigs[:5]] + [""]
    L += ["### What went right", ""] + ([f"- {r['check']}: {r['detail']}" for r in right] or ["- nothing passed"]) + [""]
    L += ["### What went wrong", ""] + ([f"- **{ICON[r['status']]}** {r['check']}: {r['detail']}" for r in wrong] or ["- nothing"]) + [""]
    fixes = [r for r in wrong if r.get("fix")]
    L += ["### How to fix", ""] + ([f"- {r['check']}: {r['fix']}" for r in fixes] or ["- no action needed"]) + [""]
    if other:
        L += ["### Not checked / pending", ""] + [f"- {ICON[r['status']]} {r['check']}: {r['detail']}" for r in other] + [""]
    return "\n".join(L)


def render(ev: dict) -> str:
    now = datetime.datetime.now(IST).strftime("%Y-%m-%d %H:%M IST")
    c = ev.get("counts", {})
    L = ["# Blast Radius approver report", "",
         f"Generated {now} from `{ev.get('observations')}`. Evaluated on: {_machine(ev.get('evaluator_machine_type'), {})}.",
         f"Schema mode: {_schema_mode(ev)}.",
         "", f"## Recommendation: **{ev['recommendation']}**", "",
         "Check totals: " + ", ".join(f"{k} {v}" for k, v in sorted(c.items())), "",
         "| Run | Recommendation | Fail | Warn |", "|---|---|---|---|"]
    for e in ev["records"]:
        f = sum(r["status"] == "fail" for r in e["results"]); w = sum(r["status"] == "warn" for r in e["results"])
        L.append(f"| {e['id']} | {e['recommendation']} | {f} | {w} |")
    L += ["", "## Golden eval coverage", ""] + \
         [f"- {ICON[r['status']]} {r['check'].split(':', 1)[1]}: {r['detail']}" for r in ev.get("golden_coverage", [])] + [""]
    L += [record_section(e) for e in ev["records"]]
    L += ["---", "Rule: any FAIL means REJECT. WARN and TODO items are listed for the approver but do not block. "
          "Blast Radius never files or posts anything; a person decides what to send upstream.", ""]
    return "\n".join(L)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("eval_json")
    ap.add_argument("-o", "--out", default=None)
    a = ap.parse_args(argv)
    md = render(json.loads(Path(a.eval_json).read_text()))
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(md)
        print(a.out)
    else:
        sys.stdout.write(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
