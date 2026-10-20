# Operations: the PR check and the daily run (technical)

Plain-language version: the [README](../README.md). This page is the detail behind it.

## Entry points

| Command | Runs | Output |
|---|---|---|
| `make check PR=<url>` | `ops/daily_run.py --pr <url>` | `ops/runs/<date>-check-<HHMM>/`, `reports/daily/<date>-check-<HHMM>/` |
| `make daily` | `ops/daily_run.py` | `ops/runs/<date>/`, `reports/daily/<date>/` |
| `make decide REPORT=<dir> DECISION=<d>` | `python -m reports.pr_report decide` | `<dir>/DECISION.json`, report re-rendered |
| `python -m reports.pr_report <ops run dir> --out <dir>` | re-render reports from an existing run | `<dir>/<pr>/REPORT.*`, `<dir>/SUMMARY.*` |

`make` puts `.venv/bin` first on `PATH`, so the `uv` installed by `make setup` (extra `ops`) is the one the runner uses.

## Start of a run

A daily run, and a one-off `ops/daily_run.py` check, begins by fetching `origin` and fast-forwarding the checkout
to `origin/main`. Benchmark mode does not: it runs the commit the checkout is already on, and it refuses to start
unless that commit is the one named by `--expect-commit` (or `POC_EXPECT_COMMIT`) and the work tree is clean.
It never fetches or checks out another commit.

That commit is the Proof-of-Change code the run actually used. Its full SHA is stored on every record as
`poc_commit` (schema rev 8; optional in the schema so an older record still validates) and printed in the run-log
header next to the words "Proof-of-Change commit". The reviewer report header shows the same SHA when the record has it.

The run stops, before it selects or tests anything, when it cannot do that update:

- the checkout has uncommitted changes;
- local history has diverged from `origin/main`, so a fast-forward is impossible;
- `git fetch origin main` fails.

`check_record` (the record check used when a record is written) fails a `pr_run` record that omits `poc_commit` or
gives a value that is not a 40-character commit id.

## Inputs of a daily run

- **Tracked libraries:** a CSV, one row per library: `library,repo,added_on_ist,added_by,priority,status,why_added,
  test_notes`. Resolution: `--libraries-file`, else `$POC_LIBRARIES_FILE`, else `libraries_file` in `ops/local.json`,
  else the committed seed list `ops/tracked-libraries.csv` (numpy, pandas, scikit-learn).
- **Chosen PRs (optional):** a `<date>.md` file naming specific PRs per library, with install and test commands and
  an expected verdict. Resolution: `--chosen-prs`, else `<chosen_prs_dir>/<date>.md` (`$POC_CHOSEN_PRS_DIR` or
  `ops/local.json`), else `<libraries file folder>/chosen-prs/<date>.md`.
- **Independent verification (optional):** `<verification_dir>/<date>/verification.jsonl` (or, if present, a
  `verification*.jsonl` file of schema-rev-5 `verification` records), scored after all verdicts. For rev-5 records
  only `verification.checker_verdict` is scored; `verdict_under_review` (the checked run's own verdict) never is, and
  records with `check_status` `unverified` are skipped.

`ops/local.json` is git-ignored and holds machine-local paths (keys: `libraries_file`, `chosen_prs_dir`,
`verification_dir`, `golden_status`, `research_dir`; see `poc/local_config.py`). Environment variables override it.
There is no scheduler in this repo; run `make daily` (or `ops/daily_run.py`) from whatever scheduler you use.

## Selecting PRs

- **Chosen-PRs file names PRs for a repo:** exactly those PRs, at the pinned head SHA; selection filters do not apply.
  Expected verdicts are read only after every verdict is final (`read_expectations`), so they cannot steer the run;
  `REPORT.md` then scores expected vs actual (match / miss / false alarm).
- **Otherwise:** open PRs updated since the last run (`ops/seen_prs.json`), not drafts, upstream CI not failing,
  touching Python or compiled code inside the package; pure-Python first; at most `--max-per-library` (3).
- **`--pr <url>`:** exactly that PR (repeatable), no library list, no chosen-PRs file, and `seen_prs.json` cut-offs are not moved,
  so a manual check never changes what the next daily run selects.

## How a PR is tested (routes)

| Route | When | main side | PR side |
|---|---|---|---|
| `nightly+patch` | numpy / pandas / scikit-learn, PR touches only `.py` | latest scientific-python nightly wheel | copy of the main venv with the PR diff applied to the installed package |
| `source-build` | same libraries, PR touches compiled code | nightly wheel | PR head built from source (`--build-timeout`, 1800 s) |
| `source-pair` | any other library | base-branch tip (or merge-base if the PR conflicts) built from git | GitHub's test merge commit (or the PR head) |

Tests: test files mapped from the touched modules (or the chosen-PRs file's subset), **3 alternating runs per side**
(main 1, PR 1, main 2, ...), `OMP/OPENBLAS/MKL/NUMEXPR_NUM_THREADS=1`, pytest `-q -rfE --timeout=120` with JUnit XML,
`--run-timeout` 900 s per run, `-n 4` workers. PR code never sees our environment (see "Environment of untrusted
code" below). The comparison is plain code: `poc/diff.py confirm()` per test over the 3 runs, then
`poc/verdict.py pr_verdict()`.

Both sides get the library's test extras plus `optional_test_deps` (per library in `LIBS`), so tests don't skip
for missing optional modules. The nightly wheel is pinned (exact file, sha256, build date and commit are recorded);
source-pair records the GitHub test merge commit. Thread env: `OMP`, `OPENBLAS`, `MKL`, `NUMEXPR`, `VECLIB_MAXIMUM`,
`BLIS` thread counts all 1.

Comparison: rename-aware. An id that disappears is only `removed_tests` if no new id with the same base test name
appeared; otherwise it is listed under `reparametrized` and the new ids are judged by their own outcomes. Failures
identical on both sides are `preexisting_failures`. Unexplained pytest exit codes give `could_not_verify`.

Test modules that fail to load (collection errors: JUnit testcases with an empty classname) are tracked as modules,
never as tests: their ids are made side-independent on every route (the environment / `site-packages.` prefix is
dropped), and they are listed as `load_failed_both`, `load_failed_pr` (with the number of main-side tests that no
longer run) or `load_failed_main`. They never count as "unchanged", removed or new. `executed` records the fewest tests
that actually ran (passed, failed or errored; not skipped, not load failures) in any run of each side.

Verdict, in order:

1. `could_not_verify` if setup/build/patch failed, a run timed out or a side produced no results;
2. `needs_attention` for regressions or new failing tests (nothing below can hide them);
3. `could_not_verify` if no test actually ran on a side (every test skipped, or every module failed to load);
4. `could_not_verify` if a test module loads on one side only ("test module X fails to load on the PR side (N
   test(s) no longer run)");
5. `could_not_verify` if a test module of the changed code (`test_<stem>.py` of a changed source file, or a changed
   test file; every module when the changed files are unknown) fails to load on both sides, even if unrelated tests
   pass;
6. `could_not_verify` if an exit code is unexplained, or new/changed tests were skipped or failed only because
   an optional dependency is missing (a new test whose failure is `ModuleNotFoundError: No module named 'X'`,
   or another missing-dependency message the comparison already recognises, is blocked, not a pull-request break);
7. `could_not_verify` if the only remaining difference is flaky tests. A test that passes and fails across the 3
   runs of one side (main or the pull request) is listed in the record and the report, and the reason names it.
   It is not a regression and does not, on its own, produce `needs_attention`. A real regression or a new failing
   test still produces `needs_attention` when another test is flaky;
8. otherwise `needs_attention` for tests missing on the PR side or other outcome changes, `verified` if nothing differs.

Then the coverage gate. The reason says how many tests ran on each side, how many were unchanged (and how many of
those were skipped on both sides), flaky tests, and every module that failed to load.

## Coverage gate (`poc/coverage_gate.py`)

Every gated record says where its coverage numbers come from (`coverage_gate.measurement`): `measured` (a real
coverage.py run of the PR side), `not measured: predates gate` (the record is older than the coverage gate; there is
no coverage run at all, so nothing is a measurement), `not measured` (the run was skipped or failed; see
`coverage.why`) or `not needed` (no changed Python lines). The reviewer report states this first, in bold.

"Verified" must mean the changed code was exercised. After the 3 timed runs, `coverage_run()` installs `coverage` and
`pytest-cov` into the PR venv and runs the PR side's test subset once more under `--cov=<dirs of the changed
files>` (untimed, so the 3 timed runs stay clean; logs `coverage-pytest.log`, data `coverage-pr.json`). Changed lines
are computed by `difflib` between the main-side file and the PR-side file that was actually tested (exact for every
route, including a diff applied with offsets); executable lines are coverage.py's executed + missing lines. Only
non-test Python files that ship with the library count (not `tests/`, `test_*.py`, `conftest.py`, docs, benchmarks,
`setup.py`).

| Case | Effect |
|---|---|
| Python changes, 0% of changed executable lines ran | `verified` -> `could_not_verify`, reason "not fully verified: changed code never ran: 0 of N ..." |
| Python changes, under 50% | verdict kept; `coverage_gate.confidence = lower` (report: WARN, Medium confidence) |
| Python changes, coverage not measured (old record, `--no-coverage`, or the coverage run failed) | verdict kept; confidence lower; note says why |
| Compiled sources (`.c .h .cpp .pyx .pxd ...`, not build config) and no changed test file whose name contains the module stem | `verified` -> `could_not_verify`, "not fully verified: compiled code changed (...)" |
| No executable change (docs/tests/config) | stays `verified`, note "no executable code changed" |
| `needs_attention` / `could_not_verify` | never changed |

Record fields (schema rev 4, all optional): `changed_lines_total`, `changed_lines_covered` (null = not measured),
`coverage` (raw run), `coverage_gate` {kind, changed, confidence, note}, `verdict_before_coverage_gate`,
`reason_before_coverage_gate`. The gate is idempotent. Records are gated before they are written, so
`records.jsonl`, each `record.json` and `REPORT.md` state the same final verdict; `reports/pr_report.py` re-applies
the gate when rendering.

**Limitations.** coverage.py cannot measure compiled code, so the compiled rule is a heuristic: a changed test file
named after the module (`item_selection.c` -> `test_item_selection.py`) counts as "a test that calls into the changed
module"; it does not prove the test reaches the changed C lines, and a test with an unrelated name is not recognised.
A PR mixing Python and compiled changes gets both rules. Lines run only by import (module-level code) count as
covered. The coverage run adds roughly one more test run per PR (about 15-60 s on day-1 PRs).

## Operator console (browse + start checks)

React UI (`console/web`, NVIDIA green/dark) talks to a stdlib JSON API (`poc/console_api.py`). Live jobs expose stage + agent swarm progress via `POC_PROGRESS_PATH` JSONL (`poc/run_progress.py`).

| Endpoint | Purpose |
|---|---|
| `GET /api/health` | liveness |
| `GET /api/runs` | recent `ops/runs/**/record.json` summaries |
| `GET /api/runs/<id>` | full record + folder |
| `POST /api/checks` | `{ "pr_url", "model_provider?" }` → background `daily_run --pr` |
| `GET /api/jobs/<id>` | status, `stages[]`, `current_stage` / `current_agent`, `swarm` map, log tail |

```bash
make console-api    # :8787
make console-web    # :5173 (Vite proxies /api → :8787)
# or: make console-build && make console-api  → open :8787
```

Jobs run in a daemon thread. Poll `/api/jobs/<id>` while `daily_run` writes progress events (install → pytest → Ultra/Lightning/Super → done).

### Free public URL (recommended — no Nebius Compute bill)

Builder **Token Factory** credits pay for Nemotron calls, not for hosting. Skip Nebius Serverless AI Endpoint if you want $0 hosting.

**Option A — Render (free tier, easiest)**

1. Push this repo to GitHub.
2. [Render](https://dashboard.render.com) → **New** → **Blueprint** → select the repo (`render.yaml`).
3. Set secrets in the dashboard:
   - **`NEBIUS_API_KEY`** (Token Factory / models)
   - **`GITHUB_TOKEN`** — read-only PAT for public repos. `GITHUB_POC_TOKEN` is used when `GITHUB_TOKEN` is unset, then `GH_TOKEN`. The token is for API reads on the host only. A 403 or 429 with `X-RateLimit-Remaining: 0` waits until `X-RateLimit-Reset` (capped, default 15 minutes) and retries once instead of skipping that library.
   - Optional: `NEBIUS_PROJECT_ID`, `POC_DEMO_REPOS`
4. Deploy → open `https://<service>.onrender.com` (same console UI). Free instances sleep when idle.

**Option B — local + share link (truly free)**

```bash
make console-build && make console-api   # :8787
# other terminal: cloudflared tunnel --url http://127.0.0.1:8787
# or: npx localtunnel --port 8787
```

Do **not** rewrite to Streamlit — you’d lose the swarm theater and still need a Python backend for `daily_run`.

### Nebius host (paid Compute — only if you have AI Cloud credits)

Token Factory (`NEBIUS_API_KEY`) is for models only. A Nebius **navigable website** needs a **Serverless AI Endpoint** (Compute billing) ([docs](https://docs.nebius.com/serverless/endpoints/manage)).

1. Prerequisites: Docker, [Nebius CLI](https://docs.nebius.com/cli/) logged in, `jq`, a VPC **subnet id**, an image host you can push to.
2. Build and push the image:

```bash
export IMAGE=docker.io/<you>/poc-console:latest   # or any image host Nebius can pull
make docker-console IMAGE="$IMAGE"
```

3. Create the Endpoint (`--auth none` so a browser can open it without a Bearer header):

```bash
export SUBNET_ID=…                    # Nebius VPC subnet
export NEBIUS_API_KEY=…               # Token Factory — swarm + probes inside the container
# optional: NEBIUS_PROJECT_ID, POC_DEMO_REPOS
make nebius-console IMAGE="$IMAGE" SUBNET_ID="$SUBNET_ID"
```

4. The script prints a managed **`https://…`** URL (also under Serverless AI → Endpoints → Public endpoints). Open it — same SPA as local: paste a PR, watch Ultra / Lightning / Super.
5. Health: `curl -sS "$URL/api/health"`.

Local-only (no Nebius URL): `make console-host` on `0.0.0.0:8787`.

Progress files live under `ops/runs/_jobs/<job_id>.jsonl` inside the container (ephemeral unless you mount a volume).

## GitHub App (demo/mirror repos only)

Optional path so Proof-of-Change can answer on GitHub itself — **only** for repos listed in `POC_DEMO_REPOS`
(G-ext). Upstream libraries stay read-only.

| Env | Purpose |
|---|---|
| `POC_DEMO_REPOS` | Comma-separated `owner/repo` allowlist (required to post) |
| `GITHUB_WEBHOOK_SECRET` | HMAC for `POST /webhook` |
| `GITHUB_APP_INSTALLATION_TOKEN` | Pre-minted installation token (simplest for demos) |
| `GITHUB_APP_ID`, `GITHUB_APP_PRIVATE_KEY`, `GITHUB_APP_INSTALLATION_ID` | Mint a token via JWT (`pip install -e '.[github]'`) |
| `POC_REPORT_BASE_URL` | Optional public base for behavior-map links in comments/checks |

```bash
export POC_DEMO_REPOS="your-org/your-demo-repo"
export GITHUB_WEBHOOK_SECRET="…"
export GITHUB_APP_INSTALLATION_TOKEN="…"
.venv/bin/python -m poc.github_app --host 0.0.0.0 --port 8080
```

- `GET /health` — liveness JSON.
- `POST /webhook` — verifies signature, `handle_event`, then `apply` (runs `daily_run --pr`, writes
  `reports/hosted/<id>.html`, posts check run + comment when a token is present).
- Check-run conclusion is never `failure`. Without a token, `apply(..., dry_run=True)` writes HTML only.
- MVP runs the PR check inline after acknowledging the webhook (long runs may hit GitHub's delivery timeout; queue later if needed).

## Sandbox backends (`--sandbox-backend`)

| Backend | When | What runs remotely |
|---|---|---|
| `local` (default) | always available | nothing — bubblewrap on the operator machine (`guardrails/sandbox.py`) |
| `contree` | `NEBIUS_API_KEY` + `NEBIUS_PROJECT_ID` set, and `pip install -e '.[contree]'` (`contree-sdk==0.3.6`) | source-pair **probe** and **pytest** dual-runs on Nebius Token Factory Sandboxes |

Contree flow (`poc/contree_sandboxes.py`): OCI `python:3.12-slim-bookworm` → main checkpoint at the base SHA (`disposable=False`) → fork PR checkpoint at the head SHA → disposable dual-runs (semaphore ≤40 via `CONTREE_MAX_OPS`). Record fields: `machine`, `sandbox_backend`, `sandbox_backend_note`, `contree.{main_uuid,pr_uuid}`. Missing credentials or SDK → **explicit** fallback to local (never silent). `POC_REQUIRE_CONTREE=1` refuses instead. Keys stay in the orchestrator process; they are not passed into Contree shell env. Optional live smoke: `POC_CONTREE_SMOKE=1` python -c 'from poc.contree_sandboxes import smoke; print(smoke())'. Nightly/source-build routes stay on local bubblewrap.

## Sandbox (`guardrails/sandbox.py`)

Untrusted code never runs directly on the machine (unless Contree owns the dual-run — see above). Every install and build (PR build code such as `setup.py` or meson
runs here), pytest run, coverage run, probe, `uv pip freeze`, `patch` and every start of a venv Python runs inside a
**bubblewrap** sandbox (`bwrap`, unprivileged user namespaces, no root daemon). Each side (main, PR) has its own:

| Inside the sandbox | Source |
|---|---|
| `/usr`, `/bin` `/lib` `/lib64` `/sbin` (links or read-only binds) | host, read-only |
| `/etc`: `ld.so.cache`, `ld.so.conf(.d)`, `alternatives`, `ssl`, `ca-certificates`, `localtime`, `timezone`, `os-release`, `protocols`, `services`, `mime.types`; a one-user `passwd`/`group` | host files, read-only; `passwd`/`group` generated |
| `/etc/resolv.conf`, `hosts`, `nsswitch.conf`, `gai.conf`, `host.conf` | only in the install/build phase |
| `/opt/uv-python` | the uv-managed Pythons, read-only (venvs are created inside, so they point here) |
| `/opt/uv-cache` (install phase only) | the shared uv cache as a read-only lower layer plus a private tmpfs layer that is thrown away on exit (`--overlay-src`/`--tmp-overlay`): builds can use the cache but never write to it. bwrap older than 0.10 has no overlays; then each side gets its own empty cache in its temporary home |
| the side's own dirs, at their real paths | read-write: `work/venv-<side>`, `work/home-<side>` (HOME; TMPDIR is `HOME/.tmp`), `work/out-<side>`, `work/cwd-<side>`, the side's checkout (`work/side-<side>`, or `work/src` for the PR side of a source build) |
| `work/src/.git` (worktree checkouts) | read-only, so `git describe` works for version tools |
| a wheel, a probe file, a constraints file | read-only, only the one file a step needs |
| `/tmp`, `/proc`, `/dev` | fresh tmpfs, new procfs, minimal devices |

Options: `--unshare-all` (user, mount, PID, IPC, UTS, cgroup and network namespaces), `--die-with-parent`,
`--new-session`, `--cap-drop ALL`, and the allowlisted environment below. Nothing else exists inside: no `/home`, no
other worktrees or agent data, no `/sys`, not the other side's venv. **Network:** only the install/build phase
shares the host network (`--share-net`); the test, coverage, probe, freeze and version-check phases have none (only
their own loopback interface, so not even services on the host's 127.0.0.1). JUnit and coverage files are written
inside the side's `out-` dir and moved to the run folder afterwards. git on our own fresh clones runs outside.

**Fail closed:** at the start of every PR the sandbox is test-started; if it cannot start, the PR is not run and gets
**could_not_verify** with the reason `sandbox unavailable: ...`. `--unsafe-no-sandbox` skips the sandbox; the daily
run and `make check` never pass it. `run_meta.json` records the sandbox used (`"sandbox"`). The tests in
`tests/test_sandbox.py` start real sandboxes with dummy secret files planted outside and fake credentials in the
environment, and check every phase (a hostile build backend, pytest, a probe) and the shared cache.

To mount a dir at its real path, bwrap creates its ancestors as empty directories on the sandbox's own tmpfs, so a
parent of the work dir (for example a parent it shares with the repo) exists inside, but only as that skeleton. The
containment check reads the mount table inside the sandbox and walks everything outside the mounts: every mount is a
system mount or lies under the side's own dirs, no file exists outside a mount, and each skeleton directory contains
only the path components that lead to mounts. `tests/test_sandbox.py` also runs itself with `--basetemp` next to the
repo, and has a negative control that exposes the repo's parent and expects the check to fail.

> **TODO (open issue): sandbox the release-pair runner.** `harness/run.py` (release pairs) gets the allowlisted
> environment but does **not** run inside the sandbox yet: its installs, tests and coverage run directly on the
> machine with the runner's filesystem access and network. That is acceptable only because it installs **published
> releases** from the package index. Before it is pointed at anything else (a branch, a PR, a git URL, a local
> checkout, an unpublished or nightly build), route its subprocesses through `guardrails/sandbox.py` the same way
> `ops/daily_run.py` does (per-side read-write dirs, read-only shared cache, network only for installs, fail closed),
> and extend `tests/test_sandbox.py` to cover it.

## Environment of untrusted code (`guardrails/isolation.py`)

Every subprocess that may run code from a PR or a package gets an **allowlisted** environment built by
`untrusted_env()`, never a filtered copy of ours. That covers installs and builds of either side, pytest, the coverage
run, probes, `uv pip freeze`, `patch` and every start of a venv Python (installed `.pth` files run on startup). It
applies to `make check` and the daily run (`ops/daily_run.py`, `base_env()`), and to the release-pair runner
started by `harness/run.py`.

| Variable | Value |
|---|---|
| `PATH`, `LANG`, `LC_ALL`, `TERM`, `TMPDIR`, `SOURCE_DATE_EPOCH`, `SSL_CERT_FILE` | passed through, only if set |
| `HOME` | a per-environment temporary home (`work/home-main`, `work/home-pr`, `work/home-git`), never the real one |
| `OMP_NUM_THREADS`, `OPENBLAS_NUM_THREADS`, `MKL_NUM_THREADS`, `NUMEXPR_NUM_THREADS`, `VECLIB_MAXIMUM_THREADS`, `BLIS_NUM_THREADS` | `1` |
| `PYTHONHASHSEED` / `PYTHONDONTWRITEBYTECODE` / `MPLBACKEND` | `0` / `1` / `Agg` |
| installs only: `UV_CACHE_DIR`, `UV_PYTHON_INSTALL_DIR` | the real uv cache and managed-Python dirs (so a temporary HOME does not re-download everything) |
| installs only: `UV_LINK_MODE` / `UV_NO_CONFIG` | `copy` (installed files never share inodes with the cache) / `1` (no uv config files) |
| installs only, per call: `SETUPTOOLS_SCM_PRETEND_VERSION` | `9999.0.0` for checkouts without tags |

Everything else is dropped: tokens, API keys, database URLs, proxies, `PIP_*`/`UV_INDEX_*`, `PYTHONPATH`, `CI`,
`DISPLAY`, `XDG_*`. A second, independent check (`SECRET_NAME`: TOKEN, SECRET, PASSWORD, KEY, AUTH, PAT, DSN,
DATABASE_URL, COOKIE, SESSION, ...) fails loudly at import time if a credential-looking name is ever added to the
allowlist, and again on every environment built (also for values that are URLs with a password). `run()` refuses
to start anything without an explicit environment. Proxies are not passed through: on a machine that needs one,
installs fail visibly instead of handing proxy credentials to PR code. The temporary HOME hides files such as
`~/.netrc` and `~/.git-credentials` by default. It is not a filesystem sandbox: code can still read absolute paths
the user can read.

## Probes (`poc/probes.py`, `probes/`)

Tests only show what the test suite checks. A **probe** checks one specific behaviour of a PR directly: a small,
deterministic Python script that runs on both sides (main and PR) in the same isolated environments the tests used,
prints observations as JSON, and plain code compares them. Only fixed probes exist today, one file per PR under
`probes/<owner>/<repo>/<pr>.py` (more than one: `<pr>-<name>.py`). Model-written probes will use the same interface.

Interface. The file starts with a literal `PROBE` dict (read with `ast.literal_eval`, never imported):
`id`, `target` (`owner/repo#pr`), `about`, `timeout_s` (optional, default 120 s), and `claims`: what the PR says,
each `{id, text, source, covers: [glob patterns over observation names], expect: "same" | "differs"}`. Its last
stdout line is `{"observations": {"<name>": <JSON value>, ...}}`. Each side runs 3 times, alternating, with that
side's venv Python, an empty working directory and that side's allowlisted environment (see above; same as the
tests). Each run's observations are saved one per line as `probe-<id>-<side>-<n>.jsonl` (plus a `.log`
with the full output), and every observation in the record cites its line in run 1 of each side.

Labels, per observation:

| Observation | Claim covering it | Label | Verdict effect |
|---|---|---|---|
| same on both sides | expects same | `proven` | none |
| same on both sides | none | `no_difference` | none |
| same on both sides | expects differs | `needs_human` | needs_attention |
| differs | expects differs | `proven` | none |
| differs | expects same | `false_claim` | needs_attention |
| differs | none | `unmentioned` | needs_attention |
| varies between runs of one side | any | `flaky` | needs_attention |
| probe crashed on both sides | - | `not_testable` | none (reported) |

A probe that crashes on one side only shows up as the `probe.error` observation differing (`unmentioned`).

Verdict rule. The tests decide first (comparison, then the rules above); then any probe observation needing
attention makes the verdict needs_attention, also over could_not_verify, because a difference was actually seen.
Green probes never upgrade a verdict. The coverage gate runs after this and never lowers needs_attention. A PR
without a probe file gets exactly the tests' verdict and reason; its record says `"probes": {"status": "none"}`.
The record (schema rev 6, additive) keeps every run's observations, so `--rejudge` recomputes the labels without
environments. The reviewer report has a **Probes** section (each observation with both values and its citations)
and adds the claims as rows `P-C1`, ... in the claims table; observations no claim covers are listed as
"Change not in the PR description". The golden known-answer case `golden-pr-mlxtend-1229-probe`
(`evals/fixtures/golden_pr_v1.jsonl`) is part of `--require-golden`: tests alone pass on that PR (verified), the
probe finds two unclaimed behaviour changes, so the expected verdict is needs_attention.

## Baselines, model-written probes and the freeze rule

**`--baseline`** says what may decide the verdict; each record stores it (`baseline`, schema rev 7; records without
it are `full`), and the reviewer report prints it under the title.

| Baseline | Decides the verdict | Not used |
|---|---|---|
| `tests` | the test comparison only | probes, coverage gate, claim flagging |
| `tests+diff` | tests + **differential probes** | claim probes, coverage gate, claim flagging |
| `tests+probes` | tests + **claim probes** (fixed and/or model-written) | differential probes, coverage gate, claim flagging |
| `full` (default) | tests + claim probes + coverage gate + claim flagging | differential probes run and are shown, but do not decide |

**Differential probes** (`poc/diff_probes.py`) are a deliberately simple, model-free baseline. From the base-side code
and the diff's old-side line numbers they pick the module-level public functions the PR touches, call each with the
same simple inputs on both sides (`1, 0, -1, 2.5, "abc", [1, 2, 3], None` for every required argument; `random`
and NumPy seeded) and compare canonical summaries of the results (an exception becomes `{"raises": "<type>"}`). They
have no claims, so under `tests+diff` any difference needs attention.

**Model-written probes** (`--model-provider`, `poc/model_provider.py`, `poc/model_probes.py`):

| Provider | What it does |
|---|---|
| `none` (default) | fixed probes only; the record and report say so |
| `nebius` | Nebius Token Factory (`https://api.tokenfactory.nebius.com/v1`, OpenAI-compatible, structured JSON output). Model ids: `--claims-model` and `--probe-model`, default `nvidia/nemotron-3-super-120b-a12b` (REQUIREMENTS section 4a). The key is read from `NEBIUS_API_KEY` by the orchestrator only. If that variable is missing or empty, the run stops before it starts and says how to set it. It never prints the key. `--model-provider none` is how you run with the AI off |
| `recorded` | answers from `evals/fixtures/model_responses/<owner>/<repo>/<pr>.json`. These are **test fixtures**: every probe written from them is labelled `model (recorded fixture, not blind)` |

The model first extracts claims, and each claim must quote the PR text exactly. It then writes probe code, which is
validated: at most 20,000 characters, it must parse, it may not define its own `PROBE`, and its claim ids must be
known. Model code is untrusted. It runs only in the side's sandbox, without network, with a 60 s timeout. Its output
is capped at 256 kB (every probe's files are also capped by a file-size limit), with at most 200 observations.

**Freeze rule** (`poc/freeze.py`, hard):

1. Probes are generated only from the PR title and description and from **base-side** code. Any input path on the
   PR side is rejected.
2. Before the first PR-side execution (its install, build or patch), every probe is **frozen**. Its content sha256,
   generator, time and the sha256 of its generation inputs go into `probe_plan` and the probe's `freeze`.
3. The runner re-checks the freeze before every PR-side run. A probe whose content changed, or which was frozen or
   written after PR-side execution started, is refused (`probes.refused`) and not run.

**Blind or not.** Only a live `nebius` probe that passed the freeze rule is blind. The following are never blind:
fixed probes (the mlxtend #1229 probe has `"provenance": "post-hoc"`: it was written after the results were known),
recorded fixtures and differential probes. They are kept as known-answer regression cases.
`evals/pr_metrics.score_records` scores any verdict they could decide in a separate NOT BLIND column, and
`blind_score` refuses such records. `python -m evals.ablation --records-root DIR` (or `--run --out-dir DIR`) writes
`ablation.md` and `ablation.json`: for each baseline, the catch rate, false alarms and could-not-verify rate (blind),
plus a NOT BLIND column.

## Behaviour-preservation claims (`poc/behaviour_claims.py`)

Tests check what a PR changes, rarely that everything else stayed the same. When the PR title or description claims
that results stay the same and no probe checks it, the PR cannot be **verified**: the verdict becomes
**could_not_verify** with the reason `unverified behaviour claim: "<quote>"; needs a probe (tests: ...)`. When a
probe for the PR has a claim that expects `same`, the probe decides (it can confirm the claim, or contradict it, which
gives needs_attention). The rule never upgrades a verdict and never hides needs_attention.

The regex list (`PATTERNS`, case-insensitive) is deliberately small: results/output/behaviour/values/predictions/
importances/scores + "unchanged / identical / preserved", "do(es) not change" / "don't change", "the same output /
results / behaviour", "for a given / the same / a fixed seed", "backward(s) compatible / compatibility", "no
behaviour(al) / functional / user-facing / API change", "no change in/to the results", plus "passed through",
"left unchanged", "returned unchanged", "exactly as before" and "untouched". The same list is applied to added
changelog lines and added docstring lines in the diff, not only the title and description. A match right after a negation
("not backwards compatible", "breaks backward compatibility", "no longer") is ignored, and so are Markdown headings,
HTML comments, fenced code blocks, unticked checklist items (`- [ ]`, including a wrapped continuation line) and
template boilerplate (stock instruction lines such as "Please make sure ..." or "Thanks for contributing"). A ticked
item (`- [x]`) is the author's own line and can still be a claim. The quotes are stored in the record
(`behaviour_claims`) so a re-judge gives the same answer.

## Files a run writes

```
ops/runs/<folder>/                         (git-ignored)
  REPORT.md            run log for operators: per-PR lines, what went right/wrong, skipped PRs, expected vs actual
  records.jsonl        one record per PR;  selection.json  what was picked and skipped
  run_meta.json        timings, machine, problems (needed by --report-only). Wall time is the sum of each
                       pull request's own time. The first start time is kept across --resume.
  schema_check.log    first line is `N/N valid` (how many records validate)
  invocations/invocation-N/run_meta.json
                       that invocation's own timings; --resume does not overwrite an earlier one
  superseded/attempt-N/ earlier attempts of the same date (records, logs, NOTE.md); the selection stays frozen
  <pkg>-<pr>/          record.json, pr.diff, setup-*.log, build-pr.log / patch.log / git.log, freeze-{main,pr}.txt,
                       pytest-{main,pr}-{1,2,3}.log, junit-{main,pr}-{1,2,3}.xml,
                       coverage-pytest.log, coverage-pr.json (coverage gate)
ops/work/                                  scratch venvs and checkouts, deleted after each PR (git-ignored)
ops/seen_prs.json                          incremental state for the daily selection (git-ignored)
reports/daily/<folder>/                    (git-ignored)
  SUMMARY.html|pdf|md  needs-attention first
  <pkg>-<pr>/REPORT.html|pdf|md, SOURCE.json (where it came from), DECISION.json (after make decide)
```

## The reviewer report for a PR run (`reports/pr_report.py`)

Same section order, renderers and verdict vocabulary as the golden-record reports (`reports/reviewer.py`,
[REPORT_SPEC.md](REPORT_SPEC.md)), adapted to main-vs-PR:

- **Verdict mapping:** `verified` -> VERIFIED / Approve (Approve with notes if a check warned or tests were fixed);
  `needs_attention` -> NEEDS ATTENTION / Reject; `could_not_verify` -> COULD NOT VERIFY / Re-run. **Any failed
  check below also gives COULD NOT VERIFY / Re-run** (the run cannot be trusted).
- **Coverage gate:** a gated `could_not_verify` (reason "not fully verified ...") is COULD NOT VERIFY / **Review by
  hand** (a re-run would not change it), Low confidence. Low coverage or "not measured" is a WARN. The summary lists
  every verdict the gate changed under "Changed by the coverage gate", and earlier attempts under "Re-runs".
- **Record shape:** pr_run records (schema rev 3+) keep the PR in a `pr` object and durations in `duration_s`;
  `normalize()` flattens them (older flat records still render).
- **Confidence:** High when every check passes, Medium with warnings, Low for COULD NOT VERIFY.
- **Claims:** C1 is the PR title (not testable until Nemotron claim extraction exists); C2 is the implicit claim
  "tests that pass on main still pass"; one "unmentioned change" row per kind of difference. Each row cites a log
  line: the pytest `FAILED ...` line for a failing test, otherwise the pytest summary line of the relevant side.
  All citations are re-read from disk and must match (`verify`), otherwise the check fails.
- **Evals and guardrails:** 3 runs per side, single-thread env, machine type recorded, nothing posted upstream,
  citations verified (FAIL -> Re-run); flaky tests, PR moved since tested, `pip check` (WARN -> lower confidence).
- **Known-answer replay (ported from render_report.py):** if the latest replay status file (`$BR_GOLDEN_STATUS`,
  else `golden_status` in `ops/local.json`; JSON with `all_passed`, `date_ist`, `failed`) has
  `all_passed: false`, every report is COULD NOT VERIFY / Re-run with Low confidence. The same applies to the
  golden-record reports (`reports/reviewer.py`), where a record's own failed `golden_check` also forces it. Tests set
  `BR_GOLDEN_STATUS` to empty so they never depend on a machine-local file.
- **PDF:** headless Chrome/Chromium (`$BR_CHROME`, PATH, or `/Applications/Google Chrome.app`). Without it, HTML and
  Markdown are still written and a note is printed.

## Flags (ops/daily_run.py)

`--pr URL` (repeatable), `--libraries-file`, `--chosen-prs`, `--verification`, `--libraries a,b`, `--max-per-library 3`,
`--scan-limit 15`, `--runs 3`, `--workers 4`, `--python 3.12`, `--test-timeout 120`, `--run-timeout 900`,
`--build-timeout 1800`, `--min-free-gb 20`, `--select-only`, `--resume`, `--reselect`, `--rerun-note TEXT`,
`--report-only` (rebuild REPORT.md and the reviewer reports from `records.jsonl`, `run_meta.json` and
`selection.json`; nothing is re-tested. Saved records are first brought up to the current rules: a calendar date in
`run_date` and the gated final verdict. Changed `records.jsonl` / `record.json` files are rewritten and the originals
kept once under `pre-migration/`), `--rejudge` (with `--report-only`: also recompute each verdict from the saved
JUnit files with the current comparison rules; the previous verdict is kept under `rejudged`), `--date` (run folder,
may be nested, e.g. `<date>/<name>`; `run_date` is the folder's calendar date), `--ops-dir`, `--work-dir`, `--report-dir`, `--no-report`,
`--baseline tests|tests+diff|tests+probes|full` (what decides the verdict, default `full`; see "Baselines"),
`--model-provider nebius|recorded|none` (default `nebius`; a missing or empty `NEBIUS_API_KEY` stops the run before it starts, including a benchmark or an eval that uses this default. `--model-provider none` runs with the AI off. The full baseline still refuses to test when no model is available, see docs/decisions/2026-10-14-require-model-for-ai-gate.md), `--claims-model ID`, `--probe-model ID`, `--recorded-dir DIR`,
`--unsafe-no-sandbox` (run PR code without the sandbox; never used by the daily run), `--sandbox-backend local|contree` (default `local`; Contree needs `NEBIUS_API_KEY`, `NEBIUS_PROJECT_ID`, and `.[contree]`), `--no-coverage` (skip the coverage run; the gate then says "not measured"), `--no-probes` (do not run probe files;
the record says `"probes": {"status": "none"}`).

A full daily run takes about 15-20 minutes (day 1: 15 PRs in 16.4 min wall time, before the coverage run existed).
