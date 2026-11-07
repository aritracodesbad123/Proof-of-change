#!/usr/bin/env bash
# Film GitHub Pages replay console + live140 slide, then mux loud stereo TTS.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
export PATH="$HOME/.local/bin:/tmp/node_modules/.bin:$PATH"
export DISPLAY="${DISPLAY:-:99}"
OUT_SILENT="${ROOT}/proof-of-change-demo-silent.mp4"
OUT="${ROOT}/proof-of-change-demo.mp4"
PUPPETEER_CACHE_DIR="${PUPPETEER_CACHE_DIR:-/tmp/puppeteer-cache}"
export PUPPETEER_CACHE_DIR

pkill -f "Xvfb ${DISPLAY}" 2>/dev/null || true
pkill -f "film_platform_demo" 2>/dev/null || true
sleep 0.5

Xvfb "${DISPLAY}" -screen 0 1280x720x24 -ac +extension RANDR >/tmp/demo-xvfb2.log 2>&1 &
XVFB_PID=$!
sleep 1

# Start ffmpeg first so we catch the first paint
ffmpeg -y -loglevel error \
  -f x11grab -video_size 1280x720 -framerate 30 -i "${DISPLAY}.0+0,0" \
  -t 182 \
  -c:v libx264 -pix_fmt yuv420p -preset veryfast -crf 20 \
  "${OUT_SILENT}" &
FF_PID=$!
sleep 1

cd /tmp
export NODE_PATH=/tmp/node_modules
node /tmp/film_platform_demo.mjs >/tmp/demo-tour.log 2>&1 || {
  echo "tour failed"; tail -50 /tmp/demo-tour.log; kill $FF_PID $XVFB_PID 2>/dev/null || true; exit 1
}

wait "$FF_PID" || true
kill "$XVFB_PID" 2>/dev/null || true

# Rebuild narration (loud stereo AAC) onto the new silent picture
python3 "${ROOT}/narrate.py"

# Standalone mp3 — chat video embeds often mute; this lets you hear the VO alone
ffmpeg -y -loglevel error -i "${OUT}" -vn -c:a libmp3lame -q:a 2 "${ROOT}/proof-of-change-demo-narration.mp3"

echo "Wrote ${OUT}"
ffprobe -v error -show_entries stream=codec_type,codec_name,channels,duration -of compact=p=0 "${OUT}"
ls -lh "${OUT}" "${ROOT}/proof-of-change-demo-narration.mp3"
