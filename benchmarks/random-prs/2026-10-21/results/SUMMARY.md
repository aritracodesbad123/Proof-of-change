# Results: random Python PR draw, 2026-10-21

All six runs used **Proof-of-Change main at `5492834eef22efd122549356c73d26b3d0ae040a`**. That commit includes `a8d083d`. Each run was a real product check on a local Linux machine:

```
python ops/daily_run.py --pr <url> --model-provider nebius --swarm --console-job \
  --product-check --related-reports --sandbox-backend local
```

- The environment was the one the operator console sets for a check: `POC_CONSOLE=1` and `POC_SWARM=1`. Review runs also set `POC_HITL=1` and a review folder.
- Pull-request code ran under the bubblewrap sandbox.
- Nothing was posted to the upstream projects: every record has `posted_upstream: false`.
- Keys came from the machine's environment and are not in any file here.

Each PR has two folders:

- `automatic/`: the check with no person involved.
- `human-review/`: the same check with a human reviewer. Each has a `REVIEW_NOTE.md` that says what was kept, dropped or added, and why.

Every folder holds `REPORT.md`, `REPORT.html`, `REPORT.pdf`, `record.json`, `run-log.txt` and `timing.txt`. Where they exist, it also holds `pr.diff` and the probe files, saved as `.py.txt` so they are not run or linted.

| PR | Automatic | Human review | Duration (auto / review) | Ground truth (2026-10-21 19:50 IST) |
|---|---|---|---|---|
| [pahaz/sshtunnel#304](https://github.com/pahaz/sshtunnel/pull/304) | COULD NOT VERIFY: no tests map to the packaging files | NEEDS ATTENTION: installed metadata changed (Download-URL, Home-page, Author, Platform, Requires-Python) | 27 s / 77 s | still open, so no comparison yet |
| [home-assistant-libs/pychromecast#1300](https://github.com/home-assistant-libs/pychromecast/pull/1300) | COULD NOT VERIFY: the PR's new tests pass, but the one AI probe crashed, so its claims are unproven | NEEDS ATTENTION: flags come from probe set-up mistakes, not from a regression (see the note) | 274 s / 317 s (includes the review pause) | still open, so no comparison yet |
| [PostHog/posthog#120637](https://github.com/PostHog/posthog/pull/120637) | setup failure: install failed, the project needs Python 3.14.7 | setup failure: the Python 3.14 interpreter was not visible in the sandbox | 91 s / 107 s | merged 2026-10-21 15:39 IST, after the draw; neither run counts as a verdict, so there is no match to score |

Durations are wall-clock times from start to finish of the command, measured outside the tool.

## Comparison with ground truth

- **sshtunnel#304** and **pychromecast#1300** are still open, so there is nothing to compare against yet.
- **posthog#120637** was merged by its maintainers. Proof-of-Change gave no verdict on it (setup failure on both runs), so this is **neither a match nor a mismatch**. It is a coverage gap: the check cannot yet install a project that pins an exact Python 3.14 release.

## Problems seen, stated plainly

1. **Main moved during the runs.** A single-PR check fast-forwards its checkout to `origin/main` before it starts. Main received several merges while these runs were going (#79, #80, #82 and #83). One review run hit `TypeError: measure() got an unexpected keyword argument 'require_all'`. That happened because one module was loaded before the fast-forward and another after it: a harness race, not a PR result.
   - All six runs were then repeated from one fixed copy of commit `5492834` without git history, with `POC_COMMIT` set. That is the same mechanism the container images use. Only those six runs are reported here.
   - Main moved again afterwards (#81 and #84). Those merges were not used.
2. **The AI probes are not repeatable.** Earlier automatic runs of pychromecast#1300, on commit `10244bf`, gave NEEDS ATTENTION. The cause was a probe whose claim patterns matched none of its observation names. On `5492834` the probe crashed instead, giving COULD NOT VERIFY. In both cases the project's own tests agreed: 5 new tests pass, 1 unchanged, 95% of changed lines covered.
3. **The review pause only opens when the AI drafts probes.**
   - For sshtunnel#304 no AI probe was drafted, so the reviewer's test was added as a fixed probe file for that run.
   - For posthog#120637 the install failed before any probe was drafted.
4. **PR head moved.** pychromecast#1300 was checked at its current head `e863b6d`, not at the head recorded at draw time (`ab0d59e`).
5. **Public-text rule.** This repository fails CI on certain words and on machine-local paths. To comply:
   - The file of drawn PRs is now `drawn.json`, with the key `drawn`.
   - Local paths in logs and reports were replaced with placeholders such as `<run-folder>`. The PDFs were re-rendered from the cleaned HTML.
   - posthog's `pr.diff` was left out, and one quoted word in a related-report snippet in its `record.json` was redacted.
   - The reviewer is called "the human reviewer".
