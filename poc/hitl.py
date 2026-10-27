"""Human-in-the-loop mid-check: pause after AI drafts claims/probes for operator approval.

When POC_HITL is set, a command-line run and a benchmark run refuse to start. No environment
variable waives that. The operator console passes ``--console-job`` on a single pull-request
check; that flag is the only way such a check may start with approval on. A benchmark run
still refuses, even with the flag. Approval can change which probes run, so it is not a
study-run option.
"""
from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Any

from poc import freeze, probe_quality, run_progress
from poc.model_provider import PROBES_PROMPT, PROBES_SCHEMA, Provider, ProviderError
from poc.prompt_text import untrusted_block

MAX_EXTRA_SCENARIOS = 20
MAX_IDEA_CHARS = 500
MAX_REQUEST_BYTES = 64 * 1024
HUMAN_REQUESTED = "human-requested"
DEFAULT_TIMEOUT_S = 2 * 60 * 60
POLL_S = 1.0

# Heuristic tokens that suggest the human should clarify business intent.
_BUSINESS_RE = re.compile(
    r"(?i)\b(?:"
    r"validation|schema|contract|pricing|permission|workflow|"
    r"must|should\s+not|api\s+shape"
    r")\b"
)

_QUESTION_TEMPLATES = (
    ("validation", "Which inputs or states must validation accept vs reject after this change?"),
    ("schema", "What schema or field shape should callers rely on after this PR?"),
    ("contract", "Which API or behavioural contract must stay the same vs may change?"),
    ("pricing", "Are there pricing or billing rules this behaviour must respect?"),
    ("permission", "Which roles or permissions should gain or lose access?"),
    ("workflow", "What end-to-end workflow step must still succeed (or fail) the same way?"),
    ("must", "Which 'must' requirements from the PR text are non-negotiable for shipping?"),
    ("should not", "What must this change explicitly not do?"),
    ("api shape", "Is the public API shape frozen, or are breaking signature changes intended?"),
)


_ON = ("1", "true", "yes", "on")


def _flag(name: str) -> bool:
    return (os.environ.get(name) or "").strip().lower() in _ON


def hitl_requested() -> bool:
    """True when POC_HITL is set, whether or not this process may honour it."""
    return _flag("POC_HITL")


def console_job() -> bool:
    """True when this process was started by the operator console."""
    return _flag("POC_CONSOLE")


def hitl_enabled() -> bool:
    """Operator approval runs only inside a console job. A bare POC_HITL does not turn it on."""
    return hitl_requested() and console_job()


_approval_ran = False


def reset_approval_ran() -> None:
    """Clear the per-pull-request mark that the approval step ran."""
    global _approval_ran
    _approval_ran = False


def note_approval_ran() -> None:
    """The approval step was entered for the pull request that is running now."""
    global _approval_ran
    _approval_ran = True


def approval_ran() -> bool:
    """True after this pull request entered the approval step. False until then."""
    return _approval_ran


def take_approval_ran() -> bool:
    """Whether the approval step ran, then clear the mark for the next pull request."""
    ran = approval_ran()
    reset_approval_ran()
    return ran


def study_operator_approval_stop(bench: bool, *, console_job: bool = False, single_pr: bool = False) -> str | None:
    """Plain-language refusal for a command-line or benchmark run that has POC_HITL set.

    ``console_job`` is the ``--console-job`` flag, never an environment variable. It lets one
    pull-request check start. A benchmark run stops even when the flag is set.
    """
    if not hitl_requested():
        return None
    if console_job and single_pr and not bench:
        return None
    kind = "benchmark" if bench else "command-line"
    return (
        "STOPPED: operator approval is turned on (POC_HITL is set), but this is a "
        f"{kind} run. That step lets a person add or drop probes, so it can change "
        "which probes run. Unset POC_HITL and start this run again."
    )


def hitl_dir() -> Path | None:
    raw = (os.environ.get("POC_HITL_DIR") or "").strip()
    return Path(raw) if raw else None


def business_followup(claims: list[dict], title: str, body: str | None) -> dict[str, Any]:
    """Heuristic: scan claims + PR text; return needs_business_followup + 1–3 questions."""
    parts = [title or "", body or ""]
    for c in claims or []:
        parts.append(str(c.get("text") or ""))
        parts.append(str(c.get("source_quote") or ""))
    blob = "\n".join(parts)
    hits: list[str] = []
    seen: set[str] = set()
    for label, _q in _QUESTION_TEMPLATES:
        token = label
        if label == "should not":
            if re.search(r"(?i)\bshould\s+not\b", blob) and label not in seen:
                hits.append(label)
                seen.add(label)
            continue
        if label == "api shape":
            if re.search(r"(?i)\bapi\s+shape\b", blob) and label not in seen:
                hits.append(label)
                seen.add(label)
            continue
        if re.search(rf"(?i)\b{re.escape(token)}\b", blob) and label not in seen:
            hits.append(label)
            seen.add(label)
    if not hits and _BUSINESS_RE.search(blob):
        hits = ["must"]
    questions: list[dict[str, str]] = []
    by_label = {lab: q for lab, q in _QUESTION_TEMPLATES}
    for lab in hits[:3]:
        questions.append({"id": lab.replace(" ", "_"), "prompt": by_label[lab]})
    return {
        "needs_business_followup": bool(questions),
        "business_questions": questions,
    }


def probe_preview(p: dict) -> dict[str, Any]:
    code = p.get("code") or ""
    return {
        "id": p.get("id"),
        "about": (p.get("about") or "")[:300],
        "claims": p.get("claims") or [],
        "code_preview": code[:800] + ("…" if len(code) > 800 else ""),
    }


def write_draft(outdir: Path, *, claims: list, probes: list[dict], title: str, body: str | None,
                rejected_claims: list | None = None) -> dict[str, Any]:
    outdir.mkdir(parents=True, exist_ok=True)
    follow = business_followup(claims, title, body)
    draft = {
        "claims": claims,
        "rejected_claims": rejected_claims or [],
        "probes": [probe_preview(p) for p in probes],
        "probe_ids": [str(p.get("id")) for p in probes if p.get("id")],
        **follow,
        "written_at": time.time(),
    }
    path = outdir / "hitl_draft.json"
    path.write_text(json.dumps(draft, indent=2, default=str), encoding="utf-8")
    # Clear any stale approval so a re-run waits again.
    appr = outdir / "hitl_approval.json"
    if appr.exists():
        appr.unlink()
    return draft


def read_draft(outdir: Path) -> dict[str, Any] | None:
    path = outdir / "hitl_draft.json"
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def read_approval(outdir: Path) -> dict[str, Any] | None:
    path = outdir / "hitl_approval.json"
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def validate_approval(draft: dict[str, Any], body: dict[str, Any]) -> str | None:
    """None if ok, else error message (HTTP 400)."""
    if not isinstance(body, dict):
        return "approval body must be a JSON object"
    try:
        size = len(json.dumps(body).encode("utf-8"))
    except (TypeError, ValueError):
        return "approval body must be plain JSON"
    if size > MAX_REQUEST_BYTES:
        return f"the review is too large (over {MAX_REQUEST_BYTES // 1024} KB)"
    if body.get("cancel") is True:
        return None
    approve = body.get("approve")
    if not isinstance(approve, list) or not all(isinstance(x, str) for x in approve):
        return "approve must be an array of probe id strings"
    extras = body.get("extra_scenarios") or []
    if not isinstance(extras, list) or not all(isinstance(x, str) for x in extras):
        return "extra_scenarios must be an array of strings"
    if len(extras) > MAX_EXTRA_SCENARIOS:
        return f"at most {MAX_EXTRA_SCENARIOS} test ideas"
    if any(len(x) > MAX_IDEA_CHARS for x in extras):
        return f"each test idea must be at most {MAX_IDEA_CHARS} characters"
    skip = bool(body.get("skip_business_followup"))
    answers = body.get("business_answers") or {}
    if not isinstance(answers, dict):
        return "business_answers must be an object"
    if draft.get("needs_business_followup") and not skip:
        qs = draft.get("business_questions") or []
        missing = [q["id"] for q in qs if not str(answers.get(q["id"]) or "").strip()]
        if missing:
            return f"business answers required for: {', '.join(missing)} (or set skip_business_followup)"
    return None


def write_approval(outdir: Path, body: dict[str, Any]) -> dict[str, Any]:
    outdir.mkdir(parents=True, exist_ok=True)
    payload = {
        "approve": list(body.get("approve") or []),
        "extra_scenarios": [s.strip() for s in (body.get("extra_scenarios") or []) if str(s).strip()],
        "business_answers": dict(body.get("business_answers") or {}),
        "skip_business_followup": bool(body.get("skip_business_followup")),
        "cancelled": body.get("cancel") is True,
        "written_at": time.time(),
    }
    if len(payload["extra_scenarios"]) > MAX_EXTRA_SCENARIOS:
        payload["extra_scenarios"] = payload["extra_scenarios"][:MAX_EXTRA_SCENARIOS]
    (outdir / "hitl_approval.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def wait_for_approval(outdir: Path, timeout_s: float = DEFAULT_TIMEOUT_S, poll_s: float = POLL_S) -> dict[str, Any]:
    run_progress.emit("await_human", detail="waiting for your review of the AI probes")
    deadline = time.time() + timeout_s
    path = outdir / "hitl_approval.json"
    while time.time() < deadline:
        if path.is_file():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                time.sleep(poll_s)
                continue
            if isinstance(data, dict):
                return data
        time.sleep(poll_s)
    raise TimeoutError(f"review not completed: no answer within {int(timeout_s)}s, so no probe ran")


class ReviewCancelled(RuntimeError):
    """The person cancelled the check at the review step."""


def uncovered_claims(claims: list[dict], probes: list[dict]) -> list[str]:
    """Testable claim ids that no probe left after review checks."""
    covered = {c.get("id") for p in probes for c in (p.get("claims") or []) if isinstance(c, dict)}
    return [c["id"] for c in claims if c.get("testable") and c.get("id") and c["id"] not in covered]


def scenario_texts(approval: dict[str, Any]) -> list[str]:
    """extra_scenarios plus non-empty business_answers values (capped)."""
    out: list[str] = []
    for s in approval.get("extra_scenarios") or []:
        t = str(s).strip()
        if t and t not in out:
            out.append(t)
    answers = approval.get("business_answers") or {}
    if isinstance(answers, dict) and not approval.get("skip_business_followup"):
        for v in answers.values():
            t = str(v or "").strip()
            if t and t not in out:
                out.append(t)
    return out[:MAX_EXTRA_SCENARIOS]


def generate_scenario_probes(
    provider: Provider,
    *,
    repo: str,
    pr: int,
    title: str,
    body: str | None,
    claims: list[dict],
    scenarios: list[str],
    base_files: dict,
    context_fn,
    tidy_id,
    unescape_code,
    validate_probe,
) -> tuple[list[dict], list[str]]:
    """Gated model probe gen per scenario; validate_probe + probe_quality.lint. Returns (probes, errors)."""
    from poc.model_probes import _context  # local import avoids cycle at module load

    ctx = {"repo": repo, "pr": pr}
    claim_ids = {c["id"] for c in claims if c.get("id")}
    changed = list(base_files.keys())
    pr_text = untrusted_block("pull request text", f"Title: {title}\n\nDescription:\n{body or ''}")
    base_ctx = context_fn(base_files) if context_fn else _context(base_files)
    probes_out: list[dict] = []
    errors: list[str] = []
    for i, scenario in enumerate(scenarios):
        idea = f"Test idea from the reviewer ({i + 1}/{len(scenarios)}):\n{scenario}"
        user = (
            pr_text
            + "\n\n"
            + untrusted_block("claims", json.dumps(claims, indent=1))
            + "\n\n"
            + untrusted_block("reviewer test idea", idea)
            + "\n\nWrite exactly one probe that checks this test idea against the BASE-side code below.\n\n"
            + untrusted_block("base side source code", base_ctx)
        )
        try:
            resp = provider.complete_json("probes", PROBES_PROMPT, user, PROBES_SCHEMA, ctx)
        except ProviderError as e:
            errors.append(f"test idea {i + 1}: {e}")
            continue
        for raw in (resp or {}).get("probes", [])[:1]:
            if not isinstance(raw, dict):
                continue
            p = dict(raw)
            if isinstance(p.get("id"), str):
                p["id"] = tidy_id(p["id"])
            else:
                p["id"] = f"scenario-{i + 1}"
            # Avoid colliding with approved draft ids.
            base_id = str(p["id"])
            p["id"] = tidy_id(f"hitl-{base_id}-{i + 1}")
            p["code"] = unescape_code(p.get("code"))
            if not str(p.get("about") or "").strip():
                p["about"] = f"Human-requested test idea: {scenario[:200]}"
            # Drop claim links that are not in the extracted set so validate_probe can pass.
            if claim_ids:
                p["claims"] = [c for c in (p.get("claims") or []) if isinstance(c, dict) and c.get("id") in claim_ids]
            else:
                p["claims"] = []
            why = validate_probe(p, claim_ids)
            if why:
                errors.append(f"test-idea probe {p.get('id')!r} rejected: {why}")
                continue
            lint = probe_quality.lint(p.get("code") or "", changed)
            if not lint.get("ok"):
                detail = "; ".join(
                    f"{x.get('rule')}: {x.get('detail')}" for x in (lint.get("problems") or [])[:3]
                )
                errors.append(f"test-idea probe {p.get('id')!r} lint: {detail or 'failed'}")
                continue
            probes_out.append(p)
    return probes_out, errors


def gate_and_materialize(
    *,
    provider: Provider,
    repo: str,
    pr: int,
    title: str,
    body: str | None,
    draft_probes: list[dict],
    claims: list[dict],
    rejected_claims: list,
    base_files: dict,
    base_root: Path,
    pr_roots: list,
    outdir: Path,
    tidy_id,
    unescape_code,
    validate_probe,
    probe_file,
    errors: list[str],
) -> dict[str, Any]:
    """HITL pause then freeze approved probes and probes from test ideas. Mutates errors list; returns generate()-style out."""
    from poc.model_probes import _context

    note_approval_ran()
    out: dict[str, Any] = {
        "provider": provider.describe(),
        "claims": claims,
        "rejected_claims": rejected_claims,
        "probes": [],
        "errors": errors,
        "hitl": True,
    }
    hdir = hitl_dir()
    if hdir is None:
        errors.append("POC_HITL=1 but POC_HITL_DIR unset")
        return out

    draft = write_draft(hdir, claims=claims, probes=draft_probes, title=title, body=body,
                        rejected_claims=rejected_claims)
    out["hitl_draft"] = {"probe_ids": draft.get("probe_ids"), "needs_business_followup": draft.get("needs_business_followup")}
    approval = wait_for_approval(hdir)
    if approval.get("cancelled"):
        raise ReviewCancelled("review cancelled: the check was stopped at the review step, so no probe ran")
    out["hitl_approval"] = {
        "approve": approval.get("approve"),
        "extra_scenarios": approval.get("extra_scenarios"),
        "skip_business_followup": approval.get("skip_business_followup"),
    }

    approve_ids = {str(x) for x in (approval.get("approve") or [])}
    kept = [p for p in draft_probes if str(p.get("id")) in approve_ids]

    scenarios = scenario_texts(approval)
    if scenarios:
        run_progress.emit("probes", "super", f"Super writing {len(scenarios)} probe(s) from test ideas")
        extra, serr = generate_scenario_probes(
            provider,
            repo=repo,
            pr=pr,
            title=title,
            body=body,
            claims=claims,
            scenarios=scenarios,
            base_files=base_files,
            context_fn=_context,
            tidy_id=tidy_id,
            unescape_code=unescape_code,
            validate_probe=validate_probe,
        )
        errors.extend(serr)
        for p in extra:
            p["origin"] = HUMAN_REQUESTED
        kept.extend(extra)

    inputs = freeze.base_inputs(title, body, base_files, base_root, pr_roots)
    gen = freeze.generator("model", model=provider.models["probes"], provider=provider.name)
    outdir.mkdir(parents=True, exist_ok=True)
    by_id = {c["id"]: c for c in claims if c.get("testable")}
    claim_ids = set(by_id)
    frozen: list[dict] = []
    for p in kept:
        why = validate_probe(p, claim_ids)
        if why and claim_ids:
            # Dropped claims list still allowed for no-claims probes
            if p.get("claims"):
                errors.append(f"probe {p.get('id')!r} rejected after HITL: {why}")
                continue
            why = validate_probe(dict(p, claims=[]), set())
            if why:
                errors.append(f"probe {p.get('id')!r} rejected after HITL: {why}")
                continue
        path = outdir / f"model-{p['id']}.py"
        path.write_text(probe_file(p, f"{repo}#{pr}", by_id, gen["label"]))
        origin = p.get("origin") or "ai"
        out["probes"].append({"path": path, "freeze": freeze.freeze(path, gen, inputs), "origin": origin})
        frozen.append(p)
    draft_ids = [str(p.get("id")) for p in draft_probes]
    out["human_review"] = {
        "kept_ai_probes": [i for i in draft_ids if i in approve_ids],
        "dropped_ai_probes": [i for i in draft_ids if i not in approve_ids],
        "test_ideas": scenarios,
        "human_requested_probes": [str(p.get("id")) for p in frozen if p.get("origin") == HUMAN_REQUESTED],
        "claims_without_probe": uncovered_claims(claims, frozen),
    }
    run_progress.emit("probes", "super", f"Review approved {len(out['probes'])} probe(s)")
    return out
