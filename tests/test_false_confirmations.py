"""Hand checks come from a jsonl file. A row applies only when repo, pull request, and head all match."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from bench.accuracy import (
    DEFAULT_HAND_CHECKS,
    HandCheckError,
    arm_rates,
    assess_saved,
    load_hand_checks,
    read_saved,
    saved_markdown,
    saved_report,
)
from bench.report import main as report_main

FIXTURE = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "hand_checks" / "sample.jsonl"
HEAD = "a" * 40
OTHER = "e" * 40


def rec(repo, number, head, verdict, source):
    return {
        "repo": repo,
        "pr": {"repo": repo, "number": number, "head_sha": head},
        "verdict": verdict,
        "hand_check": "break",
        "_source": source,
    }


def test_exact_match_applies_and_ignores_a_note_on_the_record():
    labels = load_hand_checks(FIXTURE)
    got = assess_saved([rec("o/r", 1, HEAD, "verified", "a.json")], labels)
    assert got["wrong_passes"]["count"] == 1
    assert got["false_confirmations"] == {"count": 1, "n": 1, "rate": 1.0}
    assert got["unlabelled"] == 0


def test_different_head_is_unlabelled():
    labels = load_hand_checks(FIXTURE)
    got = assess_saved([rec("o/r", 1, "f" * 40, "verified", "a.json")], labels)
    assert got["false_confirmations"] == {"count": 0, "n": 0, "rate": None}
    assert got["wrong_passes"]["count"] == 0
    assert got["unlabelled"] == 1


def test_earlier_verified_broken_head_counts_when_the_later_record_does_not():
    labels = load_hand_checks(FIXTURE)
    records = [
        rec("o/r", 1, HEAD, "verified", "a.json"),
        rec("o/r", 1, "f" * 40, "could_not_verify", "b.json"),
    ]
    got = assess_saved(records, labels)
    assert got["pull_requests"] == 1
    assert got["pull_request_verdicts"]["could_not_verify"] == 1
    assert got["pull_request_verdicts"]["verified"] == 0
    assert got["wrong_passes"] == {"count": 1, "n": 1, "rate": 1.0}
    assert got["false_confirmations"] == {"count": 1, "n": 1, "rate": 1.0}
    assert got["unlabelled"] == 0
    row = {"case_id": "only", "category": "known_safe", "outcome": "ran", "verdict": "could_not_verify"}
    arm = arm_rates([row], {"only": records}, labels)
    assert arm["false_confirmations"] == {"count": 1, "n": 1, "rate": 1.0}
    assert arm["wrong_passes"]["count"] == 1


def test_an_earlier_verified_record_does_not_borrow_a_later_head():
    labels = load_hand_checks(FIXTURE)
    records = [
        rec("o/r", 1, "f" * 40, "verified", "a.json"),
        rec("o/r", 1, HEAD, "could_not_verify", "b.json"),
    ]
    got = assess_saved(records, labels)
    assert got["pull_request_verdicts"]["could_not_verify"] == 1
    assert got["wrong_passes"]["count"] == 0
    assert got["false_confirmations"] == {"count": 0, "n": 0, "rate": None}
    assert got["unlabelled"] == 1
    row = {"case_id": "only", "category": "known_safe", "outcome": "ran", "verdict": "could_not_verify"}
    arm = arm_rates([row], {"only": records}, labels)
    assert arm["wrong_passes"]["count"] == 0
    assert arm["unlabelled"] == 1


def test_two_records_at_the_same_head_count_once():
    labels = load_hand_checks(FIXTURE)
    records = [
        rec("o/r", 1, HEAD, "verified", "a.json"),
        rec("o/r", 1, HEAD, "verified", "b.json"),
    ]
    got = assess_saved(records, labels)
    assert got["records"] == 2 and got["pull_requests"] == 1
    assert got["wrong_passes"] == {"count": 1, "n": 1, "rate": 1.0}
    assert got["false_confirmations"] == got["wrong_passes"]


def test_broken_verified_is_a_wrong_pass_and_unlabelled_stays_out():
    labels = load_hand_checks(FIXTURE)
    records = [
        rec("o/r", 1, HEAD, "verified", "a.json"),
        rec("o/r", 2, OTHER, "verified", "b.json"),
        rec("o/r", 9, HEAD, "verified", "c.json"),
    ]
    got = assess_saved(records, labels)
    assert got["wrong_passes"]["count"] == 1
    assert got["false_confirmations"] == {"count": 1, "n": 2, "rate": 0.5}
    assert got["unlabelled"] == 1
    text = saved_markdown(assess_saved(records, labels))
    assert "Unlabelled verified pull requests: 1." in text
    assert "not a pass" in text


def test_a_labelled_verified_pull_request_that_does_not_break_is_not_a_wrong_pass():
    labels = load_hand_checks(FIXTURE)
    got = assess_saved([rec("o/r", 2, OTHER, "verified", "a.json")], labels)
    assert got["wrong_passes"]["count"] == 0
    assert got["false_confirmations"] == {"count": 0, "n": 1, "rate": 0.0}
    assert got["unlabelled"] == 0


def test_missing_file_is_reported_and_a_file_beside_the_records_is_ignored(tmp_path):
    folder = tmp_path / "saved"
    slot = folder / "lib-1"
    slot.mkdir(parents=True)
    (slot / "record.json").write_text(json.dumps(rec("o/r", 1, HEAD, "verified", "record.json")))
    (folder / "hand_checks.jsonl").write_text("not json\n")
    assert DEFAULT_HAND_CHECKS == Path(__file__).resolve().parents[1] / "data" / "hand_checks.jsonl"
    text = saved_report(folder, checks=tmp_path / "missing.jsonl")
    assert "Hand checks not available." in text
    assert "Wrong passes:" not in text
    text = saved_report(folder)
    assert "Hand checks not available." not in text


def test_malformed_row_is_rejected(tmp_path):
    good = json.loads(FIXTURE.read_text().splitlines()[0])

    def write(row):
        path = tmp_path / "hand_checks.jsonl"
        path.write_text(json.dumps(row) + "\n")
        return path

    with pytest.raises(HandCheckError, match="missing broken"):
        load_hand_checks(write({key: value for key, value in good.items() if key != "broken"}))
    bad = dict(good, broken="true")
    with pytest.raises(HandCheckError, match="broken must be true or false"):
        load_hand_checks(write(bad))
    bad = dict(good, checker_verdict="break")
    with pytest.raises(HandCheckError, match="checker_verdict"):
        load_hand_checks(write(bad))
    bad = dict(good, head="abc")
    with pytest.raises(HandCheckError, match="head must be a 40-character commit"):
        load_hand_checks(write(bad))
    bad = dict(good, extra=1)
    with pytest.raises(HandCheckError, match="unexpected extra"):
        load_hand_checks(write(bad))
    path = tmp_path / "hand_checks.jsonl"
    path.write_text(FIXTURE.read_text().splitlines()[0] + "\n" + FIXTURE.read_text().splitlines()[0] + "\n")
    with pytest.raises(HandCheckError, match="repeated pull request"):
        load_hand_checks(path)


def test_case_with_two_records_at_one_head_counts_once():
    labels = load_hand_checks(FIXTURE)
    row = {"case_id": "only", "category": "known_safe", "outcome": "ran", "verdict": "verified"}
    records = [
        rec("o/r", 1, HEAD, "verified", "one.json"),
        rec("o/r", 1, HEAD, "verified", "two.json"),
    ]
    got = arm_rates([row], {"only": records}, labels)
    assert got["false_confirmations"] == {"count": 1, "n": 1, "rate": 1.0}
    assert got["unlabelled"] == 0
    assert got["wrong_passes"]["count"] == 1


def test_saved_report_does_not_write_the_records(tmp_path):
    folder = tmp_path / "saved"
    slot = folder / "2026-11-01" / "abc" / "lib-1"
    slot.mkdir(parents=True)
    payload = rec("o/r", 1, HEAD, "verified", "record.json")
    (slot / "record.json").write_text(json.dumps(payload))
    before = (slot / "record.json").read_bytes()
    text = saved_report(folder, checks=FIXTURE)
    assert (slot / "record.json").read_bytes() == before
    assert read_saved(folder)[0]["verdict"] == "verified"
    assert "Wrong passes: 1." in text
    assert "False confirmations: 1/1." in text
    out = tmp_path / "out"
    assert report_main(["--records", str(folder), "--hand-checks", str(FIXTURE), "--out", str(out)]) == 0
    assert (out / "evidence.md").read_text() == text
    assert report_main(["--records", str(folder), "--out", str(folder / "inside")]) == 2
    assert not (folder / "inside").exists()
    assert (slot / "record.json").read_bytes() == before

