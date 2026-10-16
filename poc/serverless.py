"""Nebius Serverless AI entrypoints (REQUIREMENTS §4a).

orchestrate(event)  — webhook/API handler for a single PR run (endpoint)
daily_job(config)   — batch daily ops over tracked libraries (Serverless job)

Both are thin wrappers around ops.daily_run; they do not invent a second pipeline.
"""
from __future__ import annotations

import os
from typing import Any


def orchestrate(event: dict, env: dict | None = None) -> dict[str, Any]:
    """Serverless AI endpoint handler: start or describe a Proof-of-Change run.

    Expected event keys: repo, pr (int), optional claim, optional dry_run.
    Real Nebius deploy wires this function as the HTTP handler; locally it returns a plan.
    """
    env = os.environ if env is None else env
    repo = event.get("repo")
    pr = event.get("pr")
    if not repo or not pr:
        return {"ok": False, "error": "need repo and pr"}
    from poc.github_app import may_post
    if not may_post(str(repo), env) and not event.get("allow_any_repo"):
        return {"ok": False, "error": f"repo {repo} not in demo allowlist"}
    plan = {
        "ok": True,
        "action": "run",
        "repo": repo,
        "pr": int(pr),
        "claim": event.get("claim"),
        "argv": ["--libraries", str(repo).split("/")[-1], "--max-per-library", "1",
                 "--model-provider", event.get("model_provider") or "nebius"],
        "dry_run": bool(event.get("dry_run")),
    }
    if event.get("dry_run"):
        return plan
    # ponytail: live invoke stays out of the endpoint until Nebius deploy; return the plan for the job to pick up
    return plan | {"queued": True, "note": "enqueue via daily_job or ops.daily_run locally"}


def daily_job(config: dict | None = None) -> dict[str, Any]:
    """Serverless AI job: one daily batch. config may override argv fragments."""
    config = config or {}
    argv = list(config.get("argv") or [])
    if not argv:
        argv = ["--baseline", config.get("baseline") or "full",
                "--model-provider", config.get("model_provider") or "nebius"]
    if config.get("dry_run"):
        return {"ok": True, "dry_run": True, "argv": argv}
    # Import late so the job module stays importable without running the full daily CLI.
    from ops import daily_run
    code = daily_run.main(argv)
    return {"ok": code == 0, "exit": code, "argv": argv}


def health() -> dict:
    return {"service": "proof-of-change", "nebius_key_set": bool(os.environ.get("NEBIUS_API_KEY")),
            "contree_key_set": bool(os.environ.get("CONTREE_API_KEY"))}
