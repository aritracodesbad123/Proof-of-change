"""A product check refuses to start unless NEBIUS_API_KEY, TAVILY_API_KEY and NEBIUS_PROJECT_ID are all set."""
from __future__ import annotations

import types

import pytest

from ops import daily_run

VALUES = {"NEBIUS_API_KEY": "neb-secret-111", "TAVILY_API_KEY": "tav-secret-222", "NEBIUS_PROJECT_ID": "proj-333"}


def product_args(**kw):
    return types.SimpleNamespace(pr=["https://github.com/o/r/pull/1"], product_check=True, bench=False,
                                 select_only=False, report_only=False, **kw)


def test_all_present_starts():
    assert daily_run.product_keys_start_refusal(product_args(), env=dict(VALUES)) is None


@pytest.mark.parametrize("gone", list(VALUES))
@pytest.mark.parametrize("how", ["missing", "blank"])
def test_each_missing_key_refuses_by_name_without_values(gone, how):
    env = dict(VALUES)
    if how == "missing":
        env.pop(gone)
    else:
        env[gone] = "   "
    line = daily_run.product_keys_start_refusal(product_args(), env=env)
    assert line and gone in line.split("missing:")[1]
    assert not any(v in line for v in VALUES.values())
    others = [k for k in VALUES if k != gone]
    assert not any(k in line.split("missing:")[1].split(".")[0] for k in others)


def test_all_missing_lists_all():
    line = daily_run.product_keys_start_refusal(product_args(), env={})
    tail = line.split("missing:")[1]
    assert all(k in tail for k in VALUES)


def test_study_and_benchmark_runs_unchanged():
    study = types.SimpleNamespace(pr=[], product_check=False, bench=False, select_only=False, report_only=False)
    assert daily_run.product_keys_start_refusal(study, env={}) is None
    bench = product_args()
    bench.bench = True
    assert daily_run.product_keys_start_refusal(bench, env={}) is None
