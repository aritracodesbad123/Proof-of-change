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
# Worst case for one check, built from the real call limits (a test ties each term to its source):
#   setup searches: one per demo_helper.lookup_queries entry (3)
#   setup-gap searches: one per repair try (3) plus the batch gate search (1)
#   related-reports search: 1
#   crawl: one call per seed (at most 2), each capped at tavily_crawl.CRAWL_LIMIT pages; basic crawl is
#          1 credit per 10 pages, so ceil(40 / 10) = 4 per seed
#   extract: one call of at most tavily_crawl.EXTRACT_MAX pages; basic extract is 1 credit per 5 pages, so 3
SETUP_SEARCHES, GAP_SEARCHES, RELATED_SEARCHES = 3, 4, 1
CRAWL_SEEDS, CRAWL_PAGES_PER_CREDIT, EXTRACT_PAGES_PER_CREDIT = 2, 10, 5


def worst_case(crawl_limit: int = 40, extract_max: int = 12) -> int:
    crawl = CRAWL_SEEDS * -(-crawl_limit // CRAWL_PAGES_PER_CREDIT)
    extract = -(-extract_max // EXTRACT_PAGES_PER_CREDIT)
    return SETUP_SEARCHES + GAP_SEARCHES + RELATED_SEARCHES + crawl + extract


WORST_CASE_CHECK = worst_case()

_lock = threading.Lock()
_active: dict | None = None   # the meter of the check now running in this process


def begin(check: str = "") -> dict:
    """Start metering one check and return its meter. Calls from any thread count toward it, so the parallel
    side preparation of one check adds up correctly. Checks in one process run one after another; if a second
    check starts before the first is taken, both meters are marked ``overlapped`` so neither total is trusted."""
    global _active
    meter = {"check": check, "search_calls": 0, "search_credits": 0.0, "crawl_calls": 0, "crawl_credits": 0.0,
             "extract_calls": 0, "extract_credits": 0.0, "overlapped": False}
    with _lock:
        if _active is not None:
            _active["overlapped"] = True
            meter["overlapped"] = True
        _active = meter
    return meter


def record(kind: str, *, depth: str = "basic", payload: dict | None = None) -> None:
    """Count one Tavily call toward the running check. kind is search, crawl or extract."""
    if kind == "search":
        credits = SEARCH_CREDITS.get(depth, 1.0)
    else:
        usage = (payload or {}).get("usage") if isinstance(payload, dict) else None
        try:
            credits = float((usage or {}).get("credits") or 0)
        except (TypeError, ValueError):
            credits = 0.0
    with _lock:
        if _active is None:
            return
        _active[f"{kind}_calls"] += 1
        _active[f"{kind}_credits"] += credits


def take(meter: dict | None) -> dict | None:
    """The totals of this check's meter, and stop metering it. None when the check was not metered."""
    global _active
    if not meter:
        return None
    with _lock:
        if _active is meter:
            _active = None
        out = dict(meter)
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
    if fetch is None and not str(env.get("TAVILY_API_KEY") or "").strip():
        return f"{LIMIT_REACHED}: TAVILY_API_KEY is not set, so the usage under the cap cannot be read"
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
