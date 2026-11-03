"""Offline checks for test-file mapping and a pinned run.

A project's pytest ``python_files`` setting (or pytest's default) decides which files are tests. A line inside a
multi-line statement counts as executable for changed-line coverage. A run pinned with --expect-commit stops
when main moves, and still writes the PDFs and the go/no-go summary. No pull request is contacted.
"""
import shutil
import subprocess
from pathlib import Path

import pytest

from ops import bench
from ops import daily_run as dr
from poc import coverage_gate, model_provider

ROOT = Path(__file__).resolve().parents[1]
SYN = ROOT / "tests" / "fixtures" / "bench" / "inputs-synthetic.csv"

# A function whose return value is one statement written on several lines. The pull request changes the later line.
_BEFORE = "def build(n):\n    return (\n        n,\n        1,\n    )\n"
_AFTER = _BEFORE.replace("        1,\n", "        2,\n")


def _git(cwd, *args):
    return subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True, text=True).stdout.strip()


def _write(root: Path, rel: str, text: str = "# fixture\n") -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _checkout(tmp_path: Path) -> Path:
    """A tiny project: one package module and tests under the default names plus a custom name."""
    for rel in ("pkg/graph.py", "pkg/runners.py", "tests/check_graph.py", "tests/test_graph.py",
                "tests/graph_test.py", "tests/runners.py", "tests/task.py"):
        _write(tmp_path, rel)
    return tmp_path


_CUSTOM = {
    "pytest.ini": "[pytest]\npython_files = check_*.py\n",
    "setup.cfg": "[tool:pytest]\npython_files = check_*.py\n",
    "tox.ini": "[pytest]\npython_files = check_*.py\n",
    "pyproject.toml": '[tool.pytest.ini_options]\npython_files = ["check_*.py"]\n',
}


@pytest.mark.parametrize("filename,text", list(_CUSTOM.items()))
def test_custom_python_files_maps_that_pattern_only(tmp_path, filename, text):
    root = _checkout(tmp_path)
    _write(root, filename, text)
    files = {"all": ["pkg/graph.py", "tests/test_graph.py"], "package_py": ["pkg/graph.py"]}
    assert dr.map_repo_tests(files, root) == ["tests/check_graph.py"]
    edited = {"all": ["tests/check_graph.py"], "package_py": []}
    assert dr.map_repo_tests(edited, root) == ["tests/check_graph.py"]


def test_default_python_files_when_the_setting_is_absent(tmp_path):
    root = _checkout(tmp_path)
    # A pytest section that does not set python_files keeps pytest's own default.
    _write(root, "setup.cfg", "[tool:pytest]\naddopts = -q\n")
    files = {"all": ["pkg/graph.py"], "package_py": ["pkg/graph.py"]}
    assert dr.map_repo_tests(files, root) == ["tests/test_graph.py", "tests/graph_test.py"]
    bare = _checkout(tmp_path / "bare")
    assert dr.map_repo_tests(files, bare) == ["tests/test_graph.py", "tests/graph_test.py"]


def test_catch_all_pattern_keeps_tests_and_skips_the_package_module(tmp_path):
    root = _checkout(tmp_path)
    _write(root, "pytest.ini", "[pytest]\npython_files = *\n")
    files = {"all": ["pkg/runners.py", "tests/task.py"], "package_py": ["pkg/runners.py"]}
    got = dr.map_repo_tests(files, root)
    assert got == ["tests/task.py", "tests/runners.py"]
    assert "pkg/runners.py" not in got


def test_a_line_inside_a_multi_line_statement_counts_as_executable():
    start = 2  # the `return (` line, which is the line coverage.py records
    lines = dr.changed_lines_for_coverage(_BEFORE, _AFTER)
    assert lines == {start}
    raw = coverage_gate.changed_lines(_BEFORE, _AFTER)
    assert raw and start not in raw
    report = {"pkg/build.py": {"executed_lines": [start], "missing_lines": []}}
    measured = coverage_gate.measure({"pkg/build.py": lines}, report)
    assert (measured["changed_lines_total"], measured["changed_lines_covered"]) == (1, 1)
    unmapped = coverage_gate.measure({"pkg/build.py": raw}, report)
    assert unmapped["changed_lines_total"] == 0
    assert dr.main_lines_for_coverage(_BEFORE, _AFTER) == {start}


def _init_repo(path: Path) -> str:
    path.mkdir(parents=True)
    _git(path, "init", "-q", "-b", "main")
    _git(path, "config", "user.email", "proof-of-change@users.noreply.github.com")
    _git(path, "config", "user.name", "Proof-of-Change")
    (path / "README").write_text("one\n")
    _git(path, "add", "README")
    _git(path, "commit", "-q", "-m", "one")
    return _git(path, "rev-parse", "HEAD")


def test_commit_moved_reason_names_the_two_commits_and_no_path(tmp_path):
    repo = tmp_path / "poc"
    first = _init_repo(repo)
    assert dr.commit_moved_reason(first, repo) is None
    assert dr.commit_moved_reason(None, repo) is None
    (repo / "README").write_text("two\n")
    _git(repo, "commit", "-q", "-am", "two")
    second = _git(repo, "rev-parse", "HEAD")
    reason = dr.commit_moved_reason(first, repo)
    assert reason is not None
    assert first in reason and second in reason
    assert "main has moved" in reason
    assert "/" not in reason


def _pdf_text(path: Path) -> str:
    data = path.read_bytes()
    assert data.startswith(b"%PDF") and len(data) > 200
    if shutil.which("pdftotext"):
        return subprocess.run(["pdftotext", str(path), "-"], capture_output=True, text=True).stdout
    return data.decode("latin-1", "replace")


def test_pinned_run_stops_when_main_moves_and_still_writes_pdfs(tmp_path, monkeypatch):
    repo = tmp_path / "poc"
    first = _init_repo(repo)
    monkeypatch.setattr(dr, "REPO_ROOT", repo)
    monkeypatch.setattr(model_provider, "auth_refusal", lambda *_a, **_k: None)
    import poc.hitl as hitl
    monkeypatch.setattr(hitl, "study_operator_approval_stop", lambda **_k: None)
    monkeypatch.setattr(dr, "resolve_python", lambda p: p)
    monkeypatch.setattr(dr, "detect_machine_type", lambda: {"label": "test", "arch": "x", "cpu_count": 1})
    ran = []

    def case(_dr, _a, row, *_rest):
        ran.append(row["id"])
        (repo / "README").write_text("moved\n")
        _git(repo, "commit", "-q", "-am", "moved")
        return {"verdict": "verified", "reason": "the first check finished", "baseline": "tests",
                "files": {"all": [], "package_py": [], "compiled": [], "other": []}}

    monkeypatch.setattr(bench, "run_case", case)
    out = tmp_path / "pdfs"
    ns = type("A", (), {})()
    ns.bench = str(SYN)
    ns.ids = "B01,B02"
    ns.provider = None
    ns.bench_out = str(tmp_path / "out")
    ns.swarm = False
    ns.work_dir = str(tmp_path / "w")
    ns.ops_dir = str(tmp_path)
    ns.python = "python3"
    ns.report_dir = str(out)
    ns.no_report = False
    ns.console_job = False
    ns.pr = None
    ns.pinned_commit = first
    ns.poc_commit = first
    rc = bench.run(ns, dr)
    assert ran == ["B01"]
    assert rc == 1
    summary = _pdf_text(out / "SUMMARY.pdf")
    assert "NO-GO" in summary and "main has moved" in summary and first in summary
    assert "verified" in _pdf_text(out / "B01" / "REPORT.pdf").lower() or "VERIFIED" in _pdf_text(out / "B01" / "REPORT.pdf")
    assert not (out / "B02").exists()
    reason_line = next(ln for ln in summary.splitlines() if "main has moved" in ln)
    assert "/" not in reason_line.split("Stopped:", 1)[-1]


def test_daily_run_stops_before_the_next_pull_request(tmp_path, monkeypatch):
    """The daily loop, not only bench mode: the second pull request is not checked, and the go/no-go is written."""
    repo = tmp_path / "poc"
    first = _init_repo(repo)
    monkeypatch.setattr(dr, "REPO_ROOT", repo)
    monkeypatch.setattr(dr, "ensure_tools", lambda: {"installed": []})
    monkeypatch.setattr(dr, "leave_run_pointer", lambda *_a, **_k: None)
    tested = []

    def fake_test(_repo, _cfg, item, *_rest):
        tested.append(item["pr"])
        (repo / "README").write_text("moved\n")
        _git(repo, "commit", "-q", "-am", "moved")
        return {"verdict": "could_not_verify", "reason": "stub check", "baseline": "tests",
                "files": {"all": [], "package_py": [], "compiled": [], "other": []},
                "repo": _repo, "library": "widgets", "author": "a", "updated_at_ist": "",
                "ci_state": "none", "ci_detail": "-",
                "pr": {"number": item["pr"], "repo": _repo, "url": item["url"], "title": item["title"],
                       "head_sha": "ab" * 20},
                "duration_s": {"total_wall": 1}, "tested_at_ist": "2026-11-03 10:00 IST",
                "coverage_gate": {"kind": "stub"}}

    monkeypatch.setattr(dr, "test_pr", fake_test)
    monkeypatch.setattr(dr, "chosen_items", lambda *_a, **_k: [
        {"pr": 1, "title": "one", "url": "https://github.com/example-org/widgets/pull/1", "author": "a",
         "head_sha": "ab" * 20, "updated_at_ist": "", "ci_state": "none", "ci_detail": "-",
         "files": {"all": ["widgets/a.py"], "package_py": ["widgets/a.py"], "compiled": [], "other": []}},
        {"pr": 2, "title": "two", "url": "https://github.com/example-org/widgets/pull/2", "author": "a",
         "head_sha": "cd" * 20, "updated_at_ist": "", "ci_state": "none", "ci_detail": "-",
         "files": {"all": ["widgets/b.py"], "package_py": ["widgets/b.py"], "compiled": [], "other": []}},
    ])
    reports = tmp_path / "reports"
    code = dr.main([
        "--pr", "https://github.com/example-org/widgets/pull/1",
        "--pr", "https://github.com/example-org/widgets/pull/2",
        "--expect-commit", first, "--model-provider", "none", "--baseline", "tests",
        "--unsafe-no-sandbox",
        "--min-free-gb", "0", "--ops-dir", str(tmp_path / "ops"), "--date", "2026-11-03-offline",
        "--report-dir", str(reports), "--no-probes",
    ])
    assert tested == [1]
    assert code == 1
    summary = _pdf_text(reports / "SUMMARY.pdf")
    assert "NO-GO" in summary and "main has moved" in summary and first in summary
    reason_line = next(ln for ln in summary.splitlines() if "main has moved" in ln)
    assert "/" not in reason_line.split("Stopped:", 1)[-1]
