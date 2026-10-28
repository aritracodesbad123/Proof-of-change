# A PDF on every exit: placeholders, refusals, stop signals, bench and report errors

Status: proposed

## What changed

Every way a check or batch can end now leaves a PDF of the results and the go/no-go verdict:

- Before each check, a could-not-verify placeholder REPORT.pdf and record.json say that the check started but did
  not finish. The real report and record replace them.
- Early refusals, provider refusals, login failures, a held run lock, crashes and a stop signal (SIGTERM) write a
  no-go SUMMARY.pdf that gives the reason.
- Bench mode writes one PDF per case and a summary in a `finally` block.
- If the full report fails, each PR's PDF is written separately, plus a summary. An empty run writes a "nothing
  tested" summary.
- After the console's time limit kills a check, it writes a could-not-verify report and a no-go summary.

## Why

The PDF must always be generated, even after a timeout, crash, refusal, missing key or kill. Before, a run could end
without any PDF: refusals returned before reports, bench mode never wrote PDFs, a killed process left nothing, and
one report error lost every PDF.

## Decision

Last-resort PDFs (`poc/pdf_always.py`) use only the built-in maker: reportlab, or a small hand-written PDF when
reportlab is missing. They read verdicts through `poc/final_verdict.final()`. A placeholder record has its own
record kind: `--resume` never reuses it, and `final()` always reads it as could_not_verify. A killed check therefore
appears in the summary and in scoring as could_not_verify and can never count as anything better. The console only
treats a real record as a finished check.

## Alternatives and tradeoffs

Emailing reports was rejected, since nothing is ever emailed or sent. Writing reports only at the end is simpler but
loses them on a kill. The last-resort PDFs are plain text, not the full reviewer report.

## What it means for you

Look for SUMMARY.pdf in the run's reports folder after any run. A "NO-GO, could not run" summary gives the reason.
A COULD NOT VERIFY report that says the check did not finish means the process was stopped. Success,
`--no-report` and `--select-only` add no extra PDF.
