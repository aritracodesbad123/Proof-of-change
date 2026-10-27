"""Product checks: model-written probes import the installed package (not a src/ layout folder), and a probe whose
last line is a Python literal of the observations object is read safely. Study runs stay exactly as before."""
import json
import types
from pathlib import Path

import pytest

from ops import daily_run
from poc import model_probes, model_provider, probes
from poc.probes import PROBE_ERROR

TITLE = "Fix the parser"
BODY = "The parser now returns an empty list for empty input."


def _src_layout(root: Path, *names: str) -> Path:
    for n in names:
        (root / "src" / n).mkdir(parents=True)
        (root / "src" / n / "__init__.py").write_text("def parse(x):\n    return x\n")
    return root


# ---------------------------------------------------------------- src layout imports
def test_src_packages_only_for_a_src_layout(tmp_path):
    assert model_probes.src_packages(tmp_path) == set()
    _src_layout(tmp_path, "pkg", "other")
    (tmp_path / "src" / "single.py").write_text("x = 1\n")
    assert model_probes.src_packages(tmp_path) == {"pkg", "other", "single"}
    (tmp_path / "src" / "__init__.py").write_text("")   # src is itself a package: not a layout folder
    assert model_probes.src_packages(tmp_path) == set()


@pytest.mark.parametrize("code,want", [
    ("from src.pkg import parse\nprint(parse(1))\n", "from pkg import parse\nprint(parse(1))\n"),
    ("from src.pkg.sub import a as b, c\n", "from pkg.sub import a as b, c\n"),
    ("from src import pkg\npkg.parse(1)\n", "import pkg\npkg.parse(1)\n"),
    ("import src.pkg.sub as m\nm.f()\n", "import pkg.sub as m\nm.f()\n"),
    ("try:\n    from src.pkg import parse\nexcept ImportError:\n    parse = None\n",
     "try:\n    from pkg import parse\nexcept ImportError:\n    parse = None\n"),
    ("from src.pkg import parse  # the API\n", "from pkg import parse\n"),
])
def test_src_prefixed_imports_are_rewritten_to_the_installed_name(code, want):
    fixed, why = model_probes.fix_src_imports(code, {"pkg"})
    assert why is None and fixed == want


@pytest.mark.parametrize("code", [
    "import src\n",                                  # the folder itself
    "import src.pkg\nsrc.pkg.parse(1)\n",            # no alias: the name src would still be used
    "from src.nothere import x\n",                   # not a package in the folder
    "from src import pkg, nothere\n",
    "x = 1; from src.pkg import parse\n",            # shares a line with other code
    "from src.pkg import (\n    parse)\nprint(src)\n",   # src still referenced after the rewrite
])
def test_src_imports_that_cannot_be_rewritten_safely_are_rejected(code):
    fixed, why = model_probes.fix_src_imports(code, {"pkg"})
    assert why and fixed == code


def test_no_layout_means_no_change():
    code = "from src.pkg import parse\n"
    assert model_probes.fix_src_imports(code, set()) == (code, None)
    code = "from .src import x\nimport pkg\n"
    assert model_probes.fix_src_imports(code, {"pkg"}) == (code, None)


class _Stub(model_provider.Provider):
    name = "stub"

    def __init__(self, code: str):
        super().__init__()
        self.code, self.prompts = code, {}

    def complete_json(self, task, system, user, schema, ctx):
        self.prompts[task] = system
        self._remember(task, True)
        if task == "claims":
            return {"claims": [{"id": "C1", "text": "empty input gives []", "source_quote": BODY,
                                "testable": True, "expect": "differs"}]}
        return {"probes": [{"id": "p1", "about": "parse", "code": self.code,
                            "claims": [{"id": "C1", "covers": ["v"], "expect": "differs"}]}]}


def _gen(tmp_path, code, product):
    base = _src_layout(tmp_path / "side-main", "pkg")
    prov = _Stub(code)
    res = model_probes.generate(prov, "o/r", 1, TITLE, BODY, {"src/pkg/__init__.py": base / "src/pkg/__init__.py"},
                                base, [tmp_path / "side-pr"], tmp_path / "out", product=product)
    return prov, res


CODE = "from src.pkg import parse\nprint(json.dumps({'observations': {'v': parse([])}}))\n"


def test_product_check_rewrites_the_import_and_adds_the_prompt_rules(tmp_path):
    prov, res = _gen(tmp_path, CODE, product=True)
    assert prov.prompts["probes"] == model_provider.PROBES_PROMPT + model_probes.PRODUCT_PROBE_RULES
    assert "import name" in model_probes.PRODUCT_PROBE_RULES and "json.dumps" in model_probes.PRODUCT_PROBE_RULES
    (x,) = res["probes"]
    text = Path(x["path"]).read_text()
    assert "from pkg import parse" in text and "src.pkg" not in text
    assert res["rewritten_imports"] == ["p1"]


def test_product_check_rejects_an_unfixable_src_import(tmp_path):
    _, res = _gen(tmp_path, "import src\nprint(src)\n", product=True)
    assert res["probes"] == [] and any("src/ folder" in e for e in res["errors"])


def test_study_run_is_unchanged(tmp_path):
    prov, res = _gen(tmp_path, CODE, product=False)
    assert prov.prompts["probes"] == model_provider.PROBES_PROMPT
    (x,) = res["probes"]
    assert "from src.pkg import parse" in Path(x["path"]).read_text() and "rewritten_imports" not in res


def test_plan_probes_passes_the_product_route(tmp_path, monkeypatch):
    seen = {}

    def fake_generate(*args, **kw):
        seen["product"] = kw.get("product")
        return {"probes": [], "claims": [], "rejected_claims": [], "errors": []}
    monkeypatch.setattr(model_probes, "generate", fake_generate)
    item = {"pr": 1, "title": TITLE, "body": BODY, "files": {"all": []}}
    for product, want in ((True, True), (False, False)):
        a = types.SimpleNamespace(baseline=None, model_note=None, provider=object(), product_check=product, pr=1,
                                  bench=None, no_probes=False)
        monkeypatch.setattr(daily_run.probes, "find_probes", lambda *x: [])
        daily_run.plan_probes("o/r", item, {}, tmp_path, [], tmp_path, a)
        assert seen["product"] is want


# ---------------------------------------------------------------- Python-literal output
LIT = "{'observations': {'count': 0, 'is_keyword': False, 'name': None, 'xs': [1, 'a'], 'd': {'k': 1.5}}}"


def test_python_literal_observations_are_read_on_a_product_check():
    want = {"count": 0, "is_keyword": False, "name": None, "xs": [1, "a"], "d": {"k": 1.5}}
    assert probes.observations_of("noise\n" + LIT + "\n", 0, literal_output=True) == want
    assert probes.observations_of(LIT, 1, literal_output=True) == dict(want, **{PROBE_ERROR: {"exit_code": 1}})


def test_study_parsing_is_unchanged():
    assert PROBE_ERROR in probes.observations_of(LIT, 0)
    assert PROBE_ERROR in probes.observations_of(LIT, 0, literal_output=False)
    # JSON output reads the same either way
    j = json.dumps({"observations": {"a": True}})
    assert probes.observations_of(j, 0, literal_output=True) == probes.observations_of(j, 0) == {"a": True}


@pytest.mark.parametrize("line", [
    "{'count': 0}",                                         # no observations wrapper
    "{'observations': {'a': 1}, 'extra': 2}",               # extra key
    "{'observations': [1, 2]}",                             # observations not a dict
    "{'observations': {'a': (1, 2)}}",                      # tuple: would change on the way to JSON
    "{'observations': {'a': {1, 2}}}",                      # set
    "{'observations': {'a': b'x'}}",                        # bytes
    "{'observations': {'a': 1j}}",                          # complex
    "{'observations': {1: 'a'}}",                           # non-string name
    "{'observations': {'a': {2: 'x'}}}",                    # non-string nested key
    "{'observations': {'a': float('nan')}}",                # not a literal
    "{'observations': {'a': Foo()}}",                       # an object repr
    "{'observations': {'a': 1}} trailing",
    "observations: {'a': 1}",
    "",
])
def test_ambiguous_output_stays_unparsed(line):
    assert probes.literal_observations(line) is None
    assert PROBE_ERROR in probes.observations_of(line, 0, literal_output=True)


def test_literal_output_still_obeys_the_contract():
    many = "{'observations': {" + ", ".join(f"'n{i}': {i}" for i in range(probes.MAX_OBSERVATIONS + 1)) + "}}"
    assert "contract" in probes.observations_of(many, 0, literal_output=True)[PROBE_ERROR]
    assert probes.observations_of("", "timeout", literal_output=True) == {PROBE_ERROR: {"timeout": True}}


def test_run_probe_reads_literal_output_only_when_asked(tmp_path):
    import sys
    p = tmp_path / "lit.py"
    p.write_text('PROBE = {"id": "lit", "target": "o/r#1", "about": "x", "claims": []}\n'
                 "print({'observations': {'v': 1}})\n")
    py = {"main": Path(sys.executable), "pr": Path(sys.executable)}
    env = {"PATH": "/usr/bin:/bin"}
    for flag, ok in ((True, True), (False, False)):
        out = tmp_path / f"o-{flag}"
        out.mkdir()
        it = probes.run_probe(p, py, out, tmp_path / "cwd", {"main": env, "pr": env}, runs=1, literal_output=flag)
        assert all(r["ok"] is ok for r in it["per_run"])
