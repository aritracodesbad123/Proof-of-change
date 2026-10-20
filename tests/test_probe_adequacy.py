"""Probe adequacy by changed-line coverage on the main side (poc/probe_adequacy.py, ops/daily_run.probe_coverage):
a probe that runs none of the PR's changed lines is not_adequate and can never lead to 'verified'."""
import json
import stat
import sys

import pytest

from guardrails import sandbox
from ops import daily_run as dr
from ops.daily_run import compare_sides, verdict_for
from poc import probe_adequacy as pa
from poc import probes

CLAIM = [{"source": "PR description", "quote": "Results are unchanged.", "pattern": "unchanged"}]
SAME = [{"id": "C1", "text": "results unchanged", "covers": ["r"], "expect": "same"}]


def _cmp_verified():
    same = {"t::a": ("passed", ""), "t::b": ("passed", "")}
    return compare_sides({"main": [same] * 3, "pr": [same] * 3})


def _probe(claims, main, pr, adequacy=None):
    spec = {"id": "p", "target": "o/r#1", "about": "x", "claims": claims}
    it = probes.entry(spec, {"main": [main] * 3, "pr": [pr] * 3}, {"main": ["m"], "pr": ["p"]}, [], "library", None)
    if adequacy == "unmeasured":
        it["probe_changed_line_coverage"] = pa.assess({"status": "not measured", "why": "test"})
    elif adequacy:
        it["probe_changed_line_coverage"] = pa.assess(
            {"status": "measured", "changed_lines_total": 4, "changed_lines_covered": 2 if adequacy == "adequate" else 0})
    return {"status": "ran", "items": [it]}


# ---------------------------------------------------------------- changed lines on the main side
def test_main_side_lines():
    main = "a\nb\nc\nd\n"
    assert pa.main_side_lines(main, "a\nB\nc\nd\n") == {2}              # replaced
    assert pa.main_side_lines(main, "a\nc\nd\n") == {2}                 # deleted
    assert pa.main_side_lines(main, "a\nb\nNEW\nc\nd\n") == {2, 3}      # inserted: neighbours stand in
    assert pa.main_side_lines(main, "x\n" + main) == {1}                # inserted at the top
    assert pa.main_side_lines(main, main + "z\n") == {4}                # appended
    assert pa.main_side_lines(None, "new file\n") == set()
    assert pa.main_side_lines(main, None) == {1, 2, 3, 4}               # file deleted by the PR
    assert pa.main_side_lines(main, main) == set()


@pytest.mark.parametrize("cov,adequacy", [
    ({"status": "measured", "changed_lines_total": 5, "changed_lines_covered": 1}, "adequate"),
    ({"status": "measured", "changed_lines_total": 5, "changed_lines_covered": 0}, "not_adequate"),
    ({"status": "measured", "changed_lines_total": 0, "changed_lines_covered": 0}, "not_adequate"),
    ({"status": "not measured", "why": "--no-coverage"}, "unmeasured"),
    (None, "unmeasured"),
])
def test_assess(cov, adequacy):
    assert pa.assess(cov)["adequacy"] == adequacy


def test_measure_uses_the_coverage_gate_counting():
    cov_files = {"/w/side-main/widgets/core.py": {"executed_lines": [1, 2], "missing_lines": [5, 6]}}
    r = pa.measure({"widgets/core.py": {2, 3, 5}}, cov_files)      # 3 is not executable
    assert (r["changed_lines_total"], r["changed_lines_covered"], r["adequacy"]) == (2, 1, "adequate")
    r = pa.measure({"widgets/core.py": {5, 6}}, cov_files)
    assert (r["changed_lines_covered"], r["adequacy"]) == (0, "not_adequate")


# ---------------------------------------------------------------- verdict
def test_not_adequate_probe_cannot_lead_to_verified():
    # the probe "proves" the same-claim, but it never reached the changed code
    v, reason, _ = verdict_for(_cmp_verified(), None, probe_results=_probe(SAME, {"r": 1}, {"r": 1}, "not_adequate"),
                               claims=CLAIM)
    assert v == "could_not_verify"
    assert "not_adequate" in reason and "unverified behaviour claim" in reason
    assert "C1 proven" not in reason


def test_adequate_probe_still_decides():
    assert verdict_for(_cmp_verified(), None, probe_results=_probe(SAME, {"r": 1}, {"r": 1}, "adequate"),
                       claims=CLAIM)[0] == "verified"


def test_unmeasured_coverage_does_not_cover_the_change():
    v, reason, _ = verdict_for(_cmp_verified(), None, probe_results=_probe(SAME, {"r": 1}, {"r": 1}, "unmeasured"),
                               claims=CLAIM)
    assert v == "could_not_verify"
    assert "no measured line coverage" in reason and "unverified behaviour claim" in reason
    missing = _probe(SAME, {"r": 1}, {"r": 1})          # no coverage block at all
    assert verdict_for(_cmp_verified(), None, probe_results=missing, claims=CLAIM)[0] == "could_not_verify"
    assert not pa.has_measured_coverage(missing["items"][0])
    # A difference is still needs attention, so this cannot hide a finding.
    red = verdict_for(_cmp_verified(), None, probe_results=_probe([], {"c": 1}, {"c": 2}, "unmeasured"))
    assert red[0] == "needs_attention" and "differs" in red[1]
    # No behaviour claim: the tests were already verified. Dropping the probe holds that verdict.
    assert verdict_for(_cmp_verified(), None, probe_results=_probe(SAME, {"r": 1}, {"r": 1}, "unmeasured"))[0] == "verified"
    # A run that already could not verify is not raised.
    assert verdict_for(None, "source build failed",
                       probe_results=_probe(SAME, {"r": 1}, {"r": 1}, "unmeasured"))[0] == "could_not_verify"


def test_not_adequate_probe_still_flags_differences():
    v, reason, _ = verdict_for(_cmp_verified(), None, probe_results=_probe([], {"c": 1}, {"c": 2}, "not_adequate"))
    assert v == "needs_attention" and "differs and no claim covers it" in reason


def test_deciding_items_keeps_only_red_and_amber_of_not_adequate():
    pr = _probe([], {"c": 1, "d": 1}, {"c": 2, "d": 1}, "not_adequate")
    items, notes = pa.deciding_items(pr["items"])
    assert [o["name"] for o in items[0]["observations"]] == ["c"] and len(notes) == 1
    assert pr["items"][0]["observations"][1]["name"] == "d"      # the record itself is not changed


def test_summary():
    pr = _probe(SAME, {"r": 1}, {"r": 1}, "not_adequate")
    s = pa.summary(pr["items"])
    assert s["status"] == "measured" and s["not_adequate"] == ["p"] and s["probes"]["p"]["changed_lines_total"] == 4
    assert pa.summary([])["status"] == "no probes"


# ---------------------------------------------------------------- probe_coverage: a real coverage.py run (no sandbox)
PROBE_SRC = '''import json
import sys
sys.path.insert(0, {root!r})
from widgets import core
PROBE = {{"id": "{pid}", "target": "o/widgets#1", "about": "x", "claims": []}}
print(json.dumps({{"observations": {{"v": core.{fn}()}}}}))
'''


@pytest.fixture
def no_sandbox():
    was = sandbox.enabled()
    sandbox.configure(False)
    yield
    sandbox.configure(was)


def test_probe_coverage_runs_each_probe_on_main_under_coverage(tmp_path, no_sandbox):
    pytest.importorskip("coverage")
    main, pr = tmp_path / "side-main", tmp_path / "side-pr"
    for root, body in ((main, "    return 1\n"), (pr, "    return 2\n")):
        (root / "widgets").mkdir(parents=True)
        (root / "widgets" / "__init__.py").write_text("")
        (root / "widgets" / "core.py").write_text("def changed():\n" + body + "\n\ndef untouched():\n    return 0\n")
    vm = tmp_path / "venv-main"
    (vm / "bin").mkdir(parents=True)
    py = vm / "bin" / "python"
    py.write_text(f"#!/bin/sh\nexec {sys.executable} \"$@\"\n")
    py.chmod(py.stat().st_mode | stat.S_IEXEC)
    paths = {}
    for pid, fn in (("hits", "changed"), ("misses", "untouched")):
        paths[pid] = tmp_path / f"{pid}.py"
        paths[pid].write_text(PROBE_SRC.format(root=str(main), pid=pid, fn=fn))
    results = {"status": "ran", "items": [{"id": pid, "path": str(p)} for pid, p in paths.items()]}
    item = {"files": {"all": ["widgets/core.py", "tests/test_core.py"]}}
    prdir = tmp_path / "prdir"
    prdir.mkdir()

    class A:
        no_coverage = False
    s = dr.probe_coverage(item, results, vm, main, pr, prdir, A())
    by = {it["id"]: it["probe_changed_line_coverage"] for it in results["items"]}
    assert by["hits"]["adequacy"] == "adequate" and by["hits"]["changed_lines_covered"] == 1
    assert by["misses"]["adequacy"] == "not_adequate" and by["misses"]["changed_lines_total"] == 1
    assert s["not_adequate"] == ["misses"] and s["side"] == "main"
    assert json.loads((prdir / "probe-cov-hits.json").read_text())["files"]

    A.no_coverage = True
    s = dr.probe_coverage(item, results, vm, main, pr, prdir, A())
    assert s["status"] == "not measured" and results["items"][0]["probe_changed_line_coverage"]["adequacy"] == "unmeasured"
    assert dr.probe_coverage(item, {"items": []}, vm, main, pr, prdir, A())["status"] == "no probes"
