"""HITL mid-check: multi-scenario approval, business follow-up gate, draft/approval files."""
from __future__ import annotations

import threading
import time
from pathlib import Path

from poc import console_api, hitl, model_probes


def test_business_followup_detects_keywords():
    out = hitl.business_followup(
        [{"id": "C1", "text": "API shape must stay stable", "source_quote": "must not break callers"}],
        "schema validation",
        "permission and workflow notes",
    )
    assert out["needs_business_followup"]
    assert 1 <= len(out["business_questions"]) <= 3


def test_validate_approval_requires_business_answers():
    draft = {
        "needs_business_followup": True,
        "business_questions": [{"id": "schema", "prompt": "What schema?"}],
    }
    err = hitl.validate_approval(draft, {
        "approve": [],
        "extra_scenarios": ["pricing edge case"],
        "business_answers": {},
        "skip_business_followup": False,
    })
    assert err and "business answers" in err


def test_validate_approval_allows_skip():
    draft = {
        "needs_business_followup": True,
        "business_questions": [{"id": "schema", "prompt": "What schema?"}],
    }
    assert hitl.validate_approval(draft, {
        "approve": ["p1"],
        "extra_scenarios": [],
        "business_answers": {},
        "skip_business_followup": True,
    }) is None


def test_scenario_texts_merges_answers_capped():
    approval = {
        "extra_scenarios": ["a", "b"],
        "business_answers": {"schema": "keep v1 fields", "x": ""},
        "skip_business_followup": False,
    }
    texts = hitl.scenario_texts(approval)
    assert texts == ["a", "b", "keep v1 fields"]


def test_write_and_wait_approval(tmp_path, monkeypatch):
    monkeypatch.setenv("POC_HITL", "1")
    monkeypatch.setenv("POC_HITL_DIR", str(tmp_path))
    draft = hitl.write_draft(
        tmp_path,
        claims=[{"id": "C1", "text": "t", "testable": True, "expect": "same", "source_quote": "t"}],
        probes=[{"id": "p1", "about": "about", "claims": [], "code": "x = 1\n"}],
        title="t",
        body="b",
    )
    assert draft["probe_ids"] == ["p1"]
    assert (tmp_path / "hitl_draft.json").is_file()

    def later():
        time.sleep(0.15)
        hitl.write_approval(tmp_path, {
            "approve": ["p1"],
            "extra_scenarios": ["edge: empty input"],
            "business_answers": {},
            "skip_business_followup": True,
        })

    threading.Thread(target=later, daemon=True).start()
    got = hitl.wait_for_approval(tmp_path, timeout_s=5, poll_s=0.05)
    assert got["approve"] == ["p1"]
    assert got["extra_scenarios"] == ["edge: empty input"]


def test_submit_job_scenarios_400_without_business_answers(tmp_path, monkeypatch):
    monkeypatch.setattr(console_api, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(console_api, "RUNS_ROOT", tmp_path / "ops" / "runs")
    job_id = "hitljob1"
    hdir = tmp_path / "ops" / "runs" / "_jobs" / job_id
    hdir.mkdir(parents=True)
    hitl.write_draft(
        hdir,
        claims=[{"id": "C1", "text": "schema must match", "source_quote": "schema must match"}],
        probes=[{"id": "p1", "about": "a", "claims": [], "code": "pass\n"}],
        title="schema",
        body="contract validation",
    )
    with console_api._jobs_lock:
        console_api._jobs[job_id] = {
            "id": job_id,
            "status": "awaiting_human",
            "hitl_dir": str(hdir),
            "progress_path": str(hdir / "progress.jsonl"),
        }
    try:
        console_api.submit_job_scenarios(job_id, {
            "approve": ["p1"],
            "extra_scenarios": ["one"],
            "business_answers": {},
            "skip_business_followup": False,
        })
        assert False, "expected ValueError"
    except ValueError as e:
        assert "business" in str(e).lower()


def test_submit_job_scenarios_writes_approval(tmp_path, monkeypatch):
    monkeypatch.setattr(console_api, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(console_api, "RUNS_ROOT", tmp_path / "ops" / "runs")
    job_id = "hitljob2"
    hdir = tmp_path / "ops" / "runs" / "_jobs" / job_id
    hdir.mkdir(parents=True)
    hitl.write_draft(
        hdir,
        claims=[{"id": "C1", "text": "ok", "source_quote": "ok"}],
        probes=[{"id": "p1", "about": "a", "claims": [], "code": "pass\n"}],
        title="t",
        body="b",
    )
    with console_api._jobs_lock:
        console_api._jobs[job_id] = {
            "id": job_id,
            "status": "awaiting_human",
            "hitl_dir": str(hdir),
            "progress_path": str(hdir / "progress.jsonl"),
        }
    out = console_api.submit_job_scenarios(job_id, {
        "approve": ["p1"],
        "extra_scenarios": ["s1", "s2"],
        "business_answers": {},
        "skip_business_followup": True,
    })
    assert out["extra_scenarios"] == ["s1", "s2"]
    assert (hdir / "hitl_approval.json").is_file()


def test_gate_materialize_multi_scenario(tmp_path, monkeypatch):
    """Approve one draft probe + two extra scenarios → frozen probe files (scripted provider)."""

    class Scripted:
        name = "recorded"
        models = {"probes": "fixture", "claims": "fixture"}
        calls: list = []

        def describe(self):
            return {"name": self.name, "models": self.models}

        def complete_json(self, task, system, user, schema, ctx):
            self.calls.append(task)
            # One probe per scenario call; import changed module so probe_quality.lint passes.
            n = sum(1 for t in self.calls if t == "probes")
            code = (
                "import json\n"
                "import pkg.m as m\n"
                "print(json.dumps({'observations': {'v': m.f(1)}}))\n"
            )
            return {
                "probes": [{
                    "id": f"sc{n}",
                    "about": f"scenario {n}",
                    "claims": [],
                    "code": code,
                }]
            }

    hdir = tmp_path / "hitl"
    hdir.mkdir()
    monkeypatch.setenv("POC_HITL", "1")
    monkeypatch.setenv("POC_HITL_DIR", str(hdir))
    monkeypatch.setenv("POC_PROGRESS_PATH", str(tmp_path / "p.jsonl"))

    base = tmp_path / "base"
    (base / "pkg").mkdir(parents=True)
    (base / "pkg" / "m.py").write_text("def f(x):\n    return x\n")
    outdir = tmp_path / "model-probes"
    draft = [{
        "id": "p1",
        "about": "draft",
        "claims": [],
        "code": "import json\nprint(json.dumps({'observations': {'v': 0}}))\n",
    }]

    def approve_soon():
        time.sleep(0.1)
        hitl.write_approval(hdir, {
            "approve": ["p1"],
            "extra_scenarios": ["empty list", "negative numbers"],
            "business_answers": {},
            "skip_business_followup": True,
        })

    threading.Thread(target=approve_soon, daemon=True).start()
    out = hitl.gate_and_materialize(
        provider=Scripted(),
        repo="o/r",
        pr=1,
        title="t",
        body="b",
        draft_probes=draft,
        claims=[],
        rejected_claims=[],
        base_files={"pkg/m.py": base / "pkg" / "m.py"},
        base_root=base,
        pr_roots=[],
        outdir=outdir,
        tidy_id=model_probes._tidy_id,
        unescape_code=model_probes._unescape_code,
        validate_probe=model_probes.validate_probe,
        probe_file=model_probes.probe_file,
        errors=[],
    )
    assert out["hitl"] is True
    assert len(out["probes"]) == 3  # approved draft + 2 scenarios
    names = {Path(p["path"]).name for p in out["probes"]}
    assert "model-p1.py" in names


def test_extra_scenarios_cap():
    draft = {"needs_business_followup": False, "business_questions": []}
    too_many = [f"s{i}" for i in range(hitl.MAX_EXTRA_SCENARIOS + 1)]
    err = hitl.validate_approval(draft, {
        "approve": [],
        "extra_scenarios": too_many,
        "business_answers": {},
        "skip_business_followup": False,
    })
    assert err and "at most" in err


def test_await_human_in_stages():
    from poc import run_progress
    assert "await_human" in run_progress.STAGES
