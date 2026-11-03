# Run PDFs are saved on a runs branch

## What changed

As soon as a run has written its PDFs and the go/no-go summary, the run copies them to a `runs` branch on
origin. Each `REPORT.pdf`, the `SUMMARY.pdf` (including a refused or no-go summary), and `record.json` go under
`runs/<date>/<short commit>/<pr id>/`. The short commit is the first 7 characters of the Proof-of-Change commit
the run used. The pr id is the folder name the run already uses for that check, such as `widgets-7`. A run that
only has a no-go summary uses the run folder's name.

The copy is made in a temporary clone. This checkout, and `main`, are not updated and are not switched. If the
`runs` branch does not exist yet, it is created as an orphan branch (a branch with no parent commit). The commit
is authored as Proof-of-Change <proof-of-change@users.noreply.github.com>. The same GitHub token the run already
uses for reads (`GITHUB_TOKEN`, then `GITHUB_POC_TOKEN`, then `GH_TOKEN`) is used for the copy.

The copy is tried up to 3 times. After a failed try it waits 1 second, then 2. If the remote branch moved, the
temporary clone rebases onto that tip and tries the update again. PDFs are never emailed.

Before anything is copied, every file is checked with the same public-file rules used on main. In `record.json`
and other text, machine-local paths are rewritten as relative paths, and keys and tokens (including a bearer
header) are removed. A PDF is read with `pdftotext`. If that text still has an internal path, a secret, or any
other public-file failure, the PDF is not copied. That is a failed save, with the same banner, and nothing
unscrubbed is pushed.

The GitHub token is not put in the remote address, in a command, or in anything the run prints. Git asks a
small helper for the password. `run.log`, the report, error text and `pdf_push.url` are checked again so a
token cannot remain there.

If there is no token, or every try fails, the run still finishes and the local files stay. The report and
`run.log` then start with the line `PDFs NOT saved to GitHub: <reason>`. Each record gains
`pdf_push`, with `ok`, `attempts`, `error` and `url`.

## Why

A run's PDFs lived only on the machine that ran the check. When that machine went away, the report went with it.
The run has to put the PDFs somewhere that outlives the machine, without posting anything on the pull request
under test and without changing the checkout the operator is using.

## Decision

- Push only the PDFs and `record.json`, from a temporary clone, onto `runs`. Do not push logs, HTML, or the
  checkout.
- Create `runs` as an orphan branch when it is missing. Rebase when the remote tip has moved. Do not overwrite
  the branch.
- Retry 3 times with a short wait. A failed copy never fails the run.
- Say so in plain words in the report and in `run.log`, and store `pdf_push` on the record.
- Scrub text with the public-file rules before copying it. Do not copy a PDF whose text still fails those rules.
- Keep the token out of the remote address and out of every line the run prints.
- Do not email PDFs. Do not change how a verdict is chosen.

## Alternatives and tradeoffs

- Copying from the operator's checkout would have been shorter, and it would have risked leaving that checkout
  on `runs` or with a half-finished commit. A temporary clone keeps the checkout where it was.
- Waiting until a later job copies the files would miss a run that stops as soon as the PDFs exist. The run
  copies them itself, immediately.
- Three tries with a short wait will not outlast a long outage. The local files and the banner remain, so the
  gap is visible.

## What it means for you

After a run, the PDFs and the record are on the `runs` branch under that day's date, the short commit, and the
check's folder name. The record's `pdf_push.url` is the path. If the copy did not happen, the report and
`run.log` say `PDFs NOT saved to GitHub:` and the reason, and the PDFs are still in the local run folder.
Nothing is sent by email. The verdict is unchanged.

## Offline proof

`tests/test_run_pdf_push.py` uses a local bare repository as origin. It covers a first successful copy onto a
new orphan branch, a retry after one rejection (the earlier remote commit is kept), a rejection on every try
(the banner, and the local files stay), and a run with no token (no branch is created, and the banner is
shown). A record that names a machine path and a fake key is copied only after that text is rewritten. A PDF
whose text still names a machine path is not copied, and the banner says so. `run.log`, the report and
`pdf_push` do not contain the token on a success or a failure. No pull request is contacted.
