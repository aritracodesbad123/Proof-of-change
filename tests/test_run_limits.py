"""Live-run guards: --require-boundary-rule, --max-provider-calls, --max-cost-usd, and no Contree retry under
--require-contree. All offline: the provider's HTTP call and Contree are replaced."""
import io
import json
from types import SimpleNamespace

import pytest

from ops import daily_run
from poc import contree_sandboxes as cs
from poc import cost, model_provider, run_limits

MODEL = "nvidia/nemotron-3-super-120b-a12b"


@pytest.fixture(autouse=True)
def _clean():
    run_limits.reset()
    cost.reset()
    yield
    run_limits.reset()
    cost.reset()


def _fake_http(monkeypatch, usage=None):
    sent = []
    usage = {"prompt_tokens": 1000, "completion_tokens": 1000} if usage is None else usage

    class R(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def urlopen(req, timeout=None):
        sent.append(req)
        body = {"model": MODEL, "usage": usage,
                "choices": [{"message": {"content": json.dumps({"ok": 1})}, "finish_reason": "stop"}]}
        return R(json.dumps(body).encode())
    monkeypatch.setattr(model_provider.urllib.request, "urlopen", urlopen)
    return sent


def _provider():
    return model_provider.NebiusProvider("not-a-real-key", models={"claims": MODEL, "probes": MODEL})


def test_fifth_provider_call_is_refused_before_it_is_sent(monkeypatch):
    sent = _fake_http(monkeypatch)
    run_limits.configure(max_calls=4)
    p = _provider()
    for _ in range(4):
        p.complete_json("probes", "s", "u", {}, {})
    with pytest.raises(run_limits.RunLimitStop) as e:
        p.complete_json("probes", "s", "u", {}, {})
    assert len(sent) == 4
    assert "provider call 5" in str(e.value.code) and "not-a-real-key" not in str(e.value.code)
    assert isinstance(e.value, SystemExit)


def test_no_call_limit_by_default(monkeypatch):
    sent = _fake_http(monkeypatch)
    p = _provider()
    for _ in range(6):
        p.complete_json("probes", "s", "u", {}, {})
    assert len(sent) == 6


def test_call_that_could_pass_the_cost_cap_is_refused_before_it_is_sent(monkeypatch):
    sent = _fake_http(monkeypatch)
    monkeypatch.setenv("POC_MAX_TOKENS", "32000")   # worst case per call: 32000 * $0.90 / 1M = $0.0288 + input
    run_limits.configure(max_cost_usd=0.10)
    p = _provider()
    p.complete_json("claims", "s", "u", {}, {})   # real price: $0.0012
    assert run_limits.spent_usd() == pytest.approx(0.0012)
    big = "x" * 200_000   # 100k tokens of input at worst: $0.03, plus $0.0288 output
    p.complete_json("probes", "s", big, {}, {})
    p.complete_json("probes", "s", big, {}, {})
    with pytest.raises(run_limits.RunLimitStop) as e:
        p.complete_json("probes", "s", big * 3, {}, {})   # $0.0036 spent + up to $0.1188 > $0.10
    assert len(sent) == 3 and "--max-cost-usd 0.10" in str(e.value.code)


def test_call_without_usage_counts_at_its_worst_case(monkeypatch):
    _fake_http(monkeypatch, usage={})
    monkeypatch.setenv("POC_MAX_TOKENS", "32000")
    run_limits.configure(max_cost_usd=0.10)
    p = _provider()
    for _ in range(3):
        p.complete_json("probes", "s", "u", {}, {})
    with pytest.raises(run_limits.RunLimitStop):
        p.complete_json("probes", "s", "u", {}, {})   # 4 * 0.0288 > 0.10


def test_cli_flags_reach_the_limits(monkeypatch):
    seen = {}
    monkeypatch.setattr(run_limits, "configure", lambda n, usd: seen.update(n=n, usd=usd))
    from poc import hitl
    monkeypatch.setattr(hitl, "study_operator_approval_stop", lambda **k: "stop here")
    with pytest.raises(SystemExit):
        daily_run._main(["--max-provider-calls", "4", "--max-cost-usd", "0.10", "--model-provider", "none",
                         "--pr", "https://github.com/o/r/pull/1"])
    assert seen == {"n": 4, "usd": 0.10}


@pytest.mark.parametrize("found,ok", [
    ([{"file": "rich/highlighter.py", "line": 85, "old": "x"}], True),
    ([{"file": "rich/highlighter.py", "line": 86, "old": "x"}], False),
    ([{"file": "rich/other.py", "line": 85, "old": "x"}], False),
    ([{"file": "rich/highlighter.py", "line": 85}, {"file": "rich/highlighter.py", "line": 90}], False),
    ([], False),
    (None, False),
])
def test_boundary_rule_must_match_exactly(found, ok):
    stop = run_limits.boundary_rule_stop("rich/highlighter.py:85", found)
    assert (stop is None) is ok
    assert run_limits.boundary_rule_stop(None, found) is None


def test_plan_probes_stops_after_the_plan_is_written(tmp_path, monkeypatch):
    found = [{"file": "rich/highlighter.py", "line": 90, "old": "x"}]
    monkeypatch.setattr(daily_run.model_probes, "generate", lambda *a, **k: {"probes": [], "claims": [],
                                                                              "boundary_rule": found})
    a = SimpleNamespace(baseline="tests+probes", no_probes=False, provider=object(), model_note=None,
                        require_boundary_rule="rich/highlighter.py:85", product_check=True, bench=None)
    item = {"pr": 4147, "title": "t", "body": "", "files": {"all": []}, "diff": ""}
    rec = {}
    monkeypatch.setattr(daily_run.probes, "find_probes", lambda *a: [])
    with pytest.raises(run_limits.RunLimitStop) as e:
        daily_run.plan_probes("o/r", item, rec, tmp_path, [tmp_path], tmp_path, a)
    assert rec["probe_plan"]["model_boundary_rule"] == found   # the plan is on the record
    assert "rich/highlighter.py:90" in str(e.value.code)
    a.require_boundary_rule = "rich/highlighter.py:90"
    daily_run.plan_probes("o/r", item, {}, tmp_path, [tmp_path], tmp_path, a)   # a match goes on


def test_boundary_rule_turns_parallel_prep_off(monkeypatch):
    monkeypatch.setenv("POC_PARALLEL", "1")
    a = SimpleNamespace(product_check=True, bench=None, pr=["u"], require_boundary_rule=None)
    assert daily_run.parallel_on(a) is True
    a.require_boundary_rule = "rich/highlighter.py:85"
    assert daily_run.parallel_on(a) is False


def _prep_seen(monkeypatch, **flags):
    seen = {}

    def prep(*args, **kw):
        seen.update(kw)
        raise cs.ContreeError("contree request failed: ApiTimeoutError")
    monkeypatch.setattr(cs, "prepare_source_pair", prep)
    monkeypatch.setattr(daily_run, "run", lambda *a, **k: pytest.fail("ran locally"))
    a = SimpleNamespace(**({"sandbox_backend": "contree", "product_check": True, "pr": 1, "bench": None} | flags))
    why = daily_run._maybe_prepare_contree(a, "o/r", "a" * 40, "b" * 40, {"files": {"all": []}}, 60)
    assert why and "ApiTimeoutError" in why
    return seen


def test_no_contree_retry_flag_turns_the_retry_off(monkeypatch):
    seen = _prep_seen(monkeypatch, require_contree=True, no_contree_retry=True)
    assert seen.get("retry_transient") is False


def test_hosted_require_contree_keeps_its_retries(monkeypatch):
    seen = _prep_seen(monkeypatch, require_contree=True)
    assert seen.get("retry_transient") is True
    a = daily_run_args(["--pr", "https://github.com/o/r/pull/1", "--product-check", "--require-contree",
                        "--live-check"])
    assert a.no_contree_retry is False
    assert _prep_seen(monkeypatch, **vars(a) | {"sandbox_backend": "contree"}).get("retry_transient") is True


def daily_run_args(argv):
    """The arguments _main parses, without starting a run."""
    import argparse
    got, orig = {}, argparse.ArgumentParser.parse_args

    def parse(self, args=None, namespace=None):
        got["a"] = orig(self, args, namespace)
        raise SystemExit("captured")
    with pytest.MonkeyPatch.context() as m:
        m.setattr(argparse.ArgumentParser, "parse_args", parse)
        with pytest.raises(SystemExit):
            daily_run._main(argv)
    return got["a"]


def test_configure_starts_a_fresh_count(monkeypatch):
    _fake_http(monkeypatch, usage={})
    monkeypatch.setenv("POC_MAX_TOKENS", "32000")
    run_limits.configure(max_calls=4, max_cost_usd=0.10)
    p = _provider()
    for _ in range(3):
        p.complete_json("probes", "s", "u", {}, {})
    run_limits.configure(max_calls=4, max_cost_usd=0.10)   # a second run in the same process
    assert run_limits.spent_usd() == 0
    for _ in range(3):
        p.complete_json("probes", "s", "u", {}, {})


def test_provider_stop_writes_a_could_not_verify_record(monkeypatch, tmp_path):
    _fake_http(monkeypatch)
    run_limits.configure(max_calls=0)
    rec = {"repo": "o/r", "probe_plan": {"model_boundary_rule": []}}
    run_limits.watch_record(rec, tmp_path / "r-1")
    with pytest.raises(run_limits.RunLimitStop) as e:
        _provider().complete_json("claims", "s", "u", {}, {})
    on_disk = json.loads((tmp_path / "r-1" / "record.json").read_text())
    assert on_disk["verdict"] == "could_not_verify" and on_disk["reason"] == e.value.code
    assert on_disk["run_limit_stop"] == e.value.code and "probe_plan" in on_disk


def test_boundary_stop_writes_the_probe_plan_to_disk(tmp_path, monkeypatch):
    found = [{"file": "rich/highlighter.py", "line": 90, "old": "x"}]
    monkeypatch.setattr(daily_run.model_probes, "generate", lambda *a, **k: {"probes": [], "claims": [],
                                                                              "boundary_rule": found})
    monkeypatch.setattr(daily_run.probes, "find_probes", lambda *a: [])
    a = SimpleNamespace(baseline="tests+probes", no_probes=False, provider=object(), model_note=None,
                        require_boundary_rule="rich/highlighter.py:85", product_check=True, bench=None)
    item = {"pr": 4147, "title": "t", "body": "", "files": {"all": []}, "diff": ""}
    rec = {"repo": "o/r"}
    run_limits.watch_record(rec, tmp_path / "rich-4147")
    with pytest.raises(run_limits.RunLimitStop):
        daily_run.plan_probes("o/r", item, rec, tmp_path, [tmp_path], tmp_path, a)
    on_disk = json.loads((tmp_path / "rich-4147" / "record.json").read_text())
    assert on_disk["verdict"] == "could_not_verify"
    assert on_disk["probe_plan"]["model_boundary_rule"] == found
    assert "rich/highlighter.py:90" in on_disk["run_limit_stop"]


def test_test_pr_watches_its_record():
    import inspect
    src = inspect.getsource(daily_run.test_pr)
    assert "run_limits.watch_record(rec, prdir)" in src
