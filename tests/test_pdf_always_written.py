"""A PDF of every check and of the go/no-go summary is always written: without Chrome, with a hanging Chrome,
and when a check crashes partway (then the PDF says could not verify and gives the reason)."""
import json
import shutil
import types
from pathlib import Path

import pytest

pytest.importorskip("reportlab")

import reports.pr_report as pr
import reports.reviewer as rv
from ops import daily_run

FIXTURE = Path(__file__).resolve().parents[1] / "evals" / "fixtures" / "record_rev2_example.json"


def _run_folder(tmp_path):
    d = tmp_path / "run" / "pr1"
    d.mkdir(parents=True)
    shutil.copy(FIXTURE, d / "record.json")
    return tmp_path / "run"


def _pdfs(out):
    return {p.relative_to(out).as_posix(): p.stat().st_size for p in out.rglob("*.pdf")}


def _hanging_chrome(tmp_path, monkeypatch):
    fake = tmp_path / "chrome"
    fake.write_text("#!/bin/sh\nsleep 30\n")
    fake.chmod(0o755)
    monkeypatch.setattr(rv, "find_chrome", lambda: str(fake))
    monkeypatch.setattr(rv, "PDF_TIMEOUT_S", 1)
    monkeypatch.setattr(rv, "CHROME_PROBE_TIMEOUT_S", 1)
    monkeypatch.setattr(rv, "_CHROME_READY", {})


def test_no_chrome_still_writes_report_and_summary_pdf(tmp_path, monkeypatch):
    monkeypatch.setattr(rv, "find_chrome", lambda: None)
    pr.render_run(_run_folder(tmp_path), tmp_path / "o")
    got = _pdfs(tmp_path / "o")
    assert "SUMMARY.pdf" in got and any(k.endswith("/REPORT.pdf") for k in got)
    assert all(v > 0 for v in got.values())


def test_hanging_chrome_summary_pdf_uses_builtin_maker(tmp_path, monkeypatch):
    _hanging_chrome(tmp_path, monkeypatch)
    pr.render_run(_run_folder(tmp_path), tmp_path / "o")
    got = _pdfs(tmp_path / "o")
    assert got.get("SUMMARY.pdf", 0) > 0 and any(k.endswith("/REPORT.pdf") for k in got)


@pytest.mark.parametrize("err", [TimeoutError("check timed out"), RuntimeError("crashed partway")])
def test_crashed_check_gets_could_not_verify_pdf_with_reason(tmp_path, monkeypatch, err):
    monkeypatch.setattr(rv, "find_chrome", lambda: None)
    rdir = tmp_path / "run"
    rdir.mkdir()
    a = types.SimpleNamespace(no_report=False, report_dir=str(tmp_path / "o"))
    cfg, item = {"pkg": "lib"}, {"pr": 7, "title": "t", "head_sha": "0" * 40}
    monkeypatch.setattr(daily_run, "new_record", lambda *x, **k: (_ for _ in ()).throw(KeyError("x")))
    rec = daily_run.harness_error_record("o/lib", cfg, item, rdir, a, {}, err)
    assert rec["verdict"] == "could_not_verify" and type(err).__name__ in rec["reason"]
    assert json.loads((rdir / "lib-7" / "record.json").read_text())["verdict"] == "could_not_verify"
    assert daily_run.reviewer_reports(rdir, a, [rec], "check") is True
    out = tmp_path / "o"
    got = _pdfs(out)
    assert got.get("SUMMARY.pdf", 0) > 0 and any(k.endswith("/REPORT.pdf") for k in got)
    md = next(out.rglob("REPORT.md")).read_text()
    assert "COULD NOT VERIFY" in md.upper() and str(err) in md
