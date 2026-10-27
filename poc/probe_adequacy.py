"""Probe adequacy by coverage: does a probe execute any changed line on the OLD (main) side?

Generic over the pair: "main" is the old side (merge first parent, base branch, or an old release) and "PR" the new
side (merge commit, PR head, or a new release). Only the two file trees matter.

A probe that never reaches the changed code cannot tell main and PR apart, so its green results ("same", "proven")
say nothing about the PR. Each probe is run once more on the main side under coverage.py (ops/daily_run.py,
probe_coverage) and the result goes into the probe's entry as `probe_changed_line_coverage`:

    {"status": "measured", "changed_lines_total": 12, "changed_lines_covered": 5, "files": [...],
     "adequacy": "adequate" | "not_adequate", "note": "..."}
    {"status": "not measured", "why": "...", "adequacy": "unmeasured"}

Changed lines on the main side (main_side_lines) are the main file's lines that the PR replaces or deletes; where the
PR only inserts lines, the main lines on either side of the insertion point stand in for it (they show the probe
reached that spot). A file that is new on the PR side has no main-side lines. Counting uses
poc/coverage_gate.measure (executable lines = coverage's executed + missing lines).

Verdict rule (deciding_items, used by ops/daily_run.with_probes, and poc/behaviour_claims.probe_covers):

* adequate        -> the probe decides as before
* not_adequate    -> it can never lead to 'verified': its green observations are dropped from the verdict and it
                     does not count as checking a behaviour claim. Its red and amber observations still count (a
                     difference is never hidden).
* rejected        -> the probe's claim patterns match none of its observation names. It does not count. Red and
                     amber observations still count, and the reason is recorded on the probe.
* unmeasured      -> no measured line coverage. It does not count as covering the change: green observations are
                     dropped and it does not check a behaviour claim. Red and amber observations still count.
"""
from __future__ import annotations

import difflib

from poc import coverage_gate
from poc.verdict import COLOUR, FindingLabel

ADEQUATE, NOT_ADEQUATE, UNMEASURED = "adequate", "not_adequate", "unmeasured"


def main_side_lines(main_text: str | None, pr_text: str | None, statement_start: bool = False) -> set[int]:
    """1-based lines of main_text that the PR replaces or deletes; for pure insertions, the main lines just before
    and after the insertion point. None (file absent on main) -> empty set.
    statement_start (product checks): each line is mapped to the first line of the main-side statement that holds
    it (coverage_gate.statement_starts), since coverage reports a multi-line statement only at its first line."""
    if main_text is None:
        return set()
    old = main_text.splitlines()
    new = (pr_text or "").splitlines()
    out: set[int] = set()
    for tag, i1, i2, _j1, _j2 in difflib.SequenceMatcher(None, old, new, autojunk=False).get_opcodes():
        if tag in ("replace", "delete"):
            out.update(range(i1 + 1, i2 + 1))
        elif tag == "insert":
            out.update(x for x in (i1, i1 + 1) if 1 <= x <= len(old))
    return coverage_gate.statement_starts(main_text, out) if statement_start else out


def assess(cov: dict | None) -> dict:
    """Coverage block of one probe -> the same block with adequacy and note filled in."""
    cov = dict(cov or {"status": "not measured", "why": "no coverage data"})
    if cov.get("status") != "measured":
        cov.update(adequacy=UNMEASURED, note=f"probe coverage not measured ({cov.get('why', 'unknown reason')})")
        return cov
    t, h = cov.get("changed_lines_total") or 0, cov.get("changed_lines_covered") or 0
    if h > 0:
        cov.update(adequacy=ADEQUATE, note=f"ran {h} of {t} changed line(s) on the main side")
    elif t == 0:
        cov.update(adequacy=NOT_ADEQUATE, note="no changed executable line exists on the main side (new files, "
                                               "comments or docstrings only), so the probe cannot be shown to reach "
                                               "the change")
    else:
        cov.update(adequacy=NOT_ADEQUATE, note=f"ran none of the {t} changed line(s) on the main side")
    return cov


def measure(changed_main: dict, cov_files: dict) -> dict:
    """changed_main: {rel path: main-side changed lines}; cov_files: coverage.py JSON 'files'."""
    return assess(coverage_gate.measure(changed_main, cov_files, require_all=False))


def adequacy_of(item: dict) -> str | None:
    return (item.get("probe_changed_line_coverage") or {}).get("adequacy")


def has_measured_coverage(item: dict) -> bool:
    """True only when line coverage was measured and at least one changed line ran."""
    cov = item.get("probe_changed_line_coverage") or {}
    if cov.get("adequacy") == NOT_ADEQUATE:
        return False
    return cov.get("status") == "measured" and (cov.get("changed_lines_covered") or 0) > 0


def _red_amber(item: dict) -> list[dict]:
    """Observations that still have to be reported. Dropping them could hide a difference and raise the verdict."""
    return [o for o in item.get("observations", []) if COLOUR.get(FindingLabel(o["label"])) in ("red", "amber")]


def deciding_items(items: list[dict]) -> tuple[list[dict], list[str]]:
    """Probe entries as the verdict may use them, and notes for the reason text.

    A not_adequate probe, a probe with no measured line coverage, and a probe whose claim patterns match none of
    its observation names, keep only their red/amber observations (they still flag the PR). Their green ones are
    dropped so they cannot lead to 'verified'."""
    from poc import probes
    out, notes = [], []
    for it in items:
        if it.get("status") in ("uninformative", "not_run"):
            why = it.get("uninformative_reason") or it.get("status")
            notes.append(f"probe {it['id']} is {it['status']} ({why}); its matching results do not count")
            out.append(dict(it, observations=[]))
            continue
        why_reject = it.get("rejected_reason") or probes.rejection_reason(it)
        if it.get("status") not in ("crashed", "error") and (it.get("status") == "rejected" or probes.rejection_reason(it)):
            notes.append(why_reject or f"probe {it['id']} is rejected; its matching results do not count")
            out.append(dict(it, observations=_red_amber(it)))
            continue
        if adequacy_of(it) == NOT_ADEQUATE:
            notes.append(f"probe {it['id']} is not_adequate ({it['probe_changed_line_coverage'].get('note')}); its "
                         f"matching results do not count")
            out.append(dict(it, observations=_red_amber(it)))
            continue
        if not has_measured_coverage(it):
            cov = it.get("probe_changed_line_coverage") or {}
            why = cov.get("why") or "no coverage data"
            notes.append(f"probe {it['id']} has no measured line coverage ({why}); it does not count as covering "
                         f"the change")
            out.append(dict(it, observations=_red_amber(it)))
            continue
        out.append(it)
    return out, notes


def summary(items: list[dict]) -> dict:
    """Record-level `probe_changed_line_coverage`: per probe id, covered / total and adequacy."""
    per = {it["id"]: {k: (it.get("probe_changed_line_coverage") or {}).get(k)
                      for k in ("status", "changed_lines_covered", "changed_lines_total", "adequacy")}
           for it in items}
    if not per:
        return {"status": "no probes", "probes": {}}
    st = "measured" if all(v["status"] == "measured" for v in per.values()) else (
        "partly measured" if any(v["status"] == "measured" for v in per.values()) else "not measured")
    return {"status": st, "side": "main", "probes": per,
            "not_adequate": sorted(k for k, v in per.items() if v["adequacy"] == NOT_ADEQUATE)}
