"""A generated probe that imports or calls a missing name is regenerated once, then dropped.

The tree is generic. One case uses the same shape as a real missing plural module beside a
singular module that exists (argument.py is on disk, arguments.py is not). The pull-request
text from that example is data for the prompt only. The checker has no library names in it.

A probe that does run, and sees the base and the pull request disagree, still needs attention.
A matching import failure is not coverage and does not prove a claim.
"""
import json
import os
import sys
from pathlib import Path

from ops.daily_run import compare_sides, verdict_for
from poc import model_probes, model_provider, probe_adequacy, probe_names, probes

FIX = Path(__file__).parent / "fixtures" / "pr_text" / "invoke-1097.json"
BODY = "answer() stays the same."
CLAIM = {"id": "C1", "text": "answer() stays the same.", "source_quote": "answer() stays the same.",
         "testable": True, "expect": "same"}
LINKS = [{"id": "C1", "covers": ["c1.*"], "expect": "same"}]


def _parser_package(root: Path, value: int) -> None:
    """A package whose parser has argument.py and not arguments.py, and calc.answer returns value."""
    pkg = root / "widget"
    parser = pkg / "parser"
    parser.mkdir(parents=True)
    (pkg / "__init__.py").write_text("")
    (pkg / "calc.py").write_text(f"def answer():\n    return {value}\n")
    (parser / "__init__.py").write_text("")
    (parser / "argument.py").write_text(
        "class Argument:\n    def __init__(self, name):\n        self.name = name\n")
    (parser / "parser.py").write_text("def parse(argv):\n    return list(argv)\n")


def _bad_import() -> str:
    return ("import json\n"
            "import widget.parser.arguments as arguments\n"
            "print(json.dumps({'observations': {'c1.value': arguments.answer()}}))\n")


def _good_import() -> str:
    return ("import json\n"
            "import widget.calc as calc\n"
            "print(json.dumps({'observations': {'c1.value': calc.answer()}}))\n")


class Sequence(model_provider.Provider):
    name = "sequence"

    def __init__(self, answers):
        super().__init__()
        self.answers = list(answers)
        self.probe_calls = 0
        self.users = []

    def complete_json(self, task, system, user, schema, ctx):
        if task == "claims":
            return {"claims": [CLAIM]}
        self.probe_calls += 1
        self.users.append(user)
        return {"probes": self.answers.pop(0)}


def _probe(code: str) -> dict:
    return {"id": "p1", "about": "answer", "claims": LINKS, "code": code}


def _generate(tmp_path, provider, base: Path | None = None):
    base = base or (tmp_path / "base")
    _parser_package(base, 1)
    pr = tmp_path / "pr"
    _parser_package(pr, 2)
    out = model_probes.generate(
        provider, "o/r", 1, "Keep answer", BODY,
        {"widget/calc.py": base / "widget" / "calc.py"}, base, [pr], tmp_path / "out")
    return base, pr, out


def _cmp_verified():
    same = {"t::a": ("passed", ""), "t::b": ("passed", "")}
    return compare_sides({"main": [same] * 3, "pr": [same] * 3})


# ---------------------------------------------------------------- the base tree
def test_plural_module_is_missing_and_the_singular_module_is_listed(tmp_path):
    _parser_package(tmp_path, 1)
    msgs = probe_names.problems(_bad_import(), tmp_path)
    text = " ".join(msgs)
    assert "widget.parser.arguments" in text
    assert "widget.parser contains: argument, parser" in text
    assert probe_names.problems(_good_import(), tmp_path) == []


def test_a_missing_name_that_is_not_a_plural_is_reported_the_same_way(tmp_path):
    """No plural-to-singular table: a different missing sibling is only named, not rewritten."""
    _parser_package(tmp_path, 1)
    code = "import widget.parser.context as context\nprint(context)\n"
    text = " ".join(probe_names.problems(code, tmp_path))
    assert "widget.parser.context" in text
    assert "widget.parser contains: argument, parser" in text


def test_undefined_name_and_a_missing_call_are_reported(tmp_path):
    _parser_package(tmp_path, 1)
    undef = "import json\nprint(json.dumps({'observations': {'c1.value': answer()}}))\n"
    assert any(m.startswith("undefined name: answer") for m in probe_names.problems(undef, tmp_path))
    missing_call = ("import widget.calc as calc\n"
                    "print(calc.missing())\n")
    text = " ".join(probe_names.problems(missing_call, tmp_path))
    assert "widget.calc.missing" in text and "answer" in text


def test_a_name_checked_for_absence_is_allowed(tmp_path):
    _parser_package(tmp_path, 1)
    samples = [
        "try:\n    import widget.parser.arguments as arguments\n    present = True\n"
        "except ImportError:\n    present = False\n"
        "print(present)\n",
        "import widget.parser.argument as argument\n"
        "print(hasattr(argument, 'removed_symbol'))\n",
        "import widget.parser.argument as argument\n"
        "try:\n    value = argument.removed_symbol\nexcept AttributeError:\n    value = None\n"
        "print(value)\n",
        "import pytest\n"
        "with pytest.raises(ImportError):\n"
        "    import widget.parser.arguments\n"
        "print(1)\n",
        "try:\n    from widget.parser.argument import Removed\n    gone = False\n"
        "except ImportError:\n    gone = True\n"
        "print(gone)\n",
    ]
    for code in samples:
        assert probe_names.problems(code, tmp_path) == [], code


def test_a_broad_except_does_not_make_a_missing_import_optional(tmp_path):
    _parser_package(tmp_path, 1)
    code = ("try:\n    import widget.parser.arguments as arguments\n    value = 1\n"
            "except Exception:\n    value = 0\nprint(value)\n")
    assert any("arguments" in m for m in probe_names.problems(code, tmp_path))


def test_stdlib_imports_are_not_required_to_live_in_the_tree(tmp_path):
    _parser_package(tmp_path, 1)
    code = "import json\nprint(json.dumps({'observations': {'c1.value': 1}}))\n"
    assert probe_names.problems(code, tmp_path) == []


# ---------------------------------------------------------------- regeneration
def test_one_regeneration_feeds_back_the_missing_module_and_keeps_the_fix(tmp_path):
    prov = Sequence([[_probe(_bad_import())], [_probe(_good_import())]])
    _base, _pr, out = _generate(tmp_path, prov)
    assert prov.probe_calls == 2
    assert "widget.parser.arguments" in prov.users[1]
    assert "widget.parser contains: argument, parser" in prov.users[1]
    assert out["name_checks"][0]["outcome"] == "fixed"
    text = out["probes"][0]["path"].read_text()
    assert "widget.calc" in text and "widget.parser.arguments" not in text


def test_a_second_missing_name_writes_no_probe(tmp_path):
    prov = Sequence([[_probe(_bad_import())], [_probe(_bad_import())]])
    _base, _pr, out = _generate(tmp_path, prov)
    assert prov.probe_calls == 2
    assert out["probes"] == []
    assert any("arguments" in e for e in out["errors"])
    assert not list((tmp_path / "out").glob("*.py"))


def test_an_undefined_name_is_regenerated_once(tmp_path):
    undef = "import json\nprint(json.dumps({'observations': {'c1.value': answer()}}))\n"
    prov = Sequence([[_probe(undef)], [_probe(_good_import())]])
    _base, _pr, out = _generate(tmp_path, prov)
    assert prov.probe_calls == 2 and "undefined name: answer" in prov.users[1]
    assert "widget.calc" in out["probes"][0]["path"].read_text()


def test_invoke_1097_text_is_only_the_prompt_data(tmp_path):
    """The real pull-request wording is the description. The tree is the plural-missing shape.
    The package name in the fixture is the example's; the checker is the same function as above."""
    pr = json.loads(FIX.read_text())
    root = tmp_path / "base"
    parser = root / "invoke" / "parser"
    parser.mkdir(parents=True)
    (root / "invoke" / "__init__.py").write_text("")
    (parser / "__init__.py").write_text("")
    (parser / "argument.py").write_text("class Argument:\n    def __init__(self, name):\n        self.name = name\n")
    (parser / "parser.py").write_text("def parse(argv):\n    return argv\n")
    quote = ("When a required `param_1` argument is exposed as `param-1` on the command line, omitting it "
             "reports the Python attribute name instead of the CLI name.")
    bad = ("import json\nimport invoke.parser.arguments as arguments\n"
           "print(json.dumps({'observations': {'c1.value': 1}}))\n")
    good = ("import json\nimport invoke.parser.argument as argument\n"
            "print(json.dumps({'observations': {'c1.value': argument.Argument('param-1').name}}))\n")
    links = [{"id": "C1", "covers": ["c1.*"], "expect": "differs"}]

    class One(model_provider.Provider):
        name = "one"

        def __init__(self):
            super().__init__()
            self.answers = [[{"id": "p1", "about": "missing argument", "claims": links, "code": bad}],
                            [{"id": "p1", "about": "missing argument", "claims": links, "code": good}]]
            self.probe_calls = 0

        def complete_json(self, task, system, user, schema, ctx):
            if task == "claims":
                return {"claims": [{"id": "C1", "text": quote, "source_quote": quote,
                                    "testable": True, "expect": "differs"}]}
            self.probe_calls += 1
            return {"probes": self.answers.pop(0)}

    prov = One()
    out = model_probes.generate(prov, "o/r", 1097, pr["title"], pr["body"],
                                {"invoke/parser/parser.py": parser / "parser.py"}, root, [tmp_path / "pr"],
                                tmp_path / "out")
    assert prov.probe_calls == 2
    text = out["probes"][0]["path"].read_text()
    assert "invoke.parser.argument" in text and "invoke.parser.arguments" not in text
    assert "invoke.parser contains: argument, parser" in " ".join(
        " ".join(c["error"]) for c in out["name_checks"])


# ---------------------------------------------------------------- does not silently regress
def test_repaired_probe_that_sees_a_difference_needs_attention(tmp_path):
    """Base returns 1 and the pull request returns 2. The claim says the result stays the same.

    The first probe imports a module that is not there, so both sides fail the same way. That
    match is not coverage. The repaired probe calls the real function, the values differ, and
    the verdict is needs attention rather than verified."""
    prov = Sequence([[_probe(_bad_import())], [_probe(_good_import())]])
    base, pr, out = _generate(tmp_path, prov)
    path = out["probes"][0]["path"]
    assert "widget.parser.arguments" not in path.read_text()

    def run(root):
        env = os.environ.copy()
        env["PYTHONPATH"] = str(root)
        env.pop("PYTHONSAFEPATH", None)
        obs, _log, _secs = probes.run_once(path, Path(sys.executable), tmp_path, env, 30)
        return obs

    main_obs, pr_obs = run(base), run(pr)
    assert main_obs["c1.value"] == 1 and pr_obs["c1.value"] == 2

    spec = probes.read_spec(path)
    item = probes.entry(spec, {"main": [main_obs] * 3, "pr": [pr_obs] * 3},
                        {"main": ["m"], "pr": ["p"]}, [], "model", path)
    item["probe_changed_line_coverage"] = {
        "status": "measured", "changed_lines_total": 1, "changed_lines_covered": 1, "adequacy": "adequate"}
    verdict, reason, _flags = verdict_for(
        _cmp_verified(), None, probe_results={"status": "ran", "items": [item]})
    assert verdict == "needs_attention"
    assert verdict != "verified"
    assert "c1.value" in reason

    # The unrepaired import fails the same way on both trees. That match must not count as coverage
    # or as the claim passing, even if a line counter had moved.
    crashed = probe_names.problems(_bad_import(), base)
    assert crashed
    same = {"c1.value": 0}
    passed = probes.entry(spec, {"main": [same] * 3, "pr": [same] * 3},
                          {"main": ["m"], "pr": ["p"]}, [], "model", path)
    passed["probe_changed_line_coverage"] = {
        "status": "measured", "changed_lines_total": 1, "changed_lines_covered": 1, "adequacy": "adequate"}
    would_pass, would_reason, _flags = verdict_for(
        _cmp_verified(), None, probe_results={"status": "ran", "items": [passed]})
    assert would_pass == "verified" and "proven" in would_reason
    blocked = probe_names.mark_unusable(passed, crashed[0])
    decided, _notes = probe_adequacy.deciding_items([blocked])
    assert decided[0]["observations"] == []
    assert blocked["probe_changed_line_coverage"]["changed_lines_covered"] == 0
    assert blocked["probe_changed_line_coverage"]["changed_lines_touched"] == 1
    blocked_verdict, blocked_reason, _flags = verdict_for(
        _cmp_verified(), None, probe_results={"status": "ran", "items": [blocked]})
    assert "proven" not in blocked_reason
    assert "C1" not in blocked_reason


def test_an_undefined_probe_is_not_executed_and_is_not_coverage(tmp_path, monkeypatch):
    from ops import daily_run
    called = []
    monkeypatch.setattr(daily_run.probes, "run_probe", lambda *a, **k: called.append(True))
    monkeypatch.setattr(daily_run.freeze, "verify", lambda *a, **k: None)
    monkeypatch.setattr(daily_run, "_contree_ready", lambda: False)
    monkeypatch.setattr(daily_run, "probe_env", lambda v, settings=None: {})
    path = tmp_path / "model-p1.py"
    path.write_text('PROBE = {"id": "model-p1", "target": "o/r#1", "about": "x", "claims": []}\n'
                    "import json\n"
                    "print(json.dumps({'observations': {'c1.value': missing_name()}}))\n")
    py = tmp_path / "venv-main" / "bin" / "python"
    py.parent.mkdir(parents=True)
    plan = [{"path": path, "source": "model", "freeze": {"generator": {"kind": "model"}, "sha256": "x",
                                                         "frozen_at": "t"}}]
    a = type("A", (), {"runs": 1, "product_check": False, "provider": None})()
    out = daily_run.run_probes("o/r", 1, {"main": py, "pr": py}, tmp_path, tmp_path, a, plan, "t")
    assert called == []
    item = out["items"][0]
    assert item["status"] == "not_run" and item["observations"] == []
    assert item["probe_changed_line_coverage"]["changed_lines_covered"] == 0
    assert "undefined name" in item["uninformative_reason"]
    assert any("undefined name" in e for e in out["errors"])


def test_an_empty_probe_file_is_not_executed(tmp_path, monkeypatch):
    from ops import daily_run
    called = []
    monkeypatch.setattr(daily_run.probes, "run_probe", lambda *a, **k: called.append(True))
    monkeypatch.setattr(daily_run.freeze, "verify", lambda *a, **k: None)
    monkeypatch.setattr(daily_run, "_contree_ready", lambda: False)
    monkeypatch.setattr(daily_run, "probe_env", lambda v, settings=None: {})
    path = tmp_path / "model-p1.py"
    path.write_text('PROBE = {"id": "model-p1", "target": "o/r#1", "about": "x", "claims": []}\n'
                    "import json\n")
    py = tmp_path / "venv-main" / "bin" / "python"
    py.parent.mkdir(parents=True)
    plan = [{"path": path, "source": "model", "freeze": {"generator": {"kind": "model"}}}]
    a = type("A", (), {"runs": 1, "product_check": False, "provider": None})()
    out = daily_run.run_probes("o/r", 1, {"main": py, "pr": py}, tmp_path, tmp_path, a, plan, "t")
    assert called == []
    assert out["items"][0]["status"] == "not_run"
    assert "empty probe" in out["items"][0]["uninformative_reason"]
