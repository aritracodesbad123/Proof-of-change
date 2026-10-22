"""Base-commit choice for product checks: a merged PR (merge-base equals the PR head) is compared with its recorded
base, not with itself; identical sides never reach the docstring-only path. Local git repo, no network."""
import subprocess
from pathlib import Path

from ops import daily_run as dr


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", repo, *args], check=True, capture_output=True, text=True).stdout.strip()


def _repo(tmp_path: Path) -> tuple[Path, str, str]:
    repo = tmp_path / "src"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@example.invalid")
    _git(repo, "config", "user.name", "t")
    (repo / "m.py").write_text("def f():\n    return 1\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "base")
    base = _git(repo, "rev-parse", "HEAD")
    (repo / "m.py").write_text("def f():\n    return 2\n")
    _git(repo, "commit", "-qam", "pr")
    head = _git(repo, "rev-parse", "HEAD")
    return repo, base, head


def test_merged_pr_uses_recorded_base(tmp_path):
    repo, base, head = _repo(tmp_path)
    res = {"main_sha": head, "pr_sha": head, "comparison_basis": "merge-base vs PR head (no merge ref available)"}
    assert dr.distinct_base(repo, dr.base_env(tmp_path / "h"), tmp_path / "g.log", {"head_sha": head, "base_sha": base}, res) is None
    assert res["main_sha"] == base and res["pr_sha"] == head
    assert "merge-base" in res["comparison_basis"]


def _two_commit_repo(tmp_path: Path) -> tuple[Path, dict]:
    """main: B -> L (later main commit). PR branch from B: C1 (a.py) -> C2 (b.py). Then the PR is merged into main
    with a merge commit M (first parent L)."""
    repo = tmp_path / "src2"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@example.invalid")
    _git(repo, "config", "user.name", "t")
    (repo / "m.py").write_text("x = 0\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "base")
    s = {"B": _git(repo, "rev-parse", "HEAD")}
    _git(repo, "checkout", "-q", "-b", "pr")
    (repo / "a.py").write_text("a = 1\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "c1")
    s["C1"] = _git(repo, "rev-parse", "HEAD")
    (repo / "b.py").write_text("b = 2\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "c2")
    s["C2"] = _git(repo, "rev-parse", "HEAD")
    _git(repo, "checkout", "-q", "main")
    (repo / "later.py").write_text("later = 1\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "later main")
    s["L"] = _git(repo, "rev-parse", "HEAD")
    _git(repo, "merge", "-q", "--no-ff", "-m", "merge pr", s["C2"])
    s["M"] = _git(repo, "rev-parse", "HEAD")
    return repo, s


def _changed(repo: Path, a: str, b: str) -> set[str]:
    return set(_git(repo, "diff", "--name-only", a, b).split())


def test_two_commit_pr_compares_all_commits(tmp_path):
    repo, s = _two_commit_repo(tmp_path)
    res = {"main_sha": s["C2"], "pr_sha": s["C2"], "comparison_basis": "x"}
    item = {"head_sha": s["C2"], "base_sha": s["B"], "merge_commit_sha": s["M"]}
    assert dr.distinct_base(repo, dr.base_env(tmp_path / "h"), tmp_path / "g.log", item, res) is None
    assert res["main_sha"] == s["B"] and res["main_sha"] != s["C1"]
    assert _changed(repo, res["main_sha"], res["pr_sha"]) == {"a.py", "b.py"}


def test_later_base_commits_not_pulled_in(tmp_path):
    repo, s = _two_commit_repo(tmp_path)
    res = {"main_sha": s["C2"], "pr_sha": s["C2"], "comparison_basis": "x"}
    item = {"head_sha": s["C2"], "base_sha": s["L"], "merge_commit_sha": s["M"]}
    assert dr.distinct_base(repo, dr.base_env(tmp_path / "h"), tmp_path / "g.log", item, res) is None
    assert res["main_sha"] == s["B"]
    assert "later.py" not in _changed(repo, res["main_sha"], res["pr_sha"])
    assert "merge-base" in res["comparison_basis"]


def test_merge_base_equal_to_head_uses_merge_commit_first_parent(tmp_path):
    repo, s = _two_commit_repo(tmp_path)
    res = {"main_sha": s["C2"], "pr_sha": s["C2"], "comparison_basis": "x"}
    item = {"head_sha": s["C2"], "base_sha": s["M"], "merge_commit_sha": s["M"]}
    assert dr.distinct_base(repo, dr.base_env(tmp_path / "h"), tmp_path / "g.log", item, res) is None
    assert res["main_sha"] == s["L"]
    assert "first parent of the PR merge commit" in res["comparison_basis"]


def test_no_head_parent_fallback(tmp_path):
    repo, s = _two_commit_repo(tmp_path)
    res = {"main_sha": s["C2"], "pr_sha": s["C2"], "comparison_basis": "x"}
    bad = dr.distinct_base(repo, dr.base_env(tmp_path / "h"), tmp_path / "g.log", {"head_sha": s["C2"]}, res)
    assert bad and bad["why"].startswith("unsupported:") and res["main_sha"] == s["C2"]


def test_no_distinct_base_is_unsupported(tmp_path):
    repo, base, _ = _repo(tmp_path)
    res = {"main_sha": base, "pr_sha": base, "comparison_basis": "x"}
    bad = dr.distinct_base(repo, dr.base_env(tmp_path / "h"), tmp_path / "g.log", {"head_sha": base, "base_sha": base}, res)
    assert bad and bad["ok"] is False and bad["why"].startswith("unsupported:")


def test_open_pr_unchanged(tmp_path):
    repo, base, head = _repo(tmp_path)
    res = {"main_sha": base, "pr_sha": head, "comparison_basis": "merge-base vs PR head"}
    before = dict(res)
    assert dr.distinct_base(repo, dr.base_env(tmp_path / "h"), tmp_path / "g.log", {"head_sha": head, "base_sha": base}, res) is None
    assert res == before


def test_identical_sides_never_reach_docstring_only():
    v, reason, flags = dr.verdict_for(None, "x", docstring_only=True, same_sides=True)
    assert v == dr.Verdict.COULD_NOT_VERIFY.value and reason.startswith("unsupported:")
    assert "by construction" not in reason and "holds_by_construction" not in flags


def test_store_verdict_same_sha_product_check_not_verified():
    rec = {"product_check": True, "docstring_only": True, "sides": {"main_sha": "a" * 40, "pr_sha": "a" * 40},
           "files": {"all": ["m.py"]}}
    dr._store_verdict(rec, None, "x", None)
    assert rec["verdict"] == dr.Verdict.COULD_NOT_VERIFY.value
    assert "by construction" not in rec["reason"] and rec["docstring_only"] is False


def test_study_path_unchanged_for_same_sha():
    rec = {"docstring_only": True, "sides": {"main_sha": "a" * 40, "pr_sha": "a" * 40}, "files": {"all": ["m.py"]}}
    dr._store_verdict(rec, None, "x", None)
    assert "by construction" in rec["reason"]
