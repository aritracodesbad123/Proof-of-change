#!/usr/bin/env bash
# Health check: both local services, then the public HTTPS address. Exit 0 only if all answer.
set -u
fail=0
check() { # name url
  if curl -fsS --max-time 10 "$2" >/dev/null; then echo "ok    $1"; else echo "FAIL  $1 ($2)"; fail=1; fi
}
check "console (local)"  http://127.0.0.1:8787/api/health
check "github app (local)" http://127.0.0.1:8080/health
site="$(sed -n 's/^POC_PUBLIC_URL=//p' /etc/proof-of-change/env 2>/dev/null | head -1)"
if [ -n "$site" ]; then check "console (public HTTPS)" "$site/api/health"; else echo "skip  public check (POC_PUBLIC_URL empty or env not readable; run with sudo)"; fi
for u in proof-of-change-console proof-of-change-app caddy; do
  if systemctl is-active --quiet "$u"; then echo "ok    $u running"; else echo "FAIL  $u not running"; fail=1; fi
done
exit $fail
