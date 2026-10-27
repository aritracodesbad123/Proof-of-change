"""PDF outcome reaches every surface: App comment and check run are edited in place, never re-posted."""
import json
from pathlib import Path

import pytest

from poc import github_app as ga
from reports import pdf_status as ps

ENV = {"POC_DEMO_REPOS": "demo/repo", "GITHUB_APP_INSTALLATION_TOKEN": "t", "POC_REPORT_BASE_URL": "https://r.example"}


def _dir(tmp_path, name="run-1"):
    d = tmp_path / name
    d.mkdir()
    (d / "REPORT.html").write_text("<h1>r</h1>")
    return d


def _saved(d, **kw):
    body = ga.summary_comment("verified", "ok", "https://r.example/run-1.html", pdf_preparing=True)
    args = dict(repo="demo/repo", pr=7, comment_id=11, comment_body=body, check_run_id=22,
                check_title="Proof-of-Change: verified", check_summary="ok", pdf_url="https://r.example/run-1.pdf")
    args.update(kw)
    return ga.remember_posts(d, **args)


def _fakes():
    calls = []
    return calls, (lambda repo, cid, body, tok, env=None: calls.append(("comment", repo, cid, body)) or {}), \
        (lambda repo, rid, payload, tok, env=None: calls.append(("check", repo, rid, payload)) or {})


def test_ready_edits_same_comment_and_check_run_with_link(tmp_path):
    d = _dir(tmp_path)
    _saved(d)
    calls, pc, pk = _fakes()
    assert ga.update_posts_for_pdf(d, ps.READY, ENV, pc, pk)
    (k1, repo, cid, body), (k2, _, rid, payload) = calls
    assert (k1, repo, cid, k2, rid) == ("comment", "demo/repo", 11, "check", 22)
    assert "[PDF report](https://r.example/run-1.pdf)" in body and "PDF preparing" not in body
    assert "https://r.example/run-1.pdf" in payload["output"]["summary"]


def test_failure_edits_in_place_with_clear_text(tmp_path):
    d = _dir(tmp_path)
    _saved(d)
    calls, pc, pk = _fakes()
    assert ga.update_posts_for_pdf(d, ps.ERROR, ENV, pc, pk)
    assert ga.FAILED_TEXT in calls[0][3] and "PDF preparing" not in calls[0][3]
    assert ga.FAILED_TEXT in calls[1][3]["output"]["summary"]


def test_no_edit_without_saved_ids(tmp_path):
    d = _dir(tmp_path)
    assert _saved(d, comment_id=None, check_run_id=None) is None
    calls, pc, pk = _fakes()
    assert not ga.update_posts_for_pdf(d, ps.READY, ENV, pc, pk)
    assert calls == []


def test_edit_is_idempotent(tmp_path):
    d = _dir(tmp_path)
    _saved(d)
    calls, pc, pk = _fakes()
    assert ga.update_posts_for_pdf(d, ps.READY, ENV, pc, pk)
    assert not ga.update_posts_for_pdf(d, ps.READY, ENV, pc, pk)
    assert not ga.update_posts_for_pdf(d, ps.ERROR, ENV, pc, pk)
    assert len(calls) == 2


def test_edit_refused_outside_demo_repos(tmp_path):
    d = _dir(tmp_path)
    _saved(d, repo="upstream/repo")
    assert not ga.update_posts_for_pdf(d, ps.READY, ENV)  # real patchers refuse before any request


def test_retry_success_triggers_edit(tmp_path, monkeypatch):
    d = _dir(tmp_path)
    seen = []
    monkeypatch.setattr(ga, "publish_pdf_outcome", lambda rd, st, *a, **k: seen.append(st))

    def to_pdf(h, p):
        Path(p).write_bytes(b"%PDF-1.4")
    assert ps.retry_until_ready(d, delays=(0,), sleep=lambda s: None, to_pdf=to_pdf) == ps.READY
    assert seen == [ps.READY]


def test_final_failure_shows_failed_everywhere(tmp_path, monkeypatch):
    d = _dir(tmp_path)
    seen = []
    monkeypatch.setattr(ga, "publish_pdf_outcome", lambda rd, st, *a, **k: seen.append(st))

    def boom(h, p):
        raise RuntimeError("x")
    assert ps.retry_until_ready(d, delays=(0, 0), sleep=lambda s: None, to_pdf=boom) == ps.ERROR
    assert seen == [ps.ERROR]
    assert ps.user_label(ps.ERROR) == "PDF could not be generated."
    assert ps.user_label(ps.PREPARING) == "PDF preparing…"


def test_hosted_page_shows_failure(tmp_path):
    d = _dir(tmp_path)
    hosted = tmp_path / "hosted"
    ps.write_status(d, ps.PREPARING, 1)
    ga.write_hosted_report({"id": "run-1", "verdict": "verified"}, hosted, report_dir=d)
    assert "PDF preparing" in (hosted / "run-1.html").read_text()
    assert ga.publish_failed_pdf(d, hosted) == 1
    page = (hosted / "run-1.html").read_text()
    assert ga.FAILED_TEXT in page and "PDF preparing" not in page


def test_console_reports_failed(tmp_path, monkeypatch):
    from poc import console_api
    d = _dir(tmp_path)
    ps.write_status(d, ps.ERROR, 5)
    monkeypatch.setattr(console_api, "find_reviewer_report_file",
                        lambda rid, ext, **k: (d / "REPORT.html") if ext == "html" else None)
    assert console_api.report_links("run-1")["report_pdf_status"] == "failed"


def test_lock_stops_a_second_worker(tmp_path):
    d = _dir(tmp_path)
    ps.write_status(d, ps.PREPARING, 1)
    calls = []
    with ps._FolderLock(d) as held:
        assert held.held
        out = ps.retry_until_ready(d, delays=(0,), sleep=lambda s: None, to_pdf=lambda h, p: calls.append(1))
    assert out == ps.PREPARING and calls == []


def test_resume_restarts_preparing_and_fails_old_ones(tmp_path, monkeypatch):
    monkeypatch.setattr(ga, "publish_pdf_outcome", lambda *a, **k: None)
    fresh, old, done = _dir(tmp_path, "fresh"), _dir(tmp_path, "old"), _dir(tmp_path, "done")
    for d in (fresh, old, done):
        ps.write_status(d, ps.PREPARING, 1)
    (done / "REPORT.pdf").write_bytes(b"%PDF")
    s = json.loads((old / ps.STATUS_FILE).read_text())
    s["started_at"] -= ps.TIME_LIMIT_S + 10
    (old / ps.STATUS_FILE).write_text(json.dumps(s))
    started = []
    out = ps.resume_pending([tmp_path], start=lambda d: started.append(d.name) or True)
    assert out == {"resumed": ["fresh"], "failed": ["old"], "reposted": []} and started == ["fresh"]
    assert ps.read_state(old) == ps.ERROR
    assert json.loads((done / ps.STATUS_FILE).read_text())["state"] == ps.READY


def test_pdf_written_atomically_and_checked(tmp_path, monkeypatch):
    from reports import reviewer as rv
    html, pdf = str(tmp_path / "r.html"), str(tmp_path / "REPORT.pdf")
    Path(html).write_text("<p>x</p>")
    monkeypatch.setattr(rv, "_to_pdf_direct", lambda h, p: Path(p).write_bytes(b"<html>not pdf") and None)
    assert rv.to_pdf(html, pdf) is not None
    assert not Path(pdf).exists() and not Path(pdf + ".tmp").exists()
    seen = {}

    def good(h, p):
        seen["path"] = p
        Path(p).write_bytes(b"%PDF-1.4 ok")
    monkeypatch.setattr(rv, "_to_pdf_direct", good)
    assert rv.to_pdf(html, pdf) is None
    assert seen["path"].endswith("REPORT.pdf.tmp") and Path(pdf).read_bytes().startswith(b"%PDF")
    assert not Path(pdf + ".tmp").exists()


def test_no_chrome_gate_removed_from_pr_report():
    src = (Path(__file__).resolve().parent.parent / "reports" / "pr_report.py").read_text()
    assert "no Chrome/Chromium found, so no PDFs" not in src


def test_hosted_app_refuses_without_report_base():
    with pytest.raises(SystemExit):
        ga.require_report_base({})
    assert ga.require_report_base({"POC_REPORT_BASE_URL": "https://r.example"})
    with pytest.raises(SystemExit):
        ga.serve(env={})


def _flaky(fails, calls, kind):
    state = {"n": 0}

    def f(repo, ident, data, tok, env=None):
        state["n"] += 1
        if state["n"] <= fails:
            raise ga.GitHubAppError("GitHub API PATCH failed: HTTP 502")
        calls.append((kind, ident))
        return {}
    return f


def test_failed_edit_is_retried_with_backoff_then_marked_done(tmp_path):
    d = _dir(tmp_path)
    _saved(d)
    calls, slept = [], []
    pc, pk = _flaky(1, calls, "comment"), _flaky(2, calls, "check")
    assert ga.update_posts_for_pdf(d, ps.READY, ENV, pc, pk, delays=(1, 2, 3), sleep=slept.append)
    assert calls == [("comment", 11), ("check", 22)]  # each item edited exactly once
    assert slept == [1, 2, 3]
    assert json.loads((d / ga.COMMENT_FILE).read_text())["done"] == ps.READY


def test_edit_still_failing_leaves_done_null(tmp_path):
    d = _dir(tmp_path)
    _saved(d)
    calls, slept = [], []
    pc, pk = _flaky(99, calls, "comment"), _flaky(0, calls, "check")
    assert not ga.update_posts_for_pdf(d, ps.READY, ENV, pc, pk, delays=(1, 1), sleep=slept.append)
    assert slept == [1, 1] and calls == []
    assert json.loads((d / ga.COMMENT_FILE).read_text())["done"] is None
    assert ga.posts_pending(d)


def test_resume_pending_retries_edit_for_ready_folder_with_done_null(tmp_path, monkeypatch):
    d = _dir(tmp_path)
    (d / ps.PDF_FILE).write_bytes(b"%PDF-1.4 x" * 50)
    ps.write_status(d, ps.READY, 1)
    _saved(d)
    calls = []
    monkeypatch.setattr(ga, "patch_pr_comment", _flaky(0, calls, "comment"))
    monkeypatch.setattr(ga, "patch_check_run", _flaky(0, calls, "check"))
    monkeypatch.setattr(ga, "installation_token", lambda env=None: "t")
    out = ps.resume_pending([tmp_path], start=lambda d: False)
    assert out["reposted"] == ["run-1"] and calls == [("comment", 11), ("check", 22)]
    assert json.loads((d / ga.COMMENT_FILE).read_text())["done"] == ps.READY
    out = ps.resume_pending([tmp_path], start=lambda d: False)  # done now: no second edit
    assert out["reposted"] == [] and len(calls) == 2


def test_resume_pending_retries_edit_for_error_folder(tmp_path, monkeypatch):
    d = _dir(tmp_path)
    ps.write_status(d, ps.ERROR, 3)
    _saved(d)
    calls = []
    monkeypatch.setattr(ga, "patch_pr_comment", _flaky(0, calls, "comment"))
    monkeypatch.setattr(ga, "patch_check_run", _flaky(0, calls, "check"))
    monkeypatch.setattr(ga, "installation_token", lambda env=None: "t")
    assert ps.resume_pending([tmp_path], start=lambda d: False)["reposted"] == ["run-1"]
    assert json.loads((d / ga.COMMENT_FILE).read_text())["done"] == ps.ERROR
