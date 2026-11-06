"""Re-judge stored records with the parent code and with the candidate code.

Usage: python scripts/rejudge_preservation.py PARENT_REF AFTER_REF RECORD_DIR [RECORD_DIR ...]

AFTER_REF may be "-" to judge the current directory instead of a commit. Each ref is
exported with git archive into a temporary folder. The records are read as data.
Nothing in them is executed, nothing is written back, and no model is called.

Every record.json under the record directories is listed. A file that does not parse,
or that has no probe items, is counted and named. The candidate sha is printed. This
output is a re-judge of stored records. It is not a reissued verdict and it is not a
production tally. Unit fixtures are not in this tally.
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
from ops.daily_run import rejudge_probes, broad_gate_for
out = {}
for root in sys.argv[1:]:
    for p in sorted(glob.glob(os.path.join(root, "**", "record.json"), recursive=True)):
        key = p
        try:
            data = json.load(open(p))
        except Exception as e:
            out[key] = {"error": "parse:" + type(e).__name__}
            continue
        recs = data if isinstance(data, list) else [data]
        for i, rec in enumerate(recs):
            slot = f"{p}#{i}"
            if not isinstance(rec, dict):
                out[slot] = {"error": "not an object", "judged": False}
                continue
            pr = rec.get("pr")
            num = pr.get("number") if isinstance(pr, dict) else pr or rec.get("case")
            repo = rec.get("repo") or (pr.get("repo") if isinstance(pr, dict) else None)
            case = f"{repo} #{num}"
            url = None
            push = rec.get("pdf_push")
            if isinstance(push, dict) and isinstance(push.get("url"), str):
                url = push["url"]
            base = {"case": case, "stored": rec.get("verdict"), "url": url, "repo": repo, "number": num}
            items = rec.get("probes").get("items") if isinstance(rec.get("probes"), dict) else None
            if "verdict" not in rec or not items:
                out[slot] = dict(base, judged=False, note="no probe items" if "verdict" in rec else "no verdict")
                continue
            try:
                v = derive_verdict(rec, rec.get("baseline"))
                pp = rejudge_probes(rec.get("probes"), bool(rec.get("product_check")),
                                    broad_gate=broad_gate_for(rec))
                summary = (pp or {}).get("summary") or {}
                out[slot] = dict(base, judged=True, verdict=v,
                                 flagged=[f.get("name") for f in summary.get("flagged") or []],
                                 invalid=list(summary.get("advisory_invalid_preservation") or []),
                                 reason=summary.get("reason") or "")
            except Exception as e:
                out[slot] = dict(base, judged=False, error=type(e).__name__ + ": " + str(e)[:180])
json.dump(out, sys.stdout)
"""


def judge(ref: str, roots: list[str]) -> dict:
    if ref == "-":
        r = subprocess.run([sys.executable, "-c", JUDGE, *map(os.path.abspath, roots)],
                           cwd=os.getcwd(), capture_output=True, text=True)
        if r.returncode != 0:
            sys.stderr.write(r.stderr)
            raise SystemExit(r.returncode)
        return json.loads(r.stdout)
    with tempfile.TemporaryDirectory() as tree:
        arc = subprocess.run(["git", "archive", ref], capture_output=True, check=True).stdout
        subprocess.run(["tar", "-x", "-C", tree], input=arc, check=True)
        r = subprocess.run([sys.executable, "-c", JUDGE, *map(os.path.abspath, roots)], cwd=tree,
                           capture_output=True, text=True)
        if r.returncode != 0:
            sys.stderr.write(r.stderr)
            raise SystemExit(r.returncode)
        return json.loads(r.stdout)


def _sha(ref: str) -> str:
    if ref == "-":
        head = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True, check=True).stdout.strip()
        return head + (" (worktree differs from HEAD)" if dirty else "")
    return subprocess.run(["git", "rev-parse", ref], capture_output=True, text=True, check=True).stdout.strip()


def main(argv: list[str]) -> int:
    if len(argv) < 3:
        print(__doc__)
        return 2
    parent_ref, after_ref, roots = argv[0], argv[1], argv[2:]
    parent, after = judge(parent_ref, roots), judge(after_ref, roots)
    keys = sorted(set(parent) | set(after))
    print(f"re-judged_candidate_sha: {_sha(after_ref)}")
    print(f"parent_sha: {_sha(parent_ref)}")
    print("dataset: stored record.json files. Not a reissued verdict. Not a production tally.")
    print("synthetic_unit_fixtures: not included")
    print(f"files: {len(keys)} (parent {len(parent)}, candidate {len(after)})")
    changed = []
    unchanged = 0
    not_judged = []
    errors = []
    for k in keys:
        b, a = parent.get(k) or {}, after.get(k) or {}
        row = a or b
        if row.get("error") or b.get("error") or a.get("error"):
            errors.append((k, b.get("error") or b.get("verdict"), a.get("error") or a.get("verdict"), row))
            continue
        if not b.get("judged") or not a.get("judged"):
            not_judged.append((k, row))
            continue
        same = (b.get("verdict") == a.get("verdict") and b.get("flagged") == a.get("flagged")
                and (b.get("invalid") or []) == (a.get("invalid") or []))
        if same:
            unchanged += 1
        else:
            changed.append((k, b, a))
    print(f"judged: {unchanged + len(changed)}")
    print(f"unchanged: {unchanged}")
    print(f"changed: {len(changed)}")
    print(f"not_judged: {len(not_judged)}")
    print(f"errors: {len(errors)}")
    print("rows:")
    for k in keys:
        b, a = parent.get(k) or {}, after.get(k) or {}
        row = a or b
        print("\t".join([
            str(row.get("case") or ""),
            str(row.get("stored")),
            str(b.get("verdict") if b.get("judged") else b.get("note") or b.get("error")),
            str(a.get("verdict") if a.get("judged") else a.get("note") or a.get("error")),
            k,
            str(row.get("url") or ""),
        ]))
    print("changed_rows:")
    for k, b, a in changed:
        print(f"  {a.get('case')}: stored {a.get('stored')} parent {b.get('verdict')} candidate {a.get('verdict')}")
        print(f"    flagged {b.get('flagged')} -> {a.get('flagged')}")
        print(f"    invalid {b.get('invalid')} -> {a.get('invalid')}")
        print(f"    {k}")
        if a.get("url"):
            print(f"    {a.get('url')}")
    print("not_judged_rows:")
    for k, row in not_judged:
        print(f"  {row.get('case')}: {row.get('note') or row.get('error')}  {k}")
    print("error_rows:")
    for k, berr, aerr, row in errors:
        print(f"  {row.get('case')}: parent {berr} candidate {aerr}  {k}")
    watched = ("3163", "162", "5278", "732", "1515")
    print("named:")
    seen = {w: [] for w in watched}
    for k in keys:
        row = (after.get(k) or parent.get(k) or {})
        num = str(row.get("number"))
        if num in seen:
            b, a = parent.get(k) or {}, after.get(k) or {}
            seen[num].append((k, b, a, row))
    for w in watched:
        if not seen[w]:
            print(f"  #{w}: NOT IN DATASET")
            continue
        for k, b, a, row in seen[w]:
            print(f"  #{w} {row.get('case')}: stored {row.get('stored')} parent {b.get('verdict')} "
                  f"candidate {a.get('verdict')} judged {a.get('judged')} {k}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
