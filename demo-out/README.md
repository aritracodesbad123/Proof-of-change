# Demo video pack (hackathon)

Built from `docs/drafts/submission/DEMO_VIDEO_BRIEF.md` and `CURSOR_PROMPT.md`.

| File | What |
|---|---|
| `proof-of-change-demo.mp4` | 3:00 demo with captions + Microsoft neural TTS (`edge-tts`, voice `en-US-JennyNeural`) |
| `proof-of-change-demo-silent.mp4` | Same picture, no audio (re-voice source) |
| `narrate.py` | Builds timed narration via `edge-tts` and muxes AAC onto the silent master |
| `slides.html` | Auto-timed 7-segment deck used to film |
| `STORYBOARD.md` | Segment plan + sources |
| `SOURCES.md` | Segment → repo file map |
| `record_demo.sh` | Re-record picture: Xvfb + Chrome `--app` + ffmpeg |

Hard rules respected: live140 labelled as recorded example; no live #4147 catch; no false-alarm %; no “first” claim; no names/keys on screen.

## Re-voice
```bash
pip install edge-tts
python3 narrate.py   # reads *-silent.mp4, writes proof-of-change-demo.mp4
```
