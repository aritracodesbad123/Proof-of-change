"""Eval checks. Each check returns a Result(check, status, detail, fix).

status is one of: pass, fail, warn, skip, todo.
  fail -> the run must be rejected
  warn -> approver should look, but the run is not rejected for it
  todo -> the check is not active yet (missing data from the protocol owner)
"""
from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path

from guardrails.schema import CLASS_KEYS, REQUIRED_RUNS_PER_SIDE, SCHEMA_ID, SINGLE_THREAD_VARS, mode_for, validate_record

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


def check_schema(rec: dict, require_ci_fields: bool = True, require_v1: bool | None = None) -> Result:
    errs = validate_record(rec, require_ci_fields=require_ci_fields, require_v1=require_v1)
    mode = mode_for(rec, require_ci_fields, require_v1)
    if not errs:
        ref = " (schema reference verified by sha256)" if rec.get("schema_sha256") else ""
        return Result("schema", "pass", f"record matches the shared schema {SCHEMA_ID}, mode {mode}{ref}")
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
                and _norm(rec.get("dependent", "")) == _norm(m["dependent"])
                and ("old_version" not in m or rec.get("old_version") == m["old_version"])):
            return c
    return None


def check_golden_case(rec: dict, case: dict) -> Result:
    cls, exp = rec.get("classification") or {}, case["expect"]
    problems = []
    for k, v in exp.get("exact", {}).items():
        if cls.get(k) != v:
            problems.append(f"{k}={cls.get(k)} (expected exactly {v})")
    for k, v in exp.get("min", {}).items():
        if not isinstance(cls.get(k), int) or cls[k] < v:
            problems.append(f"{k}={cls.get(k)} (expected >= {v})")
    if "accepted" in exp and rec.get("accepted") is not exp["accepted"]:
        problems.append(f"accepted={rec.get('accepted')} (expected {exp['accepted']})")
    if exp.get("matches_expected") and rec.get("matches_expected") != exp["matches_expected"]:
        problems.append(f"matches_expected={rec.get('matches_expected')}")
    sigs = " | ".join(normalise_error_line(s) for s, _ in rec.get("top_error_signatures_breaks", []))
    for s in exp.get("signature_contains", []):
        if s not in sigs:
            problems.append(f"top break signatures lack {s!r}")
    problems += _per_run_summary_problems(rec, exp.get("per_run_summary", {}))
    status = case.get("status", "active")
    name = case["name"] + {"TODO": " [TODO data]", "pending": " [PENDING, not golden yet]"}.get(status, "")
    if problems and status == "pending":
        return Result(f"golden:{case['name']}", "warn", f"{name}: " + "; ".join(problems),
                      "Candidate pair does not hold yet; the protocol owner to confirm or replace it before it becomes golden.")
    if problems:
        return Result(f"golden:{case['name']}", "fail", f"{name}: " + "; ".join(problems),
                      "A known break was missed or miscounted: the classifier or environment regressed. Diff this "
                      "run's freeze files and class-*.txt against the golden run before approving anything.")
    return Result(f"golden:{case['name']}", "pass", f"{name}: all expected values hold")


PYTEST_E_PREFIX_RE = re.compile(r"^\s*E(?:\s+|$)")
IMPORT_ERR_NAMES = ("ImportError", "ModuleNotFoundError")


def normalise_error_line(line: str) -> str:
    """Strip pytest's failure-line prefix (`E   `) and surrounding whitespace, so messages are compared by
    content, not by how the log happened to render them. 'E   ImportError: x' -> 'ImportError: x'."""
    return PYTEST_E_PREFIX_RE.sub("", str(line or ""), count=1).strip()


def is_import_error_mentioning(line: str, needle: str) -> bool:
    """True if `line` (with or without the `E   ` prefix, possibly after a 'package import x: ' label)
    is an ImportError/ModuleNotFoundError whose text contains `needle`."""
    msg = normalise_error_line(line)
    return needle in msg and any(re.search(rf"\b{n}\b", msg) for n in IMPORT_ERR_NAMES)


SUMMARY_RE = re.compile(r"(\d+) (passed|failed|errors?|skipped|xfailed|xpassed)\b")


def parse_pytest_summary(line: str) -> dict:
    """'2238 passed, 33 skipped, 1 xfailed' -> {'passed': 2238, 'skipped': 33, 'xfailed': 1}. 'error' -> 'errors'."""
    out = {}
    for n, k in SUMMARY_RE.findall(line or ""):
        out["errors" if k.startswith("error") else k] = int(n)
    return out


def run_summary_counts(r: dict) -> tuple[dict, str | None]:
    """Raw pytest counts for one run, keyed like parse_pytest_summary. Uses the runner's `summary_counts`
    when present (normalised: error->errors, warning dropped) and cross-checks it against `pytest_summary`."""
    parsed = parse_pytest_summary(r.get("pytest_summary", ""))
    sc = r.get("summary_counts")
    if not isinstance(sc, dict):
        return parsed, None
    norm = {("errors" if k.startswith("error") else k): v for k, v in sc.items() if not k.startswith("warning")}
    clash = None
    if {k: v for k, v in norm.items() if v} != {k: v for k, v in parsed.items() if v}:
        clash = f"summary_counts {norm} disagree with pytest_summary {parsed}"
    return norm, clash


def _per_run_summary_problems(rec: dict, spec: dict) -> list[str]:
    """spec = {"old": {"passed": 2238}, "new": {"passed": 0, "errors": 525}}; every run on that side must match.

    Counts come from pytest's own summary line (per_run[].pytest_summary), not from the JUnit-derived
    per_run counts, because JUnit counts xpassed as passed. Missing keys in the summary count as 0.
    """
    problems = []
    for side, want in spec.items():
        runs = [r for r in rec.get("per_run", []) if r.get("side") == side]
        if len(runs) != REQUIRED_RUNS_PER_SIDE:
            problems.append(f"{side}: {len(runs)} runs, gate needs {REQUIRED_RUNS_PER_SIDE}")
        for r in runs:
            got, clash = run_summary_counts(r)
            if clash:
                problems.append(f"{side} run {r.get('run')}: {clash}")
            for k, v in want.items():
                if got.get(k, 0) != v:
                    problems.append(f"{side} run {r.get('run')}: pytest says {k}={got.get(k, 0)} (gate {v})")
    return problems


def check_import_message(rec: dict, needle: str, run_dir: Path | None, case_name: str) -> Result:
    """The import failure on the new side must mention `needle` (e.g. `_safe_tags`) in every new-side run.

    Sources, in order: record field `import_failure_messages` (planned runner field), the runner's new-side
    import probe (`dependent_import.new`), the record's break signatures, then the run's pytest-new-N.log files.
    If none is available the check is skipped. Messages are matched by content: pytest's `E   ` prefix and
    whitespace are stripped first (normalise_error_line), so a signature that starts with `E   ` still matches.
    """
    cid = f"golden:{case_name}:import_message"
    msgs = rec.get("import_failure_messages")
    if isinstance(msgs, list) and msgs:
        ok = any(needle in normalise_error_line(m) for m in msgs)
        return Result(cid, "pass" if ok else "fail",
                      f"record import_failure_messages {'mention' if ok else 'do not mention'} {needle!r}",
                      "" if ok else "The import fails for a different reason than the golden case; inspect the new-side logs.")
    probe = (rec.get("dependent_import") or {}).get("new") if isinstance(rec.get("dependent_import"), dict) else None
    probe_hits = [f"{k}: {v}" for k, v in (probe or {}).items() if is_import_error_mentioning(str(v), needle)]
    sigs = [normalise_error_line(s) for s, _ in rec.get("top_error_signatures_breaks", [])
            if is_import_error_mentioning(s, needle)]
    if probe_hits or sigs:
        src = (f"new-side import probe ({probe_hits[0][:90]})" if probe_hits else "") + \
              ("; " if probe_hits and sigs else "") + (f"break signature ({sigs[0][:90]})" if sigs else "")
        return Result(cid, "pass", f"import error mentioning {needle!r} found in {src}")
    if run_dir is not None:
        new_runs = sorted(r.get("run") for r in rec.get("per_run", []) if r.get("side") == "new")
        missing, cited = [], []
        for n in new_runs:
            f = run_dir / f"pytest-new-{n}.log"
            hit = None
            if f.is_file():
                with f.open(errors="replace") as fh:
                    for ln, line in enumerate(fh, 1):
                        if is_import_error_mentioning(line, needle):
                            hit = f"{f.name}:{ln}"
                            break
            (cited if hit else missing).append(hit or f.name)
        if new_runs and not missing:
            return Result(cid, "pass", f"import error mentioning {needle!r} found in every new-side log ({', '.join(cited)}); "
                          "record itself does not carry the message")
        if new_runs:
            return Result(cid, "fail", f"no import error mentioning {needle!r} in {missing}",
                          "The import fails for a different reason (or not at all); inspect the new-side logs.")
    return Result(cid, "skip", f"cannot check {needle!r}: record has no import_failure_messages field, the break signatures "
                  "do not carry it, and the run logs are not available",
                  "Runner should record import-failure messages (planned), or keep runs/<id>/ next to the record.")


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
                    require_ci_fields: bool = True, require_v1: bool | None = None) -> list[Result]:
    cases = load_golden() if cases is None else cases
    run_dir = (Path(runs_root) / rec["logs"]) if runs_root and rec.get("logs") else None
    if run_dir is not None and not run_dir.is_dir():
        alt = Path(runs_root) / Path(rec["logs"]).name  # runs moved/flattened, e.g. research/dev-runs/<id>
        run_dir = alt if alt.is_dir() else None
    res = [check_schema(rec, require_ci_fields, require_v1), check_versions(rec, run_dir), check_runs_per_side(rec),
           check_single_thread(rec), check_expected(rec)]
    case = golden_for(rec, cases)
    if case:
        res.append(check_golden_case(rec, case))
        needle = case["expect"].get("import_failure_message_contains")
        if needle:
            res.append(check_import_message(rec, needle, run_dir, case["name"]))
    claims = rec.get("explanations")
    if claims is None:
        res.append(Result("llm_citations", "skip", "no Nemotron explanations in this record yet"))
    elif run_dir is None:
        res.append(Result("llm_citations", "fail", "explanations present but the run's log directory is missing",
                          "Keep runs/<id>/ next to the record so claims can be checked."))
    else:
        res.append(check_citations(claims, run_dir))
    return res


def golden_coverage(records: list[dict], cases: list[dict] | None = None, require: bool = False) -> list[Result]:
    """Which golden cases this batch covers. With require=True (golden eval batch, CI) a missing active case fails;
    otherwise (daily batches) it is skipped. TODO/pending cases are never required."""
    cases = load_golden() if cases is None else cases
    out = []
    for c in cases:
        hit = [r for r in records if golden_for(r, [c])]
        if hit:
            out.append(Result(f"golden-coverage:{c['name']}", "pass", f"covered by {[r['id'] for r in hit]}"))
        elif c.get("status") in ("TODO", "pending"):
            out.append(Result(f"golden-coverage:{c['name']}", "todo",
                              f"no record in this batch ({c.get('status')}: {c.get('todo')})"))
        elif require:
            out.append(Result(f"golden-coverage:{c['name']}", "fail", "active golden case missing from this golden batch",
                              "Run the golden case in the eval batch."))
        else:
            out.append(Result(f"golden-coverage:{c['name']}", "skip", "not in this batch (daily batch; not required)"))
    return out


def recommendation(results: list[Result]) -> str:
    return "REJECT" if any(r.status == "fail" for r in results) else "APPROVE"


_ = CLASS_KEYS  # re-exported for callers
