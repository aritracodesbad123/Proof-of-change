"""Replay saved run records against two versions of the probe-output parser.

Usage: python scripts/rejudge_probe_output.py BEFORE_REF AFTER_REF RUNS_REF

BEFORE_REF and AFTER_REF are code commits (`-` means the working tree). RUNS_REF is the
branch that holds record.json files (for example origin/runs). Records are read with
git and copied to a temporary folder. Nothing in them is executed, nothing is written
back, and no model is called.

The before side judges each record as it was stored. The after side, where a run kept
the rejected JSON object (stored under probe.error) or a raw stdout string, parses that
text again with the current observations parser and then judges. A retry is only counted:
it would call the model, so it is not run.
"""
import copy
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

BEFORE = r"""
import glob, json, os, sys
sys.path.insert(0, os.getcwd())
from evals.checks import derive_verdict
out = {}
for root in sys.argv[1:]:
    for p in sorted(glob.glob(os.path.join(root, "**", "record.json"), recursive=True)):
        try:
            data = json.load(open(p))
        except Exception as e:
            out[p] = {"error": type(e).__name__}
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
            base = {"case": f"{repo} #{num}", "repo": repo, "number": num, "stored": rec.get("verdict")}
            items = rec.get("probes").get("items") if isinstance(rec.get("probes"), dict) else None
            if "verdict" not in rec or not items:
                out[slot] = dict(base, judged=False)
                continue
            try:
                out[slot] = dict(base, judged=True, verdict=derive_verdict(rec, rec.get("baseline")))
            except Exception as e:
                out[slot] = dict(base, judged=False, error=type(e).__name__ + ": " + str(e)[:200])
json.dump(out, sys.stdout)
"""


def materialize(ref: str, dest: Path) -> int:
    names = subprocess.check_output(["git", "ls-tree", "-r", "--name-only", ref], text=True).splitlines()
    n = 0
    for name in names:
        if not name.endswith("record.json"):
            continue
        data = subprocess.check_output(["git", "show", f"{ref}:{name}"])
        path = dest / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        n += 1
    return n


def _covers(item: dict) -> list:
    out = []
    for c in item.get("claims") or []:
        if isinstance(c, dict):
            for pat in c.get("covers") or []:
                if isinstance(pat, str) and pat not in out:
                    out.append(pat)
    return out


def _parse_error(obs) -> bool:
    if not isinstance(obs, dict) or set(obs) != {"probe.error"}:
        return False
    err = obs.get("probe.error")
    if not isinstance(err, dict) or err.get("timeout"):
        return False
    if err.get("crash") in ("non-json output", "ambiguous output", "no observations"):
        return True
    if "contract" in err:
        return True
    return "crash" not in err and "contract" not in err


def _stdout_text(run) -> str | None:
    if not isinstance(run, dict):
        return None
    for key in ("stdout", "raw_stdout", "probe_stdout"):
        if isinstance(run.get(key), str) and run[key].strip():
            return run[key]
    return None


def _reparse(obs, covers):
    """(observations, recovered, from_stdout). Recovered is false when the new parser still has no observations."""
    from poc import probes
    if not hasattr(probes, "flat_observations"):
        return obs, False, False
    text = _stdout_text(obs)
    from_stdout = text is not None
    if text is None and isinstance(obs, dict) and set(obs) == {probes.PROBE_ERROR}:
        err = obs.get(probes.PROBE_ERROR)
        if isinstance(err, dict) and not err.get("timeout") and "contract" not in err and err.get("crash") not in (
                "non-json output", "ambiguous output", "no observations"):
            body = {k: v for k, v in err.items() if k != "exit_code"}
            if body and "crash" not in body:
                text = json.dumps(body)
    if text is None:
        return obs, False, False
    code = 0
    if isinstance(obs, dict) and isinstance(obs.get(probes.PROBE_ERROR), dict):
        code = obs[probes.PROBE_ERROR].get("exit_code", 0)
    parsed = probes.observations_of(text, code, True, covers)
    real = {k: v for k, v in parsed.items() if k != probes.PROBE_ERROR} if isinstance(parsed, dict) else {}
    if not real:
        return obs, False, from_stdout
    return parsed, True, from_stdout


def _would_retry(item: dict) -> bool:
    from poc import probes
    if item.get("source") != "model" or not hasattr(probes, "output_parse_failure"):
        return False
    runs = item.get("runs") or {}
    for side in ("main", "pr"):
        rs = runs.get(side) or []
        if not rs or any(not probes.output_parse_failure(obs) for obs in rs):
            return False
    return True


def _reason(rec: dict) -> tuple[str, str]:
    """(verdict, reason) through the same gates as derive_verdict. The verdict is checked against that function."""
    import copy as _copy

    from evals.checks import derive_verdict
    from ops.daily_run import (
        advisory_gate,
        ai_probe_gate,
        apply_execution_evidence_filters,
        broad_gate_for,
        broken_probe_gate,
        cap_for_uncollected_file,
        lower_verdict,
        no_evidence_gate,
        rejudge_probes,
        uses,
        verdict_for,
        without_rewrite,
    )
    from poc import coverage_gate

    def once(record):
        pp = rejudge_probes(record.get("probes"), bool(record.get("product_check")),
                            broad_gate=broad_gate_for(record))
        cmp = record.get("comparison")
        if isinstance(cmp, dict):
            cmp = _copy.deepcopy(cmp)
            apply_execution_evidence_filters(cmp)
        cnv = None if cmp else (record.get("reason") or "no comparison")
        v = verdict_for(cmp, cnv, record.get("exit_check"), record.get("files"), pp, record.get("behaviour_claims"),
                        record.get("baseline"), docstring_only=bool(record.get("docstring_only")),
                        coverage=record.get("coverage"))
        v = cap_for_uncollected_file(cmp if isinstance(cmp, dict) else None, v[0], v[1])
        base = {k: x for k, x in record.items() if not str(k).endswith((
            "_before_coverage_gate", "_before_ai_probe_gate", "_before_broken_probe_gate",
            "_before_no_evidence_gate", "_before_advisory_gate"))}
        payload = base | {"probes": pp, "verdict": v[0], "reason": v[1]}
        if not uses(record.get("baseline"), "coverage"):
            out = advisory_gate(no_evidence_gate(broken_probe_gate(payload)))
        else:
            gated = coverage_gate.apply(payload | {"baseline": record.get("baseline")})
            out = advisory_gate(no_evidence_gate(broken_probe_gate(ai_probe_gate(gated))))
        alt = without_rewrite(record)
        if alt is not None:
            other = derive_verdict(alt, record.get("baseline"))
            final = lower_verdict(out["verdict"], other)
            reason = out.get("reason") or ""
            if final != out["verdict"]:
                reason = (reason + "; a probe rewrite cannot raise the verdict").strip("; ")
            return final, reason
        return out["verdict"], out.get("reason") or ""

    verdict, reason = once(rec)
    official = derive_verdict(rec, rec.get("baseline"))
    if verdict != official:
        return official, reason + f" (gate verdict {verdict} differed from derive_verdict)"
    return verdict, reason


def judge_after(root: Path) -> dict:
    out = {}
    for path in sorted(root.rglob("record.json")):
        slot = f"{path}#0"
        try:
            data = json.loads(path.read_text())
        except Exception as e:
            out[str(path)] = {"error": type(e).__name__}
            continue
        recs = data if isinstance(data, list) else [data]
        for i, rec in enumerate(recs):
            slot = f"{path}#{i}"
            if not isinstance(rec, dict):
                out[slot] = {"error": "not an object", "judged": False}
                continue
            pr = rec.get("pr")
            num = pr.get("number") if isinstance(pr, dict) else pr or rec.get("case")
            repo = rec.get("repo") or (pr.get("repo") if isinstance(pr, dict) else None)
            base = {"case": f"{repo} #{num}", "repo": repo, "number": num, "stored": rec.get("verdict"),
                    "path": str(path.relative_to(root))}
            items = rec.get("probes").get("items") if isinstance(rec.get("probes"), dict) else None
            parse_runs = recovered = stdout_runs = stdout_recovered = 0
            retry = False
            had_parse = False
            if items:
                rec = copy.deepcopy(rec)
                for it in rec["probes"]["items"]:
                    if not isinstance(it, dict):
                        continue
                    covers = _covers(it)
                    runs = it.get("runs") or {}
                    for side, rs in list(runs.items()):
                        if not isinstance(rs, list):
                            continue
                        new_rs = []
                        for obs in rs:
                            if _parse_error(obs):
                                parse_runs += 1
                                had_parse = True
                            parsed, ok, from_stdout = _reparse(obs, covers)
                            if from_stdout:
                                stdout_runs += 1
                            if ok:
                                recovered += 1
                                if from_stdout:
                                    stdout_recovered += 1
                            new_rs.append(parsed)
                        runs[side] = new_rs
                    if _would_retry(it):
                        retry = True
            base.update(parse_error=had_parse, parse_runs=parse_runs, recovered_runs=recovered,
                        stdout_runs=stdout_runs, stdout_recovered=stdout_recovered, would_retry=retry)
            if "verdict" not in rec or not items:
                out[slot] = dict(base, judged=False)
                continue
            try:
                verdict, reason = _reason(rec)
                out[slot] = dict(base, judged=True, verdict=verdict, reason=reason)
            except Exception as e:
                out[slot] = dict(base, judged=False, error=type(e).__name__ + ": " + str(e)[:240])
    return out


def judge_before(ref: str, root: Path) -> dict:
    if ref == "-":
        r = subprocess.run([sys.executable, "-c", BEFORE, str(root)], cwd=os.getcwd(),
                           capture_output=True, text=True)
    else:
        with tempfile.TemporaryDirectory() as tree:
            arc = subprocess.run(["git", "archive", ref], capture_output=True, check=True).stdout
            subprocess.run(["tar", "-x", "-C", tree], input=arc, check=True)
            r = subprocess.run([sys.executable, "-c", BEFORE, str(root)], cwd=tree,
                               capture_output=True, text=True)
    if r.returncode != 0:
        sys.stderr.write(r.stderr)
        raise SystemExit(r.returncode)
    return json.loads(r.stdout)


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(__doc__)
        return 2
    before_ref, after_ref, runs_ref = argv
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "runs"
        n = materialize(runs_ref, root)
        print(f"records read from {runs_ref}: {n}")
        if after_ref != "-":
            print("after ref must be '-' so the re-parse uses this working tree", file=sys.stderr)
            return 2
        before, after = judge_before(before_ref, root), judge_after(root)
    keys = sorted(set(before) | set(after))
    judged = unchanged = changed = errors = skipped = 0
    changes = []
    parse_records = recovered_records = retry_records = stdout_records = stdout_recovered_records = 0
    held = []
    for k in keys:
        b, a = before.get(k) or {}, after.get(k) or {}
        if a.get("parse_error"):
            parse_records += 1
        if a.get("recovered_runs"):
            recovered_records += 1
        if a.get("would_retry"):
            retry_records += 1
        if a.get("stdout_runs"):
            stdout_records += 1
        if a.get("stdout_recovered"):
            stdout_recovered_records += 1
        case = a.get("case") or b.get("case")
        num = a.get("number") if a.get("number") is not None else b.get("number")
        repo = a.get("repo") or b.get("repo")
        if repo == "mahmoud/boltons" and num in (751, 752, 758, 803):
            held.append((case, b.get("verdict") or b.get("stored"), a.get("verdict") or a.get("stored"),
                         a.get("judged"), b.get("error"), a.get("error")))
        if b.get("error") or a.get("error"):
            errors += 1
            changes.append(f"  ERROR {case}: {b.get('error') or ''} {a.get('error') or ''}")
            continue
        if not b.get("judged") or not a.get("judged"):
            skipped += 1
            continue
        judged += 1
        if b.get("verdict") == a.get("verdict"):
            unchanged += 1
            continue
        changed += 1
        why = (a.get("reason") or "").replace("\n", " ")
        if len(why) > 400:
            why = why[:400] + "..."
        flag = "re-parsed" if a.get("recovered_runs") else "no re-parse"
        changes.append(f"  {case}: {b.get('verdict')} -> {a.get('verdict')} ({flag}) {why}")
    print(f"judged: {judged}")
    print(f"unchanged: {unchanged}")
    print(f"changed: {changed}")
    print(f"errors: {errors}")
    print(f"not judged: {skipped}")
    print(f"records with a probe-output parse error: {parse_records}")
    print(f"of those, recovered by the new parser: {recovered_records}")
    print(f"records that kept raw probe stdout: {stdout_records}")
    print(f"of those, re-parsed into observations: {stdout_recovered_records}")
    print(f"records that would trigger the one output retry: {retry_records}")
    print("changes:")
    print("\n".join(changes) if changes else "  (none)")
    print("held-out mahmoud/boltons:")
    for row in held:
        print(" ", row)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
