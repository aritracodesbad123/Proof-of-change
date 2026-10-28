"""A probe whose code does not parse is sent back with its exact parse error, a fixed number of times, and every
attempt is recorded. Built on the rich #4147 failure: "unexpected character after line continuation character"."""
from poc import model_probes
from tests.test_probe_min_one import GOOD, _run

# The rich #4147 probe text was not saved by that run; this reproduces the same error: one line with literal
# backslash-n sequences that still does not parse once they are turned into line breaks.
BROKEN_CODE = "x = 1\\nif x:\\nprint(x)"
BROKEN = {"probes": [dict(GOOD["probes"][0], id="p1", code=BROKEN_CODE)]}


def test_parse_error_reproduces_the_rich_4147_message():
    e = model_probes.parse_error(BROKEN_CODE)
    assert e["message"] == "unexpected character after line continuation character" and e["line"] == 1
    assert e["code_line"] == BROKEN_CODE
    assert model_probes.parse_error(GOOD["probes"][0]["code"]) is None


def test_repair_feeds_the_exact_error_and_keeps_the_fix(tmp_path):
    fixed = {"probes": [dict(GOOD["probes"][0], id="p1")]}
    prov, out = _run(tmp_path, [BROKEN, fixed])
    ask = prov.prompts[2][1]
    assert "unexpected character after line continuation character (line 1" in ask
    assert "Offending line: " + BROKEN_CODE in ask and "Full code as received" in ask
    assert out["parse_repairs"] == [{"attempt": 1, "probe": "p1", "outcome": "fixed",
                                     "error": model_probes.parse_error(BROKEN_CODE)}]
    assert len(out["probes"]) == 1 and "retried" not in out


def test_repair_is_capped_and_every_attempt_recorded(tmp_path):
    answers = [BROKEN] * (model_probes.PARSE_REPAIR_TRIES + 1) + [BROKEN]
    prov, out = _run(tmp_path, answers)
    reps = out["parse_repairs"]
    assert [r["attempt"] for r in reps] == list(range(1, model_probes.PARSE_REPAIR_TRIES + 1))
    assert all(r["outcome"].startswith("still fails: unexpected character") for r in reps)
    # claims + first probes + the capped repairs + the usual one "no usable probe" retry, and no more
    assert len(prov.prompts) == 2 + model_probes.PARSE_REPAIR_TRIES + 1


def test_no_repair_when_code_parses(tmp_path):
    prov, out = _run(tmp_path, [GOOD])
    assert len(prov.prompts) == 2 and "parse_repairs" not in out
