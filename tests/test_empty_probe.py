"""An AI-written probe with no test code is rejected when it is written (and regenerated), never run as a crash."""
import ast

import pytest

from poc import model_probes, model_provider

CLAIM = {"claims": [{"id": "C1", "text": "f changes", "source_quote": "f now changes", "testable": True,
                     "expect": "differs"}]}
GOOD = "import json\nprint(json.dumps({'observations': {'f.a': 1}}))\n"
CLAIMS = [{"id": "C1", "covers": ["f.*"], "expect": "differs"}]


@pytest.mark.parametrize("code", ["", "import json\n", '"""only a docstring"""\nimport os\npass\n...\n',
                                  "# just a comment\nfrom os import path\n"])
def test_code_without_test_statements_is_an_empty_probe(code):
    assert model_probes.validate_probe({"id": "p1", "code": code, "claims": CLAIMS}, {"C1"}) == \
        model_probes.EMPTY_PROBE


def test_real_code_is_not_empty():
    assert model_probes.validate_probe({"id": "p1", "code": GOOD, "claims": CLAIMS}, {"C1"}) is None
    assert model_probes.has_test_code(ast.parse("x = 1\n"))


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


def test_empty_probe_is_regenerated(tmp_path):
    empty = {"id": "p1", "about": "f", "claims": CLAIMS, "code": "import json\n"}
    good = dict(empty, code=GOOD)
    prov = Sequence([[empty], [good]])
    out = _gen(tmp_path, prov)
    assert prov.probe_calls == 2 and "empty probe" in " ".join(out["retried"]["why"])
    assert [p["path"].name for p in out["probes"]] == ["model-p1.py"]
    assert "print(json.dumps" in out["probes"][0]["path"].read_text()


def test_empty_probe_twice_writes_no_probe_file(tmp_path):
    empty = {"id": "p1", "about": "f", "claims": CLAIMS, "code": ""}
    out = _gen(tmp_path, Sequence([[empty], [empty]]))
    assert out["probes"] == []
    assert any("empty probe" in e for e in out["errors"])
