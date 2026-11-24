"""A probe that builds a stand-in for the real target is rejected, and a broken call is not evidence."""
from ops.daily_run import compare_sides, verdict_for
from poc import model_probes, model_provider, probe_names, probes

GOOD = "import json\nimport widget.calc as calc\nprint(json.dumps({'observations': {'c1.value': calc.answer()}}))\n"
CLAIM = {"claims": [{"id": "C1", "text": "answer changes", "source_quote": "answer changes", "testable": True,
                     "expect": "differs"}]}
LINKS = [{"id": "C1", "covers": ["c1.*"], "expect": "differs"}]


def _package(root):
    pkg = root / "widget"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("")
    (pkg / "calc.py").write_text("class Solver:\n    def answer(self):\n        return 1\n")


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


def test_an_importerror_handler_that_defines_a_class_is_rejected(tmp_path):
    _package(tmp_path)
    code = ("try:\n    from widget.calc import Solver\n"
            "except ImportError:\n    class Solver:\n        def answer(self):\n            return 0\n"
            "print(Solver)\n")
    msgs = probe_names.problems(code, tmp_path)
    assert any("stand-in" in m for m in msgs)


def test_a_constant_fallback_is_still_an_absence_check(tmp_path):
    _package(tmp_path)
    code = ("try:\n    from widget.calc import Solver\n    present = True\n"
            "except ImportError:\n    present = False\nprint(present)\n")
    assert probe_names.problems(code, tmp_path) == []


def test_defining_the_targets_class_instead_of_importing_it_is_rejected(tmp_path):
    _package(tmp_path)
    code = ("import widget.calc as calc\n"
            "class Solver:\n    def answer(self):\n        return 0\n"
            "print(calc, Solver)\n")
    msgs = probe_names.problems(code, tmp_path)
    assert any("Solver" in m and "instead of importing" in m for m in msgs)


def test_a_stand_in_is_regenerated_once(tmp_path):
    pkg = tmp_path / "widget"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("")
    (pkg / "calc.py").write_text("def answer():\n    return 1\n")
    bad = ("try:\n    from widget.calc import Solver\n"
           "except ImportError:\n    class Solver:\n        def answer(self):\n            return 0\n"
           "import json\nprint(json.dumps({'observations': {'c1.value': 1}}))\n")
    first = {"id": "p1", "about": "calc", "claims": LINKS, "code": bad}
    second = dict(first, code=GOOD)
    prov = Sequence([[first], [second]])
    out = model_probes.generate(prov, "o/r", 1, "Change answer", "answer changes",
                                {"widget/calc.py": tmp_path / "widget" / "calc.py"}, tmp_path,
                                [tmp_path / "pr"], tmp_path / "out")
    assert prov.probe_calls == 2
    assert out["probes"] and "class Solver" not in out["probes"][0]["path"].read_text()


def _compared():
    main = {"tests/test_widget.py::test_fix": ("failed", "AssertionError"),
            "tests/test_widget.py::test_keep": ("passed", "")}
    pr = {"tests/test_widget.py::test_fix": ("passed", ""),
          "tests/test_widget.py::test_keep": ("passed", "")}
    return compare_sides({"main": [main] * 3, "pr": [pr] * 3})


def _item(main, pr, claims):
    spec = {"id": "model-p1", "target": "o/r#1", "about": "x", "claims": claims, "source": "model"}
    item = probes.entry(spec, {"main": [main] * 3, "pr": [pr] * 3}, {"main": ["m"], "pr": ["p"]}, [], "model", None)
    item["probe_changed_line_coverage"] = {"status": "measured", "changed_lines_covered": 1,
                                           "changed_lines_total": 1, "adequacy": "adequate"}
    return item


def test_every_observation_from_a_broken_call_is_broken_and_does_not_need_attention():
    claims = [{"id": "C2", "text": "help now prints", "covers": ["c2.*"], "expect": "differs"},
              {"id": "C5", "text": "the other task stays", "covers": ["c5.*"], "expect": "same"}]
    item = _item({"c2.error_type": "AttributeError", "c2.task_values": None,
                  "c5.error_type": "AttributeError", "c5.task_values": None},
                 {"c2.error_type": "AttributeError", "c2.task_values": None,
                  "c5.error_type": "AttributeError", "c5.task_values": None}, claims)
    by_name = {o["name"]: o for o in item["observations"]}
    assert by_name["c2.task_values"]["probe_broken"] and by_name["c2.task_values"]["label"] == "not_testable"
    assert by_name["c5.task_values"]["label"] == "not_testable"
    assert by_name["c5.task_values"]["label"] != "proven"
    v, reason, _fl = verdict_for(_compared(), None, None, {"all": ["pkg/widget.py", "tests/test_widget.py"]},
                                 {"status": "ran", "items": [item]})
    assert v != "needs_attention"
    assert "does not differ although the claim says it does" not in reason


def test_a_different_call_that_really_differs_still_needs_attention():
    claims = [{"id": "C1", "text": "the result stays", "covers": ["c1.*"], "expect": "same"}]
    item = _item({"c2.error_type": "AttributeError", "c2.task_values": None, "c1.value": 1},
                 {"c2.error_type": "AttributeError", "c2.task_values": None, "c1.value": 2}, claims)
    by_name = {o["name"]: o for o in item["observations"]}
    assert by_name["c2.task_values"].get("probe_broken")
    assert not by_name["c1.value"].get("probe_broken")
    assert by_name["c1.value"]["label"] == "false_claim"
    v, _reason, _fl = verdict_for(_compared(), None, None, {"all": ["pkg/widget.py", "tests/test_widget.py"]},
                                  {"status": "ran", "items": [item]})
    assert v == "needs_attention"
