"""A pull request is a typing-only no-code change only when every changed file is a stub or a py.typed marker."""
import argparse

from evals.score_bench import study_record_problems
from ops import daily_run as dr

SKIP = "no Python/compiled code in the package (docs, CI or tooling only)"
HINT_DIFF = """diff --git a/pkg/a.py b/pkg/a.py
--- a/pkg/a.py
+++ b/pkg/a.py
@@ -1,2 +1,2 @@
-def f(x):
-    return x
+def f(x: int) -> int:
+    return x
"""


def _files(paths, pkg="pkg"):
    return dr.classify_files(paths, pkg)


def _passed():
    return dr.compare_sides({"main": [{"t::c": ("passed", "")}] * 3, "pr": [{"t::c": ("passed", "")}] * 3})


def test_only_pyi_files_are_typing_only():
    paths = ["pkg/mod.pyi", "pkg/api.pyi"]
    fc = _files(paths)
    assert dr.typing_only_change(paths) is True
    assert dr.selection_skip_for_files(fc, "pkg") is None
    rec = {}
    assert dr.mark_typing_only(rec, fc) is True
    assert rec["no_code_change"] is True
    assert rec["no_code_change_reason"] == "typing_only"
    assert "behaviour was not checked" in rec["reason"]
    # A stub together with the marker is still every file being one of those two kinds.
    both = ["pkg/mod.pyi", "pkg/py.typed"]
    assert dr.typing_only_change(both) is True
    assert dr.mark_typing_only({}, _files(both)) is True


def test_only_py_typed_is_typing_only():
    for paths in (["pkg/py.typed"], ["py.typed"], ["src/pkg/py.typed"]):
        fc = _files(paths)
        assert dr.typing_only_change(paths) is True
        assert dr.selection_skip_for_files(fc, "pkg") is None
        rec = {}
        assert dr.mark_typing_only(rec, fc) is True
        assert rec["no_code_change_reason"] == "typing_only"


def test_pyi_plus_py_stays_on_the_normal_path():
    paths = ["pkg/mod.pyi", "pkg/mod.py"]
    fc = _files(paths)
    assert dr.typing_only_change(paths) is False
    assert dr.selection_skip_for_files(fc, "pkg") is None
    rec = {"verdict": "verified", "reason": "tests match"}
    assert dr.mark_typing_only(rec, fc) is False
    assert "no_code_change" not in rec and "no_code_change_reason" not in rec
    assert rec["verdict"] == "verified"
    assert dr.verdict_for(_passed(), None, None, fc)[0] == "verified"


def test_py_file_with_only_hint_edits_stays_on_the_normal_path():
    """The diff text is only annotations. The file is still .py, so the normal verdict applies."""
    paths = dr.diff_files(HINT_DIFF)
    assert paths == ["pkg/a.py"]
    assert ": int" in HINT_DIFF and "->" in HINT_DIFF
    fc = _files(paths)
    assert dr.typing_only_change(paths) is False
    rec = {}
    assert dr.mark_typing_only(rec, fc) is False
    assert "no_code_change_reason" not in rec
    verdict, reason, _ = dr.verdict_for(_passed(), None, None, fc)
    assert verdict == "verified"
    assert "typing" not in reason


def test_empty_or_non_python_diff_keeps_the_existing_skip():
    assert dr.diff_files("") == []
    assert dr.typing_only_change([]) is False
    assert dr.selection_skip_for_files(_files([]), "pkg") == SKIP
    assert dr.mark_typing_only({}, _files([])) is False
    docs = ["README.md", "docs/guide.rst"]
    assert dr.typing_only_change(docs) is False
    assert dr.selection_skip_for_files(_files(docs), "pkg") == SKIP
    assert dr.mark_typing_only({}, _files(docs)) is False
    # A marker plus any other file is not the rule, and it is not the empty-diff skip either.
    mixed = ["pkg/py.typed", "README.md"]
    assert dr.typing_only_change(mixed) is False
    assert dr.selection_skip_for_files(_files(mixed), "pkg") == SKIP


def test_typing_only_bench_record_is_not_marked_invalid(monkeypatch, tmp_path):
    monkeypatch.delenv("POC_SWARM", raising=False)
    monkeypatch.delenv("POC_HITL", raising=False)
    fc = _files(["pkg/mod.pyi"])
    rec = {"files": fc, "per_run": [], "baseline": "full"}
    assert dr.mark_typing_only(rec, fc) is True
    runner = argparse.Namespace(provider=None, swarm=False, model_skipped=None, model_provider="none",
                                model_fallback=None, bench="inputs.csv")
    dr.finish_typing_only(rec, tmp_path, tmp_path / "work", 0.0, runner)
    assert rec["no_code_change"] is True and rec["no_code_change_reason"] == "typing_only"
    assert rec["verdict"] == "no_code_change"
    assert "invalid" not in rec
    assert runner.model_skipped is None
    # The model was not called on purpose, so the study scorer still accepts the record.
    assert study_record_problems("typing.json", rec) == []
