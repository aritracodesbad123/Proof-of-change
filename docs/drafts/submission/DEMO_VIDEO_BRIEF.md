# Proof-of-Change — Demo Video Brief (for filming)
Source: `docs/drafts/DEMO_SCRIPT.md` on main `88e8eb6`. Target 2:45, hard cap 3:00. Plain language.

## Ground rules (read before filming)
- Honesty frame: show what works, say plainly what is not proven.
- The only verdict example is **live140**, always labelled as a recorded example.
- **No** live #4147 catch. **No** false-alarm rate or percentage. **No** "first tool" claim.
- No people's names on screen. No API keys on screen.

## Shot list
| Time | On screen | Narration |
|---|---|---|
| 0:00–0:20 | PR description reading "fixes X, existing behaviour preserved." | "Coding agents now write pull requests and describe what they changed. But a description is just a claim. Proof-of-Change checks those claims by running the old code and the new code side by side." |
| 0:20–0:45 | A PR on GitHub; the Proof-of-Change check starts. | "When a PR opens, our app reads the code. The only things it writes are one comment and one check result." |
| 0:45–1:15 | Claims list: "should change" / "should stay the same". | "NVIDIA Nemotron, served through Nebius Token Factory, turns the description into testable claims: what should change and what should stay the same, including nearby inputs just past the edited code." |
| 1:15–1:50 | Side-by-side probe results: old value vs new value per input. | "Each claim becomes a small probe. We run it on the code before and after the change and record the real results. If a probe measures nothing, we say we could not verify. We never call an empty check verified." |
| 1:50–2:20 | live140 trailing-space case → needs attention / false claim, evidence block, saved PDF report. **Label visible for the whole segment.** | "Here's a recorded example from a saved run. The PR said behaviour was preserved; the probe showed trailing spaces changed. Verdict: needs attention, with the exact input and both outputs attached. Every run saves a PDF report (built-in maker; Chrome not required). Reports are not emailed." |
| 2:20–2:45 | Related-work card, then Known-gaps card. | "Tools like ORION and repro-engine already check stay-same and should-change behaviour. ORION is the closest to us, and we don't claim to be first. Our angle is comparing how agent-written and human-written PRs hold up against their own descriptions. What isn't proven yet: no live catch of a known real bug on the current code, and no validated false-alarm rate. Some results are 'could not verify' when probes come back empty." |
| 2:45–3:00 | Repo URL. | "Proof-of-Change: don't trust the description — check the behaviour." |

## On-screen labels (verbatim)
1. Hero segment (whole 1:50–2:20): **"Recorded example from a saved run (live140) — not a live run on today's code."**
2. Verdict chips, as named in the product: **verified**, **needs attention**, **could not verify**.
3. Related-work card: **"Closest related work: ORION (arXiv 2610.35223). Also: repro-engine, Testora, PatchGuru, Breakcheck, hearsay. We do not claim to be first."**
4. Angle card: **"Our angle: do agent-written and human-written PRs hold up against their own descriptions?"**
5. Known-gaps card:
   - **"No confirmed live catch of a known real bug on current code yet."**
   - **"No validated false-alarm rate yet."**
   - **"Empty probes return 'could not verify' — intended, but lowers coverage."**
   - **"VeeReview failed its own preregistered calibration against human labels."**
6. Closing card: **"github.com/aritracodesbad123/Proof-of-change"**

## Do-not-say / do-not-show
- "live", "today", "confirmed catch", or today's main SHA next to live140
- "caught #4147" in any form
- any false-alarm number (including 0/9)
- "first tool to…"
- names, keys, tokens

## Check before filming
