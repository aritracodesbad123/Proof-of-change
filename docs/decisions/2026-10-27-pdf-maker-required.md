# A product check needs the built-in PDF maker

Status: proposed

## What changed

A product check now refuses to start when the `reportlab` package cannot be imported. The message is one
plain line that says the built-in PDF maker is missing and to install the project's dependencies.
A study run, a selection-only run and a run with `--no-report` are not affected.

## Why

`reportlab` is already a declared dependency in `pyproject.toml`, and it is the fallback when Chrome hangs
or is missing. An environment without it could finish a check with no PDF. Refusing at start makes that
failure visible before any work is done, instead of after it.
