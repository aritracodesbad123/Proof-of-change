# Benchmark cases test their pinned commits; a slow PDF never stops a check

Status: proposed

## What happened

In the final live run, four benchmark cases (attrs, jsonschema, markupsafe, rich) were reported as not run.
The benchmark runner started each case as an ordinary pull-request check, so the check compared the
project's current base-branch tip and GitHub's current test merge, not the commits the case file pins.
Upstream had moved since the cases were written, and the runner's own commit check correctly refused the
results. markupsafe also hit a one-off Contree network (transport) error.

Two real pull-request checks finished their verdicts but then waited forever on headless Chrome while
printing the PDF report, so the run recorded them as errors. The same Chrome also hangs on a small
local report with no remote fonts or images, so the cause is Chrome start-up, not the report.

## What changed

1. `bench/run.py` passes each case file's `base_sha` and `head_sha` to the check as `--base-sha` /
   `--head-sha`. With those flags the check clones the repository, fetches exactly those two commits and
   tests main = `base_sha`, PR = `head_sha`. No base-branch tip, merge ref or merge-base is looked up. The
   commits come only from the case file; there are no per-repository settings. The flags must come
   together, as full 40-character SHAs, with exactly one `--pr`; otherwise the check refuses to start.
   The pull-request text and diff shown to the claim step are still read from GitHub.
2. The benchmark runner retries a case once, and only when the record says Contree could not be reached
   (`ContreeTransportError`). A test failure, a setup gap, any other Contree failure or any verdict from
   tests that ran is never retried. The result notes whether a retry happened.
3. The PDF always arrives. Each PDF starts a fresh headless Chrome with its own temporary profile, extra
   flags that stop background network, keychain and first-run waits, a 60-second hard limit and its own
   process group; on a hang the whole group is killed (a leftover helper holding the output pipe was what
   kept the run waiting). If Chrome is missing, fails or hangs, a built-in pure-Python PDF maker
   (reportlab, a normal Python dependency, no OS packages) renders the same report straight away. Only if
   both fail is `pdf_error` set, starting with "ERROR:", and logged for the team; users see no workaround.
   Report rendering as a whole is guarded: if it fails the check keeps its exit code; records and
   verdicts are written before reports and are never changed. A CI test builds a PDF for every saved
   sample report in the repository with the built-in maker and fails if any is missing or empty.
4. Product checks record a `timings` map (seconds per step: checkout, Tavily lookup, Python setup,
   dependency install, each side's install and tests, each model call, probes, verdict, record) and the
   report shows it as a short table. Report and PDF time is printed by the run. Timing only; study
   records do not get the field.

## What did not change

- Verdict rules, the answer key and the study route: without the new flags every run behaves exactly as
  before.
- Live product checks (console, GitHub App, request worker) never pass the new flags.

## Tests

`tests/test_bench_pinned_and_pdf_timeout.py`: the pinned commits reach the command and the checkout uses
them, not the tips; one retry on a transport error and no retry otherwise; a hanging Chrome is stopped
and only the PDF is skipped; a report failure leaves the record and exit code as they were.
