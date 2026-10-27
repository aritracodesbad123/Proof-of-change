"""Product route: a PR that changes only comments or docs is verified without a full check."""
import argparse
import difflib

from ops import daily_run as dr
from poc import comment_only as co


def _diff(files):
    """files: {path: (base, head)} -> unified git diff text."""
    out = []
    for path, (base, head) in files.items():
        out.append(f"diff --git a/{path} b/{path}\n")
        out.extend(difflib.unified_diff(base.splitlines(True), head.splitlines(True), f"a/{path}", f"b/{path}", n=1))
    return "".join(out)


def _run(files, title="Tidy", body="", doc_tests=None, monkeypatch=None):
    item = {"diff": _diff(files), "title": title, "body": body, "head_sha": "h" * 40, "base_sha": "b" * 40}
    reader = lambda side, path: files[path][0 if side == "base" else 1]  # noqa: E731
    monkeypatch.setattr(dr, "finish", lambda rec, *a, **k: rec)
    rec = {}
    a = argparse.Namespace()
    called = []
    tests = doc_tests or (lambda *x: called.append(x) or (True, "doc tests passed"))
    return dr.comment_only_fast_path("o/r", item, rec, None, None, 0.0, a, reader=reader, doc_tests=tests), called


BASE = "def f(x):\n    # add one\n    return x + 1\n\n\ny = 2\n"


def test_comment_only_is_verified_with_lines(monkeypatch):
    head = "def f(x):\n    # add one to x\n    return x + 1\n\n\n# the answer\ny = 2\n"
    rec, called = _run({"pkg/m.py": (BASE, head)}, monkeypatch=monkeypatch)
    assert rec["verdict"] == "verified" and rec["fast_path"] == "comment_only"
    assert rec["reason"].startswith("Comment-only change: no code was altered.")
    assert "pkg/m.py lines 2, 6" in rec["reason"]
    assert rec["fast_path_lines"]["comments"] == {"pkg/m.py": [2, 6]}
    assert called == []   # no sandbox for comments


def test_docstring_change_runs_doc_tests(monkeypatch):
    head = 'def f(x):\n    """Add one."""\n    # add one\n    return x + 1\n\n\ny = 2\n'
    rec, called = _run({"pkg/m.py": (BASE, head)}, monkeypatch=monkeypatch)
    assert len(called) == 1 and rec["fast_path"] == "docstring_only"
    assert rec["verdict"] == "verified" and "Documentation text only" in rec["reason"]


def test_docstring_change_with_failing_doc_tests_takes_normal_path(monkeypatch):
    head = 'def f(x):\n    """Add one."""\n    # add one\n    return x + 1\n\n\ny = 2\n'
    rec, _ = _run({"pkg/m.py": (BASE, head)}, doc_tests=lambda *x: (False, "doc tests failed (exit 1)"),
                  monkeypatch=monkeypatch)
    assert rec is None


def test_code_and_comment_change_takes_normal_path(monkeypatch):
    head = "def f(x):\n    # add two\n    return x + 2\n\n\ny = 2\n"
    assert _run({"pkg/m.py": (BASE, head)}, monkeypatch=monkeypatch)[0] is None


def test_value_changed_beside_trailing_comment_takes_normal_path(monkeypatch):
    base = "x = 1  # comment\n"
    assert _run({"pkg/m.py": (base, "x = 2  # comment\n")}, monkeypatch=monkeypatch)[0] is None


def test_code_hidden_in_non_docstring_string_takes_normal_path(monkeypatch):
    base = 'def f():\n    x = 1\n    s = """\n    # looks like a comment\n    """\n    return s\n'
    head = 'def f():\n    x = 1\n    s = """\n    # looks like a comment, edited\n    """\n    return s\n'
    assert _run({"pkg/m.py": (base, head)}, monkeypatch=monkeypatch)[0] is None


def test_docs_only_is_verified(monkeypatch):
    rec, _ = _run({"README.md": ("# A\nold\n", "# A\nnew\n"), "docs/guide.txt": ("a\n", "b\n")},
                  monkeypatch=monkeypatch)
    assert rec["verdict"] == "verified" and rec["fast_path"] == "comment_only"
    assert "Docs changed in README.md lines 2" in rec["reason"]
    assert "docs changed in docs/guide.txt lines 1" in rec["reason"]


def test_docs_conf_py_is_code(monkeypatch):
    assert co.is_doc_file("docs/conf.py") is False
    files = {"docs/conf.py": ("project = 'a'\n", "project = 'b'\n")}
    assert _run(files, monkeypatch=monkeypatch)[0] is None
    # a comment-only edit to docs/conf.py is still judged as Python, by its syntax tree
    rec, _ = _run({"docs/conf.py": ("x = 1\n", "# note\nx = 1\n")}, monkeypatch=monkeypatch)
    assert rec["fast_path_lines"]["comments"] == {"docs/conf.py": [1]}


def test_parse_failure_takes_normal_path(monkeypatch):
    assert _run({"pkg/m.py": (BASE, "def f(:\n")}, monkeypatch=monkeypatch)[0] is None


def test_config_files_take_normal_path(monkeypatch):
    for path in ("setup.cfg", "pyproject.toml"):
        assert _run({path: ("[a]\nx=1\n", "[a]\n# c\nx=1\n")}, monkeypatch=monkeypatch)[0] is None


def test_claimed_fix_with_comment_only_needs_attention(monkeypatch):
    head = "def f(x):\n    # add one to x\n    return x + 1\n\n\ny = 2\n"
    rec, _ = _run({"pkg/m.py": (BASE, head)}, title="Fix crash when x is None", monkeypatch=monkeypatch)
    assert rec["verdict"] == "needs_attention" and "does not do what it says" in rec["reason"]


def test_doc_wording_is_not_a_behaviour_claim():
    assert co.claimed_behaviour_change("Fix typo in comment", "Adds a docstring link") is None
    assert co.claimed_behaviour_change("Docs", "This fixes the parser bug") is not None


def test_renamed_or_new_code_file_takes_normal_path():
    diff = "diff --git a/pkg/a.py b/pkg/b.py\nsimilarity index 100%\nrename from pkg/a.py\nrename to pkg/b.py\n"
    assert co.classify(diff, lambda s, p: "x = 1\n") is None
    diff = "diff --git a/pkg/n.py b/pkg/n.py\nnew file mode 100644\n--- /dev/null\n+++ b/pkg/n.py\n@@ -0,0 +1 @@\n+# hi\n"
    assert co.classify(diff, lambda s, p: "# hi\n") is None


def test_fast_path_only_on_product_route():
    src = open(dr.__file__).read()
    i = src.index("done = comment_only_fast_path(")
    assert "if product_route(a):" in src[i - 80:i]
