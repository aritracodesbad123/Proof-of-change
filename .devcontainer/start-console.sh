#!/usr/bin/env bash
# Start the Codespace console. Sign-in is skipped only while port 8787 stays private.
PORT=8787
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if command -v python >/dev/null 2>&1; then
  PYTHON=python
else
  PYTHON=python3
fi

raw=""
if command -v gh >/dev/null 2>&1; then
  raw="$(gh codespace ports --json port,visibility 2>/dev/null || true)"
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

POC_SWARM=1 POC_SINGLE_USER=1 nohup "$PYTHON" -m poc.console_api --host 0.0.0.0 --port "$PORT" >/tmp/poc-console.log 2>&1 &
