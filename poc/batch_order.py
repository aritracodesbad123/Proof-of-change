"""Batch order for a product run: lookup first, then setup, then the run, one PR at a time.

Pass 1 goes through the PRs in order. A PR whose setup lookup fails, or whose setup fails, is logged and skipped,
and the batch moves on to the next PR. After every other PR is done, the end pass takes each skipped PR again:
the lookup diagnoses the failure, the fix is applied on both sides and setup is retried, up to 3 tries. A PR
that still fails gets "could not verify". Every step is written to the order log.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Callable

MAX_TRIES = 3


def is_setup_failure(rec: dict | None) -> bool:
    """True when the record failed in setup or install, not in a test."""
    from poc import demo_helper
    if not isinstance(rec, dict):
        return False
    if not demo_helper.counts_as_verdict(rec):
        return True
    if rec.get("verdict") != "could_not_verify":
        return False
    reason = str(rec.get("reason") or "").lower()
    return any(m in reason for m in ("setup failed", "install failed", "could not be set up", "build failed",
                                     "setup problem", "source checkout", "dependency install"))


class OrderLog:
    def __init__(self, path: Path | None):
        self.path = Path(path) if path else None
        self.rows: list[dict] = []

    def add(self, key: str, step: str, outcome: str, **extra) -> None:
        row = {"at": time.strftime("%Y-%m-%d %H:%M:%S"), "pr": key, "step": step, "outcome": outcome, **extra}
        self.rows.append(row)
        print(f"[order] {key}: {step}: {outcome}", flush=True)
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(row, default=str) + "\n")


def run_batch(items: list, key: Callable, lookup: Callable, run: Callable, *, diagnose: Callable | None = None,
              give_up: Callable | None = None, log: OrderLog | None = None, max_tries: int = MAX_TRIES) -> list[dict]:
    """Run ``items`` in batch order and return the final records, in the order they finished.

    lookup(item) -> bool: the setup lookup worked. run(item) -> record or None.
    diagnose(item, failure_text) -> None: look the failure up and stage a fix for both sides before the next try.
    give_up(item, why) -> record: the "could not verify" record for a PR that never got through setup.
    """
    log = log or OrderLog(None)
    done: list[dict] = []
    skipped: list[tuple] = []
    for pos, item in enumerate(items, 1):
        k = key(item)
        log.add(k, "queue", f"position {pos} of {len(items)}")
        if not lookup(item):
            log.add(k, "setup lookup", "failed; skipped for the end pass")
            skipped.append((item, "the setup lookup failed"))
            continue
        log.add(k, "setup lookup", "ok")
        rec = run(item)
        if rec is None:
            log.add(k, "run", "no record; skipped for the end pass")
            skipped.append((item, "the run gave no record"))
            continue
        if is_setup_failure(rec):
            why = str(rec.get("reason") or "setup failed")
            log.add(k, "setup", f"failed; skipped for the end pass: {why[:160]}")
            skipped.append((item, why))
            continue
        log.add(k, "run", f"done: {rec.get('verdict')}")
        done.append(rec)
    if skipped:
        log.add("-", "end pass", f"retrying {len(skipped)} skipped PR(s)")
    for item, why in skipped:
        k = key(item)
        final = None
        for attempt in range(1, max_tries + 1):
            tag = f"end pass try {attempt} of {max_tries}"
            if diagnose is not None:
                try:
                    diagnose(item, why)
                    log.add(k, f"{tag}: diagnosis", "looked up the failure; fix staged for main and pr")
                except Exception as exc:  # noqa: BLE001 — a failed diagnosis is logged, the try still counts
                    log.add(k, f"{tag}: diagnosis", f"failed ({type(exc).__name__})")
            if not lookup(item):
                why = "the setup lookup failed"
                log.add(k, f"{tag}: setup lookup", "failed")
                continue
            log.add(k, f"{tag}: setup lookup", "ok")
            rec = run(item)
            if rec is None:
                why = "the run gave no record"
                log.add(k, f"{tag}: run", "no record")
                continue
            if is_setup_failure(rec):
                why = str(rec.get("reason") or "setup failed")
                log.add(k, f"{tag}: setup", f"failed: {why[:160]}")
                final = rec
                continue
            log.add(k, f"{tag}: run", f"done: {rec.get('verdict')}")
            final = rec
            break
        else:
            if final is None and give_up is not None:
                final = give_up(item, why)
            if final is not None:
                final["verdict"] = "could_not_verify"
                final["reason"] = f"could not verify: setup still failed after {max_tries} tries: {why}"[:400]
            log.add(k, "end pass", f"gave up after {max_tries} tries: could not verify")
        if final is not None:
            final.setdefault("batch_order", {})["end_pass"] = True
            done.append(final)
    return done
