"""PDF status next to each report, and a background retry when the first PDF attempt fails.

Every report folder that should have a REPORT.pdf gets a small ``pdf_status.json``:

    {"state": "preparing" | "ready" | "error", "attempts": N, "updated_at": <unix time>}

* ``ready``      REPORT.pdf exists and is non-empty.
* ``preparing``  the first attempt (Chrome, then the built-in PDF maker) failed; a detached background
                 worker keeps regenerating the PDF from the saved REPORT.html with backoff.
* ``error``      every background try failed. An error is logged for maintainers. Users still only see
                 "PDF preparing…" (no workaround is offered to them).

The record, its verdict and the HTML/Markdown reports are never touched here: this module only reads
REPORT.html and writes REPORT.pdf and pdf_status.json. Error text is never written to the status file,
so nothing private can leak through it.

Run the worker by hand: ``python -m reports.pdf_status retry <report folder>``.
"""
from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import time
from pathlib import Path

STATUS_FILE = "pdf_status.json"
PDF_FILE = "REPORT.pdf"
HTML_FILE = "REPORT.html"
PREPARING, READY, ERROR = "preparing", "ready", "error"
# 5 tries over roughly ten minutes: waits before each try, in seconds.
RETRY_DELAYS_S = (15, 45, 90, 180, 270)
NO_RETRY_ENV = "POC_PDF_NO_BACKGROUND_RETRY"

log = logging.getLogger("proof_of_change.pdf")


def _pdf_ok(pdf: Path) -> bool:
    try:
        return pdf.is_file() and pdf.stat().st_size > 0
    except OSError:
        return False


def write_status(report_dir: str | Path, state: str, attempts: int = 0) -> Path:
    """Atomically write pdf_status.json (state + attempt count + time only, never error text)."""
    if state not in (PREPARING, READY, ERROR):
        raise ValueError(f"unknown PDF state {state!r}")
    d = Path(report_dir)
    d.mkdir(parents=True, exist_ok=True)
    p = d / STATUS_FILE
    tmp = d / (STATUS_FILE + ".tmp")
    tmp.write_text(json.dumps({"state": state, "attempts": int(attempts), "updated_at": round(time.time(), 1)}))
    os.replace(tmp, p)
    return p


def read_state(report_dir: str | Path) -> str | None:
    """'ready' when the PDF exists (whatever the file says); else the saved state; None if nothing is known."""
    d = Path(report_dir)
    if _pdf_ok(d / PDF_FILE):
        return READY
    try:
        state = json.loads((d / STATUS_FILE).read_text()).get("state")
    except (OSError, ValueError, AttributeError):
        return None
    if state == READY:  # file says ready but the PDF is gone: treat it as still being prepared
        return PREPARING
    return state if state in (PREPARING, ERROR) else None


def user_label(state: str | None) -> str | None:
    """What a user sees while the PDF is missing. Same text for preparing and error: no workaround is shown."""
    return "PDF preparing…" if state in (PREPARING, ERROR) else None


def start_background_retry(report_dir: str | Path) -> bool:
    """Start a detached worker that survives the check process. Returns False when disabled or it fails to start."""
    if os.environ.get(NO_RETRY_ENV):
        return False
    d = Path(report_dir).resolve()
    repo_root = Path(__file__).resolve().parent.parent
    try:
        subprocess.Popen(  # noqa: S603 - fixed argv, our own module
            [sys.executable, "-m", "reports.pdf_status", "retry", str(d)],
            cwd=str(repo_root), stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            start_new_session=True, close_fds=True)
    except OSError as e:
        log.error("PDF background retry could not start for %s: %s", d.name, type(e).__name__)
        return False
    return True


def after_first_attempt(report_dir: str | Path, error: str | None) -> str:
    """Record the result of the first PDF attempt; on failure mark 'preparing' and start the background retry."""
    d = Path(report_dir)
    if error is None and _pdf_ok(d / PDF_FILE):
        write_status(d, READY, 1)
        return READY
    write_status(d, PREPARING, 1)
    if os.environ.get(NO_RETRY_ENV):  # tests and dry runs: record 'preparing' only
        return PREPARING
    if not start_background_retry(d):
        # The worker could not start: try the same loop in a daemon thread of this process as a last resort.
        import threading
        threading.Thread(target=retry_until_ready, args=(d,), daemon=True, name="pdf-retry").start()
    return PREPARING


def retry_until_ready(report_dir: str | Path, delays=RETRY_DELAYS_S, sleep=time.sleep, to_pdf=None) -> str:
    """Regenerate REPORT.pdf from the saved REPORT.html with backoff until it exists. Returns the final state."""
    d = Path(report_dir)
    pdf, html_p = d / PDF_FILE, d / HTML_FILE
    if to_pdf is None:
        from reports import reviewer as rv
        to_pdf = rv.to_pdf
    attempts = 1
    for wait in delays:
        if _pdf_ok(pdf):
            break
        sleep(wait)
        attempts += 1
        try:
            if html_p.is_file():
                to_pdf(str(html_p), str(pdf))
        except Exception:  # noqa: BLE001 - keep trying; the final failure is logged below
            pass
        if _pdf_ok(pdf):
            break
        write_status(d, PREPARING, attempts)
    if _pdf_ok(pdf):
        write_status(d, READY, attempts)
        try:  # swap "PDF preparing…" for the real link on any hosted GitHub App page
            from poc import github_app
            github_app.publish_ready_pdf(d)
        except Exception:  # noqa: BLE001 - the PDF exists; the console finds it on its own
            pass
        return READY
    write_status(d, ERROR, attempts)
    log.error("PDF still missing after %d attempts for report %s; HTML and Markdown reports are unchanged",
              attempts, d.name)
    print(f"ERROR: PDF still missing after {attempts} attempts for report {d.name}", file=sys.stderr, flush=True)
    return ERROR


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 2 or argv[0] != "retry":
        print("usage: python -m reports.pdf_status retry <report folder>", file=sys.stderr)
        return 2
    logging.basicConfig(level=logging.INFO)
    return 0 if retry_until_ready(argv[1]) == READY else 1


if __name__ == "__main__":
    raise SystemExit(main())
