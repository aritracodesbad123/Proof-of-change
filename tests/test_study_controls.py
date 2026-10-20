"""Study runs leave the advisory swarm and operator approval off.

Command-line and benchmark runs make no swarm model calls unless --swarm or POC_SWARM is set.
Operator approval (POC_HITL) cannot run there: the run refuses to start. The operator console
turns both on itself.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from ops import bench, daily_run
from poc import agents, console_api, cost, hitl, model_provider

ROOT = Path(__file__).resolve().parents[1]
FIX = model_provider.RECORDED_DIR
SUPER = "nvidia/nemotron-3-super-120b-a12b"
USAGE = {"prompt_tokens": 1_000_000, "completion_tokens": 1_000_000,
         "completion_tokens_details": {"reasoning_tokens": 600_000}}


def _rec() -> dict:
    return {
        "verdict": "verified",
        "reason": "tests match",
        "title": "feature groups",
        "repo": "rasbt/mlxtend",
        "pr": {"repo": "rasbt/mlxtend", "number": 1229, "url": "u", "head_sha": "a" * 40},
        "files": {"package_py": [], "compiled": [], "other": []},
        "per_run": [],
        "finding_labels": ["proven"],
        "comparison": {"regressions": []},
        "probes": {"items": [{"id": "groups-columns", "about": "groups", "labels": ["proven"]}],
                   "summary": {}},
    }


def _runner(provider, swarm: bool):
    return argparse.Namespace(provider=provider, swarm=swarm, model_skipped=None,
                              model_provider="recorded", model_fallback=None)


class _Counting(model_provider.Provider):
    name = "nebius"
    blind = True

    def complete_json(self, task, system, user, schema, ctx):
        cost.record_call(SUPER, USAGE, ok=True)
        self._remember(task, True)
        if task == "judge":
            return {"labels": [{"id": "F1", "label": "proven", "reason": "recorded"}]}
        if task == "helper":
            return {"notes": ["optional"]}
        if task == "summary":
            return {"text": "Verdict stays verified.", "quotes": []}
        return {"ok": True}


def _quiet_env(monkeypatch):
    monkeypatch.delenv("POC_SWARM", raising=False)
    monkeypatch.delenv("POC_HITL", raising=False)
    monkeypatch.delenv("POC_CONSOLE", raising=False)
    monkeypatch.delenv(model_provider.KEY_ENV, raising=False)


def test_swarm_off_makes_no_swarm_calls_and_records_off(tmp_path, monkeypatch):
    _quiet_env(monkeypatch)
    cost.reset()
    cost.record_call(SUPER, USAGE, ok=True)  # a study call, not a swarm call
    prov = _Counting()
    rec = _rec()
    daily_run.finish(rec, tmp_path, tmp_path / "work", 0.0, _runner(prov, False))
    assert rec["swarm"] == "off"
    assert rec["swarm_requested"] is False
    assert rec["operator_approval"] == "off"
    assert rec["operator_approval_requested"] is False
    assert prov.calls == []
    assert rec["cost"]["ai_calls"] == 1
    assert rec["cost"]["swarm"]["ai_calls"] == 0
    assert rec["verdict"] == "verified"


def test_switches_record_what_ran(tmp_path, monkeypatch):
    """A switch that is set is recorded even when the step is skipped."""
    from evals import score_bench as sb

    _quiet_env(monkeypatch)

    def finish_one(runner):
        cost.reset()
        rec = _rec()
        daily_run.finish(rec, tmp_path, tmp_path / "work", 0.0, runner)
        return rec

    # No model: the swarm was requested and never started.
    none = finish_one(_runner(None, True))
    assert none["swarm_requested"] is True and none["swarm"] == "off"
    assert none["operator_approval_requested"] is False and none["operator_approval"] == "off"
    assert sb.study_record_problems("no-model.json", none)

    # --no-probes skips the swarm call and still records the request.
    probes = _runner(_Counting(), True)
    probes.baseline = "full"
    probes.no_probes = True
    probes.model_note = "recorded"
    daily_run.skip_unused_model(probes)
    assert "no-probes" in probes.model_skipped
    skipped = finish_one(probes)
    assert skipped["swarm_requested"] is True and skipped["swarm"] == "off"
    assert probes.provider.calls == []
    assert sb.study_record_problems("no-probes.json", skipped)

    # A baseline with no claim probes drops the provider. The request stays on the record.
    base = _runner(_Counting(), True)
    base.baseline = "tests"
    base.no_probes = False
    base.model_note = "recorded"
    daily_run.skip_unused_model(base)
    assert base.provider is None and "does not use claim probes" in base.model_skipped
    recorded = finish_one(base)
    assert recorded["swarm_requested"] is True and recorded["swarm"] == "off"
    assert sb.study_record_problems("baseline.json", recorded)

    # POC_HITL is set, but the approval step is never entered.
    monkeypatch.setenv("POC_HITL", "1")
    monkeypatch.setenv("POC_CONSOLE", "1")
    monkeypatch.setenv("POC_HITL_DIR", str(tmp_path))
    held = finish_one(_runner(None, False))
    assert held["operator_approval_requested"] is True and held["operator_approval"] == "off"
    assert held["swarm_requested"] is False and held["swarm"] == "off"
    assert sb.study_record_problems("hitl.json", held)

    # Both switches off: the four fields are present and the study scorer accepts them.
    monkeypatch.delenv("POC_HITL", raising=False)
    off = finish_one(_runner(_Counting(), False))
    assert off["swarm_requested"] is False and off["operator_approval_requested"] is False
    assert off["swarm"] == "off" and off["operator_approval"] == "off"
    assert sb.study_record_problems("off.json", off) == []

    hitl.note_approval_ran()
    approved = finish_one(_runner(None, False))
    assert approved["operator_approval"] == "on" and approved["operator_approval_requested"] is False
    assert approved["swarm"] == "off" and approved["swarm_requested"] is False
    assert hitl.approval_ran() is False


def test_swarm_on_records_its_calls_separately(tmp_path, monkeypatch):
    _quiet_env(monkeypatch)
    cost.reset()
    prov = _Counting()
    prov.complete_json("claims", "s", "u", {}, {})  # study call, outside the swarm
    prov.calls.clear()
    rec = _rec()
    daily_run.finish(rec, tmp_path, tmp_path / "work", 0.0, _runner(prov, True))
    assert rec["swarm"] == "on"
    assert rec["swarm_requested"] is True
    assert rec["operator_approval_requested"] is False
    assert rec["verdict"] == "verified"
    assert [c["task"] for c in prov.calls] == ["judge", "helper", "summary"]
    assert rec["cost"]["ai_calls"] == 1
    assert rec["cost"]["ai_cost_usd"] == 1.2
    assert rec["cost"]["swarm"]["ai_calls"] == 3
    assert rec["cost"]["swarm"]["ai_cost_usd"] == 3.6
    assert rec["cost"]["total_cost_usd"] == round(
        rec["cost"]["ai_cost_usd"] + rec["cost"]["computer_cost_usd"], 6)


def test_recorded_fixture_verdict_is_identical_with_swarm_on_or_off(tmp_path, monkeypatch):
    _quiet_env(monkeypatch)
    assert (FIX / "rasbt" / "mlxtend" / "1229.json").is_file()

    def once(swarm: bool, folder: str):
        cost.reset()
        prov = model_provider.RecordedProvider(FIX)
        rec = _rec()
        before = rec["verdict"]
        prdir = tmp_path / folder
        prdir.mkdir()
        daily_run.finish(rec, prdir, prdir / "work", 0.0, _runner(prov, swarm))
        return before, rec, [c["task"] for c in prov.calls]

    before_off, off, off_calls = once(False, "off")
    before_on, on, on_calls = once(True, "on")
    assert off["verdict"] == before_off == on["verdict"] == before_on
    assert off["reason"] == on["reason"]
    assert off["swarm"] == "off" and on["swarm"] == "on"
    assert off["swarm_requested"] is False and on["swarm_requested"] is True
    assert off["operator_approval"] == "off" and on["operator_approval"] == "off"
    assert off["operator_approval_requested"] is False and on["operator_approval_requested"] is False
    assert off_calls == []
    assert on_calls == ["judge", "helper", "summary"]
    saved = json.loads((tmp_path / "off" / "record.json").read_text())
    assert saved["swarm"] == "off" and saved["operator_approval"] == "off"


def test_poc_swarm_env_and_cli_flag(monkeypatch, capsys):
    _quiet_env(monkeypatch)
    assert agents.swarm_enabled(False) is False
    assert agents.swarm_enabled(True) is True
    monkeypatch.setenv("POC_SWARM", "1")
    assert agents.swarm_enabled(False) is True
    monkeypatch.setenv("POC_SWARM", "on")
    assert agents.swarm_enabled(False) is True
    monkeypatch.setenv("POC_SWARM", "no")
    assert agents.swarm_enabled(False) is False

    seen = {}
    real = agents.swarm_enabled

    def spy(flag=False):
        seen["flag"] = flag
        return real(flag)

    monkeypatch.setattr(daily_run.agents, "swarm_enabled", spy)
    monkeypatch.delenv("POC_SWARM", raising=False)
    with pytest.raises(SystemExit) as missing:
        daily_run.main(["--model-provider", "nebius"])
    assert missing.value.code not in (0, None)
    assert seen["flag"] is False
    assert model_provider.KEY_ENV in capsys.readouterr().err

    with pytest.raises(SystemExit):
        daily_run.main(["--swarm", "--model-provider", "nebius"])
    assert seen["flag"] is True


def test_cli_and_benchmark_refuse_to_start_when_poc_hitl_is_on(monkeypatch, capsys):
    _quiet_env(monkeypatch)
    monkeypatch.setenv("POC_HITL", "1")
    with pytest.raises(SystemExit) as cli:
        daily_run.main(["--model-provider", "none", "--select-only"])
    assert cli.value.code not in (0, None)
    err = capsys.readouterr().err
    assert "STOPPED" in err and "POC_HITL" in err and "command-line" in err

    monkeypatch.setenv("POC_HITL", "yes")
    monkeypatch.setenv("POC_CONSOLE", "1")  # the console marker must not unlock a benchmark
    with pytest.raises(SystemExit) as bench_run:
        daily_run.main(["--bench", "bench/benchmark-v0.csv", "--model-provider", "none"])
    assert bench_run.value.code not in (0, None)
    err = capsys.readouterr().err
    assert "STOPPED" in err and "benchmark" in err and "POC_HITL" in err

    monkeypatch.setenv("POC_HITL", "on")
    code = bench.run(argparse.Namespace(), None)
    assert code == 2
    assert "benchmark" in capsys.readouterr().err


def test_operator_approval_cannot_be_turned_on_outside_the_console(monkeypatch, capsys, tmp_path):
    _quiet_env(monkeypatch)
    monkeypatch.setenv("POC_HITL", "1")
    monkeypatch.setenv("POC_HITL_DIR", str(tmp_path))
    assert hitl.hitl_enabled() is False
    assert hitl.study_operator_approval_stop(bench=False)
    with pytest.raises(SystemExit) as unknown:
        daily_run.main(["--operator-approval", "--model-provider", "none"])
    assert unknown.value.code == 2
    assert "operator-approval" in capsys.readouterr().err

    cost.reset()
    rec = _rec()
    daily_run.finish(rec, tmp_path, tmp_path / "work", 0.0, _runner(model_provider.RecordedProvider(FIX), True))
    assert rec["operator_approval"] == "off"
    assert rec["operator_approval_requested"] is True
    assert rec["swarm"] == "on"
    assert rec["swarm_requested"] is True

    monkeypatch.setenv("POC_CONSOLE", "1")
    assert hitl.hitl_enabled() is True
    stopped = hitl.study_operator_approval_stop(bench=False)
    assert stopped and "command-line" in stopped and "POC_HITL" in stopped
    assert hitl.study_operator_approval_stop(bench=True)


def test_poc_hitl_refuses_command_line_and_study_even_with_the_console_marker(monkeypatch, capsys):
    """POC_CONSOLE must not let a command-line or study run start while POC_HITL is set."""
    _quiet_env(monkeypatch)
    monkeypatch.setenv("POC_HITL", "1")
    monkeypatch.setenv("POC_CONSOLE", "1")
    monkeypatch.setenv("POC_CONSOLE_JOB", "1")  # an environment variable must not open the path
    with pytest.raises(SystemExit) as cli:
        daily_run.main(["--model-provider", "none", "--select-only"])
    assert cli.value.code not in (0, None)
    err = capsys.readouterr().err
    assert "STOPPED" in err and "command-line" in err and "POC_HITL" in err

    with pytest.raises(SystemExit) as study:
        daily_run.main(["--bench", "bench/benchmark-v0.csv", "--model-provider", "none"])
    assert study.value.code not in (0, None)
    err = capsys.readouterr().err
    assert "STOPPED" in err and "benchmark" in err and "POC_HITL" in err

    with pytest.raises(SystemExit) as flagged_bench:
        daily_run.main(["--console-job", "--bench", "bench/benchmark-v0.csv", "--model-provider", "none"])
    assert flagged_bench.value.code not in (0, None)
    err = capsys.readouterr().err
    assert "STOPPED" in err and "benchmark" in err and "POC_HITL" in err

    with pytest.raises(SystemExit) as flagged_daily:
        daily_run.main(["--console-job", "--model-provider", "none", "--select-only"])
    assert flagged_daily.value.code not in (0, None)
    assert "command-line" in capsys.readouterr().err


def test_console_child_gets_past_the_operator_approval_stop(tmp_path):
    """Start daily_run the way the console does, as a real process, and show it passes the stop."""
    url = "https://github.com/me/demo/pull/3"
    built = console_api.console_daily_run_argv(url, "none", [])
    assert "--console-job" in built and "--swarm" in built and "--pr" in built
    argv = [sys.executable, built[1], *built[2:]]
    env = os.environ.copy()
    env["POC_HITL"] = "1"
    env["POC_HITL_DIR"] = str(tmp_path)
    env["POC_CONSOLE"] = "1"
    env["POC_SWARM"] = "1"
    env["POC_PROGRESS_PATH"] = str(tmp_path / "progress.jsonl")
    # A dirty checkout stops at the git check, which runs after the operator-approval check,
    # and it keeps this test from fetching or switching branches.
    marker = ROOT / "console-job-probe.txt"
    marker.write_text("probe\n")
    try:
        proc = subprocess.run(argv, cwd=ROOT, env=env, capture_output=True, text=True, timeout=90)
    finally:
        marker.unlink(missing_ok=True)
    text = proc.stderr + proc.stdout
    assert "operator approval is turned on" not in text
    assert "uncommitted changes" in text
    assert proc.returncode != 0


def test_swarm_on_study_uses_a_labelled_folder():
    plain = Path("runs/bench-v0")
    assert bench.labelled_study_out(plain, False) == plain
    labelled = bench.labelled_study_out(plain, True)
    assert labelled.name == "bench-v0-swarm-on"
    assert labelled.parent == plain.parent
    assert bench.labelled_study_out(labelled, True) == labelled


def test_console_turns_swarm_and_approval_on_explicitly(monkeypatch, tmp_path):
    _quiet_env(monkeypatch)
    monkeypatch.setattr(console_api, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(console_api, "find_record_for_pr", lambda *a, **k: None)
    (tmp_path / "ops").mkdir()
    captured = {}

    class Proc:
        stdout = iter(())

        def wait(self):
            return 0

    def fake_popen(argv, **kw):
        captured["argv"] = list(argv)
        captured["env"] = kw.get("env") or {}
        return Proc()

    holder = {}

    class FakeThread:
        def __init__(self, target=None, daemon=None):
            holder["target"] = target

        def start(self):
            pass

    monkeypatch.setattr(console_api.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(console_api.threading, "Thread", FakeThread)
    job = console_api.start_check("https://github.com/me/demo/pull/3", model_provider="none")
    assert job["status"] == "queued"
    holder["target"]()
    assert "--swarm" in captured["argv"]
    assert "--console-job" in captured["argv"]
    env = captured["env"]
    assert env["POC_SWARM"] == "1"
    assert env["POC_HITL"] == "1"
    assert env["POC_CONSOLE"] == "1"
    assert env.get("POC_HITL_DIR")
