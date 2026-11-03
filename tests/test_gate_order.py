"""A flagged probe claim is needs attention even when no test was collected on either side.

Nothing from a pull request is run again. The dask, rich and barcode fixtures are judged by their own tests.
"""
import importlib.util
import json
from pathlib import Path

from ops.daily_run import compare_sides, nothing_collected_both, verdict_for
from poc import probes

FX = Path(__file__).resolve().parent / "fixtures" / "gate_order"
COV = {"status": "measured", "changed_lines_total": 1, "changed_lines_covered": 1, "adequacy": "adequate"}
EMPTY = "tests produced no results on both sides (collection failed; see pytest logs)"


def _load(name):
    return json.loads((FX / name).read_text())


def _comparison(spec):
    def side(rows):
        return [{k: (v, "") for k, v in rows.items()}] * 3

    return compare_sides({"main": side(spec["tests"]["main"]), "pr": side(spec["tests"]["pr"])})


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


def _judge(name, *, cnv_reason=None):
    spec = _load(name)
    pp = _probes(spec)
    if cnv_reason:
        return spec, None, pp, verdict_for(None, cnv_reason, probe_results=pp)
    cmp = _comparison(spec)
    return spec, cmp, pp, verdict_for(cmp, None, probe_results=pp)


def _script():
    path = Path(__file__).resolve().parents[1] / "scripts" / "rejudge_gate_order.py"
    spec = importlib.util.spec_from_file_location("rejudge_gate_order", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_flagged_claim_and_nothing_collected_needs_attention():
    _spec, cmp, pp, (v, reason, _fl) = _judge("flagged-nothing-collected.json")
    assert nothing_collected_both(cmp, None)
    assert [f["claim"] for f in probes.summarize(pp["items"])["flagged"]] == ["C1"]
    assert v == "needs_attention"
    assert "flagged claim(s) C1" in reason and "no tests ran" in reason
    v2, reason2, _ = _judge("flagged-nothing-collected.json", cnv_reason=EMPTY)[3]
    assert v2 == "needs_attention"
    assert "flagged claim(s) C1" in reason2 and "no tests ran" in reason2
    assert "no results on both sides" in reason2


def test_clean_probes_and_nothing_collected_stay_could_not_verify():
    _spec, cmp, pp, (v, reason, _fl) = _judge("clean-nothing-collected.json")
    assert nothing_collected_both(cmp, None)
    assert probes.summarize(pp["items"])["flagged"] == []
    assert v == "could_not_verify"
    assert "flagged claim" not in reason
    assert "no test actually ran" in reason
    v2, reason2, _ = _judge("clean-nothing-collected.json", cnv_reason=EMPTY)[3]
    assert v2 == "could_not_verify"
    assert "flagged claim" not in reason2
    assert "no results on both sides" in reason2


def test_agreeing_inputs_stay_could_not_verify_when_nothing_was_collected():
    """The probe never reached the change. That exception is unchanged."""
    spec = {"id": "p1", "target": "o/r#1", "about": "x", "claims": [
        {"id": "C1", "text": "the result differs", "covers": ["out"], "expect": "differs"}]}
    item = probes.entry(spec, {"main": [{"out": 1}] * 3, "pr": [{"out": 1}] * 3}, None, [], "model", None)
    item["probe_changed_line_coverage"] = dict(COV)
    item["unable_to_reach"] = "unable to reach the change: calls `_helper` without the new argument"
    cmp = _comparison({"tests": {"main": {}, "pr": {}}})
    assert nothing_collected_both(cmp, None)
    v, reason, _ = verdict_for(cmp, None, probe_results={"status": "ran", "items": [item]})
    assert v == "could_not_verify"
    assert "needs attention: flagged" not in reason
    assert reason.startswith("no test actually ran")


def test_rejudge_script_lists_only_the_records_that_move(tmp_path):
    mod = _script()
    flagged = _judge("flagged-nothing-collected.json")
    clean = _judge("clean-nothing-collected.json")

    def write(folder, judged, stored):
        _spec, cmp, pp, _verdict = judged
        folder.mkdir()
        (folder / "record.json").write_text(json.dumps({
            "comparison": cmp, "probes": pp, "files": {"all": ["pkg/mod.py"], "package_py": ["pkg/mod.py"]},
            "baseline": "full", "product_check": False, "docstring_only": False,
            "behaviour_claims": [], "verdict": stored, "reason": "stored",
            "coverage": {"status": "measured", "changed_lines_total": 1, "changed_lines_covered": 1},
        }))

    write(tmp_path / "flagged", flagged, "could_not_verify")
    write(tmp_path / "clean", clean, "could_not_verify")
    text = "\n".join(mod.report(tmp_path))
    assert "flagged/record.json: stored could_not_verify, new rule needs_attention" in text
    assert "clean/record.json: stored could_not_verify, new rule could_not_verify" in text
    assert "moved:" in text
    assert "flagged/record.json: could_not_verify -> needs_attention" in text
    assert "clean/record.json: could_not_verify ->" not in text
    assert str(tmp_path) not in text
    for line in text.splitlines():
        assert not line.strip().startswith("/")
