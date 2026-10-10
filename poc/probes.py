"""Probes: small deterministic Python scripts run on BOTH sides of a PR, compared by plain code.

Interface (the same for the fixed probe library today and for model-written probes later)
----------------------------------------------------------------------------------------
A probe is one Python file. It must:

* define a literal dict ``PROBE`` (read with ``ast.literal_eval``; the file is never imported by the harness):

    PROBE = {
        "id": "short-name",                     # unique within the PR
        "target": "owner/repo#123",              # the PR it was written for
        "about": "one sentence: what it observes",
        "claims": [                              # the PR's claims this probe can check (may be empty)
            {"id": "C1", "source": "PR description", "text": "...",
             "covers": ["observation.name", "prefix.*"],   # fnmatch patterns over observation names
             "expect": "differs" | "same"},                # what the claim says about main vs PR
        ],
        "timeout_s": 120,                        # optional
    }

* when run as ``python <file>`` with the side's interpreter (cwd: an empty folder, thread counts pinned to 1,
  no credentials in the environment), print ONE JSON object as its last line:
  ``{"observations": {"<name>": <any JSON value>, ...}}``. It must be deterministic (fixed seeds, no clock, no
  network) and must not assert: it reports what it saw.

Fixed probes live in ``probes/<owner>/<repo>/<pr>.py`` (more probes for the same PR: ``<pr>-<name>.py``).
A model-written probe is the same kind of file, saved in the run folder and passed in with source "model".

Judging (``judge``): each observation is compared over 3 alternating runs per side with ``poc.diff.confirm``
(same / differs / flaky). Field-level differences come from ``poc.diff.compare``. Labels:

    same,    claim expects same     -> proven            differs, claim expects differs -> proven
    same,    no claim               -> no_difference     differs, claim expects same    -> false_claim
    same,    claim expects differs  -> needs_human       differs, no claim              -> unmentioned
    flaky                           -> flaky             probe crashed on both sides    -> not_testable

Any red or amber label (false_claim, unmentioned, needs_human, flaky) makes the PR verdict needs_attention.
"""
from __future__ import annotations

import ast
import fnmatch
import hashlib
import json
import subprocess
import time
from pathlib import Path

from poc.diff import compare, confirm, parse_probe_output
from poc.verdict import COLOUR, FindingLabel

PROBES_DIR = Path(__file__).resolve().parent.parent / "probes"
PROBE_ERROR = "probe.error"   # observation name used when a run printed no usable observations
ABSENT = "<absent>"
DEFAULT_TIMEOUT = 120


class ProbeError(ValueError):
    pass


def read_spec(path: Path) -> dict:
    """The PROBE dict of a probe file, validated. The file is parsed, never imported."""
    src = Path(path).read_text()
    spec = None
    for node in ast.parse(src).body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "PROBE" for t in node.targets):
            spec = ast.literal_eval(node.value)
    if not isinstance(spec, dict):
        raise ProbeError(f"{path}: no literal PROBE dict")
    for k in ("id", "target", "about"):
        if not isinstance(spec.get(k), str) or not spec[k]:
            raise ProbeError(f"{path}: PROBE[{k!r}] must be a non-empty string")
    claims = spec.setdefault("claims", [])
    for c in claims:
        if not {"id", "text", "covers", "expect"} <= set(c) or c["expect"] not in ("same", "differs"):
            raise ProbeError(f"{path}: claim {c.get('id')!r} needs id, text, covers and expect (same|differs)")
    spec.setdefault("timeout_s", DEFAULT_TIMEOUT)
    spec["sha256"] = hashlib.sha256(src.encode()).hexdigest()
    return spec


def find_probes(repo: str, pr: int, root: Path = PROBES_DIR) -> list[Path]:
    """Fixed probes for a PR: probes/<owner>/<repo>/<pr>.py and <pr>-*.py."""
    d = Path(root) / repo
    if not d.is_dir():
        return []
    return sorted([p for p in d.glob(f"{pr}.py")] + [p for p in d.glob(f"{pr}-*.py")])


def observations_of(stdout: str, exit_code) -> dict:
    """{name: value} from one probe run. A run without usable observations becomes one PROBE_ERROR observation."""
    obj = parse_probe_output(stdout, exit_code)
    obs = obj.get("observations") if isinstance(obj, dict) else None
    if not isinstance(obs, dict) or "crash" in obj or "timeout" in obj:
        return {PROBE_ERROR: {k: v for k, v in obj.items() if k != "observations"} or {"crash": "no observations"}}
    if exit_code not in (0, "0"):
        obs = dict(obs, **{PROBE_ERROR: {"exit_code": exit_code}})
    return obs


def output_lines(obs: dict) -> list[str]:
    """Canonical saved form, one observation per line, so each observation can be cited by file and line."""
    return [json.dumps({"observation": k, "value": obs[k]}, sort_keys=True) for k in sorted(obs)]


def write_output(path: Path, obs: dict) -> None:
    Path(path).write_text("\n".join(output_lines(obs)) + "\n")


def read_output(path: Path) -> dict:
    out = {}
    for ln in Path(path).read_text().splitlines():
        if ln.strip():
            d = json.loads(ln)
            out[d["observation"]] = d["value"]
    return out


def citation(fname: str, obs: dict, name: str) -> dict | None:
    """{file, line, quote} of an observation in a saved output file (see output_lines)."""
    for i, ln in enumerate(output_lines(obs), 1):
        if json.loads(ln)["observation"] == name:
            return {"file": fname, "line": i, "quote": json.dumps({"observation": name})[1:-1]}
    return None


def claim_for(spec: dict, name: str) -> dict | None:
    return next((c for c in spec.get("claims", []) if any(fnmatch.fnmatchcase(name, pat) for pat in c["covers"])), None)


def label_for(state: str, claim: dict | None, name: str, crashed_both: bool) -> str:
    if state == "flaky":
        return FindingLabel.FLAKY.value
    if name == PROBE_ERROR and crashed_both:
        return FindingLabel.NOT_TESTABLE.value
    if claim is None:
        return (FindingLabel.NO_DIFFERENCE if state == "same" else FindingLabel.UNMENTIONED_CHANGE).value
    if state == claim["expect"]:
        return FindingLabel.PROVEN.value
    return (FindingLabel.FALSE_CLAIM if claim["expect"] == "same" else FindingLabel.NEEDS_HUMAN).value


def judge(spec: dict, runs: dict, files: dict | None = None) -> list[dict]:
    """runs = {"main": [obs, obs, obs], "pr": [...]} -> one result per observation name (sorted).
    files = {"main": [file names], "pr": [...]} of the saved outputs, for citations."""
    names = sorted(set().union(*[set(o) for side in ("main", "pr") for o in runs[side]]))
    crashed_both = all(PROBE_ERROR in o for side in ("main", "pr") for o in runs[side])
    out = []
    for name in names:
        m = [{"v": o.get(name, ABSENT)} for o in runs["main"]]
        p = [{"v": o.get(name, ABSENT)} for o in runs["pr"]]
        state = confirm(m, p)
        claim = claim_for(spec, name)
        res = {"name": name, "state": state, "label": label_for(state, claim, name, crashed_both),
               "claim": claim["id"] if claim else None,
               "main": m[0]["v"], "pr": p[0]["v"]}
        if state != "same":
            res["diffs"] = [dict(d, field=d["field"].split(".", 1)[1] if "." in d["field"] else "")
                            for d in compare({"v": m[0]["v"]}, {"v": p[0]["v"]})]
        if files:
            res["citations"] = {side: citation(files[side][0], runs[side][0], name) for side in ("main", "pr")
                                if name in runs[side][0]}
        out.append(res)
    return out


def run_once(path: Path, python: Path, cwd: Path, env: dict, timeout: int) -> tuple[dict, str, float]:
    t0 = time.time()
    try:
        cp = subprocess.run([str(python), str(path)], cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout)
        out, code, log = cp.stdout, cp.returncode, cp.stdout[-4000:] + ("\n--- stderr ---\n" + cp.stderr[-4000:]
                                                                        if cp.stderr else "")
    except subprocess.TimeoutExpired:
        out, code, log = "", "timeout", f"timed out after {timeout}s"
    return observations_of(out, code), log, round(time.time() - t0, 1)


def run_probe(path: Path, pythons: dict, outdir: Path, cwd: Path, env: dict, runs: int = 3,
              source: str = "library") -> dict:
    """Run one probe file `runs` times per side, alternating main/PR; save outputs; judge. Returns the record entry."""
    spec = read_spec(path)
    cwd.mkdir(parents=True, exist_ok=True)
    got: dict = {"main": [], "pr": []}
    files: dict = {"main": [], "pr": []}
    per_run = []
    for i in range(1, runs + 1):
        for side in ("main", "pr"):
            obs, log, secs = run_once(path, pythons[side], cwd, env, int(spec["timeout_s"]))
            fname = f"probe-{spec['id']}-{side}-{i}.jsonl"
            write_output(outdir / fname, obs)
            (outdir / f"probe-{spec['id']}-{side}-{i}.log").write_text(log)
            got[side].append(obs)
            files[side].append(fname)
            per_run.append({"side": side, "run": i, "seconds": secs, "ok": PROBE_ERROR not in obs})
    return entry(spec, got, files, per_run, source, path)


def entry(spec: dict, got: dict, files: dict, per_run: list, source: str, path: Path | str | None) -> dict:
    results = judge(spec, got, files)
    return {"id": spec["id"], "source": source, "path": str(path) if path else None, "sha256": spec.get("sha256"),
            "target": spec["target"], "about": spec["about"], "claims": spec.get("claims", []),
            "runs_per_side": len(got["main"]), "per_run": per_run, "outputs": files, "runs": got,
            "observations": results}


def rejudge_entry(item: dict) -> dict:
    """Recompute an entry's observations from its recorded runs (no files, no environments needed)."""
    spec = {"id": item["id"], "target": item["target"], "about": item["about"], "claims": item.get("claims", [])}
    return dict(item, observations=judge(spec, item["runs"], item.get("outputs")))


def summarize(items: list[dict]) -> dict:
    """Findings over all probes of a PR: labels, red/amber observations, proven claims, reason text."""
    obs = [o | {"probe": it["id"]} for it in items for o in it["observations"]]
    labels = [FindingLabel(o["label"]) for o in obs]
    flagged = [o for o in obs if COLOUR.get(FindingLabel(o["label"])) in ("red", "amber")]
    proven = sorted({o["claim"] for o in obs if o["label"] == FindingLabel.PROVEN.value})
    bits = []
    if flagged:
        names = {FindingLabel.UNMENTIONED_CHANGE.value: "differs and no claim covers it",
                 FindingLabel.FALSE_CLAIM.value: "differs although the claim says it does not",
                 FindingLabel.NEEDS_HUMAN.value: "does not differ although the claim says it does",
                 FindingLabel.FLAKY.value: "gives different results between runs of the same side"}
        bits.append(f"probe: {len(flagged)} observation(s) need attention: "
                    + "; ".join(f"{o['name']} {names[o['label']]}" + (f" ({o['claim']})" if o.get("claim") else "")
                                for o in flagged[:4]))
    if proven:
        bits.append(f"probe: claim(s) {', '.join(proven)} proven")
    same = sum(1 for o in obs if o["label"] == FindingLabel.NO_DIFFERENCE.value)
    if same:
        bits.append(f"probe: {same} other observation(s) identical on both sides")
    errors = [o for o in obs if o["label"] == FindingLabel.NOT_TESTABLE.value]
    if errors:
        bits.append(f"probe: {len(errors)} probe(s) could not run on either side")
    return {"labels": [x.value for x in labels], "flagged": [{k: o[k] for k in ("probe", "name", "label", "claim")}
                                                             for o in flagged],
            "proven_claims": proven, "reason": "; ".join(bits)}
