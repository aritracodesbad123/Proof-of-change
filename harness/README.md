# harness/

Reserved for Jonathan (baseline/protocol owner):

- `br_run.py`: the runner. One (upstream, old, new, dependent) tuple to one observation record.
- `PROTOCOL.md`: the shared test procedure.

Owned by Nathan:

- `run.py`: wrapper that enforces the single-thread environment and 3 alternating runs per side, adds
  `machine_type` / `thread_env` to every record, and validates the record schema before accepting it.
- `machine.py`: machine-type detection (GitHub Actions runner or local box).

Until `harness/br_run.py` lands in this repo, `run.py` finds the runner through `$BR_RUNNER`.
