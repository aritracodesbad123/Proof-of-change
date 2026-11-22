# Proof-of-Change — Demo storyboard (7 segments)

Target 2:45, hard cap 3:00. Narration from `docs/drafts/DEMO_SCRIPT.md` / `docs/drafts/submission/DEMO_VIDEO_BRIEF.md`.
Filmed deliverable: `demo-out/proof-of-change-demo.mp4` (auto-timed slides + captions for voice-over room).

## Files used
| Segment | Source files |
|---|---|
| All | `docs/drafts/DEMO_SCRIPT.md`, `docs/drafts/submission/DEMO_VIDEO_BRIEF.md` |
| Hero / live140 | `docs/drafts/CURSOR_HERO_CASE.md`, `tests/fixtures/claim_one_difference/rich-4147.json`, `tests/fixtures/boundary/rich-4147-live140-c2.json` |
| Gaps / related | `docs/drafts/README_HONESTY_SKELETON.md` |
| Product framing | `docs/drafts/README.md`, root `README.md` |

## live140 record found
- `tests/fixtures/claim_one_difference/rich-4147.json` — full saved run (`id` contains `live140`), verdict `needs_attention`, observation `C2.space_after` labelled `false_claim`.
- `tests/fixtures/boundary/rich-4147-live140-c2.json` — probe `model-probe-c2` stay-same claim + old/new runs.
- PDF: no committed live140 PDF in repo — slide uses a report card framed from the same record (built-in maker; Chrome not required).

---

### 1. Problem — 0:00–0:20
- **Frame:** Fake PR description: “fixes X, existing behaviour preserved.” Brand: Proof-of-Change.
- **On-screen:** That PR text; product name.
- **Narration:** “Coding agents now write pull requests and describe what they changed. But a description is just a claim. Proof-of-Change checks those claims by running the old code and the new code side by side.”
- **Source:** `DEMO_SCRIPT.md` §0:00–0:20

### 2. Open a PR — 0:20–0:45
- **Frame:** GitHub-style PR + Proof-of-Change check starting; “reads code / writes one comment + one check”.
- **Narration:** “When a PR opens, our app reads the code. The only things it writes are one comment and one check result.”
- **Source:** `DEMO_SCRIPT.md`, honesty skeleton “How it works on GitHub”

### 3. Claims — 0:45–1:15
- **Frame:** Claims list chips: should change / should stay the same; Nemotron via Nebius Token Factory.
- **Narration:** “NVIDIA Nemotron, served through Nebius Token Factory, turns the description into testable claims: what should change and what should stay the same, including nearby inputs just past the edited code.”
- **Source:** `DEMO_VIDEO_BRIEF.md`, skeleton “Where Nemotron…”

### 4. Old vs new — 1:15–1:50
- **Frame:** Side-by-side probe table (old value vs new value). Chips: verified / needs attention / could not verify.
- **Narration:** “Each claim becomes a small probe. We run it on the code before and after the change and record the real results. If a probe measures nothing, we say we could not verify. We never call an empty check verified.”
- **Source:** `DEMO_SCRIPT.md` §1:15–1:50

### 5. live140 verdict — 1:50–2:20
- **Frame:** Banner (whole segment): “Recorded example from a saved run (live140) — not a live run on today's code.” Trailing-space case → needs attention / false claim; evidence block; PDF report card.
- **Narration:** “Here's a recorded example from a saved run. The PR said behaviour was preserved; the probe showed trailing spaces changed. Verdict: needs attention, with the exact input and both outputs attached. Every run saves a PDF report (built-in maker; Chrome not required). Reports are not emailed.”
- **Source:** `CURSOR_HERO_CASE.md`, live140 fixture files above

### 6. Related work + gaps — 2:20–2:45
- **Frame:** Related-work card → Known-gaps card (verbatim labels from brief).
- **Narration:** “Tools like ORION and repro-engine already check stay-same and should-change behaviour. ORION is the closest to us, and we don't claim to be first. Our angle is comparing how agent-written and human-written PRs hold up against their own descriptions. What isn't proven yet: no live catch of a known real bug on the current code, and no validated false-alarm rate. Some results are 'could not verify' when probes come back empty.”
- **Source:** `DEMO_VIDEO_BRIEF.md` on-screen labels 3–5

### 7. Close — 2:45–3:00
- **Frame:** Closing card: `github.com/aritracodesbad123/Proof-of-change`
- **Narration:** “Proof-of-Change: don't trust the description — check the behaviour.”
- **Source:** `DEMO_VIDEO_BRIEF.md` closing card

## Screen-capture plan (if re-filming live UI)
1. Problem/claims/gaps: use `demo-out/slides.html` (this deck).
2. Optional live UI: GitHub Pages replay https://aritracodesbad123.github.io/Proof-of-change/ — only if time; still keep live140 labelled as recorded.
3. Leave audio free for voice-over; captions already on slides.
4. Do not show author names, keys, false-alarm %, or a live #4147 catch.
