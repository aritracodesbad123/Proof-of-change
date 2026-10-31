# Demo video pack (hackathon)

Built from `docs/drafts/submission/DEMO_VIDEO_BRIEF.md` and `CURSOR_PROMPT.md`.

| File | What |
|---|---|
| `proof-of-change-demo.mp4` | 3:00 demo: **real GitHub Pages console** + live140 honesty slides + Microsoft neural TTS (`edge-tts`, `en-US-JennyNeural`, stereo) |
| `proof-of-change-demo-narration.mp3` | Same voice track alone (use this if a player mutes the mp4) |
| `proof-of-change-demo-silent.mp4` | Picture only |
| `narrate.py` | Timed `edge-tts` → loud stereo AAC mux |
| `assemble_demo.sh` / `capture_console.mjs` | Capture Pages replay UI + assemble |
| `slides.html` | Honesty slides (live140 / gaps / close) |
| `STORYBOARD.md` / `SOURCES.md` | Plan + sources |

Hard rules respected: live140 labelled as recorded example; no live #4147 catch; no false-alarm %; no “first” claim; no names/keys on screen.

## Rebuild
```bash
pip install edge-tts
./assemble_demo.sh
```
