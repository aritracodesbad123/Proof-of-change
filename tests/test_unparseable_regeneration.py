"""An empty or still-unparseable probe is regenerated once. The first failure is not scored.

If that new probe is also unparseable or cannot be run, the record stays could_not_verify, including when
tests fail on the base and pass on the pull request. A new probe that is valid is judged by the usual gates.
The AI-probe gate is not changed: a verified result still needs a model probe that ran a changed line.
"""
from evals.checks import derive_verdict
from ops.daily_run import compare_sides
from poc import model_probes, probes
from tests.test_probe_min_one import GOOD, _run

BROKEN = {"probes": [dict(GOOD["probes"][0], id="p1", code="def broken(:\n    pass\n")]}
FILES = {"all": ["pkg/widget.py", "tests/test_widget.py"], "package_py": ["pkg/widget.py"], "compiled": [],
         "other": ["tests/test_widget.py"]}
COVERAGE = {"status": "measured", "changed_lines_total": 2, "changed_lines_covered": 2}


def _answers(last):
    """First probe, both parse repairs, the existing unusable retry, then ``last`` (the one regeneration)."""
    return [BROKEN] * (model_probes.PARSE_REPAIR_TRIES + 2) + [last]


def _fail_then_pass():
    main = {"tests/test_widget.py::test_fix": ("failed", "AssertionError: old"),
            "tests/test_widget.py::test_keep": ("passed", "")}
    pr = {"tests/test_widget.py::test_fix": ("passed", ""),
          "tests/test_widget.py::test_keep": ("passed", "")}
    return compare_sides({"main": [main] * 3, "pr": [pr] * 3})


def _record(probe):
    rec = {"files": FILES, "comparison": _fail_then_pass(), "behaviour_claims": [], "docstring_only": False,
           "baseline": "full", "coverage": dict(COVERAGE), "product_check": True}
    if probe is not None:
        rec["probes"] = probe
    return rec


def _ran_probe(covered):
    spec = {"id": "p1", "target": "o/r#1", "about": "x",
            "claims": [{"id": "C1", "expect": "differs", "covers": ["v"]}]}
    runs = {"main": [{"v": 1}] * 3, "pr": [{"v": 2}] * 3}
    item = {**spec, "source": "model", "status": "ran", "runs": runs, "observations": probes.judge(spec, runs),
            "probe_changed_line_coverage": {"status": "measured", "changed_lines_total": 1,
                                            "changed_lines_covered": covered, "adequacy": "adequate"}}
    return probes.apply_status({"status": "ran", "items": [item]})


def _probe_calls(prov) -> int:
    return sum(1 for task, _user in prov.prompts if task == "probes")


def test_a_still_unparseable_probe_is_regenerated_once_and_the_discard_is_kept(tmp_path):
    prov, out = _run(tmp_path, _answers(GOOD))
    assert _probe_calls(prov) == model_probes.PARSE_REPAIR_TRIES + 3
    assert "discarded because it was empty or did not parse" in prov.prompts[-1][1]
    assert "def broken" not in prov.prompts[-1][1]
    assert [p["path"].name for p in out["probes"]] == ["model-p1.py"]
    assert "print(json.dumps" in out["probes"][0]["path"].read_text()
    kept = tmp_path / "out" / "p1.rejected.py"
    reply = tmp_path / "out" / "rejected-reply.json"
    assert kept.is_file() and "def broken" in kept.read_text()
    assert reply.is_file() and "def broken" in reply.read_text()
    assert out["unparseable_regeneration"]["rejected"] == ["p1.rejected.py"]
    assert out["unparseable_regeneration"]["reply"] == "rejected-reply.json"


def test_a_valid_probe_is_not_regenerated(tmp_path):
    prov, out = _run(tmp_path, [GOOD])
    assert _probe_calls(prov) == 1 and "unparseable_regeneration" not in out
    assert not (tmp_path / "out" / "rejected-reply.json").exists()


def test_a_bad_claim_is_not_this_regeneration(tmp_path):
    bad = {"probes": [dict(GOOD["probes"][0], claims=[{"id": "C9", "covers": ["f.*"], "expect": "differs"}])]}
    prov, out = _run(tmp_path, [bad, bad])
    assert _probe_calls(prov) == 2 and "unparseable_regeneration" not in out
    assert out["probes"] == []


def test_regenerated_probe_still_unparseable_stays_could_not_verify(tmp_path):
    """Fail-then-pass tests do not verify a pull request whose regenerated probe cannot be parsed."""
    _prov, out = _run(tmp_path, _answers(BROKEN))
    assert out["probes"] == []
    assert (tmp_path / "out" / "p1.rejected.py").is_file()
    assert (tmp_path / "out" / "rejected-reply.json").is_file()
    # No probe was kept, which is what a run records when generation produces nothing usable.
    verdict = derive_verdict(_record({"status": "none", "items": []}), "full")
    assert verdict == "could_not_verify"
    # The same tests with a probe that was regenerated but cannot be run stay could_not_verify.
    unrun = {"status": "error", "items": [{
        "id": "p1", "source": "model", "status": "rejected", "target": "o/r#1", "about": "discarded",
        "claims": [], "observations": [], "runs": {"main": [], "pr": []}}]}
    assert derive_verdict(_record(unrun), "full") == "could_not_verify"


def test_a_valid_regenerated_probe_is_judged_normally():
    """The new probe is not verified for having been regenerated. The usual gates decide."""
    proved = derive_verdict(_record(_ran_probe(1)), "full")
    assert proved == "verified"
    # A probe that ran and covered no changed line is still not verified (the AI-probe gate).
    missed = derive_verdict(_record(_ran_probe(0)), "full")
    assert missed == "could_not_verify"
    # Tests alone, which is what an unparseable probe leaves behind, are verified only without that gate.
    assert derive_verdict(_record({"status": "none", "items": []}), "tests") == "verified"
