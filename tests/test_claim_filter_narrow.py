"""The test/tool filter must not swallow product sentences (2026-10-15 decision).

The 17 sentences below were wrongly dropped by the first version of the filter on four pull-request
descriptions (these four were used to tune this narrower rule, so they are regressions, not held-out cases).
They describe the product change, the bug, or that nothing else changes, so they must reach the claim extractor."""
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


def _passing_comparison():
    from ops.daily_run import compare_sides
    passed = {"t::a": ("passed", ""), "t::b": ("passed", "")}
    return compare_sides({"main": [passed] * 3, "pr": [passed] * 3})


def _kept_unchanged_claim():
    """A behaviour sentence written after a test list. The narrower filter keeps it, so it is a real claim."""
    body = "## Testing\n- `pytest -q`\n\nResults are unchanged for existing callers."
    claims = b.find("Keep the parser", body)
    assert len(claims) == 1 and claims[0]["pattern"] == "unchanged"
    assert claims[0]["quote"] == "Results are unchanged for existing callers."
    return claims


_SAME = [{"id": "C1", "text": "results unchanged", "covers": ["r"], "expect": "same"}]
_STALE_COVERAGE = {"status": "measured", "changed_lines_total": 4, "changed_lines_covered": 2,
                   "adequacy": "adequate"}


def test_kept_claim_whose_only_probe_crashed_is_not_verified():
    """The filter keeps the promise, and a crashed probe must not turn that promise into 'verified'."""
    from ops.daily_run import verdict_for
    from poc import probes

    claims = _kept_unchanged_claim()
    err = probes.PROBE_ERROR
    item = probes.classify_item({
        "id": "model-x", "source": "model", "claims": _SAME,
        "runs": {"main": [{err: {"crash": "boom"}}] * 3, "pr": [{err: {"crash": "boom"}}] * 3},
        "observations": [{"name": err, "state": "same", "label": "not_testable",
                          "main": {"crash": "boom"}, "pr": {"crash": "boom"}}],
        "probe_changed_line_coverage": dict(_STALE_COVERAGE),
    })
    assert item["status"] == "crashed"
    assert item["probe_changed_line_coverage"]["changed_lines_covered"] == 0
    assert not b.probe_covers({"items": [item]})
    v, reason, _ = verdict_for(_passing_comparison(), None, probe_results={"items": [item]}, claims=claims)
    assert v == "could_not_verify"
    assert reason.startswith('unverified behaviour claim: "Results are unchanged for existing callers."')


@pytest.mark.parametrize("status", ["crashed", "error", "uninformative", "not_run"])
def test_stale_coverage_on_a_probe_that_did_not_run_does_not_verify(status):
    """A coverage block left over from before the crash still does not check the claim."""
    from ops.daily_run import verdict_for

    claims = _kept_unchanged_claim()
    item = {"id": "model-x", "source": "model", "status": status, "claims": _SAME,
            "observations": [{"name": "r", "state": "same", "label": "proven", "claim": "C1", "main": 1, "pr": 1}],
            "probe_changed_line_coverage": dict(_STALE_COVERAGE)}
    assert not b.probe_covers({"items": [item]})
    v, reason, _ = verdict_for(_passing_comparison(), None, probe_results={"items": [item]}, claims=claims)
    assert v == "could_not_verify" and "unverified behaviour claim" in reason


def test_kept_claim_with_a_probe_that_ran_a_changed_line_is_verified():
    from ops.daily_run import verdict_for

    claims = _kept_unchanged_claim()
    item = {"id": "model-x", "source": "model", "status": "ran", "claims": _SAME,
            "observations": [{"name": "r", "state": "same", "label": "proven", "claim": "C1", "main": 1, "pr": 1}],
            "probe_changed_line_coverage": dict(_STALE_COVERAGE)}
    assert b.probe_covers({"items": [item]})
    assert verdict_for(_passing_comparison(), None, probe_results={"items": [item]}, claims=claims)[0] == "verified"


def test_measured_zero_covered_lines_do_not_check_a_kept_claim():
    from ops.daily_run import verdict_for

    claims = _kept_unchanged_claim()
    item = {"id": "model-x", "source": "model", "status": "ran", "claims": _SAME,
            "observations": [{"name": "r", "state": "same", "label": "proven", "claim": "C1", "main": 1, "pr": 1}],
            "probe_changed_line_coverage": {"status": "measured", "changed_lines_total": 4,
                                            "changed_lines_covered": 0, "adequacy": "adequate"}}
    assert not b.probe_covers({"items": [item]})
    v, reason, _ = verdict_for(_passing_comparison(), None, probe_results={"items": [item]}, claims=claims)
    assert v == "could_not_verify" and "unverified behaviour claim" in reason


def test_empty_probe_from_the_runner_does_not_cover_a_kept_claim():
    """No observations is the runner's empty probe. It covers nothing, even with a leftover adequate count."""
    from ops.daily_run import verdict_for
    from poc import probes

    claims = _kept_unchanged_claim()
    item = probes.classify_item({
        "id": "model-x", "source": "model", "claims": _SAME,
        "runs": {"main": [], "pr": []}, "observations": [],
        "probe_changed_line_coverage": dict(_STALE_COVERAGE),
    })
    assert item["status"] == "error"
    assert item["probe_changed_line_coverage"]["changed_lines_covered"] == 0
    assert not b.probe_covers({"items": [item]})
    v, reason, _ = verdict_for(_passing_comparison(), None, probe_results={"items": [item]}, claims=claims)
    assert v == "could_not_verify" and "unverified behaviour claim" in reason


def test_console_and_swarm_share_the_verdict_code(tmp_path, monkeypatch):
    """The console launches the same check that decides the verdict. The swarm runs after that verdict is stored
    and does not replace it, including a could-not-verify from a crashed probe."""
    import io
    import os

    from ops import daily_run
    from poc import agents, console_api, model_provider

    assert "probe_covers" in daily_run.verdict_for.__code__.co_names
    assert "verdict_for" in daily_run._store_verdict.__code__.co_names
    assert "run_swarm" in daily_run.finish.__code__.co_names
    assert "verdict_for" not in daily_run.finish.__code__.co_names
    assert "probe_covers" not in daily_run.finish.__code__.co_names
    assert "verdict_for" not in agents.run_swarm.__code__.co_names
    assert "probe_covers" not in agents.run_swarm.__code__.co_names

    claims = _kept_unchanged_claim()
    item = {"id": "model-x", "source": "model", "status": "crashed", "claims": _SAME,
            "observations": [], "probe_changed_line_coverage": dict(_STALE_COVERAGE)}
    v, reason, _ = daily_run.verdict_for(
        _passing_comparison(), None, probe_results={"items": [item]}, claims=claims)
    assert v == "could_not_verify"

    class Stub(model_provider.Provider):
        name = "recorded"
        blind = False

        def complete_json(self, task, system, user, schema, ctx):
            if task == "judge":
                return {"labels": []}
            if task == "helper":
                return {"notes": []}
            return {"text": "Verdict stays with the check.", "quotes": []}

    rec = {"verdict": v, "reason": reason, "repo": "me/demo", "pr": {"number": 3, "title": "Keep the parser"},
           "files": {"package_py": [], "compiled": [], "other": []}, "per_run": [], "baseline": "full"}
    monkeypatch.setattr(daily_run, "check_record", lambda record: [])
    # The swarm is off unless this run asks for it. Asking still runs it only after the verdict, and it
    # must not replace a could-not-verify that came from a crashed probe.
    runner = type("Runner", (), {"provider": Stub(), "model_skipped": None, "swarm": True})()
    daily_run.finish(rec, tmp_path, tmp_path / "work", 0.0, runner)
    assert rec["verdict"] == v and rec["reason"] == reason
    assert rec["agents"]["advisory"] is True

    captured = {}

    class FakeProc:
        def __init__(self):
            self.stdout = io.StringIO("")

        def wait(self):
            return 0

    def fake_popen(argv, **kwargs):
        captured["argv"] = list(argv)
        return FakeProc()

    class ImmediateThread:
        def __init__(self, target=None, daemon=None):
            self.target = target

        def start(self):
            self.target()

    root = tmp_path / "repo"
    (root / "ops").mkdir(parents=True)
    (root / "ops" / "daily_run.py").write_text("# stub\n")
    monkeypatch.setattr(console_api, "REPO_ROOT", root)
    monkeypatch.setattr(console_api.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(console_api.threading, "Thread", ImmediateThread)
    monkeypatch.setattr(console_api, "console_run_flags", lambda: console_api.ConsoleRunPlan([], None, False, None))
    monkeypatch.setattr(console_api, "find_record_for_pr", lambda repo, pr: None)
    saved = {k: os.environ.get(k) for k in ("POC_HITL", "POC_HITL_DIR", "POC_PROGRESS_PATH")}
    try:
        job = console_api.start_check("https://github.com/me/demo/pull/3", model_provider="recorded")
    finally:
        for key, val in saved.items():
            if val is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = val
    argv = captured["argv"]
    assert any(str(part).endswith("ops/daily_run.py") for part in argv)
    assert "--pr" in argv and "https://github.com/me/demo/pull/3" in argv
    assert job["status"] == "done"
