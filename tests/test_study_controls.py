"""Study runs leave the advisory swarm and operator approval off.

Command-line and benchmark runs make no swarm model calls unless --swarm or POC_SWARM is set.
Operator approval (POC_HITL) cannot run there: the run refuses to start. The operator console
turns both on itself.
"""
from __future__ import annotations

import argparse
import json

import pytest

from ops import bench, daily_run
from poc import agents, console_api, cost, hitl, model_provider

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
    assert rec["operator_approval"] == "off"
    assert prov.calls == []
    assert rec["cost"]["ai_calls"] == 1
    assert rec["cost"]["swarm"]["ai_calls"] == 0
    assert rec["verdict"] == "verified"


def test_switches_record_what_ran(tmp_path, monkeypatch):
    """A requested swarm that never starts, and an approval env that never reaches the step, stay off."""
    _quiet_env(monkeypatch)
    monkeypatch.setenv("POC_HITL", "1")
    monkeypatch.setenv("POC_CONSOLE", "1")
    monkeypatch.setenv("POC_HITL_DIR", str(tmp_path))
    cost.reset()
    skipped = _rec()
    runner = _runner(_Counting(), True)
    runner.model_skipped = "AI calls skipped because --no-probes was set"
    daily_run.finish(skipped, tmp_path, tmp_path / "work", 0.0, runner)
    assert skipped["swarm"] == "off"
    assert skipped["operator_approval"] == "off"
    assert runner.provider.calls == []

    asked = _rec()
    daily_run.finish(asked, tmp_path, tmp_path / "work", 0.0, _runner(None, True))
    assert asked["swarm"] == "off"
    assert asked["operator_approval"] == "off"

    from poc import hitl
    hitl.note_approval_ran()
    approved = _rec()
    daily_run.finish(approved, tmp_path, tmp_path / "work", 0.0, _runner(None, False))
    assert approved["operator_approval"] == "on"
    assert approved["swarm"] == "off"
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
    assert off["operator_approval"] == "off" and on["operator_approval"] == "off"
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
    assert "STOPPED" in err and "POC_HITL" in err and "command-line" in err and "console" in err

    monkeypatch.setenv("POC_HITL", "yes")
    monkeypatch.setenv("POC_CONSOLE", "1")  # the console marker must not unlock a benchmark
    with pytest.raises(SystemExit) as bench_run:
        daily_run.main(["--bench", "bench/benchmark-v0.csv", "--model-provider", "none"])
    assert bench_run.value.code not in (0, None)
    err = capsys.readouterr().err
    assert "STOPPED" in err and "benchmark" in err and "POC_HITL" in err and "console" in err

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
    assert rec["swarm"] == "on"

    monkeypatch.setenv("POC_CONSOLE", "1")
    assert hitl.hitl_enabled() is True
    assert hitl.study_operator_approval_stop(bench=False) is None
    assert hitl.study_operator_approval_stop(bench=True)


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
    env = captured["env"]
    assert env["POC_SWARM"] == "1"
    assert env["POC_HITL"] == "1"
    assert env["POC_CONSOLE"] == "1"
    assert env.get("POC_HITL_DIR")
