"""Schema validation for observation records.

Fields mirror what Jonathan's runner (br_run.py) writes today, plus the CI fields
Nathan's harness adds (`machine_type`, `thread_env`, `ci`). Pure stdlib, no jsonschema
dependency, so it runs anywhere the runner runs.
"""
from __future__ import annotations

CLASS_KEYS = ("real_break", "already_broken", "flaky", "import_failure", "fixed_by_new", "lost_tests")
SINGLE_THREAD_VARS = ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS")
REQUIRED_RUNS_PER_SIDE = 3

# field -> allowed types (None means JSON null is allowed)
RECORD_FIELDS: dict[str, tuple] = {
    "id": (str,), "date_ist": (str,), "who": (str,),
    "upstream": (str,), "old_version": (str,), "new_version": (str,),
    "new_version_requested": (str,), "new_direct_url": (str, type(None)),
    "dependent": (str,), "dependent_version": (str,), "test_source": (str,),
    "test_selection": (str,), "subset_note": (str, type(None)),
    "python": (str,), "machine": (str,), "host": (str,), "cpu_count": (int,),
    "platform": (str,), "runs_per_side": (int,), "workers": (str,),
    "test_timeout_s": (int,), "run_timeout_s": (int,),
    "env_diff": (list,), "pip_check_new": (str,), "per_run": (list,),
    "classification": (dict,), "top_error_signatures_breaks": (list,),
    "top_error_signatures_already_broken": (list,), "duration_s": (dict,),
    "expected": (str,), "expected_class": (str,), "matches_expected": (str,),
    "hand_check": (str, dict, type(None)), "upstream_issue": (str, type(None)),
    "notes": (str, type(None)), "logs": (str,),
}
# Added by harness/run.py. Required by Jonathan's constraint: every record names its machine type.
CI_FIELDS: dict[str, tuple] = {
    "machine_type": (dict,),   # {"arch", "os", "runner_name", "runner_os", "runner_arch", "image", "cpu_count"}
    "thread_env": (dict,),     # the single-thread variables actually used
}
PER_RUN_FIELDS = {
    "side": (str,), "run": (int,), "exit": (int, str), "seconds": (int, float),
    "passed": (int,), "failed": (int,), "error": (int,), "collection_errors": (int,),
    "skipped": (int,), "pytest_summary": (str,),
}
EXPECTED_CLASSES = {"no_break", "break", "unknown"}
MATCHES = {"yes", "no", "n/a"}


def _typecheck(obj: dict, spec: dict, where: str) -> list[str]:
    errs = []
    for k, types in spec.items():
        if k not in obj:
            errs.append(f"{where}: missing field '{k}'")
        elif not isinstance(obj[k], types) or (isinstance(obj[k], bool) and bool not in types):
            errs.append(f"{where}: field '{k}' has type {type(obj[k]).__name__}, expected {'/'.join(t.__name__ for t in types)}")
    return errs


def validate_record(rec: dict, require_ci_fields: bool = True) -> list[str]:
    """Return a list of human-readable schema errors (empty list = valid)."""
    if not isinstance(rec, dict):
        return ["record is not a JSON object"]
    rid = rec.get("id", "<no id>")
    errs = _typecheck(rec, RECORD_FIELDS, rid)
    if require_ci_fields:
        errs += _typecheck(rec, CI_FIELDS, rid)
        mt = rec.get("machine_type")
        if isinstance(mt, dict) and not (mt.get("arch") and mt.get("os")):
            errs.append(f"{rid}: machine_type must include at least 'arch' and 'os'")
    if isinstance(rec.get("classification"), dict):
        for k in CLASS_KEYS:
            v = rec["classification"].get(k)
            if not isinstance(v, int) or v < 0:
                errs.append(f"{rid}: classification.{k} must be a non-negative int, got {v!r}")
    if isinstance(rec.get("per_run"), list):
        for i, r in enumerate(rec["per_run"]):
            if not isinstance(r, dict):
                errs.append(f"{rid}: per_run[{i}] is not an object"); continue
            errs += _typecheck(r, PER_RUN_FIELDS, f"{rid}.per_run[{i}]")
            if r.get("side") not in ("old", "new"):
                errs.append(f"{rid}.per_run[{i}]: side must be 'old' or 'new'")
    if rec.get("expected_class") not in EXPECTED_CLASSES:
        errs.append(f"{rid}: expected_class must be one of {sorted(EXPECTED_CLASSES)}")
    if rec.get("matches_expected") not in MATCHES:
        errs.append(f"{rid}: matches_expected must be one of {sorted(MATCHES)}")
    return errs
