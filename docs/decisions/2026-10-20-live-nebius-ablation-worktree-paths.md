# Live Nebius ablation records and absolute worktree paths

## What changed

Live Nebius Token Factory A/B/C dual-run results for mlxtend pull request 1229 are tracked under `reports/hackathon-ablation-nebius/` (summary plus slim per-baseline records), and `reports/AGENT_SWARM_EVALUATION.md` documents the measured verdicts and costs.

`ops/daily_run.py` and `ops/bench.py` now pass **absolute** paths to `git worktree add` when checking out the main and PR sides of a source pair. `ops` / work roots from `--ops-dir` / `--work-dir` are also resolved to absolute paths at startup. A bench-mode test expectation was updated to match.

## Why

`git -C <clone> worktree add <path>` resolves a **relative** `<path>` against the clone directory, not the process working directory. With a relative `--ops-dir`, checkouts landed nested under `src/.../side-main` while install still looked for `work/side-main`, so `uv pip install -e` failed with “Distribution not found” and live ablation never reached pytest or probes.

## Decision

Always resolve worktree destinations (and the ops/work roots) to absolute paths before calling git. Publish slim live records under `reports/` because full dual-run trees under `ops/runs/` stay gitignored.

## Alternatives and tradeoffs

- Require callers to pass absolute `--ops-dir` only: easy to forget; the bug would return on relative paths.
- Change clone layout so worktrees are always under `src/`: larger refactor than resolving paths.
- Commit full `ops/runs/` trees: large, machine-local, and already ignored on purpose.

## What it means for you

Relative `--ops-dir` / `--work-dir` on a laptop should install and dual-run correctly. Judge-facing live Nebius numbers for mlxtend#1229 live in `reports/hackathon-ablation-nebius/` and the evaluation report; regenerating them still needs `NEBIUS_API_KEY` and a long dual-run.
