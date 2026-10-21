"""Human review: dropped probes cap the verdict, the review is recorded, and human-requested probes are labelled."""
from __future__ import annotations

import threading
import time
from pathlib import Path

import pytest

from ops import daily_run
from poc import hitl, model_probes
from reports import pr_report, reviewer

CODE = "import json\nimport pkg.m as m\nprint(json.dumps({'observations': {'v': m.f(1)}}))\n"
FALSE_CLAIM = {"id": "C1", "text": "f(1) now returns 2", "testable": True}


class Scripted:
    name = "recorded"
    models = {"probes": "fixture", "claims": "fixture"}

    def __init__(self):
        self.calls = []

    def describe(self):
        return {"name": self.name, "models": self.models}

    def complete_json(self, task, system, user, schema, ctx):
        self.calls.append(task)
        return {"probes": [{"id": f"idea{len(self.calls)}", "about": "from a test idea", "claims": [], "code": CODE}]}


def _gate(tmp_path, monkeypatch, approval: dict, provider=None):
    hdir = tmp_path / "hitl"
    hdir.mkdir()
    monkeypatch.setenv("POC_HITL", "1")
    monkeypatch.setenv("POC_HITL_DIR", str(hdir))
    monkeypatch.setenv("POC_PROGRESS_PATH", str(tmp_path / "p.jsonl"))
    base = tmp_path / "base"
    (base / "pkg").mkdir(parents=True)
    (base / "pkg" / "m.py").write_text("def f(x):\n    return x\n")
    draft = [{
        "id": "p1", "about": "checks the claim",
        "claims": [{"id": "C1", "covers": ["v"], "expect": "differs"}], "code": CODE,
    }]

    def answer():
        time.sleep(0.1)
        hitl.write_approval(hdir, approval)

    threading.Thread(target=answer, daemon=True).start()
    return hitl.gate_and_materialize(
        provider=provider or Scripted(), repo="o/r", pr=1, title="t", body="b",
        draft_probes=draft, claims=[FALSE_CLAIM], rejected_claims=[],
        base_files={"pkg/m.py": base / "pkg" / "m.py"}, base_root=base, pr_roots=[],
        outdir=tmp_path / "model-probes", tidy_id=model_probes._tidy_id,
        unescape_code=model_probes._unescape_code, validate_probe=model_probes.validate_probe,
        probe_file=model_probes.probe_file, errors=[],
    )


def test_dropping_the_only_probe_for_a_false_claim_cannot_yield_verified(tmp_path, monkeypatch):
    out = _gate(tmp_path, monkeypatch, {"approve": [], "extra_scenarios": [], "skip_business_followup": True})
    hr = out["human_review"]
    assert hr["dropped_ai_probes"] == ["p1"] and hr["kept_ai_probes"] == []
    assert hr["claims_without_probe"] == ["C1"]

    # With the probe gone, the tests alone would say verified. The review cap stops that.
    monkeypatch.setattr(daily_run, "verdict_for", lambda *a, **k: ("verified", "tests pass", []))
    rec = {"human_review": hr, "files": {}, "probes": None, "behaviour_claims": []}
    daily_run._store_verdict(rec, None, None, None)
    assert rec["verdict"] == "could_not_verify"
    assert "C1" in rec["reason"]


def test_keeping_the_probe_leaves_the_verdict_alone(tmp_path, monkeypatch):
    out = _gate(tmp_path, monkeypatch, {"approve": ["p1"], "extra_scenarios": [], "skip_business_followup": True})
    assert out["human_review"]["claims_without_probe"] == []
    rec = {"human_review": out["human_review"]}
    assert daily_run.cap_for_review(rec, "verified", "r") == ("verified", "r")
    assert daily_run.cap_for_review({"human_review": {"claims_without_probe": ["C1"]}}, "needs_attention", "r") \
        == ("needs_attention", "r")


def test_review_is_recorded_and_human_requested_probes_are_labelled(tmp_path, monkeypatch):
    out = _gate(tmp_path, monkeypatch, {
        "approve": ["p1"], "extra_scenarios": ["empty input"], "skip_business_followup": True})
    hr = out["human_review"]
    assert hr["kept_ai_probes"] == ["p1"]
    assert hr["test_ideas"] == ["empty input"]
    assert len(hr["human_requested_probes"]) == 1
    origins = sorted(p["origin"] for p in out["probes"])
    assert origins == ["ai", "human-requested"]

    item = {"id": hr["human_requested_probes"][0], "source": "model", "origin": "human-requested",
            "freeze": {"generator": {"label": "model probe"}}}
    assert pr_report.generator_label(item).startswith("human-requested")

    R = reviewer.Report()
    reviewer.human_review_section(R, {"human_review": hr})
    html = reviewer.to_html(R, "t")
    md = reviewer.to_md(R)
    for text in (html, md):
        assert "Human review" in text and "p1" in text and "empty input" in text


def test_idea_and_request_size_caps():
    draft = {"needs_business_followup": False}
    long_idea = "x" * (hitl.MAX_IDEA_CHARS + 1)
    assert "characters" in hitl.validate_approval(draft, {"approve": [], "extra_scenarios": [long_idea]})
    huge = {"approve": ["a" * 1000] * 80, "extra_scenarios": []}
    assert "too large" in hitl.validate_approval(draft, huge)
    assert hitl.validate_approval(draft, {"approve": [], "extra_scenarios": ["ok"]}) is None


def test_cancel_stops_the_check_before_anything_runs(tmp_path, monkeypatch):
    assert hitl.validate_approval({}, {"cancel": True}) is None
    with pytest.raises(hitl.ReviewCancelled, match="review cancelled"):
        _gate(tmp_path, monkeypatch, {"cancel": True})
    assert not list((tmp_path / "model-probes").glob("*.py")) if (tmp_path / "model-probes").exists() else True


def test_timeout_says_review_not_completed(tmp_path, monkeypatch):
    monkeypatch.setenv("POC_PROGRESS_PATH", str(tmp_path / "p.jsonl"))
    with pytest.raises(TimeoutError, match="review not completed"):
        hitl.wait_for_approval(Path(tmp_path), timeout_s=0.1, poll_s=0.02)
