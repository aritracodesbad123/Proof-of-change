"""Cost logging: tokens, price, call counts, and the two per-PR numbers."""
import json

from poc import cost

SUPER = "nvidia/nemotron-3-super-120b-a12b"
U = {"prompt_tokens": 1_000_000, "completion_tokens": 1_000_000,
     "completion_tokens_details": {"reasoning_tokens": 600_000}}


def test_price_uses_the_listed_rates_and_counts_thinking_as_output():
    assert cost.tokens(U) == (1_000_000, 1_000_000, 600_000)
    assert abs(cost.price(SUPER, U) - 1.20) < 1e-9
    assert cost.price("unknown/model", U) is None and cost.price(SUPER, None) is None


def test_ledger_counts_every_call_including_failures_and_resets():
    cost.reset()
    cost.record_call(SUPER, U)
    cost.record_call(SUPER, None, ok=False)          # timed out: counted as a call, no tokens known
    s = cost.take({"build": 10.0, "tests": 5.0})
    assert s["ai_calls"] == 2 and s["failed_ai_calls"] == 1 and s["calls_without_usage"] == 1
    assert s["cost_complete"] is False and abs(s["cost_usd"] - 1.2) < 1e-9
    assert s["compute_seconds"] == {"build": 10.0, "tests": 5.0} and "nebius.com" in s["rate_source"]
    assert cost.take()["ai_calls"] == 0


def test_per_pr_counts_could_not_verify_in_spend_but_not_as_final():
    recs = [{"verdict": "verified", "cost_usd": 0.02}, {"verdict": "needs_attention", "cost_usd": 0.02},
            {"verdict": "could_not_verify", "cost_usd": 0.02}]
    p = cost.per_pr(recs)
    assert p["attempted"] == 3 and p["with_final_verdict"] == 2
    assert abs(p["per_pr_attempted_usd"] - 0.02) < 1e-9 and abs(p["per_pr_with_final_verdict_usd"] - 0.03) < 1e-9
    assert cost.per_pr([{"verdict": "could_not_verify", "cost_usd": 0.01}])["per_pr_with_final_verdict_usd"] is None


def test_nebius_provider_logs_cost_even_when_the_answer_is_empty(monkeypatch):
    from poc import model_provider as mp

    class R:
        def __init__(self, d): self.d = d
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self): return json.dumps(self.d).encode()

    reply = {"model": SUPER, "usage": U, "choices": [{"finish_reason": "length", "message": {"content": None}}]}
    monkeypatch.setattr(mp.urllib.request, "urlopen", lambda req, timeout=None: R(reply))
    monkeypatch.delenv("POC_RAW_DIR", raising=False)
    cost.reset()
    p = mp.NebiusProvider("k", models={"claims": SUPER})
    try:
        p.complete_json("claims", "s", "u", {}, {})
    except mp.ProviderError:
        pass
    s = cost.take()
    assert s["ai_calls"] == 1 and s["failed_ai_calls"] == 1 and s["output_tokens"] == 1_000_000


def test_patchguru_chat_logs_each_call(tmp_path):
    from evals.patchguru_runner import NebiusChat
    reply = {"model": SUPER, "usage": U, "choices": [{"message": {"content": "ok"}}]}
    chat = NebiusChat(None, SUPER, tmp_path, "k", transport=lambda body: reply)
    cost.reset()
    chat._call("chat", "", "hi", {}, {})
    chat._call("chat", "", "again", {}, {})
    assert cost.take()["ai_calls"] == 2


def test_cost_report_counts_attempts_and_flags_missing_raw(tmp_path):
    from ops import cost_report
    rd = tmp_path / "run"
    (rd / "full" / "raw").mkdir(parents=True)
    (rd / "tests").mkdir()
    (rd / "score").mkdir()
    (rd / "full" / "B01-full.json").write_text(json.dumps({"verdict": "verified", "duration_s": {"total_wall": 60}}))
    (rd / "full" / "B02-full.json").write_text(json.dumps({"verdict": "could_not_verify"}))
    (rd / "tests" / "B01-tests.json").write_text(json.dumps({"verdict": "verified"}))
    (rd / "score" / "B01-full.json").write_text(json.dumps({"verdict": "verified"}))   # copy: skipped
    (rd / "full" / "raw" / "1-claims.json").write_text(json.dumps({"server_model": SUPER, "usage": U}))
    t = cost_report.collect([rd])
    assert len(t["ours"]["records"]) == 3 and len(t["ours"]["calls"]) == 1 and t["ours"]["tests_only"]
    md = cost_report.render(t, [rd])
    assert "$0.4000" in md and "$0.6000" in md   # $1.20 / 3 attempted, / 2 with a final verdict
