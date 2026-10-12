"""Decision-log check (guardrails/decision_log.py)."""
import subprocess

import pytest

from guardrails import decision_log as dl

ENTRY = "docs/decisions/2026-10-11-benchmark-scorer.md"


@pytest.mark.parametrize("changes,ok", [
    ([("M", "poc/leakage.py")], False),
    ([("M", "poc/leakage.py"), ("A", ENTRY)], True),
    ([("A", ".github/workflows/ci.yml")], False),
    ([("M", "README.md"), ("M", "docs/OPERATIONS.md")], True),              # no code changed
    ([("M", "tests/test_x.py")], True),
    ([("M", "ops/daily_run.py"), ("M", ENTRY)], False),                     # editing an old entry does not count
    ([("M", "ops/daily_run.py"), ("A", "docs/decisions/README.md")], False),
    ([("M", "ops/daily_run.py"), ("A", "docs/decisions/benchmark.md")], False),
    ([("M", "ops/daily_run.py"), ("A", "docs/decisions/2026-10-11-Bad_Name.md")], False),
    ([("M", "reports/pr_report.py"), ("A", "docs/decisions/2026-10-11-x.md")], True),
])
def test_check(changes, ok):
    assert dl.check(changes)[0] is ok


def test_failure_message_explains_the_fix():
    ok, msg = dl.check([("M", "evals/x.py"), ("A", "docs/decisions/notes.md")])
    assert not ok and "docs/decisions/YYYY-MM-DD-<short-topic>.md" in msg and "notes.md" in msg


def test_parse_name_status_uses_the_new_path_of_renames():
    assert dl.parse_name_status("M\tpoc/a.py\nR100\told.md\tdocs/decisions/2026-10-11-a.md\n") == [
        ("M", "poc/a.py"), ("R100", "docs/decisions/2026-10-11-a.md")]


def git(cwd, *a):
    subprocess.run(["git", "-C", str(cwd), *a], check=True, capture_output=True)


def test_main_against_a_base_branch(tmp_path, monkeypatch, capsys):
    git(tmp_path, "init", "-q", "-b", "main")
    git(tmp_path, "config", "user.email", "t@example.com")
    git(tmp_path, "config", "user.name", "t")
    (tmp_path / "poc").mkdir()
    (tmp_path / "poc" / "a.py").write_text("x = 1\n")
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-q", "-m", "base")
    git(tmp_path, "checkout", "-q", "-b", "change")
    (tmp_path / "poc" / "a.py").write_text("x = 2\n")
    git(tmp_path, "commit", "-q", "-am", "code")
    monkeypatch.chdir(tmp_path)
    assert dl.main(["--base", "main"]) == 1
    (tmp_path / "docs" / "decisions").mkdir(parents=True)
    (tmp_path / "docs" / "decisions" / "2026-10-11-a.md").write_text("# a\n")
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-q", "-m", "entry")
    assert dl.main(["--base", "main"]) == 0
    assert "decision-log entry added" in capsys.readouterr().out
