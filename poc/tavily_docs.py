"""Tavily doc lookup for a product check.

Probe generation does not call this. The product demo helper calls it on a console or daily
product check before either side is installed. That check does not start without TAVILY_API_KEY,
and a failed lookup stops it. A study run does not call this. The key is sent only as the
request body and is never written into the result.
"""
from __future__ import annotations

import json
import os
import urllib.request

KEY_ENV = "TAVILY_API_KEY"
API = "https://api.tavily.com/search"
MISSING_KEY = "Tavily key missing: set TAVILY_API_KEY. A check cannot run without the setup lookup."
EMPTY_RESPONSE = "the lookup returned an empty response"
INVALID_RESPONSE = "the lookup returned a response that was not valid"


def available(env: dict | None = None) -> bool:
    env = os.environ if env is None else env
    raw = env.get(KEY_ENV)
    return bool(raw and str(raw).strip())


def missing_key_line(env: dict | None = None) -> str | None:
    """The one-line refusal when the key is missing or blank. None when it is set.

    The line names the variable. It never contains the key.
    """
    if available(env):
        return None
    return MISSING_KEY


def lookup(query: str, *, max_results: int = 3, env: dict | None = None, timeout: float = 30) -> dict:
    """Fetch short snippets. ok is false when the key is missing or the call fails.

    timeout is seconds. The demo helper uses a short one. The key is removed from any error text.
    A missing key is a refusal, not a skip. An empty or unusable response is a failed lookup.
    """
    env = os.environ if env is None else env
    key = env.get(KEY_ENV)
    if not key or not str(key).strip():
        return {"ok": False, "error": MISSING_KEY, "query": query, "results": [], "refused": True}
    secret = str(key).strip()
    body = {"api_key": secret, "query": query, "max_results": max_results, "include_answer": True,
            "include_usage": True}
    req = urllib.request.Request(
        API, data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
        method="POST")  # br-allow-external: Tavily setup lookup for a product check
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310
            raw = r.read()
    except Exception as e:  # noqa: BLE001
        message = f"{type(e).__name__}: {e}".replace(secret, "[redacted]")
        return {"ok": False, "error": message, "query": query, "results": []}
    from poc import tavily_budget
    try:   # an answered call is billed; its own usage block says how much when it can be read
        parsed = json.loads(raw) if raw and raw.strip() else None
    except json.JSONDecodeError:
        parsed = None
    tavily_budget.record("search", depth=str(body.get("search_depth") or "basic"),
                         payload=parsed if isinstance(parsed, dict) else None)
    if not raw or not raw.strip():
        return {"ok": False, "error": EMPTY_RESPONSE, "query": query, "results": []}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {"ok": False, "error": INVALID_RESPONSE, "query": query, "results": []}
    if not isinstance(data, dict):
        return {"ok": False, "error": INVALID_RESPONSE, "query": query, "results": []}
    results = []
    for item in (data.get("results") or [])[:max_results]:
        if not isinstance(item, dict):
            continue
        results.append({"title": item.get("title"), "url": item.get("url"),
                        "content": (item.get("content") or "")[:500]})
    return {"ok": True, "answer": data.get("answer"), "results": results, "query": query}
