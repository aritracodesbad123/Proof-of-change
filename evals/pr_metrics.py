"""Labelled-PR evals: withhold the answer, then score catch rate and false-alarm rate.

    catch rate       = flagged regressions / scorable caused_regression PRs
    false-alarm rate = flagged safe PRs   / scorable safe PRs
"flagged" means verdict == needs_attention. could_not_verify is counted separately, never as a catch.
Only cases with verification == "verified" are scored; TODO/unverified cases and example_data are reported, not scored.
"""
from __future__ import annotations

import json
from pathlib import Path

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
