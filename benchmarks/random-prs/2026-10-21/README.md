# Random Python PR draw — 2026-10-21

**Purpose.** Three open GitHub pull requests from Python projects, picked at random, to demo and benchmark Proof-of-Change on code we didn't choose. This set is **separate from the research study** (the 92 locked pairs / v1.1). Nothing here feeds the study.

## Filters
Pool collected 21 Oct 2026 (IST) from the public GitHub search API:
- Search: `is:pr is:open draft:false language:python updated:>=2026-10-07 -author:app/dependabot -author:app/renovate -author:app/pre-commit-ci`, sorted by most recently updated, first 1,000 results (GitHub's cap).
- Repo: primary language Python, 200+ stars, pushed on or after 2026-09-21, and has `pyproject.toml`, `setup.py` or `setup.cfg` on its default branch.
- PR: changes at least one `.py` file, 300 or fewer changed lines (added + removed), not docs-only or CI-only, author not an automated account.

Result: **61 PRs** in `pool.json`, sorted by repo name (lowercase) then PR number.

## Seed and draw
`random.Random(20261021)` shuffles the pool's indices; the first three are the PRs drawn. If a drawn PR broke a rule, the next index in that order would replace it and be logged in `drawn.json` under `redraws`. None were needed.

## Redo the draw
```
python3 draw.py pool.json
```
This prints the same three PRs every time.

## Files
- `pool.json`: the filters and all 61 eligible PRs.
- `draw.py`: the draw script.
- `drawn.json`: the three PRs drawn, with head and base commit SHAs at draw time.
- `results/`: Proof-of-Change output for each PR drawn, one automatic and one human-review run each. Start with `results/SUMMARY.md`.
- `ground_truth.json`: what the maintainers did later (merged, closed, reverted), to fill in afterwards.

## Known gap

While the pool was being built, GitHub's limit on logged-out requests cut off one batch of about 15 repositories during the star check. PRs from those repositories never entered the pool. The draw from the pool is still random and reproducible, but the pool is slightly smaller than the filters alone would give.
