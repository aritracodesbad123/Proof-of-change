# Codespace checks run in Contree, and setup no longer fails silently

## What changed

A live test in a fresh Codespace found three problems. The console did not stay running after the start command. The console web page was not built. Bubblewrap could not create a user namespace, so the console refused to run pull-request code.

- Setup runs from `.devcontainer/post-create.sh`. It stops at the first failing step, logs to a file, installs `contree-sdk`, checks that the web page was built, and reports whether bubblewrap can start.
- `start-console.sh` builds the web page if it is missing, starts the server detached from the start command, waits for port 8787 to listen, and prints a clear result. The private-port refusal is unchanged.
- The container is not loosened. It is not privileged, and seccomp, AppArmor and capabilities stay at their defaults.
- The console already prefers Contree when it can run. It now also accepts the judge's own Nebius key and Contree project ID from Codespaces secrets (`NEBIUS_API_KEY`, `CONTREE_PROJECT_ID`) or from hidden console fields kept in memory.
- When Contree is chosen and bubblewrap cannot start, the check runs in Contree-only mode. Installs, declared test dependencies and optional test backends go into the Contree checkpoints, and tests and probes run there. Any local step that would run pull-request or package code is refused. Coverage, probe coverage, the local freeze, the installed-commit guard and the optional-module retry are not run, and the record says so.
- If a Contree checkpoint fails, the check falls back to bubblewrap only when bubblewrap can start. Otherwise it stops with a clear message.

## Why

Loosening the container's seccomp or AppArmor profile would widen what any code in it can ask of the kernel. Contree already isolates pull-request code on a separate service, and the judge pays for it with their own account. Refusing local steps keeps a check from quietly running pull-request code outside a sandbox.

## Decision

- Do not loosen the Codespace container. Run live Codespace checks in Contree with the judge's own key and project ID.
- In Contree-only mode, refuse every local step that runs pull-request or package code. Fall back to bubblewrap after a Contree failure only when bubblewrap works.
- Keys are never passed into the pull-request code's environment.
- The study stays on bubblewrap and is unchanged.
- This has not been tested in a live Codespace. A human retest decides whether more is needed.
