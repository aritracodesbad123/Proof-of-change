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
    tavily_budget._active = None
    yield
    tavily_budget._active = None


def _usage(used, limit=1000):
    return {"ok": True, "key": {"usage": used, "limit": None},
            "account": {"plan_usage": used, "plan_limit": limit, "paygo_usage": 0, "paygo_limit": None}}


def test_meter_counts_each_kind_and_totals():
    m = tavily_budget.begin("c")
    tavily_budget.record("search")
    tavily_budget.record("search", depth="advanced")
    tavily_budget.record("crawl", payload={"usage": {"credits": 4}})
    tavily_budget.record("extract", payload={"usage": {"credits": 2}})
    got = tavily_budget.take(m)
    assert not got["overlapped"]
    assert got["search_calls"] == 2 and got["search_credits"] == 3
    assert got["crawl_credits"] == 4 and got["extract_credits"] == 2 and got["total_credits"] == 9
    assert "Tavily credits used: 9" in tavily_budget.log_line(got)


def test_no_meter_outside_a_check():
    tavily_budget.record("search")
    assert tavily_budget.take(None) is None


def test_answered_search_is_metered(monkeypatch):
    class R:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self): return json.dumps({"results": []}).encode()
    monkeypatch.setattr(tavily_docs.urllib.request, "urlopen", lambda *a, **k: R())
    m = tavily_budget.begin()
    tavily_docs.lookup("q", env={"TAVILY_API_KEY": "tvly-test-not-real"})
    assert tavily_budget.take(m)["search_calls"] == 1


def test_missing_key_search_is_not_metered():
    m = tavily_budget.begin()
    tavily_docs.lookup("q", env={})
    assert tavily_budget.take(m)["search_calls"] == 0


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


_SCRIPT = """
import json, sys, time
sys.path.insert(0, {root!r})
from poc import tavily_crawl
calls = []
def crawl_fn(url, **kw):
    calls.append(url)
    time.sleep({delay})   # hold the lock long enough that a second run is sure to wait on it
    return {{"ok": True, "usage": {{"credits": 1}}, "results": [
        {{"url": "https://github.com/{repo}/blob/{sha}/CONTRIBUTING.md", "raw_content": "pip install -e ."}}]}}
def extract_fn(urls):
    calls.append("extract")
    return {{"ok": True, "usage": {{"credits": 1}}, "results": []}}
start = {start!r}
while start and not __import__("os").path.exists(start):
    time.sleep(0.005)
got = tavily_crawl.crawl_repo({repo!r}, {sha!r}, {checkout!r}, env={{"TAVILY_API_KEY": "tvly-not-real"}},
                              crawl_fn=crawl_fn, extract_fn=extract_fn, cache_root={cache!r})
print(json.dumps({{"crawls": sum(1 for c in calls if c != "extract"), "hit": got["cache"]["hit"]}}))
"""


def _script(tmp_path, start="", delay=0.0):
    checkout = tmp_path / "co"
    checkout.mkdir(exist_ok=True)
    (checkout / "pyproject.toml").write_text('[project]\nname = "widget"\n')
    return _SCRIPT.format(root=str(ROOT), repo=REPO, sha=SHA, checkout=str(checkout),
                          cache=str(tmp_path / "shared-cache"), start=start, delay=delay)


def _out(proc_stdout: str) -> dict:
    return json.loads(proc_stdout.strip().splitlines()[-1])


def test_crawl_cache_is_reused_by_a_later_process(tmp_path):
    script = _script(tmp_path)
    runs = [_out(subprocess.run([sys.executable, "-c", script], capture_output=True, text=True,
                                check=True).stdout) for _ in range(2)]
    assert runs[0] == {"crawls": 1, "hit": False}
    assert runs[1] == {"crawls": 0, "hit": True}


def test_two_processes_started_together_crawl_exactly_once(tmp_path):
    start = tmp_path / "go"
    script = _script(tmp_path, start=str(start), delay=0.5)
    procs = [subprocess.Popen([sys.executable, "-c", script], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              text=True) for _ in range(2)]
    start.write_text("go")   # release both at the same moment
    outs = [_out(p.communicate(timeout=60)[0]) for p in procs]
    assert sum(o["crawls"] for o in outs) == 1
    assert sorted(o["hit"] for o in outs) == [False, True]
    assert not list((tmp_path / "shared-cache").glob("*.tmp"))


def test_threads_of_one_check_add_to_its_meter():
    import threading
    m = tavily_budget.begin("one check")
    threads = [threading.Thread(target=tavily_budget.record, args=("search",)) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    got = tavily_budget.take(m)
    assert got["search_calls"] == 8 and not got["overlapped"]


def test_a_second_check_before_the_first_is_taken_marks_both_overlapped():
    first = tavily_budget.begin("a")
    second = tavily_budget.begin("b")
    assert tavily_budget.take(first)["overlapped"] and tavily_budget.take(second)["overlapped"]


def test_cap_without_a_key_refuses_before_reading_usage(monkeypatch):
    monkeypatch.setattr(tavily_budget, "fetch_usage", lambda *a, **k: pytest.fail("usage read without a key"))
    line = tavily_budget.refusal(env={tavily_budget.CAP_ENV: "900"})
    assert line.startswith(tavily_budget.LIMIT_REACHED) and "TAVILY_API_KEY is not set" in line


def test_formula_matches_the_published_examples():
    # docs.tavily.com/documentation/api-credits: 10 pages basic = 1 + 2 = 3; advanced = 1 + 4 = 5
    assert tavily_budget.crawl_credits(10, instructions=False) == 3
    assert tavily_budget.crawl_credits(10, instructions=False, depth="advanced") == 5
    assert tavily_budget.crawl_credits(10, instructions=True) == 4
    assert tavily_budget.extract_credits(12) == 3 and tavily_budget.extract_credits(12, "advanced") == 6


def test_worst_case_is_priced_from_the_bodies_the_code_really_sends(monkeypatch):
    from poc import demo_helper
    sent = []
    monkeypatch.setattr(tavily_crawl, "_post", lambda api, body, env, timeout: sent.append((api, body)) or {})
    for s in tavily_crawl.seeds(REPO, SHA, "docs.example.org"):
        tavily_crawl.crawl(s["url"], select_domains=s["select_domains"], select_paths=s["select_paths"], env={})
    tavily_crawl.extract([f"https://x/{i}" for i in range(tavily_crawl.EXTRACT_MAX)], env={})
    real = sum(tavily_budget.request_credits(api, body) for api, body in sent)
    assert all(b["instructions"] and b["extract_depth"] == "basic" and b["limit"] == tavily_crawl.CRAWL_LIMIT
               for api, b in sent if api == tavily_crawl.CRAWL_API)
    assert tavily_budget.SETUP_SEARCHES == len(demo_helper.lookup_queries("acme/widget", "widget"))
    assert tavily_budget.GAP_SEARCHES == demo_helper.MAX_GAP_TRIES + 1   # one per repair try plus the batch gate
    searches = tavily_budget.SETUP_SEARCHES + tavily_budget.GAP_SEARCHES + tavily_budget.RELATED_SEARCHES
    assert tavily_budget.WORST_CASE_CHECK == tavily_budget.worst_case() == searches + real
    # 40 pages with instructions: map 4 x 2 = 8, extract 8 x 1 = 8, so 16 per seed; 2 seeds; extract 12 = 3
    assert real == 2 * 16 + 3 and tavily_budget.WORST_CASE_CHECK == 43


def test_capped_check_end_to_end_refuses_with_no_tavily_call(tmp_path, monkeypatch):
    from ops import daily_run as _dr
    monkeypatch.setattr(_dr, "live_pr_refusal", lambda *a, **k: None)   # an open pull request
    from types import SimpleNamespace

    from ops import daily_run
    from poc import demo_helper
    monkeypatch.setenv("TAVILY_API_KEY", "tvly-e2e-not-real")
    monkeypatch.setenv(tavily_budget.CAP_ENV, "620")
    monkeypatch.setattr(tavily_budget, "fetch_usage", lambda *a, **k: _usage(613))
    tavily_calls = []
    monkeypatch.setattr(tavily_docs.urllib.request, "urlopen", lambda *a, **k: tavily_calls.append(a))
    monkeypatch.setattr(demo_helper, "live_fetch", lambda *a, **k: tavily_calls.append(a))
    monkeypatch.setattr(tavily_crawl, "_post", lambda *a, **k: tavily_calls.append(a))
    a = SimpleNamespace(bench=None, pr=["https://github.com/acme/widgets/pull/4"], product_check=True,
                        provider=None, runs=1, workers=1, test_timeout=30, run_timeout=30, build_timeout=30,
                        python="python3", model_provider="none", baseline="full", poc_commit="a" * 40)
    item = {"pr": 4, "diff": "", "head_sha": "a" * 40, "url": "https://github.com/acme/widgets/pull/4",
            "title": "t", "body": "", "base_sha": "b" * 40, "author": "dev", "base_ref": "main",
            "updated_at_utc": "2026-10-27T00:00:00Z", "updated_at_ist": "2026-10-27 05:30 IST",
            "ci_state": "unknown", "ci_detail": "",
            "files": {"all": ["pkg/__init__.py"], "package_py": ["pkg/__init__.py"], "compiled": [], "other": []}}
    rec = daily_run.test_pr("acme/widgets", {"pkg": "widgets", "dist": "widgets"}, item,
                            tmp_path / "run", tmp_path / "work", a, {})
    assert rec["verdict"] == "could_not_verify"
    assert rec["tavily_credit_refusal"].startswith(tavily_budget.LIMIT_REACHED)
    assert tavily_calls == []
    saved = json.loads((tmp_path / "run" / "widgets-4" / "record.json").read_text())
    assert saved["tavily_credits"]["total_credits"] == 0 and "_tavily_meter" not in saved
    assert "tvly-e2e-not-real" not in json.dumps(saved)


def test_api_usage_block_is_the_source_per_call():
    from poc import tavily_budget as tb
    m = tb.begin("o/r#1")
    tb.record("search", payload={"usage": {"credits": 2}})          # e.g. auto-upgraded to advanced
    tb.record("search")                                             # no usage block: estimated at basic rate
    tb.record("crawl", payload={"usage": {"credits": 3}})
    t = tb.take(m)
    assert t["total_credits"] == 6 and t["api_reported_credits"] == 5 and t["estimated_credits"] == 1
    assert [c["source"] for c in t["calls"]] == ["api", "estimate", "api"]
    assert t["calls"][0]["usage"] == {"credits": 2}
    assert "API-reported 5, estimated 1" in tb.log_line(t)


def test_take_active_returns_a_crashed_checks_meter():
    from poc import tavily_budget as tb
    tb.begin("o/r#2")
    tb.record("search", payload={"usage": {"credits": 1}})
    t = tb.take_active()
    assert t["total_credits"] == 1 and tb.take_active() is None


def test_search_asks_for_usage(monkeypatch):
    import io
    import json
    import urllib.request

    from poc import tavily_budget as tb
    from poc import tavily_docs
    sent = {}

    def fake(req, timeout=None):
        sent.update(json.loads(req.data))
        return io.BytesIO(json.dumps({"results": [], "usage": {"credits": 1}}).encode())
    monkeypatch.setattr(urllib.request, "urlopen", fake)
    m = tb.begin("o/r#3")
    tavily_docs.lookup("q", env={"TAVILY_API_KEY": "k"})
    t = tb.take(m)
    assert sent["include_usage"] is True and t["calls"][0]["source"] == "api"
