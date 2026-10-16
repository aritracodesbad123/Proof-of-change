"""Nemotron agent swarm: role-routed Nebius calls after the code verdict.

Roles (REQUIREMENTS §4a):
  judge    Ultra 550B — advisory labels on findings (does not override the code verdict)
  helper   Lightning (Nano fallback) — noise / install notes (advisory only)
  summary  Super 120B — plain-language report text that may only quote real record fields

Claims and probes stay in poc/model_probes.py (Super). This module runs after probes and the
code verdict so the swarm cannot change the merge advice silently.

    out = run_swarm(provider, rec)   # mutates rec with agents / explanation; returns out
"""
from __future__ import annotations

import json
from typing import Any

from poc import model_provider
from poc.model_provider import HELPER_FALLBACK, Provider, ProviderError

JUDGE_SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["labels"],
    "properties": {"labels": {"type": "array", "items": {
        "type": "object", "additionalProperties": False,
        "required": ["id", "label", "reason"],
        "properties": {
            "id": {"type": "string"},
            "label": {"type": "string",
                      "enum": ["proven", "false", "unmentioned", "needs_human"]},
            "reason": {"type": "string"}}}}}}

HELPER_SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["notes"],
    "properties": {"notes": {"type": "array", "items": {"type": "string"}}}}

SUMMARY_SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["text", "quotes"],
    "properties": {
        "text": {"type": "string"},
        "quotes": {"type": "array", "items": {"type": "string"}}}}

JUDGE_PROMPT = """You label each finding from a pull-request check. For every finding give id, label
(proven | false | unmentioned | needs_human), and a one-sentence reason. Labels are advisory only;
plain code owns the verdict. Answer with JSON only."""

HELPER_PROMPT = """You suggest short, optional notes: noise patterns to ignore in future diffs, or
install hints. Do not invent failures. At most 5 short notes. Answer with JSON only."""

SUMMARY_PROMPT = """Write a short plain-English summary of this PR check for a human reviewer.
Quote only strings that appear in the provided record excerpt (put those strings in "quotes").
Do not invent log lines. Answer with JSON only."""


def _role(provider: Provider | None, task: str) -> dict:
    if provider is None:
        return {"role": task, "model": None, "status": "skipped", "note": "no model provider"}
    return {"role": task, "model": (provider.models or {}).get(task), "status": "pending", "note": None}


def _call(provider: Provider, task: str, system: str, user: str, schema: dict, ctx: dict) -> dict:
    """One gated-style call: Nebius providers already go through cost/_remember; refuse unknown tasks."""
    if task not in provider.models:
        raise ProviderError(f"provider has no model configured for task {task!r}")
    return provider.complete_json(task, system, user, schema, ctx)


def _findings_payload(rec: dict) -> list[dict]:
    out = []
    for i, lab in enumerate(rec.get("finding_labels") or []):
        out.append({"id": f"F{i + 1}", "code_label": lab})
    c = rec.get("comparison") or {}
    for key in ("regressions", "new_tests_failing", "removed_tests", "other_changes", "fixed", "flaky"):
        for j, name in enumerate((c.get(key) or [])[:8]):
            out.append({"id": f"{key}-{j + 1}", "kind": key, "name": str(name)[:200]})
    for it in ((rec.get("probes") or {}).get("items") or [])[:12]:
        out.append({"id": f"probe-{it.get('id')}", "kind": "probe",
                    "labels": it.get("labels") or [], "about": (it.get("about") or "")[:200]})
    return out[:40]


def _record_excerpt(rec: dict) -> str:
    bits = {
        "title": rec.get("title") or (rec.get("pr") or {}).get("title"),
        "verdict": rec.get("verdict"),
        "reason": (rec.get("reason") or "")[:800],
        "baseline": rec.get("baseline"),
        "probe_summary": ((rec.get("probes") or {}).get("summary") or {}),
    }
    return json.dumps(bits, indent=1)[:6000]


def run_swarm(provider: Provider | None, rec: dict, ctx: dict | None = None,
              *, run_judge: bool = True, run_helper: bool = True, run_summary: bool = True) -> dict:
    """Fill rec['agents'] and optional rec['explanation']. Never changes rec['verdict']."""
    ctx = dict(ctx or {})
    ctx.setdefault("repo", rec.get("repo") or (rec.get("pr") or {}).get("repo") or "unknown/repo")
    ctx.setdefault("pr", (rec.get("pr") or {}).get("number") or rec.get("pr") or 0)
    agents: list[dict[str, Any]] = []
    out: dict[str, Any] = {"agents": agents, "advisory": True}

    if provider is None:
        rec["agents"] = {"status": "skipped", "note": "no model provider", "roles": []}
        rec.setdefault("explanation", {"status": "not yet wired", "why": "no model provider"})
        return out

    from poc import run_progress

    # --- judge (Ultra), advisory
    if run_judge:
        run_progress.emit("agent_judge", "ultra", "Ultra is judging findings for this PR")
        role = _role(provider, "judge")
        agents.append(role)
        try:
            user = "Findings:\n" + json.dumps(_findings_payload(rec), indent=1)[:8000]
            raw = _call(provider, "judge", JUDGE_PROMPT, user, JUDGE_SCHEMA, ctx)
            role["status"] = "ok"
            role["labels"] = raw.get("labels") or []
            out["judge"] = raw
        except Exception as e:  # noqa: BLE001
            role["status"] = "error"
            role["note"] = f"{type(e).__name__}: {e}"[:200]

    # --- helper (Lightning / Nano fallback), advisory
    if run_helper:
        run_progress.emit("agent_helper", "lightning", "Lightning is drafting remediation notes")
        role = _role(provider, "helper")
        agents.append(role)
        try:
            user = "Record excerpt:\n" + _record_excerpt(rec)
            raw = _call(provider, "helper", HELPER_PROMPT, user, HELPER_SCHEMA, ctx)
            role["status"] = "ok"
            role["notes"] = raw.get("notes") or []
            out["helper"] = raw
        except ProviderError as e:
            # ponytail: one retry on Nano if Lightning fails; restore model id so later PRs still try Lightning
            prev = provider.models.get("helper")
            if prev and prev != HELPER_FALLBACK:
                provider.models["helper"] = HELPER_FALLBACK
                role["model"] = HELPER_FALLBACK
                role["note"] = f"fell back to Nano after {type(e).__name__}"
                try:
                    user = "Record excerpt:\n" + _record_excerpt(rec)
                    raw = _call(provider, "helper", HELPER_PROMPT, user, HELPER_SCHEMA, ctx)
                    role["status"] = "ok"
                    role["notes"] = raw.get("notes") or []
                    out["helper"] = raw
                except Exception as e2:  # noqa: BLE001
                    role["status"] = "error"
                    role["note"] = f"{type(e2).__name__}: {e2}"[:200]
                finally:
                    provider.models["helper"] = prev
            else:
                role["status"] = "error"
                role["note"] = f"{type(e).__name__}: {e}"[:200]
        except Exception as e:  # noqa: BLE001
            role["status"] = "error"
            role["note"] = f"{type(e).__name__}: {e}"[:200]

    # --- summary (Super)
    if run_summary:
        run_progress.emit("agent_summary", "super", "Super is writing the PR summary")
        role = _role(provider, "summary")
        agents.append(role)
        try:
            user = "Record excerpt:\n" + _record_excerpt(rec)
            raw = _call(provider, "summary", SUMMARY_PROMPT, user, SUMMARY_SCHEMA, ctx)
            text = str(raw.get("text") or raw.get("summary") or "").strip()
            quotes = [q for q in (raw.get("quotes") or []) if isinstance(q, str)]
            excerpt = _record_excerpt(rec)
            # only keep quotes that actually appear in the excerpt we sent
            kept = [q for q in quotes if q and q in excerpt]
            if not text:
                # Model sometimes returns empty text; never leave the console blank.
                text = (
                    f"Verdict: {rec.get('verdict') or 'unknown'}. "
                    f"{(rec.get('reason') or '')[:700]}"
                ).strip()
                role["note"] = "model returned empty text; filled from code verdict/reason"
            role["status"] = "ok"
            rec["explanation"] = {
                "status": "wired",
                "model": role["model"],
                "text": text[:2000],
                "quotes": kept[:20],
                "advisory": True,
            }
            out["summary"] = rec["explanation"]
        except Exception as e:  # noqa: BLE001
            role["status"] = "error"
            role["note"] = f"{type(e).__name__}: {e}"[:200]
            rec["explanation"] = {"status": "error", "why": role["note"]}

    rec["agents"] = {
        "status": "ran",
        "advisory": True,
        "note": "judge/helper/summary are advisory; code owns the verdict",
        "roles": agents,
        "provider": provider.describe(),
    }
    if "explanation" not in rec:
        rec["explanation"] = {"status": "not yet wired"}
    return out


def models_for_args(claims: str, probes: str, judge: str | None = None,
                    helper: str | None = None, summary: str | None = None) -> dict:
    """Build the models dict passed to model_provider.select from CLI flags."""
    d = dict(model_provider.DEFAULT_MODELS)
    d["claims"], d["probes"] = claims, probes
    if judge:
        d["judge"] = judge
    if helper:
        d["helper"] = helper
    if summary:
        d["summary"] = summary
    return d
