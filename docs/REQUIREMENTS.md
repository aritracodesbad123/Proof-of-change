# Proof-of-Change: requirements

Status: draft v0.3.1 (2026-10-10 IST), by Nathan (ops/QA/dev). v0.3.1 integrates §4a (NVIDIA and Nebius stack), the
shared v1 observation schema and Jonathan's final golden records (G1–G3). Replaces v0.2 (Blast Radius downstream testing), which is
kept here as one of Proof-of-Change's checks and as its eval source.

**Source of truth:** `nvidia-nebius-hackathon/proof-of-change-spec.md` (Proof-of-Change Product Specification v1.0,
29 Sep 2026, 26-page PDF), cited below as "spec §N". Aritra's summary and Jonathan's eval framing (10 Oct 2026)
were added on top. Items marked **[ASSUMED]** are mine and need confirmation; see §14.

## 1. Goal

Every pull request should come with proof. Proof-of-Change reads what a PR claims, writes small probes for each claim
and for changed public code, runs them on **main** and on **the PR** side by side in forked Nebius Token Factory
Sandboxes, and gives the reviewer a **verdict** and a **behavior map**: what is proven, what is false, and what changed
that nobody mentioned (spec §1). Tagline: "Don't just read the PR. Run it."

Built for the Nebius x NVIDIA Global AI Hackathon, Coding and Agentic Engineering track. **Internal submission target:
Fri 30 Oct 2026, 12:00 noon IST.** The official Devpost deadline is 10:00 am PT = 10:30 pm IST that day (spec facts table, §8.2).

## 2. Scope

In scope (MVP, spec §7.1):
- Python projects that install with pip (pyproject or requirements file). **Python only.**
- Any repo in principle. NumPy, pandas and scikit-learn are **test subjects** that prove it works, not the product.
- Triggers: GitHub App on new or updated PRs, and a `/prove` PR comment (`/prove "claim"` adds a claim).
- Claim extraction with source quotes. Probe generation (claim, no-change and extension-point probes). Build main
  once, fork for the PR, run probes on both sides in parallel in Sandboxes. Normalise, rerun on difference, verdict.
- Output: GitHub check run (never failing), one summary comment, a web report with the behavior map, finding detail
  and raw outputs.
- Demos: the real psf/requests PR #6655 replay (main), and the constructed `poc-demo-bookstore` (FastAPI + SQLite)
  with 4 planted PRs, **labelled as example data** everywhere it appears.

Stretch (spec §7.2): MCP server (`prove_change`, `run_probe`) for Cursor/Claude, run-timeline screen, "copy as pytest",
checkpoint cache per base SHA, Serverless AI eval job, Tavily doc lookup (Tavily bonus).

Out of scope (spec §7.3): non-Python languages; services needing DBs other than SQLite, queues or several services;
private repos and secrets; GitLab/Bitbucket; blocking merges by default; **posting to any real upstream repository**
(all demos run on our own mirror repos).

## 3. Roles

| Who | Role | Owns |
|---|---|---|
| Aritra Chakraborty | Product owner, approver, demo lead | Spec, decisions (§14), demo repos and planted PRs, README, video, Devpost text. Approves or rejects each run from its approver report; merges to `main`. |
| Jonathan | Eval-set and protocol owner | The **labelled PR set** (§9), the downstream-test runner (`harness/br_run.py`) and protocol, golden data. |
| Nathan | Ops, QA, dev; eval and guardrail enforcer | CI/CD, eval harness and metrics, guardrails, approver reports, the daily routine (§10). Enforces evals and guardrails on every run, Jonathan's included. |

Spec §8.1 plans roles for 2–4 people (agent engineer, sandbox/platform engineer, frontend). Who builds the agent loop,
the Sandbox runner, the GitHub App and the web report is **open** (§14 Q1).

## 4. Pipeline: PR in, verdict and behavior map out (spec §6.1–6.2)

| # | Step | Powered by | Deterministic? |
|---|---|---|---|
| 0 | Trigger: webhook, `/prove` or MCP call creates a run with repo, base SHA, head SHA and PR text | Service on a Nebius Serverless AI endpoint (fallback host: §14) | yes |
| 1 | Environment setup script (pyproject, requirements, CI config) | Nemotron 3.5 Lightning (fallback Nemotron 3 Nano 30B) | model, hand-checked for demos |
| 2 | Build main at base SHA, keep the image as the "main" checkpoint (`disposable=False`) | Sandboxes (Contree SDK) | yes |
| 3 | Fork the main checkpoint, apply the PR, save the "PR" checkpoint | Sandboxes branching | yes |
| 4 | Claim extraction: atomic claims, each with a `source_quote` copied from the PR text; untestable claims marked grey; `unclaimed_surfaces` listed | Nemotron 3 Super 120B, JSON-schema output | model |
| 5 | Probe generation: claim, no-change, extension-point, edge-input, contract probes | Nemotron 3 Super; the extension-point rule is deterministic | model + rule |
| 6 | Dual run: every probe on both checkpoints in parallel with a timeout; 3 reruns per side on any difference | Sandboxes, semaphore at 40 (< 50-operation beta limit) | yes |
| 7 | Normalise and diff field by field | **Code** (`poc/diff.py`); Lightning may only *propose* new noise rules | yes |
| 8 | Label each finding (proven / false / unmentioned / needs human) with a one-sentence reason | Nemotron 3 Ultra 550B | model |
| 9 | PR verdict | **Code** (`poc/verdict.py`) | yes |
| 10 | Report: behavior map, check run, comment, web report | Code; Nemotron 3 Super writes the summary, quoting real outputs | mostly |

Model IDs are confirmed at build time with `GET /v1/models` (spec §6.2): `nvidia/nemotron-3-super-120b-a12b`,
`nvidia/Nemotron-3-Ultra-550b-a55b`, `nvidia/Nemotron-3_5-Lightning`, `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B`.

**Downstream tests as a check (from v0.2).** For library PRs (NumPy, pandas, scikit-learn), one extra probe family
runs a dependent project's test suite against main and against the PR, with the v0.2 rules: two envs that differ only
in the upstream; **3 alternating runs per side**; **single thread** (`OMP/OPENBLAS/MKL/NUMEXPR_NUM_THREADS=1`);
**`machine_type` and `thread_env` in every record**; per-test and per-invocation timeouts; strict schema validation.
**Installed (wheel) packages are tested with pytest `--import-mode=prepend`** (`--pyargs`); `importlib` only for tests
run from a git checkout. A collection error counts **once per test module as `import_failure`**, never as a real
break; the tests that vanish with it are `lost_tests`.

> **Root cause, G1 mismatch (found by Jonathan, 10 Oct 2026, `research/LOG.md` "import-mode root cause").** The dev
> runner reported 280 failed / 250 passed / 13 errors on scikit-learn 1.6.0rc1 instead of the raw `525 errors`. It
> was not the worker count or `python -P`: under `--import-mode=importlib` a failed `import imblearn` leaves the
> package **half-loaded** in `sys.modules`, so later modules import the broken half and produce fake failures and
> fake passes. With `prepend` every run reproduces the raw result (old 2238 passed; new 0 passed, 525 errors).
Its result becomes a finding like any other probe. **[ASSUMED]** It runs in the same Sandboxes checkpoints in
production, and on the box or CI for the eval set until the Sandbox runner exists.

## 4a. NVIDIA and Nebius stack

Source: Jonathan's `blast-radius-research/docs/NVIDIA_NEBIUS_STACK.md`, based on the [hackathon rules](https://nebiusglobalaihackathon.devpost.com/rules) and spec §6. The README must name every NVIDIA model and Nebius service listed under Required.

### Hard rule from the hackathon
The project must run on Nebius Token Factory or Nebius AI Cloud **and** use at least one NVIDIA open model (Nemotron, GR00T, Cosmos or Sonic). The README must name every NVIDIA model and Nebius service used. Proof-of-Change meets this through the Nemotron models below, served on Token Factory.

### Required (MVP)

| Tool | Owner | What it does in Proof-of-Change | Pipeline step |
|---|---|---|---|
| **NVIDIA Nemotron 3 Super 120B** (`nvidia/nemotron-3-super-120b-a12b`) | NVIDIA, served on Token Factory | Reads the PR and extracts testable claims (JSON schema output); writes the probe scripts; writes the plain-language report summary, quoting real outputs only | 4, 5, 9 |
| **NVIDIA Nemotron 3 Ultra 550B** (`nvidia/Nemotron-3-Ultra-550b-a55b`) | NVIDIA, served on Token Factory | Judges each main-vs-PR difference: proven, false, unmentioned, or needs a human, with a one-sentence reason | 8 |
| **NVIDIA Nemotron 3.5 Lightning** (`nvidia/Nemotron-3_5-Lightning`), fallback **Nemotron 3 Nano 30B** (`nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B`) | NVIDIA, served on Token Factory | Cheap, fast work: working out how to install and test a repo, spotting new output noise patterns, short summaries | 1, 7 |
| **Nebius Token Factory API** (OpenAI-compatible, structured output) | Nebius | Serves all the Nemotron models above | all model steps |
| **Nebius Token Factory Sandboxes** (Contree SDK, beta) | Nebius | Builds main once and saves a checkpoint, forks it for the PR, and runs every probe and test suite on both sides in parallel, isolated. Beta limit: 50 operations at once | 2, 3, 6 |
| **Nebius Serverless AI endpoint** | Nebius | Hosts the Proof-of-Change service: webhook/API, queue, orchestrator, run store, web report | 0, 9 |
| **Nebius Serverless AI job** | Nebius | Batch runs: daily ops over all tracked libraries' open PRs, and offline evaluation replays | 10, daily ops |

Model IDs must be confirmed at build time with `GET https://api.tokenfactory.nebius.com/v1/models`. Do not use Nemotron 3 Nano Omni: it was scheduled to leave Token Factory Serverless on 31 Aug 2026.

### Recommended (strengthens guardrails and the pitch)

| Tool | Why |
|---|---|
| **NVIDIA NemoClaw / OpenShell** | Runs the always-on ops agent (the daily PR-testing run) under an enforced policy: which hosts it may reach, which files it may touch, and no posting. This makes the "never posts upstream" guardrail enforced by the platform, not only by our code. Shown in the hackathon materials as NVIDIA's stack for private, always-on agents. |
| **Contree MCP server** (Nebius Sandboxes) | Lets Cursor or Claude call Proof-of-Change sandboxes directly. Needed only for the MCP stretch goal. |
| **Token Factory preloaded SWE environments** (SWE-bench Verified, SWE-rebench) | Ready-made environments to measure false alarms on known-good fixes. |

### Optional, not NVIDIA
- **Tavily** web search: fetch current docs or changelogs for a probe. Adds eligibility for the $3,000 Best Use of Tavily bonus (needs a live Tavily call at runtime).

### Not needed for this project
- NVIDIA Cosmos, GR00T, Sonic, Isaac and the Physical AI Workbench, and Jetson hardware. These are for the Physical AI track.
- NVIDIA NIM and NeMo are not named in the hackathon materials, so we don't depend on them.

### Open items
1. Nebius API key and credits ($25 with code NEBIUS-DEVPOST-GLOBAL26, plus $25 through the Builders Program). Until then everything runs on our own machine, and records say `machine: box`.
2. Whether credits cover a Serverless AI endpoint, and Ultra 550B call volume.
3. Per-run network isolation in Sandboxes: not documented; ask Nebius.

## 5. Verdict rules (spec §6.7; implemented in `poc/verdict.py`)

Per finding (behavior-map colour): **green** proven (or unchanged where "no change" was claimed); **red** false claim,
or unmentioned change on public surface; **amber** differs, claim-related but uncertain, or **flaky** (a side disagrees
with itself across reruns: never red); **grey** not testable (always shown, never hidden).

Per PR, applied in this order:

| Verdict | Rule | Check conclusion |
|---|---|---|
| could not verify | the project did not build, or fewer than half of the testable claims could be probed | neutral |
| needs attention | at least one false claim, unmentioned public change, or amber finding | neutral |
| verified | every testable claim proven and no red finding | success |

Verdicts **never block a merge** and a check is never marked failed by default; blocking is an opt-in repo setting
(spec §5.5 Screen 6, §6.7). **[ASSUMED]** A PR with no testable claims and no findings is "could not verify"; a testable
claim probed but not proven with no red/amber finding is "needs attention".

## 6. Behavior map (spec §5.6)

Three columns: what the PR says (claims + a "not mentioned" node) → what the code touched (changed public functions,
classes, endpoints, commands) → what we observed (one node per probe, coloured as in §5). A red node linked to "not
mentioned" is the headline finding. Each finding panel shows the exact input, main output, PR output, rerun agreement,
probe code and the model's reasoning next to the raw outputs.

## 7. Guardrails

- **G-det (deterministic comparison).** Probes only print one JSON object and never assert. The comparison of main vs
  PR outputs, the rerun confirmation and the PR verdict are plain code (`poc/diff.py`, `poc/verdict.py`). A model
  can explain and label, but it cannot change observed outputs or "make a probe pass"; raw outputs are always shown
  next to the model's words (spec §6.4, §6.7).
- **G-quote.** Every claim carries a `source_quote` copied from the PR text; no quote, no claim. Every LLM statement in a
  report must cite a real output or log line (eval E6 from v0.2, kept).
- **G-sandbox.** Untrusted PR code runs only in VM-isolated Token Factory Sandboxes, with a timeout per run, no secrets
  passed in, and one command per probe (no long-lived servers between runs).
- **Network-cutoff risk.** The Sandboxes docs we read show network access (needed for installs) and **no documented
  per-run switch to turn it off** (spec §6.5, §10). Mitigation: install before probes, probes talk to localhost only,
  and ask Nebius (§14 Q8). Until answered, probe isolation from the internet is **not guaranteed**, and reports say so.
  The box/CI downstream harness already runs tests without network where it can (`unshare -rn` in Jonathan's runner).
- **G-ext (no external posting).** Nothing posts to a real upstream repo, issue tracker, chat or email. The GitHub App
  only writes check runs and comments on **our own demo/mirror repos**. CI uses a read-only token, and
  `guardrails/no_external.py` fails CI on posting/pushing code. The App's write path is a reviewed exception
  (`# br-allow-external:`) **[ASSUMED]**.
- **G-schema.** Every record (downstream run, probe result, eval result) is schema-validated before it counts.
  **Single source of truth:** the shared JSON Schema `harness/schema/observation.schema.json` (`$id`
  `blast-radius/observation/v1`, sha256 `5a3c3d36…8383e`, agreed with Jonathan, merged from `feat/shared-schema` @
  `ed75df4`). `guardrails/schema.py` loads that file and validates it with a stdlib-only subset of JSON Schema; it
  no longer keeps its own field list. Nathan extensions, documented in the module docstring:
  E1 modes: `v1` (full schema; forced for golden batches with `--require-v1`, and automatic for any record that
  declares `schema_version`), `ci` (pre-v1 harness records: no `schema_version/accepted/gates/network/report`),
  `legacy` (`--legacy`: also no `machine_type/thread_env`); E2 cross-field rule `classification` may be null only
  when `accepted` is false; E3 a record's `schema_path` is **never opened** (it may name another checkout), the
  reference is verified by `schema_sha256` against this repo's copy; E4 JSON booleans never count as integers.
- **G-blind.** Eval runs get the PR without the answer (§9); `evals/pr_metrics.blind_input` refuses inputs that leak
  the label.

## 8. Approver report (every run)

Every run (a Proof-of-Change run on a PR, a downstream-test record, or an eval batch) produces a Markdown approver
report: header (source, machine type, schema mode), overall **APPROVE / REJECT**, then per item: what was run and
where, the verdict/class counts, **What went right**, **What went wrong**, **How to fix**, pending/TODO items.
Rule: any FAIL → REJECT; WARN and TODO are shown but do not block. Generator: `reports/generate.py` (today it covers
downstream records and eval batches; PR-run reports with verdict and behavior-map summary are **TODO**). The approver
recommendation is about trusting the run, not about merging the PR.

## 9. Evals

**Labelled PR set** (Jonathan builds it; `evals/labelled_prs.json`): real merged PRs from NumPy, pandas and
scikit-learn, each labelled `caused_regression` or `safe`, with evidence links. Each case has an `input` block (all
Proof-of-Change sees) and an `answer` block (withheld; used only for scoring).

- **Catch rate** = regressions flagged `needs attention` / scored regressions.
- **False-alarm rate** = safe PRs flagged `needs attention` / scored safe PRs.
- `could not verify` is reported separately and never counts as a catch. Only cases with `verification: verified`
  are scored. With ~10 PRs these are counts/anecdotes, and public material says so (spec §9.2).
- Targets (spec §9.1): requests #6655 shows C1 proven and the override break as an unmentioned red finding on every
  run; all 4 bookstore PRs get the expected verdict; zero false red findings on the honest PR.

**Answer key, current state:**

| Case | Label | Verification | Downstream check |
|---|---|---|---|
| psf/requests #6655 (base `eea3bbf`, head `c0813a2`) | caused_regression (docker-py override of `get_connection()`) | verified (spec §7.4; local probes 29 Sep 2026) | not applicable |
| scikit-learn/scikit-learn #29677 "API Revamp estimator tags" (merged 4 Sep 2024, 20:55 IST, merge `e04142cb`) | caused_regression (removed `_safe_tags`; imbalanced-learn 0.12.4 fails at import) | **verified by me**: `def _safe_tags` exists in `sklearn/utils/_tags.py` at parent `0bfebf42`, is gone at `e04142cb` and at tag 1.6.0rc1, and comes back (deprecated) at 1.6.0 via PR #30327 | golden G1 (below) |
| pandas-dev/pandas #56633 "CoW: Enable CoW by default and remove warning build" (merged 1 Feb 2024, 14:34 IST, merge `3b57972c`, base `c3014abb`) | caused_regression (CoW mandatory; UpSetPlot #303) | **verified**: found by Jonathan; PR, merge commit and base re-checked against the GitHub API 10 Oct 2026; downstream break reproduced at release level (2.3.3 → 3.0.0rc0) | golden G2 |
| Safe PRs | safe | **TODO** (Jonathan). The clean pair G3 is a release pair, not a PR, so it does not fill this slot | n/a |
| poc-demo-bookstore PRs 1–4 | 1 safe, 3 regressions | **example data**, never scored | n/a |

**Golden downstream cases (`evals/golden_cases.json`; records `evals/fixtures/golden_v1.jsonl`, Jonathan's final
runner, HARNESS_VERSION 1.0, 10 Oct 2026 IST; all three active, all three required in a golden batch):**
- G1 (active): scikit-learn 1.5.2 → 1.6.0rc1 vs imbalanced-learn 0.12.4 (Python 3.13). Old side `2238 passed, 33
  skipped, 1 xfailed, 5 xpassed` x3; new side `0 passed, 525 errors` x3; the import error mentions `_safe_tags`
  (matched by content: pytest's `E   ` prefix is stripped first). Exact classes: **import_failure 46 (modules),
  lost_tests 2243, real_break 0**, every other class 0. The 525 errors are 20 module collection errors plus 505
  xdist "CollectError" setup failures, counted once per module.
- G2 (active): pandas 2.3.3 → 3.0.0rc0 vs UpSetPlot 0.9.0 (numpy 2.3.5, matplotlib 3.10.8, pytest 9.1.1): exactly
  **67 real breaks, 6 already broken** (unchanged), every other class 0; old `233 passed, 6 failed` x3, new `166
  passed, 73 failed` x3; top signature "Invalid RGBA argument: nan". Answer key: pandas PR #56633.
- G3 (active, promoted from candidate C1 on 10 Oct): scikit-learn 1.5.1 → 1.5.2 vs imbalanced-learn 0.12.4
  (Python 3.12; 1.5.1 has no cp313 wheel): **2238 passed on both sides in every run, 0 in every class**. Guards
  against false alarms.
- Raw pytest counts are asserted from `per_run[].summary_counts`, cross-checked against `pytest_summary`; never from
  JUnit counts (JUnit counts xpassed as passed: 2243 = 2238 + 5).

**Per-record evals:** schema (shared v1 schema; strict); versions installed; 3
alternating runs per side; single thread; golden cases; LLM citations; prediction match (warn); golden coverage in
golden batches.

## 10. Daily routine

From Sun 11 Oct 2026, 10:15 AM IST: Jonathan sends **3 real merged PRs a day** (from the labelled set). Nathan runs each
blind (input only), runs the downstream check where one applies, applies evals and guardrails, and produces an approver
report for Aritra the same day **[ASSUMED: same-day turnaround]**. Catch/false-alarm counts are updated as scored
cases accumulate.

## 11. CI/CD

- Repo `aritracodesbad123/blast-radius` (to be created; the name may change to Proof-of-Change, §14 Q9). `main` is
  protected: PR required, CI must pass, no force push. Work happens on `feat/*` branches; Aritra approves and merges.
- `.github/workflows/ci.yml` (push to `main`/`feat/**`, PRs): ubuntu-latest, Python 3.11 and 3.12, single-thread env;
  records the runner machine type; ruff; no-external guardrail; pytest (verdict rules, deterministic diff, metrics,
  schema, evals); strict golden evals (`--require-golden --require-v1`) on `evals/fixtures/golden_v1.jsonl`; approver report to the step summary and as an artifact.
- Heavy work (Sandbox runs, downstream suites, the labelled-PR replay) runs outside PR CI: on the box now, as a
  Serverless AI job later (spec §6.2 step 10). Its results go through the same evals.
- Submission needs a public repo with an open-source license (Apache-2.0 proposed) and a README naming every NVIDIA
  model and Nebius service used (spec §11.3).

## 12. Plan to 30 Oct 2026 (Aritra's summary mapped onto spec §8.2)

| Week (IST) | Milestone |
|---|---|
| 1: Wed 30 Sep – Tue 6 Oct | requests #6655 probes run on both commits **inside Sandboxes** from one main checkpoint and one PR fork; a CLI prints the difference. **Status unknown:** on the box I only found the local (non-Sandbox) probe run from 29 Sep. |
| 2: Wed 7 – Tue 13 Oct (current) | A PR link alone → claims → probes → both sides → correct verdict JSON for requests #6655 and ≥3 of 4 bookstore PRs. |
| 3: Wed 14 – Tue 20 Oct | GitHub App (webhook, check run, comment, `/prove`) + hosted web report with the behavior map. |
| 4: Wed 21 – Tue 27 Oct | Demo runs 5 times in a row without manual fixes; eval table filled with real counts; rough video cut. |
| Final: Wed 28 – Fri 30 Oct | Code freeze Wed 28 end of day; video under 3:00; **submit by 12:00 noon IST Fri 30 Oct**. |

## 13. Repository layout

```
docs/REQUIREMENTS.md     this document
poc/                     verdict.py (enums + rule), diff.py (normalise/compare/confirm) - deterministic core
harness/                 downstream-test runner wrapper (Jonathan's br_run.py + PROTOCOL.md go here); schema/observation.schema.json (shared v1)
evals/                   labelled_prs.json, pr_metrics.py (catch/false-alarm), golden_cases.json, checks, fixtures
guardrails/              schema, isolation/timeouts, no-external scan
reports/                 approver report generator, samples
tests/                   pytest
```
Not built yet: claim extraction, probe generation, the Sandbox runner, GitHub App, web report, MCP server.

## 14. Open questions

From Aritra / spec §14:
1. **Team size and roles.** Who builds the agent loop, the Sandbox runner, the GitHub App and the web report? Spec
   §8.1 says that with 2 people, the MCP server and the timeline are cut first.
2. **Python only for the MVP?** Spec recommends yes. This draft assumes yes.
3. **Second demo: a real repo or the constructed bookstore?** Spec recommends the constructed one, clearly labelled.
   Aritra's summary also says constructed. Confirm.
4. **Tavily for the $3k bonus?** Spec: only if a probe genuinely needs current third-party docs.
5. Hosting: a Serverless AI endpoint, or a free host with Token Factory? Do the credits cover Compute?
6. License: Apache-2.0 or MIT?
7. Credit budget for Ultra calls per run.
8. Ask Nebius about per-run network isolation, the 50-operation limit and extra credits (the network-cutoff risk, §7).

Added by Nathan:
9. Repo name: keep `aritracodesbad123/blast-radius` or rename to Proof-of-Change before going public?
10. Week-1 milestone status: has anything run in Sandboxes yet? Are there Nebius API keys and credits?
11. ~~pandas answer key: which pandas PR made Copy-on-Write mandatory?~~ **Resolved 10 Oct:** pandas PR #56633,
    merge commit `3b57972c` (Jonathan; re-checked against the GitHub API). `evals/labelled_prs.json` case `pandas-56633`.
12. **Is scikit-learn #29677 a fair "caused regression" label?** `_safe_tags` was a private helper and was restored
    (deprecated) before 1.6.0 final. Downstream still broke on `_validate_data`.
13. Daily routine: 3 PRs a day blind. Where do reports go (chat, files)? Is same-day turnaround expected?
14. Downstream check in production: does it run inside the Sandboxes, or only for the eval set on the box/CI?
15. ~~Schema convergence with Jonathan's v1 schema~~ **Resolved 10 Oct:** `feat/shared-schema` (`ed75df4`) merged;
    `harness/schema/observation.schema.json` is the single source of truth and `guardrails/schema.py` reads it (§7
    G-schema). Remaining: Jonathan's three golden records name `schema_path` in the main checkout
    (`/workspace/blast-radius/harness/...`); evals verify them by `schema_sha256` instead of opening that path.
16. Carried from v0.2, **partly resolved 10 Oct:** Jonathan's runner now reproduces `525 errors` for G1 (root
    cause: importlib import mode, §4) and records `machine_type` and `thread_env`. It still has no
    `import_failure_messages` field; the eval reads the new-side import probe (`dependent_import.new`) and signatures
    instead. **Still open:** should a prediction mismatch be WARN or FAIL? Who approves when Aritra is away?
17. Golden G1 per-category counts and the G3 clean pair: **resolved 10 Oct** (§9).
