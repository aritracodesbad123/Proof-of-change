"""Day-10 monitor fixes: empty collection, report self-check, quote marks, the PR title, wording, and probe reach.

Offline. No live model, search, or pull-request rerun.
"""
import json
from types import SimpleNamespace

import pytest

from ops import daily_run as dr
from poc import coverage_gate, demo_helper, model_probes, probe_reach, probes
from reports import pr_report

DIFF = """\
diff --git a/pkg/_mod.py b/pkg/_mod.py
--- a/pkg/_mod.py
+++ b/pkg/_mod.py
@@ -1,4 +1,4 @@ class FileSink
 class FileSink:
     def __init__(self, path, **kwargs):
-        self._fn = self._make_rotation_function(rotation)
+        self._fn = self._make_rotation_function(rotation, kwargs.get("newline"))
@@ -8,3 +8,3 @@ def _make_rotation_function
-    def _make_rotation_function(rotation):
+    def _make_rotation_function(rotation, newline=None):
         return None
"""

P = ("passed", "")
E = ("load_error", "collection failure")


def _verified_cmp():
    same = {"t::a": P}
    return dr.compare_sides({"main": [same] * 3, "pr": [same] * 3})


def _flagged_probe():
    spec = {"id": "p1", "target": "o/r#1", "about": "x", "claims": []}
    item = probes.entry(spec, {"main": [{"c": 1}] * 3, "pr": [{"c": 2}] * 3}, None, [], "model", None)
    item["probe_changed_line_coverage"] = {"status": "measured", "changed_lines_total": 2,
                                           "changed_lines_covered": 1, "adequacy": "adequate"}
    return {"status": "ran", "items": [item]}


# ---------------------------------------------------------------- (52) empty collection
def test_52_nothing_collected_on_both_sides_stays_could_not_verify():
    reason = "tests produced no results on both sides (collection failed; see pytest logs)"
    v, text, _ = dr.verdict_for(None, reason, probe_results=_flagged_probe())
    assert v == "could_not_verify"
    assert "no results on both sides" in text


def test_52_collection_errors_only_on_both_sides_stay_could_not_verify():
    res = {"main": [{"::pkg.tests.test_mod": E}] * 3, "pr": [{"::pkg.tests.test_mod": E}] * 3}
    cmp = dr.compare_sides(res)
    v, text, _ = dr.verdict_for(cmp, None, probe_results=_flagged_probe())
    assert cmp["executed"] == {"main": 0, "pr": 0}
    assert v == "could_not_verify"
    assert "no test actually ran" in text


def test_52_a_mapped_gap_can_still_be_raised_by_a_probe():
    """Collecting nothing is the exception. A different could-not-verify reason still takes a probe finding."""
    v, text, _ = dr.verdict_for(None, "no tests could be mapped to the touched modules", probe_results=_flagged_probe())
    assert v == "needs_attention" and "tests: no tests could be mapped" in text


def test_52_skipped_tests_were_collected_and_a_probe_can_still_flag():
    skipped = {"t::a": ("skipped", "nope")}
    cmp = dr.compare_sides({"main": [skipped] * 3, "pr": [skipped] * 3})
    v, _, _ = dr.verdict_for(cmp, None, probe_results=_flagged_probe())
    assert v == "needs_attention"


# ---------------------------------------------------------------- (53) self-check
def _record(folder_ready, verdict, **extra):
    rec = {"pr": {"repo": "Delgan/loguru", "number": 1536, "title": "Count bytes",
                  "url": "https://example.com/pull/1536", "head_sha": "a" * 40, "base_sha": "b" * 40},
           "repo": "Delgan/loguru", "library": "loguru", "verdict": verdict, "reason": "because",
           "poc_commit": "c" * 40, "route": "source-pair", "tested_at_ist": "t",
           "files": {"package_py": ["loguru/_file_sink.py"], "compiled": [], "other": [], "all": ["loguru/_file_sink.py"]},
           "machine_type": {"label": "t", "arch": "x", "cpu_count": 1}, "thread_env": {},
           "runs_per_side": 3, "posted_upstream": False,
           "per_run": [{"side": s, "run": i, "exit": 0} for i in (1, 2, 3) for s in ("main", "pr")],
           "coverage_gate": {"kind": "python", "changed": False, "confidence": "normal", "note": "n",
                             "measurement": "not measured"}}
    rec.update(extra)
    (folder_ready / "record.json").write_text(json.dumps(rec))
    return rec


def test_53_self_check_fails_when_the_report_disagrees(tmp_path):
    run = tmp_path / "run"
    d = run / "loguru-1536"
    d.mkdir(parents=True)
    _record(d, "needs_attention", exit_check={"explained": False, "problems": ["main run 1: pytest exit 4"],
                                              "detail": "pytest exit 4"},
            per_run=[{"side": s, "run": i, "exit": 4} for i in (1, 2, 3) for s in ("main", "pr")])
    with pytest.raises(pr_report.VerdictMismatch) as caught:
        pr_report.render_run(run, tmp_path / "out", formats=("md", "html"))
    text = str(caught.value)
    assert "NEEDS ATTENTION" in text and "COULD NOT VERIFY" in text


def test_53_daily_summary_and_per_pr_section_must_match_the_record():
    md = "\n".join([
        "| [Delgan/loguru#1536](https://example.com) | Count bytes | source-pair | **needs_attention** | because |",
        "",
        "### Delgan/loguru#1536: Count bytes",
        "",
        "- **Verdict: could_not_verify**: because",
        "",
    ])
    rec = {"repo": "Delgan/loguru", "pr": {"number": 1536}, "verdict": "needs_attention", "reason": "because"}
    audit = demo_helper.check_report([rec], md)
    assert audit["ok"] is False
    assert any("per-PR report shows could_not_verify" in item for item in audit["mismatches"])


# ---------------------------------------------------------------- (54) quote marks
def test_54_straight_backtick_and_curly_quotes_match():
    body = 'The output for the reported input is unchanged (`"( AS )"`).'
    quote = "The output for the reported input is unchanged ('( AS )')."
    raw = {"claims": [{"id": "C1", "expect": "differs", "source_quote": quote}]}
    kept, rejected = model_probes.grounded_claims(raw, "Don't raise IndexError", body, loose=True)
    assert rejected == [] and kept[0]["quote_match"] == "loose"
    curly = "The output for the reported input is unchanged (\u201c( AS )\u201d)."
    assert model_probes.loose_norm(curly) == model_probes.loose_norm(quote)
    assert model_probes.loose_norm("`keep` this") == model_probes.loose_norm("keep this")
    raw = {"claims": [{"id": "C1", "expect": "differs", "source_quote": "foo now returns 2 for good"}]}
    assert model_probes.grounded_claims(raw, "t", "foo now returns `3` for good", loose=True)[0] == []


# ---------------------------------------------------------------- (55) title claim
def test_55_dont_raise_in_the_title_covers_main_raises_pr_returns():
    title = "Don't raise IndexError on short parenthesis groups"
    spec = {"id": "p1", "target": "o/r#1", "about": "x", "claims": []}
    runs = {"main": [{"out": {"raises": "IndexError"}, "other": 1}] * 3,
            "pr": [{"out": "( AS )", "other": 2}] * 3}
    item = probes.entry(spec, runs, None, [], "model", None)
    labels = {o["name"]: o["label"] for o in item["observations"]}
    assert labels["out"] == "unmentioned" and labels["other"] == "unmentioned"
    settled = probes.apply_title_claim({"status": "ran", "items": [item]}, title)
    by_name = {o["name"]: o for o in settled["items"][0]["observations"]}
    assert by_name["out"]["label"] == "proven" and by_name["out"]["claim"] == "title"
    assert by_name["other"]["label"] == "unmentioned"
    covered = probes.apply_title_claim(
        {"status": "ran", "items": [probes.entry(spec, {"main": [{"out": {"raises": "IndexError"}}] * 3,
                                                       "pr": [{"out": "( AS )"}] * 3}, None, [], "model", None)]},
        title)
    v, _, _ = dr.verdict_for(_verified_cmp(), None, probe_results=probes.apply_status(covered))
    assert v == "verified"
    assert probes.dont_raise_names("Do not raise ValueError or TypeError here") == ["ValueError", "TypeError"]


# ---------------------------------------------------------------- (56) wording and coverage note
def test_56_both_sides_when_both_collected_nothing():
    rec = {}
    a = SimpleNamespace(run_timeout=30)
    _cmp, reason, _ex = dr.finalize_tests(rec, [], {"main": [{}], "pr": [{}]}, a)
    assert "both sides" in reason and "one side" not in reason
    _cmp, reason, _ex = dr.finalize_tests(rec, [], {"main": [{"t::a": P}], "pr": [{}]}, a)
    assert "one side" in reason


def test_56_a_new_record_does_not_say_it_predates_the_coverage_gate():
    item = {"pr": 1, "title": "t", "url": "u", "author": "a", "head_sha": "a" * 40, "base_sha": "b" * 40,
            "base_ref": "main", "updated_at_utc": "2026-10-31T00:00:00Z", "updated_at_ist": "i",
            "ci_state": "none", "ci_detail": "-", "files": {"all": ["pkg/a.py"], "package_py": ["pkg/a.py"],
                                                            "compiled": [], "other": []}}
    a = SimpleNamespace(runs=1, workers="0", test_timeout=1, run_timeout=1, build_timeout=1, python="3.12",
                        poc_commit="c" * 40, baseline="full")
    rec = dr.new_record("acme/pkg", {"dist": "pkg", "pkg": "pkg", "nightly": False}, item, a, {"arch": "x"}, "2026-10-31")
    rec["verdict"], rec["reason"] = "could_not_verify", "tests produced no results on both sides"
    note = coverage_gate.apply(rec)["coverage_gate"]["note"]
    assert "predates the coverage gate" not in note
    assert "NOT MEASURED" in note and "has not been run" in note


# ---------------------------------------------------------------- (57) (58) reach
def test_57_internal_helper_without_the_new_argument_cannot_reach_the_change():
    bad = "FileSink._make_rotation_function(10)\n"
    ok_arg = "FileSink._make_rotation_function(10, newline='\\n')\n"
    public = "sink = FileSink('p')\n"
    both = "FileSink._make_rotation_function(10)\nsink = FileSink('p')\n"
    assert "unable to reach the change" in probe_reach.unable_to_reach(bad, DIFF)
    assert "`newline`" in probe_reach.unable_to_reach(bad, DIFF)
    assert probe_reach.unable_to_reach(ok_arg, DIFF) is None
    assert probe_reach.unable_to_reach(public, DIFF) is None
    assert probe_reach.unable_to_reach(both, DIFF) is None


def test_58_a_differs_claim_on_agreeing_inputs_is_could_not_verify_not_needs_attention():
    spec = {"id": "p1", "target": "o/r#1", "about": "x", "claims": [
        {"id": "C1", "text": "the result differs", "covers": ["out"], "expect": "differs"}]}
    item = probes.entry(spec, {"main": [{"out": 1}] * 3, "pr": [{"out": 1}] * 3}, None, [], "model", None)
    assert item["observations"][0]["label"] == "needs_human"
    item["probe_changed_line_coverage"] = {"status": "measured", "changed_lines_total": 2,
                                           "changed_lines_covered": 1, "adequacy": "adequate"}
    reached = {"status": "ran", "items": [item]}
    assert dr.verdict_for(_verified_cmp(), None, probe_results=reached)[0] == "needs_attention"
    missed = {"status": "ran", "items": [dict(item, unable_to_reach=(
        "unable to reach the change: calls `_make_rotation_function` without the new argument `newline`, "
        "and does not go through a public entry point"))]}
    v, reason, _ = dr.verdict_for(_verified_cmp(), None, probe_results=missed)
    assert v == "could_not_verify"
    assert "both sides agree" in reason and "C1" in reason
    # A real difference is still needs attention, and the reach note is shown.
    differed = probes.entry({"id": "p1", "target": "o/r#1", "about": "x", "claims": []},
                            {"main": [{"out": 1}] * 3, "pr": [{"out": 2}] * 3}, None, [], "model", None)
    differed["unable_to_reach"] = missed["items"][0]["unable_to_reach"]
    differed["probe_changed_line_coverage"] = item["probe_changed_line_coverage"]
    v, reason, _ = dr.verdict_for(_verified_cmp(), None, probe_results={"status": "ran", "items": [differed]})
    assert v == "needs_attention" and "unable to reach the change" in reason


def test_57_settle_reads_the_probe_and_the_saved_diff(tmp_path):
    (tmp_path / "pr.diff").write_text(DIFF)
    probe = tmp_path / "p1.py"
    probe.write_text("FileSink._make_rotation_function(10)\n")
    spec = {"id": "p1", "target": "o/r#1", "about": "x", "claims": [
        {"id": "C1", "text": "the result differs", "covers": ["out"], "expect": "differs"}]}
    item = probes.entry(spec, {"main": [{"out": 1}] * 3, "pr": [{"out": 1}] * 3}, None, [], "model", probe)
    rec = {"probes": {"status": "ran", "items": [item]}, "pr": {"title": "Count bytes"}, "product_check": False}
    dr.settle_probes(rec, tmp_path)
    assert rec["probes"]["items"][0]["unable_to_reach"].startswith("unable to reach the change")


# ---------------------------------------------------------------- item 9
def test_source_json_carries_both_shas_and_the_tool_commit(tmp_path):
    run = tmp_path / "run"
    d = run / "loguru-1536"
    d.mkdir(parents=True)
    _record(d, "could_not_verify")
    pr_report.render_run(run, tmp_path / "out", formats=("md", "html"))
    src = json.loads((tmp_path / "out" / "loguru-1536" / "SOURCE.json").read_text())
    assert src["head_sha"] == "a" * 40
    assert src["base_sha"] == "b" * 40
    assert src["main_sha"] == "b" * 40
    assert src["tool_commit"] == "c" * 40
    assert "run_dir" in src and "formats" in src
