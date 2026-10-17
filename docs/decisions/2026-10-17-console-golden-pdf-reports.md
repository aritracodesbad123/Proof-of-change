# Console serves golden-format PDF reports

**Date:** 2026-10-17  
**Status:** accepted

## Context

Operators want the same reviewer PDF as `reports/samples/golden-v1/*/REPORT.pdf` (verdict, claims, pass/fail, trust checks) after a console PR check. `daily_run` already calls `reports/pr_report.render_run`, but the Docker image had no Chromium so PDFs were skipped, and the SPA did not link to `REPORT.pdf`.

## Decision

1. Install Chromium in the console image; set `BR_CHROME` for `reviewer.to_pdf`.
2. Resolve reports under `reports/daily/<day>/<dir>/REPORT.{pdf,html}` and expose `GET /api/runs/<id>/report.pdf|.html`.
3. Analysis (and finished job) UI links: Open PDF report / Open HTML report.

## Consequences

Free Render still loses files on sleep; download while the service is up. Image size grows with Chromium.
