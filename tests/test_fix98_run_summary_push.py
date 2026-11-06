"""Fix 98: the run-level go/no-go SUMMARY.pdf is always pushed, and the saved banner follows the final push."""
import json
import subprocess

from ops import daily_run as dr
from poc import pdf_always
from tests.test_run_pdf_push import (DAY, PR, SHA, TOKEN, _bare, _clear_tokens, _layout, _names, _publish,
                                     _blob, _reject_always, _user_repo)

STALE = "PDFs NOT saved to GitHub: could not push to the runs branch after 3 attempts"


def _pdf_text(path):
    return subprocess.run(["pdftotext", str(path), "-"], capture_output=True, text=True).stdout


def _ready(tmp_path, monkeypatch):
    bare, user = tmp_path / "origin.git", tmp_path / "checkout"
    _bare(bare)
    _user_repo(user, bare)
    _clear_tokens(monkeypatch)
    monkeypatch.setenv("GITHUB_TOKEN", TOKEN)
    report, run, _rec = _layout(tmp_path)
    (report / "SUMMARY.md").write_text("# Go/no-go\n\nGO\n")
    return bare, user, report, run


def test_run_level_summary_is_pushed_into_the_run_folder(tmp_path, monkeypatch):
    bare, user, report, run = _ready(tmp_path, monkeypatch)
    result = _publish(report, run, user, lambda s: None)
    assert result["ok"] is True
    names = _names(bare)
    base = f"runs/{DAY}/{SHA[:7]}"
    assert f"{base}/SUMMARY.pdf" in names and f"{base}/SUMMARY.md" in names
    assert f"{base}/{PR}/REPORT.pdf" in names


def test_uncleanable_summary_is_redacted_and_pushed_never_skipped(tmp_path, monkeypatch):
    bare, user, report, run = _ready(tmp_path, monkeypatch)
    secret_path = "/" + "work" + "space" + "/secret/run"
    pdf_always.write_pdf(report / "SUMMARY.pdf", "summary", ["Go/no-go: GO", f"log at {secret_path}"])
    (report / "SUMMARY.md").write_text(f"# Go/no-go\n\nGO\n\nlog at {secret_path}\n")
    # Make ordinary scrubbing useless so only the forced line blanking can clean it.
    monkeypatch.setattr(dr, "scrub_published_text", lambda text, token=None, path=None: text)
    result = _publish(report, run, user, lambda s: None)
    assert result["ok"] is True
    base = f"runs/{DAY}/{SHA[:7]}"
    names = _names(bare)
    assert f"{base}/SUMMARY.pdf" in names and f"{base}/SUMMARY.md" in names
    pdf = _blob(bare, f"{base}/SUMMARY.pdf")
    out = tmp_path / "pushed.pdf"
    out.write_bytes(pdf)
    text = _pdf_text(out)
    assert "GO" in text and secret_path not in text
    assert secret_path.encode() not in _blob(bare, f"{base}/SUMMARY.md")
    assert not any("SUMMARY" in s for s in result.get("skipped") or [])


def test_later_success_clears_the_old_not_saved_banner(tmp_path, monkeypatch):
    bare, user, report, run = _ready(tmp_path, monkeypatch)
    _reject_always(bare)
    first = _publish(report, run, user, lambda s: None)
    assert first["ok"] is False
    assert STALE in (report / "SUMMARY.md").read_text()
    assert STALE in (run / "run.log").read_text()
    (bare / "hooks" / "pre-receive").unlink()
    second = _publish(report, run, user, lambda s: None)
    assert second["ok"] is True
    for path in (report / "SUMMARY.md", run / "REPORT.md", run / "run.log"):
        assert "NOT saved" not in path.read_text(), path
    assert "PDFs saved to GitHub:" in (run / "run.log").read_text()
    assert "NOT saved" not in _pdf_text(report / "SUMMARY.pdf")
    assert "GO" in (report / "SUMMARY.md").read_text()
    out = tmp_path / "pushed.pdf"
    out.write_bytes(_blob(bare, f"runs/{DAY}/{SHA[:7]}/SUMMARY.pdf"))
    assert "NOT saved" not in _pdf_text(out)
    assert "NOT saved" not in _blob(bare, f"runs/{DAY}/{SHA[:7]}/SUMMARY.md").decode()


def test_later_failure_replaces_an_old_saved_line(tmp_path, monkeypatch):
    bare, user, report, run = _ready(tmp_path, monkeypatch)
    assert _publish(report, run, user, lambda s: None)["ok"] is True
    _reject_always(bare)
    (report / "SUMMARY.md").write_text("# Go/no-go\n\nNO-GO\n")  # something new to push
    assert _publish(report, run, user, lambda s: None)["ok"] is False
    log = (run / "run.log").read_text()
    assert "PDFs saved to GitHub:" not in log and STALE in log
    assert log.count("PDFs NOT saved") == 1
    rec = json.loads((run / PR / "record.json").read_text())
    assert rec["pdf_push"]["ok"] is False


def test_one_uncleanable_record_does_not_refuse_the_whole_set(tmp_path, monkeypatch):
    bare, user, report, run = _ready(tmp_path, monkeypatch)

    def refuse(path, field, token):
        raise dr._PublishRefused("nope")

    monkeypatch.setattr(dr, "_record_bytes_for_push", refuse)
    result = _publish(report, run, user, lambda s: None)
    assert result["ok"] is True
    names = _names(bare)
    assert f"runs/{DAY}/{SHA[:7]}/SUMMARY.pdf" in names
    assert any("record.json" in s for s in result.get("skipped") or [])
