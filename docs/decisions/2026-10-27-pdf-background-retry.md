# PDF background retry: no PDF goes missing unnoticed

Date: 2026-10-27

## Context

Every finished check writes REPORT.md, REPORT.html and REPORT.pdf. The PDF is made by headless Chrome,
with a built-in pure-Python PDF maker as the fallback. If both fail when a check finishes, the PDF was
simply missing and nothing told anyone.

## Decision

- Each report folder gets a small `pdf_status.json` next to the report: `preparing`, `ready` or `error`,
  with the number of attempts and a timestamp. It never holds error text.
- If the first attempt fails, the status is `preparing` and a detached background worker
  (`python -m reports.pdf_status retry <report folder>`, in its own session so it outlives the check)
  regenerates the PDF from the saved REPORT.html. It tries 5 times with growing waits
  (15 s, 45 s, 90 s, 3 min, 4.5 min: about 10 minutes in total). If the worker cannot start,
  the same loop runs in a background thread instead.
- When the PDF exists the status becomes `ready`. The web console swaps "PDF preparing…" for the real
  download link (the run page re-checks every 20 seconds, and job views refresh the link on each poll).
  GitHub App hosted pages that showed "PDF preparing…" are updated to link the PDF.
- After the final failed try the status becomes `error`, an error is logged for maintainers, and users see
  a clear "PDF could not be generated." in the console, on the hosted page and in the App's PR comment
  and check run. Nothing says "preparing" forever.
- The GitHub App saves the id of its own PR comment and check run (`github_comment.json` in the report
  folder) when it posts "PDF preparing…". When the retry ends, it edits those same two items in place
  (PATCH), with the PDF link or the failure line. It never posts anything new, edits only items it posted,
  only on the PR the check ran for, and only on allowed demo repos. A second edit is a no-op, and nothing
  is edited when no id was saved. If the PDF was ready when posting, the comment already has the link.
- Hosted App mode refuses to start without `POC_REPORT_BASE_URL`, so every link in a comment works.
- PDFs are written to `REPORT.pdf.tmp`, checked to start with `%PDF`, then renamed into place, so nobody
  ever reads a half-written file.
- A lock file (`.pdf.lock`) per report folder stops two workers from writing the same PDF.
- On startup (App and console) any folder still `preparing` gets its retry restarted, or is marked
  `error` once it is older than the retry window plus 5 minutes.
- Reports no longer skip the PDF when Chrome is missing: the built-in PDF maker makes it right away.
- While the App runs, a background sweep (`PendingEditSweeper`, every `EDIT_SWEEP_INTERVAL_S` = 5 minutes)
  retries any comment/check-run edit still pending (`done` null) once its PDF is ready or failed, with no
  waits inside the sweep. After `EDIT_SWEEP_MAX_ATTEMPTS` (12) sweeps or `EDIT_SWEEP_MAX_AGE_S` (6 hours)
  it gives up: `done` becomes `gave_up`, `final_error` is saved in `github_comment.json`, and a plain error
  is logged. The sweep never raises or blocks webhook handling, and stops cleanly on shutdown.
- The record, the verdict and the HTML/Markdown reports are never changed by any of this.

## Consequences

- A missing PDF is always visible: "PDF preparing…" while retrying, then the link or a clear failure line,
  plus a logged error for maintainers.
- Tests mock the PDF writer, the worker start and the waits; no test starts a real worker
  (`POC_PDF_NO_BACKGROUND_RETRY` is set for the whole test suite).
