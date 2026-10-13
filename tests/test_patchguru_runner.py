"""PatchGuru comparison runner (evals/patchguru_runner.py): eligibility, firewall + raw saving, verdict mapping."""
import json

import pytest

from evals import patchguru_runner as pg
from poc.leakage import Fingerprints, LeakageError
from poc.model_gate import Gate

BEFORE = "import os\n\n\ndef f(x):\n    return x + 1\n\n\ndef g(y):\n    return y\n"


def test_single_function_change_is_eligible():
    after = BEFORE.replace("x + 1", "x + 2")
    r = pg.changed_functions({"pkg/m.py": BEFORE, "tests/test_m.py": "x=1"}, {"pkg/m.py": after,
                                                                            "tests/test_m.py": "x=2"})
    assert r["eligible"] and r["functions"] == [("pkg/m.py", "f")]


def test_docstring_only_module_change_still_eligible():
    after = '"""Doc."""\n' + BEFORE.replace("x + 1", "x + 2")
    assert pg.changed_functions({"m.py": BEFORE}, {"m.py": after})["eligible"]


@pytest.mark.parametrize("after,why", [
    (BEFORE.replace("x + 1", "x + 2").replace("return y", "return -y"), "2 functions change"),
    (BEFORE.replace("import os", "import sys"), "outside functions"),
    (BEFORE + "\n\ndef h():\n    pass\n", "is added"),
])
def test_ineligible(after, why):
    r = pg.changed_functions({"m.py": BEFORE}, {"m.py": after})
    assert not r["eligible"] and why in r["why"]


def test_method_names_are_qualified():
    b = "class A:\n    def m(self):\n        return 1\n"
    r = pg.changed_functions({"m.py": b}, {"m.py": b.replace("1", "2")})
    assert r["functions"] == [("m.py", "A.m")]


def fake_server(model="nvidia/nemotron-x"):
    def t(body):
        return {"model": model, "choices": [{"message": {"content": "ok"}}], "usage": {"total_tokens": 3}}
    return t


def test_every_call_is_gated_and_saved_raw(tmp_path):
    chat = pg.NebiusChat(Gate.no_answer_key(pr="o/r#1"), "m", tmp_path / "raw", "k", transport=fake_server())
    pg.install_query_llm(chat)
    import sys
    assert sys.modules["patchguru.llms.OpenAI"].query_llm("write a spec") == "ok"
    s = chat.summary()
    assert s["blind"] and s["firewall_all_passed"] and s["server_models"] == ["nvidia/nemotron-x"]
    raw = json.loads((tmp_path / "raw" / "001-patchguru.json").read_text())
    assert raw["response"]["model"] == "nvidia/nemotron-x" and raw["prompt"] == "write a spec"


def test_missing_server_model_makes_run_a_pilot(tmp_path):
    chat = pg.NebiusChat(Gate.no_answer_key(), "m", tmp_path, "k", transport=fake_server(model=None))
    chat.complete_json("patchguru", "", "hi", {}, {})
    assert chat.summary()["blind"] is False


def test_leaking_prompt_never_reaches_the_server(tmp_path):
    sent = []
    fp = Fingerprints(urls={pg_hash("https://github.com/o/r/issues/99")}, source="t")
    chat = pg.NebiusChat(Gate(fp, pr="o/r#1"), "m", tmp_path, "k", transport=lambda b: sent.append(b))
    with pytest.raises(LeakageError):
        chat.complete_json("patchguru", "", "see https://github.com/o/r/issues/99", {}, {})
    assert not sent and chat.summary()["blind"] is False


def pg_hash(u):
    from poc.leakage import _h, norm_url
    return _h(norm_url(u))


@pytest.mark.parametrize("states,pre,post", [
    ({"intent_analysis": True, "stage": "completed", "review_conclusion": "NORMAL",
      "execution_status": [{"exit_code": 0}]}, "verified", "verified"),
    ({"intent_analysis": True, "stage": "completed", "review_conclusion": "BUG",
      "execution_status": [{"exit_code": 1, "error_message": "AssertionError"}]}, "needs_attention", "needs_attention"),
    ({"intent_analysis": True, "stage": "completed", "review_conclusion": "NORMAL", "review_traces": [{}],
      "execution_status": [{"exit_code": 1, "error_message": "AssertionError"}, {"exit_code": 0}]},
     "needs_attention", "verified"),
    ({"intent_analysis": True, "stage": "completed", "review_conclusion": "NORMAL",
      "execution_status": [{"exit_code": 1, "error_message": "AssertionError in pre_f"}, {"exit_code": 0}]},
     "verified", "verified"),
    ({"intent_analysis": True, "stage": "failed", "execution_status": [{"exit_code": 1, "error_message": "TypeError"}]},
     "could_not_verify", "could_not_verify"),
    ({"intent_analysis": False}, "could_not_verify", "could_not_verify"),
])
def test_verdicts_before_and_after_self_review(states, pre, post):
    v = pg.verdicts(states)
    assert (v["pre"][0], v["post"][0]) == (pre, post)
