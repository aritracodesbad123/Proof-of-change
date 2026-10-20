"""Cost of one review: AI tokens (input, output, thinking), the Nebius price for them, how many AI calls were made
(retries and review steps included) and how long the machine spent building and testing.

Advisory swarm calls (judge, helper, summary) are tallied on `swarm` and left out of the headline totals, so a
study run stays comparable with the paper's section 7.10 figures.

Prices are Nebius Token Factory list prices in US dollars per 1 million tokens, from
https://nebius.com/services/token-factory/models/nvidia-nemotron-models-inference (checked 2026-10-13).
Thinking ("reasoning") tokens are part of the output tokens the server reports and are billed as output.
"""
from __future__ import annotations

from contextlib import contextmanager

RATE_SOURCE = ("Nebius Token Factory list price, https://nebius.com/services/token-factory/models/"
               "nvidia-nemotron-models-inference (checked 2026-10-13)")
RATES = {  # model: (USD per 1M input tokens, USD per 1M output tokens)
    "nvidia/nemotron-3-super-120b-a12b": (0.30, 0.90),
    "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B": (0.06, 0.24),
}
_RATES_LOWER = {k.lower(): v for k, v in RATES.items()}

# Computer time is priced at a cloud machine comparable to the test machine the runs use (8 vCPU Intel Xeon, ~16 GiB RAM).
# Matched: Nebius CPU-only Intel Ice Lake platform (cpu-d3), preset 8vcpu-32gb, the smallest preset with 8 vCPUs:
# 8 x $0.012 per vCPU-hour + 32 x $0.0045 per GiB-hour = $0.24 per hour. Override with POC_MACHINE_USD_PER_HOUR.
MACHINE_RATE_DEFAULT = 0.24
MACHINE_RATE_SOURCE = ("Nebius AI Cloud compute pricing, https://docs.nebius.com/compute/resources/pricing (checked "
                       "2026-10-13; prices from 2026-10-01): Intel Ice Lake cpu-d3 preset 8vcpu-32gb, "
                       "8 x $0.012/vCPU-h + 32 x $0.0045/GiB-h")


def machine_rate() -> tuple[float, str]:
    import os
    v = os.environ.get("POC_MACHINE_USD_PER_HOUR")
    if v:
        return float(v), "POC_MACHINE_USD_PER_HOUR (set by the operator)"
    return MACHINE_RATE_DEFAULT, MACHINE_RATE_SOURCE


def computer_cost(seconds: float | None) -> float:
    return round((seconds or 0) / 3600 * machine_rate()[0], 6)


_ledger: list[dict] = []
_swarm_depth = 0


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


@contextmanager
def swarm_scope():
    """Mark AI calls recorded inside this block as advisory-swarm spend."""
    global _swarm_depth
    _swarm_depth += 1
    try:
        yield
    finally:
        _swarm_depth -= 1


def record_call(model: str | None, usage: dict | None, ok: bool = True, swarm: bool = False) -> None:
    """Note one AI call (also failed ones and retries) for the review that is running now.

    Calls inside swarm_scope(), or passed swarm=True, are kept on the swarm line and left out of the headline total.
    """
    _ledger.append({"model": model, "usage": usage, "ok": ok, "swarm": bool(swarm) or _swarm_depth > 0})


def _tally(calls: list[dict]) -> dict:
    out = {"ai_calls": len(calls), "failed_ai_calls": sum(1 for c in calls if not c.get("ok", True)),
           "input_tokens": 0, "output_tokens": 0, "thinking_tokens": 0, "cost_usd": 0.0,
           "calls_without_usage": 0}
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
    out["ai_cost_usd"] = out["cost_usd"]
    out["cost_complete"] = out["calls_without_usage"] == 0
    return out


def summarize(calls: list[dict], compute_seconds: dict | None = None) -> dict:
    main = [c for c in calls if not c.get("swarm")]
    swarm = _tally([c for c in calls if c.get("swarm")])
    swarm["rate_source"] = RATE_SOURCE
    out = _tally(main)
    out["rate_source"] = RATE_SOURCE
    out["compute_seconds"] = compute_seconds or {}
    rate, src = machine_rate()
    out["machine_usd_per_hour"], out["machine_rate_source"] = rate, src
    out["computer_cost_usd"] = computer_cost((compute_seconds or {}).get("total_wall"))
    # Headline total is study spend only: claims, probes and computer time. Swarm dollars stay on out["swarm"].
    out["total_cost_usd"] = round(out["ai_cost_usd"] + out["computer_cost_usd"], 6)
    out["swarm"] = swarm
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
    """The headline numbers. Each record gives cost_usd (AI) and optionally computer_cost_usd. Every attempt counts
    toward spend; only verified / needs_attention count as a final verdict."""
    ai = sum(r.get("cost_usd") or 0 for r in records)
    comp = sum(r.get("computer_cost_usd") or 0 for r in records)
    n = len(records)
    final = sum(1 for r in records if r.get("verdict") in ("verified", "needs_attention"))
    div = lambda x, d: round(x / d, 6) if d else None   # noqa: E731
    return {"attempted": n, "with_final_verdict": final, "verdict_rate": div(final, n),
            "total_usd": round(ai, 6), "ai_usd": round(ai, 6), "computer_usd": round(comp, 6),
            "total_all_usd": round(ai + comp, 6),
            "per_pr_attempted_usd": div(ai, n), "per_pr_with_final_verdict_usd": div(ai, final),
            "ai_per_attempted": div(ai, n), "computer_per_attempted": div(comp, n), "total_per_attempted": div(ai + comp, n),
            "ai_per_final": div(ai, final), "computer_per_final": div(comp, final),
            "total_per_final": div(ai + comp, final)}
