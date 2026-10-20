# A probe that cannot import its target is not adequate

## What changed

A probe that cannot import its target on both sides is not adequate. It cannot support verified, and the difference between two import errors does not become needs attention.

## Why

Failing to import is not an observation of the function. Two different import errors, or an import error written with extra detail, used to look like a real difference or like a probe that had run.

## Decision

If every observation is an import failure on both sides (ImportError or ModuleNotFoundError, including a short message that says it cannot import), mark the probe uninformative and do not count its coverage. One side importing and the other not is still a real difference. One observation that returned a value is not this case.

## Alternatives and tradeoffs

- Count the probe as ran. It would support verified without ever calling the function.
- Treat a one-sided import error the same way. That would hide a change that broke the import.

## What it means for you

A probe that cannot import its target on either side does not count. A probe that imports on one side only is still reported as a difference.
