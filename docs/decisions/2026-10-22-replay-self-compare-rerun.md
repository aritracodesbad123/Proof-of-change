# Replace three published results that compared a pull request with itself

**Date:** 2026-10-22
**Status:** accepted

## What changed

Three results in `replay/` (the published results page) are replaced with new product checks. The new checks ran in Contree only (`POC_REQUIRE_CONTREE=1`, `--sandbox-backend contree`, `--product-check`) on main after the base-commit fix (#114). The new files are exported with `ops/export_replay.py` exactly as the checks returned them. The only edit is that a local folder path in each report's "make decide" line is replaced with the usual `<run>/report/<name>` placeholder. Before each check, the main and pull-request commits were confirmed to differ, and each new record's main and pull-request commits differ.

| Pull request | Old main commit | Old PR commit | Old verdict | New main commit | New PR commit | New verdict |
|---|---|---|---|---|---|---|
| bopen/elevation #89 | f94e513fa302 | f94e513fa302 | needs_attention | fd48ce75ebcd | f94e513fa302 | needs_attention |
| googlefonts/glyphsLib #1208 | 3783ef49b506 | 3783ef49b506 | could_not_verify | 0d7b5ccdaab4 | 3783ef49b506 | could_not_verify |
| optuna/optuna #6873 | 83a36def362a | 83a36def362a | could_not_verify | 0d05a967362d | 83a36def362a | could_not_verify |

All three new main commits are the merge-base of the pull request's recorded base and its head.

## Why

The old results were made on code version 0fa0016, on the local sandbox. For these merged pull requests, the main side was the pull-request head itself, so each check compared the pull request with itself. Their verdicts were not valid, even where they happened to match the new verdict. The new verdicts come from a real main-versus-pull-request comparison.

## Not changed

No other published result is touched. The verdict labels happen to be the same as before, but the reasons are different: they now describe real differences between main and the pull request. The new checks ran on code versions 2561858 (elevation, glyphsLib) and 527dff7 (optuna), because main moved between checks. Each record stores its own code version.
