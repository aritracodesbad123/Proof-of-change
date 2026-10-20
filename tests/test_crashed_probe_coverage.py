"""A crashed, unparsed or empty probe never counts toward changed-line coverage or 'adequate' (synthetic cases)."""
from ops import daily_run
from poc import probe_adequacy, probes

ERR = probes.PROBE_ERROR
COV = {"status": "measured", "changed_lines_total": 4, "changed_lines_covered": 2, "adequacy": "adequate"}


def _item(main_runs, pr_runs, obs, cov=COV, source="model"):
    return {"id": "model-x", "source": source, "runs": {"main": main_runs, "pr": pr_runs}, "observations": obs,
            "probe_changed_line_coverage": dict(cov)}


def _err_obs():
    return [{"name": ERR, "state": "same", "label": "not_testable", "main": {"crash": "x"}, "pr": {"crash": "x"}}]


def test_crash_on_every_main_run_is_not_adequate_and_covers_nothing():
    it = probes.classify_item(_item([{ERR: {"crash": "non-json output"}}] * 3, [{ERR: {"crash": "x"}}] * 3,
                                    _err_obs()))
    cov = it["probe_changed_line_coverage"]
    assert it["status"] == "crashed"
    assert cov["adequacy"] == "not_adequate" and cov["changed_lines_covered"] == 0 and cov["changed_lines_touched"] == 2


def test_nonzero_exit_after_output_counts_as_crash():
    runs = [{"a": 1, ERR: {"exit_code": 1}}] * 3
    it = probes.classify_item(_item(runs, runs, [{"name": "a", "state": "same", "label": "no_difference",
                                                  "main": 1, "pr": 1}]))
    assert it["status"] == "crashed"


def test_working_probe_keeps_its_coverage():
    runs = [{"a": 1}] * 3
    it = probes.classify_item(_item(runs, [{"a": 2}] * 3, [{"name": "a", "state": "differs",
                                                            "label": "unmentioned", "main": 1, "pr": 2}]))
    assert it["status"] == "ran" and it["probe_changed_line_coverage"]["changed_lines_covered"] == 2


def test_crash_only_on_pr_side_is_not_adequate():
    it = probes.classify_item(_item([{"a": 1}] * 3, [{ERR: {"crash": "boom"}}] * 3,
                                    [{"name": "a", "state": "differs", "label": "unmentioned", "main": 1,
                                      "pr": "ABSENT"}]))
    assert it["status"] == "crashed" and it["probe_changed_line_coverage"]["adequacy"] == "not_adequate"
    assert it["observations"][0]["label"] == "not_testable"


def test_probe_with_no_observations_covers_nothing():
    it = probes.classify_item(_item([], [], []))
    assert it["status"] == "error" and it["probe_changed_line_coverage"]["changed_lines_covered"] == 0


def test_crashed_probe_cannot_satisfy_ai_probe_gate():
    item = probes.classify_item(_item([{ERR: {"crash": "x"}}] * 3, [{ERR: {"crash": "x"}}] * 3, _err_obs()))
    rec = {"verdict": "verified", "baseline": "full", "reason": "tests pass", "probes": {"items": [item]}}
    assert daily_run.ai_probe_gate(rec)["verdict"] == "could_not_verify"


def test_gate_ignores_crashed_status_even_with_stale_counts():
    item = _item([{ERR: {}}] * 3, [{ERR: {}}] * 3, _err_obs()) | {"status": "crashed"}
    rec = {"verdict": "verified", "baseline": "full", "reason": "", "probes": {"items": [item]}}
    assert daily_run.ai_probe_gate(rec)["verdict"] == "could_not_verify"


def test_uninformative_and_not_run_cover_nothing_and_cannot_verify():
    exc = {"raises": "AttributeError"}
    uninf = probes.classify_item(_item([{"f": exc}] * 3, [{"f": exc}] * 3,
                                       [{"name": "f", "state": "same", "label": "no_difference",
                                         "main": exc, "pr": exc}]))
    skip = {"skipped": "no type-aware input"}
    notrun = probes.classify_item(_item([{"f": skip}] * 3, [{"f": skip}] * 3,
                                        [{"name": "f", "state": "same", "label": "no_difference",
                                          "main": skip, "pr": skip}]))
    for it, status in ((uninf, "uninformative"), (notrun, "not_run")):
        assert it["status"] == status
        assert it["probe_changed_line_coverage"]["changed_lines_covered"] == 0
        rec = {"verdict": "verified", "baseline": "full", "reason": "tests pass", "probes": {"items": [it]}}
        assert daily_run.ai_probe_gate(rec)["verdict"] == "could_not_verify"


def test_one_crashed_run_is_not_a_side_crash():
    it = probes.classify_item(_item([{"a": 1}, {"a": 1}, {ERR: {"crash": "x"}}], [{"a": 1}] * 3,
                                    [{"name": "a", "state": "same", "label": "no_difference", "main": 1, "pr": 1}]))
    assert it["status"] == "ran" and it["probe_changed_line_coverage"]["adequacy"] == "adequate"


def test_crashed_probe_does_not_count_as_an_unclaimed_difference():
    item = probes.classify_item(_item([{ERR: {"crash": "x"}}] * 3, [{"a": 1}] * 3,
                                      [{"name": "a", "state": "differs", "label": "unmentioned", "main": "ABSENT",
                                        "pr": 1}]))
    kept, notes = probe_adequacy.deciding_items([item])
    assert kept[0]["observations"] == [] and notes
    same = {"t::ok": ("passed", "")}
    verdict = daily_run.verdict_for(daily_run.compare_sides({"main": [same] * 3, "pr": [same] * 3}), None,
                                    probe_results={"items": [item]}, baseline="tests+probes")[0]
    assert verdict == "verified"
