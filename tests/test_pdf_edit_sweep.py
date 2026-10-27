import json
import logging
import threading

from poc import github_app as ga
from reports import pdf_status as ps

ENV = {"POC_DEMO_REPOS": "demo/repo", "GITHUB_APP_INSTALLATION_TOKEN": "t", "POC_REPORT_BASE_URL": "https://r.example"}


def _pending(tmp_path, state=ps.READY):
    d = tmp_path / "run-1"
    d.mkdir()
    (d / "REPORT.html").write_text("<h1>r</h1>")
    body = ga.summary_comment("verified", "ok", "https://r.example/run-1.html", pdf_preparing=True)
    ga.remember_posts(d, repo="demo/repo", pr=7, comment_id=11, comment_body=body, check_run_id=22,
                      check_title="t", check_summary="ok", pdf_url="https://r.example/run-1.pdf")
    ps.write_status(d, state, 1)
    if state == ps.READY:
        (d / ps.PDF_FILE).write_bytes(b"%PDF-1.4 test")
    return d


def _info(d):
    return json.loads((d / ga.COMMENT_FILE).read_text())


def test_sweep_retries_and_marks_done(tmp_path):
    d = _pending(tmp_path)
    calls, fail = [], {"n": 1}

    def pc(repo, cid, body, tok, env=None):
        calls.append(body)
        if fail["n"]:
            fail["n"] -= 1
            raise ga.GitHubAppError("boom")
        return {}

    def update(rd, state, env=None, delays=()):
        assert delays == ()  # a sweep never waits inside
        return ga.update_posts_for_pdf(rd, state, ENV, pc, lambda *a, **k: {}, delays=delays,
                                       sleep=lambda s: (_ for _ in ()).throw(AssertionError("slept")))

    out1 = ga.sweep_pending_posts([tmp_path], now=1000, update=update)
    assert out1["retrying"] == ["run-1"] and ga.posts_pending(d)
    out2 = ga.sweep_pending_posts([tmp_path], now=1300, update=update)
    assert out2["done"] == ["run-1"]
    assert _info(d)["done"] == ps.READY and not ga.posts_pending(d)
    assert "[PDF report](https://r.example/run-1.pdf)" in calls[-1]
    assert ga.sweep_pending_posts([tmp_path], now=1600, update=update) == {"done": [], "retrying": [], "gave_up": []}


def test_sweep_gives_up_after_limit_with_logged_error(tmp_path, caplog):
    d = _pending(tmp_path)
    update = lambda *a, **k: False  # noqa: E731
    for i in range(3):
        assert ga.sweep_pending_posts([tmp_path], now=1000 + i, update=update, max_attempts=3)["retrying"]
    with caplog.at_level(logging.ERROR):
        out = ga.sweep_pending_posts([tmp_path], now=1010, update=update, max_attempts=3)
    assert out["gave_up"] == ["run-1"]
    info = _info(d)
    assert info["done"] == ga.GAVE_UP and "gave up after 3" in info["final_error"]
    assert not ga.posts_pending(d)
    assert any("Gave up editing" in r.getMessage() for r in caplog.records)


def test_sweep_gives_up_by_age(tmp_path):
    d = _pending(tmp_path)
    ga.sweep_pending_posts([tmp_path], now=0, update=lambda *a, **k: False, max_age_s=100)
    assert ga.sweep_pending_posts([tmp_path], now=101, update=lambda *a, **k: False, max_age_s=100)["gave_up"]
    assert _info(d)["done"] == ga.GAVE_UP


def test_sweep_never_raises_and_skips_preparing(tmp_path):
    _pending(tmp_path, state=ps.PREPARING)

    def boom(*a, **k):
        raise RuntimeError("x")
    assert ga.sweep_pending_posts([tmp_path], now=1, update=boom)["retrying"] == []
    (tmp_path / "run-1" / "pdf_status.json").write_text("{}")
    ga.sweep_pending_posts([tmp_path / "missing", tmp_path], now=1, update=boom)  # no raise


def test_sweeper_thread_runs_and_stops_cleanly():
    ran = threading.Event()

    def sweep():
        ran.set()
        raise RuntimeError("never escapes")
    s = ga.PendingEditSweeper(interval_s=0.001, sweep=sweep).start()
    assert ran.wait(2)
    s.stop()
    assert not s.thread.is_alive()
