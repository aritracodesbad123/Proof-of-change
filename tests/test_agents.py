"""Nemotron agent swarm (poc/agents.py): advisory roles; code verdict stays authoritative."""
from __future__ import annotations

import json
from pathlib import Path

from poc import agents, model_provider

REPO = Path(__file__).resolve().parents[1]
FIX = REPO / "evals/fixtures/model_responses"


def test_default_models_include_swarm_roles():
    for role in ("claims", "probes", "judge", "helper", "summary"):
        assert role in model_provider.DEFAULT_MODELS


def test_run_swarm_recorded_fills_explanation_without_changing_verdict(tmp_path):
    # copy fixture under a throwaway root so RecordedProvider finds it
    dest = tmp_path / "rasbt" / "mlxtend"
    dest.mkdir(parents=True)
    src = FIX / "rasbt" / "mlxtend" / "1229.json"
    (dest / "1229.json").write_text(src.read_text())
    prov = model_provider.RecordedProvider(tmp_path)
    rec = {
        "verdict": "verified",
        "reason": "tests match",
        "title": "feature groups",
        "repo": "rasbt/mlxtend",
        "pr": {"repo": "rasbt/mlxtend", "number": 1229},
        "finding_labels": ["proven"],
        "comparison": {"regressions": []},
        "probes": {"items": [{"id": "groups-columns", "about": "groups", "labels": ["proven"]}],
                   "summary": {}},
    }
    out = agents.run_swarm(prov, rec)
    assert rec["verdict"] == "verified"  # code owns the verdict
    assert out["advisory"] is True
    assert rec["agents"]["advisory"] is True
    roles = {r["role"]: r for r in rec["agents"]["roles"]}
    assert roles["judge"]["status"] == "ok" and roles["judge"]["labels"]
    assert roles["helper"]["status"] == "ok"
    assert roles["summary"]["status"] == "ok"
    assert rec["explanation"]["status"] == "wired"
    assert rec["explanation"]["text"]
    assert rec["explanation"].get("advisory") is True


def test_run_swarm_fills_empty_summary_from_verdict(monkeypatch):
    class EmptySummary(model_provider.Provider):
        name = "nebius"
        blind = True

        def complete_json(self, task, system, user, schema, ctx):
            if task == "summary":
                return {"text": "", "quotes": []}
            if task == "judge":
                return {"labels": []}
            if task == "helper":
                return {"notes": []}
            return {}

    rec = {"verdict": "needs_attention", "reason": "C3 mismatch", "repo": "o/r", "pr": {"number": 1}}
    agents.run_swarm(EmptySummary(), rec)
    assert "needs_attention" in rec["explanation"]["text"]
    assert "C3 mismatch" in rec["explanation"]["text"]
    assert rec["agents"]["roles"][-1].get("note")


def test_run_swarm_unwraps_nested_json_summary_text():
    class Nested(model_provider.Provider):
        name = "nebius"
        blind = True

        def complete_json(self, task, system, user, schema, ctx):
            if task == "summary":
                return {"text": json.dumps({"summary": "Plain English for the reviewer."}), "quotes": []}
            if task == "judge":
                return {"labels": []}
            if task == "helper":
                return {"notes": []}
            return {}

    rec = {"verdict": "verified", "reason": "ok", "repo": "o/r", "pr": {"number": 1}}
    agents.run_swarm(Nested(), rec)
    assert rec["explanation"]["text"] == "Plain English for the reviewer."


def test_run_swarm_none_provider_skips():
    rec = {"verdict": "needs_attention", "reason": "x"}
    agents.run_swarm(None, rec)
    assert rec["agents"]["status"] == "skipped"
    assert rec["verdict"] == "needs_attention"


def test_models_for_args_overrides():
    m = agents.models_for_args("c", "p", judge="j", helper="h", summary="s")
    assert m["claims"] == "c" and m["probes"] == "p"
    assert m["judge"] == "j" and m["helper"] == "h" and m["summary"] == "s"


def test_helper_nano_fallback_restores_shared_model_id():
    """A failed Lightning call must not leave later PRs stuck on Nano."""
    lightning = model_provider.DEFAULT_MODELS["helper"]

    class Boom(model_provider.Provider):
        name = "nebius"
        blind = True

        def complete_json(self, task, system, user, schema, ctx):
            raise model_provider.ProviderError("down")

    prov = Boom()
    assert prov.models["helper"] == lightning
    rec = {"verdict": "verified", "reason": "ok", "repo": "o/r", "pr": {"number": 1}}
    agents.run_swarm(prov, rec, run_judge=False, run_summary=False)
    assert prov.models["helper"] == lightning
    assert rec["agents"]["roles"][0]["model"] == model_provider.HELPER_FALLBACK
    assert rec["agents"]["roles"][0]["status"] == "error"


def test_finish_skips_swarm_when_model_skipped(tmp_path, monkeypatch):
    """--no-probes sets model_skipped; finish must not call the swarm (stamp stays honest)."""
    from ops import daily_run

    called = {"n": 0}
    monkeypatch.setattr(agents, "run_swarm", lambda *a, **k: called.__setitem__("n", called["n"] + 1))
    monkeypatch.setattr(daily_run, "check_record", lambda rec: [])
    monkeypatch.setattr(daily_run, "stamp_model_use", lambda rec, a: None)

    class P(model_provider.Provider):
        name = "nebius"

    a = type("A", (), {"provider": P(), "model_skipped": "AI calls skipped because --no-probes was set"})()
    rec = {"files": {"package_py": [], "compiled": [], "other": []}, "per_run": [], "verdict": "verified",
           "reason": "ok"}
    daily_run.finish(rec, tmp_path, tmp_path / "work", 0.0, a)
    assert called["n"] == 0
    assert rec["agents"]["status"] == "skipped"
    assert "no-probes" in rec["explanation"]["why"]


def test_fixture_has_swarm_tasks():
    d = json.loads((FIX / "rasbt/mlxtend/1229.json").read_text())
    assert "TEST FIXTURE" in d["_fixture"]
    for task in ("judge", "helper", "summary"):
        assert task in d
