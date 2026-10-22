# Product checks fetch the Contree coverage report from a file

**Date:** 2026-10-22
**Status:** proposed

## What changed

- On a product check (`--product-check` with `--pr`), the coverage run inside Contree no longer prints the coverage report into the command output. It keeps only the changed files, compresses the report with gzip, encodes it as base64 text and writes it to a file inside the sandbox. The run prints just the file's length and its SHA-256 checksum (a fingerprint that changes if any character changes).
- The coverage run is saved as a Contree image instead of being thrown away, and the file is then read back from that image in pieces of 40,000 characters, each through its own short disposable run. The pieces are joined, the checksum is compared, and only then is the report decoded and used.
- The whole fetch has one overall deadline (the run timeout), not one per piece. Each piece gets only the time that is left. If too little time is left for the next piece, the fetch stops and coverage stays "not measured" with the reason "ran out of time after N of M pieces".
- If the file is missing, a piece cannot be read or has the wrong size, the checksum does not match, or the report cannot be decoded, coverage stays "not measured" with a plain reason that starts "the coverage report could not be fetched from Contree". A product check then stays capped at could not verify, as before.
- Study runs, bench mode and the daily study are unchanged: they still read the report from the command output.

## Why

Contree caps how much a command can print. In the 22 October rerun, two product checks ran their tests correctly, but the coverage report was larger than that cap, so it was cut off and the checks ended as could not verify with "the coverage report was cut short by the Contree output limit". The tests had passed; only the measurement was lost.

## Decision

- Move the report out of the capped output and into a file, then fetch it in pieces small enough to fit under the cap.
- Compress it first, so most reports need only one piece.
- Give the whole fetch one deadline, so up to 200 pieces can never add up to far more than the check's time limit.
- Check the length and checksum before trusting it. A report that cannot be fetched whole is never treated as measured.

## Alternatives and tradeoffs

- Compressing alone and printing inline would be simpler, but a large enough report would still hit the cap.
- A dedicated file-download call in the Contree SDK would avoid the extra runs, but reading pieces with ordinary commands works with the runner the project already uses.
- Cost: each product coverage run now keeps one saved image in Contree, and that image is not deleted afterwards (also listed in docs/LIMITATIONS.md). Each run also adds at least one short extra run. Reports are limited to 200 pieces (about 8 million characters after compression); anything bigger stays "not measured".

## What it means for you

Product checks on projects with large coverage reports can now have their coverage measured instead of ending as could not verify for that reason alone. Nothing changes for you to do.
