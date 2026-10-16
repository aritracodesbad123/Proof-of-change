"""Nebius Serverless AI entrypoints (REQUIREMENTS §4a).

orchestrate(event)  — webhook/API handler for a single PR run (endpoint)
daily_job(config)   — batch daily ops over tracked libraries (Serverless job)
console_http        — long-lived console API + SPA (same as poc.console_api)

Both orchestrate and daily_job wrap the real pipeline; console_http hosts the UI.
"""
from __future__ import annotations

import os
from typing import Any


def orchestrate(event: dict, env: dict | None = None) -> dict[str, Any]:
    """Serverless AI endpoint: enqueue a PR check (same path as the operator console).

    Expected event keys: repo + pr, or pr_url; optional model_provider, dry_run, allow_any_repo.
    """
    env = os.environ if env is None else env
    pr_url = (event.get("pr_url") or "").strip()
    repo = event.get("repo")
    pr = event.get("pr")
    if not pr_url and repo and pr:
        pr_url = f"https://github.com/{repo}/pull/{int(pr)}"
    if not pr_url:
        return {"ok": False, "error": "need pr_url or repo+pr"}

    from poc.github_app import may_post
    from poc.console_api import PR_RE

    m = PR_RE.search(pr_url)
    if not m:
        return {"ok": False, "error": "pr_url must look like https://github.com/owner/repo/pull/123"}
    repo_name = m.group(1)
    if not may_post(str(repo_name), env) and not event.get("allow_any_repo"):
        return {"ok": False, "error": f"repo {repo_name} not in demo allowlist"}

    provider = event.get("model_provider") or "nebius"
    plan = {
        "ok": True,
        "action": "run",
        "repo": repo_name,
        "pr": int(m.group(2)),
        "pr_url": pr_url,
        "model_provider": provider,
        "dry_run": bool(event.get("dry_run")),
    }
    if event.get("dry_run"):
        return plan

    from poc import console_api

    job = console_api.start_check(pr_url, model_provider=provider)
    return plan | {"queued": True, "job": job}


def daily_job(config: dict | None = None) -> dict[str, Any]:
    """Serverless AI job: one daily batch. config may override argv fragments."""
    config = config or {}
    argv = list(config.get("argv") or [])
    if not argv:
        argv = ["--baseline", config.get("baseline") or "full",
                "--model-provider", config.get("model_provider") or "nebius"]
    if config.get("dry_run"):
        return {"ok": True, "dry_run": True, "argv": argv}
    from ops import daily_run
    code = daily_run.main(argv)
    return {"ok": code == 0, "exit": code, "argv": argv}


def health() -> dict:
    return {
        "service": "proof-of-change",
        "console": True,
        "nebius_key_set": bool(os.environ.get("NEBIUS_API_KEY")),
        "contree_ready": bool(os.environ.get("NEBIUS_API_KEY") and os.environ.get("NEBIUS_PROJECT_ID")),
    }


def console_http(host: str | None = None, port: int | None = None) -> None:
    """Long-lived process for Nebius (or local): serve SPA + /api/*."""
    from poc.console_api import serve

    serve(
        host or os.environ.get("POC_CONSOLE_HOST", "0.0.0.0"),
        int(port or os.environ.get("POC_CONSOLE_PORT", "8787")),
    )
