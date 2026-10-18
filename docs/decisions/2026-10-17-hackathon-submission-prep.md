# Hackathon submission prep: judge evidence and console honesty

**Date:** 2026-10-17  
**Status:** accepted

## What changed

We prepared the repository for NVIDIA×Nebius hackathon judging: audit / eval / demo / checklist under `reports/`, a short judge-facing README section, and console UI/API honesty so demos show whether a run is live, recorded, or using a sample path. The console API now surfaces `model_provider`, `run_flags`, and `run_note` (including unsafe-sandbox warnings) on queued jobs.

## Why

Judges need verifiable evidence and a demo that does not overclaim. Without clear live-vs-recorded badges and a run note when the sandbox is unavailable, a console demo can look like a full live Nebius check when it is not. Ablation that needs `NEBIUS_API_KEY` stays blocked until that key exists.

## Decision

1. Ship judge materials under `reports/` (audit, swarm evaluation write-up, 3-minute demo script, submission checklist, golden eval JSON dumps).
2. Keep agent-swarm semantics advisory (Ultra does not feed the score); document live Nebius ablation as blocked without `NEBIUS_API_KEY`.
3. Expose honesty fields from `start_check` / job status (`model_provider`, `run_flags`, `run_note`, warning when `--unsafe-no-sandbox` is used) and match the console UI with sample-demo / live / recorded cues.

## Alternatives and tradeoffs

- **Skip the decision log / ship reports only** — CI rejects code changes under `poc/` and `reports/` without an entry.
- **Force live Nebius in every demo** — fails on hosts without Contree/sandbox or API key; hurts judge reproducibility.
- **Tradeoff:** honesty badges and sample paths make demos reliable but require operators to read `run_note` before treating a run as a full live check.

## What it means for you

If you open the operator console for a demo, check the live/recorded/sample cues and any sandbox warning on the job. Hackathon evidence lives under `reports/`; live Nebius ablation still needs `NEBIUS_API_KEY`.
