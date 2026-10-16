"""Optional Tavily doc lookup for probes that need live docs (REQUIREMENTS stretch / Tavily bonus).

Only called when a probe explicitly requests docs and TAVILY_API_KEY is set. Never runs by default
in the daily path — claim/probe generation stays offline.
"""
from __future__ import annotations

import json
import os
import urllib.request

KEY_ENV = "TAVILY_API_KEY"
API = "https://api.tavily.com/search"


def available(env: dict | None = None) -> bool:
    env = os.environ if env is None else env
    raw = env.get(KEY_ENV)
    return bool(raw and str(raw).strip())


def lookup(query: str, *, max_results: int = 3, env: dict | None = None) -> dict:
    """Fetch short doc/changelog snippets for a probe. Raises if key missing."""
    env = os.environ if env is None else env
    key = env.get(KEY_ENV)
    if not key or not str(key).strip():
        return {"ok": False, "error": f"{KEY_ENV} not set; Tavily lookup skipped"}
    body = {"api_key": key, "query": query, "max_results": max_results, "include_answer": True}
    req = urllib.request.Request(
        API, data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
        method="POST")  # br-allow-external: optional Tavily doc lookup for probes
    try:
        with urllib.request.urlopen(req, timeout=30) as r:  # noqa: S310
            data = json.loads(r.read())
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}
    results = []
    for item in (data.get("results") or [])[:max_results]:
        results.append({"title": item.get("title"), "url": item.get("url"),
                        "content": (item.get("content") or "")[:500]})
    return {"ok": True, "answer": data.get("answer"), "results": results, "query": query}
