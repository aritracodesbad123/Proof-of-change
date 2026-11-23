"""False confirmations use the same per-pull-request count as wrong passes."""
from __future__ import annotations

import json

from bench.accuracy import arm_rates, assess_saved, read_saved, saved_report
from bench.manifest import REGRESSION
from bench.report import main as report_main


def rec(repo, number, verdict, hand, source, category=None):
    row = {
        "repo": repo,
        "pr": {"repo": repo, "number": number},
        "verdict": verdict,
        "hand_check": hand,
        "_source": source,
    }
    if category is not None:
        row["category"] = category
    return row


def test_two_records_of_one_pull_request_count_once():
    records = [
        rec("o/r", 1, "verified", "break", "b.json"),
        rec("o/r", 1, "verified", "break", "a.json"),
    ]
    got = assess_saved(records)
    assert got["false_confirmations"] == {"count": 1, "n": 1, "rate": 1.0}
    assert got["records"] == 2 and got["pull_requests"] == 1


def test_denominator_matches_the_wrong_pass_convention():
    """Both rates count a pull request once. Two records are not two denominators."""
    records = [
        rec("o/r", 7, "verified", "break", "a.json", "known_regression_tests_miss"),
        rec("o/r", 7, "verified", "break", "b.json", "known_regression_tests_miss"),
        rec("o/r", 8, "needs_attention", "break", "c.json", "known_regression_tests_catch"),
        rec("o/r", 9, "verified", None, "d.json", "known_safe"),
    ]
    assert "known_regression_tests_miss" in REGRESSION
    got = assess_saved(records)
    assert got["wrong_passes"] == {"count": 1, "n": 2, "rate": 0.5}
    assert got["false_confirmations"] == {"count": 1, "n": 1, "rate": 1.0}
    assert got["unchecked"] == 1
    assert got["wrong_passes"]["n"] == 2  # two regression pull requests, three regression records would be wrong
    assert got["false_confirmations"]["n"] != 2  # the duplicate verified record is not a second check


def test_zero_false_confirmations():
    got = assess_saved([rec("o/r", 3, "verified", "no_break", "a.json")])
    assert got["false_confirmations"] == {"count": 0, "n": 1, "rate": 0.0}
    assert got["unchecked"] == 0
    assert got["wrong_passes"] == {"count": 0, "n": 0, "rate": None}


def test_pull_request_with_no_hand_check_is_excluded_and_unchecked():
    records = [
        rec("o/r", 3, "verified", None, "a.json"),
        rec("o/r", 3, "verified", None, "c.json"),
        rec("o/r", 4, "verified", "no_break", "b.json"),
        rec("o/r", 5, "could_not_verify", None, "e.json"),
    ]
    got = assess_saved(records)
    assert got["false_confirmations"] == {"count": 0, "n": 1, "rate": 0.0}
    assert got["unchecked"] == 1
    assert got["pull_requests"] == 3


def test_needs_attention_hand_check_is_a_real_break():
    got = assess_saved([rec("o/r", 2, "verified", {"verdict": "needs_attention"}, "a.json")])
    assert got["false_confirmations"]["count"] == 1 and got["false_confirmations"]["n"] == 1


def test_several_check_records_for_one_case_count_once():
    row = {"case_id": "only", "category": "known_safe", "outcome": "ran", "verdict": "verified"}
    by_case = {"only": [{"hand_check": "break"}, {"hand_check": "break"}]}
    got = arm_rates([row], by_case)
    assert got["false_confirmations"] == {"count": 1, "n": 1, "rate": 1.0}
    assert got["unchecked"] == 0
    assert got["wrong_passes"] == {"count": 0, "n": 0, "rate": None}


def test_saved_report_does_not_write_the_records(tmp_path):
    folder = tmp_path / "saved"
    slot = folder / "2026-11-01" / "abc" / "lib-1"
    slot.mkdir(parents=True)
    payload = rec("o/r", 1, "verified", None, "record.json")
    (slot / "record.json").write_text(json.dumps(payload))
    before = (slot / "record.json").read_bytes()
    text = saved_report(folder)
    assert (slot / "record.json").read_bytes() == before
    assert read_saved(folder)[0]["verdict"] == "verified"
    assert "Unchecked verified pull requests: 1." in text
    assert "False confirmations: n/a (n=0)." in text
    out = tmp_path / "out"
    assert report_main(["--records", str(folder), "--out", str(out)]) == 0
    assert (out / "evidence.md").read_text() == text
    assert report_main(["--records", str(folder), "--out", str(folder / "inside")]) == 2
    assert not (folder / "inside").exists()
    assert (slot / "record.json").read_bytes() == before


def test_missing_verdict_counts_as_could_not_verify():
    got = assess_saved([{"repo": "o/r", "pr": {"repo": "o/r", "number": 9}, "verdict": None, "_source": "a.json"}])
    assert got["record_verdicts"]["could_not_verify"] == 1
    assert got["false_confirmations"]["n"] == 0
    assert got["unchecked"] == 0
