# Known-answer benchmark

Small made-up pull requests on a tiny package (`toypkg`), each with a frozen expected verdict.

- `cases/<ID>/before/`, `after/`: the changed files on each side. `claim.txt`: the pull request's claim.
  `recorded.json`: the evidence a run would record (per-run test results P/F/E for main then the PR, probe
  observations and changed-line coverage, install errors). No case file contains an expected verdict.
- `answer_key.json`: expected verdict per case, mode (`full`, `tests`) and route (`single`, `daily`, `helper`).
  Only `score.py` reads it.
- `run_case.py`: runs one case through the real verdict code and gates; refuses answer files.
- `build_cases.py`: writes the case folders. `python -m evals.bench12.build_cases`
- Score: `python -m evals.bench12.score`. CI runs it through `tests/test_bench12.py`.

The suite checks the verdict rules against fixed recorded evidence. It does not test package installs or how good
the AI's probes are; the runs on random real pull requests cover that.
