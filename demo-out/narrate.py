#!/usr/bin/env python3
"""Generate Microsoft Edge neural TTS (edge-tts) narration timed to the demo slides."""
from __future__ import annotations

import asyncio
import json
import subprocess
import wave
from pathlib import Path

import edge_tts

ROOT = Path(__file__).resolve().parent
VOICE = "en-US-JennyNeural"  # Microsoft neural voice via edge-tts
RATE = "+5%"
AUDIO_DIR = ROOT / "audio"
SEGMENTS = [
    (
        20.0,
        "Coding agents now write pull requests and describe what they changed. "
        "But a description is just a claim. Proof-of-Change checks those claims "
        "by running the old code and the new code side by side.",
    ),
    (
        25.0,
        "When a PR opens, our app reads the code. The only things it writes are "
        "one comment and one check result.",
    ),
    (
        30.0,
        "NVIDIA Nemotron, served through Nebius Token Factory, turns the "
        "description into testable claims: what should change and what should "
        "stay the same, including nearby inputs just past the edited code.",
    ),
    (
        35.0,
        "Each claim becomes a small probe. We run it on the code before and "
        "after the change and record the real results. If a probe measures "
        "nothing, we say we could not verify. We never call an empty check verified.",
    ),
    (
        30.0,
        "Here's a recorded example from a saved run. The PR said behaviour was "
        "preserved; the probe showed trailing spaces changed. Verdict: needs "
        "attention, with the exact input and both outputs attached. Every run "
        "saves a PDF report — built-in maker; Chrome not required. Reports are "
        "not emailed.",
    ),
    (
        25.0,
        "Tools like ORION and repro-engine already check stay-same and "
        "should-change behaviour. ORION is the closest to us, and we don't claim "
        "to be first. Our angle is comparing how agent-written and human-written "
        "PRs hold up against their own descriptions. What isn't proven yet: no "
        "live catch of a known real bug on the current code, and no validated "
        "false-alarm rate. Some results are could not verify when probes come "
        "back empty.",
    ),
    (
        15.0,
        "Proof-of-Change: don't trust the description — check the behaviour.",
    ),
]


def ffprobe_duration(path: Path) -> float:
    out = subprocess.check_output(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=nw=1:nk=1",
            str(path),
        ],
        text=True,
    ).strip()
    return float(out)


def wav_duration(path: Path) -> float:
    with wave.open(str(path), "rb") as w:
        return w.getnframes() / float(w.getframerate())


async def synth(text: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    mp3 = dest.with_suffix(".mp3")
    communicate = edge_tts.Communicate(text, VOICE, rate=RATE)
    await communicate.save(str(mp3))
    # Normalize to mono 48k wav for easy concat / padding
    subprocess.check_call(
        [
            "ffmpeg",
            "-y",
            "-loglevel",
            "error",
            "-i",
            str(mp3),
            "-ac",
            "1",
            "-ar",
            "48000",
            str(dest),
        ]
    )


def fit_to_slot(src: Path, slot_s: float, dest: Path) -> dict:
    dur = wav_duration(src)
    # Leave a short breath at the end of each slot
    target = max(0.5, slot_s - 0.35)
    filters = []
    if dur > target:
        # Speed up just enough to fit (atempo supports 0.5..2.0)
        ratio = min(1.5, dur / target)
        # chain atempo filters if needed (each must be 0.5..2.0)
        rem = ratio
        while rem > 2.0 + 1e-9:
            filters.append("atempo=2.0")
            rem /= 2.0
        filters.append(f"atempo={rem:.4f}")
        dur = dur / ratio
    pad = max(0.0, slot_s - dur)
    af = ",".join(filters) if filters else "anull"
    if pad > 0.001:
        # pad after speech
        if filters:
            af = f"{af},apad=pad_dur={pad:.4f}"
        else:
            af = f"apad=pad_dur={pad:.4f}"
    cmd = [
        "ffmpeg",
        "-y",
        "-loglevel",
        "error",
        "-i",
        str(src),
        "-af",
        af,
        "-t",
        f"{slot_s:.4f}",
        "-ac",
        "1",
        "-ar",
        "48000",
        str(dest),
    ]
    subprocess.check_call(cmd)
    return {
        "raw_s": round(wav_duration(src), 3),
        "slot_s": slot_s,
        "fitted_s": round(ffprobe_duration(dest), 3),
        "sped": dur < wav_duration(src) - 0.01,
    }


async def main() -> None:
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    meta = {"voice": VOICE, "rate": RATE, "engine": "edge-tts (Microsoft neural)", "segments": []}
    fitted_paths: list[Path] = []
    for i, (slot, text) in enumerate(SEGMENTS, start=1):
        raw = AUDIO_DIR / f"seg{i:02d}-raw.wav"
        fitted = AUDIO_DIR / f"seg{i:02d}.wav"
        await synth(text, raw)
        info = fit_to_slot(raw, slot, fitted)
        info.update({"i": i, "text": text})
        meta["segments"].append(info)
        fitted_paths.append(fitted)
        print(f"seg{i:02d}: raw={info['raw_s']}s → slot={slot}s")

    # Concat
    list_file = AUDIO_DIR / "concat.txt"
    list_file.write_text("".join(f"file '{p.name}'\n" for p in fitted_paths))
    narration = ROOT / "narration.wav"
    subprocess.check_call(
        [
            "ffmpeg",
            "-y",
            "-loglevel",
            "error",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(list_file),
            "-c",
            "copy",
            str(narration),
        ],
        cwd=str(AUDIO_DIR),
    )

    silent = ROOT / "proof-of-change-demo-silent.mp4"
    # Prefer rebuilding from current silent master; fall back to any existing
    if not silent.exists():
        raise SystemExit(f"missing silent video: {silent}")
    out = ROOT / "proof-of-change-demo.mp4"
    tmp = ROOT / "proof-of-change-demo-voiced.tmp.mp4"
    subprocess.check_call(
        [
            "ffmpeg",
            "-y",
            "-loglevel",
            "error",
            "-i",
            str(silent),
            "-i",
            str(narration),
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-shortest",
            str(tmp),
        ]
    )
    tmp.replace(out)
    meta["output"] = str(out)
    meta["duration_s"] = ffprobe_duration(out)
    (AUDIO_DIR / "meta.json").write_text(json.dumps(meta, indent=2))
    print(f"Wrote {out} ({meta['duration_s']:.1f}s) voice={VOICE}")


if __name__ == "__main__":
    asyncio.run(main())
