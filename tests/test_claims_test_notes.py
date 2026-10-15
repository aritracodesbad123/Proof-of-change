"""Sentences about the PR's own tests or a tool's output are not behaviour claims (2026-10-14 decision)."""
from poc import behaviour_claims as b


def quotes(body):
    return [c["quote"] for c in b.find("t", body)]


def test_test_description_is_not_a_claim():
    assert quotes("- Add regressions for learned lambdas, near-zero values, untouched columns, and unchanged inputs.") == []
    assert quotes("Added regression tests: outputs are unchanged for ints.") == []
    assert quotes("New tests check that results stay unchanged.") == []


def test_tool_note_is_not_a_claim():
    assert quotes("The mypy check reports two errors in unrelated files; its output is identical on the base.") == []
    assert quotes("ruff output is unchanged.") == []


def test_test_plan_section_is_dropped_but_later_sections_kept():
    body = "## Test plan\n- results unchanged on the old suite\n\n## Notes\nOutputs are unchanged for floats."
    assert quotes(body) == ["Outputs are unchanged for floats."]


def test_real_behaviour_claims_still_found():
    assert quotes("The values are unchanged; only the freq attribute differs.")
    assert quotes("Results are unchanged for float input. Tests were added.") == ["Results are unchanged for float input."]
    assert quotes("Missing values are passed through to the output.")
