#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
OUT="${ROOT}/proof-of-change-demo.mp4"
DISPLAY_NUM="${DISPLAY_NUM:-99}"
export DISPLAY=":${DISPLAY_NUM}"

pkill -f "Xvfb :${DISPLAY_NUM}" 2>/dev/null || true
pkill -f "google-chrome" 2>/dev/null || true
sleep 0.5
rm -rf /tmp/poc-demo-chrome
mkdir -p /tmp/poc-demo-chrome

Xvfb ":${DISPLAY_NUM}" -screen 0 1280x720x24 -ac +extension RANDR >/tmp/demo-xvfb.log 2>&1 &
XVFB_PID=$!
sleep 1

# --app hides browser chrome; --kiosk as backup fullscreen
google-chrome-stable \
  --user-data-dir=/tmp/poc-demo-chrome \
  --app="file://${ROOT}/slides.html" \
  --window-size=1280,720 \
  --window-position=0,0 \
  --disable-infobars \
  --disable-session-crashed-bubble \
  --noerrdialogs \
  --disable-notifications \
  --autoplay-policy=no-user-gesture-required \
  --disable-features=TranslateUI,ChromeWhatsNewUI \
  --no-first-run \
  --disable-default-apps \
  --force-device-scale-factor=1 \
  >/tmp/demo-chrome.log 2>&1 &
CHROME_PID=$!

sleep 5
# Move app window to 0,0 and size exactly
WID=$(xdotool search --onlyvisible --class "Chrome\|Chromium\|Google-chrome" | head -1 || true)
if [[ -n "${WID:-}" ]]; then
  xdotool windowmove "$WID" 0 0
  xdotool windowsize "$WID" 1280 720
fi
sleep 0.5
# Reload to restart timer cleanly
if [[ -n "${WID:-}" ]]; then
  xdotool windowactivate "$WID"
  xdotool key --clearmodifiers ctrl+r
fi
sleep 1.5

ffmpeg -y -loglevel error \
  -f x11grab -video_size 1280x720 -framerate 30 -i "${DISPLAY}.0+0,0" \
  -t 180 \
  -c:v libx264 -pix_fmt yuv420p -preset veryfast -crf 20 \
  "${OUT}"

kill "${CHROME_PID}" 2>/dev/null || true
kill "${XVFB_PID}" 2>/dev/null || true
wait 2>/dev/null || true
echo "Wrote ${OUT}"
ls -lh "${OUT}"
ffprobe -v error -show_entries format=duration -of default=nw=1:nk=1 "${OUT}"
