# Run Proof-of-Change on one Nebius VM

This folder puts the hosted console and the GitHub App on one small Nebius virtual machine (VM), behind HTTPS.

| Piece | What it does |
| --- | --- |
| `setup.sh` | Installs the app and everything around it. Safe to run again. |
| `env.template` | The list of server settings, all empty. Copied to `/etc/proof-of-change/env`, readable by root only. |
| `proof-of-change-console.service` | Runs one console process on `127.0.0.1:8787`. |
| `proof-of-change-app.service` | Runs the GitHub App listener on `127.0.0.1:8080`. |
| `Caddyfile.template` | HTTPS in front of both, with a free automatic certificate. |
| `sshd-hardening.conf` | SSH by key only. |
| `healthcheck.sh` | Checks that everything answers. |

The app code in `/opt/proof-of-change` belongs to root and is read-only to the services; they can write only to
`/var/lib/proof-of-change`. The service files point every folder the app writes to there (run folders,
reviewer and hosted reports, build space, the App's delivery list). Nothing listens on the internet except Caddy (ports 443 and 80) and SSH (22). The console and the App listener
answer only on the machine itself.

## The machine

Ubuntu 24.04, 2 vCPU, 8 GiB memory, 32 GiB disk, a static public IP, SSH user `poc`. About $0.08 an hour. Pull
request code never runs on this machine: it runs in Contree (Nebius sandboxes), and if Contree can't start the
check ends as "could not verify". So 2 vCPU is enough. It runs one check at a time; a second one waits.

## Steps

1. **Connect.** From your computer: `ssh -i ~/.ssh/poc_nebius poc@<static-ip>`
2. **Get the code.**
   ```
   git clone https://github.com/aritracodesbad123/Proof-of-change.git
   cd Proof-of-change
   ```
3. **(Recommended) Limit SSH to your own address.** Find your address (for example at a "what is my IP" page)
   and run `export POC_SSH_ALLOW_CIDRS="<your-ip>/32"`. You can list several, separated by spaces. Make sure your
   current address is on the list, or you will lock yourself out. If you skip this, setup prints a warning and
   leaves port 22 open to everyone, but only with the key (no passwords).
4. **Run setup.** `sudo -E bash deploy/nebius/setup.sh --ip <static-ip>`
   Your address becomes `https://<ip-with-dashes>.sslip.io`, for example `https://203-0-113-7.sslip.io`.
   (sslip.io is a free name service that points that name at your IP, so the HTTPS certificate can be issued
   without buying a domain. If you own a domain, use `--domain your.domain` instead.)
5. **Fill in the keys.** `sudo nano /etc/proof-of-change/env` and fill at least `NEBIUS_API_KEY`,
   `NEBIUS_PROJECT_ID`, `TAVILY_API_KEY` and `POC_TAVILY_CREDIT_CAP`. `POC_HOSTED=1`, `POC_REQUIRE_CONTREE=1`
   and `POC_DAILY_CAP=5` are already set. The file stays root-only (mode 600); never copy it anywhere.
6. **Restart.** `sudo systemctl restart proof-of-change-console proof-of-change-app`
7. **Check health.** `sudo bash deploy/nebius/healthcheck.sh`. Every line should say `ok`. From anywhere, the
   address `https://<site>/api/health` should answer.
8. **Connect the GitHub App (optional).** In the App's settings set the webhook URL to
   `https://<site>/webhook` and the secret to the same value as `GITHUB_WEBHOOK_SECRET`. Fill the
   `GITHUB_APP_*` settings and `POC_DEMO_REPOS`, then restart as in step 6.

## Known limits

- **The GitHub App's queue is in memory.** If the App listener restarts, checks still waiting in its queue are
  lost; ask again with a new `/prove` comment or a push.
- **A daily-cap refusal only shows in the log.** When `POC_DAILY_CAP` is reached, an App check is not run and
  nothing is posted to GitHub; see `sudo journalctl -u proof-of-change-app`.
- **Sign-up needs email (SMTP).** New accounts get a code by email, so the `SMTP_*` settings must be filled.
  Those credentials live only in the server settings file `/etc/proof-of-change/env`, never in the repository.

## Letting judges in

Sign-up is invite-only. Setup generates an invite code and stores it as `POC_INVITE_CODE` in the root-only
settings file; it is never committed. To see it on the VM: `sudo grep '^POC_INVITE_CODE=' /etc/proof-of-change/env`.
Send it to the judges privately (for example in the submission form or a direct message), never in the public
README or a public issue. They enter it once, when they create their account. Accounts are created by email code
(needs the `SMTP_*` settings) or by Google or GitHub sign-in (needs those `*_CLIENT_ID`/`*_CLIENT_SECRET`
settings). To change the code, edit the file and restart the console. After judging, set `POC_SIGNUP_DISABLED=1`
to close sign-up completely.

## Updating

`cd Proof-of-change && git pull && sudo -E bash deploy/nebius/setup.sh --ip <static-ip>`. Your settings file is
kept.

## Logs

`sudo journalctl -u proof-of-change-console -f` (or `-u proof-of-change-app`, `-u caddy`). Keys never appear in
the logs.

## Stopping the costs

Stop the VM in the Nebius console when it isn't needed, and delete it (and its static IP) after judging.
