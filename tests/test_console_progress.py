"""Console progress during pytest. Study runs leave POC_PROGRESS_PATH unset."""
import os
from pathlib import Path

from ops import daily_run
from poc import run_progress


def test_run_tests_emits_before_and_after_each_pass(tmp_path, monkeypatch):
    progress = tmp_path / "progress.jsonl"
    monkeypatch.setenv("POC_PROGRESS_PATH", str(progress))
    monkeypatch.setattr(daily_run, "_contree_ready", lambda: False)

    def fake_run(*_args, **_kwargs):
        return 0, 0.1

    monkeypatch.setattr(daily_run, "run", fake_run)
    daily_run.run_tests(
        {"main": tmp_path, "pr": tmp_path},
        {"main": [], "pr": []},
        tmp_path, tmp_path, 1, "0", 30, 60,
        cwds={"main": tmp_path, "pr": tmp_path},
    )
    details = [event.get("detail") for event in run_progress.read_events(progress)]
    assert details.count("before run 1/1") == 2
    assert details.count("after run 1/1") == 2


def test_heartbeat_goes_to_stdout_progress_not_the_pytest_log(tmp_path, monkeypatch, capsys):
    progress = tmp_path / "progress.jsonl"
    monkeypatch.setenv("POC_PROGRESS_PATH", str(progress))
    monkeypatch.setattr(daily_run, "HEARTBEAT_S", 0.02)
    monkeypatch.setattr(daily_run.sandbox, "enabled", lambda: False)
    log = tmp_path / "pytest-main-1.log"
    rc, _secs = daily_run.run(
        ["python3", "-c", "import time; time.sleep(0.08)"],
        log,
        env={"PATH": os.environ.get("PATH", ""), "HOME": str(tmp_path)},
        timeout=5,
    )
    assert rc == 0
    assert "still running" not in log.read_text()
    details = [event.get("detail") or "" for event in run_progress.read_events(progress)]
    assert any(item.startswith("still running (") for item in details)
    assert "still running" in capsys.readouterr().out


def test_without_progress_path_the_log_has_no_heartbeat(tmp_path, monkeypatch):
    monkeypatch.delenv("POC_PROGRESS_PATH", raising=False)
    monkeypatch.setattr(daily_run.sandbox, "enabled", lambda: False)
    log = tmp_path / "quiet.log"
    rc, _secs = daily_run.run(
        ["python3", "-c", "print('ok')"],
        log,
        env={"PATH": os.environ.get("PATH", ""), "HOME": str(tmp_path)},
        timeout=5,
    )
    assert rc == 0
    text = log.read_text()
    assert "still running" not in text
    assert Path(log).exists()
