"""A claim's covers must name observations the probe code records; if not, the probes are asked for once more."""
from poc import model_probes, model_provider
from tests.test_probe_min_one import GOOD, _run

CODE_C2 = "import json\nobs = {}\nobs['c2.first_col.row0'] = 1\nprint(json.dumps({'observations': obs}))\n"
BAD = {"probes": [{"id": "P1", "about": "f", "claims": [{"id": "C1", "covers": ["c1.row0.first_col"],
                                                         "expect": "differs"}], "code": CODE_C2}]}


def test_recorded_names_reads_literal_and_fstring_keys():
    code = "obs = {'a.x': 1}\nfor w in 'ab':\n    obs[f'c1.{w}'] = w\nobs['b.y'] = 2\n"
    assert model_probes.recorded_names(code) == ({"a.x", "b.y"}, {"c1."})


def test_dynamic_key_means_nothing_can_be_told():
    assert model_probes.recorded_names("obs = {}\nfor k in ks:\n    obs[k] = 1\n") is None
    p = {"claims": [{"id": "C1", "covers": ["zzz"]}], "code": "obs = {}\nfor k in ks:\n    obs[k] = 1\n"}
    assert model_probes.unmatched_covers(p) == []


def test_unmatched_cover_is_listed_and_patterns_count():
    assert model_probes.unmatched_covers(BAD["probes"][0]) == ["C1:c1.row0.first_col"]
    ok = dict(BAD["probes"][0], claims=[{"id": "C1", "covers": ["c2.*"], "expect": "differs"}])
    assert model_probes.unmatched_covers(ok) == []
    fs = {"claims": [{"id": "C1", "covers": ["c1.buzz"]}], "code": "obs = {}\nobs[f'c1.{w}'] = 1\n"}
    assert model_probes.unmatched_covers(fs) == []


def test_unmatched_cover_is_retried_once_and_a_better_answer_is_kept(tmp_path):
    prov, out = _run(tmp_path, [BAD, GOOD])
    assert [t for t, _ in prov.prompts] == ["claims", "probes", "probes"]
    assert "C1:c1.row0.first_col" in prov.prompts[-1][1] and out["retried"]
    assert "kept_first_answer" not in out["retried"] and "unmatched_covers" not in out


def test_first_answer_kept_when_retry_is_no_better(tmp_path):
    prov, out = _run(tmp_path, [BAD, BAD])
    assert len(prov.prompts) == 3 and out["retried"]["kept_first_answer"]
    assert len(out["probes"]) == 1 and out["unmatched_covers"] == ["C1:c1.row0.first_col"]


def test_retry_that_drops_a_link_is_not_kept(tmp_path):
    unlinked = {"probes": [dict(GOOD["probes"][0], claims=[])]}
    prov, out = _run(tmp_path, [BAD, unlinked])
    assert out["retried"]["kept_first_answer"] and len(out["probes"]) == 1


def test_matching_covers_are_not_retried(tmp_path):
    prov, out = _run(tmp_path, [GOOD])
    assert len(prov.prompts) == 2 and "retried" not in out


def test_prompt_asks_for_covers_that_match_printed_names():
    assert "Every cover must be an observation name your" in model_provider.PROBES_PROMPT


def test_a_cover_that_is_only_the_claim_id_is_not_asked_about():
    p = {"claims": [{"id": "C1", "covers": ["C1", "c1.*"]}], "code": CODE_C2}
    assert model_probes.unmatched_covers(p) == []


def _probe(pid, cid, covers, code=CODE_C2):
    return {"id": pid, "about": "f", "claims": [{"id": cid, "covers": covers, "expect": "differs"}], "code": code}


CODE_C1 = "import json\nobs = {'x.a': 1, 'x.b': 2}\nprint(json.dumps({'observations': obs}))\n"


def test_retry_with_fewer_usable_probes_is_not_kept():
    first = [_probe("P1", "C1", ["x.zz"], CODE_C1), _probe("P2", "C1", ["x.a"], CODE_C1)]
    assert "fewer usable probes" in model_probes.retry_weakens(first, [_probe("P1", "C1", ["x.*"], CODE_C1)])


def test_retry_matching_fewer_names_for_a_claim_is_not_kept():
    first = [_probe("P1", "C1", ["x.*", "zz"], CODE_C1)]
    assert "fewer observation names for C1" in model_probes.retry_weakens(first, [_probe("P1", "C1", ["x.a"], CODE_C1)])


def test_retry_hiding_its_names_is_not_kept():
    hidden = "obs = {}\nfor k in ks:\n    obs[k] = 1\n"
    first = [_probe("P1", "C1", ["x.a", "zz"], CODE_C1)]
    assert "fewer observation names" in model_probes.retry_weakens(first, [_probe("P1", "C1", ["x.a"], hidden)])


def test_replacing_a_real_cover_with_an_id_cover_is_no_gain():
    first = [_probe("P1", "C1", ["x.a", "zz"], CODE_C1)]
    assert "fewer unmatched" in model_probes.retry_weakens(first, [_probe("P1", "C1", ["x.a", "C1.*"], CODE_C1)])


def test_retry_with_same_unmatched_count_is_not_kept():
    first = [_probe("P1", "C1", ["x.a", "zz"], CODE_C1)]
    assert "fewer unmatched" in model_probes.retry_weakens(first, [_probe("P1", "C1", ["x.a", "yy"], CODE_C1)])


def test_a_strictly_better_retry_is_kept():
    first = [_probe("P1", "C1", ["x.a", "zz"], CODE_C1)]
    assert model_probes.retry_weakens(first, [_probe("P1", "C1", ["x.*"], CODE_C1)]) is None
