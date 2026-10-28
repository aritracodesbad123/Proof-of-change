"""Every way a check or batch can end still leaves a PDF: placeholder before each check (kept if the process is
killed), refusals before the run starts, provider refusal, bench mode, report errors, a stop signal, and the
console's time-limit kill."""
import json
import os
import shutil
import signal
import subprocess
import sys
import time
import types
from pathlib import Path

import pytest

from ops import bench
from ops import daily_run as dr
from poc import model_provider, pdf_always

ROOT = Path(__file__).resolve().parents[1]
SYN = ROOT / "tests" / "fixtures" / "bench" / "inputs-synthetic.csv"


def _text(p: Path) -> str:
    data = p.read_bytes()
    assert data.startswith(b"%PDF") and len(data) > 200
    if shutil.which("pdftotext"):
        return subprocess.run(["pdftotext", str(p), "-"], capture_output=True, text=True).stdout
    return data.decode("latin-1")


def _only_summary(root: Path) -> Path:
    found = list(root.rglob("SUMMARY.pdf"))
    assert len(found) == 1, found
    return found[0]


@pytest.fixture
def reports(tmp_path, monkeypatch):
    d = tmp_path / "reports"
    monkeypatch.setenv("POC_REPORT_DIR", str(d))
    return d


def test_builtin_maker_works_without_reportlab(tmp_path, monkeypatch):
    import builtins
    real = builtins.__import__

    def no_reportlab(name, *a, **k):
        if name.startswith("reportlab"):
            raise ImportError("no reportlab")
        return real(name, *a, **k)
    monkeypatch.setattr(builtins, "__import__", no_reportlab)
    p = pdf_always.nogo_summary(tmp_path, "x", "the built-in PDF maker is missing")
    assert "NO-GO" in _text(p) and "missing" in _text(p)


def test_placeholder_is_left_when_check_is_stopped_partway(tmp_path):
    a = types.SimpleNamespace(no_report=False, report_dir=str(tmp_path / "o"))

    def killed(*_a, **_k):
        raise SystemExit(143)
    orig = dr.new_record
    dr.new_record = killed
    try:
        with pytest.raises(SystemExit):
            dr.test_pr("o/lib", {"pkg": "lib"}, {"pr": 5, "diff": "", "title": "t"}, tmp_path / "run",
                       tmp_path / "work", a, {})
    finally:
        dr.new_record = orig
    t = _text(tmp_path / "o" / "lib-5" / "REPORT.pdf")
    assert "COULD NOT VERIFY" in t and "did not finish" in t


def test_placeholder_survives_a_real_kill(tmp_path):
    code = ("import sys,time; sys.path.insert(0, %r); from poc import pdf_always;"
            "pdf_always.placeholder(%r, 'lib-9', 'o/lib#9'); print('ready', flush=True); time.sleep(60)"
            % (str(ROOT), str(tmp_path)))
    p = subprocess.Popen([sys.executable, "-c", code], stdout=subprocess.PIPE, text=True)
    assert p.stdout.readline().strip() == "ready"
    p.send_signal(signal.SIGKILL)
    p.wait(timeout=10)
    assert "COULD NOT VERIFY" in _text(tmp_path / "lib-9" / "REPORT.pdf")


@pytest.mark.parametrize("how", ["return", "exit_text"])
def test_early_refusal_writes_nogo_summary(reports, monkeypatch, how):
    def refuse(argv=None):
        if how == "exit_text":
            raise SystemExit("refusing: --base-sha / --head-sha need exactly one --pr")
        print("Stopped: only 1 GB of free disk space", file=sys.stderr)
        return 2
    monkeypatch.setattr(dr, "_main", refuse)
    if how == "exit_text":
        with pytest.raises(SystemExit):
            dr.main([])
    else:
        assert dr.main([]) == 2
    t = _text(_only_summary(reports))
    assert "NO-GO" in t and "could not run" in t
    assert ("free disk space" if how == "return" else "head-sha") in t


def test_provider_refusal_writes_nogo_summary(reports, monkeypatch):
    def provider_refused(argv=None):
        print("the model provider refused the key", file=sys.stderr)
        return 1
    monkeypatch.setattr(dr, "_main", provider_refused)
    assert dr.main([]) == 1
    assert "provider refused" in _text(_only_summary(reports))


def test_no_report_flag_and_success_write_no_extra_pdf(reports, monkeypatch):
    monkeypatch.setattr(dr, "_main", lambda argv=None: 0)
    assert dr.main([]) == 0
    monkeypatch.setattr(dr, "_main", lambda argv=None: 2)
    assert dr.main(["--no-report"]) == 2
    assert not reports.exists() or not list(reports.rglob("*.pdf"))


def test_bench_refusal_writes_nogo_summary(tmp_path, monkeypatch):
    monkeypatch.setenv(model_provider.KEY_ENV, "test-key")
    monkeypatch.setattr(dr, "sync_to_origin_main", lambda *a, **k: (_ for _ in ()).throw(AssertionError("sync")))
    monkeypatch.setattr(dr, "given_commit", lambda root, expected: "a" * 40)
    p = tmp_path / "x-answers.csv"
    p.write_text(SYN.read_text())
    out = tmp_path / "pdfs"
    assert dr.main(["--bench", str(p), "--ids", "B01", "--expect-commit", "a" * 40, "--unsafe-no-sandbox",
                    "--report-dir", str(out)]) == 2
    t = _text(out / "SUMMARY.pdf")
    assert "NO-GO" in t and "answer key" in t


def test_bench_cases_write_pdfs_even_when_one_crashes(tmp_path, monkeypatch):
    a = types.SimpleNamespace(bench=str(SYN), ids="B01,B02", provider=None, bench_out=str(tmp_path / "out"),
                              swarm=False, work_dir=str(tmp_path / "w"), ops_dir=str(tmp_path), python="python3",
                              report_dir=str(tmp_path / "pdfs"), no_report=False, console_job=False, pr=None)
    monkeypatch.setattr(model_provider, "auth_refusal", lambda *_: None)
    monkeypatch.setattr(dr, "resolve_python", lambda p: p)
    monkeypatch.setattr(dr, "detect_machine_type", lambda: {})
    import poc.hitl as hitl
    monkeypatch.setattr(hitl, "study_operator_approval_stop", lambda **k: None)
    calls = []

    def case(dr_, a_, row, *rest):
        calls.append(row["id"])
        if len(calls) == 1:
            raise TimeoutError("the case timed out")
        return {"verdict": "needs_attention", "reason": "a test fails on the PR side"}
    monkeypatch.setattr(bench, "run_case", case)
    assert bench.run(a, dr) == 1
    pdfs = tmp_path / "pdfs"
    first, second = calls
    assert "TimeoutError" in _text(pdfs / first / "REPORT.pdf")
    assert "NEEDS ATTENTION" in _text(pdfs / second / "REPORT.pdf")
    assert "NO-GO" in _text(pdfs / "SUMMARY.pdf")


def test_report_error_writes_each_pdf_and_summary(tmp_path, monkeypatch):
    import reports.pr_report as pr
    monkeypatch.setattr(pr, "render_run", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("render broke")))
    a = types.SimpleNamespace(no_report=False, report_dir=str(tmp_path / "o"))
    recs = [{"library": "lib", "pr": 1, "verdict": "verified", "reason": "ok", "logs": "lib-1/"},
            {"library": "lib", "pr": 2, "verdict": "could_not_verify", "reason": "build timed out", "logs": "lib-2/"}]
    assert dr.reviewer_reports(tmp_path, a, recs, "check") is True
    o = tmp_path / "o"
    assert "VERIFIED" in _text(o / "lib-1" / "REPORT.pdf")
    assert "build timed out" in _text(o / "lib-2" / "REPORT.pdf")
    assert "NO-GO" in _text(o / "SUMMARY.pdf")


def test_nothing_tested_still_writes_summary(tmp_path):
    a = types.SimpleNamespace(no_report=False, report_dir=str(tmp_path / "o"))
    assert dr.reviewer_reports(tmp_path, a, [], "daily summary") is True
    assert "nothing tested" in _text(tmp_path / "o" / "SUMMARY.pdf")


def test_sigterm_writes_nogo_summary(tmp_path):
    code = ("import sys,time; sys.path.insert(0, %r); import ops.daily_run as d;"
            "d._main = lambda argv=None: (print('ready', flush=True), time.sleep(60));"
            "sys.exit(d.main([]))" % str(ROOT))
    env = {k: v for k, v in os.environ.items()}
    env["POC_REPORT_DIR"] = str(tmp_path)
    p = subprocess.Popen([sys.executable, "-c", code], stdout=subprocess.PIPE, text=True, env=env, cwd=str(ROOT))
    assert p.stdout.readline().strip() == "ready"
    p.send_signal(signal.SIGTERM)
    assert p.wait(timeout=30) == 143
    assert "SIGTERM" in _text(_only_summary(tmp_path))


def test_console_time_limit_kill_writes_cnv_pdf(tmp_path, monkeypatch):
    from poc import console_api
    monkeypatch.setattr(console_api, "REPORTS_DAILY", tmp_path)
    p = Path(console_api.timeout_pdfs("me/demo", 3, 1200))
    assert p.name == "SUMMARY.pdf" and "NO-GO" in _text(p)
    t = _text(p.parent / "demo-3" / "REPORT.pdf")
    assert "COULD NOT VERIFY" in t and "time limit" in t


def test_console_job_timeout_path_calls_timeout_pdfs(tmp_path, monkeypatch):
    from poc import console_api, session_key
    monkeypatch.delenv("NEBIUS_API_KEY", raising=False)
    monkeypatch.delenv("CODESPACES", raising=False)
    monkeypatch.setattr(console_api, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(console_api, "RUNS_ROOT", tmp_path / "ops" / "runs")
    monkeypatch.setattr(console_api, "REPORTS_DAILY", tmp_path / "reports")
    monkeypatch.setattr(console_api, "console_run_flags",
                        lambda *_a, **_k: console_api.ConsoleRunPlan([], None, False, None))
    session_key.set_key("sess-pdf", "k" * 20)
    monkeypatch.setattr(console_api, "_read_child", lambda proc, logf, collected, deadline: (-9, True))
    monkeypatch.setattr(console_api.subprocess, "Popen", lambda *a, **k: types.SimpleNamespace())
    monkeypatch.setattr(console_api, "find_record_for_pr", lambda *a, **k: None)
    holder = {}

    class FakeThread:
        def __init__(self, target=None, daemon=None):
            holder["target"] = target

        def start(self):
            pass
    monkeypatch.setattr(console_api.threading, "Thread", FakeThread)
    job = console_api.start_check("https://github.com/me/demo/pull/3", model_provider="nebius",
                                  session_token="sess-pdf")
    holder["target"]()
    session_key.clear_key("sess-pdf")
    status = console_api.get_job(job["id"])["status"]
    monkeypatch.undo()
    s = _only_summary(tmp_path / "reports")
    assert "NO-GO" in _text(s) and (s.parent / "demo-3" / "REPORT.pdf").exists()
    assert status == "timed out"
