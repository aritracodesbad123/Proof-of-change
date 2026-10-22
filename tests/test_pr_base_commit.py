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
    assert "base.sha" in res["comparison_basis"]


def test_merged_pr_falls_back_to_first_parent(tmp_path):
    repo, base, head = _repo(tmp_path)
    res = {"main_sha": head, "pr_sha": head, "comparison_basis": "x"}
    assert dr.distinct_base(repo, dr.base_env(tmp_path / "h"), tmp_path / "g.log", {"head_sha": head}, res) is None
    assert res["main_sha"] == base


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
