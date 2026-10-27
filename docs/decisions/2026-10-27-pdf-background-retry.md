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
- After the final failed try the status becomes `error` and an error is logged for maintainers.
  Users keep seeing "PDF preparing…"; no workaround is offered to them.
- The record, the verdict and the HTML/Markdown reports are never changed by any of this.

## Consequences

- A missing PDF is always visible: either as "PDF preparing…" to users, or as a logged error.
- Tests mock the PDF writer, the worker start and the waits; no test starts a real worker
  (`POC_PDF_NO_BACKGROUND_RETRY` is set for the whole test suite).
