"""Run one benchmark case through the real verdict code, offline and without a model.

This is the "tool" side of the benchmark. It reads only the case folder (before/, after/, claim.txt,
recorded.json) and never the answer key: any path naming an answer file is refused.
Route "single" is a single-PR check (console or request-a-check); route "daily" adds the daily-run selection.
The final verdict goes through the same steps as a real run: typing-only rule, verdict rules, coverage gate and
AI-probe gate (ops/daily_run.gate). The golden re-derivation (evals/checks.derive_verdict) is computed alongside,
so the benchmark also catches the two paths drifting apart.
"""
from __future__ import annotations

import json
from pathlib import Path

from ops import daily_run as dr
from poc import demo_helper, probes

PKG_NAME = "toypkg"
CODES = {"P": ("passed", ""), "F": ("failed", "AssertionError"), "E": ("error", "RuntimeError")}
TEST_FILE = "tests/test_toypkg.py::test_"


def _refuse_answers(path: Path) -> None:
    if "answer" in str(path).lower():
        raise ValueError(f"refusing to read {path.name}: a benchmark run never sees the answer key")


def _files(d: Path, side: str) -> dict[str, str]:
    root = d / side
    return {str(p.relative_to(root)): p.read_text() for p in sorted(root.rglob("*")) if p.is_file()}


def changed_paths(d: Path) -> list[str]:
    before, after = _files(d, "before"), _files(d, "after")
    return sorted(p for p in set(before) | set(after) if before.get(p) != after.get(p))


def _runs(spec: dict) -> dict:
    out = {"main": [{}, {}, {}], "pr": [{}, {}, {}]}
    for test, sides in spec.items():
        for side, seq in zip(("main", "pr"), sides):
            for i, c in enumerate(seq):
                if c in CODES:
                    out[side][i][TEST_FILE + test] = CODES[c]
    return out


def _probe_item(p: dict) -> dict:
    spec = {"id": "model-1", "target": PKG_NAME, "about": "recorded model probe", "claims": p["claims"]}
    recorded_runs = {"main": p["main"], "pr": p["pr"]}
    return {**spec, "source": "model", "status": "ran", "runs": recorded_runs,
            "observations": probes.judge(spec, recorded_runs),
            "probe_changed_line_coverage": {"status": "measured", "changed_lines_total": p["changed_lines_total"],
                                            "changed_lines_covered": p["changed_lines_covered"]}}


def run_case(case_dir: Path, baseline: str = "full", route: str = "single") -> dict:
    """{'verdict', 'reason', 'golden_verdict'} for one case. golden_verdict is None where the golden path does not
    apply (skips, typing-only, recovery rerun)."""
    d = Path(case_dir)
    _refuse_answers(d)
    rec_in = json.loads((d / "recorded.json").read_text())
    paths = changed_paths(d)
    files = dr.classify_files(paths, PKG_NAME)
    if route == "daily":
        skip = dr.selection_skip_for_files(files, PKG_NAME)
        if skip:
            return {"verdict": "skipped", "reason": skip, "golden_verdict": None}
    if "rerun_tests" in rec_in:  # setup-helper recovery rerun (poc/demo_helper.py)
        # The recorded evidence: a first run stopped by a setup gap, then a rerun whose tests all passed.
        cov = rec_in["probe_changed_line_coverage"]
        first = {"verdict": "could_not_verify", "reason": "setup gap: " + rec_in["first_run_setup_gap"]}
        rerun = {"verdict": "verified", "reason": "rerun: " + rec_in["rerun_tests"]}
        rec = dict(first, coverage={"changed_lines_total": rec_in["changed_lines_total"]},
                   probes={"items": [{"id": "model-1", "source": "model", "status": "ran", "observations": [],
                                      "probe_changed_line_coverage": {"status": "measured", **cov}}]})
        held = demo_helper._coverage_blocks_verified(rec, rerun["verdict"], lambda: dict(rerun))
        v, why = held if held else (rerun["verdict"], rerun["reason"])
        return {"verdict": v, "reason": why, "golden_verdict": None}
    rec: dict = {"baseline": baseline, "files": files, "behaviour_claims": []}
    if dr.mark_typing_only(rec, files):
        return {"verdict": rec["verdict"], "reason": rec["reason"], "golden_verdict": None}
    cnv = rec_in.get("install_error")
    cmp = None if cnv else dr.compare_sides(_runs(rec_in["runs"]))
    p = rec_in.get("probe")
    rec["comparison"] = cmp
    rec["probes"] = probes.apply_status({"items": [_probe_item(p)]}) if p else None
    # A real run only checks for a docstring-only change once both sides installed (ops/daily_run.py).
    rec["docstring_only"] = not cnv and dr.change_is_docstring_only(files, d / "before", d / "after")
    rec["coverage"] = ({"status": "measured", "changed_lines_total": 1, "changed_lines_covered": 1}
                       if files.get("package_py") else {"status": "not measured", "why": "no changed python"})
    dr._store_verdict(rec, cmp, cnv, None)
    out = dr.gate(rec)
    if cnv:
        rec["reason"] = cnv
    from evals.checks import derive_verdict
    return {"verdict": out["verdict"], "reason": out["reason"], "golden_verdict": derive_verdict(rec, baseline)}
