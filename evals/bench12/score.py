"""Score the benchmark: run every case (run_case.py, which never sees the key), then compare with answer_key.json.

This is the only module that reads the answer key. Usage: python -m evals.bench12.score
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from evals.bench12.run_case import run_case

HERE = Path(__file__).resolve().parent
KEY = HERE / "answer_key.json"


def score(key_path: Path = KEY) -> list[dict]:
    key = json.loads(key_path.read_text())
    rows = []
    for e in key["answers"]:
        got = run_case(HERE / "cases" / e["case"], e["baseline"], e["route"])
        ok = got["verdict"] == e["expected"] and got["golden_verdict"] in (None, e["expected"])
        rows.append({**e, "actual": got["verdict"], "golden": got["golden_verdict"], "ok": ok,
                     "reason": got["reason"]})
    return rows


def main() -> int:
    rows = score()
    for r in rows:
        print(f"{'PASS' if r['ok'] else 'FAIL'} {r['case']:5s} {r['baseline']:5s} {r['route']:6s} "
              f"expected={r['expected']:16s} actual={r['actual']:16s} golden={r['golden']}")
    bad = [r for r in rows if not r["ok"]]
    print(f"{len(rows) - len(bad)}/{len(rows)} match the answer key")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
