"""Labelled-PR evals: withhold the answer, then score catch rate and false-alarm rate.

    catch rate       = flagged regressions / scorable caused_regression PRs
    false-alarm rate = flagged safe PRs   / scorable safe PRs
"flagged" means verdict == needs_attention. could_not_verify is counted separately, never as a catch.
Only cases with verification == "verified" are scored; TODO/unverified cases and example_data are reported, not scored.

Blind scoring. A verdict counts in the BLIND metrics only if every probe that could decide it under the record's
baseline is blind: written by a live model (provider nebius) and passed the freeze rule (poc/freeze.py). Fixed probes
(post-hoc or hand-written), recorded model responses (test fixtures) and differential probes are never blind; records
whose verdict they could decide are scored in a separate, clearly labelled NOT BLIND column (`score_records`).
A record with no deciding probes (baseline tests, or no probe) is blind.
"""
from __future__ import annotations

import json
from pathlib import Path

from poc import freeze
from poc.verdict import Verdict

LABELS_PATH = Path(__file__).with_name("labelled_prs.json")
ANSWER_WORDS = ("regression", "caused_regression", "expected_verdict", "yanked", "broke")


def load_cases(path: Path = LABELS_PATH) -> list[dict]:
    return json.loads(Path(path).read_text())["cases"]


def blind_input(case: dict) -> dict:
    """What Proof-of-Change receives: the input block only. Raises if the answer leaks into it."""
    inp = dict(case["input"])
    leaks = [w for w in ANSWER_WORDS if w in json.dumps(inp).lower()]
    if leaks:
        raise ValueError(f"{case['id']}: answer leaks into input ({leaks})")
    return inp


def score(cases: list[dict], verdicts: dict[str, str]) -> dict:
    """verdicts: case id -> Verdict value produced by a blind run."""
    scorable = [c for c in cases if c["answer"].get("verification") == "verified"]
    reg = [c for c in scorable if c["answer"]["label"] == "caused_regression"]
    safe = [c for c in scorable if c["answer"]["label"] == "safe"]
    flagged = {cid for cid, v in verdicts.items() if v == Verdict.NEEDS_ATTENTION.value}
    cnv = sorted(cid for cid, v in verdicts.items() if v == Verdict.COULD_NOT_VERIFY.value)
    missing = sorted(c["id"] for c in scorable if c["id"] not in verdicts)
    caught = [c["id"] for c in reg if c["id"] in flagged]
    false_alarms = [c["id"] for c in safe if c["id"] in flagged]
    return {
        "scored_regressions": len(reg), "caught": caught,
        "catch_rate": round(len(caught) / len(reg), 3) if reg else None,
        "scored_safe": len(safe), "false_alarms": false_alarms,
        "false_alarm_rate": round(len(false_alarms) / len(safe), 3) if safe else None,
        "could_not_verify": cnv, "missing_verdicts": missing,
        "not_scored": sorted(c["id"] for c in cases if c not in scorable),
        "note": "Small set: report counts, not percentages, in public material (spec 9.2).",
    }


class NotBlind(ValueError):
    """Raised when a non-blind probe result is offered to blind scoring."""


def deciding_probes(rec: dict) -> list[dict]:
    """Probe results that could decide the record's verdict under its baseline (ops/daily_run.probe_items)."""
    from ops.daily_run import probe_items
    return (probe_items(rec.get("probes"), rec.get("baseline")) or {}).get("items") or []


def non_blind_probes(rec: dict) -> list[str]:
    """Labels of the deciding probes that are not blind (empty: the verdict is blind)."""
    def label(it):
        g = (it.get("freeze") or {}).get("generator") or it.get("generator") or {}
        return g.get("label") or "fixed (no generator recorded)"
    return [f"{it.get('id')}: {label(it)}" for it in deciding_probes(rec) if not freeze.is_blind(it)]


def record_is_blind(rec: dict) -> bool:
    return not non_blind_probes(rec)


def assert_blind(rec: dict) -> None:
    bad = non_blind_probes(rec)
    if bad:
        raise NotBlind(f"{rec.get('id')}: not blind ({'; '.join(bad)})")


def case_for(cases: list[dict], rec: dict) -> dict | None:
    pr = rec.get("pr") or {}
    repo, num = pr.get("repo") or rec.get("repo"), pr.get("number")
    return next((c for c in cases if c["input"].get("repo") == repo and c["input"].get("pr") == num), None)


def blind_score(cases: list[dict], records: list[dict]) -> dict:
    """Blind metrics only: refuses (NotBlind) any record whose verdict a non-blind probe could decide."""
    verdicts = {}
    for rec in records:
        assert_blind(rec)
        c = case_for(cases, rec)
        if c:
            verdicts[c["id"]] = rec["verdict"]
    return score(cases, verdicts)


def score_records(cases: list[dict], records: list[dict]) -> dict:
    """{"blind": metrics over blind records, "not_blind": metrics over the others (labelled, never mixed in)}."""
    blind = [r for r in records if record_is_blind(r)]
    other = [r for r in records if not record_is_blind(r)]
    out = {"blind": blind_score(cases, blind)}
    v = {c["id"]: r["verdict"] for r in other if (c := case_for(cases, r))}
    out["not_blind"] = score(cases, v) | {
        "label": "NOT BLIND: verdicts a post-hoc fixed probe, a recorded model fixture or a differential probe could "
                 "decide; known-answer regression data, not a blind result",
        "records": {r.get("id"): non_blind_probes(r) for r in other}}
    return out
