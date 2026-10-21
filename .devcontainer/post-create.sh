#!/usr/bin/env bash
# One-time Codespace setup. Stops at the first failing step and logs everything.
set -Eeuo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LOG="${POC_SETUP_LOG:-/tmp/poc-setup.log}"
exec > >(tee -a "$LOG") 2>&1
trap 'echo "SETUP FAILED at line $LINENO: $BASH_COMMAND (full log: $LOG)"' ERR
cd "$ROOT"
echo "== Proof-of-Change setup $(date -u +%FT%TZ)"
echo "== installing bubblewrap"
sudo apt-get update -q
sudo apt-get install -y -q bubblewrap
echo "== installing the Python package"
python -m pip install -q -e '.[dev,contree]'
echo "== building the console web page"
(cd console/web && npm ci --no-audit --no-fund && npm run build)
test -f console/web/dist/index.html
echo "== checking the sandbox"
if bwrap --ro-bind / / true 2>/dev/null; then echo "SANDBOX_OK"; else echo "SANDBOX_UNAVAILABLE: bubblewrap cannot create a namespace in this container"; fi
echo "== setup finished"
