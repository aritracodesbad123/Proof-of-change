import pytest

from evals.pr_metrics import blind_input, load_cases, score
from poc.diff import compare, confirm, normalise, parse_probe_output
from poc.verdict import CHECK_CONCLUSION, Claim, FindingLabel, RunSummary, Verdict, pr_verdict

F = FindingLabel


def test_verdict_values_and_never_block():
    assert {v.value for v in Verdict} == {"verified", "needs_attention", "could_not_verify", "no_code_change"}
    assert "failure" not in CHECK_CONCLUSION.values()


@pytest.mark.parametrize("run,expected", [
    (RunSummary(build_ok=False), Verdict.COULD_NOT_VERIFY),
    (RunSummary(True, [Claim("C1", True, probed=True, proven=True)], [F.PROVEN]), Verdict.VERIFIED),
    # requests #6655: claim proven, but an unmentioned change on public surface
    (RunSummary(True, [Claim("C1", True, True, True), Claim("C2", False)], [F.PROVEN, F.UNMENTIONED_CHANGE, F.NOT_TESTABLE]),
     Verdict.NEEDS_ATTENTION),
    (RunSummary(True, [Claim("C1", True, True, False)], [F.FALSE_CLAIM]), Verdict.NEEDS_ATTENTION),
    (RunSummary(True, [Claim("C1", True, True, True)], [F.PROVEN, F.FLAKY]), Verdict.NEEDS_ATTENTION),
    # fewer than half of testable claims probed
    (RunSummary(True, [Claim("C1", True, True, True), Claim("C2", True), Claim("C3", True)], [F.PROVEN]),
     Verdict.COULD_NOT_VERIFY),
    (RunSummary(True, [], []), Verdict.COULD_NOT_VERIFY),
])
def test_pr_verdict_rules(run, expected):
    assert pr_verdict(run) == expected


def test_diff_is_deterministic_and_noise_free():
    main = {"status": 200, "override_called": True, "t": "2024-03-11T16:51:00Z", "url": "http://127.0.0.1:5123/", "seconds": 0.1}
    pr = {"status": 200, "override_called": True, "t": "2026-10-10T05:00:00Z", "url": "http://127.0.0.1:6001/", "seconds": 9.9}
    assert compare(main, pr) == []
    pr2 = {"crash": "InvalidURL", "override_called": False}
    fields = {d["field"] for d in compare(main, pr2)}
    assert {"status", "override_called", "crash"} <= fields


def test_diff_type_aware():
    assert compare({"x": 1}, {"x": 1.0}) and compare({"x": True}, {"x": 1}) and compare({"x": "1"}, {"x": 1})


def test_parse_probe_output():
    assert parse_probe_output('noise\n{"status": 200}', 0) == {"status": 200}
    assert parse_probe_output("Traceback ...", 1) == {"crash": "non-json output", "exit_code": 1}
    assert parse_probe_output("", "timeout") == {"timeout": True}


def test_confirm_reruns():
    a, b = {"s": 200}, {"s": 500}
    assert confirm([a] * 3, [a] * 3) == "same"
    assert confirm([a] * 3, [b] * 3) == "differs"
    assert confirm([a, b, a], [b] * 3) == "flaky"
    assert normalise({"pid": 1, "a": "0xdeadbeef00"}) == {"a": "<addr>"}


def test_labelled_set_withholds_answers():
    cases = load_cases()
    for c in cases:
        inp = blind_input(c)
        assert "answer" not in inp and "label" not in inp
    leaky = {"id": "x", "input": {"title": "this caused_regression"}, "answer": {}}
    with pytest.raises(ValueError):
        blind_input(leaky)


def test_known_cases_present_and_marked():
    by_id = {c["id"]: c for c in load_cases()}
    assert by_id["requests-6655"]["answer"]["verification"] == "verified"
    assert by_id["scikit-learn-29677"]["answer"]["downstream_check"]["golden_case"] == "golden-sklearn160rc1-imblearn-import-failure"
    cow = by_id["pandas-56633"]
    assert cow["answer"]["verification"] == "verified"
    assert cow["input"]["head_sha"].startswith("3b57972c") and cow["input"]["base_sha"].startswith("c3014abb")
    assert cow["answer"]["downstream_check"]["golden_case"] == "golden-pandas300rc0-upsetplot-cow"
    assert not any(c["id"].startswith("pandas-cow-default") for c in load_cases())


def test_score_catch_and_false_alarm():
    cases = [
        {"id": "r1", "input": {}, "answer": {"label": "caused_regression", "verification": "verified"}},
        {"id": "r2", "input": {}, "answer": {"label": "caused_regression", "verification": "verified"}},
        {"id": "s1", "input": {}, "answer": {"label": "safe", "verification": "verified"}},
        {"id": "s2", "input": {}, "answer": {"label": "safe", "verification": "verified"}},
        {"id": "t1", "input": {}, "answer": {"label": "safe", "verification": "TODO"}},
    ]
    m = score(cases, {"r1": "needs_attention", "r2": "could_not_verify", "s1": "verified", "s2": "needs_attention"})
    assert m["catch_rate"] == 0.5 and m["false_alarm_rate"] == 0.5
    assert m["could_not_verify"] == ["r2"] and m["not_scored"] == ["t1"] and m["missing_verdicts"] == []
