"""Hard limits for one watched live run: provider calls, AI spend, and the expected edited-pattern rule.

Each limit is off unless its flag is given. A limit that is hit stops the whole run with a plain reason (SystemExit),
before the provider call is sent or before any pull-request code runs. The reasons never contain an API key.
"""
from __future__ import annotations

import threading

_lock = threading.Lock()
_state: dict = {"max_calls": None, "max_cost": None, "sent": 0}


class RunLimitStop(SystemExit):
    """A run limit was reached. Carries the plain stop reason as its exit code text."""


_current: dict = {"rec": None, "prdir": None}


def configure(max_calls: int | None = None, max_cost_usd: float | None = None) -> None:
    """Set the limits and start a fresh count. Earlier calls in the same process (a second run) never count."""
    with _lock:
        _state.update(max_calls=max_calls, max_cost=max_cost_usd, sent=0)
        _calls.clear()
        _current.update(rec=None, prdir=None)


def watch_record(rec: dict, prdir) -> None:
    """The record of the check that is running now. A guard stop writes it to prdir/record.json first."""
    _current.update(rec=rec, prdir=prdir)


def stop(reason: str):
    """Write the running check's record as could_not_verify with the stop reason (and its probe plan, if any),
    then raise RunLimitStop. The record write never hides the stop."""
    rec, prdir = _current.get("rec"), _current.get("prdir")
    if rec is not None and prdir is not None:
        try:
            import json
            from pathlib import Path
            rec["verdict"], rec["reason"], rec["run_limit_stop"] = "could_not_verify", reason, reason
            Path(prdir).mkdir(parents=True, exist_ok=True)
            (Path(prdir) / "record.json").write_text(json.dumps(rec, indent=1, default=str))
        except Exception:  # noqa: BLE001, S110 - the stop itself still happens
            pass
    raise RunLimitStop(reason)


def worst_case_usd(model: str, system: str, user: str, max_tokens: int) -> float:
    """Highest price one call could cost: generous input count (2 characters a token) plus the full output budget.
    An unknown model is priced at the dearest known rate."""
    from poc import cost
    rate = cost._RATES_LOWER.get((model or "").lower()) or max(cost.RATES.values(), key=lambda r: r[1])
    return (len(system or "") + len(user or "")) / 2 / 1e6 * rate[0] + int(max_tokens) / 1e6 * rate[1]


_calls: list[dict] = []   # every call this process sent; "est" is its real price, or its worst case if unknown


def spent_usd() -> float:
    """AI spend so far: real prices where the server reported usage, worst-case prices where it did not."""
    with _lock:
        return _spent_locked()


def before_call(task: str, model: str, system: str, user: str, max_tokens: int) -> None:
    """Called just before a provider call is sent. Refuses the call when it would be over either limit."""
    with _lock:
        n, cap_n, cap_usd = _state["sent"] + 1, _state["max_calls"], _state["max_cost"]
        if cap_n is not None and n > cap_n:
            stop(f"STOPPED: provider call {n} ({task}) refused: --max-provider-calls is {cap_n}. "
                               "Nothing more was sent. Result: could not verify.")
        worst = worst_case_usd(model, system, user, max_tokens)
        spent = _spent_locked()
        if cap_usd is not None and spent + worst > cap_usd:
            stop(f"STOPPED: provider call {n} ({task}) refused: ${spent:.4f} spent plus up to "
                               f"${worst:.4f} for this call would pass --max-cost-usd {cap_usd:.2f}. "
                               "Nothing more was sent. Result: could not verify.")
        _state["sent"] = n
        _calls.append({"task": task, "est": worst, "actual": None})


def after_call(model: str | None, usage: dict | None) -> None:
    """Replace the last call's worst-case estimate with its real price when the server reported usage."""
    from poc import cost
    with _lock:
        if not _calls:
            return
        p = cost.price(model, usage)
        if p is not None:
            _calls[-1]["est"] = p
            _calls[-1]["actual"] = p


def _spent_locked() -> float:
    return sum(c["est"] for c in _calls)


def reset() -> None:
    with _lock:
        _state.update(max_calls=None, max_cost=None, sent=0)
        _calls.clear()
        _current.update(rec=None, prdir=None)


def boundary_rule_stop(expected: str | None, found) -> str | None:
    """--require-boundary-rule FILE:LINE. None when the probe plan's edited-pattern list is exactly that one entry,
    else the plain stop reason. Called after the probe plan is written and before any pull-request code runs."""
    if not expected:
        return None
    got = [f"{m.get('file')}:{m.get('line')}" for m in (found or []) if isinstance(m, dict)]
    if got == [expected.strip()]:
        return None
    return (f"STOPPED: the edited-pattern rule found {', '.join(got) or 'nothing'}, not {expected.strip()} "
            "(--require-boundary-rule). The probe plan was written; no pull-request code ran. "
            "Result: could not verify.")
