# Proof-of-Change — Demo Video Script (target 2:45, hard cap 3:00)

> Internal draft. Narration is plain language for a non-technical viewer.
> **CLEARED LIVE CATCH: pending clearance** — do not add any live #4147 catch line until cleared.

## 0:00–0:20 — The problem
**On screen:** a pull request description saying "fixes X, existing behaviour preserved."
**Narration:** "Coding agents now write pull requests and describe what they changed. But a description is just a claim. Proof-of-Change checks those claims by running the old code and the new code side by side."

## 0:20–0:45 — Open a PR
**On screen:** open a PR on GitHub; the Proof-of-Change GitHub App starts a check.
**Narration:** "When a PR opens, our app reads the code. The only things it writes are one comment and one check result."

## 0:45–1:15 — Claims
**On screen:** list of claims pulled from the PR text: "should change" and "should stay the same".
**Narration:** "Nemotron, served through Nebius Token Factory, turns the description into testable claims: what should change, and what should stay the same — including nearby inputs just past the edited code."

## 1:15–1:50 — Check old vs new
**On screen:** side-by-side probe results, old value vs new value, per input.
**Narration:** "Each claim becomes a small probe. We run it on the code before and after the change and record the real return values — not the inputs, the results. If a probe measures nothing, we say we could not verify. We never call an empty check 'verified'."

## 1:50–2:20 — Verdict with evidence (labelled recorded example)
**On screen:** banner: **"Recorded example from a saved run (live140) — not a live run on today's code."** Show the trailing-space case: claim says behaviour preserved, probe shows output changed → needs attention, false claim.
**Narration:** "Here's a recorded example from a saved run. The PR said behaviour was preserved; the probe showed trailing spaces changed. Verdict: needs attention, with the exact input and both outputs attached. Every run also saves a PDF report — no browser needed to produce it."

[PLACEHOLDER — CLEARED LIVE CATCH: pending clearance. Insert only if cleared; otherwise skip.]

## 2:20–2:45 — Where we fit + honest gaps
**On screen:** short related-work card, then a gaps card.
**Narration:** "Tools like ORION and repro-engine already check stay-same and should-change behaviour; we don't claim to be first. Our angle is comparing how agent-written and human-written PRs hold up to their own claims.
What isn't proven yet: we haven't shown a live catch of a known real bug on the current code, and we don't yet have a validated false-alarm rate. Results can be 'could not verify' when probes come back empty."

## 2:45–3:00 — Close
**Narration:** "Proof-of-Change: don't trust the description — check the behaviour." Show repo URL.

### Do-not-say list
- "Confirmed live catch" / "caught #4147 live" (unless cleared)
- Any false-alarm percentage
- "First tool to…"
