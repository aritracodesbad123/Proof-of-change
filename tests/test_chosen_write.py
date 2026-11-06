"""The chosen-PRs note is checked with the daily reader's parser when it is written.

The captured-day note is tests/fixtures/chosen/chosen-2026-11-06.md. A broken copy moves the first
heading's number off the heading, so it survives only in a URL. The reader does not take a number
from a URL, and the other sections would still parse: that cleaned subset must be refused.

tests/fixtures/chosen/chosen-2026-11-04.md is held out. It uses a different heading style and was
not used to choose these rules. The checker only calls the existing reader.
"""
from __future__ import annotations

import datetime as dt
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from ops import chosen_write, daily_run

ROOT = Path(__file__).resolve().parent.parent
FIX = Path(__file__).parent / "fixtures" / "chosen"
CAPTURED = FIX / "chosen-2026-11-06.md"
HELD_OUT = FIX / "chosen-2026-11-04.md"
WHEN = dt.datetime(2026, 11, 6, 4, 30, tzinfo=dt.timezone.utc)


def _break_captured(text: str) -> str:
    old = "## 1. Delgan/loguru PR #1515"
    assert old in text
    return text.replace(old, "## 1. Delgan/loguru", 1)


def _run(*args, stdin=None):
    return subprocess.run(
        [sys.executable, "-m", "ops.chosen_write", *args],
        cwd=ROOT, input=stdin, capture_output=True, text=True, check=False)


def _pdf_text(path: Path) -> str:
    if not shutil.which("pdftotext"):
        pytest.skip("pdftotext is required to read the no-go summary")
    return subprocess.run(["pdftotext", str(path), "-"], capture_output=True, text=True).stdout


def test_three_heading_forms_match_one_selection(tmp_path):
    """Forms the reader already accepts are not a mismatch when the fields agree."""
    sha, base = "a" * 40, "b" * 40
    intended = {"acme/widget": [{"pr": 12, "head_sha": sha, "base_sha": base, "install": None, "test_cmd": None}]}
    bodies = [
        f"## 1. acme/widget #12\n- Head: {sha}\n- Base: {base}\n",
        f"## 1. acme/widget PR #12\n- Head: {sha}\n- Base: {base}\n",
        f"## 1. acme/widget pull request #12\n- Head: {sha}\n- Base: {base}\n",
        f"## 1. demo\n- **Repo:** https://github.com/acme/widget\n- **Open PR:** #12\n- Head: {sha}\n- Base: {base}\n",
    ]
    for body in bodies:
        parsed, problems = chosen_write.assess(body, intended)
        assert problems == []
        assert parsed["acme/widget"][0]["pr"] == 12
    prose = bodies[0] + "Expected Proof-of-Change verdict: `verified`\nWatch fixes #99.\n"
    parsed, problems = chosen_write.assess(prose, intended)
    assert problems == []
    assert "expected" not in json.dumps(parsed).lower()


def test_field_mismatch_names_both_values():
    text = f"## 1. acme/widget #3\n- Head: {'a' * 40}\n"
    intended = {"acme/widget": [{"pr": 3, "head_sha": "b" * 40}]}
    parsed, problems = chosen_write.assess(text, intended)
    assert parsed["acme/widget"][0]["head_sha"] == "a" * 40
    assert any("head_sha" in item and "a" * 40 in item and "b" * 40 in item for item in problems)


def test_omitted_field_is_not_a_disagreement():
    text = f"## 1. acme/widget #3\n- Head: {'c' * 40}\n"
    intended = [{"repo": "acme/widget", "pr": 3}]
    _parsed, problems = chosen_write.assess(text, intended)
    assert problems == []


def test_write_refuses_a_cleaned_subset_and_keeps_the_previous_file(tmp_path):
    captured = CAPTURED.read_text(encoding="utf-8")
    broken = _break_captured(captured)
    kept = parse_of = daily_run.parse_chosen(CAPTURED)
    parsed = chosen_write.parse_text(broken)
    assert "Delgan/loguru" not in parsed
    assert set(parsed) == {"andialbrecht/sqlparse", "pyinvoke/invoke"}
    dest = tmp_path / "2026-11-06.md"
    dest.write_text("KEEP\n", encoding="utf-8")
    with pytest.raises(chosen_write.ChosenWriteError) as raised:
        chosen_write.write_chosen(dest, broken, kept, now=WHEN)
    assert dest.read_text(encoding="utf-8") == "KEEP\n"
    assert "Delgan/loguru#1515" in str(raised.value)
    assert raised.value.parsed == parsed
    marker = json.loads(chosen_write.marker_path(dest).read_text(encoding="utf-8"))
    assert marker["ok"] is False and marker["parsed"] == parsed
    log = chosen_write.log_path(dest).read_text(encoding="utf-8")
    assert log.startswith("2026-11-06T04:30:00Z FAILED")
    assert "Stopped:" in log
    body = _pdf_text(chosen_write.no_go_dir(dest) / "SUMMARY.pdf")
    assert "NO-GO" in body and "could not run" in body
    assert "Delgan/loguru#1515" in body and "owner/name #N" in body
    assert not chosen_write.selection_path(dest).exists()
    assert parse_of["Delgan/loguru"][0]["pr"] == 1515


def test_write_stores_the_exact_note_and_the_parse(tmp_path):
    text = CAPTURED.read_text(encoding="utf-8")
    intended = daily_run.parse_chosen(CAPTURED)
    dest = tmp_path / "2026-11-06.md"
    # A previous refusal must clear once a write is accepted.
    chosen_write.marker_path(dest).write_text("{}\n", encoding="utf-8")
    stale = chosen_write.no_go_dir(dest)
    stale.mkdir()
    (stale / "SUMMARY.pdf").write_bytes(b"%PDF-1.4\n")
    parsed = chosen_write.write_chosen(dest, text, intended, now=WHEN)
    assert dest.read_bytes() == CAPTURED.read_bytes()
    assert parsed == intended
    assert json.loads(chosen_write.selection_path(dest).read_text(encoding="utf-8")) == intended
    assert not chosen_write.marker_path(dest).exists()
    assert not chosen_write.no_go_dir(dest).exists()
    log = chosen_write.log_path(dest).read_text(encoding="utf-8")
    assert "OK" in log and "Delgan/loguru#1515" in log


def test_unfinished_write_leaves_a_marker(tmp_path, monkeypatch):
    text = "## 1. acme/widget #1\n"
    dest = tmp_path / "day.md"
    real = chosen_write._atomic

    def guarded(path, data):
        if Path(path) == dest:
            raise OSError("disk full")
        real(path, data)

    monkeypatch.setattr(chosen_write, "_atomic", guarded)
    with pytest.raises(chosen_write.ChosenWriteError) as raised:
        chosen_write.write_chosen(dest, text, {"acme/widget": [{"pr": 1}]}, now=WHEN)
    assert "did not finish" in str(raised.value)
    assert not dest.exists()
    assert chosen_write.read_failure(dest)
    assert "did not finish" in chosen_write.log_path(dest).read_text(encoding="utf-8")


def test_cli_refuses_the_broken_captured_note_and_prints_the_parse(tmp_path):
    captured = CAPTURED.read_text(encoding="utf-8")
    intended = tmp_path / "selection.json"
    intended.write_text(json.dumps(daily_run.parse_chosen(CAPTURED)), encoding="utf-8")
    dest = tmp_path / "note.md"
    dest.write_text("KEEP\n", encoding="utf-8")
    proc = _run("write", str(dest), "--intended", str(intended), "--from-file", str(CAPTURED),
                "--now", "2026-11-06T04:30:00Z")
    # The good note is the positive case: accepted, printed, and byte-for-byte.
    assert proc.returncode == 0, proc.stderr
    printed = json.loads(proc.stdout)
    assert printed == daily_run.parse_chosen(dest)
    assert dest.read_bytes() == CAPTURED.read_bytes()
    broken = tmp_path / "broken.md"
    broken.write_text(_break_captured(captured), encoding="utf-8")
    refused = tmp_path / "refused.md"
    refused.write_text("KEEP\n", encoding="utf-8")
    bad = _run("write", str(refused), "--intended", str(intended), "--from-file", str(broken),
               "--now", "2026-11-06T04:30:00Z")
    assert bad.returncode == 2
    assert "Stopped:" in bad.stderr
    assert "No-go summary:" in bad.stderr
    assert "Delgan/loguru#1515" in bad.stderr
    assert json.loads(bad.stdout)["andialbrecht/sqlparse"][0]["pr"] == 944
    assert "Delgan/loguru" not in json.loads(bad.stdout)
    assert refused.read_text(encoding="utf-8") == "KEEP\n"
    preflight = chosen_write.log_path(refused).read_text(encoding="utf-8")
    assert preflight.startswith("2026-11-06T04:30:00Z FAILED")
    check = _run("check", str(refused), "--now", "2026-11-06T04:30:00Z")
    assert check.returncode == 2 and "Stopped:" in check.stderr


def test_held_out_handwritten_mismatch_is_a_visible_refusal(tmp_path):
    """4 Nov is handwritten `owner/name #N: title`, not the `owner/name PR #N` form.

    The rules were not fitted to this file. The same text is accepted when the selection is the
    parse, and refused with a no-go summary when the selection names a different base commit.
    """
    text = HELD_OUT.read_text(encoding="utf-8")
    assert " PR #" not in text
    assert "#7413:" in text
    parsed = daily_run.parse_chosen(HELD_OUT)
    intended = tmp_path / "selection.json"
    intended.write_text(json.dumps(parsed), encoding="utf-8")
    good = tmp_path / "held.md"
    ok = _run("write", str(good), "--intended", str(intended), "--from-file", str(HELD_OUT),
              "--now", "2026-11-06T04:30:00Z")
    assert ok.returncode == 0, ok.stderr
    assert good.read_bytes() == HELD_OUT.read_bytes()
    assert json.loads(ok.stdout) == parsed
    wrong = json.loads(json.dumps(parsed))
    wrong["psf/requests"][0]["base_sha"] = "f" * 40
    wrong_path = tmp_path / "wrong.json"
    wrong_path.write_text(json.dumps(wrong), encoding="utf-8")
    refused = tmp_path / "refused.md"
    refused.write_text("KEEP\n", encoding="utf-8")
    bad = _run("write", str(refused), "--intended", str(wrong_path), "--from-file", str(HELD_OUT),
               "--now", "2026-11-06T04:30:00Z")
    assert bad.returncode == 2
    assert "Stopped:" in bad.stderr and "No-go summary:" in bad.stderr
    assert "psf/requests#7413" in bad.stderr and "base_sha" in bad.stderr
    assert refused.read_text(encoding="utf-8") == "KEEP\n"
    body = _pdf_text(chosen_write.no_go_dir(refused) / "SUMMARY.pdf")
    assert "NO-GO" in body and "could not run" in body
    assert "psf/requests#7413" in body and "base_sha" in body
    assert "in the file and" in body and "f" * 40 in body


def test_daily_run_stops_on_the_marker_before_selection(tmp_path, monkeypatch, capsys):
    note = tmp_path / "chosen.md"
    note.write_text("## 1. acme/widget #9\n", encoding="utf-8")
    with pytest.raises(chosen_write.ChosenWriteError):
        chosen_write.write_chosen(note, "KEEP-NOT-USED\n", {"acme/widget": [{"pr": 1}]}, now=WHEN)
    # The write failed, so the heading the reader accepts is still the file. The marker is the stop.
    assert note.read_text(encoding="utf-8") == "## 1. acme/widget #9\n"
    libraries = tmp_path / "libraries.csv"
    libraries.write_text("library,repo,added_on_ist,priority,status\nwidget,acme/widget,2026-11-06,1,active\n",
                         encoding="utf-8")
    monkeypatch.delenv("POC_HITL", raising=False)
    monkeypatch.delenv("POC_EXPECT_COMMIT", raising=False)
    monkeypatch.setattr(daily_run, "resolve_poc_commit", lambda root=None: "a" * 40)
    monkeypatch.setattr(daily_run, "leave_run_pointer", lambda *args, **kwargs: None)
    monkeypatch.setattr(daily_run, "ensure_tools", lambda: {})
    code = daily_run.main([
        "--model-provider", "none", "--select-only", "--no-report",
        "--ops-dir", str(tmp_path / "ops"), "--libraries-file", str(libraries),
        "--chosen-prs", str(note), "--date", "2026-11-06", "--min-free-gb", "0"])
    err = capsys.readouterr().err
    assert code == 2
    assert "Stopped:" in err and "not accepted" in err
    assert "acme/widget#1" in err
    # The reader would have accepted the file. The marker is what stops the run.
    assert daily_run.parse_chosen(note)["acme/widget"][0]["pr"] == 9
    assert daily_run.empty_chosen_stop(note, daily_run.parse_chosen(note)) is None


def test_marker_absent_keeps_the_empty_file_stop(tmp_path):
    empty = tmp_path / "empty.md"
    empty.write_text("## 1. demo\nno number\n", encoding="utf-8")
    assert chosen_write.run_stop(empty, {})
    good = tmp_path / "good.md"
    good.write_text("## 1. acme/widget #4\n", encoding="utf-8")
    assert chosen_write.run_stop(good, daily_run.parse_chosen(good)) is None
