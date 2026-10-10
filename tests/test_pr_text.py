"""PR description at merge time (poc/pr_text.py) and its use in benchmark mode."""
import json
from pathlib import Path

from poc import pr_text

FIX = json.loads((Path(__file__).parent / "fixtures" / "pr_text" / "edited-after-merge.json").read_text())


def test_picks_the_revision_in_force_at_merge():
    body, src = pr_text.body_at_merge(FIX)
    assert body == "Speeds up widget sorting.\r\n\r\nBenchmarks attached."
    assert "regression" not in body
    assert src == "at merge: edit history (revision of 2024-04-25T12:00:00Z)"


def test_never_edited_uses_the_current_text():
    pr = {"body": "Original.", "mergedAt": "2024-05-01T10:00:00Z", "lastEditedAt": None,
          "userContentEdits": {"totalCount": 0, "nodes": []}}
    assert pr_text.body_at_merge(pr) == ("Original.", "at merge: never edited")


def test_falls_back_to_current_when_history_is_missing_or_incomplete():
    pr = dict(FIX, userContentEdits={"totalCount": 3, "nodes": []})
    body, src = pr_text.body_at_merge(pr)
    assert body == FIX["body"] and src == pr_text.CURRENT
    pr = dict(FIX, userContentEdits={"totalCount": 250, "nodes": FIX["userContentEdits"]["nodes"][1:]})
    assert pr_text.body_at_merge(pr)[1].startswith(pr_text.CURRENT)    # newer revisions not all visible
    deleted = dict(FIX, userContentEdits={"totalCount": 1, "nodes": [{"editedAt": "2024-04-20T08:00:00Z",
                                                                       "deletedAt": "2024-04-21T00:00:00Z", "diff": None}]})
    assert pr_text.body_at_merge(deleted)[1] == pr_text.CURRENT


def test_no_token_records_current(monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    body, src = pr_text.description_at_merge("example-org/widgets", 1, "current text")
    assert body == "current text" and src.startswith("current, may be edited after merge")


def test_benchmark_mode_uses_the_text_at_merge(monkeypatch):
    from ops import bench

    class FakeGH:
        def __init__(self, _log):
            pass

        def json(self, _path):
            return {"title": "Faster sort", "body": FIX["body"], "user": {"login": "someone"}, "base": {"ref": "main"}}

    class DR:
        GitHub = FakeGH
    monkeypatch.setattr(pr_text, "fetch", lambda repo, n, token=None: FIX)
    t = bench.pr_text(DR, {"repo": "example-org/widgets", "pr": "5100", "pr_title": "x"})
    assert t["body"] == "Speeds up widget sorting.\r\n\r\nBenchmarks attached."
    assert t["pr_text_source"].startswith("at merge: edit history")

    def boom(*a, **k):
        raise RuntimeError("offline")
    monkeypatch.setattr(pr_text, "fetch", boom)
    t = bench.pr_text(DR, {"repo": "example-org/widgets", "pr": "5100", "pr_title": "x"})
    assert t["body"] == FIX["body"] and t["pr_text_source"].startswith("current, may be edited after merge")
