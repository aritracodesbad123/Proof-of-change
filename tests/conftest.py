import json
from pathlib import Path

import pytest

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
