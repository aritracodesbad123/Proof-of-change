# Three-minute demo script

**Primary demo case:** [mlxtend#1229](https://github.com/rasbt/mlxtend/pull/1229)  
**Credential-free path:** console → **Try sample (mlxtend#1229, prerecorded)**  
**Live path (when `NEBIUS_API_KEY` is set):** same PR with provider `nebius` — UI must show **Live Nebius / Nemotron**, not the fixture badge.

**Demo video:** _TODO — record and paste public YouTube URL here_  
(`https://youtu.be/________`)

---

### 0:00–0:20 — Why passing tests is not enough

- Open the console (local: `make console-api` + `make console-web`, or `make console-host`).
- State: mlxtend#1229 changes feature-group permutation behaviour; **project tests still pass**.
- Point at the problem: merge advice based only on green CI can miss behavioral drift.

### 0:20–0:55 — Nemotron and the swarm’s distinct jobs

- Click **Try sample** (or paste the PR and choose `nebius` for live).
- Call out roles while stages light up:
  - **Super** — claims + probes (can affect the verdict via executed probes).
  - **Ultra / Lightning / Super-summary** — **advisory only** after the code verdict (labels, notes, plain-English summary).
- If the badge says **Prerecorded fixture (not blind)**, say so out loud. If live, say “real Token Factory call.”

### 0:55–1:40 — Run original and modified versions

- Watch **Install main / Install PR / Pytest / Probes**.
- Emphasize: same probe scripts run on **base** and **PR**; plain code compares observations.
- For live: mention Nebius Token Factory endpoint and Super model id briefly.

### 1:40–2:15 — Deterministic verdict and evidence

- Open the finished analysis / report.
- Verdict should be **needs_attention** when probes run (B/C); tests-only would have said **verified**.
- Click through probe evidence (observation diffs / log links). Say: **models propose; execution decides**.

### 2:15–2:40 — Measured A/B/C (if available)

- Show [`reports/AGENT_SWARM_EVALUATION.md`](AGENT_SWARM_EVALUATION.md) table:
  - A `tests` → verified  
  - B/C `tests+probes` / `full` → needs_attention  
- Clarify: swarm after verdict is advisory; the lift vs A is the **probe path**.
- If live ablation was not run, say so — do not invent rates.

### 2:40–3:00 — Practical value and one limitation

- Value: catch tests-pass behavioral breaks before merge; advice-only (never blocks).
- Limitation pick one: (a) live hosted sandbox may use `--unsafe-no-sandbox` without Contree; (b) Ultra does not yet feed the score; (c) labelled safe-PR set incomplete for blind FPR.
- CTA: judges can reproduce with the sample button or commands in the evaluation report.
