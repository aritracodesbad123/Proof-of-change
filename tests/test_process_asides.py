"""Claim extraction drops an author's process asides; real claims still need probes (loguru #1515, invoke #1097)."""
import json
from pathlib import Path

import pytest

from poc import behaviour_claims as bc
from poc import claim_hygiene as ch

FIX = Path(__file__).parent / "fixtures" / "pr_text"


def _pr(name):
    return json.loads((FIX / f"{name}.json").read_text())


def test_loguru_1515_aside_is_not_a_claim():
    pr = _pr("loguru-1515")
    quotes = [c["quote"] for c in bc.find(pr["title"], pr["body"])]
    assert "I left it untouched." not in quotes
    assert quotes == []


@pytest.mark.parametrize("text", [
    "I left it untouched.",
    "We kept that as is.",
    "I deliberately didn't touch the formatter, it is left unchanged.",
    "I haven't changed the CI config; it is untouched.",
])
def test_asides_dropped(text):
    assert bc.find("t", text) == []


@pytest.mark.parametrize("text", [
    "I kept the output unchanged.",
    "We left the return values untouched.",
    "Results are unchanged.",
    "The parser is backwards compatible.",
    "Existing behaviour is untouched.",
])
def test_real_claims_kept(text):
    assert len(bc.find("t", text)) == 1


def test_invoke_1097_test_outcome_claims_dropped_real_claims_kept():
    assert ch.is_test_outcome_claim("Two new test cases added for regression coverage fail before the fix.")
    assert ch.is_test_outcome_claim("The control test case passes both before and after the fix.")
    assert not ch.is_test_outcome_claim(
        "When a required argument is omitted, the error message shows the Python attribute name instead of the CLI name.")
    assert not ch.is_test_outcome_claim(
        "Real CLI checks confirm that after the fix the missing-argument error uses the CLI name and successful "
        "`--param-1`/`--param-2` calls work.")


def test_invoke_1097_no_spurious_preservation_claim():
    pr = _pr("invoke-1097")
    assert bc.find(pr["title"], pr["body"]) == []
