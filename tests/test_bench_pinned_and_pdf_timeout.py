"""Benchmark cases test their pinned commits; a Contree transport error is retried once (nothing else is);
a PDF that times out is skipped without touching the verdict or the record."""
from __future__ import annotations

import json
import subprocess
import sys
import types
from pathlib import Path

import pytest

from bench import run
from ops import daily_run
from reports import reviewer
from tests.test_bench_harness import cases, fake_exec, record  # noqa: F401


@pytest.fixture(autouse=True)
def _no_keys(monkeypatch):
    for k in run.SECRET_NAMES:
        monkeypatch.delenv(k, raising=False)


def test_command_passes_pinned_sides_from_case_file(tmp_path):
    c = cases()["fx-safe"]
    cmd = run.command(c, "tests", tmp_path, "n")
    assert cmd[cmd.index("--base-sha") + 1] == c["base_sha"]
    assert cmd[cmd.index("--head-sha") + 1] == c["head_sha"]


def _multi_exec(recs):
    calls = []

    def execute(cmd, env, **kw):
        rec = recs[len(calls)]
        calls.append(cmd)
        return fake_exec(rec)(cmd, env, **kw)
    return execute, calls


def transport_rec(c):
    r = record(c, "could_not_verify")
    r["contree"] = {"failed": "contree request failed: ContreeTransportError"}
    return r


def test_retry_once_on_transport_error(tmp_path):
    c = cases()["fx-safe"]
    ex, calls = _multi_exec([transport_rec(c), record(c, "verified")])
    r = run.run_one(c, "tests", tmp_path, ex)
    assert len(calls) == 2 and r["verdict"] == "verified" and r["retried_after_contree_transport_error"] is True


def test_only_one_retry(tmp_path):
    c = cases()["fx-safe"]
    ex, calls = _multi_exec([transport_rec(c), transport_rec(c), record(c, "verified")])
    r = run.run_one(c, "tests", tmp_path, ex)
    assert len(calls) == 2 and r["verdict"] == "could_not_verify"


@pytest.mark.parametrize("verdict", ["needs_attention", "could_not_verify"])
def test_no_retry_on_test_failure_or_other_contree_error(tmp_path, verdict):
    c = cases()["fx-catch"]
    rec = record(c, verdict)
    rec["contree"] = {"failed": "sandbox command failed (exit 1)"}
    ex, calls = _multi_exec([rec, record(c, "verified")])
    r = run.run_one(c, "tests", tmp_path, ex)
    assert len(calls) == 1 and r["verdict"] == verdict and r["retried_after_contree_transport_error"] is False


def test_pinned_args_validation():
    a = types.SimpleNamespace(base_sha=None, head_sha=None)
    assert daily_run.pinned_args_problem(a, {"o/r": [1]}) is None
    a = types.SimpleNamespace(base_sha="a" * 40, head_sha=None)
    assert "together" in daily_run.pinned_args_problem(a, {"o/r": [1]})
    a = types.SimpleNamespace(base_sha="a" * 40, head_sha="xyz")
    assert "40-character" in daily_run.pinned_args_problem(a, {"o/r": [1]})
    a = types.SimpleNamespace(base_sha="a" * 40, head_sha="b" * 40)
    assert "exactly one" in daily_run.pinned_args_problem(a, {"o/r": [1, 2]})
    assert daily_run.pinned_args_problem(a, {"o/r": [1]}) is None


def test_source_pair_uses_pinned_sides_not_tips(tmp_path, monkeypatch):
    cmds = []
    monkeypatch.setattr(daily_run, "run", lambda c, log, **kw: (cmds.append([str(x) for x in c]), (0, ""))[1])
    item = {"pr": 7, "head_sha": "b" * 40, "base_ref": "main", "pinned_sides": {"main": "a" * 40, "pr": "b" * 40}}
    sp = daily_run.source_pair("o/r", item, tmp_path, tmp_path / "git.log", sys.executable, 60, product=True)
    assert sp["ok"] and sp["main_sha"] == "a" * 40 and sp["pr_sha"] == "b" * 40
    flat = " ".join(" ".join(c) for c in cmds)
    assert "pull/7" not in flat and "merge-base" not in flat and "origin/main" not in flat


def _hanging_chrome(tmp_path, monkeypatch):
    fake = tmp_path / "chrome"
    fake.write_text("#!/bin/sh\nsleep 30 &\nsleep 30\n")  # hangs, and leaves a helper holding the pipe
    fake.chmod(0o755)
    monkeypatch.setattr(reviewer, "find_chrome", lambda: str(fake))
    monkeypatch.setattr(reviewer, "PDF_TIMEOUT_S", 1)


def test_chrome_hang_falls_back_to_builtin_pdf(tmp_path, monkeypatch, capsys):
    import time
    _hanging_chrome(tmp_path, monkeypatch)
    html = tmp_path / "r.html"
    html.write_text("<h1>Verdict: VERIFIED</h1><p>x</p><ul><li>a</li></ul><table><tr><td>1</td><td>2</td></tr></table>")
    t0 = time.time()
    err = reviewer.to_pdf(str(html), str(tmp_path / "r.pdf"))
    assert time.time() - t0 < 15
    assert err is None
    pdf = (tmp_path / "r.pdf").read_bytes()
    assert pdf.startswith(b"%PDF") and len(pdf) > 500
    assert "PDF timed out" in capsys.readouterr().err


def test_chrome_missing_falls_back(tmp_path, monkeypatch):
    monkeypatch.setattr(reviewer, "find_chrome", lambda: None)
    html = tmp_path / "r.html"
    html.write_text("<p>hello</p>")
    assert reviewer.to_pdf(str(html), str(tmp_path / "r.pdf")) is None
    assert (tmp_path / "r.pdf").stat().st_size > 0


def test_both_makers_failing_is_logged_error_not_verdict(tmp_path, monkeypatch, capsys):
    _hanging_chrome(tmp_path, monkeypatch)
    monkeypatch.setattr(reviewer, "_fallback_pdf", lambda h, p: (_ for _ in ()).throw(RuntimeError("x")))
    html = tmp_path / "r.html"
    html.write_text("<p>x</p>")
    err = reviewer.to_pdf(str(html), str(tmp_path / "r.pdf"))
    assert err.startswith("ERROR: PDF not generated") and "ERROR" in capsys.readouterr().err


def test_pr_report_with_hanging_chrome_keeps_verdict(tmp_path, monkeypatch):
    import shutil as sh
    from reports.generate import main as pr_main
    _hanging_chrome(tmp_path, monkeypatch)
    src = Path(__file__).resolve().parents[1] / "evals" / "fixtures" / "record_rev2_example.json"
    sh.copy(src, tmp_path / "rec.json")
    before = (tmp_path / "rec.json").read_text()
    assert pr_main([str(tmp_path / "rec.json"), "--out", str(tmp_path / "o"), "--formats", "md,html,pdf"]) == 0
    assert (tmp_path / "rec.json").read_text() == before
    pdfs = list((tmp_path / "o").rglob("*.pdf"))
    assert pdfs and all(p.stat().st_size > 0 for p in pdfs)


def test_report_failure_never_changes_exit_or_records(tmp_path, monkeypatch, capsys):
    import reports.pr_report as pr
    rec = {"id": "r", "verdict": "verified"}
    (tmp_path / "records.jsonl").write_text(json.dumps(rec) + "\n")

    def boom(*a, **k):
        raise subprocess.TimeoutExpired("chrome", 1)
    monkeypatch.setattr(pr, "render_run", boom)
    a = types.SimpleNamespace(no_report=False, report_dir=str(tmp_path / "out"))
    assert daily_run.reviewer_reports(tmp_path, a, [rec], "check") is None
    assert json.loads((tmp_path / "records.jsonl").read_text())["verdict"] == "verified"
    assert "verdicts are unchanged" in capsys.readouterr().err


def test_step_timings_recorded_and_shown(monkeypatch):
    from poc import run_progress
    clock = iter([100.0, 103.0, 110.0, 111.5])
    monkeypatch.setattr(run_progress.time, "time", lambda: next(clock))
    run_progress.reset_timings()
    run_progress.emit("fetch_pr")
    run_progress.emit("setup_lookup")
    run_progress.emit("setup_lookup")  # a progress tick does not split the step
    run_progress.note_model_call("claims", 4.24)
    t = run_progress.timings(now=120.0)
    assert t == {"fetch_pr": 3.0, "setup_lookup": 17.0}
    rec = {"per_run": [{"side": "old", "seconds": 2.0}, {"side": "new", "seconds": 3.0}, {"side": "old", "seconds": 1.0}],
           "verdict": "verified"}
    monkeypatch.setattr(run_progress, "timings", lambda now=None: {"fetch_pr": 3.0, "setup_lookup": 17.0})
    st = daily_run.step_timings(rec)
    assert st["sandbox prep (checkout)"] == 3.0 and st["Tavily setup lookup"] == 17.0
    assert st["tests (main side)"] == 3.0 and st["tests (PR side)"] == 3.0 and st["model call 1 (claims)"] == 4.2
    assert rec["verdict"] == "verified" and "timings" not in rec
