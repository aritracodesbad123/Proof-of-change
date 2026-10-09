"""Eval checks. Each check returns a Result(check, status, detail, fix).

status is one of: pass, fail, warn, skip, todo.
  fail -> the run must be rejected
  warn -> approver should look, but the run is not rejected for it
  todo -> the check is not active yet (missing data from Jonathan)
"""
from __future__ import annotations

import json
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path

from guardrails.schema import CLASS_KEYS, REQUIRED_RUNS_PER_SIDE, SINGLE_THREAD_VARS, validate_record

GOLDEN_PATH = Path(__file__).with_name("golden_cases.json")


@dataclass
class Result:
    check: str
    status: str
    detail: str
    fix: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def _norm(name: str) -> str:
    return name.lower().replace("_", "-")


def check_schema(rec: dict, require_ci_fields: bool = True) -> Result:
    errs = validate_record(rec, require_ci_fields=require_ci_fields)
    if not errs:
        return Result("schema", "pass", "record matches the schema" + (" (incl. machine_type)" if require_ci_fields else ""))
    return Result("schema", "fail", "; ".join(errs[:6]) + (f" (+{len(errs) - 6} more)" if len(errs) > 6 else ""),
                  "Run through `python -m harness.run` so machine_type/thread_env are added, or fix the runner output.")


def check_versions(rec: dict, run_dir: Path | None = None) -> Result:
    up = _norm(rec.get("upstream", ""))
    old, new, req = rec.get("old_version"), rec.get("new_version"), rec.get("new_version_requested")
    problems = []
    if req not in (None, "nightly") and new != req:
        problems.append(f"installed new version {new} != requested {req}")
    want = {f"{up}=={old}", f"{up}=={new}"}
    got = {_norm(x.split("==")[0]) + "==" + x.split("==")[-1] for x in rec.get("env_diff", [])}
    if got != want:
        problems.append(f"env_diff {sorted(got)} should be exactly {sorted(want)} (only the upstream may differ)")
    if run_dir is not None:
        for side, ver in (("old", old), ("new", new)):
            f = run_dir / f"freeze-{side}.txt"
            if f.exists():
                lines = {_norm(line.split("==")[0]) + "==" + line.split("==")[-1]
                         for line in f.read_text().splitlines() if "==" in line}
                if f"{up}=={ver}" not in lines:
                    problems.append(f"{f.name} does not contain {up}=={ver}")
    if problems:
        return Result("versions_installed", "fail", "; ".join(problems),
                      "Check the runner's install step and setup.log; rerun with the exact pinned versions.")
    status, extra = "pass", ""
    if rec.get("pip_check_new") not in ("ok", None):
        status, extra = "warn", f"; pip check on new env reported: {rec['pip_check_new'][:160]}"
    return Result("versions_installed", status, f"{up} {old} -> {new}; env differs only in {up}{extra}",
                  "Review the dependency conflict; it may explain some failures." if status == "warn" else "")


def check_runs_per_side(rec: dict) -> Result:
    per = rec.get("per_run", [])
    sides = [r.get("side") for r in per]
    c = Counter(sides)
    problems = []
    if rec.get("runs_per_side") != REQUIRED_RUNS_PER_SIDE:
        problems.append(f"runs_per_side={rec.get('runs_per_side')} (required {REQUIRED_RUNS_PER_SIDE})")
    if c["old"] != REQUIRED_RUNS_PER_SIDE or c["new"] != REQUIRED_RUNS_PER_SIDE:
        problems.append(f"per_run has old={c['old']} new={c['new']} (required 3 each)")
    expected_order = ["old", "new"] * REQUIRED_RUNS_PER_SIDE
    if sides != expected_order:
        problems.append(f"runs not alternating old/new: {sides}")
    timeouts = [f"{r.get('side')}#{r.get('run')}" for r in per if r.get("exit") == "timeout"]
    if timeouts:
        problems.append(f"timed out: {timeouts}")
    if problems:
        return Result("runs_per_side", "fail", "; ".join(problems),
                      "Rerun with --runs 3 (the harness enforces it); for timeouts, subset the suite or raise "
                      "--run-timeout and record why in subset_note.")
    # consistency within a side is informative (flaky tests), not a failure
    unstable = []
    for side in ("old", "new"):
        sig = {(r["passed"], r["failed"], r["error"]) for r in per if r["side"] == side}
        if len(sig) > 1:
            unstable.append(side)
    if unstable:
        return Result("runs_per_side", "warn", f"3 alternating runs per side, but counts vary within: {unstable}",
                      "Inspect class-flaky.txt; flaky tests are excluded from real breaks.")
    return Result("runs_per_side", "pass", "3 alternating runs per side, identical counts within each side")


def check_single_thread(rec: dict) -> Result:
    te = rec.get("thread_env")
    if te is None:
        return Result("single_thread", "warn",
                      "thread_env not recorded (br_run.py sets OMP/OPENBLAS/MKL=1 internally but does not record it)",
                      "Run through `python -m harness.run`, which records thread_env.")
    bad = [k for k in SINGLE_THREAD_VARS if str(te.get(k)) != "1"]
    if bad:
        return Result("single_thread", "fail", f"not single-threaded: {bad}",
                      "Rerun with OMP_NUM_THREADS=OPENBLAS_NUM_THREADS=MKL_NUM_THREADS=1.")
    return Result("single_thread", "pass", "OMP/OPENBLAS/MKL_NUM_THREADS=1")


def check_expected(rec: dict) -> Result:
    m = rec.get("matches_expected")
    if m == "yes":
        return Result("matches_expected", "pass", f"outcome matches the prediction written before the run ({rec.get('expected_class')})")
    if m == "n/a":
        return Result("matches_expected", "skip", "expected_class=unknown")
    return Result("matches_expected", "warn", f"outcome does not match the prediction: {rec.get('expected')!r}",
                  "Not a harness failure: either a new finding or a wrong prediction. Hand-check the top signatures.")


def load_golden(path: Path = GOLDEN_PATH) -> list[dict]:
    return json.loads(Path(path).read_text())["cases"]


def golden_for(rec: dict, cases: list[dict]) -> dict | None:
    for c in cases:
        m = c["match"]
        if (_norm(rec.get("upstream", "")) == _norm(m["upstream"]) and rec.get("new_version") == m["new_version"]
                and _norm(rec.get("dependent", "")) == _norm(m["dependent"])):
            return c
    return None


def check_golden_case(rec: dict, case: dict) -> Result:
    cls, exp = rec.get("classification", {}), case["expect"]
    problems = []
    for k, v in exp.get("exact", {}).items():
        if cls.get(k) != v:
            problems.append(f"{k}={cls.get(k)} (expected exactly {v})")
    for k, v in exp.get("min", {}).items():
        if not isinstance(cls.get(k), int) or cls[k] < v:
            problems.append(f"{k}={cls.get(k)} (expected >= {v})")
    if exp.get("matches_expected") and rec.get("matches_expected") != exp["matches_expected"]:
        problems.append(f"matches_expected={rec.get('matches_expected')}")
    sigs = " | ".join(s for s, _ in rec.get("top_error_signatures_breaks", []))
    for s in exp.get("signature_contains", []):
        if s not in sigs:
            problems.append(f"top break signatures lack {s!r}")
    name = case["name"] + (" [TODO data]" if case.get("status") == "TODO" else "")
    if problems:
        return Result(f"golden:{case['name']}", "fail", f"{name}: " + "; ".join(problems),
                      "A known break was missed or miscounted: the classifier or environment regressed. Diff this "
                      "run's freeze files and class-*.txt against the golden run before approving anything.")
    return Result(f"golden:{case['name']}", "pass", f"{name}: all expected values hold")


def check_citations(claims: list[dict], log_root: Path) -> Result:
    """Every LLM (Nemotron) claim must cite >= 1 log line that really contains the quoted text.

    claim = {"text": str, "citations": [{"file": "pytest-new-1.log", "line": 2104, "quote": "Invalid RGBA"}]}
    `file` is relative to the run's log directory and may not escape it.
    """
    log_root = Path(log_root).resolve()
    problems = []
    cache: dict[Path, list[str]] = {}
    for i, cl in enumerate(claims):
        cits = cl.get("citations") or []
        if not cits:
            problems.append(f"claim {i} has no citation: {cl.get('text', '')[:80]!r}")
            continue
        for c in cits:
            f = (log_root / str(c.get("file", ""))).resolve()
            if log_root not in f.parents:
                problems.append(f"claim {i}: citation path {c.get('file')!r} escapes the run directory"); continue
            if not f.is_file():
                problems.append(f"claim {i}: cited file {c.get('file')!r} does not exist"); continue
            lines = cache.setdefault(f, f.read_text(errors="replace").splitlines())
            ln = c.get("line")
            if not isinstance(ln, int) or not 1 <= ln <= len(lines):
                problems.append(f"claim {i}: line {ln!r} out of range for {c.get('file')}"); continue
            q = c.get("quote", "")
            if not q or q not in lines[ln - 1]:
                problems.append(f"claim {i}: {c.get('file')}:{ln} does not contain {q!r}")
    if problems:
        return Result("llm_citations", "fail", "; ".join(problems[:5]) + (f" (+{len(problems) - 5} more)" if len(problems) > 5 else ""),
                      "Drop or regenerate the unsupported claims; every claim must quote a real log line.")
    return Result("llm_citations", "pass", f"{len(claims)} claim(s), every one backed by a real log line")


def evaluate_record(rec: dict, runs_root: Path | None = None, cases: list[dict] | None = None,
                    require_ci_fields: bool = True) -> list[Result]:
    cases = load_golden() if cases is None else cases
    run_dir = (Path(runs_root) / rec["logs"]) if runs_root and rec.get("logs") else None
    if run_dir is not None and not run_dir.is_dir():
        alt = Path(runs_root) / Path(rec["logs"]).name  # runs moved/flattened, e.g. research/dev-runs/<id>
        run_dir = alt if alt.is_dir() else None
    res = [check_schema(rec, require_ci_fields), check_versions(rec, run_dir), check_runs_per_side(rec),
           check_single_thread(rec), check_expected(rec)]
    case = golden_for(rec, cases)
    if case:
        res.append(check_golden_case(rec, case))
    claims = rec.get("explanations")
    if claims is None:
        res.append(Result("llm_citations", "skip", "no Nemotron explanations in this record yet"))
    elif run_dir is None:
        res.append(Result("llm_citations", "fail", "explanations present but the run's log directory is missing",
                          "Keep runs/<id>/ next to the record so claims can be checked."))
    else:
        res.append(check_citations(claims, run_dir))
    return res


def golden_coverage(records: list[dict], cases: list[dict] | None = None) -> list[Result]:
    cases = load_golden() if cases is None else cases
    out = []
    for c in cases:
        hit = [r for r in records if golden_for(r, [c])]
        if not hit:
            st = "todo" if c.get("status") == "TODO" else "fail"
            out.append(Result(f"golden-coverage:{c['name']}", st, f"no record in this batch for {c['name']}"
                              + (f" (TODO: {c.get('todo')})" if st == "todo" else ""),
                              "Run the golden case in the eval batch." if st == "fail" else ""))
        else:
            out.append(Result(f"golden-coverage:{c['name']}", "pass", f"covered by {[r['id'] for r in hit]}"))
    return out


def recommendation(results: list[Result]) -> str:
    return "REJECT" if any(r.status == "fail" for r in results) else "APPROVE"


_ = CLASS_KEYS  # re-exported for callers
