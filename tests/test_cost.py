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


def test_cost_report_counts_attempts_matched_set_and_flags_missing_raw(tmp_path, monkeypatch):
    from ops import cost_report
    monkeypatch.setenv("POC_MACHINE_USD_PER_HOUR", "3.6")      # $0.001 per second
    rd = tmp_path / "run"
    (rd / "full" / "raw").mkdir(parents=True)
    (rd / "tests").mkdir()
    (rd / "score").mkdir()
    pg = rd / "pg"
    (pg / "logs" / "B01" / "patchguru" / "raw").mkdir(parents=True)
    rec = lambda v, wall: json.dumps({"verdict": v, "tested_at_ist": "2026-10-13 10:00 IST",  # noqa: E731
                                      "duration_s": {"total_wall": wall}})
    (rd / "full" / "B01-full.json").write_text(rec("verified", 100))
    (rd / "full" / "B02-full.json").write_text(rec("could_not_verify", 100))
    (rd / "tests" / "B01-tests.json").write_text(rec("verified", 100))
    (rd / "score" / "B01-full.json").write_text(rec("verified", 100))   # copy: skipped
    (rd / "full" / "raw" / "100030-claims-1.json").write_text(json.dumps({"server_model": SUPER, "usage": U}))
    (pg / "B01-patchguru_post_review.json").write_text(json.dumps({"verdict": "could_not_verify", "elapsed_s": 50}))
    (pg / "logs" / "B01" / "patchguru" / "raw" / "001-chat.json").write_text(
        json.dumps({"request": {"model": SUPER}, "response": {"model": SUPER, "usage": U}}))
    t = cost_report.collect([rd])
    assert len(t["ours"]["records"]) == 3 and t["ours"]["tests_only"] and not t["ours"]["untied"]
    md = cost_report.render(t, [rd])
    assert "PILOT" in md and "some data missing" in md and "Matched comparison" in md and "All runs" in md
    assert "Cases both tools attempted: B01." in md
    # all runs, ours: AI $1.20 + computer 300 s x $0.001 = $1.50 over 3 attempted / 2 final (rate 67%)
    assert "$0.5000" in md and "$0.7500" in md and "67%" in md
    # PatchGuru: no final verdict -> per-final is n/a, rate 0%
    assert "0%" in md and "n/a" in md


def test_record_cost_block_has_ai_computer_and_total(monkeypatch):
    monkeypatch.delenv("POC_MACHINE_USD_PER_HOUR", raising=False)
    cost.reset()
    cost.record_call(SUPER, U)
    s = cost.take({"total_wall": 3600})
    assert s["ai_cost_usd"] == 1.2 and s["computer_cost_usd"] == 0.24 and s["total_cost_usd"] == 1.44
    assert "docs.nebius.com/compute/resources/pricing" in s["machine_rate_source"]


def test_per_pr_reports_verdict_rate_and_total():
    p = cost.per_pr([{"verdict": "verified", "cost_usd": 1, "computer_cost_usd": 1},
                     {"verdict": "could_not_verify", "cost_usd": 1, "computer_cost_usd": 1}])
    assert p["verdict_rate"] == 0.5 and p["total_per_attempted"] == 2 and p["total_per_final"] == 4
