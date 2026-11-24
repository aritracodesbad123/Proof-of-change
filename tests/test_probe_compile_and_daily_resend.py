"""A probe that does not compile is rejected and regenerated, and a daily run resends a crash once."""
import ast
from types import SimpleNamespace

from ops import daily_run
from poc import model_probes, model_provider

CLAIM = {"claims": [{"id": "C1", "text": "f changes", "source_quote": "f now changes", "testable": True,
                     "expect": "differs"}]}
CLAIMS = [{"id": "C1", "covers": ["f.*"], "expect": "differs"}]
GOOD = "import json\nprint(json.dumps({'observations': {'f.a': 1}}))\n"
NONLOCAL = "nonlocal row\nrow = 1\nprint(row)\n"


def test_module_level_nonlocal_parses_and_does_not_compile():
    ast.parse(NONLOCAL)
    why = model_probes.validate_probe({"id": "p1", "code": NONLOCAL, "claims": CLAIMS}, {"C1"})
    assert why and why.startswith("code does not compile:")
    assert "nonlocal" in why
    assert model_probes.validate_probe({"id": "p1", "code": GOOD, "claims": CLAIMS}, {"C1"}) is None


class Sequence(model_provider.Provider):
    name = "sequence"

    def __init__(self, answers):
        super().__init__()
        self.answers = list(answers)
        self.probe_calls = 0

    def complete_json(self, task, system, user, schema, ctx):
        if task == "claims":
            return CLAIM
        self.probe_calls += 1
        return {"probes": self.answers.pop(0)}


def _gen(tmp_path, provider):
    base = tmp_path / "base"
    (base / "pkg").mkdir(parents=True)
    (base / "pkg" / "m.py").write_text("def f(x):\n    return x\n")
    return model_probes.generate(provider, "o/r", 1, "Change f", "f now changes",
                                 {"pkg/m.py": base / "pkg" / "m.py"}, base, [tmp_path / "pr"], tmp_path / "out")


def test_a_probe_that_does_not_compile_is_regenerated_once(tmp_path):
    bad = {"id": "p1", "about": "f", "claims": CLAIMS, "code": NONLOCAL}
    good = dict(bad, code=GOOD)
    prov = Sequence([[bad], [good]])
    out = _gen(tmp_path, prov)
    assert prov.probe_calls == 2
    assert any("does not compile" in str(why) for why in out["retried"]["why"])
    assert [p["path"].name for p in out["probes"]] == ["model-p1.py"]
    assert "nonlocal" not in out["probes"][0]["path"].read_text()


def test_a_probe_that_still_does_not_compile_is_not_written(tmp_path):
    bad = {"id": "p1", "about": "f", "claims": CLAIMS, "code": NONLOCAL}
    out = _gen(tmp_path, Sequence([[bad], [bad]]))
    assert out["probes"] == []
    assert any("does not compile" in e for e in out["errors"])


def test_daily_run_resends_a_crashed_probe_and_a_study_run_does_not():
    provider = object()
    daily = SimpleNamespace(provider=provider, pr=None, bench=None, product_check=False)
    product = SimpleNamespace(provider=provider, pr="https://github.com/acme/widgets/pull/4",
                              bench=None, product_check=True)
    study = SimpleNamespace(provider=provider, pr="https://github.com/acme/widgets/pull/4",
                            bench="pairs.csv", product_check=True)
    one_off = SimpleNamespace(provider=provider, pr="https://github.com/acme/widgets/pull/4",
                              bench=None, product_check=False)
    assert daily_run.resend_crashed_probes(daily)
    assert daily_run.resend_crashed_probes(product)
    assert not daily_run.resend_crashed_probes(study)
    assert not daily_run.resend_crashed_probes(one_off)
    assert not daily_run.resend_crashed_probes(SimpleNamespace(provider=None, pr=None, bench=None))


def test_run_probes_uses_the_daily_resend_gate():
    import inspect
    src = inspect.getsource(daily_run.run_probes)
    assert "resend_crashed_probes(a)" in src
    assert "rewrite_crashed_probes" in src
