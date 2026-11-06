"""A probe call is bound from the base signature and from real calls in the base tree.

The model may choose which function to call. The arguments are not taken from the pull-request
text. A call that does not match the base signature is rebuilt from a call the base files already
make, or from the signature when every required argument is shown there. If it cannot be rebuilt,
the probe is not run: that is uninformative, it covers no changed line, and it does not need
attention. A real difference on another call still does.

Nothing here names one library. One fixture file holds a held-out probe as data. A second case
uses a different signature so the result does not depend on that fixture.
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from ops.daily_run import ai_probe_gate, compare_sides, verdict_for
from poc import model_probes, model_provider, probe_names, probes

HELD = Path(__file__).parent / "fixtures" / "call_binding" / "heldout.json"
PARSER_BASE = Path(__file__).parent / "fixtures" / "call_binding" / "parser_base"
BODY = "answer() stays the same."
CLAIM = {"id": "C1", "text": "answer() stays the same.", "source_quote": "answer() stays the same.",
         "testable": True, "expect": "same"}
LINKS = [{"id": "C1", "covers": ["c1.*"], "expect": "same"}]


def _write(root: Path, files: dict) -> None:
    for rel, text in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)


def _maker_tree(root: Path, label: str, score: int) -> None:
    """A constructor with one required argument, a real call, and a subscript that is not a call."""
    _write(root, {
        "widget/__init__.py": "",
        "widget/maker.py": (
            "class Context:\n"
            "    def __init__(self, name):\n"
            "        self.name = name\n"
            "\n"
            "class Maker:\n"
            "    def __init__(self, initial, core=None, module=None):\n"
            "        self.initial = initial\n"
            "        self.core = core\n"
            "        self.module = module\n"
            "\n"
            "    def label(self):\n"
            "        return self.initial.name\n"
            "\n"
            "def complete(item):\n"
            "    return item.names[0]\n"
            "\n"
            f"def score():\n"
            f"    return {score}\n"
        ),
        "tests/test_maker.py": (
            "from widget.maker import Context, Maker\n"
            "\n"
            "def test_label():\n"
            f"    ctx = Context({label!r})\n"
            "    made = Maker(initial=ctx)\n"
            "    assert made.label() == ctx.name\n"
        ),
    })


def _run(code: str, root: Path, work: Path) -> subprocess.CompletedProcess:
    work.mkdir(parents=True, exist_ok=True)
    path = work / "bound.py"
    path.write_text(code)
    env = os.environ.copy()
    env["PYTHONPATH"] = str(root)
    env.pop("PYTHONSAFEPATH", None)
    return subprocess.run([sys.executable, str(path)], cwd=work, env=env, capture_output=True, text=True,
                          timeout=30)


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
    return {"id": "p1", "about": "label", "claims": LINKS, "code": code}


def _bad_maker() -> str:
    return ("import json\n"
            "import widget.maker as maker\n"
            "value = maker.Maker(contexts=[maker.Context(name='invented', aliases=(), help={'task': 'x'})]).label()\n"
            "print(json.dumps({'observations': {'c1.value': value}}))\n")


def _cmp_verified():
    same = {"t::a": ("passed", ""), "t::b": ("passed", "")}
    return compare_sides({"main": [same] * 3, "pr": [same] * 3})


def test_constructor_binds_from_the_base_call_and_runs(tmp_path):
    """A missing required argument is filled from the base test. An unknown keyword is not deleted.

    A subscript in the implementation (names[0]) is not a call. A call that exists only on the
    pull-request side is not used. Deleting contexts= would leave a different call, so that probe
    is not run."""
    base, pr = tmp_path / "base", tmp_path / "pr"
    _maker_tree(base, "from-base", 1)
    _maker_tree(pr, "from-pr", 1)
    refused, refused_notes, reason = probe_names.prepare_calls(_bad_maker(), base)
    assert reason and "not removed" in reason and "not run" in reason
    assert refused_notes == [] and "from-base" not in refused and "from-pr" not in refused
    code = ("import widget.maker as maker\n"
            "print(maker.Maker().label())\n")
    bound, notes, reject = probe_names.prepare_calls(code, base)
    assert reject is None
    filled = [note for note in notes if note.get("filled")]
    assert filled and filled[0]["how"] == "filled"
    assert filled[0]["filled"][0]["parameter"] == "initial"
    assert "from-base" in bound and "from-pr" not in bound
    assert "names[0]" not in bound
    ran = _run(bound, base, tmp_path / "run")
    assert ran.returncode == 0, ran.stderr
    assert ran.stdout.strip() == "from-base"
    # The same tree's signature, with the required argument omitted and no call that shows it, is not run.
    lone = tmp_path / "lone"
    _write(lone, {
        "widget/__init__.py": "",
        "widget/needs.py": "class Needs:\n    def __init__(self, key):\n        self.key = key\n",
    })
    omitted = "import widget.needs as needs\nprint(needs.Needs())\n"
    _again, _notes, reason = probe_names.prepare_calls(omitted, lone)
    assert reason and "missing required" in reason and "not run" in reason
    assert probe_names.problems(omitted, lone)


def test_omission_abstains_and_a_real_difference_still_needs_attention(tmp_path):
    """A call that cannot be bound covers nothing and does not need attention.

    A different probe that really sees base 1 and the pull request 2, against a claim that the
    result stays the same, still needs attention. The abstained call does not hide that."""
    lone = tmp_path / "lone"
    _write(lone, {
        "widget/__init__.py": "",
        "widget/needs.py": "class Needs:\n    def __init__(self, key):\n        self.key = key\n",
    })
    _code, _notes, reason = probe_names.prepare_calls(
        "import widget.needs as needs\nprint(needs.Needs())\n", lone)
    assert reason
    blocked = probe_names.unusable_item("model-p1", "model", "model-p1.py", reason)
    blocked["claims"] = [{"id": "C1", "text": "the message changes", "covers": ["c1.error"], "expect": "differs"}]
    assert blocked["status"] == "not_run"
    assert blocked["observations"] == []
    assert blocked["probe_changed_line_coverage"]["changed_lines_covered"] == 0
    verdict, _why, _flags = verdict_for(
        _cmp_verified(), None, probe_results={"status": "ran", "items": [blocked]})
    gated = ai_probe_gate({
        "verdict": verdict, "reason": _why, "baseline": "full",
        "probes": {"status": "ran", "items": [blocked]},
    })["verdict"]
    assert gated != "needs_attention"

    base, pr = tmp_path / "base", tmp_path / "pr"
    _maker_tree(base, "from-base", 1)
    _maker_tree(pr, "from-base", 2)
    score = ("import json\nimport widget.maker as maker\n"
             "print(json.dumps({'observations': {'c1.value': maker.score()}}))\n")
    bound, notes, reject = probe_names.prepare_calls(score, base)
    assert reject is None and notes == [] and "score" in bound
    spec = {"id": "model-score", "target": "o/r#1", "about": "score", "claims": [
        {"id": "C1", "text": "score stays the same", "covers": ["c1.value"], "expect": "same"}]}
    path = tmp_path / "score.py"
    path.write_text('PROBE = {"id": "model-score", "target": "o/r#1", "about": "score", "claims": []}\n' + bound)

    def once(root):
        env = os.environ.copy()
        env["PYTHONPATH"] = str(root)
        env.pop("PYTHONSAFEPATH", None)
        cwd = tmp_path / "out"
        cwd.mkdir(parents=True, exist_ok=True)
        obs, _log, _secs = probes.run_once(path, Path(sys.executable), cwd, env, 30)
        return obs

    main_obs, pr_obs = once(base), once(pr)
    assert main_obs["c1.value"] == 1 and pr_obs["c1.value"] == 2
    item = probes.entry(spec, {"main": [main_obs] * 3, "pr": [pr_obs] * 3},
                        {"main": ["m"], "pr": ["p"]}, [], "model", path)
    item["probe_changed_line_coverage"] = {
        "status": "measured", "changed_lines_total": 1, "changed_lines_covered": 1, "adequacy": "adequate"}
    both, reason_both, _flags = verdict_for(
        _cmp_verified(), None, probe_results={"status": "ran", "items": [blocked, item]})
    assert both == "needs_attention" and "c1.value" in reason_both


def test_retry_shows_the_base_call_and_binds_when_the_model_repeats_it(tmp_path):
    """The one existing retry is told the base call. A second invented call is bound, not run as written.

    A later answer that already matches the signature is kept, including a value the base call does not use."""
    base = tmp_path / "base"
    _maker_tree(base, "from-base", 1)
    (tmp_path / "pr").mkdir()
    bad = _probe(_bad_maker())
    prov = Sequence([[bad], [bad]])
    out = model_probes.generate(prov, "o/r", 1, "Keep answer", BODY,
                                {"widget/maker.py": base / "widget" / "maker.py"}, base,
                                [tmp_path / "pr"], tmp_path / "out")
    assert prov.probe_calls == 2
    assert "called in" in prov.users[1] and "initial=" in prov.users[1]
    # The repeated answer still has the unknown keyword. It is not rewritten into a constructor
    # that merely runs, and no probe file is written.
    assert out["probes"] == []
    assert any("not run" in err for err in out["errors"])
    assert not list((tmp_path / "out").glob("*.py"))

    sound = _probe("import json\nimport widget.maker as maker\n"
                   "value = maker.Maker(initial=maker.Context('other')).label()\n"
                   "print(json.dumps({'observations': {'c1.value': value}}))\n")
    prov2 = Sequence([[_probe(_bad_maker())], [sound]])
    out2 = model_probes.generate(prov2, "o/r", 1, "Keep answer", BODY,
                                 {"widget/maker.py": base / "widget" / "maker.py"}, base,
                                 [tmp_path / "pr"], tmp_path / "out2")
    assert prov2.probe_calls == 2
    kept = out2["probes"][0]["path"].read_text()
    assert "other" in kept and "from-base" not in kept
    assert "call_bindings" not in out2


def test_unconnected_signature_binds_its_own_call(tmp_path):
    """A different callable, with two required arguments, is bound from its own test and runs."""
    root = tmp_path / "base"
    _write(root, {
        "widget/__init__.py": "",
        "widget/calc.py": "def blend(left, right, scale=1):\n    return (left + right) * scale\n",
        "tests/test_calc.py": "from widget.calc import blend\n\ndef test_blend():\n    assert blend(2, 3) == 5\n",
    })
    refused = "import widget.calc as calc\nprint(calc.blend(width=4))\n"
    assert any("unexpected keyword" in msg for msg in probe_names.problems(refused, root))
    _same, no_notes, reason = probe_names.prepare_calls(refused, root)
    assert reason and "not removed" in reason and no_notes == []
    code = "import widget.calc as calc\nprint(calc.blend(2))\n"
    bound, notes, reject = probe_names.prepare_calls(code, root)
    assert reject is None and notes[0]["how"] == "filled"
    assert notes[0]["filled"][0]["parameter"] == "right"
    ran = _run(bound, root, tmp_path / "run")
    assert ran.returncode == 0, ran.stderr
    assert ran.stdout.strip() == "5"
    assert "width" not in bound


def test_reexport_uses_the_defining_signature(tmp_path):
    """A name imported from another module is checked as the class that defines it."""
    root = tmp_path / "base"
    _write(root, {
        "widget/__init__.py": "",
        "widget/engine.py": (
            "class Unit:\n"
            "    def __init__(self, initial, core=None):\n"
            "        self.initial = initial\n"
        ),
        "widget/api.py": "from .engine import Unit\n",
        "tests/test_engine.py": (
            "from widget.engine import Unit\n\n"
            "def test_unit():\n"
            "    made = Unit(initial='ok')\n"
            "    assert made.initial == 'ok'\n"
        ),
    })
    bad = "import widget.api as api\nprint(api.Unit(contexts=['x']).initial)\n"
    text = " ".join(probe_names.problems(bad, root))
    assert "unexpected keyword" in text and "contexts" in text and "initial" in text
    _same, no_notes, reason = probe_names.prepare_calls(bad, root)
    assert reason and "not removed" in reason and no_notes == []
    code = "import widget.api as api\nprint(api.Unit().initial)\n"
    bound, notes, reject = probe_names.prepare_calls(code, root)
    assert reject is None and notes[0]["how"] == "filled"
    assert notes[0]["filled"][0]["parameter"] == "initial"
    ran = _run(bound, root, tmp_path / "run")
    assert ran.returncode == 0, ran.stderr
    assert ran.stdout.strip() == "ok"


def test_heldout_fixture_does_not_steal_another_call(tmp_path):
    """A probe whose only argument is an unknown keyword is not replaced by the fixture's real call."""
    spec = json.loads(HELD.read_text())
    root = tmp_path / "base"
    _write(root, spec["files"])
    bound, notes, reject = probe_names.prepare_calls(spec["probe"], root)
    assert reject and "not run" in reject and notes == []
    assert bound == spec["probe"]
    assert spec["expect"] not in bound


def test_real_base_parser_call_is_cited_and_not_substituted(tmp_path):
    """The base test's Parser(contexts=[mytask]) is a real call. It is not pasted over a different probe.

    An unknown keyword is not deleted to leave a constructor that merely runs. A probe whose only
    argument is unknown is not rewritten to Parser() or to mytask, and the reason names the base
    call that was left unused. That result is not coverage. A constructor does not call parse_argv."""
    root = tmp_path / "base"
    shutil.copytree(PARSER_BASE, root)
    kept = ("from invoke.parser import Parser, Context\n"
            "p = Parser(contexts=[Context(name='invoke', aliases=(), help={'task': 'lag'})], not_a_param=1)\n"
            "print(p.contexts[0].name)\n")
    bound, notes, reject = probe_names.prepare_calls(kept, root)
    assert reject and "not removed" in reject and "not run" in reject
    assert notes == [] and bound == kept
    assert "parse_argv" not in bound

    bare = "from invoke.parser import Parser\nprint(Parser(not_a_param=1))\n"
    again, notes2, reason = probe_names.prepare_calls(bare, root)
    assert reason and "not run" in reason and "not copied" in reason
    assert "parser_parser.py" in reason and "contexts" in reason
    assert notes2 == [] and again == bare
    assert "mytask" not in again
    blocked = probe_names.unusable_item("model-p1", "model", "model-p1.py", reason)
    blocked["claims"] = [{"id": "C1", "text": "the message changes", "covers": ["c1.error"], "expect": "differs"}]
    assert blocked["observations"] == []
    assert blocked["probe_changed_line_coverage"]["changed_lines_covered"] == 0
    verdict, why, _flags = verdict_for(
        _cmp_verified(), None, probe_results={"status": "ran", "items": [blocked]})
    gated = ai_probe_gate({
        "verdict": verdict, "reason": why, "baseline": "full",
        "probes": {"status": "ran", "items": [blocked]},
    })["verdict"]
    assert gated != "needs_attention"


def test_required_parameter_before_star_is_still_required(tmp_path):
    """def f(first, second=0, *rest): f() is missing first. f(1) is valid. *rest does not waive first.

    The call is not written with a star. A base call f('seen', 0) fills only first. second is not
    copied. With no such call, f() is not run."""
    root = tmp_path / "base"
    _write(root, {
        "pkg/__init__.py": "",
        "pkg/m.py": "def f(first, second=0, *rest):\n    return first\n",
        "tests/test_m.py": "from pkg.m import f\n\ndef test_f():\n    assert f('seen', 0) == 'seen'\n",
    })
    empty = "import pkg.m as m\nprint(m.f())\n"
    one = "import pkg.m as m\nprint(m.f(1))\n"
    assert any("missing required" in msg and "first" in msg for msg in probe_names.problems(empty, root))
    assert probe_names.problems(one, root) == []
    assert probe_names.prepare_calls(one, root)[0] == one
    bound, notes, reject = probe_names.prepare_calls(empty, root)
    assert reject is None and notes[0]["how"] == "filled"
    assert [item["parameter"] for item in notes[0]["filled"]] == ["first"]
    assert "seen" in bound and "second" not in bound
    lone = tmp_path / "lone"
    _write(lone, {"pkg/__init__.py": "", "pkg/m.py": "def f(first, second=0, *rest):\n    return first\n"})
    again, no_notes, reason = probe_names.prepare_calls(empty, lone)
    assert reason and "not run" in reason and "first" in reason and no_notes == []
    assert again == empty


def test_unchecked_calls_and_unreadable_inheritance_are_not_run(tmp_path):
    """A base call whose arguments cannot be checked is not run. A readable call is unchanged."""
    root = tmp_path / "base"
    _write(root, {
        "pkg/__init__.py": "",
        "pkg/base.py": (
            "class Parent:\n"
            "    def __init__(self, left):\n"
            "        self.left = left\n"
            "    def run(self, left):\n"
            "        return left\n"
        ),
        "pkg/child.py": "from .base import Parent\nclass Child(Parent):\n    pass\n",
        "pkg/flex.py": "def bag(**kwargs):\n    return kwargs\n",
    })
    star = "import pkg.flex as flex\nprint(flex.bag(width=1))\n"
    _same, notes, reason = probe_names.prepare_calls(star, root)
    assert reason and "**kwargs" in reason and "not run" in reason and notes == []
    spread = "import pkg.flex as flex\nprint(flex.bag(*[1]))\n"
    # *args on a **kwargs function is also unchecked. A visible call of a required function is not.
    assert probe_names.prepare_calls(spread, root)[2]
    hidden = "import pkg.child as child\nprint(child.Child(1).left)\n"
    reason = probe_names.prepare_calls(hidden, root)[2]
    assert reason and "not run" in reason and "cannot check" in reason
    method = "import pkg.child as child\nprint(child.Child.run(None, 1))\n"
    reason = probe_names.prepare_calls(method, root)[2]
    assert reason and "cannot check" in reason


# Verbatim from pyinvoke/invoke 0da941e176f4e0b28d8a69b8ac089cdbac2874e4.
# argument.py property name, and parser.py ParseMachine.complete_context.
_BASE_NAME = "return self.attr_name or self.names[0]\n"
_BASE_FORMAT = "names = ', '.join(\"'{}'\".format(x.name) for x in missing)\n"
_PR_FORMAT = "names = ', '.join(\"'{}'\".format(x.names[0]) for x in missing)\n"


def _format_missing(source: str, args: list[dict]) -> tuple[str, bool]:
    """Run one side's error line. Returns (message, whether that line ran)."""
    reached = {"line": False}

    def trace(frame, event, arg):
        if event == "line" and frame.f_code.co_name == "format_missing":
            reached["line"] = True
        return trace

    namespace: dict = {}
    exec("class Arg:\n"
         "    def __init__(self, names, attr_name=None):\n"
         "        self.names = tuple(names)\n"
         "        self.attr_name = attr_name\n"
         "    @property\n"
         "    def name(self):\n"
         f"        {_BASE_NAME}"
         "def format_missing(missing, task):\n"
         f"    {source}"
         "    return \"'{}' did not receive required positional arguments: {}\".format(task, names)\n",
         namespace)
    import sys
    sys.settrace(trace)
    try:
        built = [namespace["Arg"](item["names"], item.get("attr_name")) for item in args]
        message = namespace["format_missing"](built, "mytask")
    finally:
        sys.settrace(None)
    return message, reached["line"]


def test_real_base_parse_call_reaches_the_name_line_and_a_constructor_does_not():
    """The base call that omits a positional reaches the error line. Parser() does not.

    Argument('pos') has the same text on both sides, because name and names[0] are both 'pos'.
    An attribute name that differs from the first public name is the line the pull request edits.
    Reaching the line is not a verdict, and a constructor is not that call."""
    positional = [{"names": ("pos",)}]
    base_pos, base_hit = _format_missing(_BASE_FORMAT, positional)
    pr_pos, pr_hit = _format_missing(_PR_FORMAT, positional)
    assert base_hit and pr_hit
    assert base_pos == pr_pos == "'mytask' did not receive required positional arguments: 'pos'"
    dashed = [{"names": ("param-1", "p"), "attr_name": "param_1"}]
    base_dash, base_dash_hit = _format_missing(_BASE_FORMAT, dashed)
    pr_dash, pr_dash_hit = _format_missing(_PR_FORMAT, dashed)
    assert base_dash_hit and pr_dash_hit
    assert base_dash.endswith("'param_1'")
    assert pr_dash.endswith("'param-1'")
    assert base_dash != pr_dash
    # The real package at that commit, when it is on disk, agrees on the positional message.
    real = Path("/tmp/invoke-base")
    if (real / "invoke" / "parser" / "parser.py").is_file():
        env = os.environ.copy()
        env["PYTHONPATH"] = str(real)
        script = (
            "from invoke.parser import Parser, Context, Argument, ParseError\n"
            "arg = Argument('pos', positional=True)\n"
            "task = Context(name='mytask', args=[arg])\n"
            "hit = False\n"
            "def trace(frame, event, arg):\n"
            "    global hit\n"
            "    if event == 'line' and frame.f_code.co_name == 'complete_context':\n"
            "        hit = True\n"
            "    return trace\n"
            "import sys\n"
            "sys.settrace(trace)\n"
            "try:\n"
            "    Parser(contexts=[task]).parse_argv(['mytask'])\n"
            "except ParseError as exc:\n"
            "    print(hit)\n"
            "    print(str(exc))\n"
            "finally:\n"
            "    sys.settrace(None)\n"
            "print('constructor', Parser().ignore_unknown)\n"
        )
        ran = subprocess.run([sys.executable, "-c", script], env=env, capture_output=True, text=True, timeout=30)
        assert ran.returncode == 0, ran.stderr
        lines = ran.stdout.splitlines()
        assert lines[0] == "True"
        assert lines[1] == "'mytask' did not receive required positional arguments: 'pos'"
        assert lines[2] == "constructor False"


def test_bad_keyword_with_only_defaults_is_not_rewritten_to_the_default_call(tmp_path):
    """Deleting the only argument would leave the default call. That is not this probe, so it is not run."""
    root = tmp_path / "base"
    _write(root, {
        "widget/__init__.py": "",
        "widget/calc.py": "def ready(scale=1):\n    return scale\n",
        "tests/test_calc.py": "from widget.calc import ready\n\ndef test_ready():\n    assert ready() == 1\n",
    })
    code = "import widget.calc as calc\nprint(calc.ready(width=4))\n"
    bound, notes, reject = probe_names.prepare_calls(code, root)
    assert reject and "not run" in reject and "not copied" in reject
    assert notes == [] and bound == code
    blocked = probe_names.unusable_item("model-p1", "model", "model-p1.py", reject)
    assert blocked["status"] == "not_run"
    assert blocked["probe_changed_line_coverage"]["changed_lines_covered"] == 0
