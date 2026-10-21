"""Optional Tavily doc lookup.

Probe generation does not call this. The product demo helper calls it on a console or daily
check when TAVILY_API_KEY is set, before either side is installed. A study run does not.
The key is sent only as the request body and is never written into the result.
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


def lookup(query: str, *, max_results: int = 3, env: dict | None = None, timeout: float = 30) -> dict:
    """Fetch short snippets. Returns ok false when the key is missing or the call fails.

    timeout is seconds. The demo helper uses a short one. The key is removed from any error text.
    """
    env = os.environ if env is None else env
    key = env.get(KEY_ENV)
    if not key or not str(key).strip():
        return {"ok": False, "error": f"{KEY_ENV} not set; Tavily lookup skipped", "query": query, "results": []}
    secret = str(key).strip()
    body = {"api_key": secret, "query": query, "max_results": max_results, "include_answer": True}
    req = urllib.request.Request(
        API, data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
        method="POST")  # br-allow-external: optional Tavily doc lookup for probes
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310
            data = json.loads(r.read())
    except Exception as e:  # noqa: BLE001
        message = f"{type(e).__name__}: {e}".replace(secret, "[redacted]")
        return {"ok": False, "error": message, "query": query, "results": []}
    results = []
    for item in (data.get("results") or [])[:max_results]:
        results.append({"title": item.get("title"), "url": item.get("url"),
                        "content": (item.get("content") or "")[:500]})
    return {"ok": True, "answer": data.get("answer"), "results": results, "query": query}
