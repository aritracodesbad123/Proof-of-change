#!/usr/bin/env bash
# Set up Proof-of-Change on one fresh Ubuntu 24.04 VM. Run as root from a checkout of the repository:
#
#   sudo bash deploy/nebius/setup.sh --ip 203.0.113.7          # address becomes https://203-0-113-7.sslip.io
#   sudo bash deploy/nebius/setup.sh --domain poc.example.org  # or your own domain pointed at the VM
#
# Safe to run again (for example after a git pull): it reinstalls the app and restarts the services.
# It installs only what the app itself needs. Each pull request's own packages are installed later,
# during a check, inside the Contree sandbox; nothing per repository is installed here.
set -euo pipefail

SITE=""
while [ $# -gt 0 ]; do
  case "$1" in
    --ip) SITE="$(echo "$2" | tr . -).sslip.io"; shift 2 ;;
    --domain) SITE="$2"; shift 2 ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
done
[ "$(id -u)" -eq 0 ] || { echo "run with sudo" >&2; exit 1; }
[ -n "$SITE" ] || { echo "pass --ip <static public IP> or --domain <name>" >&2; exit 2; }

HERE="$(cd "$(dirname "$0")" && pwd)"
SRC="$(cd "$HERE/../.." && pwd)"
APP=/opt/proof-of-change/app
VENV=/opt/proof-of-change/venv
DATA=/var/lib/proof-of-change
ETC=/etc/proof-of-change
ENVF=$ETC/env
NODE_VERSION=22.20.0   # used only to build the console page, then removed

log() { echo "==> $*"; }

log "System packages"
export DEBIAN_FRONTEND=noninteractive
apt-get update -q
apt-get install -y -q --no-install-recommends \
  python3 python3-venv git curl ca-certificates xz-utils ufw \
  debian-keyring debian-archive-keyring apt-transport-https gnupg

log "Caddy (official package repository)"
if ! command -v caddy >/dev/null; then
  curl -fsSL https://dl.cloudsmith.io/public/caddy/stable/gpg.key | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
  curl -fsSL https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt > /etc/apt/sources.list.d/caddy-stable.list
  apt-get update -q && apt-get install -y -q caddy
fi

log "Service user and folders"
id proof-of-change >/dev/null 2>&1 || useradd --system --home-dir "$DATA" --shell /usr/sbin/nologin proof-of-change
# Every place the services write. The service files point the app's settings (POC_OPS_DIR, POC_OPS_RUNS,
# POC_REPORT_DIR, POC_HOSTED_REPORTS_DIR, POC_HEAVY_BUILD_DIR) here; the app code itself stays read-only.
install -d -o proof-of-change -g proof-of-change -m 750 "$DATA" "$DATA/runs" "$DATA/reports" \
  "$DATA/reports/daily" "$DATA/reports/hosted" "$DATA/work" "$DATA/work/heavy-builds" "$DATA/github-app"
install -d -o root -g root -m 700 "$ETC"

log "Server settings ($ENVF, root only)"
if [ ! -f "$ENVF" ]; then
  install -o root -g root -m 600 "$HERE/env.template" "$ENVF"
  echo "    created from the template; fill in the keys before the first check"
fi
chown root:root "$ENVF"; chmod 600 "$ENVF"
setting() { sed -n "s/^$1=//p" "$ENVF" | tail -1; }
set_if_empty() { # name value
  if [ -z "$(setting "$1")" ]; then
    if grep -q "^$1=" "$ENVF"; then sed -i "s|^$1=.*|$1=$2|" "$ENVF"; else echo "$1=$2" >> "$ENVF"; fi
  fi
}
set_if_empty POC_PUBLIC_URL "https://$SITE"
# Sign-up is invite-only: a new account needs this code. It lives only in the root-only file.
set_if_empty POC_INVITE_CODE "$(python3 -c 'import secrets; print(secrets.token_urlsafe(12))')"
set_if_empty SECRET_KEY "$(python3 -c 'import secrets; print(secrets.token_urlsafe(48))')"

log "App code ($APP)"
install -d -m 755 /opt/proof-of-change
rm -rf "$APP.new"
git -C "$SRC" archive --format=tar HEAD | (mkdir -p "$APP.new" && tar -x -C "$APP.new")
git -C "$SRC" rev-parse HEAD > "$APP.new/.deployed-commit"

log "Console page (temporary Node $NODE_VERSION, removed afterwards)"
NODE_TMP="$(mktemp -d)"
arch="$(uname -m)"; case "$arch" in x86_64) narch=x64 ;; aarch64) narch=arm64 ;; *) echo "unsupported CPU $arch" >&2; exit 1 ;; esac
NODE_TAR="node-v$NODE_VERSION-linux-$narch.tar.xz"
curl -fsSL -o "$NODE_TMP/$NODE_TAR" "https://nodejs.org/dist/v$NODE_VERSION/$NODE_TAR"
curl -fsSL -o "$NODE_TMP/SHASUMS256.txt" "https://nodejs.org/dist/v$NODE_VERSION/SHASUMS256.txt"
# Extract only if the download matches the SHA-256 that Node publishes for it.
(cd "$NODE_TMP" && grep " $NODE_TAR\$" SHASUMS256.txt | sha256sum -c -) \
  || { echo "Node download does not match its published SHA-256; stopping" >&2; exit 1; }
mkdir "$NODE_TMP/node" && tar -xJf "$NODE_TMP/$NODE_TAR" -C "$NODE_TMP/node" --strip-components=1
(cd "$APP.new/console/web" && PATH="$NODE_TMP/node/bin:$PATH" npm ci --no-audit --no-fund && PATH="$NODE_TMP/node/bin:$PATH" npm run build)
rm -rf "$NODE_TMP" "$APP.new/console/web/node_modules"

rm -rf "$APP.old"; [ -d "$APP" ] && mv "$APP" "$APP.old"; mv "$APP.new" "$APP"; rm -rf "$APP.old"
chown -R root:root "$APP" && chmod -R go-w "$APP"

log "Python packages ($VENV)"
[ -x "$VENV/bin/python" ] || python3 -m venv "$VENV"
"$VENV/bin/pip" install -q --upgrade pip
# The app plus the Contree SDK (sandbox), uv (the runner's installer) and PyJWT (GitHub App sign-in).
"$VENV/bin/pip" install -q "$APP[ops,contree,github]"
chown -R root:root "$VENV" && chmod -R go-w "$VENV"

log "systemd services (console on 127.0.0.1:8787, GitHub App on 127.0.0.1:8080)"
install -m 644 "$HERE/proof-of-change-console.service" /etc/systemd/system/
install -m 644 "$HERE/proof-of-change-app.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable proof-of-change-console proof-of-change-app >/dev/null
systemctl restart proof-of-change-console proof-of-change-app

log "Caddy for https://$SITE"
sed "s|__SITE__|$SITE|" "$HERE/Caddyfile.template" > /etc/caddy/Caddyfile
caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile
systemctl enable caddy >/dev/null
systemctl reload caddy 2>/dev/null || systemctl restart caddy

log "SSH: key sign-in only"
install -m 644 "$HERE/sshd-hardening.conf" /etc/ssh/sshd_config.d/10-proof-of-change.conf
if sshd -t; then
  systemctl reload ssh
else
  rm -f /etc/ssh/sshd_config.d/10-proof-of-change.conf
  echo "sshd -t failed; the SSH change was removed and sshd was not reloaded" >&2
  exit 1
fi

log "Firewall: 443 and 80 open, 22 for SSH"
CIDRS="${POC_SSH_ALLOW_CIDRS:-$(setting POC_SSH_ALLOW_CIDRS)}"
CIDRS="$(echo "$CIDRS" | tr ',' ' ')"
ufw --force reset >/dev/null
ufw default deny incoming >/dev/null
ufw default allow outgoing >/dev/null
ufw allow 80/tcp >/dev/null
ufw allow 443/tcp >/dev/null
if [ -n "${CIDRS// /}" ]; then
  for c in $CIDRS; do ufw allow from "$c" to any port 22 proto tcp >/dev/null; done
  echo "    SSH limited to: $CIDRS"
else
  echo "WARNING: POC_SSH_ALLOW_CIDRS is empty, so port 22 stays open to everyone (key sign-in only)." >&2
  ufw limit 22/tcp >/dev/null
fi
ufw --force enable >/dev/null
ufw status verbose

log "Health check"
sleep 3
bash "$HERE/healthcheck.sh" || echo "Some checks failed. The certificate can take a minute on the first run; try: sudo bash $HERE/healthcheck.sh"
echo
echo "Console: https://$SITE    Webhook URL for the GitHub App: https://$SITE/webhook"
