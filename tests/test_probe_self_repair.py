"""Product-check probe rules and probe self-repair (a probe that broke itself is rewritten, at most 2 times).

No model is called: a stub provider answers. The study route must stay exactly as it was."""
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

from ops import daily_run
from poc import freeze, model_probes, model_provider
from poc.probes import PROBE_ERROR

# sha256 of PROBES_PROMPT on main before this change: the study route's instructions must not move.
STUDY_PROMPT_SHA = "851652a00080b1edebedf5a2782004e4927a374e57cad618aa2b75f570030bb7"

OWN = """Traceback (most recent call last):
  File "/x/model-probes/model-probe1.py", line 68, in <module>
    result = asyncio.run(wrapped_func())
  File "/opt/py/lib/python3.14/asyncio/base_events.py", line 774, in time
    return time.monotonic()
  File "/opt/py/lib/python3.14/unittest/mock.py", line 1243, in _execute_mock_call
    result = next(effect)
StopIteration
"""
PROJECT = """Traceback (most recent call last):
  File "/x/model-probes/model-probe1.py", line 5, in <module>
    f()
  File "/work/src/pkg/mod.py", line 9, in f
    raise ValueError("boom")
ValueError: boom
"""
DRAFT = {"id": "probe1", "about": "x", "claims": [], "code": "import json\nprint(json.dumps({'observations': {}}))\n"}


class Stub:
    name = "stub"
    blind = False
    models = {"claims": "m", "probes": "m"}

    def __init__(self, codes=None):
        self.codes = list(codes or [])
        self.seen = []
        self.calls = []

    def describe(self):
        return {"provider": "stub"}

    def complete_json(self, task, system, user, schema, ctx):
        self.seen.append((task, system, user))
        if task == "claims":
            return {"claims": []}
        code = self.codes.pop(0) if self.codes else DRAFT["code"] + "# v%d\n" % len(self.seen)
        return {"probes": [dict(DRAFT, code=code)]}


def _crashed(n=3):
    return {"main": [{PROBE_ERROR: {"crash": "x"}}] * n, "pr": [{PROBE_ERROR: {"crash": "x"}}] * n}


def _setup(tmp_path, logs):
    prdir = tmp_path / "pr"
    (prdir / "model-probes").mkdir(parents=True)
    path = prdir / "model-probes" / "model-probe1.py"
    gen = freeze.generator("model", model="m", provider="stub")
    path.write_text(model_probes.probe_file(DRAFT, "o/r#1", {}, gen["label"]))
    fz = freeze.freeze(path, gen, None)
    for side in ("main", "pr"):
        for i in (1, 2, 3):
            (prdir / f"probe-model-probe1-{side}-{i}.log").write_text(logs[side])
    repair = {"draft": DRAFT, "target": "o/r#1", "claims_by_id": {}, "gen": gen, "inputs": None,
              "ctx": {"repo": "o/r", "pr": 1}}
    return prdir, path, fz, repair


def test_product_prompt_has_rules_and_study_prompt_unchanged():
    r = model_probes.PROBE_SAFETY_RULES
    for words in ("monkeypatch", "time and clock", "asyncio", "random", "os", "iterators", "fake objects",
                  "mocks", "stubs", "real public API", "deterministic function with no limit", "observations"):
        assert words in r
    assert model_probes.PRODUCT_PROBES_PROMPT.startswith(model_provider.PROBES_PROMPT)
    assert r in model_probes.PRODUCT_PROBES_PROMPT and r not in model_provider.PROBES_PROMPT
    assert hashlib.sha256(model_provider.PROBES_PROMPT.encode()).hexdigest() == STUDY_PROMPT_SHA
    assert model_probes.MAX_PROBE_REWRITES == 2


def test_generate_study_route_uses_old_prompt_and_no_repair(tmp_path):
    base = tmp_path / "base"
    base.mkdir()
    (base / "m.py").write_text("def f():\n    return 1\n")
    for product, want in ((False, model_provider.PROBES_PROMPT), (True, model_probes.PRODUCT_PROBES_PROMPT)):
        st = Stub()
        kw = {"product": True} if product else {}
        out = model_probes.generate(st, "o/r", 1, "t", "b", {"m.py": base / "m.py"}, base, [], tmp_path / str(product),
                                    **kw)
        probes_sys = [s for t, s, _ in st.seen if t == "probes"]
        assert probes_sys == [want]
        assert all(("repair" in p) == product for p in out["probes"]) and out["probes"]


def test_plan_probes_passes_product_only_on_product_route(monkeypatch, tmp_path):
    got = []

    def fake(*args, **kw):
        got.append(kw)
        return {"probes": [], "claims": [], "rejected_claims": [], "errors": []}
    monkeypatch.setattr(model_probes, "generate", fake)
    monkeypatch.setattr(daily_run.probes, "find_probes", lambda *a: [])
    item = {"pr": 1, "title": "t", "body": "", "files": {"all": []}, "diff": ""}
    for product in (False, True):
        a = SimpleNamespace(baseline="tests+probes", provider=Stub(), pr=1, bench=None, product_check=product)
        daily_run.plan_probes("o/r", item, {}, tmp_path, [], tmp_path, a)
    assert got == [{}, {"product": True}]


def _a():
    return SimpleNamespace(provider=Stub(), runs=3)


def test_repair_on_own_crash_stops_after_two_rewrites(tmp_path):
    prdir, path, fz, repair = _setup(tmp_path, {"main": OWN, "pr": OWN})
    a, reruns = _a(), []

    def rerun(p, f, ps):
        freeze.verify(p, f, ps)   # the rewrite is frozen before it reruns
        reruns.append(p.read_text())
        return {"id": "model-probe1", "runs": _crashed()}
    it, _, _, _ = daily_run._repair_probe({"id": "model-probe1", "runs": _crashed()}, path, fz, freeze.now(),
                                          repair, prdir, a, rerun)
    assert len(reruns) == 2   # both sides rerun twice: 3 attempts in total
    rep = it["repair"]
    assert [x["attempt"] for x in rep["attempts"]] == [1, 2, 3] and rep["max_attempts"] == 3
    assert "a fake value list ran out" in rep["lines"][0] and "attempt 2 of 3" in rep["lines"][0]
    assert "no rewrites left" in rep["lines"][-1]
    assert (prdir / "probe-repair" / "attempt1" / "model-probe1.py").is_file()


def test_repair_success_records_ran(tmp_path):
    prdir, path, fz, repair = _setup(tmp_path, {"main": OWN, "pr": OWN})
    it, *_ = daily_run._repair_probe({"id": "model-probe1", "runs": _crashed()}, path, fz, freeze.now(), repair,
                                     prdir, _a(), lambda p, f, ps: {"id": "model-probe1",
                                                                    "runs": {"main": [{"v": 1}], "pr": [{"v": 1}]}})
    assert it["repair"]["attempts"][-1] == {"attempt": 2, "outcome": "ran"}


def _never(*a):
    raise AssertionError("must not rerun")


def test_project_code_crash_is_not_repaired(tmp_path):
    prdir, path, fz, repair = _setup(tmp_path, {"main": PROJECT, "pr": PROJECT})
    a = _a()
    it, *_ = daily_run._repair_probe({"id": "model-probe1", "runs": _crashed()}, path, fz, freeze.now(), repair,
                                     prdir, a, _never)
    assert "repair" not in it and a.provider.seen == []


def test_pr_side_only_crash_is_not_repaired(tmp_path):
    prdir, path, fz, repair = _setup(tmp_path, {"main": "", "pr": OWN})
    runs = {"main": [{"v": 1}] * 3, "pr": [{PROBE_ERROR: {"crash": "x"}}] * 3}
    a = _a()
    it, *_ = daily_run._repair_probe({"id": "model-probe1", "runs": runs}, path, fz, freeze.now(), repair, prdir,
                                     a, _never)
    assert "repair" not in it and a.provider.seen == []
    assert not model_probes.probe_broke_itself({"runs": runs}, {"main": [OWN] * 3, "pr": [OWN] * 3}, "model-probe1.py")


def test_rewrite_prompt_has_only_source_and_error(tmp_path):
    st = Stub()
    repair = {"draft": DRAFT, "claims_by_id": {}, "ctx": {"repo": "o/r", "pr": 1}}
    new = model_probes.rewrite_probe(st, repair, "SOURCE-TEXT", "ERROR-TEXT")
    assert new is not None
    task, system, user = st.seen[0]
    assert system == model_probes.REPAIR_PROMPT
    assert user == "Probe source:\nSOURCE-TEXT\n\nIts error text:\nERROR-TEXT"
    # the repair loop hands it the error text only, never observations
    err = model_probes.error_summary({"main": [OWN], "pr": [OWN]})
    assert "observations" not in err and err.startswith("Traceback")
    assert json.dumps(_crashed()) not in err
