# Agent swarm evaluation

**Evaluation commit (baseline / golden evals):** `422788984d0df19499861f69a5234ab0cd598627`  
**Branch tip (includes this report + console UX):** see `git rev-parse HEAD` on `cursor/hackathon-submission-prep-81ec`  
**Date:** 2026-10-17  
**Models configured** ([`poc/model_provider.py`](../poc/model_provider.py)):

| Task | Model ID |
|---|---|
| claims / probes / summary | `nvidia/nemotron-3-super-120b-a12b` |
| judge | `nvidia/Nemotron-3-Ultra-550b-a55b` |
| helper | `nvidia/Nemotron-3_5-Lightning` (fallback `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B`) |

**Provider this run:** `recorded` for offline checks; **live `nebius` blocked** — `NEBIUS_API_KEY` unset in the evaluation environment.

## How A / B / C map to this codebase

| Mission config | Ablation baseline | What decides the verdict |
|---|---|---|
| A | `tests` | Deterministic pytest compare only |
| B | `tests+probes` | Tests + Super claim/probe generation (single-agent model path) |
| C | `full` | Tests + probes + coverage/AI-probe gates; **then** advisory Ultra/Lightning/Super swarm |

**Important limitation (measured in code + ADR):** the post-verdict swarm does **not** change `rec["verdict"]`. Incremental catch-rate value is from the **probe path (B/C vs A)**, not from Ultra labels. Swarm value for judges is explanation quality and advisory labels — do not treat C as “swarm improves recall” vs B.

## Fixed evaluation set

| Case | Kind | Role |
|---|---|---|
| golden-sklearn160rc1-imblearn-import-failure | Regression (package pair) | Downstream import break |
| golden-pandas300rc0-upsetplot-cow | Regression (package pair) | CoW / RGBA failures |
| golden-clean-sklearn151-152-imblearn | Safe change | False-alarm guard |
| golden-pr-mlxtend-1229-probe | Tests-pass / probes-catch | Edge + unmentioned behavioral drift |
| labelled `requests-6655`, `scikit-learn-29677`, `pandas-56633` | Regressions | Live ablation candidates |
| labelled `safe-TODO-1` | Safe | **Not filled** — FPR on PR set incomplete |

## Commands actually run

```bash
# Golden package-pair batch (CI gate)
.venv/bin/python -m evals.run_evals \
  --observations evals/fixtures/golden_v1.jsonl \
  --require-golden --require-v1 \
  --out reports/hackathon-golden-evals.json
# → {"counts": {"pass": 28, "skip": 3}, "recommendation": "APPROVE"}

# Golden PR known-answer (mlxtend#1229)
.venv/bin/python -m evals.run_evals \
  --observations evals/fixtures/golden_pr_v1.jsonl \
  --out reports/hackathon-golden-pr-evals.json
# → {"counts": {"pass": 6, "skip": 3}, "recommendation": "APPROVE"}

# Advisory swarm does not mutate verdict (recorded fixture)
.venv/bin/python -c "
from poc import agents, model_provider
import json
from pathlib import Path
p,_=model_provider.select('recorded')
rec=json.loads(Path('evals/fixtures/golden_pr_v1.jsonl').read_text().splitlines()[0])
v=rec['verdict']; agents.run_swarm(p, rec); assert rec['verdict']==v
"

# Live / full ablation (NOT run — blockers below)
# python -m evals.ablation --run --out-dir reports/hackathon-ablation-nebius --model-provider nebius
# python -m evals.ablation --run --out-dir reports/hackathon-ablation-recorded --model-provider recorded
```

## Measured A/B/C on mlxtend#1229 (known-answer fixture)

Source: [`evals/golden_cases.json`](../evals/golden_cases.json) `golden-pr-mlxtend-1229-probe` + fixture [`evals/fixtures/golden_pr_v1.jsonl`](../evals/fixtures/golden_pr_v1.jsonl), enforced by `evals.run_evals` (APPROVE above). Blind: **false** (fixed/recorded probe path).

| Config | Baseline | Verdict |
|---|---|---|
| A | `tests` | `verified` |
| A′ | `tests+diff` | `verified` |
| B | `tests+probes` | `needs_attention` |
| C | `full` | `needs_attention` |

**Interpretation:** existing tests alone miss the regression (A = false negative). Super claim/probe path recovers it (B/C). Swarm after C is advisory only — same code verdict as B for this case’s gate set.

Probe evidence expected (and checked by golden eval): differences on
`caller_x_after_call.changed_columns` and `int_groups_after_multi_group.importances`; claims C1/C2 proven.

## Package-pair golden summary (prior measured runs in fixtures)

| Case | Expected outcome | Role vs A/B/C |
|---|---|---|
| sklearn 1.6.0rc1 × imblearn | NEEDS ATTENTION (import failure) | Catch without model probes (tests/downstream) |
| pandas 3.0.0rc0 × UpSetPlot | NEEDS ATTENTION (67 new failures) | Catch without model probes |
| sklearn 1.5.1→1.5.2 × imblearn | VERIFIED (2238/2238) | Safe / false-alarm guard |

These are **not** re-executed live in this hackathon agent session; they are fixture-backed and CI-gated (`golden_v1` APPROVE).

## Swarm versus single-agent incremental value

| Question | Result |
|---|---|
| Does Ultra/Lightning/Summary change catch rate vs B? | **Not measured as a verdict metric** — by design they cannot |
| Does B/C improve over A on mlxtend#1229? | **Yes** — `verified` → `needs_attention` (fixture + golden eval) |
| Live Nebius token/cost/latency table | **Not produced** — key unset |
| Blind PR ablation table (`evals.ablation --run`) | **Not produced** — needs key + long dual-runs on labelled PRs |

## Blockers for a full live comparison

1. Export `NEBIUS_API_KEY` (and optionally `NEBIUS_PROJECT_ID` for Contree).
2. Re-run:

```bash
python -m evals.ablation --run --out-dir reports/hackathon-ablation-nebius \
  --model-provider nebius
# then open reports/hackathon-ablation-nebius/ablation.md
```

3. Fill a verified safe labelled PR (`safe-TODO-1`) before quoting blind FPR.

## Honesty note

No manufactured live Nebius metrics. Offline APPROVE results and the mlxtend A/B/C baseline table above are the measured evidence available in this environment.
