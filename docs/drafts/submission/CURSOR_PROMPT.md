# Paste into Cursor

You are helping produce a demo video plan and/or slide deck for the hackathon project Proof-of-Change.

**Sources: only these.** Repo: https://github.com/aritracodesbad123/Proof-of-change (branch `main`, at or after commit `88e8eb6`). Read `docs/drafts/DEMO_SCRIPT.md`, `docs/drafts/CURSOR_HERO_CASE.md`, `docs/drafts/README_HONESTY_SKELETON.md`, `docs/drafts/README.md`, and the root `README.md`. You cannot access any assistant workspace, scratch folder or local path outside this repo. If something is not in the repo, leave a clearly marked blank. Do not guess.

## Hard rules
1. Total length under 3:00 (target 2:45).
2. The only verdict example is the **live140** saved run, labelled for the whole segment: "Recorded example from a saved run (live140) — not a live run on today's code."
3. Do not claim a live catch of rich #4147 or any other live catch.
4. Do not show or say any false-alarm rate or percentage. Anything under "Shipping numbers" in the skeleton is gated. Leave it out.
5. Do not say "first". Cite ORION as the closest related work.
6. Show the known gaps on screen.
7. No people's names, no API keys or tokens, no `.env` contents, on any slide or frame.
8. Do not push, open PRs or change the repo. Write output to a new local folder only, for example `demo-out/`.

## Steps
1. Clone or open the repo on `main`. Confirm `docs/drafts/` exists.
2. Read `DEMO_SCRIPT.md`. It is the narration and timing. Keep the wording. Only tighten it for length.
3. Read `CURSOR_HERO_CASE.md`. Find the saved live140 run record and its report in the repo (search for `live140`). List the files you found. If you can't find them, say so and use a placeholder frame labelled "live140 record — to capture".
4. Build a 7-segment storyboard (problem, open a PR, claims, old vs new, live140 verdict, related work + gaps, close). For each segment give the frame, the narration, the on-screen text, and the source file.
5. Slides (if asked): one slide per segment, big text, plain language. Use the exact labels from DEMO_SCRIPT.md / CURSOR_HERO_CASE.md. Speaker notes = narration.
6. Video (if asked): screen-capture plan per segment: what to open, what to highlight, how long it stays. Leave room for a voice-over.
7. Final check. Grep your output for "first", "%", "false alarm", "#4147", "live catch", and any name or key-looking string. Fix every hit that breaks a rule.
8. Output: `demo-out/STORYBOARD.md`, plus `demo-out/slides.*` if slides were requested, plus a short list of which repo files each segment used.
