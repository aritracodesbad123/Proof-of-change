"""Model-written probes, the probe freeze rule, differential probes, baselines and blind scoring.

No model is called here: the recorded provider answers from TEST FIXTURES (evals/fixtures/model_responses), and the
Nebius provider is checked against a stubbed HTTP call."""
import copy
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from evals import ablation, pr_metrics
from guardrails import isolation as iso
from guardrails import sandbox
from ops import daily_run
from poc import diff_probes, freeze, model_probes, model_provider, probes

REPO = Path(__file__).resolve().parent.parent
GOLDEN = json.loads((REPO / "evals/fixtures/golden_pr_v1.jsonl").read_text().splitlines()[0])
BODY = ("Each group is now permuted by applying one row permutation to all of its columns. "
        "For integer groups the results don't change, so those results don't change for a given seed.")
TITLE = "Fix feature_importance_permutation permuting the wrong columns for feature_groups"
SIMPLE = ('PROBE = {"id": "simple", "target": "o/r#1", "about": "x", "claims": []}\n'
          'import json\nprint(json.dumps({"observations": {"v": 1}}))\n')


@pytest.fixture
def no_sandbox():
    sandbox.configure(False)
    yield
    sandbox.configure(True)


def _fake_venv(root: Path, side: str) -> Path:
    py = root / f"venv-{side}" / "bin" / "python"
    py.parent.mkdir(parents=True)
    py.write_text(f"#!{sys.executable}\nimport os, sys\nos.execv(sys.executable, [sys.executable, *sys.argv[1:]])\n")
    py.chmod(0o755)
    return py


def _frozen(path: Path, kind="fixed", **kw) -> dict:
    return {"path": path, "source": {"fixed": "library"}.get(kind, kind), "freeze": freeze.freeze(path, freeze.generator(kind, **kw), None)}


# ---------------------------------------------------------------- freeze rule
def test_tamper_after_freeze_is_detected(tmp_path):
    p = tmp_path / "p.py"
    p.write_text(SIMPLE)
    fz = freeze.freeze(p, freeze.generator("fixed"), None)
    time.sleep(0.01)
    start = freeze.now()
    freeze.verify(p, fz, start)                                   # unchanged: passes
    p.write_text(SIMPLE + "# edited\n")
    with pytest.raises(freeze.FreezeError, match="content changed after freezing"):
        freeze.verify(p, fz, start)


def test_probe_frozen_after_pr_side_start_is_refused(tmp_path):
    p = tmp_path / "p.py"
    p.write_text(SIMPLE)
    start = freeze.now()
    time.sleep(0.01)
    fz = freeze.freeze(p, freeze.generator("fixed"), None)
    with pytest.raises(freeze.FreezeError, match="after PR-side execution started"):
        freeze.verify(p, fz, start)
    with pytest.raises(freeze.FreezeError, match="never frozen"):
        freeze.verify(p, None, start)
    with pytest.raises(freeze.FreezeError, match="start time unknown"):
        freeze.verify(p, fz, None)


def test_file_rewritten_after_pr_side_start_is_refused_even_with_same_content(tmp_path):
    p = tmp_path / "p.py"
    p.write_text(SIMPLE)
    fz = freeze.freeze(p, freeze.generator("fixed"), None)
    time.sleep(0.01)
    start = freeze.now()
    time.sleep(0.01)
    p.write_text(SIMPLE)                                          # same bytes, written after the PR side started
    with pytest.raises(freeze.FreezeError, match="written after PR-side execution started"):
        freeze.verify(p, fz, start)


def test_generator_inputs_from_the_pr_head_are_rejected(tmp_path):
    base, pr = tmp_path / "side-main", tmp_path / "side-pr"
    for d in (base, pr):
        (d / "pkg").mkdir(parents=True)
        (d / "pkg" / "m.py").write_text("def f(x):\n    return x\n")
    ok = freeze.base_inputs("t", "b", {"pkg/m.py": base / "pkg/m.py"}, base, [pr])
    assert list(ok["base_files"]) == ["pkg/m.py"]
    with pytest.raises(freeze.FreezeError, match="PR-side path"):
        freeze.base_inputs("t", "b", {"pkg/m.py": pr / "pkg/m.py"}, base, [pr])
    with pytest.raises(freeze.FreezeError, match="not under the base-side root"):
        freeze.check_inputs([tmp_path / "elsewhere.py"], base, [pr])
    nested = tmp_path / "work"                                    # source build: PR source inside the work dir
    with pytest.raises(freeze.FreezeError, match="PR-side path"):
        freeze.check_inputs([nested / "src" / "x.py"], nested, [nested / "src"])
    prov, _ = model_provider.select("recorded")
    with pytest.raises(freeze.FreezeError):                       # the generator itself refuses PR-head inputs
        model_probes.generate(prov, "rasbt/mlxtend", 1229, TITLE, BODY, {"pkg/m.py": pr / "pkg/m.py"}, base, [pr],
                              tmp_path / "out")
    with pytest.raises(freeze.FreezeError):
        diff_probes.derive("diff --git a/pkg/m.py b/pkg/m.py\n--- a/pkg/m.py\n+++ b/pkg/m.py\n@@ -1,2 +1,2 @@\n",
                           ["pkg/m.py"], pr, [pr])


def test_runner_refuses_tampered_and_late_probes_on_the_pr_side(no_sandbox, tmp_path, monkeypatch):
    work, prdir = tmp_path / "work", tmp_path / "run"
    prdir.mkdir()
    pythons = {s: _fake_venv(work, s) for s in ("main", "pr")}
    monkeypatch.setattr(daily_run, "repo_relative", lambda p: str(p))
    good, tampered, late = (tmp_path / f"{n}.py" for n in ("good", "tampered", "late"))
    for p, n in ((good, "good"), (tampered, "tampered"), (late, "late")):
        p.write_text(SIMPLE.replace('"simple"', f'"{n}"'))
    plan = [_frozen(good), _frozen(tampered)]
    tampered.write_text(tampered.read_text() + "x = 1\n")
    time.sleep(0.01)
    start = freeze.now()
    time.sleep(0.01)
    plan.append(_frozen(late))
    res = daily_run.run_probes("o/r", 1, pythons, prdir, work, type("A", (), {"runs": 1})(), plan, start)
    assert [it["id"] for it in res["items"]] == ["good"]
    assert res["items"][0]["freeze"]["verified"] is True
    assert sorted(x["path"] for x in res["refused"]) == ["late.py", "tampered.py"]
    assert not list(prdir.glob("probe-tampered-*")) and not list(prdir.glob("probe-late-*"))   # never ran


def test_probe_that_rewrites_itself_on_the_main_side_is_stopped_before_the_pr_side(no_sandbox, tmp_path, monkeypatch):
    """The guard runs before EVERY PR-side run (inside the sandbox the probe file is also read-only)."""
    work, prdir = tmp_path / "work", tmp_path / "run"
    prdir.mkdir()
    pythons = {s: _fake_venv(work, s) for s in ("main", "pr")}
    monkeypatch.setattr(daily_run, "repo_relative", lambda p: str(p))
    p = tmp_path / "self.py"
    p.write_text('PROBE = {"id": "self", "target": "o/r#1", "about": "x", "claims": []}\n'
                 f'import json\nopen({str(p)!r}, "a").write("# changed\\n")\n'
                 'print(json.dumps({"observations": {"v": 1}}))\n')
    plan = [_frozen(p)]
    time.sleep(0.01)
    res = daily_run.run_probes("o/r", 1, pythons, prdir, work, type("A", (), {"runs": 1})(), plan, freeze.now())
    assert res["items"] == [] and "content changed" in res["refused"][0]["why"]
    assert not list(prdir.glob("probe-self-pr-*"))


def test_fixed_probes_are_post_hoc_and_never_blind():
    spec = probes.read_spec(REPO / "probes/rasbt/mlxtend/1229.py")
    assert spec["provenance"] == "post-hoc"
    g = freeze.generator("fixed", provenance=spec["provenance"])
    assert g["label"] == "fixed (post-hoc, written after results were known)" and g["blind"] is False
    assert freeze.generator("fixed")["provenance"] == "post-hoc"            # missing field: post-hoc
    assert freeze.generator("fixed", provenance="pre-registered")["blind"] is False


# ---------------------------------------------------------------- providers
def test_provider_selection_and_fallback():
    assert model_provider.select("none", env={})[0] is None
    prov, note = model_provider.select("nebius", env={})
    assert prov is None and "NEBIUS_API_KEY is not set: fixed probes only" in note
    prov, note = model_provider.select("nebius", env={"NEBIUS_API_KEY": "k"})
    assert prov.name == "nebius" and prov.blind and prov.models["claims"] == "nvidia/nemotron-3-super-120b-a12b"
    prov, note = model_provider.select("recorded", env={})
    assert prov.name == "recorded" and not prov.blind and "TEST FIXTURE" in note
    custom, _ = model_provider.select("nebius", env={"NEBIUS_API_KEY": "k"}, models={"probes": "nvidia/other"})
    assert custom.models == {**model_provider.DEFAULT_MODELS, "probes": "nvidia/other"}


def test_nebius_request_uses_structured_output_and_keeps_the_key_in_the_header(monkeypatch):
    seen = {}

    class Resp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return json.dumps({"choices": [{"message": {"content": json.dumps({"claims": []})}}]}).encode()

    def fake_urlopen(req, timeout):
        seen["url"], seen["body"], seen["headers"] = req.full_url, json.loads(req.data), dict(req.header_items())
        return Resp()
    monkeypatch.setattr(model_provider.urllib.request, "urlopen", fake_urlopen)
    prov = model_provider.NebiusProvider("secret-key")
    assert prov.complete_json("claims", "s", "u", model_provider.CLAIMS_SCHEMA, {}) == {"claims": []}
    assert seen["url"] == "https://api.tokenfactory.nebius.com/v1/chat/completions"
    assert seen["body"]["response_format"]["type"] == "json_schema"
    assert seen["body"]["response_format"]["json_schema"]["schema"] == model_provider.CLAIMS_SCHEMA
    assert seen["body"]["model"] == "nvidia/nemotron-3-super-120b-a12b" and seen["body"]["temperature"] == 0
    assert seen["headers"]["Authorization"] == "Bearer secret-key" and "secret-key" not in json.dumps(seen["body"])

    def boom(req, timeout):
        raise OSError("down secret-key")
    monkeypatch.setattr(model_provider.urllib.request, "urlopen", boom)
    with pytest.raises(model_provider.ProviderError) as e:
        prov.complete_json("claims", "s", "u", model_provider.CLAIMS_SCHEMA, {})
    assert "secret-key" not in str(e.value)


def test_nebius_key_is_not_allowlisted_for_untrusted_processes(monkeypatch, tmp_path):
    monkeypatch.setenv("NEBIUS_API_KEY", "fake")
    for install in (False, True):
        env = iso.untrusted_env(tmp_path, install=install)
        assert "NEBIUS_API_KEY" not in env and "fake" not in env.values()
    assert iso.SECRET_NAME.search("NEBIUS_API_KEY")
    with pytest.raises(iso.UnsafeEnv):
        iso.check_allowlist(iso.INSTALL_ALLOWLIST | {"NEBIUS_API_KEY"})


def test_recorded_fixtures_are_labelled_test_fixtures(tmp_path):
    for f in (REPO / "evals/fixtures/model_responses").rglob("*.json"):
        assert "TEST FIXTURE" in json.loads(f.read_text())["_fixture"], f
    bad = tmp_path / "o" / "r"
    bad.mkdir(parents=True)
    (bad / "1.json").write_text(json.dumps({"claims": {"claims": []}}))
    prov = model_provider.RecordedProvider(tmp_path)
    with pytest.raises(model_provider.ProviderError, match="not labelled"):
        prov.complete_json("claims", "", "", {}, {"repo": "o/r", "pr": 1})


def test_recorded_provider_writes_frozen_non_blind_probes(tmp_path):
    base = tmp_path / "side-main"
    (base / "mlxtend/evaluate").mkdir(parents=True)
    (base / "mlxtend/evaluate/feature_importance.py").write_text("def feature_importance_permutation():\n    pass\n")
    prov, _ = model_provider.select("recorded")
    res = model_probes.generate(prov, "rasbt/mlxtend", 1229, TITLE, BODY,
                                {"mlxtend/evaluate/feature_importance.py": base / "mlxtend/evaluate/feature_importance.py"},
                                base, [tmp_path / "side-pr"], tmp_path / "out")
    assert res["errors"] == [] and [c["id"] for c in res["claims"]] == ["C1", "C2"]
    (x,) = res["probes"]
    spec = probes.read_spec(x["path"])
    assert spec["id"] == "model-groups-columns" and spec["timeout_s"] == model_probes.MODEL_TIMEOUT_S
    assert spec["generator"] == "model (recorded fixture, not blind)"
    g = x["freeze"]["generator"]
    assert g["kind"] == "model" and g["provider"] == "recorded" and g["blind"] is False
    assert g["model"] == "recorded-fixture" and x["freeze"]["inputs_sha256"]
    assert list(x["freeze"]["inputs"]["base_files"]) == ["mlxtend/evaluate/feature_importance.py"]
    assert not freeze.is_blind({"freeze": x["freeze"] | {"verified": True}})


def test_ungrounded_claims_and_bad_probe_code_are_rejected():
    raw = {"claims": [{"id": "C1", "text": "t", "source_quote": "applying one row permutation", "testable": True,
                       "expect": "differs"},
                      {"id": "C2", "text": "t", "source_quote": "this sentence is not in the PR", "testable": True,
                       "expect": "same"}]}
    kept, rejected = model_probes.grounded_claims(raw, TITLE, BODY)
    assert [c["id"] for c in kept] == ["C1"] and rejected[0]["id"] == "C2"
    ok = {"id": "p", "about": "", "claims": [{"id": "C1", "covers": ["a.*"], "expect": "differs"}], "code": "print(1)"}
    assert model_probes.validate_probe(ok, {"C1"}) is None
    assert "does not parse" in model_probes.validate_probe(ok | {"code": "def ("}, {"C1"})
    assert "too long" in model_probes.validate_probe(ok | {"code": "x=1\n" * 10_000}, {"C1"})
    assert "PROBE itself" in model_probes.validate_probe(ok | {"code": "PROBE = {}"}, {"C1"})
    assert "not one of the extracted" in model_probes.validate_probe(ok, {"C9"})
    assert "bad probe id" in model_probes.validate_probe(ok | {"id": "../x"}, {"C1"})
    assert "covers no observation" in model_probes.validate_probe(
        ok | {"claims": [{"id": "C1", "covers": [], "expect": "same"}]}, {"C1"})


def test_probe_output_contract_and_size_cap():
    big = json.dumps({"observations": {"a": "x" * (probes.MAX_OUTPUT_BYTES + 10)}})
    assert "contract" in probes.observations_of(big, 0)[probes.PROBE_ERROR]
    many = json.dumps({"observations": {f"o{i}": i for i in range(probes.MAX_OBSERVATIONS + 1)}})
    assert "contract" in probes.observations_of(many, 0)[probes.PROBE_ERROR]
    assert probes.observations_of(json.dumps({"observations": {"a": 1}}), 0) == {"a": 1}


def test_probe_timeout_is_capped(tmp_path):
    p = tmp_path / "t.py"
    p.write_text('PROBE = {"id": "t", "target": "o/r#1", "about": "x", "claims": [], "timeout_s": 99999}\n')
    assert probes.read_spec(p)["timeout_s"] == probes.MAX_TIMEOUT


def test_huge_probe_output_does_not_fill_memory(tmp_path):
    p = tmp_path / "loud.py"
    p.write_text('PROBE = {"id": "loud", "target": "o/r#1", "about": "x", "claims": []}\n'
                 'import sys\nsys.stdout.write("x" * 5_000_000)\n')
    obs, log, _ = probes.run_once(p, Path(sys.executable), tmp_path, {"PATH": os.environ["PATH"]}, 30)
    assert "contract" in obs[probes.PROBE_ERROR] and len(log) < 10_000


# ---------------------------------------------------------------- differential probes
DIFF = """diff --git a/pkg/m.py b/pkg/m.py
--- a/pkg/m.py
+++ b/pkg/m.py
@@ -4,2 +4,2 @@ def scale(x):
-    return x * 2
+    return x * 3
"""


def _toy(root: Path, factor: int) -> Path:
    (root / "pkg").mkdir(parents=True)
    (root / "pkg/__init__.py").write_text("")
    (root / "pkg/m.py").write_text(f"def helper():\n    return 1\n\ndef scale(x):\n    return x * {factor}\n\n"
                                   "def _private(x):\n    return x\n")
    return root


def test_diff_probe_targets_touched_public_functions_from_base_code(tmp_path):
    assert diff_probes.old_ranges(DIFF) == {"pkg/m.py": [(4, 5)]}
    assert diff_probes.module_name("src/pkg/sub/m.py") == "pkg.sub.m"
    assert diff_probes.module_name("pkg/_internal/m.py") is None
    base = _toy(tmp_path / "base", 2)
    d = diff_probes.derive(DIFF, ["pkg/m.py", "pkg/tests/test_m.py"], base, [tmp_path / "pr"])
    assert d["targets"] == [("pkg.m", "scale")]
    assert d["inputs"]["old_ranges"] == {"pkg/m.py": [(4, 5)]} and list(d["inputs"]["base_files"]) == ["pkg/m.py"]


def test_diff_probe_finds_a_behaviour_change(tmp_path):
    base, pr = _toy(tmp_path / "base", 2), _toy(tmp_path / "pr", 3)
    d = diff_probes.derive(DIFF, ["pkg/m.py"], base, [pr])
    path = diff_probes.write(d["targets"], tmp_path / "diff-api.py", "o/r#1")
    spec = probes.read_spec(path)
    assert spec["claims"] == [] and spec["generator"] == freeze.DIFF
    runs = {}
    for side, root in (("main", base), ("pr", pr)):
        out = subprocess.run([sys.executable, str(path)], capture_output=True, text=True, cwd=tmp_path,
                             env={"PATH": os.environ["PATH"], "PYTHONPATH": str(root)}).stdout
        runs[side] = [probes.observations_of(out, 0)] * 3
    obs = {o["name"]: o for o in probes.judge(spec, runs)}
    assert obs["pkg.m.scale.input0"]["main"] == 2 and obs["pkg.m.scale.input0"]["pr"] == 3
    assert obs["pkg.m.scale.input0"]["label"] == "unmentioned"
    assert obs["pkg.m.scale.input6"]["main"] == {"raises": "TypeError"}         # None * 2
    assert obs["pkg.m.scale.input6"]["label"] == "no_difference"


# ---------------------------------------------------------------- baselines
def _diff_item(main, pr):
    spec = {"id": "diff-api", "target": "o/r#1", "about": "", "claims": []}
    it = probes.entry(spec, {"main": [main] * 3, "pr": [pr] * 3}, {"main": ["m"], "pr": ["p"]}, [], "diff", None)
    it["generator"] = freeze.generator("diff")
    return it


def test_verdict_by_baseline_on_the_known_answer_case():
    rec = copy.deepcopy(GOLDEN)
    pp = daily_run.rejudge_probes(rec["probes"])
    args = (rec["comparison"], None, rec["exit_check"], rec["files"])
    got = {b: daily_run.verdict_for(*args, pp, rec.get("behaviour_claims"), b)[0] for b in daily_run.BASELINES}
    assert got == {"tests": "verified", "tests+diff": "verified", "tests+probes": "needs_attention",
                   "full": "needs_attention"}
    with_diff = dict(pp, items=pp["items"] + [_diff_item({"f.input0": 2}, {"f.input0": 3})])
    assert daily_run.verdict_for(*args, with_diff, None, "tests+diff")[0] == "needs_attention"
    assert daily_run.verdict_for(*args, with_diff, None, "tests")[0] == "verified"
    only_diff = {"status": "ran", "items": [_diff_item({"f.input0": 2}, {"f.input0": 3})]}
    assert daily_run.verdict_for(*args, only_diff, None, "full")[0] == "verified"   # informational under full


def test_claim_flags_and_coverage_gate_only_in_full():
    rec = copy.deepcopy(GOLDEN)
    claims = [{"source": "description", "quote": "results don't change for a given seed", "pattern": "x"}]
    args = (rec["comparison"], None, rec["exit_check"], rec["files"], None, claims)
    assert daily_run.verdict_for(*args, "full")[0] == "could_not_verify"
    assert daily_run.verdict_for(*args, "tests")[0] == "verified"
    assert daily_run.verdict_for(*args, "tests+probes")[0] == "verified"
    r = {"verdict": "verified", "reason": "x", "baseline": "tests"}
    assert daily_run.gate(r) is r
    a = type("A", (), {"baseline": "tests+probes", "no_coverage": False})()
    assert daily_run.coverage_run({"files": {}}, None, None, None, [], None, None, a)["status"] == "skipped"


def test_baseline_flag_and_default(monkeypatch):
    import argparse
    seen = {}
    real = argparse.ArgumentParser.parse_args

    def spy(self, args=None, namespace=None):
        ns = real(self, args, namespace)
        seen.update(baseline=ns.baseline, provider=ns.model_provider)
        raise SystemExit(0)
    monkeypatch.setattr(argparse.ArgumentParser, "parse_args", spy)
    with pytest.raises(SystemExit):
        daily_run.main(["--select-only"])
    assert seen == {"baseline": "full", "provider": "nebius"}
    with pytest.raises(SystemExit):
        daily_run.main(["--select-only", "--baseline", "tests+diff", "--model-provider", "recorded"])
    assert seen == {"baseline": "tests+diff", "provider": "recorded"}


def test_record_carries_baseline_and_provider_and_validates(monkeypatch):
    a = type("A", (), {"runs": 3, "workers": "4", "test_timeout": 1, "run_timeout": 1, "build_timeout": 1,
                       "python": "3.12", "baseline": "tests+probes", "model_provider": "nebius", "provider": None,
                       "model_note": "model provider: nebius requested but NEBIUS_API_KEY is not set: fixed probes only"})()
    item = {"pr": 1, "head_sha": "a" * 40, "url": "u", "title": "t", "body": "results unchanged", "base_ref": "main",
            "author": "x", "updated_at_utc": "", "updated_at_ist": "", "ci_state": "", "ci_detail": "",
            "files": {"package_py": [], "compiled": [], "other": []}}
    rec = daily_run.new_record("o/r", {"dist": "r", "pkg": "r"}, item, a, {}, "2026-10-11")
    assert rec["baseline"] == "tests+probes" and rec["behaviour_claims"] == []   # claim flags: full only
    assert rec["model_provider"] == {"requested": "nebius", "used": None, "note": a.model_note, "blind": False}


# ---------------------------------------------------------------- blind scoring
def _rec(rid, verdict, items, baseline="full", repo="psf/requests", pr=6655):
    return {"id": rid, "verdict": verdict, "baseline": baseline, "pr": {"repo": repo, "number": pr},
            "probes": {"status": "ran" if items else "none", "items": items}}


def _item(gen, verified=True, source="model"):
    return {"id": "p", "source": source, "observations": [], "generator": gen,
            "freeze": {"generator": gen, "verified": verified, "sha256": "0" * 64, "frozen_at": "x"}}


LIVE = freeze.generator("model", model="nvidia/nemotron-3-super-120b-a12b", provider="nebius")
RECORDED = freeze.generator("model", model="recorded-fixture", provider="recorded")
POST_HOC = freeze.generator("fixed", provenance="post-hoc")


def test_blind_scoring_rejects_recorded_fixture_and_post_hoc_probes():
    cases = pr_metrics.load_cases()
    for gen, src in ((RECORDED, "model"), (POST_HOC, "library")):
        with pytest.raises(pr_metrics.NotBlind):
            pr_metrics.blind_score(cases, [_rec("r", "needs_attention", [_item(gen, source=src)])])
    with pytest.raises(pr_metrics.NotBlind):                       # live, but failed the freeze rule
        pr_metrics.blind_score(cases, [_rec("r", "needs_attention", [_item(LIVE, verified=False)])])
    with pytest.raises(pr_metrics.NotBlind):                       # an old record: fixed probe, no generator
        pr_metrics.blind_score(cases, [GOLDEN])
    s = pr_metrics.blind_score(cases, [_rec("r", "needs_attention", [_item(LIVE)])])
    assert s["caught"] == ["requests-6655"]
    assert pr_metrics.blind_score(cases, [_rec("r", "verified", [])])["caught"] == []   # no probes: blind
    # a non-blind probe that cannot decide under the baseline does not make the verdict non-blind
    assert pr_metrics.record_is_blind(_rec("r", "verified", [_item(POST_HOC, source="library")], baseline="tests"))
    assert not pr_metrics.record_is_blind(_rec("r", "verified", [_item(freeze.generator("diff"), source="diff")],
                                               baseline="tests+diff"))


def test_score_records_keeps_non_blind_in_a_separate_labelled_column():
    cases = pr_metrics.load_cases()
    s = pr_metrics.score_records(cases, [_rec("a", "needs_attention", [_item(RECORDED)]),
                                         _rec("b", "needs_attention", [_item(LIVE)], pr=1, repo="x/y")])
    assert s["blind"]["caught"] == [] and s["not_blind"]["caught"] == ["requests-6655"]
    assert s["not_blind"]["label"].startswith("NOT BLIND") and "a" in s["not_blind"]["records"]


def test_ablation_table(tmp_path):
    for b, v, items in (("tests", "verified", []), ("tests+probes", "needs_attention", [_item(RECORDED)]),
                        ("full", "needs_attention", [_item(LIVE)])):
        (tmp_path / b).mkdir()
        (tmp_path / b / "records.jsonl").write_text(json.dumps(_rec(f"r-{b}", v, items, baseline=b)) + "\n")
    assert ablation.main(["--records-root", str(tmp_path)]) == 0
    out = json.loads((tmp_path / "ablation.json").read_text())
    rows = {r["baseline"]: r for r in out["rows"]}
    assert rows["tests"]["blind"]["catch"] == "0/1" and rows["full"]["blind"]["catch"] == "1/1"
    assert rows["tests+probes"]["blind"]["catch"] == "n/a" and rows["tests+probes"]["not_blind"]["catch"] == "1/1"
    assert rows["tests"]["blind"]["could_not_verify"] == "0/1"
    md = (tmp_path / "ablation.md").read_text()
    assert "NOT BLIND" in md and "| tests+probes | 1 (1) | n/a | n/a | n/a | 1 (1), 1/1," in md
    unl = tmp_path / "unl"
    (unl / "full").mkdir(parents=True)                      # an unlabelled PR is counted, never scored
    (unl / "full" / "records.jsonl").write_text(json.dumps(_rec("u", "needs_attention", [], repo="o/r", pr=1)) + "\n")
    ablation.main(["--records-root", str(unl)])
    r = json.loads((unl / "ablation.json").read_text())["rows"][0]["blind"]
    assert r["unlabelled"] == 1 and r["catch"] == "n/a"


def test_src_layout_files_count_as_package_code():
    f = daily_run.classify_files(["src/marshmallow/utils.py", "tests/test_utils.py", "README.md"], "marshmallow")
    assert f["package_py"] == ["src/marshmallow/utils.py"] and f["other"] == ["tests/test_utils.py", "README.md"]
    assert daily_run.classify_files(["pandas/core/x.py"], "pandas")["package_py"] == ["pandas/core/x.py"]


def test_pep735_test_dependency_groups_are_installed(tmp_path):
    (tmp_path / "pyproject.toml").write_text(
        '[dependency-groups]\ntests = ["pytest", "simplejson", "--index-url=http://x"]\n'
        'docs = ["sphinx"]\ntest = [{include-group = "tests"}, "hypothesis"]\n')
    assert daily_run.pyproject_test_groups(tmp_path) == ["pytest", "simplejson", "hypothesis"]
    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n")
    assert daily_run.pyproject_test_groups(tmp_path) == []


def test_xdist_collection_mismatch_reruns_serially(tmp_path, monkeypatch):
    calls = []

    def fake_run(cmd, log, **kw):
        calls.append(list(map(str, cmd)))
        with open(log, "a") as fh:
            fh.write("ERROR gw1 - Different tests were collected between gw0 and gw1\n" if "-n" in calls[-1]
                     else "3 passed in 0.1s\n")
        return (1 if "-n" in calls[-1] else 0), 0.1

    monkeypatch.setattr(daily_run, "run", fake_run)
    venvs = {s: tmp_path / f"venv-{s}" for s in ("main", "pr")}
    for v in venvs.values():
        v.mkdir()
    per_run, _ = daily_run.run_tests(venvs, {"main": ["t.py"], "pr": ["t.py"]}, tmp_path, tmp_path, 1, "4", 60, 60,
                                     cwds={"main": tmp_path, "pr": tmp_path})
    assert [("-n" in c) for c in calls] == [True, False, True, False]
    assert all(e["exit"] == 0 and e["pytest_summary"] == "3 passed in 0.1s" for e in per_run)
