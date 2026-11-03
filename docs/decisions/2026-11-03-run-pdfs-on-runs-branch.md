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

If there is no token, or every try fails, the run still finishes and the local files stay. The report and
`run.log` then start with the line `PDFs NOT saved to GitHub: <reason>`. Each record gains
`pdf_push`, with `ok`, `attempts`, `error` and `url`. Machine-local paths are left out of the copies that are
pushed.

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
shown). No pull request is contacted.
