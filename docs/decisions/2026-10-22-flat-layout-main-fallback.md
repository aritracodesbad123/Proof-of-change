# A flat-layout project on main falls back to the dependencies main declares

**Date:** 2026-10-22
**Status:** accepted
Approved by review.

## What changed

On a product check (`--product-check`), when installing main fails because setuptools found multiple top-level packages in a flat layout, the check no longer stops at once. It installs only the dependencies main declares (`uv.lock`, the `[project]` table in `pyproject.toml`, or `requirements*.txt`) and puts the project folder on the import path. This is the same deps-only fallback already used for other "not a package" failures.

- If main declares nothing usable, the check stays unsupported with the flat-layout reason, and the verdict is could_not_verify.
- The pull-request side uses this fallback only when main did, and then with main's plan, so both sides get the same setup.
- The list of packages to install comes strictly from main's files on both sides. On the pull-request side, main's dependency files are read (read-only) and the pull request's folder is only put on the import path, so its code is what gets tested. The pull request's own dependency files are never read, so a dependency the pull request adds is not installed. Such a refused dependency never makes the check needs attention.
- A flat layout on the pull-request side alone does not fall back. It stays could not verify and never becomes needs attention.
- Study runs are unchanged.

This overrides the flat-layout part of the earlier note: the line in `2026-10-22-unsupported-installs-and-pytest-gaps.md` (the stop that skipped even the dependency-only install). The rest of that note still holds.

## Why

The earlier stop turned every flat-layout project into could not verify, including projects whose tests run fine once their declared dependencies are installed and the folder is importable. Before that stop, these projects were checked through the deps-only fallback, and the rerun set lost those results.

## Alternatives and tradeoffs

Keeping the stop is simpler but gives up checks that worked before. Letting the pull-request side fall back on its own would let a layout change made only by the pull request decide the setup, so it is not allowed. No package names or install steps are hardcoded, and no OS package is installed.

## What it means for you

A flat-layout project that declares its dependencies is tested again on both sides. One that declares nothing still ends quickly with could_not_verify and a readable reason.
