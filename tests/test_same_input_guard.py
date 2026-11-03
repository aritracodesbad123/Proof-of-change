"""An agreeing differs observation is not excused when another claim differs on the same input.

The barcode fixture is modelled on python-barcode pull request 162. C1 and C2 differ on low160 and high255
(IllegalCharacterError on the base, accepted on the pull request). C3 agrees on those same inputs: uses_fnc4 is
false on both sides. Nothing from that pull request is run again.
"""
import copy
import json
from pathlib import Path

from ops.daily_run import compare_sides, cross_run_test_ids, verdict_for
from poc import probes
from poc.verdict import FindingLabel

FX = Path(__file__).resolve().parent / "fixtures" / "same_input_guard"
NARROW = Path(__file__).resolve().parent / "fixtures" / "narrow_cross_run"
COV = {"status": "measured", "changed_lines_total": 1, "changed_lines_covered": 1, "adequacy": "adequate"}
P, NH = FindingLabel.PROVEN.value, FindingLabel.NEEDS_HUMAN.value


def _load(name, root=FX):
    return json.loads((root / name).read_text())


def _comparison(spec):
    def side(rows):
        one = {k: (v, "assertion failed" if v in ("failed", "error") else "") for k, v in rows.items()}
        return [one] * 3

    return compare_sides({"main": side(spec["tests"]["main"]), "pr": side(spec["tests"]["pr"])})


def _files(spec):
    all_files = list(spec["files"])
    return {"all": all_files, "package_py": list(spec.get("package_py") or []), "compiled": [],
            "other": [f for f in all_files if f not in (spec.get("package_py") or [])]}


def _probes(spec):
    items = []
    for raw in spec["probes"]:
        body = {"id": raw["id"], "target": raw.get("target", "o/r#1"), "about": raw.get("about", "x"),
                "claims": raw["claims"]}
        item = probes.entry(body, {"main": [raw["main"]] * 3, "pr": [raw["pr"]] * 3}, None, [],
                            raw.get("source", "model"), None)
        item["status"] = "ran"
        item["probe_changed_line_coverage"] = dict(COV)
        items.append(item)
    return {"status": "ran", "items": items}


def _judge(spec):
    files = _files(spec)
    cmp = _comparison(spec)
    pp = _probes(spec)
    return files, cmp, pp, verdict_for(cmp, None, None, files, pp)


def _without_cross_run(spec):
    spec = copy.deepcopy(spec)
    spec["files"] = [f for f in spec["files"] if not str(f).rsplit("/", 1)[-1].startswith("test_")]
    return spec


def _o(name, state, label, claim):
    return {"name": name, "state": state, "label": label, "claim": claim,
            "main": 1, "pr": 1 if state == "same" else 2}


def test_barcode_162_needs_attention_without_a_cross_run():
    spec = _without_cross_run(_load("barcode-162.json"))
    files, cmp, pp, (v, reason, fl) = _judge(spec)
    assert cross_run_test_ids(cmp, files) == []
    assert v == "needs_attention"
    assert "cross_run_settled" not in fl
    assert "does not differ although the claim says it does" in reason
    assert "claim not shown on these inputs" not in reason
    names = sorted(o["name"] for it in pp["items"] for o in it["observations"] if o.get("claim") == "C3")
    assert names == ["high255.uses_fnc4", "low160.uses_fnc4"]
    flagged = {f["name"] for f in probes.summarize(pp["items"])["flagged"]}
    assert set(names) <= flagged


def test_barcode_162_needs_attention_with_a_passing_cross_run():
    spec = _load("barcode-162.json")
    files, cmp, _pp, (v, reason, fl) = _judge(spec)
    assert cross_run_test_ids(cmp, files)
    assert any(i.endswith("test_high_characters") for i in cross_run_test_ids(cmp, files))
    assert v == "needs_attention"
    assert "cross_run_settled" not in fl
    assert "does not differ although the claim says it does" in reason
    assert "low160.uses_fnc4" in reason and "high255.uses_fnc4" in reason


def test_agreeing_claim_on_a_different_input_stays_advisory():
    s = probes.summarize([{"id": "p", "observations": [
        _o("low160.c1", "differs", P, "C1"),
        _o("other.uses_fnc4", "same", NH, "C3"),
    ]}])
    assert s["flagged"] == []
    assert s["advisory_agreeing_differs"] == ["other.uses_fnc4"]


def test_a_clean_observation_stays_advisory_when_its_sibling_shares_the_proven_input():
    s = probes.summarize([{"id": "p", "observations": [
        _o("low160.c1", "differs", P, "C1"),
        _o("low160.uses_fnc4", "same", NH, "C3"),
        _o("other.uses_fnc4", "same", NH, "C3"),
    ]}])
    assert [f["name"] for f in s["flagged"]] == ["low160.uses_fnc4"]
    assert s["advisory_agreeing_differs"] == ["other.uses_fnc4"]


def test_cross_run_does_not_settle_a_claim_that_agrees_on_a_proven_input():
    spec = _load("barcode-162.json")
    spec["probes"][0]["claims"].append({
        "id": "C4", "text": "a separate counter changes", "covers": ["other.out"], "expect": "differs"})
    spec["probes"][0]["main"]["other.out"] = 1
    spec["probes"][0]["pr"]["other.out"] = 1
    _files_d, cmp, _pp, (v, reason, fl) = _judge(spec)
    assert cross_run_test_ids(cmp, _files_d)
    assert v == "needs_attention" and "cross_run_settled" not in fl
    assert "low160.uses_fnc4" in reason
    assert "other.out" in reason and "claim not shown on these inputs" in reason


def test_rejudge_report_counts_what_stays_settled_and_what_flips():
    import importlib.util
    path = Path(__file__).resolve().parents[1] / "scripts" / "rejudge_same_input.py"
    spec = importlib.util.spec_from_file_location("rejudge_same_input", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    text = "\n".join(mod.collect())
    print(text)
    assert "stay settled: 6" in text
    assert "flip back: 0" in text
    assert "  none" in text
    assert "stored record.json verdict changes: none" in text
    for row in (
        "loguru #1536: verified",
        "toolz #654: verified",
        "attrs #1647 linking test: verified",
        "attrs #1647 linked, stored comparison: could_not_verify",
        "narrow agreeing-settled: verified",
        "narrow never-ran-settled: verified",
        "python-barcode #162 modelled, no cross-run: verified -> needs_attention",
        "python-barcode #162 modelled, passing cross-run: verified -> needs_attention",
    ):
        assert row in text
    assert "not in the repo: ce #556" in text
    assert "pingouin #554" in text


def test_a_never_run_differs_claim_is_still_settled_beside_a_proven_input():
    spec = _load("never-ran-settled.json", NARROW)
    spec["probes"].append({
        "id": "model-p2",
        "claims": [{"id": "C2", "text": "the high character is accepted", "covers": ["low160.out"], "expect": "differs"}],
        "main": {"low160.out": {"raises": "IllegalCharacterError"}},
        "pr": {"low160.out": "accepted"},
    })
    _files_d, cmp, _pp, (v, reason, fl) = _judge(spec)
    assert cross_run_test_ids(cmp, _files_d)
    assert v == "verified" and "cross_run_settled" in fl and "C1" in reason
