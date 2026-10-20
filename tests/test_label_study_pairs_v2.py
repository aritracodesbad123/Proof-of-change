"""The revised library label follows the written rule and leaves the pair list alone."""
import hashlib
import json
from pathlib import Path

from evals.label_study_pairs_v2 import (
    LookupFailed,
    candidates_from,
    counts,
    label_pairs,
    label_repo,
    main,
    names_from_pyproject,
    names_from_setup_cfg,
    names_from_setup_py,
    retry_call,
)

ROOT = Path(__file__).resolve().parent.parent
PAIRS = ROOT / "evals" / "study_pairs" / "main-study-pairs.json"
RULE = ROOT / "evals" / "study_pairs" / "library_label_rule_v2.md"


class FakeIndex:
    def __init__(self, files=None, pypi=None, branch="main", missing_repo=False, fail=None):
        self.files = files or {}
        self._pypi = pypi or {}
        self.branch = branch
        self.missing_repo = missing_repo
        self.fail = fail or set()
        self.pypi_calls = []

    def repo(self, owner, repo):
        self._maybe_fail("repo")
        if self.missing_repo:
            return None
        return {"default_branch": self.branch}

    def tree(self, owner, repo, branch):
        self._maybe_fail("tree")
        assert branch == self.branch
        return list(self.files)

    def file(self, owner, repo, branch, path):
        self._maybe_fail("file:" + path)
        return self.files[path]

    def pypi(self, name):
        self._maybe_fail("pypi:" + name)
        self.pypi_calls.append(name)
        return self._pypi.get(name)

    def _maybe_fail(self, key):
        if key in self.fail:
            raise LookupFailed(key)


def _info(url):
    return {"home_page": url, "project_urls": {}}


def test_setup_py_keeps_quoted_names_only():
    text = 'name = NAME\nsetup(\n    name="sentry-sdk",\n)\nfilename="skip-me"\nname=\'second\'\n'
    assert names_from_setup_py(text) == ["sentry-sdk", "second"]
    assert names_from_pyproject("[project]\nname = 'pkg-a'\n") == ["pkg-a"]
    assert names_from_pyproject("[dependency-groups]\ndev = []\n") == []
    assert names_from_setup_cfg("[METADATA]\nName = Demo\n") == ["Demo"]
    assert names_from_setup_cfg("not a config") == []


def test_declared_name_wins_over_the_repository_name():
    index = FakeIndex(
        files={"pyproject.toml": "[dependency-groups]\ndev=[]\n", "setup.py": 'setup(name="sentry-sdk")\n'},
        pypi={"sentry-sdk": _info("https://GitHub.com/getsentry/sentry-python")},
    )
    hit = label_repo("getsentry", "sentry-python", index)
    assert hit == {"label": "library", "pypi_project": "sentry-sdk", "found_by": "setup.py"}
    assert index.pypi_calls == ["sentry-sdk"]


def test_monorepo_uses_the_first_project_that_links_back():
    index = FakeIndex(
        files={
            "b/pyproject.toml": "[project]\nname='second'\n",
            "a/pyproject.toml": "[project]\nname='first'\n",
            "pkg/setup.cfg": "[metadata]\nname = from-cfg\n",
        },
        pypi={"first": _info("https://example.com/nope"),
              "second": _info("https://github.com/acme/widget.git")},
    )
    hit = label_repo("acme", "widget", index)
    assert hit == {"label": "library", "pypi_project": "second", "found_by": "pyproject.toml"}
    assert index.pypi_calls == ["first", "second"]


def test_repository_name_is_used_when_no_declared_name_links_back():
    index = FakeIndex(
        files={"setup.cfg": "[metadata]\nname = other\n"},
        pypi={"other": None, "widget": _info("https://github.com/acme/widget/")},
    )
    hit = label_repo("acme", "widget", index)
    assert hit == {"label": "library", "pypi_project": "widget", "found_by": "repo_name"}


def test_no_link_is_non_library_and_a_failed_request_is_unknown():
    quiet = FakeIndex(files={}, pypi={"widget": _info("https://github.com/other/widget")})
    assert label_repo("acme", "widget", quiet)["label"] == "non_library"
    assert quiet.pypi_calls == ["widget"]
    broken = FakeIndex(fail={"tree"})
    assert label_repo("acme", "widget", broken) == {"label": "unknown", "pypi_project": None, "found_by": None}
    absent = FakeIndex(missing_repo=True, pypi={"widget": None})
    assert label_repo("acme", "widget", absent)["label"] == "non_library"


def test_retry_runs_twice_and_keeps_a_later_success():
    calls = {"n": 0}

    def fail():
        calls["n"] += 1
        raise LookupFailed("down")

    try:
        retry_call(fail, sleep=lambda _s: None)
    except LookupFailed:
        pass
    else:
        raise AssertionError("expected failure")
    assert calls["n"] == 2

    def recover():
        calls["n"] += 1
        if calls["n"] < 4:
            raise LookupFailed("down")
        return "ok"

    assert retry_call(recover, sleep=lambda _s: None) == "ok"


def test_pairs_keep_order_and_the_list_file_is_not_written(tmp_path):
    before = PAIRS.read_bytes()
    index = FakeIndex(pypi={"widget": _info("https://github.com/acme/widget")})
    pairs = [{"repo": "acme/widget", "agent_pr": 2, "human_pr": 3},
             {"repo": "not a repo", "agent_pr": 4, "human_pr": 5},
             {"repo": "acme/widget", "agent_pr": 6, "human_pr": 7}]
    labelled = label_pairs(pairs, index)
    assert [item["agent_pr"] for item in labelled] == [2, 4, 6]
    assert labelled[0]["label"] == "library" and labelled[1]["label"] == "non_library"
    assert labelled[0]["found_by"] == "repo_name"
    assert counts(labelled)["library"] == 2
    assert index.pypi_calls == ["widget"]
    src = tmp_path / "pairs.json"
    src.write_text(json.dumps(pairs))
    out = tmp_path / "out.json"
    import evals.label_study_pairs_v2 as mod
    original = mod.Index
    mod.Index = lambda: index
    try:
        assert main(["--pairs", str(src), "--rule", str(RULE), "--out", str(out), "--only", "acme/widget"]) == 0
    finally:
        mod.Index = original
    written = json.loads(out.read_text())
    assert [item["agent_pr"] for item in written] == [2, 6]
    assert PAIRS.read_bytes() == before
    assert main(["--pairs", str(src), "--rule", str(tmp_path / "missing.md"), "--out", str(out)]) == 2


def test_recorded_sentry_python_is_library_through_sentry_sdk():
    rows = json.loads((ROOT / "evals" / "study_pairs" / "pair-labels-v2.json").read_text())
    hits = [row for row in rows if row["repo"] == "getsentry/sentry-python"]
    assert len(hits) == 1
    assert hits[0]["label"] == "library"
    assert hits[0]["pypi_project"] == "sentry-sdk"
    assert hits[0]["found_by"] == "setup.py"
    assert hits[0]["agent_pr"] == 4476 and hits[0]["human_pr"] == 4485


def test_readme_records_the_v2_rule_hash():
    digest = hashlib.sha256(RULE.read_bytes()).hexdigest()
    assert digest in (ROOT / "evals" / "study_pairs" / "README.md").read_text()


def test_candidates_follow_file_order():
    index = FakeIndex(files={
        "z/setup.py": 'name="from-setup"\n',
        "a/setup.cfg": "[metadata]\nname = from-cfg\n",
        "m/pyproject.toml": "[project]\nname='from-project'\n",
    })
    assert candidates_from("acme", "widget", index) == [
        ("from-project", "pyproject.toml"),
        ("from-cfg", "setup.cfg"),
        ("from-setup", "setup.py"),
        ("widget", "repo_name"),
    ]
