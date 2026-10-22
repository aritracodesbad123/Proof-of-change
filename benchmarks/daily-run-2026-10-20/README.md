# Daily run, 20 October 2026: all 26 pull requests

**Summary.** On 20 Oct 2026 the daily run checked 26 open pull requests from Python libraries, from 2026-10-20 11:27 IST to 2026-10-20 13:06 IST (98.7 minutes). It ran on Proof-of-Change commit `84787592503968e99f7cac8e78323d874f5b0f90` (`8478759`), using the local bubblewrap sandbox and live Nebius models in full mode. Today's rules on `main` are stricter, so some of these verdicts would come out differently if the same PRs were checked now. In particular, this run came before the coverage cap, so the 4 "verified" results were not held to today's coverage rule.

| Verdict | Count |
|---|---|
| verified | 4 |
| needs_attention | 8 |
| could_not_verify | 14 |
| **Total** | **26** |

Wall time per PR: 62–830 s, median 158 s. One of the could_not_verify results is a setup failure (numpy#32759). Five other libraries were not checked because the run hit GitHub's limit for anonymous reads (joblib, pyjanitor, pandas, scikit-learn, xarray).

| PR | Verdict | Reason in plain words | Wall time |
|---|---|---|---|
| [dask/dask#12645](https://github.com/dask/dask/pull/12645) | needs_attention | A claimed no-change result did change; one other claim proven. | 94 s |
| [zarr-developers/zarr-python#4518](https://github.com/zarr-developers/zarr-python/pull/4518) | could_not_verify | Wrong-commit guard: the installed commit couldn't be checked (no install record). | 102 s |
| [more-itertools/more-itertools#1333](https://github.com/more-itertools/more-itertools/pull/1333) | verified | Tests pass on both sides; 5 claims proven by probes. | 124 s |
| [pytoolz/toolz#650](https://github.com/pytoolz/toolz/pull/650) | could_not_verify | A claimed difference didn't show up in any probe. | 62 s |
| [pytoolz/toolz#639](https://github.com/pytoolz/toolz/pull/639) | could_not_verify | No AI probe ran a changed line. | 80 s |
| [pytoolz/toolz#641](https://github.com/pytoolz/toolz/pull/641) | needs_attention | 3 claimed differences didn't show up. | 67 s |
| [hgrecco/pint#2498](https://github.com/hgrecco/pint/pull/2498) | needs_attention | 2 claimed differences didn't show up; 2 claims proven. | 122 s |
| [hgrecco/pint#2497](https://github.com/hgrecco/pint/pull/2497) | needs_attention | 2 results changed although the claim said they wouldn't. | 141 s |
| [hgrecco/pint#2501](https://github.com/hgrecco/pint/pull/2501) | needs_attention | 14 differences appeared that no claim covers. | 187 s |
| [feature-engine/feature_engine#1112](https://github.com/feature-engine/feature_engine/pull/1112) | could_not_verify | Docstring-only change; no AI probe ran a changed line. | 770 s |
| [feature-engine/feature_engine#1110](https://github.com/feature-engine/feature_engine/pull/1110) | needs_attention | One difference appeared that no claim covers; one claim proven. | 756 s |
| [feature-engine/feature_engine#1108](https://github.com/feature-engine/feature_engine/pull/1108) | could_not_verify | Several claimed differences didn't show up in any probe. | 236 s |
| [narwhals-dev/narwhals#4068](https://github.com/narwhals-dev/narwhals/pull/4068) | verified | New tests pass; probe results identical on both sides. | 203 s |
| [narwhals-dev/narwhals#4046](https://github.com/narwhals-dev/narwhals/pull/4046) | could_not_verify | 18 new or changed tests skipped: optional modules pandas and pyarrow weren't installed. | 107 s |
| [narwhals-dev/narwhals#4088](https://github.com/narwhals-dev/narwhals/pull/4088) | verified | Tests identical on both sides (30 failures already present on main). | 81 s |
| [skrub-data/skrub#2337](https://github.com/skrub-data/skrub/pull/2337) | could_not_verify | Changed code never ran: 0 of 3 changed lines ran. | 177 s |
| [skrub-data/skrub#2348](https://github.com/skrub-data/skrub/pull/2348) | could_not_verify | No AI probe ran a changed line. | 830 s |
| [networkx/networkx#8966](https://github.com/networkx/networkx/pull/8966) | verified | New test passes; probe results identical on both sides. | 175 s |
| [networkx/networkx#8791](https://github.com/networkx/networkx/pull/8791) | could_not_verify | A behaviour claim had no probe to test it. | 64 s |
| [networkx/networkx#6919](https://github.com/networkx/networkx/pull/6919) | needs_attention | 2 claimed differences didn't show up. | 186 s |
| [numpy/numpy#32940](https://github.com/numpy/numpy/pull/32940) | needs_attention | 3 claimed differences didn't show up. | 67 s |
| [numpy/numpy#32992](https://github.com/numpy/numpy/pull/32992) | could_not_verify | Docstring-only change; no AI probe ran a changed line. | 127 s |
| [numpy/numpy#32759](https://github.com/numpy/numpy/pull/32759) | could_not_verify | Setup failure: the source build of the PR ran out of memory after 208 s. | 273 s |
| [rasbt/mlxtend#1256](https://github.com/rasbt/mlxtend/pull/1256) | could_not_verify | Docstring-only change; no AI probe ran a changed line. | 257 s |
| [rasbt/mlxtend#1255](https://github.com/rasbt/mlxtend/pull/1255) | could_not_verify | No AI probe ran a changed line (53 new tests pass). | 310 s |
| [rasbt/mlxtend#1254](https://github.com/rasbt/mlxtend/pull/1254) | could_not_verify | No AI probe ran a changed line (17 new tests pass). | 328 s |

**Source.** `ops/runs/2026-10-20/records.jsonl` and `run_meta.json`, from the daily-run output on our machine. These files aren't in the repo on `main`. The reasons are short plain-word versions of each record's own `reason` field; verdicts are copied as recorded.

**Suggested place in the repo:** `benchmarks/daily-run-2026-10-20/` (this write-up as `README.md`, plus `records.jsonl` and `run_meta.json`).
