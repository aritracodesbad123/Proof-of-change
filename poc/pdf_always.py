"""Last-resort PDFs, so a check or a batch never ends without one.

Used when the normal reviewer report cannot be made: a check that started but did not finish (placeholder),
a run refused before it started, a provider refusal, a report error, a stop signal or a time-limit kill.
Every PDF here is made by the built-in maker alone: reportlab when it is importable, otherwise a small
hand-written PDF, so even a missing reportlab still leaves a PDF. Nothing here sends anything anywhere.
"""
from __future__ import annotations

import os
import time
from pathlib import Path

PLACEHOLDER_REASON = "the check started but did not finish, so this placeholder was never replaced"


def _esc(s: str) -> str:
    return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _raw_pdf(path: Path, lines: list[str]) -> None:
    """A one-page PDF in plain Helvetica, written by hand (no dependencies)."""
    text = ["BT", "/F1 11 Tf", "14 TL", "50 800 Td"]
    for ln in lines[:52]:
        safe = ln.encode("latin-1", "replace").decode("latin-1")
        for i in range(0, max(len(safe), 1), 95):
            text.append(f"({_esc(safe[i:i + 95])}) Tj T*")
    text.append("ET")
    stream = "\n".join(text).encode("latin-1")
    objs = [b"<< /Type /Catalog /Pages 2 0 R >>",
            b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R "
            b"/Resources << /Font << /F1 5 0 R >> >> >>",
            b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    out, offs = bytearray(b"%PDF-1.4\n"), []
    for i, o in enumerate(objs, 1):
        offs.append(len(out))
        out += b"%d 0 obj\n" % i + o + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
    out += b"".join(b"%010d 00000 n \n" % x for x in offs)
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, xref)
    path.write_bytes(bytes(out))


def write_pdf(path: str | Path, title: str, lines: list[str]) -> Path:
    """Write a simple PDF with the built-in maker only. Never raises for a content problem."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    body = [title, ""] + [str(x) for x in lines] + ["", "Written " + time.strftime("%Y-%m-%d %H:%M %Z")]
    tmp = path.with_name(path.name + ".tmp")
    try:
        from xml.sax.saxutils import escape

        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
        st = getSampleStyleSheet()
        flow = [Paragraph(escape(title), st["Title"]), Spacer(1, 6)]
        flow += [Paragraph(escape(x) or "&nbsp;", st["BodyText"]) for x in body[2:]]
        SimpleDocTemplate(str(tmp), pagesize=A4, title=title).build(flow)
    except Exception:  # noqa: BLE001 - reportlab missing or failed: the hand-written PDF still works
        _raw_pdf(tmp, body)
    os.replace(tmp, path)
    return path


def placeholder(report_dir: str | Path, rid: str, subject: str) -> Path:
    """Before a check starts: a could-not-verify REPORT.pdf that the real report later replaces."""
    return write_pdf(Path(report_dir) / rid / "REPORT.pdf", f"Reviewer report {rid}: COULD NOT VERIFY",
                     [f"Check: {subject}", "Verdict: could_not_verify", f"Reason: {PLACEHOLDER_REASON}."])


def run_placeholder_summary(report_dir: str | Path, name: str) -> Path | None:
    """At run start, unless a SUMMARY.pdf is already there: a no-go summary the real one later replaces."""
    p = Path(report_dir) / "SUMMARY.pdf"
    if p.exists():
        return None
    return write_pdf(p, f"Proof-of-Change summary: {name}: NO-GO",
                     ["Go/no-go: NO-GO, could not verify", "Reason: the run started but did not finish."])


def nogo_summary(report_dir: str | Path, name: str, reason: str) -> Path:
    """A run that could not run (refused, stopped or killed): a no-go SUMMARY.pdf with the reason."""
    return write_pdf(Path(report_dir) / "SUMMARY.pdf", f"Proof-of-Change summary: {name}: NO-GO",
                     ["Go/no-go: NO-GO, could not run", f"Reason: {reason or 'unknown'}"])


def records_pdfs(report_dir: str | Path, name: str, rows: list[tuple[str, dict]], note: str | None = None,
                 stopped: str | None = None) -> Path:
    """One REPORT.pdf per (id, record), each written on its own, then a SUMMARY.pdf (even when rows is empty)."""
    out = Path(report_dir)
    lines, any_attention, any_cnv = [], False, False
    for rid, rec in rows:
        v = str(rec.get("verdict") or "could_not_verify")
        any_attention |= v == "needs_attention"
        any_cnv |= v not in ("verified", "needs_attention", "no_code_change")
        why = str(rec.get("reason") or "")
        try:
            write_pdf(out / rid / "REPORT.pdf", f"Reviewer report {rid}: {v.replace('_', ' ').upper()}",
                      [f"Verdict: {v}", f"Reason: {why}"] + ([f"Note: {note}"] if note else []))
        except Exception:  # noqa: BLE001 - one PR's PDF failing never stops the others or the summary
            pass
        lines.append(f"{rid}: {v}: {why[:160]}")
    if not rows:
        go, lines = "NO-GO, nothing tested", ["No check produced a result."]
    elif any_attention:
        go = "NO-GO, needs attention"
    elif any_cnv:
        go = "NO-GO, could not verify"
    else:
        go = "GO"
    if stopped:
        go = f"NO-GO, could not run: {stopped}"
    head = [f"Go/no-go: {go}"] + ([f"Note: {note}"] if note else []) + [""]
    return write_pdf(out / "SUMMARY.pdf", f"Proof-of-Change summary: {name}", head + lines)


def reports_root() -> Path:
    """Where reviewer reports go by default (POC_REPORT_DIR overrides, as in the console)."""
    env = (os.environ.get("POC_REPORT_DIR") or "").strip()
    return Path(env) if env else Path(__file__).resolve().parents[1] / "reports" / "daily"
