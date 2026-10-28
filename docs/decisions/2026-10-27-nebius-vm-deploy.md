# The hosted console runs on one Nebius VM behind Caddy

## What changed

`deploy/nebius/` sets up Proof-of-Change on one Ubuntu 24.04 Nebius VM (2 vCPU, 8 GiB, 32 GiB disk, static IP):
a setup script, two systemd services, a Caddy config, an sshd drop-in, a settings template and a health check.
The README links to plain-words steps.

## Why

Free Render sleeps when idle and has 512 MB of memory; Vercel cannot run a check that lasts minutes. A small
always-on VM costs about $0.08 an hour and stops costing when it is stopped or deleted. The hard work already
runs in Contree, so the VM only serves the console, receives webhooks and writes the PDF.

## How it is kept safe

- One console process (`python -m poc.console_api`) on `127.0.0.1:8787` and the App listener
  (`python -m poc.github_app`) on `127.0.0.1:8080`. Only Caddy faces the internet. Caddy passes only
  `POST /webhook` to the App; everything else goes to the console.
- Settings live in `/etc/proof-of-change/env`, owner root, mode 600. systemd reads it before it starts the
  service as the unprivileged `proof-of-change` user. Only an empty template is committed; a test checks that
  every name in it is one the code reads and that no value is committed.
- `POC_HOSTED=1`, `POC_REQUIRE_CONTREE=1` and `POC_DAILY_CAP` are preset. `POC_TAVILY_CREDIT_CAP` is left empty
  on purpose: the hosted console refuses checks until the operator sets it.
- ufw allows 443, 80 (certificate challenge and redirect to HTTPS) and 22. `POC_SSH_ALLOW_CIDRS` (read only by
  the setup script) limits 22 to listed addresses; when it is empty the script warns and leaves 22 open, rate
  limited, key only.
- SSH is key only: `PasswordAuthentication no`, `KbdInteractiveAuthentication no`, `PermitRootLogin no` in a
  drop-in that is checked with `sshd -t` before sshd reloads. If the check fails, the drop-in is removed.
- The setup installs only the app (`.[ops,contree,github]`), Caddy, git and ufw. Node is downloaded only to build
  the console page and is removed afterwards. Each pull request's packages are installed during a check inside
  Contree, never by the setup script.
- With no domain, the address is `<ip-with-dashes>.sslip.io`, so Caddy can get a Let's Encrypt certificate.

- The app code and its Python environment under `/opt/proof-of-change` belong to root; the services run with
  `ProtectSystem=strict` and can write only to `/var/lib/proof-of-change`. There are no links into the code
  folder: the service files set `POC_OPS_DIR`, `POC_OPS_RUNS`, `POC_REPORT_DIR`, `POC_HOSTED_REPORTS_DIR` and
  `POC_HEAVY_BUILD_DIR` to folders under `/var/lib/proof-of-change` (see
  `2026-10-27-data-folder-settings.md`). (An earlier version of this note said the folders were links; the
  setup script never created them.)
- Sign-up is invite-only: setup generates `POC_INVITE_CODE` into the root-only file. `POC_SIGNUP_DISABLED` is left
  empty, because setting it closes sign-up even with the code.
- The temporary Node download is checked against Node's published `SHASUMS256.txt` before it is extracted.

## Limits

- The GitHub App listener runs the check inside the webhook request. GitHub stops waiting after 10 seconds and
  marks the delivery as timed out, though the check still finishes and posts. A queue would fix this later.
- The App path uses `--require-contree` and the Tavily credit cap (inside the check), but it does not count
  toward the console's `POC_DAILY_CAP`; `POC_DEMO_REPOS` limits which repositories it acts on.
- sslip.io names share Let's Encrypt's per-domain rate limit with other users; a retry later, or a real domain,
  resolves it.
- One VM: the console's single-process lock and file-based day counter assume exactly one console process.
