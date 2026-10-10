"""Verdict enums and the deterministic PR verdict rule (spec section 6.7).

Verdicts are informational. Proof-of-Change never fails a check run and never blocks a merge by default.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Verdict(str, Enum):
    VERIFIED = "verified"                  # green check
    NEEDS_ATTENTION = "needs_attention"    # neutral check
    COULD_NOT_VERIFY = "could_not_verify"  # neutral check


class FindingLabel(str, Enum):
    """Per-probe result, shown as a colour on the behavior map."""
    PROVEN = "proven"                      # green: changed as claimed, or unchanged where "no change" was claimed
    FALSE_CLAIM = "false_claim"            # red
    UNMENTIONED_CHANGE = "unmentioned"     # red: behaviour change on public surface that no claim covers
    NEEDS_HUMAN = "needs_human"            # amber: differs, related to a claim, model unsure it matches
    FLAKY = "flaky"                        # amber: a side disagreed with itself across reruns (never red)
    NOT_TESTABLE = "not_testable"          # grey: always shown, never hidden
    NO_DIFFERENCE = "no_difference"        # same on both sides, no claim about it


COLOUR = {
    FindingLabel.PROVEN: "green", FindingLabel.NO_DIFFERENCE: "green",
    FindingLabel.FALSE_CLAIM: "red", FindingLabel.UNMENTIONED_CHANGE: "red",
    FindingLabel.NEEDS_HUMAN: "amber", FindingLabel.FLAKY: "amber",
    FindingLabel.NOT_TESTABLE: "grey",
}

# Check-run conclusions: never "failure" (verdicts do not block merges).
CHECK_CONCLUSION = {Verdict.VERIFIED: "success", Verdict.NEEDS_ATTENTION: "neutral", Verdict.COULD_NOT_VERIFY: "neutral"}


@dataclass
class Claim:
    id: str
    testable: bool
    probed: bool = False          # at least one probe actually ran on both sides
    proven: bool = False


@dataclass
class RunSummary:
    build_ok: bool
    claims: list[Claim] = field(default_factory=list)
    findings: list[FindingLabel] = field(default_factory=list)


def pr_verdict(run: RunSummary) -> Verdict:
    """Spec 6.7, applied in this order:
    1. could_not_verify: the project did not build, or fewer than half of the testable claims could be probed.
    2. needs_attention: any false claim, any unmentioned change on public surface, or any amber finding.
    3. verified: every testable claim proven and no red finding.
    Anything else (e.g. a testable claim probed but not proven, with no red/amber finding) -> needs_attention.
    [ASSUMED] A PR with zero testable claims and no findings is verified only if at least one probe ran.
    """
    if not run.build_ok:
        return Verdict.COULD_NOT_VERIFY
    testable = [c for c in run.claims if c.testable]
    if testable and sum(c.probed for c in testable) * 2 < len(testable):
        return Verdict.COULD_NOT_VERIFY
    if any(COLOUR.get(f) in ("red", "amber") for f in run.findings):
        return Verdict.NEEDS_ATTENTION
    if all(c.proven for c in testable):
        if not testable and not run.findings:
            return Verdict.COULD_NOT_VERIFY
        return Verdict.VERIFIED
    return Verdict.NEEDS_ATTENTION
