"""Evidence report. Every results folder here is FIXTURE data (SAMPLE), not a benchmark result.

The report is built only from those labelled files. It must not invent a field, must redact secrets, and
the decision line must repeat the recorded verdict for every verdict type.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from bench import report, run, summarize

BASE = "3" * 40
HEAD = "4" * 40
MERGE = "e" * 40
PR = "https://github.com/pytoolz/toolz/pull/1"
FORK_PR = "https://github.com/someone/toolz/pull/7"
SCHEMA = "poc-bench-result/1"
HEDGE = ("probably", "likely", "looks good", "safe to", "acceptable")
VERDICTS = ("verified", "needs_attention", "could_not_verify", "no_code_change")


@pytest.fixture(autouse=True)
def _no_keys(monkeypatch):
    for key in run.SECRET_NAMES:
        monkeypatch.delenv(key, raising=False)


def probe_item(main_vals=(1, 1, 1), pr_vals=(2, 2, 2), label="unmentioned", state="differs", name="held_obs"):
    """FIXTURE probe record: three runs per side, values under one observation name."""
    return {
        "id": "probe-a", "runs_per_side": 3, "per_run": [{"ok": True}] * 6,
        "runs": {"main": [{name: v} for v in main_vals], "pr": [{name: v} for v in pr_vals]},
        "observations": [{"name": name, "state": state, "label": label}],
    }


def arm_result(cid, category, arm, verdict, *, outcome="ran", reason=None, fixture=True, expected=None, **extra):
    """One FIXTURE arm result in the shape bench.run writes."""
    if expected is None:
        expected = {"known_safe": "verified", "setup_failure": "could_not_verify"}.get(category, "needs_attention")
    row = {
        "schema": SCHEMA, "case_id": cid, "arm": arm, "fixture": fixture, "category": category,
        "expected_verdict": expected, "outcome": outcome,
        "verdict": verdict if outcome == "ran" else None,
        "reason": reason if reason is not None else f"recorded reason for {verdict}",
        "stages": {"infra": "ok", "install": "ok", "tests": "ran", "probes": "ran" if "probes" in arm else "off"},
        "wall_seconds": 12.5, "check_duration_s": {"total_wall": 11.0},
        "model": {"ai_calls": 4 if "probes" in arm else 0, "failed_ai_calls": 0, "input_tokens": 20,
                  "output_tokens": 8, "cost_usd": 0.02 if "probes" in arm else 0.0, "provider": "nebius" if "probes" in arm else "none"},
        "tested": {"base_sha": BASE, "pr_sha": HEAD, "head_sha": HEAD, "pr_side": "head"},
        "command": ["python", "--pr", PR, "--product-check"],
        "probe_held_all_runs": True if "probes" in arm else None,
    }
    row.update(extra)
    return row


def write_run(root: Path, cases: list[dict], arms: dict[str, list[dict]], env=None):
    """Write FIXTURE run_meta.json and arm JSON files. A case with no file is left missing on purpose."""
    meta = {
        "environment": env or {
            "harness_commit": "abc123", "started_ist": "2026-10-22 12:00 IST", "python": "3.12.0",
            "platform": "Linux", "sandbox_backend": "contree", "POC_REQUIRE_CONTREE": "1",
            "keys": {"NEBIUS_API_KEY": "unset"},
        },
        "arms": {arm: [] for arm in arms},
        "cases": [{"id": c["id"], "category": c["category"], "expected_verdict": c["expected_verdict"],
                   "fixture": c.get("fixture", True)} for c in cases],
    }
    (root / "run_meta.json").write_text(json.dumps(meta))
    for arm, rows in arms.items():
        folder = root / arm.replace("+", "_")
        folder.mkdir(parents=True, exist_ok=True)
        for row in rows:
            (folder / f"{row['case_id']}.json").write_text(json.dumps(row))


def write_record(root: Path, arm: str, cid: str, record: dict, slug="toolz-1"):
    folder = root / "ops" / arm.replace("+", "_") / "runs" / f"bench-{cid}" / slug
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "record.json").write_text(json.dumps(record))


def render(root: Path) -> tuple[str, str]:
    md_path, html_path = report.write_report(root)
    return md_path.read_text(), html_path.read_text()


def case_block(md: str, cid: str) -> str:
    token = f"## Case {cid}"
    start = md.index(token)
    rest = md[start + len(token):]
    nxt = rest.find("\n## Case ")
    return rest if nxt < 0 else rest[:nxt]


def section(block: str, heading: str) -> str:
    token = f"### {heading}"
    start = block.index(token)
    rest = block[start + len(token):]
    nxt = rest.find("\n### ")
    return rest if nxt < 0 else rest[:nxt]


def decision_of(block: str) -> str:
    for line in block.splitlines():
        if line.startswith("Decision:"):
            return line
    raise AssertionError("no decision line")


def test_decision_line_is_the_recorded_verdict_only():
    for verdict in VERDICTS:
        line = report.decision_line({"tests": {"outcome": "ran", "verdict": verdict, "reason": "probably looks good"}})
        assert line == f"Decision: tests={verdict}."
        assert not any(word in line.lower() for word in HEDGE)
    assert report.decision_line({"tests": {"outcome": "not_run", "verdict": "verified"}}) == "Decision: tests=not_run."
    assert report.verdict_token({"outcome": "ran", "verdict": "maybe"}) == report.MISSING
    assert report.verdict_token({}) == report.MISSING
    both = report.decision_line({
        "tests": {"outcome": "ran", "verdict": "verified"},
        "tests+probes": {"outcome": "ran", "verdict": "needs_attention"},
        "tests+probes+swarm": {"outcome": "ran", "verdict": "verified"},
    })
    assert both == "Decision: tests=verified; tests+probes=needs_attention."
    assert "swarm" not in both


@pytest.mark.parametrize("verdict, category, expected", [
    ("verified", "known_safe", "verified"),
    ("needs_attention", "known_regression_tests_catch", "needs_attention"),
    ("could_not_verify", "setup_failure", "could_not_verify"),
    ("no_code_change", "ambiguous", "no_code_change"),
])
def test_written_decision_line_matches_each_verdict(tmp_path, verdict, category, expected):
    cid = f"v-{verdict}"
    row = arm_result(cid, category, "tests", verdict, expected=expected, fixture=True)
    write_run(tmp_path, [{"id": cid, "category": category, "expected_verdict": expected}], {"tests": [row]})
    md, page = render(tmp_path)
    line = decision_of(case_block(md, cid))
    assert line == f"Decision: tests={verdict}."
    assert line in page
    assert "\n" not in line
    assert "SAMPLE" in md and "SAMPLE" in page
    assert "FIXTURE DATA" in md and "FIXTURE DATA" in page


def test_not_run_and_a_leftover_verdict_stay_not_run(tmp_path):
    present = arm_result("kept", "known_safe", "tests", "verified", expected="verified")
    leftover = arm_result("stale", "known_safe", "tests", "verified", outcome="not_run", expected="verified",
                          not_run_why=["no usable record (exit 3)"], reason="should not become the decision")
    cases = [
        {"id": "kept", "category": "known_safe", "expected_verdict": "verified"},
        {"id": "stale", "category": "known_safe", "expected_verdict": "verified"},
        {"id": "missing", "category": "known_regression_tests_miss", "expected_verdict": "needs_attention"},
    ]
    write_run(tmp_path, cases, {"tests": [present, leftover]})
    md, page = render(tmp_path)
    assert decision_of(case_block(md, "stale")) == "Decision: tests=not_run."
    assert "verified" not in decision_of(case_block(md, "stale"))
    assert "no usable record (exit 3)" in section(case_block(md, "stale"), "Unverified / not run")
    missing = case_block(md, "missing")
    assert decision_of(missing) == "Decision: tests=not_run."
    assert "no result file" in section(missing, "Unverified / not run")
    assert decision_of(missing) in page


def test_two_arms_keep_the_verdict_when_model_text_disagrees(tmp_path):
    tests = arm_result("both", "known_regression_tests_miss", "tests", "needs_attention", expected="needs_attention")
    probes = arm_result("both", "known_regression_tests_miss", "tests+probes", "needs_attention", expected="needs_attention")
    swarm = arm_result("both", "known_regression_tests_miss", "tests+probes+swarm", "verified", expected="needs_attention",
                       reason="advisory arm recorded a different verdict")
    meta = [{"id": "both", "category": "known_regression_tests_miss", "expected_verdict": "needs_attention"}]
    write_run(tmp_path, meta, {"tests": [tests], "tests+probes": [probes], "tests+probes+swarm": [swarm]})
    fail = "tests/test_sample.py::test_breaks"
    write_record(tmp_path, "tests", "both", {
        "verdict": "needs_attention", "reason": "1 test(s) pass on main but fail on the PR", "repo": "pytoolz/toolz",
        "pr": {"url": PR, "repo": "pytoolz/toolz"},
        "comparison": {"regressions": [], "new_tests_failing": [], "pr_unstable": [], "flaky": [], "executed": {"main": 3, "pr": 3}},
        "probes": {"status": "off", "items": []},
    })
    write_record(tmp_path, "tests+probes", "both", {
        "verdict": "needs_attention", "reason": "probe: 1 observation(s) need attention", "repo": "pytoolz/toolz",
        "pr": {"url": PR, "repo": "pytoolz/toolz"},
        "comparison": {"regressions": [fail], "new_tests_failing": [], "pr_unstable": [],
                       "flaky": ["tests/test_sample.py::test_flaky"], "pr_unstable_noisy": [],
                       "executed": {"main": 3, "pr": 3}, "messages": {fail: "AssertionError: expected 2"}},
        "probes": {"status": "ran", "items": [probe_item()]},
        "explanation": {"status": "wired", "text": "model-text-marker-zzz probably fine and looks good", "advisory": True},
        "swarm": "off",
    })
    write_record(tmp_path, "tests+probes+swarm", "both", {
        "verdict": "needs_attention", "reason": "probe: 1 observation(s) need attention", "repo": "pytoolz/toolz",
        "pr": {"url": PR}, "swarm": "on",
        "agents": {"status": "ran", "note": "advisory only", "roles": [
            {"role": "helper", "status": "ok", "notes": ["swarm-note-marker-zzz"]},
        ]},
        "demo_helper": {"limitations": [{"plain": "needs a compiler", "needed": ["gcc"]}]},
    })
    md, page = render(tmp_path)
    block = case_block(md, "both")
    line = decision_of(block)
    assert line == "Decision: tests=needs_attention; tests+probes=needs_attention."
    assert "verified" not in line
    assert not any(word in line.lower() for word in HEDGE)
    verified = section(block, "Verified behaviour")
    inferred = section(block, "Inferred explanation")
    advisory = section(block, "Advisory notes")
    unverified = section(block, "Unverified / not run")
    assert "model-text-marker-zzz" not in verified
    assert "swarm-note-marker-zzz" not in verified
    assert fail in section(block, "Strongest supporting evidence")
    assert fail in verified
    assert "label unmentioned" in verified and "same value on all 3 runs of each side" in verified
    assert "main=1" in verified and "pr=2" in verified
    assert "AssertionError: expected 2" in verified
    assert "model-text-marker-zzz" in inferred and "probably fine" in inferred
    assert "Model text. Not executed evidence." in inferred
    assert "swarm-note-marker-zzz" in advisory
    assert "Advisory arm tests+probes+swarm recorded verdict: verified" in advisory
    assert "Swarm notes. Advisory only." in advisory
    assert "could-not-verify reason: none" in unverified
    assert "tests/test_sample.py::test_flaky" in unverified
    assert "needs a compiler" in unverified
    assert "pytoolz/toolz (check record)" in block
    assert PR in block and BASE in block and HEAD in block and "head" in block
    assert "wall_seconds=12.5" in block and "ai_calls=4" in block and "0.02" in block
    for heading in ("Verified behaviour", "Inferred explanation", "Advisory notes", "Unverified / not run"):
        assert f"### {heading}" in block and f"<h2>{heading}</h2>" in page
    assert line in page
    assert run.probe_held({"probes": {"items": [probe_item()]}}) is True


def test_unstable_probe_is_not_quoted_as_held(tmp_path):
    row = arm_result("shaky", "known_regression_tests_miss", "tests+probes", "needs_attention",
                     expected="needs_attention", probe_held_all_runs=False, reason="no stable probe finding")
    write_run(tmp_path, [{"id": "shaky", "category": "known_regression_tests_miss", "expected_verdict": "needs_attention"}],
              {"tests+probes": [row]})
    write_record(tmp_path, "tests+probes", "shaky", {
        "verdict": "needs_attention", "reason": "no stable probe finding", "repo": "pytoolz/toolz",
        "comparison": {"regressions": [], "new_tests_failing": [], "pr_unstable": []},
        "probes": {"items": [probe_item(main_vals=(1, 1, 3))]},
    })
    md, _page = render(tmp_path)
    verified = section(case_block(md, "shaky"), "Verified behaviour")
    assert "Probe result that held on all runs: none" in verified
    assert "same value on all 3 runs" not in verified
    assert "probe_held_all_runs: false" in verified
    assert report.held_probe_quotes({"probes": {"items": [probe_item(main_vals=(1, 1, 3))]}}) == []


def test_could_not_verify_reason_is_quoted(tmp_path):
    reason = "could not verify: install failed and no tests ran"
    row = arm_result("gap", "setup_failure", "tests", "could_not_verify", expected="could_not_verify", reason=reason,
                     stages={"infra": "ok", "install": "failed", "tests": "not_run", "probes": "not_run"})
    write_run(tmp_path, [{"id": "gap", "category": "setup_failure", "expected_verdict": "could_not_verify"}], {"tests": [row]})
    write_record(tmp_path, "tests", "gap", {"verdict": "could_not_verify", "reason": reason, "repo": "pytoolz/toolz"})
    md, _page = render(tmp_path)
    unverified = section(case_block(md, "gap"), "Unverified / not run")
    assert f"could-not-verify reason: {reason}" in unverified
    assert "install" in case_block(md, "gap") and "failed" in case_block(md, "gap")


def test_missing_fields_are_marked_not_recorded(tmp_path):
    row = {"schema": SCHEMA, "case_id": "bare", "arm": "tests", "fixture": True, "category": "ambiguous",
           "expected_verdict": "verified", "outcome": "ran", "verdict": "verified"}
    write_run(tmp_path, [{"id": "bare", "category": "ambiguous", "expected_verdict": "verified"}], {"tests": [row]})
    md, page = render(tmp_path)
    block = case_block(md, "bare")
    assert decision_of(block) == "Decision: tests=verified."
    assert "| tests | not recorded | not recorded | not recorded | not recorded | not recorded |" in block
    arm = "| tests | verified | " + " | ".join(["not recorded"] * 7) + " |"
    assert arm in block
    verified = section(block, "Verified behaviour")
    assert "Failing test names: not recorded" in verified
    assert "Probe result that held on all runs: not recorded" in verified
    assert "Recorded reason: not recorded" in verified
    assert section(block, "Inferred explanation").count("not recorded") >= 1
    assert section(block, "Advisory notes").count("not recorded") >= 1
    assert "unresolved uncertainties: not recorded" in section(block, "Unverified / not run")
    assert "not recorded" in page
    # Two records means the runner's own lookup refuses to choose one.
    write_record(tmp_path, "tests", "bare", {"reason": "first"}, slug="one")
    write_record(tmp_path, "tests", "bare", {"reason": "second"}, slug="two")
    md, _page = render(tmp_path)
    assert "Recorded reason: not recorded" in section(case_block(md, "bare"), "Verified behaviour")
    assert "first" not in md and "second" not in md


def test_repo_comes_from_the_record_and_pr_side_is_shown(tmp_path):
    row = arm_result("side", "known_safe", "tests", "verified", expected="verified",
                     tested={"base_sha": BASE, "pr_sha": MERGE, "head_sha": HEAD, "pr_side": "merge_ref"},
                     command=["python", "--pr", FORK_PR])
    write_run(tmp_path, [{"id": "side", "category": "known_safe", "expected_verdict": "verified"}], {"tests": [row]})
    write_record(tmp_path, "tests", "side", {
        "verdict": "verified", "reason": "tests agreed", "repo": "pytoolz/toolz",
        "pr": {"url": FORK_PR, "repo": "someone/toolz"},
    })
    md, page = render(tmp_path)
    block = case_block(md, "side")
    assert "pytoolz/toolz (check record)" in block
    assert FORK_PR in block and MERGE in block and "merge_ref" in block
    assert f'href="{FORK_PR}"' in page
    bare = arm_result("url-only", "known_safe", "tests", "verified", expected="verified",
                      command=["python", "--pr", PR])
    bare.pop("tested")
    write_run(tmp_path, [
        {"id": "side", "category": "known_safe", "expected_verdict": "verified"},
        {"id": "url-only", "category": "known_safe", "expected_verdict": "verified"},
    ], {"tests": [row, bare]})
    write_record(tmp_path, "tests", "side", {
        "verdict": "verified", "reason": "tests agreed", "repo": "pytoolz/toolz", "pr": {"url": FORK_PR},
    })
    md, _page = render(tmp_path)
    assert "pytoolz/toolz (recorded pull request URL)" in case_block(md, "url-only")
    assert PR in case_block(md, "url-only")


def test_summary_and_uplift_match_summarize(tmp_path):
    """The table and excluded reasons are the strings bench.summarize produces for this FIXTURE folder."""
    meta = [
        {"id": "m1", "category": "known_regression_tests_miss", "expected_verdict": "needs_attention"},
        {"id": "m2", "category": "known_regression_tests_miss", "expected_verdict": "needs_attention"},
    ]
    tests = [arm_result("m1", "known_regression_tests_miss", "tests", "verified", expected="needs_attention",
                        probe_held_all_runs=True)]
    probes = [arm_result("m1", "known_regression_tests_miss", "tests+probes", "needs_attention",
                         expected="needs_attention", probe_held_all_runs=True)]
    write_run(tmp_path, meta, {"tests": tests, "tests+probes": probes})
    md, page = render(tmp_path)
    summary = summarize.summarize(summarize.load(tmp_path))
    text = summarize.markdown(summary).strip()
    assert text in md and text in page
    assert summary["probe_uplift"]["caught_by_probes_not_tests"] == ["m1"]
    assert summary["probe_uplift"]["excluded"]["m2"] == "did not run in both arms"
    assert "| m2 | did not run in both arms |" in md
    assert "did not run in both arms" in page
    assert "count=1 n=2" in md  # bugs caught on the probes arm, n included
    assert "n=2" in md
    assert decision_of(case_block(md, "m2")) == "Decision: tests=not_run; tests+probes=not_run."


def test_a_non_fixture_run_is_not_marked_sample(tmp_path):
    row = arm_result("real", "known_safe", "tests", "verified", expected="verified", fixture=False)
    write_run(tmp_path, [{"id": "real", "category": "known_safe", "expected_verdict": "verified", "fixture": False}],
              {"tests": [row]})
    md, page = render(tmp_path)
    assert "SAMPLE" not in md and "SAMPLE" not in page
    assert "FIXTURE DATA" not in md


def test_output_is_redacted(tmp_path, monkeypatch):
    secret = "sekrit-value-123"
    monkeypatch.setenv("NEBIUS_API_KEY", secret)
    reason = f"leak {secret} in the reason"
    row = arm_result("leak", "known_safe", "tests", "verified", expected="verified", reason=reason,
                     stderr_tail=f"boom {secret}")
    row["outcome"] = "not_run"
    row["verdict"] = None
    row["not_run_why"] = [f"failed with {secret}"]
    write_run(tmp_path, [{"id": "leak", "category": "known_safe", "expected_verdict": "verified"}], {"tests": [row]})
    write_record(tmp_path, "tests", "leak", {
        "reason": reason,
        "explanation": {"text": f"model saw {secret}"},
        "agents": {"note": f"note {secret}", "roles": [{"role": "helper", "notes": [secret]}]},
    })
    md, page = render(tmp_path)
    assert secret not in md and secret not in page
    assert "sekrit" not in md and "sekrit" not in page
    assert "[NEBIUS_API_KEY redacted]" in md and "[NEBIUS_API_KEY redacted]" in page


def test_html_has_no_external_assets(tmp_path):
    nasty = '<script src="https://evil.example/a.js"></script>'
    row = arm_result("html", "known_safe", "tests", "verified", expected="verified", reason=nasty)
    write_run(tmp_path, [{"id": "html", "category": "known_safe", "expected_verdict": "verified"}], {"tests": [row]})
    _md, page = render(tmp_path)
    assert "<style>" in page and "</style>" in page
    assert "<script" not in page and "<link" not in page
    assert "fonts.googleapis" not in page and "url(" not in page
    assert not re.search(r"""<\w+[^>]*\ssrc=""", page)
    assert "&lt;script" in page
    assert report.main([str(tmp_path), "--out", str(tmp_path / "elsewhere")]) == 0
    assert (tmp_path / "elsewhere" / "evidence.md").is_file()
    assert (tmp_path / "elsewhere" / "evidence.html").is_file()

