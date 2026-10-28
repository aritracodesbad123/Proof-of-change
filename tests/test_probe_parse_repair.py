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
                                     "error": model_probes.parse_error(BROKEN_CODE),
                                     "counts": {"before": {"keys": 0, "inputs": 0, "read": "tokens"},
                                                "after": {"keys": 1, "inputs": 0, "read": "ast"}}}]
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


def test_repair_and_retry_trail_lands_in_the_saved_record(tmp_path, monkeypatch):
    """daily_run end to end with fakes: plan_probes calls the real generate with a scripted provider, then finish
    writes record.json. The three trail fields must be in the saved probe_plan."""
    import json
    import time
    from types import SimpleNamespace

    from ops import daily_run as dr
    from tests.test_cover_names_in_code import BAD
    from tests.test_probe_min_one import BODY, TITLE, Scripted

    monkeypatch.delenv("POC_SWARM", raising=False)
    monkeypatch.delenv("POC_HITL", raising=False)
    base = tmp_path / "base"
    (base / "pkg").mkdir(parents=True)
    (base / "pkg" / "m.py").write_text("def f(x):\n    return x\n")
    prdir, work = tmp_path / "pr", tmp_path / "work"
    prdir.mkdir()
    work.mkdir()
    bad_p1 = {"probes": [dict(BAD["probes"][0], id="p1")]}
    # broken code, then a repair that parses but names an unrecorded cover, then a cover retry that is no better
    prov = Scripted([BROKEN, bad_p1, bad_p1])
    a = SimpleNamespace(provider=prov, model_note="scripted")
    item = {"pr": 1, "title": TITLE, "body": BODY, "files": {"all": ["pkg/m.py"]}, "diff": ""}
    rec = {"files": {"package_py": ["pkg/m.py"], "compiled": [], "other": []}, "per_run": []}
    monkeypatch.setattr(dr.probes, "find_probes", lambda *x: [])
    dr.plan_probes("o/r", item, rec, base, [tmp_path / "prside"], prdir, a)
    dr.finish(rec, prdir, work, time.time())
    plan = json.loads((prdir / "record.json").read_text())["probe_plan"]
    assert plan["model_parse_repairs"] == [{"attempt": 1, "probe": "p1", "outcome": "fixed",
                                            "error": model_probes.parse_error(BROKEN_CODE),
                                     "counts": {"before": {"keys": 0, "inputs": 0, "read": "tokens"},
                                                "after": {"keys": 1, "inputs": 0, "read": "ast"}}}]
    assert plan["model_retried"]["kept_first_answer"]
    # the repair's code is kept with the original's covers (f.*), which that code does not record
    assert plan["model_unmatched_covers"] == ["C1:f.*"]


THREE = ("import json\nobs = {}\nfor i, x in enumerate([1, 'b', (3, 4)]):\n    obs['f.a'] = 1\n"
         "    obs['f.b'] = 2\n    obs['f.c'] = 3\nprint(json.dumps({'observations': obs}))\n")
ONE = "import json\nobs = {}\nfor x in [1]:\n    obs['f.a'] = 1\nprint(json.dumps({'observations': obs}))\n"


def test_text_counts_read_a_broken_original():
    broken = THREE.replace("obs = {}", "obs = {}\\n)")
    assert model_probes.parse_error(broken) is not None
    assert model_probes._token_obs_keys(broken) == 3 and model_probes._text_inputs(broken) == 3
    assert model_probes._token_obs_keys(ONE) == 1 and model_probes._text_inputs(ONE) == 1


def test_repair_that_drops_observations_is_rejected(tmp_path):
    broken = dict(GOOD["probes"][0], id="p1", code=THREE + "if x:\nprint(x)\n")
    assert model_probes.parse_error(broken["code"]) is not None
    drop = {"probes": [dict(GOOD["probes"][0], id="p1", code=ONE)]}
    prov, out = _run(tmp_path, [{"probes": [broken]}] + [drop] * model_probes.PARSE_REPAIR_TRIES + [{"probes": []}])
    reps = out["parse_repairs"]
    assert len(reps) == model_probes.PARSE_REPAIR_TRIES
    assert all(r["outcome"] == "rejected: the repair has fewer observation keys (1 < 3)" for r in reps)
    assert not any(p.get("code") == ONE for p in out["probes"])


def test_repair_takes_only_code_and_pairs_by_id(tmp_path):
    orig = dict(GOOD["probes"][0], id="p1", about="orig", code=BROKEN_CODE)
    other_id = {"probes": [dict(GOOD["probes"][0], id="p9")]}
    _, out = _run(tmp_path, [{"probes": [orig]}, other_id, other_id, {"probes": []}])
    assert all(r["outcome"] == "no fixed probe returned" for r in out["parse_repairs"])
    reply = dict(GOOD["probes"][0], id="p1", about="changed", claims=[{"id": "C1", "covers": ["zz.*"],
                                                                      "expect": "same"}])
    resp = model_probes._repair_parse_errors(type("P", (), {"complete_json": lambda *a: {"probes": [reply]}})(),
                                             "", "u", {}, {"probes": [orig]}, {})
    got = resp["probes"][0]
    assert got["code"] == reply["code"] and got["about"] == "orig" and got["claims"] == orig["claims"]


# Each way the text count of a repair could be fooled; the repair parses, so it is read from its AST.
def _keys(code):
    c = model_probes.repair_counts(code)
    assert c["read"] == "ast"
    return c["keys"], c["inputs"]


def test_ast_ignores_keys_in_comments():
    assert _keys("obs = {}\n# obs['f.b'] = 2  obs['f.c'] = 3\nobs['f.a'] = 1\n") == (1, 0)


def test_ast_ignores_keys_in_docstrings_and_plain_strings():
    code = '"""Records f.b and f.c."""\nobs = {}\nnote = "f.b f.c"\nobs["f.a"] = 1\n'
    assert _keys(code) == (1, 0)


def test_ast_ignores_dead_code():
    code = ("obs = {}\nif False:\n    obs['f.b'] = 2\nfor x in [1, 2]:\n    obs['f.a'] = x\n    continue\n"
            "    obs['f.c'] = 3\nif 0:\n    obs['f.d'] = 4\nelse:\n    obs['f.e'] = 5\n")
    assert _keys(code) == (2, 2)


def test_ast_early_break_runs_one_input():
    code = "obs = {}\nfor x in [1, 2, 3]:\n    obs['f.a'] = x\n    break\n"
    assert _keys(code) == (1, 1)
    cond = "obs = {}\nfor x in [1, 2, 3]:\n    obs['f.a'] = x\n    if x > 9:\n        break\n"
    assert _keys(cond) == (1, 3)


def test_range_inputs_read_from_text_and_ast():
    code = "obs = {}\nfor i in range(2, 8, 2):\n    obs['f.a'] = i\n"
    assert _keys(code) == (1, 3)
    assert model_probes.original_counts(code + "if x:\nprint(x)\n")["inputs"] == 3


def test_fstring_keys_count_once_per_input():
    code = "obs = {}\nfor w in ['a', 'b', 'c']:\n    obs[f'f.{w}'] = 1\n"
    assert _keys(code) == (3, 3)


def test_repair_hiding_dropped_keys_in_a_comment_is_rejected(tmp_path):
    broken = dict(GOOD["probes"][0], id="p1", code=THREE + "if x:\nprint(x)\n")
    sly = ONE + "# obs['f.b'] = 2; obs['f.c'] = 3\n"
    assert model_probes._token_obs_keys(sly) == 1   # comments are not key positions
    drop = {"probes": [dict(GOOD["probes"][0], id="p1", code=sly)]}
    _, out = _run(tmp_path, [{"probes": [broken]}] + [drop] * model_probes.PARSE_REPAIR_TRIES + [{"probes": []}])
    r = out["parse_repairs"][0]
    assert r["outcome"] == "rejected: the repair has fewer observation keys (1 < 3)"
    assert r["counts"] == {"before": {"keys": 3, "inputs": 3, "read": "tokens"},
                           "after": {"keys": 1, "inputs": 1, "read": "ast"}}


IMPORTS = ("import importlib, json\nfrom unittest import mock\nm = importlib.import_module('pkg.mod')\n"
           "obs = {'f.a': 1}\nwith mock.patch('pkg.mod.f'):\n    obs['f.b'] = 2\n"
           "print(json.dumps({'observations': obs}))\n")


def test_identical_repair_with_import_and_patch_strings_passes():
    broken = IMPORTS + "if x:\nprint(x)\n"
    assert model_probes._token_obs_keys(broken) == 2
    why, counts = model_probes._repair_loses(broken, IMPORTS)
    assert why is None and counts["before"]["keys"] == counts["after"]["keys"] == 2


def test_unreadable_key_with_keys_hidden_in_a_comment_is_rejected(tmp_path):
    broken = dict(GOOD["probes"][0], id="p1", code=THREE + "if x:\nprint(x)\n")
    sly = "import json\nk = 'f.a'\no = {}\no[k] = 1\n# o['f.b'] = 2; o['f.c'] = 3\nprint(json.dumps(o))\n"
    assert model_probes.repair_counts(sly) is None
    drop = {"probes": [dict(GOOD["probes"][0], id="p1", code=sly)]}
    _, out = _run(tmp_path, [{"probes": [broken]}] + [drop] * model_probes.PARSE_REPAIR_TRIES + [{"probes": []}])
    r = out["parse_repairs"][0]
    assert r["outcome"] == "rejected: the repair stores under a key that cannot be read"
    assert r["counts"]["after"] is None and r["counts"]["before"]["keys"] == 3


def test_line_breaks_alone_do_not_change_the_count():
    one = "obs = {'f.a': 1, 'f.b': 2}\nobs['f.c'] = 3\n"
    split = "obs = {\n    'f.a': 1,\n\n    'f.b':\n        2,\n}\nobs[\n    'f.c'\n] = 3\n"
    escaped = one.replace("\n", "\\n")
    counts = {model_probes._token_obs_keys(c + "if x:\nprint(x)\n") for c in (one, split)}
    assert counts == {3} and model_probes._token_obs_keys(escaped) == 3
    assert model_probes.repair_counts(one)["keys"] == model_probes.repair_counts(split)["keys"] == 3
