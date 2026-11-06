"""The run-level go/no-go covers every record in its date+commit folder and is never a false all-clear."""
import json
from pathlib import Path

import pytest

from ops import daily_run


def _one_pr_run(folder: Path, pr_id: str, repo: str, n: int, verdict: str):
    """What a one-PR run leaves in the shared folder: its record, then the run-level summary rebuild."""
    (folder / pr_id).mkdir(parents=True, exist_ok=True)
    (folder / pr_id / "record.json").write_text(json.dumps(
        {"verdict": verdict, "reason": f"{verdict} reason", "pr": {"repo": repo, "number": n, "title": "t"}}))
    assert daily_run.rebuild_folder_summary(folder)


def test_three_sequential_one_pr_runs_share_a_folder(tmp_path):
    folder = tmp_path / "runs" / "2026-11-06" / "abc1234"
    _one_pr_run(folder, "invoke-1097", "pyinvoke/invoke", 1097, "could_not_verify")
    _one_pr_run(folder, "loguru-1515", "Delgan/loguru", 1515, "could_not_verify")
    _one_pr_run(folder, "sqlparse-944", "andialbrecht/sqlparse", 944, "verified")
    md = (folder / "SUMMARY.md").read_text()
    for subject in ("pyinvoke/invoke#1097", "Delgan/loguru#1515", "andialbrecht/sqlparse#944"):
        assert subject in md
    assert "3 report(s)" in md and "2 could not be verified" in md and "1 verified" in md
    assert "nothing needs attention" not in md.lower()
    assert (folder / "SUMMARY.pdf").read_bytes().startswith(b"%PDF")


def test_two_sequential_runs_do_not_narrow(tmp_path):
    folder = tmp_path / "f"
    _one_pr_run(folder, "a-1", "o/a", 1, "needs_attention")
    _one_pr_run(folder, "b-2", "o/b", 2, "verified")
    md = (folder / "SUMMARY.md").read_text()
    assert "o/a#1" in md and "o/b#2" in md and "1 need attention" in md


def test_all_clear_only_when_every_record_is_verified(tmp_path):
    folder = tmp_path / "f"
    _one_pr_run(folder, "b-2", "o/b", 2, "verified")
    assert "Nothing needs attention" in (folder / "SUMMARY.md").read_text()


def test_capped_collection_gap_uses_the_existing_all_clear_rule(tmp_path):
    """The summary reads the stored verdict. could_not_verify is not an all-clear. needs_attention stays."""
    folder = tmp_path / "f"
    (folder / "b-2").mkdir(parents=True)
    (folder / "b-2" / "record.json").write_text(json.dumps({
        "verdict": "could_not_verify",
        "reason": "could not verify: pytest could not collect tests/other_changed.py, so that changed test "
                  "file did not run (tests match); fix appears already present on 2.2; "
                  "Limitation: pytest could not collect tests/other_changed.py. "
                  "That changed test file is not a pass, and this result does not cover it.",
        "already_on_base": "fix appears already present on 2.2",
        "base_ref": "2.2",
        "pr": {"repo": "o/b", "number": 2, "title": "t"},
    }))
    (folder / "a-1").mkdir()
    (folder / "a-1" / "record.json").write_text(json.dumps({
        "verdict": "needs_attention",
        "reason": "1 test(s) pass on main but fail on the PR; fix appears already present on master; "
                  "Limitation: pytest could not collect tests/other_changed.py. "
                  "That changed test file is not a pass, and this result does not cover it.",
        "already_on_base": "fix appears already present on master",
        "pr": {"repo": "o/a", "number": 1, "title": "t"},
    }))
    assert daily_run.rebuild_folder_summary(folder)
    md = (folder / "SUMMARY.md").read_text()
    assert "Nothing needs attention" not in md
    assert "tests/other_changed.py" in md
    assert "already present on 2.2" in md and "already present on master" in md
    assert "clean verification" not in md.lower()
    assert "**COULD NOT VERIFY**" in md and "**NEEDS ATTENTION**" in md
    assert "1 need attention" in md and "1 could not be verified" in md


@pytest.mark.parametrize("verdict", ["could_not_verify", "needs_attention", None])
def test_guard_refuses_false_all_clear(verdict):
    recs = [{"verdict": "verified"}, {"verdict": verdict}]
    with pytest.raises(ValueError):
        daily_run.check_no_false_all_clear("Nothing needs attention: every report is VERIFIED.", recs)
    daily_run.check_no_false_all_clear("1 could not be verified", recs)


def test_push_rebuilds_summary_from_records_already_on_branch(tmp_path, monkeypatch):
    """_runs_push_once: a one-PR run's narrow SUMMARY is replaced by one built from all records in the folder."""
    seen = {}

    def fake_rebuild(folder, token=None):
        seen["folder"] = Path(folder).relative_to(tmp_path)
        return True
    monkeypatch.setattr(daily_run, "rebuild_folder_summary", fake_rebuild)
    monkeypatch.setattr(daily_run.tempfile, "mkdtemp", lambda prefix="": str(tmp_path))

    class CP:
        returncode, stdout = 0, ""
    monkeypatch.setattr(daily_run, "_git_exec", lambda *a, **k: CP())

    def earlier_run(checkout, origin, env):  # the branch already holds another one-PR run's record
        (checkout / "runs/2026-11-06/abc/earlier-1").mkdir(parents=True)
        (checkout / "runs/2026-11-06/abc/earlier-1/record.json").write_text('{"verdict": "could_not_verify"}')
    monkeypatch.setattr(daily_run, "_init_orphan", earlier_run)
    monkeypatch.setattr(daily_run.shutil, "rmtree", lambda *a, **k: None)
    with pytest.raises(daily_run._RunsPushError):
        daily_run._runs_push_once("o", None, [("runs/2026-11-06/abc/SUMMARY.md", b"x")], False, {})
    assert seen["folder"] == Path("checkout/runs/2026-11-06/abc")


def test_own_summary_kept_when_it_covers_every_record(tmp_path):
    folder = tmp_path / "runs/d/abc"
    (folder / "a-1").mkdir(parents=True)
    (folder / "a-1/record.json").write_text('{"verdict": "verified"}')
    (folder / "SUMMARY.md").write_text("GO. Nothing needs attention")
    assert not daily_run.summary_needs_rebuild(folder, {"runs/d/abc/a-1/record.json"}, "runs/d/abc")
    (folder / "a-1/record.json").write_text('{"verdict": "could_not_verify"}')
    assert daily_run.summary_needs_rebuild(folder, {"runs/d/abc/a-1/record.json"}, "runs/d/abc")
