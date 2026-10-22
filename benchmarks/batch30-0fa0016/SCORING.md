## Scoring: 30-PR random batch (code version 0fa0016)

30 merged pull requests from public Python projects, drawn at random with a fixed seed (20261022; list in `drawn.json`). Every check ran on Proof-of-Change at commit `0fa0016`, finishing on 22 Oct 2026 at 11:03 IST. All 30 runs completed; none crashed. Verdicts are the ones in each run's own `record.json`.

### Verdicts

| Verdict | Count |
|---|---|
| Verified | 0 |
| Needs attention | 8 |
| Could not verify | 22 |

The trust check in the report flags [oyvindwe/connectlife-ha #742](runs/connectlife-ha-742/REPORT.md), [doobidoo/mcp-memory-service #1531](runs/mcp-memory-service-1531/REPORT.md) as untrustworthy (the run failed its own checks), so treat those two needs-attention verdicts with caution.

### Why: breakdown of reasons

| Reason | Runs |
|---|---|
| Setup failure: install failed | 12 |
| Difference found between main and PR | 8 |
| Changed code not exercised (incl. docstring-only) | 4 |
| Setup failure: setup gap | 3 |
| Tests did not run or collect | 3 |

Setup failures (install failed or setup gap) total 15 of 30. This is the biggest weakness the batch shows.

### Timing

From each record's `duration_s.total_wall`. Median run: 2 min 39 s. Fastest: pyrevitlabs/pyRevit #3743 (14 s). Slowest: macs3-project/MACS #784 (341 min 45 s), optiland/optiland #963 (69 min 57 s), optuna/optuna #6873 (69 min 56 s). The MACS #784 run is the outlier.

### Accuracy: not measured for this batch

Catches, misses and false alarms count only where there is outside proof of the right answer: a later revert, a follow-up bug report blaming the PR, or a maintainer's explicit confirmation. Passing maintainer CI or closing a linked issue is not proof. We searched GitHub for reverts and follow-up fixes for all 30 PRs and found none, so **all 30 PRs are unlabelled** (`labels.json`) and no accuracy, false-alarm or miss rate is reported. No labels were invented.
