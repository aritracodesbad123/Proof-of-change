# Random Python PR batch of 30 — drawn 2026-10-21/22 (IST)

**Purpose.** A larger labelled sample, as asked for in review. Separate from the research study (v1.1 stays locked). This file and the PR list are committed **before any result exists**. Results go in a later PR to this folder.

## How the runs will be done
- Proof-of-Change pinned to main `0fa0016ea51794edee0f4a085e41bf48dd813765` (exported copy, `POC_COMMIT` set, so the runner never moves to a newer main).
- Each PR: `ops/daily_run.py --pr <url> --product-check --model-provider nebius`, automatic mode, sandboxed, one at a time. Nothing is posted upstream.
- Labels come only from evidence outside the tool (a later revert, a linked bug report or follow-up fix, or the maintainer's tests). If none is found, the PR is **unlabelled**.
- Every outcome is published, including failures, could_not_verify and setup problems.

## Pool (`pool.json`, built by `build_pool.py`)
Public GitHub search API, collected 21–22 Oct 2026 (IST):
- Search: `is:pr is:merged draft:false language:python merged:<range> -author:app/dependabot -author:app/renovate -author:app/pre-commit-ci`, four date ranges (7–10, 11–13, 14–16, 17–20 Oct 2026), first 1,000 each, sorted by most recently updated. 3,980 PRs returned.
- Repo: primary language Python, 200+ stars, pushed on or after 2026-09-21, not archived, has `pyproject.toml`, `setup.py` or `setup.cfg` on its default branch.
- PR: merged, author not an automated account, 300 or fewer changed lines, changes at least one non-test `.py` file **and** at least one test `.py` file (`tests/`, `test_*.py`, `*_test.py`, `conftest.py`).

Result: **81 PRs** from 726 repositories checked. Same filters as `../2026-10-21/`, except the PRs here are merged (so later evidence can label them) and must include test changes.

## Seed and draw
`random.Random(20261022)` shuffles the pool's indices (`draw.py`). PRs are taken in that order, at most 3 per repository; skipped indices are listed in `drawn.json`. Redo with `python3 draw.py pool.json`.

## Known gaps
- One repository lookup failed on a network error during the pool build, so its PRs never entered the pool.
- The filters don't exclude applications (for example Home Assistant integrations or ERPNext). Those are expected to hit limitation L5 (app-style repos) and will be reported as setup problems, not dropped.

## The 30 PRs
| # | PR | Title | Merged (UTC) |
|---|---|---|---|
| 1 | [Second-Hand-Friends/kleinanzeigen-bot #1361](https://github.com/Second-Hand-Friends/kleinanzeigen-bot/pull/1361) | feat: add manual browser login command | 2026-10-17T19:42:14Z |
| 2 | [The-PR-Agent/pr-agent #4189](https://github.com/The-PR-Agent/pr-agent/pull/4189) | perf(similar_issue): batch embeddings before individual retries | 2026-10-20T07:54:28Z |
| 3 | [optiland/optiland #962](https://github.com/optiland/optiland/pull/962) | Align dock and document tabs at the top | 2026-10-20T15:06:20Z |
| 4 | [home-assistant/core #187420](https://github.com/home-assistant/core/pull/187420) | Follow UniFi site ID change in Network 11 | 2026-10-20T16:16:49Z |
| 5 | [caronc/apprise #1783](https://github.com/caronc/apprise/pull/1783) | tags= and tag= on urls not supported | 2026-10-11T21:14:36Z |
| 6 | [mlflow/mlflow #26542](https://github.com/mlflow/mlflow/pull/26542) | Load latest Databricks scorers from the scheduled-scorers REST config so feedback records the scorer version | 2026-10-12T02:40:25Z |
| 7 | [macs3-project/MACS #784](https://github.com/macs3-project/MACS/pull/784) | Reject truncated BAM alignment records | 2026-10-16T07:17:57Z |
| 8 | [tornadoweb/tornado #3787](https://github.com/tornadoweb/tornado/pull/3787) | web: Bound the static version cache, update docs | 2026-10-10T21:27:46Z |
| 9 | [agentscope-ai/ReMe #627](https://github.com/agentscope-ai/ReMe/pull/627) | refactor(stat): consolidate answer tests and shorten docs | 2026-10-15T13:04:27Z |
| 10 | [The-PR-Agent/pr-agent #4183](https://github.com/The-PR-Agent/pr-agent/pull/4183) | perf(gitlab): skip project lookup when fetching a merge request | 2026-10-19T21:29:08Z |
| 11 | [googlefonts/glyphsLib #1208](https://github.com/googlefonts/glyphsLib/pull/1208) | split comma-separated meta Table dlng/slng data | 2026-10-13T14:24:37Z |
| 12 | [dapr/python-sdk #1192](https://github.com/dapr/python-sdk/pull/1192) | Fix convert_to_dapr_duration double-counting sub-second time | 2026-10-12T21:25:52Z |
| 13 | [home-assistant/core #187588](https://github.com/home-assistant/core/pull/187588) | Add pylint check that __init__ is the first method of a class | 2026-10-20T17:50:34Z |
| 14 | [home-assistant/core #187475](https://github.com/home-assistant/core/pull/187475) | Handle meter unit changes in energy cost sensor | 2026-10-20T17:33:15Z |
| 15 | [optuna/optuna #6873](https://github.com/optuna/optuna/pull/6873) | Avoid All-NaN RuntimeWarning in percentile pruner best-value lookup | 2026-10-13T07:44:59Z |
| 16 | [frappe/erpnext #60004](https://github.com/frappe/erpnext/pull/60004) | fix(balance-sheet): show profit or loss of unclosed earlier years | 2026-10-14T16:03:53Z |
| 17 | [The-PR-Agent/pr-agent #4181](https://github.com/The-PR-Agent/pr-agent/pull/4181) | perf(github-action): skip unused provider initialization | 2026-10-19T21:31:18Z |
| 18 | [oceanbase/powercontext #1908](https://github.com/oceanbase/powercontext/pull/1908) | fix(dify): decouple generated contract from whole OpenAPI hash | 2026-10-09T11:23:13Z |
| 19 | [optiland/optiland #963](https://github.com/optiland/optiland/pull/963) | Remove the duplicate separator beside navigation | 2026-10-20T15:06:34Z |
| 20 | [macs3-project/MACS #780](https://github.com/macs3-project/MACS/pull/780) | Join started workers on startup failure | 2026-10-15T04:26:51Z |
| 21 | [doobidoo/mcp-memory-service #1531](https://github.com/doobidoo/mcp-memory-service/pull/1531) | fix(maintenance): regenerate_embeddings writes vectors into their store partition | 2026-10-14T18:30:53Z |
| 22 | [vllm-project/vllm #59627](https://github.com/vllm-project/vllm/pull/59627) | [Bugfix][Structured Output] Feed the token that implicitly ends reasoning to the grammar | 2026-10-08T19:38:34Z |
| 23 | [basetenlabs/truss #2682](https://github.com/basetenlabs/truss/pull/2682) | fix: return 503 for model not ready on draft/watch deployments | 2026-10-20T17:09:57Z |
| 24 | [vllm-project/vllm #60468](https://github.com/vllm-project/vllm/pull/60468) | [Perf] Warm up DeepGEMM MegaMoE kernels before serving | 2026-10-13T12:17:49Z |
| 25 | [bopen/elevation #89](https://github.com/bopen/elevation/pull/89) | Cache missing tiles | 2026-10-09T17:02:22Z |
| 26 | [vllm-project/vllm #58715](https://github.com/vllm-project/vllm/pull/58715) | [Metrics] Count finished requests by watermark status | 2026-10-12T17:21:23Z |
| 27 | [frappe/erpnext #61257](https://github.com/frappe/erpnext/pull/61257) | fix(accounts): validate payment mode accounts and enabled status | 2026-10-18T13:06:59Z |
| 28 | [oyvindwe/connectlife-ha #742](https://github.com/oyvindwe/connectlife-ha/pull/742) | Start WM26 G400 with program options, also from standby | 2026-10-17T07:47:18Z |
| 29 | [pyrevitlabs/pyRevit #3743](https://github.com/pyrevitlabs/pyRevit/pull/3743) | Keep modeless output and logging in the originating command window | 2026-10-10T08:20:04Z |
| 30 | [doobidoo/mcp-memory-service #1603](https://github.com/doobidoo/mcp-memory-service/pull/1603) | fix(mcp): propagate tool exceptions so failures reach the client as isError (#1601) | 2026-10-19T20:21:20Z |
