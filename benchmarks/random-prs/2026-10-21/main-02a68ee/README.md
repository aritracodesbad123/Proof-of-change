# Reruns on main 02a68ee (the results that count)

These are the official results for the 2026-10-21 random PR draw. They were run on main at commit
`02a68eea38919fef2e1b537c3bf5a64bd7c771b5`, which includes every verdict rule merged that day.
The earlier results in `../results/` (main `5492834`) are kept for the record, but the ones here are the ones that count.

Each PR was checked twice: once fully automatic (`automatic/`) and once with a person reviewing the tests (`human-review/`).

| PR | Automatic | Human review | Time (auto / review) |
|---|---|---|---|
| [sshtunnel #304](https://github.com/pahaz/sshtunnel/pull/304) | could_not_verify | could_not_verify | 35s / 62s |
| [pychromecast #1300](https://github.com/home-assistant-libs/pychromecast/pull/1300) | needs_attention | needs_attention | 167s / 533s |
| [posthog #120637](https://github.com/PostHog/posthog/pull/120637) | setup problem | setup problem | 114s / 99s |

- **sshtunnel #304**: only packaging files changed, so no tests reach the change.
- **pychromecast #1300**: the new tests pass, but some behaviour changes the PR claims did not show up.
- **posthog #120637**: a setup limit, not a verdict. The repo needs Python 3.14.7 and the sandbox has Python 3.12, so install failed and the record says could_not_verify.

## Files per run
`REPORT.md` / `REPORT.html` / `REPORT.pdf` (the report), `record.json` (the verdict record), `SOURCE.json`, `run-log.txt`, `timing.txt`.
The pychromecast human-review run also has `hitl_draft.json` and `hitl_approval.json`. Local file paths in the logs and reports were replaced with relative ones.
