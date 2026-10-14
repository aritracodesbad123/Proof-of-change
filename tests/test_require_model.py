"""The daily run refuses to test PRs with the AI-probe gate on and no model (docs/decisions/2026-10-14-require-model-for-ai-gate.md)."""
import argparse

import pytest

from ops import daily_run
from poc import model_provider


def _a(**kw):
    base = dict(baseline="full", provider=None, model_note="model provider: none", select_only=False,
                report_only=False, rejudge=False)
    return argparse.Namespace(**(base | kw))


def test_full_baseline_without_model_is_refused_loudly():
    msg = daily_run.model_refusal(_a())
    assert msg and msg.startswith("STOPPED") and "could_not_verify" in msg and "NEBIUS_API_KEY" in msg


def test_missing_key_message_is_carried():
    prov, note = model_provider.select("nebius", env={})
    assert prov is None
    assert "NEBIUS_API_KEY is not set" in daily_run.model_refusal(_a(model_note=note))


def test_with_model_or_without_gate_runs():
    prov, note = model_provider.select("nebius", env={"NEBIUS_API_KEY": "k"})
    assert daily_run.model_refusal(_a(provider=prov, model_note=note)) is None
    for b in ("tests", "tests+diff", "tests+probes"):
        assert daily_run.model_refusal(_a(baseline=b)) is None


def test_select_and_report_only_allowed_but_rejudge_refused():
    assert daily_run.model_refusal(_a(select_only=True)) is None
    assert daily_run.model_refusal(_a(report_only=True)) is None
    assert daily_run.model_refusal(_a(report_only=True, rejudge=True))


def test_default_provider_is_nebius(monkeypatch):
    seen = {}
    real = argparse.ArgumentParser.parse_args

    def spy(self, args=None, namespace=None):
        seen["p"] = real(self, args, namespace).model_provider
        raise SystemExit(0)
    monkeypatch.setattr(argparse.ArgumentParser, "parse_args", spy)
    with pytest.raises(SystemExit):
        daily_run.main([])
    assert seen["p"] == "nebius"


def test_main_stops_before_testing(monkeypatch):
    monkeypatch.setattr(daily_run, "sync_to_origin_main", lambda *_: "a" * 40)
    monkeypatch.setattr(daily_run.sandbox, "configure", lambda *_: None)
    with pytest.raises(SystemExit, match="STOPPED"):
        daily_run.main(["--model-provider", "none", "--date", "x-never"])
