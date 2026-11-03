"""The run copies its PDFs and record.json onto a local bare repo standing in for origin.

Nothing here contacts GitHub. The caller's checkout is only read, and only so the code can see origin.
"""
import json
import subprocess
from pathlib import Path

from ops import daily_run as dr
from poc import pdf_always

SHA = "46c8a6c" + ("b" * 33)
DAY = "2026-11-03"
PR = "widgets-7"
TOKEN_NAMES = ("GITHUB_TOKEN", "GITHUB_POC_TOKEN", "GH_TOKEN")


def _host_paths() -> list[str]:
    space = "/" + "work" + "space" + "/runs"
    home = "/" + "home" + "/" + "bo" + "x" + "/src"
    return [space, home]


def _git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    cp = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)
    if check and cp.returncode != 0:
        raise AssertionError(f"{args}\n{cp.stderr or cp.stdout}")
    return cp


def _bare(path: Path) -> None:
    subprocess.run(["git", "init", "--bare", "-q", str(path)], check=True)


def _user_repo(path: Path, bare: Path) -> None:
    path.mkdir()
    _git(path, "init", "-q", "-b", "main")
    _git(path, "config", "user.email", "t@example.com")
    _git(path, "config", "user.name", "t")
    (path / "README").write_text("checkout\n")
    _git(path, "add", "README")
    _git(path, "commit", "-q", "-m", "init")
    _git(path, "remote", "add", "origin", str(bare))


def _snap(repo: Path) -> tuple:
    def out(*args: str) -> str:
        return _git(repo, *args).stdout

    return (out("rev-parse", "HEAD"), out("status", "--porcelain"), out("branch", "--show-current"),
            out("worktree", "list"), out("branch", "--list"))


def _layout(tmp: Path) -> tuple[Path, Path, dict]:
    report, run = tmp / "reports", tmp / "run"
    (report / PR).mkdir(parents=True)
    note = " and ".join(_host_paths())
    pdf_always.write_pdf(report / PR / "REPORT.pdf", "Reviewer report widgets-7",
                         ["Verdict: verified", "Reason: the mapped tests agree", note])
    pdf_always.write_pdf(report / "SUMMARY.pdf", "Proof-of-Change summary",
                         ["Go/no-go: GO", "widgets-7: verified", note])
    rec = {"repo": "example/widgets", "library": "widgets", "logs": f"{PR}/",
           "pr": {"number": 7, "repo": "example/widgets"}, "verdict": "verified",
           "reason": "the mapped tests agree", "note": note}
    (run / PR).mkdir(parents=True)
    (run / PR / "record.json").write_text(json.dumps(rec))
    (run / "REPORT.md").write_text("# Run report\n\nThe check finished.\n")
    (run / "run.log").write_text("run started\n")
    return report, run, rec


def _clear_tokens(monkeypatch) -> None:
    for name in TOKEN_NAMES:
        monkeypatch.delenv(name, raising=False)


def _tip(bare: Path) -> str:
    cp = subprocess.run(["git", "--git-dir", str(bare), "log", "-1", "--format=%an%n%ae%n%cn%n%ce%n%P", "runs"],
                        capture_output=True, text=True, check=True)
    return cp.stdout


def _count(bare: Path, branch: str = "runs") -> int:
    cp = subprocess.run(["git", "--git-dir", str(bare), "rev-list", "--count", branch],
                        capture_output=True, text=True)
    if cp.returncode != 0:
        return 0
    return int(cp.stdout.strip() or "0")


def _blob(bare: Path, rel: str) -> bytes:
    cp = subprocess.run(["git", "--git-dir", str(bare), "show", f"runs:{rel}"], capture_output=True)
    assert cp.returncode == 0, cp.stderr.decode()
    return cp.stdout


def _names(bare: Path) -> list[str]:
    cp = subprocess.run(["git", "--git-dir", str(bare), "ls-tree", "-r", "--name-only", "runs"],
                        capture_output=True, text=True, check=True)
    return [ln for ln in cp.stdout.splitlines() if ln]


def _seed_runs(bare: Path, tmp: Path, name: str, text: str) -> None:
    wt = tmp / f"seed-{name}"
    if _count(bare) == 0 and not (bare / "refs" / "heads" / "runs").exists():
        wt.mkdir()
        _git(wt, "init", "-q", "-b", "runs")
        _git(wt, "config", "user.email", "t@example.com")
        _git(wt, "config", "user.name", "t")
        _git(wt, "remote", "add", "origin", str(bare))
    else:
        _git_clone = subprocess.run(["git", "clone", "-q", "--branch", "runs", str(bare), str(wt)],
                                    capture_output=True, text=True)
        assert _git_clone.returncode == 0, _git_clone.stderr
        _git(wt, "config", "user.email", "t@example.com")
        _git(wt, "config", "user.name", "t")
    (wt / name).write_text(text)
    _git(wt, "add", name)
    _git(wt, "commit", "-q", "-m", f"add {name}")
    _git(wt, "push", "-q", "origin", "HEAD:refs/heads/runs")


def _hook(bare: Path, body: str) -> None:
    hook = bare / "hooks" / "pre-receive"
    hook.write_text(body)
    hook.chmod(0o755)


def _reject_once(bare: Path) -> None:
    _hook(bare, """#!/bin/sh
marker="$GIT_DIR/reject-once-used"
if [ ! -f "$marker" ]; then
  echo 1 > "$marker"
  echo "declined by the test hook" >&2
  exit 1
fi
exit 0
""")


def _reject_always(bare: Path) -> None:
    _hook(bare, """#!/bin/sh
echo "declined by the test hook" >&2
exit 1
""")


def _publish(report, run, user, sleep):
    return dr.publish_run_outputs(report, run, poc_commit=SHA, date=DAY, root=user, sleep=sleep)


def test_push_creates_an_orphan_runs_branch(tmp_path, monkeypatch):
    bare, user = tmp_path / "origin.git", tmp_path / "checkout"
    _bare(bare)
    _user_repo(user, bare)
    before = _snap(user)
    _clear_tokens(monkeypatch)
    monkeypatch.setenv("GITHUB_POC_TOKEN", "local-test-token")
    report, run, rec = _layout(tmp_path)
    slept = []
    result = _publish(report, run, user, slept.append)
    assert result["ok"] is True and result["attempts"] == 1 and result["error"] is None
    assert result["url"] == f"runs/{DAY}/{SHA[:7]}/{PR}"
    assert not slept
    assert _snap(user) == before
    assert "runs" not in _git(user, "branch", "--list").stdout
    assert _count(bare, "main") == 0
    tip = _tip(bare).splitlines()
    assert tip[:4] == ["Proof-of-Change", "proof-of-change@users.noreply.github.com",
                       "Proof-of-Change", "proof-of-change@users.noreply.github.com"]
    root = subprocess.run(["git", "--git-dir", str(bare), "rev-list", "--max-parents=0", "runs"],
                          capture_output=True, text=True, check=True)
    head = subprocess.run(["git", "--git-dir", str(bare), "rev-parse", "runs"],
                          capture_output=True, text=True, check=True)
    assert root.stdout.strip() == head.stdout.strip()
    prefix = f"runs/{DAY}/{SHA[:7]}/{PR}"
    names = _names(bare)
    assert f"{prefix}/REPORT.pdf" in names
    assert f"{prefix}/SUMMARY.pdf" in names
    assert f"{prefix}/record.json" in names
    pushed = json.loads(_blob(bare, f"{prefix}/record.json"))
    assert pushed["pdf_push"] == {"ok": True, "attempts": 1, "error": None, "url": result["url"]}
    raw = b"\n".join(_blob(bare, f"{prefix}/{name}") for name in ("record.json", "REPORT.pdf", "SUMMARY.pdf"))
    for path in _host_paths():
        assert path.encode() not in raw
    assert b"local-test-token" not in raw
    local = json.loads((run / PR / "record.json").read_text())
    assert local["pdf_push"]["ok"] is True
    assert rec["note"] in local["note"]  # the local file keeps its own text
    assert "PDFs saved to GitHub:" in (run / "run.log").read_text()
    import inspect
    banned = "smtp" + "lib"
    assert banned not in inspect.getsource(dr.publish_run_outputs)
    assert banned not in inspect.getsource(dr._runs_push_once)


def test_push_retries_after_one_failure_and_keeps_the_remote_commit(tmp_path, monkeypatch):
    bare, user = tmp_path / "origin.git", tmp_path / "checkout"
    _bare(bare)
    _user_repo(user, bare)
    _seed_runs(bare, tmp_path, "keeper.txt", "keep\n")
    _reject_once(bare)
    before = _snap(user)
    _clear_tokens(monkeypatch)
    monkeypatch.setenv("GITHUB_TOKEN", "local-test-token")
    report, run, _rec = _layout(tmp_path)
    delays = []

    def sleep(seconds):
        delays.append(seconds)
        _seed_runs(bare, tmp_path, "moved.txt", "moved\n")

    result = _publish(report, run, user, sleep)
    assert result["ok"] is True and result["attempts"] == 2 and result["error"] is None
    assert delays == [1]
    assert _snap(user) == before
    names = _names(bare)
    assert "keeper.txt" in names and "moved.txt" in names
    assert any(name.endswith("/REPORT.pdf") for name in names)
    assert _count(bare) >= 3  # seed, the remote move, then this run


def test_push_failure_keeps_local_files_and_shows_the_banner(tmp_path, monkeypatch):
    bare, user = tmp_path / "origin.git", tmp_path / "checkout"
    _bare(bare)
    _user_repo(user, bare)
    _seed_runs(bare, tmp_path, "keeper.txt", "keep\n")
    _reject_always(bare)
    before = _snap(user)
    _clear_tokens(monkeypatch)
    monkeypatch.setenv("GITHUB_TOKEN", "local-test-token")
    report, run, _rec = _layout(tmp_path)
    pdf_before = (report / "SUMMARY.pdf").read_bytes()
    delays = []
    result = _publish(report, run, user, delays.append)
    banner = "PDFs NOT saved to GitHub: could not push to the runs branch after 3 attempts"
    assert result == {"ok": False, "attempts": 3, "error": "could not push to the runs branch after 3 attempts",
                      "url": None, "urls": {}}
    assert delays == [1, 2]
    assert _snap(user) == before
    assert _count(bare) == 1  # the seed commit is still the only one
    assert banner in (run / "run.log").read_text()
    report_text = (run / "REPORT.md").read_text()
    assert report_text.startswith(banner)
    assert "The check finished." in report_text
    summary = (report / "SUMMARY.pdf").read_bytes()
    assert summary != pdf_before and summary.startswith(b"%PDF")
    text = subprocess.run(["pdftotext", str(report / "SUMMARY.pdf"), "-"], capture_output=True, text=True).stdout
    assert banner in text and "GO" in text
    saved = json.loads((run / PR / "record.json").read_text())
    assert saved["pdf_push"] == {"ok": False, "attempts": 3,
                                 "error": "could not push to the runs branch after 3 attempts", "url": None}
    assert (report / PR / "REPORT.pdf").is_file()


def test_no_token_does_not_push_and_shows_the_banner(tmp_path, monkeypatch):
    bare, user = tmp_path / "origin.git", tmp_path / "checkout"
    _bare(bare)
    _user_repo(user, bare)
    before = _snap(user)
    _clear_tokens(monkeypatch)
    report, run, _rec = _layout(tmp_path)
    delays = []
    result = _publish(report, run, user, delays.append)
    banner = "PDFs NOT saved to GitHub: no GitHub token is set"
    assert result["ok"] is False and result["attempts"] == 0 and result["error"] == "no GitHub token is set"
    assert result["url"] is None
    assert delays == []
    assert _snap(user) == before
    assert _count(bare) == 0
    refs = subprocess.run(["git", "--git-dir", str(bare), "show-ref"], capture_output=True, text=True)
    assert "runs" not in refs.stdout
    assert banner in (run / "run.log").read_text()
    assert (run / "REPORT.md").read_text().startswith(banner)
    saved = json.loads((run / PR / "record.json").read_text())
    assert saved["pdf_push"]["ok"] is False and saved["pdf_push"]["attempts"] == 0
    assert (report / "SUMMARY.pdf").is_file() and (report / PR / "REPORT.pdf").is_file()
