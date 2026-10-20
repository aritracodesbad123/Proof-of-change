"""A Nebius run must not start without a key, and the record names the provider that actually ran."""
import argparse
import json

import pytest

from evals import ablation
from evals import patchguru_runner as pg
from ops import daily_run
from poc import model_provider


def _item():
    return {"pr": 1, "head_sha": "a" * 40, "url": "u", "title": "t", "body": "results unchanged", "base_ref": "main",
            "author": "x", "updated_at_utc": "", "updated_at_ist": "", "ci_state": "", "ci_detail": "",
            "files": {"package_py": [], "compiled": [], "other": []}}


def _args(**kw):
    base = dict(runs=3, workers="4", test_timeout=1, run_timeout=1, build_timeout=1, python="3.12",
                baseline="full", model_provider="nebius", provider=None, model_note=None,
                model_skipped=None, model_fallback=None)
    return argparse.Namespace(**(base | kw))


def _record(a):
    return daily_run.new_record("o/r", {"dist": "r", "pkg": "r"}, _item(), a, {}, "2026-10-15")


class _Resp:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self):
        return self.payload


def test_missing_key_refuses_before_the_run_starts(monkeypatch, capsys):
    monkeypatch.delenv(model_provider.KEY_ENV, raising=False)
    called = {}
    monkeypatch.setattr(daily_run, "sync_to_origin_main", lambda *_a, **_k: called.setdefault("sync", True))
    with pytest.raises(SystemExit) as e:
        daily_run.main(["--date", "x-never"])
    assert e.value.code not in (0, None)
    err = capsys.readouterr().err
    assert model_provider.KEY_ENV in err and "is not set" in err
    assert "--model-provider none" in err and "never printed" in err
    assert "sync" not in called


def test_explicit_nebius_with_an_empty_key_refuses(monkeypatch, capsys):
    monkeypatch.setenv(model_provider.KEY_ENV, "   ")
    monkeypatch.setattr(daily_run, "sync_to_origin_main", lambda *_a, **_k: None)
    with pytest.raises(SystemExit) as e:
        daily_run.main(["--model-provider", "nebius", "--date", "x-never"])
    assert e.value.code not in (0, None)
    err = capsys.readouterr().err
    assert model_provider.KEY_ENV in err and "is empty" in err
    assert "   " not in err
    assert "--model-provider none" in err


def test_empty_string_key_is_refused_and_not_printed(monkeypatch, capsys):
    monkeypatch.setenv(model_provider.KEY_ENV, "")
    with pytest.raises(SystemExit) as e:
        daily_run.main(["--model-provider", "nebius"])
    assert e.value.code not in (0, None)
    err = capsys.readouterr().err
    assert "is empty" in err and "super-secret" not in err


def test_only_explicit_none_and_recorded_may_start_without_a_key():
    assert model_provider.key_refusal("none", env={}) is None
    assert model_provider.key_refusal("recorded", env={}) is None
    assert model_provider.key_refusal("nebius", env={})
    assert model_provider.key_refusal("nebius", env={model_provider.KEY_ENV: ""})
    assert model_provider.key_refusal("nebius", env={model_provider.KEY_ENV: "k"}) is None


def test_mocked_provider_records_nebius(monkeypatch):
    secret = "super-secret-value"
    monkeypatch.setenv(model_provider.KEY_ENV, secret)

    def fake(req, timeout=None):
        assert secret in req.get_header("Authorization")
        body = json.dumps({"choices": [{"message": {"content": json.dumps({"claims": []})}}]}).encode()
        return _Resp(body)

    monkeypatch.setattr(model_provider.urllib.request, "urlopen", fake)
    prov, note = model_provider.select("nebius")
    assert prov.complete_json("claims", "s", "u", {}, {}) == {"claims": []}
    rec = _record(_args(provider=prov, model_note=note, model_provider="nebius"))
    assert rec["model_provider_used"] == "nebius"
    assert "model_provider_fallback" not in rec
    assert secret not in json.dumps(rec)


def test_provider_none_records_that_the_ai_was_off():
    prov, note = model_provider.select("none", env={})
    assert prov is None and "the AI was off" in note
    rec = _record(_args(model_provider="none", provider=None, model_note=note))
    assert rec["model_provider_used"] == "none"
    assert "the AI was off" in json.dumps(rec)


def test_a_failed_call_is_recorded_as_a_fallback(monkeypatch):
    secret = "super-secret-value"

    def boom(req, timeout=None):
        raise OSError("down")

    monkeypatch.setattr(model_provider.urllib.request, "urlopen", boom)
    prov = model_provider.NebiusProvider(secret)
    with pytest.raises(model_provider.ProviderError):
        prov.complete_json("claims", "s", "u", {}, {})
    rec = _record(_args(provider=prov, model_note="model provider: nebius (Token Factory, live)",
                        model_provider="nebius"))
    assert rec["model_provider_used"] == "none"
    assert "fell back or failed" in rec["model_provider_fallback"]
    assert secret not in json.dumps(rec)


def test_a_skipped_call_is_recorded():
    rec = _record(_args(model_provider="nebius", provider=None,
                        model_skipped="AI calls skipped: baseline tests does not use claim probes"))
    assert rec["model_provider_used"] == "none"
    assert "skipped" in rec["model_provider_fallback"]


def test_ablation_refuses_a_nebius_run_without_a_key(monkeypatch, tmp_path, capsys):
    monkeypatch.delenv(model_provider.KEY_ENV, raising=False)
    code = ablation.main(["--run", "--out-dir", str(tmp_path), "--model-provider", "nebius"])
    assert code == 1
    err = capsys.readouterr().err
    assert model_provider.KEY_ENV in err and "is not set" in err


SUPER = "nvidia/nemotron-3-super-120b-a12b"
USAGE = {"prompt_tokens": 1_000_000, "completion_tokens": 1_000_000,
         "completion_tokens_details": {"reasoning_tokens": 600_000}}
STALE = "stale note from an earlier pull request"
PROBE_NOTE = "the AI answered but no probe was usable, so only fixed probes ran"


@pytest.mark.parametrize("first,second", [("good", "bad"), ("bad", "good")])
def test_each_pull_request_keeps_its_own_stamp_and_cost(monkeypatch, tmp_path, first, second):
    """Two pull requests, one shared provider. Each stamp and each cost cover only that pull request's calls."""
    secret = "super-secret-value"
    monkeypatch.setenv(model_provider.KEY_ENV, secret)
    state = {"ok": True}

    def fake(req, timeout=None):
        assert secret in (req.get_header("Authorization") or "")
        if not state["ok"]:
            raise OSError("down")
        body = json.dumps({"model": SUPER, "usage": USAGE,
                           "choices": [{"message": {"content": json.dumps({"ok": True})}}]}).encode()
        return _Resp(body)

    def fake_pair(repo, cfg, item, prdir, work, a, rec):
        state["ok"] = item["kind"] == "good"
        for task in ("claims", "probes"):
            if state["ok"]:
                a.provider.complete_json(task, "s", "u", {}, {})
            else:
                with pytest.raises(model_provider.ProviderError):
                    a.provider.complete_json(task, "s", "u", {}, {})
        if not state["ok"]:
            a.model_fallback = PROBE_NOTE
        return rec

    monkeypatch.setattr(model_provider.urllib.request, "urlopen", fake)
    monkeypatch.setattr(daily_run, "sandbox_refusal", lambda *_a, **_k: None)
    monkeypatch.setattr(daily_run, "test_source_pair", fake_pair)
    prov, note = model_provider.select("nebius")
    state["ok"] = True
    prov.complete_json("claims", "s", "u", {}, {})  # a call from before this run's first pull request
    a = _args(provider=prov, model_note=note, model_provider="nebius",
              model_skipped="AI calls skipped because --no-probes was set", swarm=True)
    daily_run.begin_pr(a)
    assert a.model_skipped == "AI calls skipped because --no-probes was set"
    assert prov.calls == []
    a.model_skipped = None

    cfg = {"dist": "r", "pkg": "r", "nightly": False}
    records = {}
    for n, kind in enumerate((first, second), start=1):
        a.model_fallback = STALE
        item = _item() | {"pr": n, "diff": "", "kind": kind, "head_sha": f"{n}" * 40}
        rec = daily_run.test_pr("o/r", cfg, item, tmp_path / "runs", tmp_path / "work", a, {})
        records[kind] = rec
        dumped = json.dumps(rec)
        assert secret not in dumped and STALE not in dumped

    good, bad = records["good"]["cost"], records["bad"]["cost"]
    assert records["good"]["model_provider_used"] == "nebius"
    assert "model_provider_fallback" not in records["good"]
    assert records["bad"]["model_provider_used"] == "none"
    assert "fell back or failed" in records["bad"]["model_provider_fallback"]
    assert PROBE_NOTE in records["bad"]["model_provider_fallback"]
    # claims+probes stay on the study line. judge/helper/summary are on cost.swarm, not in the headline total.
    assert records["good"]["swarm"] == "on" and records["bad"]["swarm"] == "on"
    assert records["good"]["swarm_requested"] is True and records["bad"]["swarm_requested"] is True
    assert records["good"]["operator_approval"] == "off"
    assert records["good"]["operator_approval_requested"] is False
    assert good["ai_calls"] == 2 and good["failed_ai_calls"] == 0
    assert good["input_tokens"] == 2_000_000 and good["output_tokens"] == 2_000_000
    assert good["thinking_tokens"] == 1_200_000 and good["ai_cost_usd"] == 2.4
    assert good["swarm"]["ai_calls"] == 3 and good["swarm"]["input_tokens"] == 3_000_000
    assert good["swarm"]["ai_cost_usd"] == 3.6
    assert good["total_cost_usd"] == round(good["ai_cost_usd"] + good["computer_cost_usd"], 6)
    # helper retries once on Nano after Lightning fails → four failed swarm calls, none of them on the study line
    assert bad["ai_calls"] == 2 and bad["failed_ai_calls"] == 2
    assert bad["input_tokens"] == 0 and bad["output_tokens"] == 0 and bad["thinking_tokens"] == 0
    assert bad["ai_cost_usd"] == 0.0 and bad["calls_without_usage"] == 2
    assert bad["swarm"]["ai_calls"] == 4 and bad["swarm"]["failed_ai_calls"] == 4
    assert bad["swarm"]["ai_cost_usd"] == 0.0 and bad["swarm"]["calls_without_usage"] == 4


def test_patchguru_refuses_a_missing_or_empty_key(monkeypatch, tmp_path, capsys):
    monkeypatch.delenv(model_provider.KEY_ENV, raising=False)
    argv = ["--bench", "x.csv", "--patchguru", str(tmp_path), "--fingerprints", str(tmp_path / "fp.json"),
            "--out", str(tmp_path / "out")]
    assert pg.main(argv) == 1
    err = capsys.readouterr().err
    assert model_provider.KEY_ENV in err and "is not set" in err and "never printed" in err
    monkeypatch.setenv(model_provider.KEY_ENV, "")
    assert pg.main(argv) == 1
    assert "is empty" in capsys.readouterr().err
