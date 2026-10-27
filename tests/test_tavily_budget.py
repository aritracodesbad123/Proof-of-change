"""Tavily credit metering, the crawl cache across processes, and the up-front credit cap.
Every Tavily call is mocked; no key is real and none is needed."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

from poc import tavily_budget, tavily_crawl, tavily_docs

REPO = "acme/widget"
SHA = "d" * 40
ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def _no_keys(monkeypatch, tmp_path):
    for name in ("TAVILY_API_KEY", tavily_budget.CAP_ENV):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv(tavily_crawl.CACHE_ENV, str(tmp_path / "cache"))
    tavily_budget._meter.clear()
    yield
    tavily_budget._meter.clear()


def _usage(used, limit=1000):
    return {"ok": True, "key": {"usage": used, "limit": None},
            "account": {"plan_usage": used, "plan_limit": limit, "paygo_usage": 0, "paygo_limit": None}}


def test_meter_counts_each_kind_and_totals():
    tavily_budget.reset()
    tavily_budget.record("search")
    tavily_budget.record("search", depth="advanced")
    tavily_budget.record("crawl", payload={"usage": {"credits": 4}})
    tavily_budget.record("extract", payload={"usage": {"credits": 2}})
    got = tavily_budget.take()
    assert got["search_calls"] == 2 and got["search_credits"] == 3
    assert got["crawl_credits"] == 4 and got["extract_credits"] == 2 and got["total_credits"] == 9
    assert "Tavily credits used: 9" in tavily_budget.log_line(got)


def test_no_meter_outside_a_check():
    tavily_budget.record("search")
    assert tavily_budget.take() is None


def test_answered_search_is_metered(monkeypatch):
    class R:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self): return json.dumps({"results": []}).encode()
    monkeypatch.setattr(tavily_docs.urllib.request, "urlopen", lambda *a, **k: R())
    tavily_budget.reset()
    tavily_docs.lookup("q", env={"TAVILY_API_KEY": "tvly-test-not-real"})
    assert tavily_budget.take()["search_calls"] == 1


def test_missing_key_search_is_not_metered():
    tavily_budget.reset()
    tavily_docs.lookup("q", env={})
    assert tavily_budget.take()["search_calls"] == 0


def test_no_cap_never_checks_usage():
    assert tavily_budget.refusal(env={}, fetch=lambda: pytest.fail("usage read without a cap")) is None


def test_cap_refuses_up_front_when_one_check_would_pass_it():
    env = {tavily_budget.CAP_ENV: "990"}
    line = tavily_budget.refusal(env=env, fetch=lambda: _usage(985))
    assert line.startswith(tavily_budget.LIMIT_REACHED)
    assert tavily_budget.refusal(env=env, fetch=lambda: _usage(900)) is None


def test_plan_limit_caps_below_a_higher_cap():
    env = {tavily_budget.CAP_ENV: "5000"}
    assert tavily_budget.refusal(env=env, fetch=lambda: _usage(995)).startswith(tavily_budget.LIMIT_REACHED)


def test_unreadable_usage_refuses_when_capped_and_hides_the_key():
    env = {tavily_budget.CAP_ENV: "900", "TAVILY_API_KEY": "tvly-secret-not-real"}
    line = tavily_budget.refusal(env=env, fetch=lambda: {"ok": False, "error": "timeout"})
    assert line.startswith(tavily_budget.LIMIT_REACHED) and "tvly-secret" not in line


def test_bad_cap_value_refuses():
    assert tavily_budget.refusal(env={tavily_budget.CAP_ENV: "lots"}).startswith(tavily_budget.LIMIT_REACHED)


def test_crawl_cache_is_reused_by_a_second_process(tmp_path):
    checkout = tmp_path / "co"
    checkout.mkdir()
    (checkout / "pyproject.toml").write_text('[project]\nname = "widget"\n')
    cache = tmp_path / "shared-cache"
    script = f"""
import json, sys
sys.path.insert(0, {str(ROOT)!r})
from poc import tavily_crawl
calls = []
def crawl_fn(url, **kw):
    calls.append(url)
    return {{"ok": True, "usage": {{"credits": 1}}, "results": [
        {{"url": "https://github.com/{REPO}/blob/{SHA}/CONTRIBUTING.md", "raw_content": "pip install -e ."}}]}}
def extract_fn(urls):
    calls.append("extract")
    return {{"ok": True, "usage": {{"credits": 1}}, "results": []}}
got = tavily_crawl.crawl_repo({REPO!r}, {SHA!r}, {str(checkout)!r}, env={{"TAVILY_API_KEY": "tvly-not-real"}},
                              crawl_fn=crawl_fn, extract_fn=extract_fn, cache_root={str(cache)!r})
print(json.dumps({{"calls": len(calls), "hit": got["cache"]["hit"], "credits": got["credits"]}}))
"""
    runs = [json.loads(subprocess.run([sys.executable, "-c", script], capture_output=True, text=True,
                                      check=True).stdout.strip().splitlines()[-1]) for _ in range(2)]
    assert runs[0]["calls"] >= 1 and not runs[0]["hit"]
    assert runs[1] == {"calls": 0, "hit": True, "credits": 0.0}
    assert not list(cache.glob("*.tmp"))
