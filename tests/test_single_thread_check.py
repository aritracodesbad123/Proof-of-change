"""The single-thread self-check accepts the recorded PYTHONHASHSEED=0 (2026-10-15 decision)."""
import json
from pathlib import Path

import pytest

from ops.daily_run import THREAD_ENV
from reports import pr_report


def _status(te):
    rec = {"thread_env": te, "machine_type": {"label": "x"}}
    try:
        rows = pr_report.checks(rec)
    except Exception:  # minimal record: fall back to a full fixture record
        fx = sorted(Path(__file__).parent.glob("fixtures/**/record.json"))
        if not fx:
            pytest.skip("no fixture record")
        rec = json.loads(fx[0].read_text()) | {"thread_env": te}
        rows = pr_report.checks(rec)
    return next(r[1] for r in rows if r[0] == "Single-thread environment")


@pytest.mark.parametrize("te,want", [
    (dict(THREAD_ENV, PYTHONHASHSEED="0"), "PASS"),
    (dict(THREAD_ENV), "PASS"),
    (dict(THREAD_ENV, PYTHONHASHSEED="1"), "FAIL"),
    (dict(THREAD_ENV, OMP_NUM_THREADS="8", PYTHONHASHSEED="0"), "FAIL"),
    ({"PYTHONHASHSEED": "0"}, "FAIL"),
    ({}, "FAIL"),
])
def test_single_thread_check(te, want):
    assert _status(te) == want
