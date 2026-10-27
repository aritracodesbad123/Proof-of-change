"""Product-check fixes from the 27 Oct verification: repository addopts kept, claim-less model probes advisory,
"stays the same" claims expect same, test-outcome claims dropped, closed pull requests refused.

Fixtures are the probe sections of the scored records (tests/fixtures/product_claims_2026_10_27). Every test also
checks the study route is unchanged."""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "ops"))

import daily_run as dr  # noqa: E402

from poc import claim_hygiene, probes  # noqa: E402

FX = ROOT / "tests/fixtures/product_claims_2026_10_27"


def _rec(name):
    return json.loads((FX / f"{name}.json").read_text())


def _cmp_verified():
    """A test comparison that on its own is verified."""
    same = {"t::a": ("passed", ""), "t::b": ("passed", "")}
    return dr.compare_sides({"main": [same] * 3, "pr": [same] * 3})


def _verdict(probe_results):
    return dr.verdict_for(_cmp_verified(), None, probe_results=probe_results)


# ---- 36: the repository's own pytest addopts ---------------------------------------------------------------------

def test_36_product_keeps_repo_addopts_study_blanks_them():
    assert dr.repo_addopts_args(True) == []
    assert dr.repo_addopts_flag(True) == ""
    assert dr.repo_addopts_args(False) == ["-o", "addopts="]
    assert dr.repo_addopts_flag(False) == "-o addopts= "


def test_36_contree_shell_keeps_addopts_only_on_product(tmp_path, monkeypatch):
    shells = []

    class Sess:
        def run_op(self, side, shell, disposable, timeout):
            shells.append(shell)
            return {"stdout": "___POC_EXIT___0\n", "stderr": "", "exit_code": 0}

    from poc import contree_sandboxes
    monkeypatch.setattr(contree_sandboxes, "session", lambda: Sess())
    dr._contree_pytest_once("main", ["testing/test_tmpdir.py"], 60, 60, "0", tmp_path / "j.xml", tmp_path / "l.log",
                            keep_addopts=True)
    dr._contree_pytest_once("main", ["testing/test_tmpdir.py"], 60, 60, "0", tmp_path / "j.xml", tmp_path / "l.log")
    assert "addopts" not in shells[0]
    assert "-o addopts= " in shells[1]


def test_36_local_run_tests_keeps_addopts_only_on_product(tmp_path, monkeypatch):
    cmds = []

    def fake_run(cmd, log, **kw):
        cmds.append([str(c) for c in cmd]); Path(log).write_text("")
        return 0, 0.1

    monkeypatch.setattr(dr, "run", fake_run)
    monkeypatch.setattr(dr, "_contree_ready", lambda: False)
    monkeypatch.setattr(dr, "base_env", lambda *a, **k: {})
    monkeypatch.setattr(dr, "side_home", lambda v: tmp_path)
    monkeypatch.setattr(dr, "side_out", lambda v: tmp_path)
    monkeypatch.setattr(dr, "side_sandbox", lambda *a, **k: None)
    v = {"main": tmp_path / "vm", "pr": tmp_path / "vp"}
    t = {"main": ["t.py"], "pr": ["t.py"]}
    cw = {"main": tmp_path, "pr": tmp_path}
    dr.run_tests(v, t, tmp_path, tmp_path, 1, "0", 60, 60, cwds=cw, keep_addopts=True)
    assert all("addopts=" not in c for c in cmds)
    cmds.clear()
    dr.run_tests(v, t, tmp_path, tmp_path, 1, "0", 60, 60, cwds=cw)
    assert all("addopts=" in c for c in cmds)


def test_36_execute_tests_passes_product_route(monkeypatch):
    seen = []
    monkeypatch.setattr(dr, "run_tests", lambda *a, **k: (seen.append(k.get("keep_addopts")), ([], {}))[1])
    monkeypatch.setattr(dr, "finalize_tests", lambda *a: (None, "x", None))
    prod = SimpleNamespace(runs=1, workers="0", test_timeout=1, run_timeout=1, pr="o/r#1", product_check=True,
                           bench=None)
    dr.execute_tests({}, {}, {}, Path("."), Path("."), prod)
    dr.execute_tests({}, {}, {}, Path("."), Path("."), SimpleNamespace(**{**vars(prod), "product_check": False}))
    assert seen == [True, False]


def test_36_scored_record_shows_the_blanked_addopts_failure():
    """The fixture: the product's run collected nothing because pytester (loaded from addopts) was not loaded."""
    r = _rec("pytest-15265")
    assert r["verdict"] == "could_not_verify" and "collection failed" in r["reason"]


# ---- 37: a model probe with no claims is advisory ----------------------------------------------------------------

def test_37_claimless_model_probe_does_not_flag_requests_7520():
    r = _rec("requests-7520")
    before = probes.apply_status(copy.deepcopy(r["probes"]))
    assert _verdict(before)[0] == "needs_attention"            # study route: unchanged
    after = probes.apply_status(claim_hygiene.apply(r["probes"]))
    assert after["claim_hygiene"]["advisory_probes"] == ["model-probe1"]
    v, reason, fl = _verdict(after)
    assert v == "could_not_verify"            # an unclaimed difference is never verified
    assert "no claims attached" in reason and "advisory_unclaimed_difference" in fl
    obs = [o for it in after["items"] for o in it["observations"] if o.get("advisory")]
    assert len(obs) == 3 and all(o["label"] == "unmentioned" for o in obs)   # still shown, still labelled


def test_37_advisory_difference_can_never_be_verified():
    from poc.verdict import FindingLabel
    spec = {"id": "m", "target": "o/r#1", "about": "x", "claims": []}
    item = probes.entry(spec, {"main": [{"a": 1}] * 3, "pr": [{"a": 2}] * 3}, None, [], "model", None)
    pr = probes.apply_status(claim_hygiene.apply({"status": "ran", "items": [item]}))
    assert pr["items"][0]["observations"][0]["label"] == FindingLabel.UNMENTIONED_CHANGE.value
    assert pr["items"][0]["observations"][0]["advisory"] is True
    for docstring_only in (False, True):
        v = dr.verdict_for(_cmp_verified(), None, probe_results=pr, docstring_only=docstring_only)[0]
        assert v != "verified"
    # without a difference the claim-less probe changes nothing
    same = probes.entry(spec, {"main": [{"a": 1}] * 3, "pr": [{"a": 1}] * 3}, None, [], "model", None)
    pr2 = probes.apply_status(claim_hygiene.apply({"status": "ran", "items": [same]}))
    assert _verdict(pr2)[0] == "verified"


def test_37_claimless_probe_never_hides_test_findings():
    r = _rec("requests-7520")
    after = probes.apply_status(claim_hygiene.apply(r["probes"]))
    ok = {"t::a": ("passed", "")}
    bad = dr.compare_sides({"main": [ok] * 3, "pr": [{"t::a": ("failed", "boom")}] * 3})
    assert dr.verdict_for(bad, None, probe_results=after)[0] == "needs_attention"


def test_37_claimed_probe_still_flags_unclaimed_difference():
    r = _rec("requests-7586")
    pr = copy.deepcopy(r["probes"])
    for it in pr["items"]:
        if it["source"] == "model":
            it["claims"] = [dict(it["claims"][0], covers=["nothing.matches"])]
            it.update(probes.rejudge_entry(it))
    after = probes.apply_status(claim_hygiene.apply(pr))
    assert not (after.get("claim_hygiene") or {}).get("advisory_probes")
    assert _verdict(after)[0] != "verified"


# ---- 38: "stays the same" claims expect same ---------------------------------------------------------------------

def test_38_will_not_bypass_is_retyped_same_requests_7586():
    r = _rec("requests-7586")
    assert _verdict(probes.apply_status(copy.deepcopy(r["probes"])))[0] != "verified"   # study route unchanged
    after = probes.apply_status(claim_hygiene.apply(r["probes"]))
    assert [d["claim"] for d in after["claim_hygiene"]["retyped_same"]] == ["C4"]
    c4 = [o for it in after["items"] for o in it["observations"] if o.get("claim") == "C4"]
    assert c4 and all(o["label"] == "proven" for o in c4)
    assert _verdict(after)[0] == "verified"


def test_38_retyped_same_claim_fails_closed_when_it_differs():
    r = _rec("requests-7586")
    pr = copy.deepcopy(r["probes"])
    for it in pr["items"]:
        if it["source"] == "model":
            for run in it["runs"]["pr"]:
                run["C4.ipv4_with_port_different_port.match"] = "changed"
    after = probes.apply_status(claim_hygiene.apply(pr))
    labels = {o["label"] for it in after["items"] for o in it["observations"] if o.get("claim") == "C4"}
    assert labels == {"false_claim"}
    assert _verdict(after)[0] == "needs_attention"


def test_38_phrases():
    for t in ["will NOT bypass the proxy", "existing behavior is preserved", "output is unchanged",
              "plain IPs still match", "continues to work as before", "does not affect CIDR"]:
        assert claim_hygiene.says_stays_same(t), t
    for t in ["no longer crashes", "is not merged anymore, it now splits", "now returns a list",
              "parses links with equals signs", "fixes the crash"]:
        assert not claim_hygiene.says_stays_same(t), t


# ---- 39: claims the PR does not make are dropped ------------------------------------------------------------------

def test_39_test_outcome_claims_dropped_rich_4147():
    r = _rec("rich-4147")
    assert _verdict(probes.apply_status(copy.deepcopy(r["probes"])))[0] == "needs_attention"  # study unchanged
    after = probes.apply_status(claim_hygiene.apply(r["probes"]))
    h = after["claim_hygiene"]
    assert sorted(d["claim"] for d in h["dropped_claims"]) == ["C4", "C5"]
    assert sorted(h["dropped_probes"]) == ["model-p3", "model-p4"]
    assert h["dropped_flagged"] == ["model-p3"]
    kept = {c["id"] for it in after["items"] for c in it["claims"]}
    assert kept == {"C2", "C3"}
    # fail closed: the dropped probe had flagged a difference, so the run cannot be verified
    v, reason, _ = _verdict(after)
    assert v == "could_not_verify" and "does not make" in reason


def test_39_phrases():
    for t in ["The regression test covering adjacent tags passes.",
              "Running the test suite for the highlighter results in 84 tests passed.",
              "All tests pass", "CI is green and passes"]:
        assert claim_hygiene.is_test_outcome_claim(t), t
    for t in ["adjacent tags are no longer merged", "a request to port 6000 will NOT bypass the proxy",
              "Existing behavior for non-adjacent tags is preserved."]:
        assert not claim_hygiene.is_test_outcome_claim(t), t


def test_39_hygiene_never_mutates_input_and_is_idempotent():
    r = _rec("rich-4147")
    orig = copy.deepcopy(r["probes"])
    once = claim_hygiene.apply(r["probes"])
    assert r["probes"] == orig
    assert claim_hygiene.apply(once)["items"] == once["items"]


def test_settle_probes_cleans_only_product_records():
    r = _rec("rich-4147")
    study = {"probes": copy.deepcopy(r["probes"])}
    prod = {"probes": copy.deepcopy(r["probes"]), "product_check": True}
    dr.settle_probes(study); dr.settle_probes(prod)
    assert "claim_hygiene" not in study["probes"] and "claim_hygiene_note" not in study
    assert len(study["probes"]["items"]) == 4
    assert "claim_hygiene" in prod["probes"] and prod["claim_hygiene_note"]


# ---- 40: closed or merged pull requests are refused --------------------------------------------------------------

def test_40_closed_pr_refused_requests_7586():
    r = _rec("requests-7586")
    assert r["state"] == "closed"
    why = dr.closed_pr_reason({"state": r["state"]})
    assert why and why.startswith("refused:") and "closed or merged" in why
    assert dr.verdict_for(None, why)[0] == "could_not_verify"
    assert dr.closed_pr_reason({"state": "open"}) is None
    assert dr.closed_pr_reason({"state": "merged"}).startswith("refused:")


def test_40_test_pr_refuses_before_any_run(tmp_path, monkeypatch):
    finished = {}

    def fake_finish(rec, *a):
        finished.update(rec)
        return rec

    def boom(*a, **k):
        raise AssertionError("nothing may run for a closed pull request")

    monkeypatch.setattr(dr, "finish", fake_finish)
    monkeypatch.setattr(dr, "new_record", lambda *a, **k: {})
    monkeypatch.setattr(dr, "begin_pr", lambda a: None)
    monkeypatch.setattr(dr, "test_source_pair", boom)
    from poc import demo_helper
    monkeypatch.setattr(demo_helper, "begin_check", boom)
    a = SimpleNamespace(pr="https://github.com/o/r/pull/1", product_check=True, bench=None)
    item = {"pr": 1, "diff": "", "state": "closed"}
    dr.test_pr("o/r", {"pkg": "r"}, item, tmp_path / "r", tmp_path / "w", a, {})
    assert finished["verdict"] == "could_not_verify"
    assert finished["reason"].startswith("refused:") and finished["pr_state_refusal"]


def test_40_known_answer_case_runs_merged_and_closed_prs(tmp_path, monkeypatch):
    class Reached(Exception):
        pass

    def reached(*a, **k):
        raise Reached

    monkeypatch.setattr(dr, "finish", lambda rec, *a: (_ for _ in ()).throw(AssertionError(rec.get("reason"))))
    monkeypatch.setattr(dr, "new_record", lambda *a, **k: {})
    monkeypatch.setattr(dr, "begin_pr", lambda a: None)
    from poc import demo_helper
    monkeypatch.setattr(demo_helper, "begin_check", reached)
    monkeypatch.setattr(demo_helper, "active", lambda a: True)
    a = SimpleNamespace(pr="https://github.com/o/r/pull/1", product_check=True, bench=None, known_answer_case=True)
    for state in ("closed", "merged"):
        import pytest
        with pytest.raises(Reached):   # went past the state check into the check itself
            dr.test_pr("o/r", {"pkg": "r"}, {"pr": 1, "diff": "", "state": state}, tmp_path / state, tmp_path / "w",
                       a, {})


def test_40_benchmark_runner_marks_its_cases_known_answer(tmp_path):
    from bench import run
    case = {"pr_url": "https://github.com/o/r/pull/1"}
    for arm in run.ARMS:
        cmd = run.command(case, arm, tmp_path, "n")
        assert "--known-answer-case" in cmd and "--product-check" in cmd
    ns = dr.build_parser().parse_args(["--pr", "x", "--product-check"]) if hasattr(dr, "build_parser") else None
    if ns is not None:
        assert ns.known_answer_case is False
