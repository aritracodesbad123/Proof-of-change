# A short Chrome readiness probe before every PDF

Status: accepted

## Problem

On some machines headless Chrome never finishes `--print-to-pdf`, even for a one-line page. Each report
then waited the full 60 s PDF limit before the built-in reportlab maker took over, which broke the speed rule.

## Root cause found

The hang is reproducible with a tiny page and every flag combination tried (`--headless=new` and old,
`--no-sandbox`, `--disable-gpu`, `--disable-dev-shm-usage`, fresh `--user-data-dir`, no D-Bus, no display,
clean environment, extensions and component updates disabled). `/dev/shm` has room and the page makes no
network fetches. Chrome's own log shows force-installed extensions running in the headless session: a
machine-wide managed policy (`ExtensionSettings` with `force_installed`) loads them, `--disable-extensions`
cannot turn them off, and with them running the headless print never exits. This is the machine's
configuration, so no generic flag or code change makes Chrome finish.

## Decision

- Before the first PDF in a process, `chrome_ready()` prints a tiny page with a 5 s limit
  (`CHROME_PROBE_TIMEOUT_S`). The result is cached per process and Chrome path.
- If the probe fails, every PDF goes straight to the built-in maker. If it passes, Chrome is used with the
  normal 60 s limit. If the real page then times out, that timeout is cached for the Chrome path too, so
  later PDFs in the same process go straight to the built-in maker instead of waiting another 60 s.
- The whole Chrome process group is killed after every run, and any process still using the temporary
  profile is killed too. Temporary-folder cleanup errors are ignored.

## Measured

Same attrs report on the affected machine: 60.2 s before; 5.2 s for the first PDF after (probe plus the
built-in maker) and 0.04 s for each later PDF in the same process.

## Tests

`tests/test_chrome_readiness_probe.py`: a fake hanging Chrome gives a PDF through the fallback well under
the 60 s limit, its helper process is killed, and a second PDF does not wait again. A working fake Chrome
is still used after the probe. A fake Chrome that passes the probe but
hangs on the real page falls back once after the (injected, short) time limit, and the next PDF does not
start Chrome at all.
