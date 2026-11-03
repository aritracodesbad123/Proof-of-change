"""The chosen-PRs reader understands `## N. owner/name #N`, and an empty file does not fall back to a search."""
import json
from pathlib import Path

from ops import daily_run

HEADING = Path(__file__).parent / "fixtures" / "chosen" / "heading.md"


def test_heading_names_the_repository_and_the_pull_request():
    chosen = daily_run.parse_chosen(HEADING)
    assert "expected" not in json.dumps(chosen).lower()
    pytest_pr = chosen["pytest-dev/pytest"][0]
    assert pytest_pr["pr"] == 13764
    assert pytest_pr["head_sha"].startswith("0123")
    assert pytest_pr["install"] == "pip install -e ."
    assert daily_run.chosen_test_targets(pytest_pr) == ["testing/test_parse.py"]
    barcode = chosen["WhyNotHugo/python-barcode"][0]
    assert barcode["pr"] == 188 and barcode["head_sha"] is None
    attrs = chosen["python-attrs/attrs"][0]
    assert attrs["pr"] == 1647 and attrs["head_sha"] == "a" * 40
    exp = daily_run.read_expectations(HEADING)
    assert exp[("pytest-dev/pytest", 13764)] == "needs_attention"
    assert exp[("python-attrs/attrs", 1647)] == "verified"
    assert ("WhyNotHugo/python-barcode", 188) not in exp


def test_heading_number_is_not_repeated_when_the_line_names_it(tmp_path):
    p = tmp_path / "c.md"
    p.write_text("## 1. acme/widget #12\n- **Open PR:** #12, \"same\"\n")
    assert [row["pr"] for row in daily_run.parse_chosen(p)["acme/widget"]] == [12]


def test_present_file_with_no_pull_request_does_not_fall_back(tmp_path):
    empty = tmp_path / "day.md"
    empty.write_text("# note\n\n## 1. demo\n- no repository and no number\n")
    assert daily_run.parse_chosen(empty) == {}
    stop = daily_run.empty_chosen_stop(empty, {})
    assert stop and "will not look for other open pull requests" in stop
    assert daily_run.empty_chosen_stop(tmp_path / "missing.md", {}) is None
    good = tmp_path / "good.md"
    good.write_text("## 1. acme/widget #4\n")
    chosen = daily_run.parse_chosen(good)
    assert chosen["acme/widget"][0]["pr"] == 4
    assert daily_run.empty_chosen_stop(good, chosen) is None


def test_library_with_no_pull_request_is_named_in_the_report(tmp_path):
    why = daily_run.no_pull_request_reason(in_file=False, file_present=True, skipped=[], frozen=False)
    assert why == ("no pull request was checked: the chosen-PRs file does not name this library, "
                   "and no open pull request was found")
    set_aside = daily_run.no_pull_request_reason(
        in_file=False, file_present=False, skipped=[{"why": "draft"}, {"why": "draft"}], frozen=False)
    assert set_aside == "no pull request was checked: every candidate was set aside (draft)"
    meta = {"date": "2026-11-03", "started_ist": "s", "finished_ist": "f", "wall_min": 1, "runs": 3,
            "machine": "m", "api_calls": 0, "auth": "none"}
    md = daily_run.write_report(tmp_path, meta, [], {}, [], no_prs=[
        {"repo": "pytest-dev/pytest", "why": why}]).read_text()
    assert "## Libraries with no pull request" in md
    assert f"- pytest-dev/pytest: {why}" in md
