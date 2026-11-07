#!/usr/bin/env bash
# Assemble real console screenshots + honesty slides + loud stereo edge-tts into the demo mp4.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
export PATH="$HOME/.local/bin:$PATH"
export DISPLAY=:99
CAP="$ROOT/capture"
WORK="$ROOT/assemble"
rm -rf "$WORK"
mkdir -p "$WORK" "$CAP"

# 1) Capture live console frames
cd /tmp
node /tmp/capture_console.mjs

# 2) Render honesty slides (locked frames) via headless chrome screenshots
pkill -f 'Xvfb :99' 2>/dev/null || true; sleep 0.2
Xvfb :99 -screen 0 1280x720x24 -ac >/tmp/xvfb-assemble.log 2>&1 &
sleep 0.8
google-chrome-stable --headless=new --no-sandbox --disable-gpu \
  --window-size=1280,720 --screenshot="$CAP/08-live140.png" \
  "file://$ROOT/slides.html#live140" >/tmp/chrome-slide.log 2>&1 || true

# Force slides via small helper pages
python3 - <<'PY'
from pathlib import Path
root = Path('/workspace/demo-out')
slides = (root/'slides.html').read_text()
# inject lock + jump helpers as standalone pages
for name, start in [('08-live140', 120), ('09-gaps', 150), ('10-close', 170)]:
    html = slides.replace(
        'requestAnimationFrame(tick);',
        f'window.__DEMO_LOCK=true; document.querySelectorAll(".slide").forEach(s=>s.classList.remove("active"));\n'
        f'const slides=[...document.querySelectorAll(".slide")];\n'
        f'let active=slides[0]; for (const s of slides) {{ const a=+s.dataset.start,b=+s.dataset.end; if ({start}>=a && {start}<b) active=s; }}\n'
        f'active.classList.add("active"); document.getElementById("cap").textContent=active.dataset.cap||"";\n'
        f'document.getElementById("bar").style.width="{start/180*100:.2f}%";\n'
    )
    (root/'assemble'/f'{name}.html').write_text(html)
print('helper pages written')
PY

for name in 08-live140 09-gaps 10-close; do
  google-chrome-stable --headless=new --no-sandbox --disable-gpu \
    --window-size=1280,720 --screenshot="$CAP/${name}.png" \
    "file://$WORK/${name}.html" >/dev/null 2>&1
  echo "slide $name"
done
kill %1 2>/dev/null || true

# 3) Build timed silent video from stills (durations match DEMO_VIDEO_BRIEF)
# 0-20 landing+list, 20-45 filter, 45-110 run exploration, 110-140 live140, 140-165 gaps, 165-180 close
python3 - <<'PY'
from pathlib import Path
import subprocess
cap = Path('/workspace/demo-out/capture')
work = Path('/workspace/demo-out/assemble')
# map segments to images + durations
plan = [
  ('01-landing.png', 10),
  ('02-finished-list.png', 10),
  ('03-filtered.png', 25),
  ('04-run-top.png', 20),
  ('05-run-mid.png', 20),
  ('06-run-evidence.png', 15),
  ('07-run-lower.png', 10),
  ('08-live140.png', 30),
  ('09-gaps.png', 25),
  ('10-close.png', 15),
]
# fallbacks
for img, _ in plan:
  p = cap/img
  if not p.exists():
    # pick any existing
    alts=sorted(cap.glob('*.png'))
    if not alts: raise SystemExit('no captures')
    p.write_bytes(alts[0].read_bytes())
    print('missing', img, 'filled')

clips=[]
for i,(img,dur) in enumerate(plan):
  out=work/f'clip{i:02d}.mp4'
  subprocess.check_call([
    'ffmpeg','-y','-loglevel','error',
    '-loop','1','-i',str(cap/img),
    '-t',str(dur),
    '-vf','scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2,format=yuv420p',
    '-r','30','-c:v','libx264','-pix_fmt','yuv420p','-preset','veryfast','-crf','18',
    str(out)
  ])
  clips.append(out)
lst=work/'list.txt'
lst.write_text(''.join(f"file '{c.name}'\n" for c in clips))
silent=Path('/workspace/demo-out/proof-of-change-demo-silent.mp4')
subprocess.check_call([
  'ffmpeg','-y','-loglevel','error','-f','concat','-safe','0','-i',str(lst),'-c','copy',str(silent)
], cwd=str(work))
print('silent', silent, 'dur check')
PY

# 4) Voice
python3 "$ROOT/narrate.py"
ffmpeg -y -loglevel error -i "$ROOT/proof-of-change-demo.mp4" -vn -c:a libmp3lame -q:a 2 \
  "$ROOT/proof-of-change-demo-narration.mp3"

ffprobe -v error -show_entries stream=codec_type,channels,duration -of compact=p=0 "$ROOT/proof-of-change-demo.mp4"
ls -lh "$ROOT/proof-of-change-demo.mp4" "$ROOT/proof-of-change-demo-narration.mp3"
ls -lh "$CAP"
