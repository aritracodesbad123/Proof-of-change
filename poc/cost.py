"""Cost of one review: AI tokens (input, output, thinking), the Nebius price for them, how many AI calls were made
(retries and review steps included) and how long the machine spent building and testing.

Prices are Nebius Token Factory list prices in US dollars per 1 million tokens, from
https://nebius.com/services/token-factory/models/nvidia-nemotron-models-inference (checked 2026-10-13).
Thinking ("reasoning") tokens are part of the output tokens the server reports and are billed as output.
"""
from __future__ import annotations

RATE_SOURCE = ("Nebius Token Factory list price, https://nebius.com/services/token-factory/models/"
               "nvidia-nemotron-models-inference (checked 2026-10-13)")
RATES = {  # model: (USD per 1M input tokens, USD per 1M output tokens)
    "nvidia/nemotron-3-super-120b-a12b": (0.30, 0.90),
    "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B": (0.06, 0.24),
}
_RATES_LOWER = {k.lower(): v for k, v in RATES.items()}

_ledger: list[dict] = []


def tokens(usage: dict | None) -> tuple[int, int, int] | None:
    """(input, output, thinking) from an OpenAI-style usage block, or None when the server sent none."""
    if not usage:
        return None
    thinking = ((usage.get("completion_tokens_details") or {}).get("reasoning_tokens")) or 0
    return int(usage.get("prompt_tokens") or 0), int(usage.get("completion_tokens") or 0), int(thinking)


def price(model: str | None, usage: dict | None) -> float | None:
    t, r = tokens(usage), _RATES_LOWER.get((model or "").lower())
    if t is None or r is None:
        return None
    return t[0] / 1e6 * r[0] + t[1] / 1e6 * r[1]


def record_call(model: str | None, usage: dict | None, ok: bool = True) -> None:
    """Note one AI call (also failed ones and retries) for the review that is running now."""
    _ledger.append({"model": model, "usage": usage, "ok": ok})


def summarize(calls: list[dict], compute_seconds: dict | None = None) -> dict:
    out = {"ai_calls": len(calls), "failed_ai_calls": sum(1 for c in calls if not c.get("ok", True)),
           "input_tokens": 0, "output_tokens": 0, "thinking_tokens": 0, "cost_usd": 0.0,
           "calls_without_usage": 0, "rate_source": RATE_SOURCE, "compute_seconds": compute_seconds or {}}
    for c in calls:
        t, p = tokens(c.get("usage")), price(c.get("model"), c.get("usage"))
        if t is None or p is None:
            out["calls_without_usage"] += 1
            continue
        out["input_tokens"] += t[0]
        out["output_tokens"] += t[1]
        out["thinking_tokens"] += t[2]
        out["cost_usd"] += p
    out["cost_usd"] = round(out["cost_usd"], 6)
    out["cost_complete"] = out["calls_without_usage"] == 0
    return out


def reset() -> None:
    _ledger.clear()


def take(compute_seconds: dict | None = None) -> dict:
    """Summary of the calls since the last reset/take, then start a new ledger."""
    s = summarize(list(_ledger), compute_seconds)
    _ledger.clear()
    return s


def peek(compute_seconds: dict | None = None) -> dict:
    return summarize(list(_ledger), compute_seconds)


def per_pr(records: list[dict]) -> dict:
    """The two headline numbers. Every attempt counts toward spend; only verified / needs_attention count as a
    final verdict."""
    spend = sum(r.get("cost_usd") or 0 for r in records)
    final = sum(1 for r in records if r.get("verdict") in ("verified", "needs_attention"))
    return {"attempted": len(records), "with_final_verdict": final, "total_usd": round(spend, 6),
            "per_pr_attempted_usd": round(spend / len(records), 6) if records else None,
            "per_pr_with_final_verdict_usd": round(spend / final, 6) if final else None}
