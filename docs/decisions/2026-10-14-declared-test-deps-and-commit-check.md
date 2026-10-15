# Install what a project declares for its tests, and check we installed the right commit

## What changed

1. **Declared test packages.** Before running a project's tests, we now also install, on both the old and the new
   side, the test packages the project itself lists:
   - every pytest plugin it lists (for example pytest-asyncio), except coverage, type-checking and benchmark plugins;
   - an optional package group whose name matches a folder or file of the tests we run (tests in `tests/pandas/`
     get the project's "pandas" group);
   - a listed package whose name matches the test file or folder (`test_zarr.py` gets zarr).
2. **Right-commit check.** After each side is installed, we read the install's own record of where it came from
   (`direct_url.json`). If it points at another folder, names another commit, or is missing, the case stops as
   "could not verify" and says why. The commit seen on each side is kept in the record.

## Why

On 14 Oct two clean pull requests could not be checked: one project's tests needed pandas, the other's needed
pytest-asyncio and zarr. Both projects list these packages in their own settings; we just did not install them. A
reviewer also asked, two days running, for proof that every install was the commit we meant to test.

## Trade-offs

- Runs install a few more packages, so setup takes a little longer.
- The name matching is simple. It can miss a needed package whose name matches nothing, and it can install one that
  is not needed. Both sides always get the same packages, so this cannot create a difference between them.
- A case with a missing install record now stops instead of running. That is on purpose.
