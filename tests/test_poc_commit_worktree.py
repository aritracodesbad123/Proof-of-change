"""resolve_poc_commit treats a .git file (git worktree) like a .git folder."""
from ops import daily_run as dr


def test_git_file_worktree_is_a_checkout(tmp_path, monkeypatch):
    (tmp_path / ".git").write_text("gitdir: /elsewhere/.git/worktrees/x\n")
    monkeypatch.setattr(dr, "sync_to_origin_main", lambda root: "b" * 40)
    monkeypatch.setenv("POC_COMMIT", "a" * 40)
    assert dr.resolve_poc_commit(tmp_path) == "b" * 40


def test_git_folder_still_a_checkout(tmp_path, monkeypatch):
    (tmp_path / ".git").mkdir()
    monkeypatch.setattr(dr, "sync_to_origin_main", lambda root: "b" * 40)
    assert dr.resolve_poc_commit(tmp_path) == "b" * 40


def test_no_git_uses_poc_commit(tmp_path, monkeypatch):
    monkeypatch.setattr(dr, "sync_to_origin_main", lambda root: (_ for _ in ()).throw(AssertionError("synced")))
    monkeypatch.setenv("POC_COMMIT", "a" * 40)
    assert dr.resolve_poc_commit(tmp_path) == "a" * 40
