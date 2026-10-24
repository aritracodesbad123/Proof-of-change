## Scoring: 20 finished Contree checks (stopped early)

Open pull requests from 20 Python projects, checked in Contree on Proof-of-Change commit `863751e` (23 Oct 2026). The batch was stopped on 24 Oct 2026 while it was still running. 20 checks had finished. 10 had not, and they are listed as not run. Verdicts are the ones in each run's own `record.json`. Two checks exited with a harness error and have no verdict file; their reason is the line in `REPORT.md`.

The 120 second HTTP timeout is not in commit `863751e`. Each check fast-forwards to main before it starts, so these runs used the Contree SDK's 10 second HTTP timeout.

### Verdicts

| Verdict | Count |
|---|---|
| Verified | 0 |
| Needs attention | 3 |
| Could not verify | 15 |
| No verdict file | 2 |
| Not run | 10 |

### Why a check could not verify

The sentence is a reading of the record's reason. The record text is in the results table and is unchanged.

| Runs | Why | Pull requests |
|---|---|---|
| 4 | No project test could be mapped to the files the pull request changed, so the change cannot be verified. | pytoolz/toolz #56, WhyNotHugo/python-barcode #162, lincolnloop/python-qrcode #337, pyinvoke/invoke #957 |
| 1 | Pytest produced no results on one side, so the two sides could not be compared. | mahmoud/boltons #43 |
| 1 | The project's tests ran, but a probe was not adequate or a claim had no matching observation, so the change stays could not verify. | PyCQA/isort #2682 |
| 1 | The tests ran, but coverage produced no data, so the check is not allowed to say verified. | python-jsonschema/jsonschema #1459 |
| 2 | Contree's HTTP call timed out (the SDK allows 10 seconds for one poll) and the check exited with no verdict file. Pull-request code was not run locally. | pallets/click #2784, python-attrs/attrs #1357 |
| 6 | Contree could not prepare the main and pull-request sides: one HTTP call exceeded the SDK's 10 second timeout, so the sandbox was cancelled. Pull-request code was not run locally. | psf/requests #5922, Textualize/rich #2556, encode/httpx #2997, Delgan/loguru #86, pallets/markupsafe #512, andialbrecht/sqlparse #698 |
| 1 | Cloning the repository from GitHub failed on the machine running the check (the connection was reset, then a later fetch timed out). Contree did not run. | urllib3/urllib3 #2888 |
| 1 | A test module failed to import during setup, so the check stopped before a comparison. | pyutils/line_profiler #322 |

### Known bugs named by the pull request

A number in this table is an issue the pull request text says it fixes, or a linked issue URL from that text. Naming an issue is not proof the change is wrong or right, so every pull request stays `unlabelled` in `labels.json`. No catch rate, miss rate, or false-alarm rate is reported.

| Pull request | Named by the pull request |
|---|---|
| pallets/itsdangerous #428 | #420 |
| PyCQA/isort #2682 | #2680 |
| python-jsonschema/jsonschema #1459 | #1159 |
| pallets/click #2784 | #2783 |
| psf/requests #5922 | https://github.com/psf/requests/issues/5921 |
| Delgan/loguru #86 | https://github.com/Delgan/loguru/issues/59 |
| pallets/markupsafe #512 | #511 |
| PyCQA/isort #2588 | #1852 |
| python-jsonschema/jsonschema #1534 | #1533 |
| Textualize/rich #2697 | https://github.com/Textualize/rich/issues/2338 |
| pytest-dev/pytest #14709 | #12592, #13257 |

