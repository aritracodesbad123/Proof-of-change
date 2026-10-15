# Fetch git submodules when checking out a benchmark pull request

## What changed

When the benchmark checks out the two sides of a pull request (the code before and after the change), it now also
fetches the project's git submodules on both sides, with `git submodule update --init --recursive`.

## Why

Some projects keep part of their source code in separate repositories linked as "submodules". SciPy is one: its
build stops at once with "Missing the boost submodule" if they are not there. Without this step, every SciPy case
ended as "could not verify" because of our checkout, not because of the pull request.

## Trade-offs

- Both sides fetch the submodules the same way, each at the versions its own commit records, so the comparison
  stays fair.
- For projects without submodules the step does nothing.
- Fetching submodules adds download time and needs the network during checkout (as the clone already does). If it
  fails, the case stops with a clear message instead of a confusing build error later.
