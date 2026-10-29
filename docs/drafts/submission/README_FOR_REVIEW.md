# Proof-of-Change

<!-- REVIEW COPY. Does not replace the root README. Built from docs/drafts/README_HONESTY_SKELETON.md @ 88e8eb6 + public README/model_provider.py. Skeleton for README rewrite. Remove all HTML comments before publishing. Public text: no unfinished-work wording, no personal names. -->

## About (required blurb)
Proof-of-Change checks whether a pull request does what its description says. It turns the PR text into "should change" and "should stay the same" claims, runs probes on the old and new code, and posts a verdict with the evidence: verified, needs attention, or could not verify.

## Track
Coding and Agentic Engineering — NVIDIA × Nebius hackathon.

## Where Nemotron and Nebius Token Factory are used
- Claim extraction: Nemotron (via Nebius Token Factory) reads the PR title, description and diff and writes structured claims.
- Probe writing: Nemotron drafts small probes for each claim, including inputs just past the changed boundary.
- Model IDs (from `poc/model_provider.py` on main):
  - Claims, probes, summary (Super): `nvidia/nemotron-3-super-120b-a12b`
  - Advisory judge (Ultra): `nvidia/Nemotron-3-Ultra-550b-a55b`
  - Advisory helper (Lightning): `nvidia/Nemotron-3_5-Lightning`, with fallback (Nano) `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B`
- Endpoint: `https://api.tokenfactory.nebius.com/v1` (OpenAI-compatible), key `NEBIUS_API_KEY`, used in the orchestrator only.
- Config: `poc/model_provider.py`.
Probe execution, old-vs-new comparison and the final verdict are deterministic code, not model output.

## What we built during the hackathon
- Claim extraction from PR text, including stay-same claims for nearby inputs when the text says behaviour is preserved
- Old-vs-new probe runner and verdict engine
- Guard that turns empty measurements into "could not verify" instead of "verified"
- GitHub App integration (comment + check result)
- PDF report saved with every run
- Agent-written vs human-written PR study harness
<!-- TODO: confirm list against git history -->

## How it works on GitHub
The GitHub App reads code. It writes only its own PR comment and its check result. Nothing else in the repository is changed.

## Reports
A report is saved with every run. Reports are not emailed. A PDF report is saved with every run by the built-in maker; Chrome is not required. Reports are not emailed.

## Setup
```bash
git clone https://github.com/aritracodesbad123/Proof-of-change
cd Proof-of-change
make setup                      # ends with "SETUP OK"
export NEBIUS_API_KEY="..."     # Nebius Token Factory key
make check PR=<public GitHub PR link>
make test                       # quick evaluation gate
```
Replay (no install, no API): https://aritracodesbad123.github.io/Proof-of-change/

## Related work
- **ORION** (arXiv 2610.35223) — the closest tool to ours; checks stay-same and should-change behaviour of code changes.
- **repro-engine** — reproduces and compares behaviour across versions.
- **Testora**, **PatchGuru** — test/behaviour checks of patches against intent.
- **Breakcheck**, **hearsay** — breaking-change and claim checking.

We do not claim to be first at stay-same or should-change checking. Our angle is a study of how agent-written and human-written PRs hold up against their own descriptions.

## Known gaps
- No confirmed live catch of a known real bug on the current code yet.
- No validated false-alarm rate yet.
- Runs return "could not verify" when probes measure nothing; this is intended, but lowers coverage.
- **VeeReview**: failed its own preregistered calibration against human labels; results are not comparable yet.

## Shipping numbers
<!-- GATED: publish only after reviewer sign-off -->
<!-- TODO: False alarms on safe PRs: 0/9 — pending clearance -->
<!-- TODO: Live catch of rich #4147 — pending clearance -->
<!-- If not cleared, delete this section entirely rather than leave placeholders public. -->
