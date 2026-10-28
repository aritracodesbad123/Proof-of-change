"""Re-judge stored run records with two versions of the code and print every verdict that changes.

Usage: python scripts/rejudge_records.py BEFORE_REF AFTER_REF RECORD_DIR [RECORD_DIR ...]

Each ref is exported with `git archive` to a temporary folder. Every stored run record (a record.json with a
recorded verdict and probe items) under the record folders is re-judged offline with each version's
`evals.checks.derive_verdict`. Nothing runs tests or calls the network.
"""
import json
import os
import subprocess
import sys
import tempfile

JUDGE = r"""
import glob, json, os, sys
sys.path.insert(0, os.getcwd())
from evals.checks import derive_verdict
out = {}
for root in sys.argv[1:]:
    for p in sorted(glob.glob(os.path.join(root, "**", "record.json"), recursive=True)):
        try:
            data = json.load(open(p))
        except Exception:
            continue
        for i, rec in enumerate(data if isinstance(data, list) else [data]):
            if not (isinstance(rec, dict) and "verdict" in rec and isinstance(rec.get("probes"), dict)
                    and rec["probes"].get("items")):
                continue
            try:
                v = derive_verdict(rec, rec.get("baseline"))
            except Exception as e:
                v = "ERROR:" + type(e).__name__
            pr = rec.get("pr")
            num = pr.get("number") if isinstance(pr, dict) else pr or rec.get("case")
            repo = rec.get("repo") or (pr.get("repo") if isinstance(pr, dict) else None)
            out[f"{p}#{i}"] = {"case": f"{repo} #{num}", "verdict": v}
json.dump(out, sys.stdout)
"""


def judge(ref: str, roots: list[str]) -> dict:
    with tempfile.TemporaryDirectory() as tree:
        arc = subprocess.run(["git", "archive", ref], capture_output=True, check=True).stdout
        subprocess.run(["tar", "-x", "-C", tree], input=arc, check=True)
        r = subprocess.run([sys.executable, "-c", JUDGE, *map(os.path.abspath, roots)], cwd=tree,
                           capture_output=True, text=True, check=True)
        return json.loads(r.stdout)


def main(argv: list[str]) -> int:
    if len(argv) < 3:
        print(__doc__)
        return 2
    before_ref, after_ref, roots = argv[0], argv[1], argv[2:]
    before, after = judge(before_ref, roots), judge(after_ref, roots)
    keys = sorted(set(before) | set(after))
    changed = [k for k in keys if before.get(k, {}).get("verdict") != after.get(k, {}).get("verdict")]
    print(f"records: {len(keys)} (before {len(before)}, after {len(after)})")
    print(f"unchanged: {len(keys) - len(changed)}")
    print(f"changed: {len(changed)}")
    for k in changed:
        case = (after.get(k) or before.get(k))["case"]
        print(f"  {case}: {before.get(k, {}).get('verdict')} -> {after.get(k, {}).get('verdict')}  [{k}]")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
