"""Tavily credit metering and an up-front credit cap for a product check.

Every Tavily call a check makes goes through ``record``: a basic search costs 1 credit, an advanced one 2,
and crawl and extract report their own cost in the response ``usage`` block. ``take`` returns the per-check
totals for the record and the log.

``refusal`` runs before a check makes its first Tavily call. With ``POC_TAVILY_CREDIT_CAP`` set it reads the
account's current usage from Tavily's usage endpoint and refuses when the worst case for one check would take
usage past the cap (or past the plan limit Tavily reports). The check then stops with
"Tavily credit limit reached" instead of failing halfway. The key is never written into any message.
"""
from __future__ import annotations

import json
import os
import threading
import urllib.request

CAP_ENV = "POC_TAVILY_CREDIT_CAP"
USAGE_API = "https://api.tavily.com/usage"
LIMIT_REACHED = "Tavily credit limit reached"
SEARCH_CREDITS = {"basic": 1.0, "advanced": 2.0}
# Worst case for one check: 3 setup searches, up to 4 setup-gap searches, 1 related-reports search, and an
# uncached repository crawl (2 seeds x 40 pages, about 4 credits each) plus one extract of up to 12 pages.
WORST_CASE_CHECK = 3 + 4 + 1 + 8 + 3

_lock = threading.Lock()
_meter: dict = {}


def reset() -> None:
    with _lock:
        _meter.clear()
        _meter.update(search_calls=0, search_credits=0.0, crawl_calls=0, crawl_credits=0.0,
                      extract_calls=0, extract_credits=0.0)


def record(kind: str, *, depth: str = "basic", payload: dict | None = None) -> None:
    """Count one Tavily call. kind is search, crawl or extract."""
    with _lock:
        if not _meter:
            return
        if kind == "search":
            credits = SEARCH_CREDITS.get(depth, 1.0)
        else:
            usage = (payload or {}).get("usage") if isinstance(payload, dict) else None
            try:
                credits = float((usage or {}).get("credits") or 0)
            except (TypeError, ValueError):
                credits = 0.0
        _meter[f"{kind}_calls"] = _meter.get(f"{kind}_calls", 0) + 1
        _meter[f"{kind}_credits"] = _meter.get(f"{kind}_credits", 0.0) + credits


def take() -> dict | None:
    """The per-check totals, or None when no check is being metered."""
    with _lock:
        if not _meter:
            return None
        out = dict(_meter)
    out["total_credits"] = round(out["search_credits"] + out["crawl_credits"] + out["extract_credits"], 2)
    return out


def log_line(totals: dict | None) -> str:
    if not totals:
        return ""
    return (f"Tavily credits used: {totals['total_credits']:g} (search {totals['search_calls']} call(s) "
            f"{totals['search_credits']:g}, crawl {totals['crawl_calls']} {totals['crawl_credits']:g}, "
            f"extract {totals['extract_calls']} {totals['extract_credits']:g})")


def _cap(env: dict) -> float | None:
    raw = str(env.get(CAP_ENV) or "").strip()
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        return -1.0


def fetch_usage(env: dict | None = None, timeout: float = 15) -> dict:
    env = os.environ if env is None else env
    secret = str(env.get("TAVILY_API_KEY") or "").strip()
    req = urllib.request.Request(USAGE_API, headers={"Authorization": f"Bearer {secret}"},
                                 method="GET")  # br-allow-external: Tavily credit usage for the credit cap
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310
            data = json.loads(r.read() or b"")
    except Exception as e:  # noqa: BLE001
        msg = f"{type(e).__name__}: {e}"
        return {"ok": False, "error": msg.replace(secret, "[redacted]") if secret else msg}
    if not isinstance(data, dict):
        return {"ok": False, "error": "the usage response was not valid"}
    data["ok"] = True
    return data


def used_and_limit(usage: dict) -> tuple[float | None, float | None]:
    acct = usage.get("account") or {}
    key = usage.get("key") or {}
    used = acct.get("plan_usage", key.get("usage"))
    limit = acct.get("plan_limit", key.get("limit"))
    try:
        used = None if used is None else float(used) + float(acct.get("paygo_usage") or 0)
        if limit is not None:
            limit = float(limit) + float(acct.get("paygo_limit") or 0)
    except (TypeError, ValueError):
        return None, None
    return used, limit


def refusal(env: dict | None = None, fetch=None, need: float = WORST_CASE_CHECK) -> str | None:
    """None when the check may start. A one-line refusal when the cap would be passed.

    Without POC_TAVILY_CREDIT_CAP nothing is checked. With it set, an unreadable usage endpoint also refuses,
    since the cap cannot be confirmed.
    """
    env = os.environ if env is None else env
    cap = _cap(env)
    if cap is None:
        return None
    if cap < 0:
        return f"{LIMIT_REACHED}: {CAP_ENV} is not a number"
    got = (fetch or (lambda: fetch_usage(env)))()
    if not isinstance(got, dict) or not got.get("ok"):
        detail = (got or {}).get("error") if isinstance(got, dict) else "no response"
        return f"{LIMIT_REACHED}: the current Tavily usage could not be read ({detail}), so the cap cannot be confirmed"
    used, limit = used_and_limit(got)
    if used is None:
        return f"{LIMIT_REACHED}: the Tavily usage response had no usage figure"
    ceiling = cap if limit is None else min(cap, limit)
    if used + need > ceiling:
        return (f"{LIMIT_REACHED}: {used:g} of {ceiling:g} credits used, and one check can need up to "
                f"{need:g}")
    return None
