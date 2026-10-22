# The dependencies-only fallback reads main's files for every not-a-package error and refuses off-index lines

**Date:** 2026-10-22
**Status:** proposed

## What changed

- Every "this is not a Python package" install failure on a product check now uses the same rule as the flat-layout fallback: the list of dependencies comes only from main's files, on both sides. The pull-request side is installed from main's plan and main's folder, and only when main itself fell back. Before this, a not-a-package error other than a flat layout read the pull request's own dependency files, so a pull request could change what was installed. A not-a-package error on the pull-request side alone does not fall back.
- Before the dependencies-only fallback installs anything, it checks the requirement files it would use, including files pulled in with `-r` or `-c`. It refuses lines that install from outside the official package index: `--index-url`, `--extra-index-url`, `-i`, `-f` / `--find-links`, `-e` / `--editable`, `git+` or any other URL (including `name @ URL`), and local paths, `.` included. When any is found, nothing is installed and the result is could not verify, with a plain reason that names the refused lines.

## Why

A dependency only the pull request adds must never be installed. A `-e .` in main's files would install main's own code into the pull-request side and hide the pull request's change. Index options and URLs fetch code from outside the official index, which the setup rules do not allow.

## Not changed

Study runs, the flat-layout behaviour from `2026-10-22-flat-layout-main-fallback.md` (apart from the off-index check), and installs that do not hit the fallback.
