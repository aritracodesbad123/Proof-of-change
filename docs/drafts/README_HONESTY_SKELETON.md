# Proof-of-Change

<!-- Skeleton for README rewrite. Remove all HTML comments before publishing. Public text: no unfinished-work wording, no personal names. -->

## About (required blurb)
Proof-of-Change checks whether a pull request does what its description says. It turns the PR text into "should change" and "should stay the same" claims, runs probes on the old and new code, and posts a verdict with the evidence: verified, needs attention, or could not verify.

## Track
Coding and Agentic Engineering — NVIDIA × Nebius hackathon.

## Where Nemotron and Nebius Token Factory are used
- Claim extraction: Nemotron (via Nebius Token Factory) reads the PR title, description and diff and writes structured claims.
- Probe writing: Nemotron drafts small probes for each claim, including inputs just past the changed boundary.
- <!-- add model IDs, endpoint, config file path -->
Probe execution, old-vs-new comparison and the final verdict are deterministic code, not model output.

## What we built during the hackathon
- Claim extraction from PR text, including stay-same claims for nearby inputs when the text says behaviour is preserved
- Old-vs-new probe runner and verdict engine
- Guard that turns empty measurements into "could not verify" instead of "verified"
- GitHub App integration (comment + check result)
- PDF report saved with every run
- Agent-written vs human-written PR study harness
<!-- confirm list against git history -->

## How it works on GitHub
The GitHub App reads code. It writes only its own PR comment and its check result. Nothing else in the repository is changed.

## Reports
A PDF report is saved with every run. Reports are not emailed. Chrome is not required to produce the PDF.

## Setup
```bash
git clone https://github.com/aritracodesbad123/Proof-of-change
cd Proof-of-change
# install steps
# set NEBIUS_API_KEY (Token Factory)
# run on a PR
```
<!-- fill exact commands from repo -->

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
