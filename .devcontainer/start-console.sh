#!/usr/bin/env bash
# Start the Codespace console. Sign-in is skipped only while port 8787 stays private.
PORT=8787
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LOG="${POC_CONSOLE_LOG:-/tmp/poc-console.log}"
cd "$ROOT"

if command -v python >/dev/null 2>&1; then
  PYTHON=python
else
  PYTHON=python3
fi

raw=""
if command -v gh >/dev/null 2>&1; then
  if [ -n "${CODESPACE_NAME:-}" ]; then
    raw="$(gh codespace ports -c "$CODESPACE_NAME" --json port,visibility 2>/dev/null || true)"
  else
    raw="$(gh codespace ports --json port,visibility 2>/dev/null || true)"
  fi
else
  echo "GitHub CLI missing, so port 8787 cannot be confirmed private. Sign-in stays on; open it with the code from: cat /tmp/poc-console-code" >&2
fi
if [ -z "$raw" ]; then
  # Fail closed: an unread port list never skips sign-in. Create the owner-only console code instead.
  "$PYTHON" -c 'from poc.console_auth import ensure_access_code; ensure_access_code()' || true
fi

refusal="$(printf '%s' "$raw" | "$PYTHON" -c 'import sys
from poc.console_auth import port_refusal
sys.stdout.write(port_refusal(sys.stdin.read()) or "")')"

if [ -n "$refusal" ]; then
  printf '%s\n' "$refusal" >&2
  exit 1
fi

if [ "${POC_CONSOLE_DRY_RUN:-}" = "1" ]; then
  echo "start"
  exit 0
fi

if [ ! -f console/web/dist/index.html ]; then
  echo "Console web page not built yet. Building it now (about a minute)..."
  if ! (cd console/web && npm ci --no-audit --no-fund && npm run build) >>"$LOG" 2>&1; then
    echo "Console web page build failed. See $LOG" >&2
    exit 1
  fi
fi

listening() { "$PYTHON" -c "import socket,sys;s=socket.socket();s.settimeout(1);sys.exit(s.connect_ex(('127.0.0.1',$PORT)))"; }

if listening; then
  echo "Console already running on port $PORT."
  exit 0
fi

# setsid detaches the server from this lifecycle command, so it keeps running after the command exits.
POC_SWARM=1 POC_SINGLE_USER=1 setsid nohup "$PYTHON" -m poc.console_api --host 0.0.0.0 --port "$PORT" \
  >>"$LOG" 2>&1 < /dev/null &
disown || true

for _ in $(seq 1 30); do
  if listening; then
    echo "Console is listening on port $PORT. Open the Ports tab and the globe icon for port $PORT."
    exit 0
  fi
  sleep 1
done
echo "Console did not start within 30 seconds. Last lines of $LOG:" >&2
tail -n 20 "$LOG" >&2
exit 1
