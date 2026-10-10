"""Probes: the runner and judging rules (poc/probes.py), the verdict rule (ops/daily_run.verdict_for), the golden
known-answer PR case (rasbt/mlxtend#1229), the reviewer report's Probes section, schema rev 6. CI uses recorded probe
outputs (tests/fixtures/probes/), so nothing here needs the network."""
import copy
import json
import shutil
import stat
import sys
from pathlib import Path

import pytest

from evals.checks import GOLDEN_PR_BATCH, check_golden_pr_case, evaluate_record, load_golden
from ops.daily_run import base_env, compare_sides, rejudge_probes, verdict_for
from poc import probes
from poc.probes import PROBE_ERROR, ProbeError

REPO = Path(__file__).resolve().parent.parent
FIX = Path(__file__).parent / "fixtures" / "probes" / "mlxtend-1229"
MLX = REPO / "probes" / "rasbt" / "mlxtend" / "1229.py"
SCHEMA = json.loads((REPO / "harness" / "schema" / "observation.schema.json").read_text())
GOLDEN = json.loads(GOLDEN_PR_BATCH.read_text().splitlines()[0])

SPEC = {"id": "p", "target": "o/r#1", "about": "x", "claims": [
    {"id": "C1", "text": "a changes", "covers": ["a.*"], "expect": "differs"},
    {"id": "C2", "text": "b stays", "covers": ["b"], "expect": "same"}]}


def runs(main: dict, pr: dict, pr_alt: dict | None = None) -> dict:
    return {"main": [main] * 3, "pr": [pr, pr_alt or pr, pr]}


def labels(results):
    return {r["name"]: r["label"] for r in results}


# ---------------------------------------------------------------- probe files
def test_library_probe_spec_is_read_without_importing():
    spec = probes.read_spec(MLX)
    assert spec["id"] == "feature-groups-permutation" and spec["target"] == "rasbt/mlxtend#1229"
    assert [c["id"] for c in spec["claims"]] == ["C1", "C2"] and len(spec["sha256"]) == 64
    assert probes.find_probes("rasbt/mlxtend", 1229) == [MLX]
    assert probes.find_probes("rasbt/mlxtend", 1236) == [] and probes.find_probes("numpy/numpy", 32910) == []


@pytest.mark.parametrize("body", ["x = 1\n", 'PROBE = {"id": "p"}\n',
                                  'PROBE = {"id": "p", "target": "t", "about": "a", "claims": [{"id": "C1"}]}\n',
                                  'PROBE = {"id": "p", "target": "t", "about": "a", "claims": '
                                  '[{"id": "C1", "text": "t", "covers": [], "expect": "maybe"}]}\n'])
def test_bad_probe_specs_are_rejected(tmp_path, body):
    f = tmp_path / "1.py"
    f.write_text(body)
    with pytest.raises(ProbeError):
        probes.read_spec(f)


def test_every_library_probe_is_valid_and_named_for_its_pr():
    files = sorted((REPO / "probes").rglob("*.py"))
    assert files
    for f in files:
        spec = probes.read_spec(f)
        owner, repo, name = f.relative_to(REPO / "probes").parts
        assert spec["target"] == f"{owner}/{repo}#{name.split('-')[0].removesuffix('.py')}"


# ---------------------------------------------------------------- output parsing
def test_observations_of_output():
    assert probes.observations_of('noise\n{"observations": {"a": 1}}', 0) == {"a": 1}
    assert PROBE_ERROR in probes.observations_of("Traceback ...", 1)
    assert probes.observations_of("", "timeout") == {PROBE_ERROR: {"timeout": True}}
    assert probes.observations_of('{"observations": {"a": 1}}', 1) == {"a": 1, PROBE_ERROR: {"exit_code": 1}}
    assert PROBE_ERROR in probes.observations_of('{"no": "observations"}', 0)


def test_saved_output_round_trips_and_is_citable(tmp_path):
    obs = {"b": [1.5, 2], "a": {"x": None}}
    probes.write_output(tmp_path / "o.jsonl", obs)
    assert probes.read_output(tmp_path / "o.jsonl") == obs
    c = probes.citation("o.jsonl", obs, "b")
    assert c["line"] == 2 and c["quote"] in (tmp_path / "o.jsonl").read_text().splitlines()[1]


# ---------------------------------------------------------------- judging rules
@pytest.mark.parametrize("main,pr,name,label", [
    ({"a.x": 1}, {"a.x": 2}, "a.x", "proven"),            # claim says it changes, it does
    ({"b": 1}, {"b": 1}, "b", "proven"),                  # claim says it stays, it does
    ({"b": 1}, {"b": 2}, "b", "false_claim"),             # claim says it stays, it changes
    ({"a.x": 1}, {"a.x": 1}, "a.x", "needs_human"),       # claim says it changes, it does not
    ({"c": 1}, {"c": 2}, "c", "unmentioned"),             # no claim covers the difference
    ({"c": 1}, {"c": 1}, "c", "no_difference"),
    ({"c": 1}, {}, "c", "unmentioned"),                   # observation gone on the PR side
    ({"c": 1.0}, {"c": 1}, "c", "unmentioned"),           # type-aware: 1.0 != 1
])
def test_judge_labels(main, pr, name, label):
    assert labels(probes.judge(SPEC, runs(main, pr)))[name] == label


def test_flaky_observation_is_flaky_never_unmentioned():
    res = probes.judge(SPEC, runs({"c": 1}, {"c": 1}, pr_alt={"c": 2}))
    assert labels(res) == {"c": "flaky"}


def test_probe_crash_on_both_sides_is_not_testable_on_pr_only_is_a_difference():
    err = {PROBE_ERROR: {"crash": "non-json output", "exit_code": 1}}
    assert labels(probes.judge(SPEC, runs(err, err))) == {PROBE_ERROR: "not_testable"}
    got = labels(probes.judge(SPEC, runs({"c": 1}, err)))
    assert got[PROBE_ERROR] == "unmentioned" and got["c"] == "unmentioned"


def test_field_level_differences():
    res = probes.judge(SPEC, runs({"c": {"g1": 1, "g2": 2}}, {"c": {"g1": 1, "g2": 3}}))
    assert res[0]["diffs"] == [{"field": "g2", "main": 2, "pr": 3}]


# ---------------------------------------------------------------- the runner, on a local probe (no network)
def _side_python(tmp_path: Path, side: str) -> Path:
    exe = tmp_path / f"python-{side}"
    exe.write_text(f'#!/bin/sh\nPROBE_SIDE={side} exec "{sys.executable}" "$@"\n')
    exe.chmod(exe.stat().st_mode | stat.S_IEXEC)
    return exe


def test_run_probe_alternates_saves_and_cites(tmp_path):
    probe = tmp_path / "7.py"
    probe.write_text('import json, os\nPROBE = {"id": "env", "target": "o/r#7", "about": "side marker", "claims": []}\n'
                     'side = os.environ["PROBE_SIDE"]\n'
                     'print(json.dumps({"observations": {"side": side, "const": 42, '
                     '"has_token": any("TOKEN" in k for k in os.environ)}}))\n')
    env = base_env()
    out = tmp_path / "out"
    out.mkdir()
    item = probes.run_probe(probe, {s: _side_python(tmp_path, s) for s in ("main", "pr")}, out, tmp_path / "cwd", env)
    assert [(x["side"], x["run"]) for x in item["per_run"]] == [(s, i) for i in (1, 2, 3) for s in ("main", "pr")]
    assert labels(item["observations"]) == {"const": "no_difference", "has_token": "no_difference", "side": "unmentioned"}
    side = next(o for o in item["observations"] if o["name"] == "side")
    assert (side["main"], side["pr"]) == ("main", "pr")
    for s in ("main", "pr"):
        c = side["citations"][s]
        assert c["quote"] in (out / c["file"]).read_text().splitlines()[c["line"] - 1]
    assert probes.rejudge_entry(item)["observations"] == item["observations"]


def test_base_env_drops_credentials(monkeypatch):
    for k in ("GITHUB_TOKEN", "GITHUB_POC_TOKEN", "AWS_SECRET_ACCESS_KEY", "SOME_API_KEY", "DB_PASSWORD"):
        monkeypatch.setenv(k, "secret")
    env = base_env()
    assert not any(v == "secret" for v in env.values()) and env["OMP_NUM_THREADS"] == "1"


# ---------------------------------------------------------------- recorded mlxtend#1229 outputs (fixtures)
def _recorded():
    got = {s: [probes.read_output(FIX / f"probe-feature-groups-permutation-{s}-{i}.jsonl") for i in (1, 2, 3)]
           for s in ("main", "pr")}
    return probes.judge(probes.read_spec(MLX), got)


def test_recorded_mlxtend_outputs_flag_the_two_unclaimed_differences():
    res = {r["name"]: r for r in _recorded()}
    assert {n: r["label"] for n, r in res.items()} == {
        "caller_x_after_call.changed_columns": "unmentioned",       # X no longer left shuffled: a fix not in the PR text
        "int_groups_after_multi_group.importances": "unmentioned",  # RNG draws per group, not per column
        "int_groups_only.importances": "proven",                    # claim C2
        "list_groups.columns_permuted": "proven",                   # claim C1
        "no_groups.importances": "no_difference"}
    h = res["int_groups_after_multi_group.importances"]
    assert round(h["main"]["3"][0], 4) == 0.1186 and round(h["pr"]["3"][0], 4) == 0.1915
    assert res["caller_x_after_call.changed_columns"]["main"] == [0, 1] and res["caller_x_after_call.changed_columns"]["pr"] == []
    assert res["list_groups.columns_permuted"]["main"] == {"[2]": [0], "[3]": [0], "[4]": [0]}


# ---------------------------------------------------------------- verdict rule
def _cmp_verified():
    same = {"t::a": ("passed", ""), "t::b": ("passed", "")}
    return compare_sides({"main": [same] * 3, "pr": [same] * 3})


def _probes(main, pr):
    return {"status": "ran", "items": [probes.entry(SPEC, runs(main, pr), {"main": ["m"], "pr": ["p"]}, [], "library", None)]}


def test_probe_finding_turns_verified_into_needs_attention():
    v, reason, fl = verdict_for(_cmp_verified(), None, None, None, _probes({"c": 1}, {"c": 2}))
    assert v == "needs_attention" and reason.startswith("probe: 1 observation(s) need attention: c differs")
    assert "tests: " in reason and "unmentioned" in fl


def test_green_probes_never_change_the_verdict():
    for cmp, cnv in ((_cmp_verified(), None), (None, "main side could not be set up: x")):
        base = verdict_for(cmp, cnv)
        v, reason, _ = verdict_for(cmp, cnv, None, None, _probes({"b": 1, "a.x": 1}, {"b": 1, "a.x": 2}))
        assert v == base[0] and reason.startswith(base[1]) and "claim(s) C1, C2 proven" in reason


def test_probe_finding_counts_when_tests_could_not_verify():
    v, reason, _ = verdict_for(None, "no tests could be mapped to the touched modules", None, None,
                               _probes({"c": 1}, {"c": 2}))
    assert v == "needs_attention" and "tests: no tests could be mapped" in reason


@pytest.mark.parametrize("case", ["pandas-70520", "pandera-2552", "pandas-70989", "sklearn-35114"])
def test_no_probe_means_no_change(case):
    """Real day-1 comparisons: without probes (absent, or status none) the verdict and reason are exactly the tests'."""
    from test_daily_run import _verdict
    cmp, (v, reason, fl) = _verdict(case)
    for none in (None, {"status": "none", "items": []}):
        assert verdict_for(cmp, None, None, None, none) == verdict_for(cmp, None, None, None)
    assert rejudge_probes({"status": "none", "items": []}) == {"status": "none", "items": []}


def test_morning_prs_have_no_fixed_probe_except_mlxtend_1229():
    morning = [("pydata/xarray", 11696), ("unionai-oss/pandera", 2552), ("numpy/numpy", 32967), ("numpy/numpy", 32940),
               ("numpy/numpy", 32910), ("pandas-dev/pandas", 70989), ("pandas-dev/pandas", 70977),
               ("pandas-dev/pandas", 70976), ("pandas-dev/pandas", 70915), ("pandas-dev/pandas", 70812),
               ("pandas-dev/pandas", 70520), ("scikit-learn/scikit-learn", 35114), ("scikit-learn/scikit-learn", 35112),
               ("scikit-learn/scikit-learn", 34219)]
    assert all(probes.find_probes(r, n) == [] for r, n in morning)


# ---------------------------------------------------------------- golden known-answer case
def _case():
    return next(c for c in load_golden() if c["name"] == "golden-pr-mlxtend-1229-probe")


def test_golden_mlxtend_1229_case_passes_and_is_probe_driven():
    assert check_golden_pr_case(GOLDEN, _case()).status == "pass"
    assert all(r.status == "pass" for r in evaluate_record(GOLDEN, require_v1=True))
    assert verdict_for(GOLDEN["comparison"], None, GOLDEN["exit_check"], GOLDEN["files"])[0] == "verified"  # tests alone


def _drop_observation(rec, name):
    r = copy.deepcopy(rec)
    it = r["probes"]["items"][0]
    for side in ("main", "pr"):
        for run in it["runs"][side]:
            run.pop(name, None)
    return r


def test_golden_case_fails_when_the_probe_finding_is_lost():
    r = _drop_observation(GOLDEN, "int_groups_after_multi_group.importances")
    res = check_golden_pr_case(r, _case())
    assert res.status == "fail" and "probe observations needing attention" in res.detail
    r = _drop_observation(_drop_observation(GOLDEN, "int_groups_after_multi_group.importances"),
                          "caller_x_after_call.changed_columns")
    res = check_golden_pr_case(r, _case())
    assert res.status == "fail" and "re-derived verdict verified" in res.detail      # without the probe: a miss


def test_golden_case_fails_on_a_changed_value_or_verdict():
    r = copy.deepcopy(GOLDEN)
    for run in r["probes"]["items"][0]["runs"]["pr"]:
        run["int_groups_after_multi_group.importances"]["3"] = [0.1185770248176875]
    assert check_golden_pr_case(r, _case()).status == "fail"
    r = dict(copy.deepcopy(GOLDEN), verdict="verified")
    assert "recorded verdict verified" in check_golden_pr_case(r, _case()).detail


# ---------------------------------------------------------------- schema rev 6
def test_golden_pr_record_is_valid_rev6():
    from guardrails.schema import validate_record
    from ops.schema_check import validate
    assert validate(GOLDEN, SCHEMA) == [] and validate_record(GOLDEN) == []
    bad = copy.deepcopy(GOLDEN)
    bad["probes"]["items"][0]["observations"][0]["label"] = "suspicious"
    assert validate(bad, SCHEMA)
    bad = copy.deepcopy(GOLDEN)
    bad["probes"]["status"] = "maybe"
    assert validate(bad, SCHEMA)


# ---------------------------------------------------------------- reviewer report
def test_report_has_a_cited_probes_section(tmp_path):
    from reports.pr_report import render_run
    run = tmp_path / "run"
    d = run / "mlxtend-1229"
    d.mkdir(parents=True)
    for f in FIX.glob("*.jsonl"):
        shutil.copy(f, d)
    (d / "record.json").write_text(json.dumps(GOLDEN))
    rows = render_run(run, tmp_path / "out", formats=("md",))
    md = (tmp_path / "out" / "mlxtend-1229" / "REPORT.md").read_text()
    assert rows[0]["verdict"] == "NEEDS ATTENTION"
    sec = md.split("## Probes", 1)[1].split("\n## ", 1)[0]
    assert "`int_groups_after_multi_group.importances`" in sec and "0.118577] -> [0.191495" in sec
    assert sec.count("probe-feature-groups-permutation-main-1.jsonl:") == 5
    assert "| P-C1 |" in md and "| P-C2 |" in md and "not built yet (needs Nemotron)" not in md
    assert "Citation check (PASS): 10 citation(s)" in sec
    assert any(ln.startswith("| Every probe observation cites its output line |") and "PASS" in ln for ln in md.splitlines())
    (d / "probe-feature-groups-permutation-pr-1.jsonl").write_text("edited\n")
    render_run(run, tmp_path / "out2", formats=("md",))
    assert "do not match their log line" in (tmp_path / "out2" / "mlxtend-1229" / "REPORT.md").read_text()


def test_report_without_probes_says_so(tmp_path):
    from reports.pr_report import render_run
    d = tmp_path / "run" / "mlxtend-1229"
    d.mkdir(parents=True)
    rec = dict(copy.deepcopy(GOLDEN), probes={"status": "none", "items": []})
    (d / "record.json").write_text(json.dumps(rec))
    render_run(tmp_path / "run", tmp_path / "out", formats=("md",))
    md = (tmp_path / "out" / "mlxtend-1229" / "REPORT.md").read_text()
    assert "No probe exists for this PR" in md

