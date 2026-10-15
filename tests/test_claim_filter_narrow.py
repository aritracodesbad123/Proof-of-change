"""The test/tool filter must not swallow product sentences (2026-10-15 decision).

The 17 sentences below were wrongly dropped by the first version of the filter on four pull-request
descriptions (these four were used to tune this narrower rule, so they are regressions, not held-out cases). They describe the product change, the bug, or that nothing else changes, so they must reach the
claim extractor."""
import json
import pathlib
import re

import pytest

from poc import behaviour_claims as b

BODIES = json.loads((pathlib.Path(__file__).parent / "fixtures" / "claim_filter_pr19_regressions.json").read_text())

WRONGLY_DROPPED = [
    ("pr_1", "extend linter Fix to support creating files"),
    ("pr_2", "This cleanup removes legacy code and reduces maintenance burden without affecting any current functionality"),
    ("pr_3", "Fix overlapping images in screenshot merging by using scroll positions to crop and merge images without overlap"),
    ("pr_3", "Modify `_scrolling_screenshots_helper` to return a tuple of screenshots and their scroll positions"),
    ("pr_3", "Add `_merge_images_by_position` to merge screenshots using scroll positions to remove overlaps"),
    ("pr_3", "Update `take_scrolling_screenshot` to use `_merge_images_by_position` for merging images"),
    ("pr_3", "`_scrolling_screenshots_helper` now returns `tuple[list[bytes], list[int]]` instead of `list[bytes]`"),
    ("pr_3", "New function `_merge_images_by_position` added for merging images without overlap"),
    ("pr_4", "Other providers remain unaffected"),
    ("pr_4", "Fixes the issue where `litellm_proxy` provider would force Responses API requests through completion "
             "transformations even when native support was available"),
    ("pr_4", "`litellm_proxy` provider lacks native Responses API support, causing unnecessary transformations and errors"),
    ("pr_4", "The `litellm_proxy` provider does not have native support for OpenAI's Responses API"),
    ("pr_4", "Currently, `ProviderConfigManager.get_provider_responses_api_config()` returns `None` for "
             "`LlmProviders.LITELLM_PROXY`, causing the responses API to fall back"),
    ("pr_4", "When using `litellm_proxy/openai/gpt-5-mini` (or similar OpenAI models that support Responses API), LiteLLM should:"),
    ("pr_4", "Detect that the underlying model supports the Responses API"),
    ("pr_4", "Use the native `/v1/responses` endpoint directly via the proxy"),
    ("pr_4", "Avoid the transformation layer entirely"),
]


def _sentence_with(text, fragment):
    for s in re.split(r"[.!?](?=\s)|\n", text):
        if fragment in s:
            return s
    return None


def test_seventeen_regression_sentences():
    assert len(WRONGLY_DROPPED) == 17


@pytest.mark.parametrize("pr,fragment", WRONGLY_DROPPED)
def test_product_sentence_is_kept(pr, fragment):
    kept = b._drop_test_sections(b._clean(BODIES[pr]))
    s = _sentence_with(kept, fragment)
    assert s is not None, "sentence was dropped with its section"
    assert not b.about_tests_or_tools(s), "sentence was dropped as a test/tool note"


@pytest.mark.parametrize("pr,fragment", [
    ("pr_1", "pytest tests/core/linter/test_builtin.py"),
    ("pr_2", "Linting passes with no issues"),
    ("pr_3", "pre-commit run --files"),
    ("pr_4", "All new unit tests pass"),
])
def test_test_lines_still_dropped(pr, fragment):
    kept = b._drop_test_sections(b._clean(BODIES[pr]))
    s = _sentence_with(kept, fragment)
    assert s is None or b.about_tests_or_tools(s)


def test_section_ends_at_label_line_details_fixes_and_prose():
    for stop in ["- **Behavior**:", "<details>", "Fixes #12", "The parser now keeps comments."]:
        body = f"## Testing\n- `pytest -q`\n\n{stop}\n- Values are unchanged for floats"
        kept = b._drop_test_sections(body)
        assert "pytest" not in kept and "Values are unchanged for floats" in kept, stop


def test_nothing_else_changes_kept_inside_test_section():
    kept = b._drop_test_sections("## Testing\n- `pytest -q`\n- Other providers remain unaffected\n")
    assert "Other providers remain unaffected" in kept
    kept = b._drop_test_sections("## Testing\n- old test suite results unchanged\n")
    assert "unchanged" not in kept


def test_tool_word_needs_run_pass_or_fail():
    assert b.about_tests_or_tools("ruff check passes")
    assert b.about_tests_or_tools("Linting passes with no issues")
    assert b.about_tests_or_tools("mypy output is identical")
    assert not b.about_tests_or_tools("extend linter Fix to support creating files")
    assert not b.about_tests_or_tools("The linter now accepts empty config files")


def test_lint_workflow_and_linting_rules_sentences_kept():
    # Two product sentences from unseen pull requests: the product here is the project's own lint setup.
    assert not b.about_tests_or_tools(
        "The lint workflow was running `dev/check_function_signatures.py` on both Ubuntu and macOS matrix entries, "
        "producing duplicate warnings since the function signature comparison logic is identical regardless of "
        "operating system")
    assert not b.about_tests_or_tools("keep `tools/check_env_table.py` aligned with linting rules")
    assert not b.about_tests_or_tools("Run ruff only once in `.github/workflows/lint.yml`")
    assert b.about_tests_or_tools("ruff check passes")


def test_unindented_wrapped_list_line_ends_test_section():
    # Known limit, fails safe: the wrapped tail and anything after it are kept, not dropped.
    kept = b._drop_test_sections("## Testing\n- `pytest -q` on the parser\nsuite with defaults\n- `ruff check`\n")
    assert "pytest" not in kept
    assert "suite with defaults" in kept and "ruff check" in kept
