# Human review: pahaz/sshtunnel#304 ("Migrate to PEP518")

Order followed: fixed test suite, then behaviour probes, then human review adding test cases, then run the tests.

1. **Fixed test suite.** The PR changes only `pyproject.toml`, `setup.py` (deleted) and `setup.cfg` (deleted). No test file maps to those files, so the project's tests could not decide anything ("no tests could be mapped to the touched files").
2. **AI behaviour probes.** The AI found no behaviour claim to test and wrote no probe (no Python module changed). Because there was no AI probe, the product's review pause (keep or drop each AI probe, add test ideas) never opened: the record shows `operator_approval: off` even though review was requested.
3. **Human review.** Kept: nothing (no AI probe existed). Dropped: nothing. Added: one hand-written probe, `reviewer-probe-installed-metadata.py.txt` (run as the PR's fixed probe file `probes/pahaz/sshtunnel/304.py`, provenance post-hoc). Why: the real risk of a packaging migration is that users install something different. The probe compares the installed package on both sides: name, version, runtime dependency, extras, console script, classifiers, summary, the importable module, and the descriptive metadata fields.
4. **Run.** Same product check, with that probe added. The file was used only for this run and is not part of the repository's `probes/` folder.

## What the added probe found

Same on both sides (the claim "what users install stays the same" holds): name `sshtunnel`, version `0.4.0`, dependency `paramiko>=2.7.2`, extras `build-sphinx`, `dev`, `test`, console script `sshtunnel=sshtunnel:_cli_main`, classifiers, summary, licence, and the module (`__version__`, `SSHTunnelForwarder`, `_cli_main`).

Different (not covered by any claim, so the verdict is NEEDS ATTENTION):

| Field | Before (setup.py) | After (pyproject.toml) |
|---|---|---|
| Download-URL | `.../sshtunnel-0.4.0.zip` (versioned) | removed (moved to an unversioned Project-URL "Download") |
| Home-page | `https://github.com/pahaz/sshtunnel` | removed (now Project-URL "Homepage") |
| Author / Author-email | `Pahaz White` / `pahaz.white@gmail.com` | Author empty, Author-email `Pahaz White <pahaz.white@gmail.com>` |
| Platform | `macos, unix, windows` | removed |
| Keywords | space separated | comma separated |
| Requires-Python | not set | `>=2.7` (new) |

These are metadata details, not code behaviour. One deserves a maintainer's eye: the PR now declares `Requires-Python >=2.7` and still lists Python 2.7 to 3.8 classifiers, but a `[project]` table needs setuptools 61 or newer, which cannot run on Python 2. Also, `[tool.bdist_wheel] universal = true` in `pyproject.toml` is not a setting setuptools reads, so the old `universal=1` wheel tag from `setup.cfg` is probably lost (not measured here).

**Verdict after review: NEEDS ATTENTION.** The tests still could not run against this change; the attention flag comes from the metadata differences above.
