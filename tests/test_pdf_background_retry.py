"""Missing PDFs: status file, detached background retry with backoff, 'PDF preparing…' in console and App."""
import json
from pathlib import Path

import pytest

from reports import pdf_status as ps


def _report(tmp_path: Path, name="run-1") -> Path:
    d = tmp_path / "daily" / "2026-10-27" / name
    d.mkdir(parents=True)
    (d / "REPORT.html").write_text("<h1>Report</h1>")
    (d / "REPORT.md").write_text("# Report")
    (d / "record.json").write_text(json.dumps({"verdict": "verified"}))
    return d


def _writer(fail_times: int):
    calls = []

    def to_pdf(html, pdf):
        calls.append(html)
        if len(calls) > fail_times:
            Path(pdf).write_bytes(b"%PDF-1.4 ok")
            return None
        raise RuntimeError("chrome and fallback both failed")
    return to_pdf, calls


def test_status_file_states(tmp_path):
    d = _report(tmp_path)
    assert ps.read_state(d) is None
    ps.write_status(d, ps.PREPARING, 1)
    assert ps.read_state(d) == ps.PREPARING
    assert set(json.loads((d / ps.STATUS_FILE).read_text())) == {"state", "attempts", "updated_at", "started_at"}
    (d / "REPORT.pdf").write_bytes(b"%PDF")
    assert ps.read_state(d) == ps.READY
    with pytest.raises(ValueError):
        ps.write_status(d, "weird")


def test_default_backoff_is_five_tries_over_about_ten_minutes():
    assert len(ps.RETRY_DELAYS_S) == 5
    assert 8 * 60 <= sum(ps.RETRY_DELAYS_S) <= 12 * 60
    assert list(ps.RETRY_DELAYS_S) == sorted(ps.RETRY_DELAYS_S)


def test_retry_succeeds_after_failures_and_never_touches_record(tmp_path):
    d = _report(tmp_path)
    before = {p.name: p.read_bytes() for p in d.iterdir()}
    to_pdf, calls = _writer(fail_times=2)
    slept = []
    assert ps.retry_until_ready(d, sleep=slept.append, to_pdf=to_pdf) == ps.READY
    assert len(calls) == 3 and slept == list(ps.RETRY_DELAYS_S[:3])
    assert json.loads((d / ps.STATUS_FILE).read_text())["state"] == "ready"
    for name, data in before.items():
        assert (d / name).read_bytes() == data


def test_final_failure_logs_error_for_maintainers(tmp_path, caplog):
    d = _report(tmp_path)
    to_pdf, calls = _writer(fail_times=99)
    with caplog.at_level("ERROR", logger="proof_of_change.pdf"):
        assert ps.retry_until_ready(d, sleep=lambda s: None, to_pdf=to_pdf) == ps.ERROR
    assert len(calls) == 5
    st = json.loads((d / ps.STATUS_FILE).read_text())
    assert st["state"] == "error" and st["attempts"] == 6
    assert "chrome" not in (d / ps.STATUS_FILE).read_text().lower()
    assert any("PDF still missing" in r.message for r in caplog.records)
    assert ps.user_label(ps.read_state(d)) == "PDF could not be generated."


def test_first_attempt_ok_marks_ready_without_worker(tmp_path, monkeypatch):
    d = _report(tmp_path)
    (d / "REPORT.pdf").write_bytes(b"%PDF")
    monkeypatch.setattr(ps.subprocess, "Popen", lambda *a, **k: pytest.fail("no worker expected"))
    assert ps.after_first_attempt(d, None) == ps.READY


def test_first_attempt_failure_starts_detached_worker(tmp_path, monkeypatch):
    d = _report(tmp_path)
    monkeypatch.delenv(ps.NO_RETRY_ENV, raising=False)
    seen = {}
    monkeypatch.setattr(ps.subprocess, "Popen", lambda argv, **k: seen.update(argv=argv, **k))
    assert ps.after_first_attempt(d, "ERROR: PDF not generated") == ps.PREPARING
    assert seen["argv"][1:4] == ["-m", "reports.pdf_status", "retry"]
    assert seen["start_new_session"] is True
    assert ps.read_state(d) == ps.PREPARING


def test_worker_start_failure_falls_back_to_thread(tmp_path, monkeypatch):
    d = _report(tmp_path)
    monkeypatch.delenv(ps.NO_RETRY_ENV, raising=False)

    def boom(*a, **k):
        raise OSError("no fork")
    started = []
    monkeypatch.setattr(ps.subprocess, "Popen", boom)
    import threading
    monkeypatch.setattr(threading.Thread, "start", lambda self: started.append(self.name))
    assert ps.after_first_attempt(d, "err") == ps.PREPARING
    assert started == ["pdf-retry"]


def test_render_run_marks_preparing_when_pdf_fails(tmp_path, monkeypatch):
    from reports import pr_report
    from reports import reviewer as rv
    monkeypatch.setattr(rv, "find_chrome", lambda: "/usr/bin/chrome")
    monkeypatch.setattr(rv, "to_pdf", lambda h, p: "ERROR: PDF not generated")
    called = []
    monkeypatch.setattr(ps, "after_first_attempt", lambda od, err: called.append((Path(od).name, err)) or "preparing")
    run = tmp_path / "run"
    (run / "x").mkdir(parents=True)
    rec = {"pr": 1, "repo": "acme/widget", "library": "widget", "title": "Change 1", "head_sha": "a" * 40,
           "route": "source-pair", "verdict": "verified", "reason": "ok", "comparison": {"same": 1},
           "posted_upstream": False, "files": {"package_py": [], "compiled": [], "other": []}}
    (run / "x" / "record.json").write_text(json.dumps(rec))
    before = (run / "x" / "record.json").read_text()
    rows = pr_report.render_run(run, tmp_path / "out", formats=("md", "html", "pdf"))
    assert called and called[0][1] == "ERROR: PDF not generated"
    assert rows[0]["pdf_state"] == "preparing"
    assert (run / "x" / "record.json").read_text() == before


def test_console_links_show_preparing_then_real_link(tmp_path, monkeypatch):
    from poc import console_api
    daily = tmp_path / "daily"
    d = _report(tmp_path, "run-1")
    monkeypatch.setattr(console_api, "REPORTS_DAILY", daily)
    ps.write_status(d, ps.PREPARING, 1)
    links = console_api.report_links("run-1", folder="run-1")
    assert links["report_pdf"] is None and links["report_pdf_status"] == "preparing"
    ps.write_status(d, ps.ERROR, 6)
    assert console_api.report_links("run-1", folder="run-1")["report_pdf_status"] == "failed"
    (d / "REPORT.pdf").write_bytes(b"%PDF")
    links = console_api.report_links("run-1", folder="run-1")
    assert links["report_pdf"].endswith("/report.pdf") and links["report_pdf_status"] == "ready"


def test_github_app_comment_and_hosted_page(tmp_path):
    from poc import github_app as ga
    assert "PDF preparing…" in ga.summary_comment("verified", "ok", "https://x/r.html", pdf_preparing=True)
    assert "[PDF report](https://x/r.pdf)" in ga.summary_comment("verified", "ok", pdf_url="https://x/r.pdf")
    d = _report(tmp_path, "run-1")
    ps.write_status(d, ps.PREPARING, 1)
    hosted = tmp_path / "hosted"
    page = ga.write_hosted_report({"id": "rid", "verdict": "verified"}, hosted, report_dir=d)
    assert "PDF preparing…" in page.read_text() and not (hosted / "rid.pdf").exists()
    (d / "REPORT.pdf").write_bytes(b"%PDF")
    assert ga.publish_ready_pdf(d, hosted) == 1
    text = page.read_text()
    assert "PDF preparing" not in text and 'href="rid.pdf"' in text
    assert (hosted / "rid.pdf").read_bytes() == b"%PDF"


def test_cli_usage():
    assert ps.main(["nope"]) == 2
