## Scoring: 30-PR random batch (code version 0fa0016)

30 merged pull requests from public Python projects, drawn at random with a fixed seed (20261022; list in `drawn.json`). Every check ran on Proof-of-Change at commit `0fa0016`, finishing on 22 Oct 2026 at 11:03 IST. All 30 runs completed; none crashed.

### Verdicts

| Verdict | Count |
|---|---|
| Verified | 0 |
| Needs attention | 6 |
| Could not verify | 24 |

Two more runs (oyvindwe/connectlife-ha #742, doobidoo/mcp-memory-service #1531) first found a difference, but the run failed its own trust checks, so the published verdict is "could not verify".

### Why: breakdown of reasons

| Reason | Runs |
|---|---|
| Setup failure: install failed | 12 |
| Difference found between main and PR | 6 |
| Changed code not exercised (incl. docstring-only) | 4 |
| Setup failure: setup gap | 3 |
| Tests did not run or collect | 3 |
| Run failed its own trust checks | 2 |

Setup failures (install failed or setup gap) total 15 of 30. This is the biggest weakness the batch shows.

### Timing

Median run: 2 min 43 s. Fastest: 17 s. Slowest: macs3-project/MACS #784 (341 min 49 s), optiland/optiland #963 (70 min 1 s), optuna/optuna #6873 (70 min 1 s). The 5 h 42 min MACS #784 run is the outlier.

### Accuracy: not measured for this batch

Catches, misses and false alarms count only where there is outside proof of the right answer: a later revert, a follow-up bug report blaming the PR, or a maintainer's explicit confirmation. Passing maintainer CI and a closed linked issue do not count. We searched GitHub for reverts and follow-up fixes for all 30 PRs (`labels.json`) and found none, so **all 30 PRs are unlabelled** and no accuracy, false-alarm or miss rate is reported. No labels were invented.
