# Submission checklist — Nebius × NVIDIA Global AI Hackathon

Official rules: https://nebiusglobalaihackathon.devpost.com/rules  
Deadline: **Friday, October 30, 2026, 10:00 am PT**

## Track

- [x] Intended track: **Coding and Agentic Engineering** (primary fit: agents that run/test code)
- [ ] Alternate if desired: Best Apps and Agents (practical console) — pick one on the form

## Project requirements

| Item | Status | Notes |
|---|---|---|
| Runtime call to Nebius Token Factory or Nebius AI Cloud | Code ready; live needs key | `poc/model_provider.py` → `api.tokenfactory.nebius.com` |
| Uses ≥1 NVIDIA open-source model | Yes | Nemotron Super / Ultra / Lightning / Nano ids |
| Working demo URL | **Pending deploy approval** | Local + recorded sample works now |
| Public repo | Confirm GitHub visibility | `aritracodesbad123/Proof-of-change` |
| Open-source license visible | MIT | `LICENSE` |
| README with setup + Nemotron/Token Factory highlight | Updated this branch | Judge section at top |
| Demo video ≤3 min on public YouTube | **Missing** | Script: [`DEMO_SCRIPT_3MIN.md`](DEMO_SCRIPT_3MIN.md) |
| Feedback on Nebius/NVIDIA tools on form | Human | Required by rules |
| Significant updates during period (if pre-existing) | Document in README | Hackathon delta section |

## Judging criteria readiness

| Criterion | Prep status |
|---|---|
| Technological Implementation | Dual-run + probes + advisory swarm; eval evidence in [`AGENT_SWARM_EVALUATION.md`](AGENT_SWARM_EVALUATION.md) |
| Design | Console sample button, live vs fixture badges, sandbox honesty banner |
| Potential Impact | Honest: advice-only behavioral compatibility for OSS Python PRs |
| Quality of the Idea | “Don’t trust green tests alone — run the change” with deterministic verdict |

## Assets in `reports/`

- [x] [`HACKATHON_AUDIT.md`](HACKATHON_AUDIT.md)
- [x] [`AGENT_SWARM_EVALUATION.md`](AGENT_SWARM_EVALUATION.md)
- [x] [`DEMO_SCRIPT_3MIN.md`](DEMO_SCRIPT_3MIN.md)
- [x] This checklist
- [x] Golden eval JSON outputs (`hackathon-golden-evals.json`, `hackathon-golden-pr-evals.json`)

## Remaining blockers (priority)

1. **Export `NEBIUS_API_KEY`** and run a live Token Factory demo + optional `evals.ablation --run --model-provider nebius`.
2. **Record ≤3 min YouTube video** from [`DEMO_SCRIPT_3MIN.md`](DEMO_SCRIPT_3MIN.md).
3. **Approve and execute hosted deploy** (proposal below) so the Devpost form has a demo URL.
4. Fill labelled safe PR (`safe-TODO-1`) before quoting blind false-alarm rates.
5. Confirm GitHub repo is **public** and license shows in the About box.

---

## Deploy proposal (awaiting your approval — not executed)

Per decision **2B**, nothing has been deployed. When you approve, preferred path:

### Option A — Render Blueprint (free tier)

1. Open https://dashboard.render.com → **New** → **Blueprint**.
2. Select this repo; apply [`render.yaml`](../render.yaml) (service `poc-console`).
3. Set secrets: `NEBIUS_API_KEY` (required for live models), optional `NEBIUS_PROJECT_ID` + Contree for remote sandboxes, optional `GITHUB_TOKEN`.
4. Note: without Contree/bwrap, console uses `--unsafe-no-sandbox` (UI shows `run_note`). Free instances sleep when idle.
5. Paste `https://<service>.onrender.com` into README and Devpost.

### Option B — Nebius Serverless AI Endpoint (paid Compute)

```bash
make docker-console IMAGE=docker.io/<you>/poc-console:latest
make nebius-console IMAGE=… SUBNET_ID=… NEBIUS_API_KEY=… NEBIUS_PROJECT_ID=…
```

Script prints a managed `https://…` URL. Same SPA as local.

**Do not run either path until you explicitly approve in chat.**
