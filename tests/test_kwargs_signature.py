"""Named parameters stay checked when a definition also accepts *args or **kwargs.

Extra keywords flow into **kwargs and extra positionals flow into *args, and the probe runs.
A keyword that is not a parameter is still rejected when there is no **kwargs. A call written
with **mapping is not judged. An inherited constructor is checked when the base class can be
read. Dataclass and attrs fields are checked when they can be read, and a generated constructor
whose fields cannot be read is run rather than rejected.

The fixtures follow real signatures (a table constructor, a task collection, a frozen config,
a file sink, a composer, a spooled buffer, an exception, a header map) without naming a library
in the rule. Nothing here calls a model.
"""
import os
import sys
from pathlib import Path

from ops.daily_run import compare_sides, gate, verdict_for
from poc import probe_names, probes

_TREE = {
    "pkg/__init__.py": "",
    "pkg/table.py": (
        "class Table:\n"
        "    def __init__(self, field_names=None, **kwargs):\n"
        "        self.field_names = field_names\n"
        "        self.rest = kwargs\n"
    ),
    "pkg/tasks.py": (
        "class Collection:\n"
        "    def __init__(self, *args, **kwargs):\n"
        "        self.args = args\n"
        "        self.kwargs = kwargs\n"
    ),
    "pkg/sink.py": (
        "class FileSink:\n"
        "    def __init__(self, path, *, rotation=None, retention=None, compression=None,\n"
        "                 delay=False, mode='a', buffering=1, encoding='utf8', **kwargs):\n"
        "        self.path = path\n"
        "        self.rotation = rotation\n"
        "        self.rest = kwargs\n"
        "\n"
        "def open_sink(path, *, rotation, **kwargs):\n"
        "    return path, rotation, kwargs\n"
    ),
    "pkg/headers.py": (
        "class HeaderDict:\n"
        "    def __init__(self, headers=None, **kwargs):\n"
        "        self.headers = headers\n"
        "        self.rest = kwargs\n"
    ),
    "pkg/urls.py": (
        "class URL:\n"
        "    def __init__(self, url='', /, **kwargs):\n"
        "        allowed = {'host'}\n"
        "        for key in kwargs:\n"
        "            if key not in allowed:\n"
        "                raise TypeError(f'{key!r} is an invalid keyword argument for URL()')\n"
        "        self.url = url\n"
        "        self.rest = kwargs\n"
    ),
    "pkg/compose.py": (
        "def compose(*funcs):\n"
        "    return funcs\n"
    ),
    "pkg/errors.py": (
        "class RequestException(OSError):\n"
        "    def __init__(self, *args, **kwargs):\n"
        "        self.request = kwargs.get('request')\n"
        "        super().__init__(*args)\n"
        "\n"
        "class ConnectionError(RequestException):\n"
        "    pass\n"
    ),
    "pkg/buffers.py": (
        "class SpooledIOBase:\n"
        "    def __init__(self, max_size=5000000):\n"
        "        self.max_size = max_size\n"
        "\n"
        "class SpooledStringIO(SpooledIOBase):\n"
        "    def __init__(self, *args, **kwargs):\n"
        "        super().__init__(*args, **kwargs)\n"
    ),
    "pkg/settings.py": (
        "from dataclasses import dataclass, field\n"
        "\n"
        "@dataclass(frozen=True)\n"
        "class _Config:\n"
        "    line_length: int = 79\n"
        "    known_other: dict = field(default_factory=dict)\n"
        "    skip: bool = False\n"
        "\n"
        "class Config(_Config):\n"
        "    def __init__(self, settings_file='', settings_path='', config=None, **config_overrides):\n"
        "        self.settings_file = settings_file\n"
        "        self.overrides = config_overrides\n"
    ),
    "pkg/rows.py": (
        "from dataclasses import dataclass\n"
        "\n"
        "@dataclass\n"
        "class BaseRow:\n"
        "    name: str\n"
        "    kind: str = 'a'\n"
    ),
    "pkg/child_row.py": (
        "from dataclasses import dataclass\n"
        "from .rows import BaseRow\n"
        "\n"
        "@dataclass\n"
        "class ChildRow(BaseRow):\n"
        "    extra: int = 0\n"
    ),
    "pkg/opaque.py": (
        "from dataclasses import dataclass, field\n"
        "\n"
        "FLAG = True\n"
        "\n"
        "@dataclass\n"
        "class Dynamic:\n"
        "    name: str = field(init=FLAG)\n"
    ),
    "pkg/boxes.py": (
        "import attr\n"
        "\n"
        "@attr.define\n"
        "class Box:\n"
        "    width: int\n"
        "    height: int = 1\n"
        "\n"
        "@attr.s\n"
        "class Legacy:\n"
        "    width = attr.ib()\n"
        "    height = attr.ib(default=1)\n"
    ),
    "pkg/auth.py": (
        "from typing import overload\n"
        "\n"
        "class Auth:\n"
        "    @overload\n"
        "    def __init__(self, username: str, password: str) -> None: ...\n"
        "    @overload\n"
        "    def __init__(self, username: bytes, password: bytes) -> None: ...\n"
        "    def __init__(self, username, password):\n"
        "        self.username = username\n"
        "        self.password = password\n"
    ),
    "pkg/records.py": (
        "from typing import NamedTuple\n"
        "\n"
        "class Row(NamedTuple):\n"
        "    name: str\n"
        "    kind: str = 'a'\n"
    ),
    "pkg/jars.py": (
        "from http.cookiejar import CookieJar\n"
        "\n"
        "class Jar(CookieJar):\n"
        "    pass\n"
    ),
    "pkg/plain.py": (
        "class Plain:\n"
        "    pass\n"
        "\n"
        "def tagged(cls):\n"
        "    return cls\n"
        "\n"
        "@tagged\n"
        "class Tagged:\n"
        "    pass\n"
    ),
    "pkg/make.py": (
        "def make(name, **kwargs):\n"
        "    return name, kwargs\n"
    ),
    "tests/test_make.py": (
        "from pkg.make import make\n"
        "\n"
        "def test_make():\n"
        "    assert make('seen')[0] == 'seen'\n"
    ),
}


def _tree(root: Path) -> None:
    for rel, text in _TREE.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)


def _call(code: str, root: Path):
    return probe_names.prepare_calls(code, root)


def _ok(code: str, root: Path) -> None:
    bound, notes, reject = _call(code, root)
    assert reject is None, reject
    assert notes == []
    assert bound == code
    assert probe_names.problems(code, root) == []


def _bad(code: str, root: Path, *needles: str) -> str:
    text = " ".join(probe_names.problems(code, root))
    _bound, _notes, reason = _call(code, root)
    assert reason and "not run" in reason
    for needle in needles:
        assert needle in text or needle in reason
    return reason


def test_declared_names_are_checked_and_extra_keywords_run(tmp_path):
    """A real parameter is accepted. An extra keyword flows into **kwargs and the probe runs.

    A positional-only name passed as a keyword is still rejected. A missing required parameter
    is still rejected. Too many positionals are still rejected when there is no *args."""
    root = tmp_path / "base"
    _tree(root)
    _ok("import pkg.table as table\nprint(table.Table(field_names=['a'], align='l'))\n", root)
    _ok("import pkg.table as table\nprint(table.Table(align='l'))\n", root)
    _ok("import pkg.headers as headers\nprint(headers.HeaderDict({'A': 'b'}, Host='x'))\n", root)
    _ok("import pkg.sink as sink\nprint(sink.FileSink('p', rotation=10, newline='\\n'))\n", root)
    _ok("import pkg.sink as sink\nprint(sink.FileSink(path='p', newline='\\n'))\n", root)
    _ok("import pkg.sink as sink\nprint(sink.open_sink('p', rotation=1, newline='\\n'))\n", root)
    _bad("import pkg.sink as sink\nprint(sink.open_sink('p', newline='\\n'))\n", root, "rotation")
    _ok("import pkg.urls as urls\nprint(urls.URL('http://example', host='h'))\n", root)
    _bad("import pkg.urls as urls\nprint(urls.URL(url='http://example'))\n", root, "url")
    _bad("import pkg.sink as sink\nprint(sink.FileSink(rotation=10))\n", root, "path")
    _bad("import pkg.sink as sink\nprint(sink.FileSink('p', 'nope'))\n", root, "positional")
    _bad("import pkg.plain as plain\nprint(plain.Plain(x=1))\n", root, "x")
    _bad("import pkg.plain as plain\nprint(plain.Tagged(x=1))\n", root, "x")


def test_star_args_run_when_the_definition_accepts_them_and_mapping_does_not(tmp_path):
    """compose(*funcs) and Collection('docs', loaded_from=...) run. **mapping is not judged.

    A keyword compose does not declare is still rejected, because compose has no **kwargs."""
    root = tmp_path / "base"
    _tree(root)
    _ok("import pkg.compose as compose\nprint(compose.compose(1, 2))\n", root)
    _ok("import pkg.compose as compose\nprint(compose.compose(*[1, 2]))\n", root)
    _bad("import pkg.compose as compose\nprint(compose.compose(1, name=1))\n", root, "name")
    _ok("import pkg.tasks as tasks\nprint(tasks.Collection('docs', loaded_from='x'))\n", root)
    _ok("import pkg.tasks as tasks\nprint(tasks.Collection(*['docs']))\n", root)
    _ok("import pkg.errors as errors\nprint(errors.ConnectionError('boom', request=1))\n", root)
    _ok("import pkg.buffers as buffers\nprint(buffers.SpooledStringIO(10, encoding='utf8'))\n", root)
    reason = _bad("import pkg.table as table\nprint(table.Table(**opts))\n", root, "**mapping")
    assert "not judged" not in reason
    assert "cannot be checked" in reason


def test_inherited_constructor_is_checked_and_an_unreadable_one_runs(tmp_path):
    """ChildRow takes BaseRow's fields from the other file. Jar's base is not in this tree.

    Auth's overload stubs are not the constructor; the implementation is. A keyword the
    implementation does not take is rejected."""
    root = tmp_path / "base"
    _tree(root)
    _ok("import pkg.child_row as rows\nprint(rows.ChildRow(name='p', extra=1))\n", root)
    _ok("import pkg.child_row as rows\nprint(rows.ChildRow('p'))\n", root)
    _bad("import pkg.child_row as rows\nprint(rows.ChildRow(nope=1))\n", root, "nope", "name")
    _bad("import pkg.child_row as rows\nprint(rows.ChildRow())\n", root, "name")
    _ok("import pkg.jars as jars\nprint(jars.Jar(policy=1))\n", root)
    _ok("import pkg.auth as auth\nprint(auth.Auth('u', 'p'))\n", root)
    _bad("import pkg.auth as auth\nprint(auth.Auth(token='x'))\n", root, "token", "username")


def test_dataclass_and_attrs_fields_are_checked_when_they_can_be_read(tmp_path):
    """_Config's fields are the constructor. A field that is not there is rejected.

    Dynamic's init flag is not a constant, so its names are not checked and the probe runs.
    Config's own __init__ accepts **config_overrides, so a field name passed to Config runs."""
    root = tmp_path / "base"
    _tree(root)
    _ok("import pkg.settings as settings\nprint(settings._Config(line_length=100))\n", root)
    _ok("import pkg.settings as settings\nprint(settings._Config())\n", root)
    _bad("import pkg.settings as settings\nprint(settings._Config(not_a_field=1))\n", root,
         "not_a_field", "line_length")
    _ok("import pkg.settings as settings\nprint(settings.Config(line_length=100))\n", root)
    _ok("import pkg.boxes as boxes\nprint(boxes.Box(width=2))\n", root)
    _bad("import pkg.boxes as boxes\nprint(boxes.Box(nope=1))\n", root, "nope", "width")
    _bad("import pkg.boxes as boxes\nprint(boxes.Box())\n", root, "width")
    _ok("import pkg.boxes as boxes\nprint(boxes.Legacy(width=2, height=3))\n", root)
    _bad("import pkg.boxes as boxes\nprint(boxes.Legacy(height=3))\n", root, "width")
    _ok("import pkg.records as records\nprint(records.Row(name='p'))\n", root)
    _bad("import pkg.records as records\nprint(records.Row(nope=1))\n", root, "nope", "name")
    _ok("import pkg.opaque as opaque\nprint(opaque.Dynamic(not_readable=1))\n", root)


def test_missing_required_is_filled_and_the_extra_keyword_stays(tmp_path):
    """flag=True is not a parameter of make. It stays, and name is filled from the base call."""
    root = tmp_path / "base"
    _tree(root)
    code = "import pkg.make as make\nprint(make.make(flag=True))\n"
    bound, notes, reject = _call(code, root)
    assert reject is None
    assert notes and notes[0]["how"] == "filled"
    assert notes[0]["filled"][0]["parameter"] == "name"
    assert "seen" in bound and "flag=True" in bound.replace(" ", "")


def test_a_wrong_keyword_raises_on_both_sides_and_is_not_verified(tmp_path):
    """scheme is not a parameter of URL. It flows into **kwargs, the body raises, and both sides match.

    That match is the same exception. It is not evidence, and it does not verify the change."""
    root = tmp_path / "base"
    _tree(root)
    code = (
        "import json\n"
        "import pkg.urls as urls\n"
        "try:\n"
        "    value = urls.URL('http://example', scheme='http')\n"
        "except TypeError as exc:\n"
        "    value = {'raises': type(exc).__name__}\n"
        "print(json.dumps({'observations': {'c1.value': value}}))\n"
    )
    assert _call(code, root)[2] is None
    path = tmp_path / "probe.py"
    path.write_text(code)

    def once(work: Path):
        env = os.environ.copy()
        env["PYTHONPATH"] = str(root)
        env.pop("PYTHONSAFEPATH", None)
        work.mkdir(parents=True, exist_ok=True)
        obs, _log, _secs = probes.run_once(path, Path(sys.executable), work, env, 30)
        return obs

    main_obs, pr_obs = once(tmp_path / "main"), once(tmp_path / "pr")
    assert main_obs == pr_obs == {"c1.value": {"raises": "TypeError"}}
    spec = {"id": "p1", "target": "o/r#1", "about": "url", "claims": [
        {"id": "C1", "text": "the url changes", "covers": ["c1.value"], "expect": "differs"}]}
    item = probes.entry(spec, {"main": [main_obs] * 3, "pr": [pr_obs] * 3},
                        {"main": ["m"], "pr": ["p"]}, [], "model", path)
    assert item["observations"][0].get("probe_broken")
    item["probe_changed_line_coverage"] = {
        "status": "measured", "changed_lines_total": 1, "changed_lines_covered": 1}
    same = {"t::a": ("passed", ""), "t::b": ("passed", "")}
    verdict, why, _flags = verdict_for(
        compare_sides({"main": [same] * 3, "pr": [same] * 3}), None,
        probe_results={"status": "ran", "items": [item]})
    rec = {"verdict": verdict, "reason": why, "baseline": "full",
           "probes": {"status": "ran", "items": [item]}}
    assert gate(rec)["verdict"] != "verified"


def test_rejudging_a_record_does_not_read_the_validator():
    """A stored rejection has no observations. Re-judging that record cannot turn the verdict into verified.

    The rejection text is only a note. The judge reads the saved comparison and the saved probe runs."""
    from evals.checks import derive_verdict
    same = {"t::a": ("passed", ""), "t::b": ("passed", "")}
    record = {
        "verdict": "could_not_verify",
        "reason": "no probe ran",
        "baseline": "full",
        "comparison": compare_sides({"main": [same] * 3, "pr": [same] * 3}),
        "probes": {"status": "none", "items": []},
        "coverage": {"status": "measured", "changed_lines_total": 1, "changed_lines_covered": 1},
        "probe_plan": {"errors": [
            "probe 'p1' rejected: cannot bind pkg.table.Table: Table() accepts **kwargs, "
            "so its keywords cannot be checked; the probe is not run"]},
    }
    assert derive_verdict(record, "full") != "verified"
