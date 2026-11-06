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

import pytest

from ops.daily_run import ai_probe_gate, compare_sides, verdict_for
from poc import model_probes, model_provider, probe_adequacy, probe_names, probes

# Scrubbed title and the one sentence this test quotes. Kept in this change so the test does not
# depend on a fixture that lives only on main.
FIX = Path(__file__).parent / "fixtures" / "probe_names" / "missing-argument-pr.json"
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


def test_unlinked_retry_and_a_missing_name_share_one_model_call(tmp_path):
    """The unlinked retry is the one feedback call. It is also told the missing module.

    A second answer that links the claim but still imports the missing module is not followed
    by another call, and no probe file is written."""
    base = tmp_path / "base"
    _parser_package(base, 1)
    bad = {"id": "p1", "about": "answer", "claims": [], "code": _bad_import()}
    still = {"id": "p1", "about": "answer", "claims": LINKS, "code": _bad_import()}
    fixed = {"id": "p1", "about": "answer", "claims": LINKS, "code": _good_import()}
    prov = Sequence([[bad], [still]])
    out = model_probes.generate(prov, "o/r", 1, "Keep answer", BODY,
                                {"widget/calc.py": base / "widget" / "calc.py"}, base,
                                [tmp_path / "pr"], tmp_path / "out")
    assert prov.probe_calls == 2
    assert len(prov.users) == 2
    assert "widget.parser.arguments" in prov.users[1]
    assert "claim ids" in prov.users[1].lower() or "Every probe must list" in prov.users[1]
    assert out["probes"] == []
    assert not list((tmp_path / "out").glob("*.py"))
    prov2 = Sequence([[bad], [fixed]])
    out2 = model_probes.generate(prov2, "o/r", 1, "Keep answer", BODY,
                                 {"widget/calc.py": base / "widget" / "calc.py"}, base,
                                 [tmp_path / "pr"], tmp_path / "out2")
    assert prov2.probe_calls == 2
    assert out2["probes"] and "widget.parser.arguments" not in out2["probes"][0]["path"].read_text()


def test_a_loose_module_directory_is_not_the_whole_package(tmp_path):
    """rich/highlighter.py and no __init__.py: importing rich.text is not a missing-name repair."""
    rich = tmp_path / "rich"
    rich.mkdir()
    (rich / "highlighter.py").write_text("class ReprHighlighter:\n    pass\n")
    code = ("from rich.highlighter import ReprHighlighter\n"
            "from rich.text import Text\n"
            "print(ReprHighlighter(), Text('x'))\n")
    assert probe_names.problems(code, tmp_path) == []
    (rich / "__init__.py").write_text("")
    (rich / "highlighter.py").write_text("class ReprHighlighter:\n    pass\n")
    text = " ".join(probe_names.problems(code, tmp_path))
    assert "rich.text" in text and "highlighter" in text
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
    blocked_tests, blocked_reason, _flags = verdict_for(
        _cmp_verified(), None, probe_results={"status": "ran", "items": [blocked]})
    assert "proven" not in blocked_reason
    assert "C1" not in blocked_reason
    # The existing AI-probe gate: verified needs a model probe that ran a changed line.
    # An unusable probe has none, so the matching fallback cannot leave the check verified.
    blocked_verdict = ai_probe_gate({
        "verdict": blocked_tests, "reason": blocked_reason, "baseline": "full",
        "probes": {"status": "ran", "items": [blocked]},
    })["verdict"]
    assert blocked_verdict != "verified"
    assert blocked_verdict == "could_not_verify"


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


def test_fixture_paths_used_here_are_in_this_branch():
    """The pull-request text this module opens is a file next to the test, with title and body."""
    import re
    text = Path(__file__).read_text()
    root = Path(__file__).resolve().parents[1]
    named = re.findall(r"fixtures/(?:probe_names|pr_text)/[\w.-]+\.json", text)
    named.append("fixtures/probe_names/missing-argument-pr.json")
    for rel in named:
        path = root / "tests" / rel
        assert path.is_file(), rel
        got = json.loads(path.read_text())
        assert got.get("title") and got.get("body")


@pytest.mark.parametrize("dodge", [
    "import widget.calc as calc\nprint(getattr(calc, 'missing', 0))\n",
    "import widget.calc as calc\n"
    "try:\n    value = calc.missing()\nexcept AttributeError:\n    value = 0\nprint(value)\n",
    "try:\n    import widget.parser.arguments as arguments\n    value = 1\n"
    "except ImportError:\n    value = 0\nprint(value)\n",
])
def test_repair_cannot_hide_a_missing_name_behind_an_absence_check(tmp_path, dodge):
    first = ("import widget.calc as calc\nprint(calc.missing())\n"
             if "arguments" not in dodge else _bad_import())
    prov = Sequence([[_probe(first)], [_probe(dodge)]])
    _base, _pr, out = _generate(tmp_path, prov)
    assert prov.probe_calls == 2
    assert out["probes"] == []
    assert out["name_checks"][0]["outcome"].startswith("not fixed:")
    assert "hides missing name" in out["name_checks"][0]["outcome"]
    assert "absence check" in out["name_checks"][0]["outcome"]
    assert not list((tmp_path / "out").glob("*.py"))


def test_an_initial_absence_check_is_not_a_repair_and_is_kept(tmp_path):
    code = ("try:\n    import widget.parser.arguments as arguments\n    present = True\n"
            "except ImportError:\n    present = False\nprint(present)\n")
    prov = Sequence([[_probe(code)]])
    _base, _pr, out = _generate(tmp_path, prov)
    assert prov.probe_calls == 1
    assert "name_checks" not in out
    assert out["probes"] and "arguments" in out["probes"][0]["path"].read_text()


def test_a_later_module_function_is_visible_inside_an_earlier_one(tmp_path):
    _parser_package(tmp_path, 1)
    code = ("def run():\n    return helper(calc.answer())\n"
            "def helper(x):\n    return x\n"
            "import widget.calc as calc\n"
            "print(run())\n")
    assert probe_names.problems(code, tmp_path) == []
    text = ('PROBE = {"id": "model-p1", "target": "o/r#1", "about": "x", "claims": []}\n' + code)
    assert probe_names.local_failure(text) is None


def test_forward_ref_probe_is_executed(tmp_path, monkeypatch):
    from ops import daily_run
    called = []

    def fake(*args, **kwargs):
        called.append(True)
        return {"id": "model-p1", "observations": [], "runs": {"main": [], "pr": []}}

    monkeypatch.setattr(daily_run.probes, "run_probe", fake)
    monkeypatch.setattr(daily_run.freeze, "verify", lambda *a, **k: None)
    monkeypatch.setattr(daily_run, "_contree_ready", lambda: False)
    monkeypatch.setattr(daily_run, "probe_env", lambda v, settings=None: {})
    path = tmp_path / "model-p1.py"
    path.write_text('PROBE = {"id": "model-p1", "target": "o/r#1", "about": "x", "claims": []}\n'
                    "def run():\n    return helper()\n"
                    "def helper():\n    return 1\n"
                    "print(run())\n")
    py = tmp_path / "venv-main" / "bin" / "python"
    py.parent.mkdir(parents=True)
    plan = [{"path": path, "source": "model", "freeze": {"generator": {"kind": "model"}, "sha256": "x",
                                                         "frozen_at": "t"}}]
    a = type("A", (), {"runs": 1, "product_check": False, "provider": None})()
    out = daily_run.run_probes("o/r", 1, {"main": py, "pr": py}, tmp_path, tmp_path, a, plan, "t")
    assert called == [True]
    assert out["items"][0].get("status") != "not_run"


def test_a_class_body_name_is_not_visible_inside_a_method(tmp_path):
    code = "class T:\n    x = 1\n    def m(self):\n        return x\nprint(T)\n"
    assert any(m.startswith("undefined name: x") for m in probe_names.problems(code, tmp_path))
    text = 'PROBE = {"id": "model-p1", "target": "o/r#1", "about": "x", "claims": []}\n' + code
    assert probe_names.local_failure(text) and "undefined name: x" in probe_names.local_failure(text)
    # The class body itself still sees x, and a method still sees a real global.
    assert probe_names.problems("class T:\n    x = 1\n    y = x\nprint(T)\n", tmp_path) == []
    assert probe_names.problems("x = 1\nclass T:\n    def m(self):\n        return x\nprint(T)\n", tmp_path) == []
    # A comprehension in the class is its own function and does not see the class body either.
    comp = "class T:\n    x = 1\n    ys = [x for _ in range(1)]\nprint(T)\n"
    assert any("undefined name: x" in m for m in probe_names.problems(comp, tmp_path))
    assert probe_names.problems("x = 1\nclass T:\n    ys = [x for _ in range(1)]\nprint(T)\n", tmp_path) == []


def _argument_tree(root: Path) -> None:
    parser = root / "widget" / "parser"
    parser.mkdir(parents=True)
    (root / "widget" / "__init__.py").write_text("")
    (parser / "__init__.py").write_text("")
    (parser / "argument.py").write_text(
        "class Argument:\n"
        "    def __init__(self, name, kind=str):\n"
        "        self.name = name\n"
        "        self.kind = kind\n"
        "    def set_name(self, name):\n"
        "        self.name = name\n"
        "class Bag:\n"
        "    def __init__(self, **kwargs):\n"
        "        self.kwargs = kwargs\n"
        "def parse(argv, allow_extra=False):\n"
        "    return argv\n")


def test_unexpected_constructor_keyword_is_reported_from_the_base_signature(tmp_path):
    _argument_tree(tmp_path)
    bad = ("import widget.parser.argument as argument\n"
           "print(argument.Argument('p', takes_value=True).name)\n")
    good = ("import widget.parser.argument as argument\n"
            "print(argument.Argument('p', kind=str).name)\n")
    text = " ".join(probe_names.problems(bad, tmp_path))
    assert "takes_value" in text and "Argument()" in text and "name" in text and "kind" in text
    assert probe_names.problems(good, tmp_path) == []
    # A definition that accepts **kwargs, and a call that is not a base-tree symbol, are left alone.
    flex = "import widget.parser.argument as argument\nprint(argument.Bag(takes_value=True))\n"
    other = "import json\nprint(json.dumps({'a': 1}, indent=2))\n"
    assert probe_names.problems(flex, tmp_path) == []
    assert probe_names.problems(other, tmp_path) == []
    method = ("import widget.parser.argument as argument\n"
              "print(argument.Argument.set_name(None, takes_value=True))\n")
    assert "takes_value" in " ".join(probe_names.problems(method, tmp_path))
    fn = ("import widget.parser.argument as argument\n"
          "print(argument.parse(['p'], takes_value=True))\n")
    assert "takes_value" in " ".join(probe_names.problems(fn, tmp_path))
    assert probe_names.problems(
        "import widget.parser.argument as argument\nprint(argument.parse(['p'], allow_extra=True))\n",
        tmp_path) == []


def test_bad_constructor_keyword_is_repaired_once_or_dropped(tmp_path):
    base = tmp_path / "base"
    _argument_tree(base)
    (tmp_path / "pr").mkdir()
    bad = ("import widget.parser.argument as argument\n"
           "print(argument.Argument('p', takes_value=True).name)\n")
    good = ("import widget.parser.argument as argument\n"
            "print(argument.Argument(name='p').name)\n")
    prov = Sequence([[_probe(bad)], [_probe(good)]])
    out = model_probes.generate(prov, "o/r", 1, "Keep answer", BODY,
                                {"widget/parser/argument.py": base / "widget" / "parser" / "argument.py"},
                                base, [tmp_path / "pr"], tmp_path / "out")
    assert prov.probe_calls == 2
    assert "takes_value" in prov.users[1] and "parameters:" in prov.users[1]
    assert out["name_checks"][0]["outcome"] == "fixed"
    text = out["probes"][0]["path"].read_text()
    assert "takes_value" not in text and "name=" in text
    again = Sequence([[_probe(bad)], [_probe(bad)]])
    out2 = model_probes.generate(again, "o/r", 1, "Keep answer", BODY,
                                 {"widget/parser/argument.py": base / "widget" / "parser" / "argument.py"},
                                 base, [tmp_path / "pr"], tmp_path / "out2")
    assert again.probe_calls == 2
    assert "unexpected keyword" in out2["name_checks"][0]["outcome"]
    # takes_value is not a parameter. Deleting it would leave Argument('p'), which is a different
    # call from the one the probe wrote, so the probe is not written and is not coverage.
    assert out2["probes"] == []
    assert any("not removed" in err for err in out2["errors"])
    assert not list((tmp_path / "out2").glob("*.py"))


def test_unrelated_observations_are_not_claim_proof():
    """Names like import_success do not prove a claim whose cover is scenario1."""
    spec = {"id": "p", "target": "o/r#1", "about": "missing argument", "claims": [
        {"id": "C1", "text": "the name stays", "covers": ["c1.scenario1"], "expect": "same"},
        {"id": "C2", "text": "the error names the flag", "covers": ["c2.scenario1"], "expect": "differs"}],
            "source": "model"}
    obs = {"c1.import_success": True, "c2.parser_creation": True, "c3.parse_result": "ok"}
    item = probes.entry(spec, {"main": [obs] * 3, "pr": [obs] * 3}, {"main": ["m"], "pr": ["p"]}, [], "model", None)
    item["probe_changed_line_coverage"] = {
        "status": "measured", "changed_lines_total": 1, "changed_lines_covered": 1, "adequacy": "adequate"}
    item = probes.classify_item(item)
    assert item["status"] == "rejected"
    assert probes.rejection_reason(item)
    verdict, reason, _flags = verdict_for(_cmp_verified(), None, probe_results={"status": "ran", "items": [item]})
    assert verdict != "verified"
    assert "proven" not in reason
    decided, _notes = probe_adequacy.deciding_items([item])
    assert not any(o.get("label") == "proven" for o in decided[0]["observations"])


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
