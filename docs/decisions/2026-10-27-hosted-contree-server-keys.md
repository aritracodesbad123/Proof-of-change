# A hosted console takes Contree keys only from server settings, and every check is charged to the caps

## What changed

On a hosted console (`POC_HOSTED=1`, Render or a Space, and never a single-user Codespace), Contree reads
`NEBIUS_API_KEY` and `NEBIUS_PROJECT_ID` only from the private server settings. A Nebius project ID typed
into the start form is not stored. A hosted console stores no typed key of any kind (Nebius or Tavily)
and never uses one.

Decision: on a hosted console, model calls use the server's `NEBIUS_API_KEY` too. It is the only Nebius
key a hosted check has, and every check is charged to the caps below.
If the server settings are missing, the check refuses with "Contree unavailable" and says the operator has to
set them. The message never includes the values.

Every hosted check is charged to the caps before it starts:
- The hosted console refuses to start checks unless `POC_TAVILY_CREDIT_CAP` is set. The check enforces the
  credit cap itself, before its first Tavily call.
- Each started check counts against `POC_DAILY_CAP` (default 5) for the current India day. When the count
  reaches the cap, the console refuses with "Daily check limit reached".

The values never appear in output. They are added to the redaction list for the check, the console log
writer removes them, and no refusal message contains them.

`daily_run` now refuses outright, before any work, when `--require-contree` and `--unsafe-no-sandbox` are
both passed.

## Why

The hosted deploy keeps its keys as private server settings, with a daily cap and a per-check limit.
Reading Contree keys from user input on a hosted console would let anyone choose which account runs the
pull-request code. Charging every check to the caps keeps the server's account within budget. Passing
both sandbox flags is contradictory, so it stops instead of guessing.

## Not changed

A local console still uses only the values typed into its session. The command line and the daily study
are unchanged.

## Limitations

The daily counter is a file on the console's own disk, guarded by a lock inside one process. That is
correct for a single hosted machine running one console process. With several processes or machines
behind one address, each would count on its own and the real total could go over `POC_DAILY_CAP`. That
setup would need a shared counter.
