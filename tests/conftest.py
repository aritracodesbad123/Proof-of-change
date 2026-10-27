import json
from pathlib import Path

import pytest

from poc import hitl as _hitl


@pytest.fixture(autouse=True)
def _reset_operator_approval_mark():
    """The approval mark is per pull request. Tests must not inherit it."""
    _hitl.reset_approval_ran()
    yield
    _hitl.reset_approval_ran()


def pytest_configure(config):
    config.addinivalue_line("markers", "real_key_gate: run with the console's real typed-key gate")
    config.addinivalue_line("markers", "real_tavily_gate: run with the console's real Tavily-key gate")


@pytest.fixture(autouse=True)
def _typed_key_gate(request, monkeypatch):
    """Most console tests exercise later stages, so they pass the typed-key gate.
    Tests marked real_key_gate check the gate itself."""
    if request.node.get_closest_marker("real_key_gate") is None:
        from poc import console_api
        monkeypatch.setattr(console_api, "_has_typed_key", lambda _token: True)
    yield


@pytest.fixture(autouse=True)
def _tavily_key_gate(request, monkeypatch):
    """Most console tests exercise later stages, so they pass the Tavily key gate.
    Tests marked real_tavily_gate check the gate itself."""
    if request.node.get_closest_marker("real_tavily_gate") is None:
        from poc import console_api
        monkeypatch.setattr(console_api, "_has_tavily_key", lambda _token, base=None: True)
    yield


FIX = Path(__file__).parent / "fixtures"
REPO = Path(__file__).parent.parent


@pytest.fixture
def legacy_records():
    return [json.loads(x) for x in (FIX / "observations_legacy.jsonl").read_text().splitlines() if x.strip()]


@pytest.fixture
def ci_records():
    p = REPO / "evals" / "fixtures" / "observations_ci.jsonl"
    return [json.loads(x) for x in p.read_text().splitlines() if x.strip()]


@pytest.fixture
def upset(ci_records):
    return next(r for r in ci_records if r["dependent"] == "UpSetPlot")


@pytest.fixture
def imblearn(ci_records):
    return next(r for r in ci_records if r["dependent"] == "imbalanced-learn")


@pytest.fixture
def dev_imblearn(legacy_records):
    """The runner's dev calibration record (runner miscount; must fail the raw-reproduction gates)."""
    return next(r for r in legacy_records if r["dependent"] == "imbalanced-learn")


FIXTURE_RUNS = REPO / "evals" / "fixtures"


@pytest.fixture
def golden_v1_records():
    """The three final golden records (shared schema v1, HARNESS_VERSION 1.0, 10 Oct 2026 IST)."""
    p = REPO / "evals" / "fixtures" / "golden_v1.jsonl"
    return [json.loads(x) for x in p.read_text().splitlines() if x.strip()]


@pytest.fixture
def g_sklearn(golden_v1_records):
    return next(r for r in golden_v1_records if r["new_version"] == "1.6.0rc1")


@pytest.fixture
def g_pandas(golden_v1_records):
    return next(r for r in golden_v1_records if r["dependent"] == "UpSetPlot")


@pytest.fixture
def g_clean(golden_v1_records):
    return next(r for r in golden_v1_records if r["old_version"] == "1.5.1")


@pytest.fixture(autouse=True)
def _no_box_replay(monkeypatch):
    """Tests never read a machine-local replay status file; tests that need one set BR_GOLDEN_STATUS."""
    monkeypatch.setenv("BR_GOLDEN_STATUS", "")


@pytest.fixture(autouse=True)
def _reset_contree_bridge():
    """Contree select/session is process-global; clear so one test cannot make later run_tests/run_probes go remote."""
    from poc import contree_sandboxes
    contree_sandboxes.select("local")
    contree_sandboxes.clear_session()
    yield
    contree_sandboxes.select("local")
    contree_sandboxes.clear_session()
