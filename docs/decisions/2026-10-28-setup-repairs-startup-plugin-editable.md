# Setup repairs: failed editable build, plugin that crashes pytest at startup

Status: proposed

Follows 2026-10-27-checkout-version-and-editable-install.md. Two setup repairs found on live runs.

Both are setup repairs. They only let a check run and never raise a verdict.

- **A failed editable build stopped the whole install.** The checkpoint shell runs under `set -e`, so the
  final `pip install --no-deps -e .` stopped the install on a failed build before its fallback ran
  (markupsafe #512: `Cannot update time stamp of directory … MarkupSafe.egg-info` in pip's temporary wheel
  cache). The exit code is now caught. The build is retried once with pip's temporary folders on `/work`
  and no wheel cache. If it still fails, the checkout's own source folder is put on the path, and the
  import-origin check still confirms that the package imports from the checkout. Product checks also put
  pip's temporary folders on `/work` from the start.
- **An auto-loaded plugin crashed pytest at startup.** When pytest exits 3 with an internal error whose
  traceback is in a plugin from site-packages, and the project's own test config (`pyproject.toml`,
  `pytest.ini`, `tox.ini`, `setup.cfg`, `conftest.py`) does not name that plugin, the run is repeated once
  with that plugin turned off (`-p no:<entry point>`). The test log starts with a plain "Setup repair" line
  that names the plugin and keeps the first output (pytest #15256: pytest-asyncio's deprecation warning was
  turned into an error by pytest's own `filterwarnings = error`). A plugin the config names is never turned
  off. Nothing is per repository, and no package name is hardcoded.
- **The coverage run is a separate pytest start.** The same startup repair is applied there, with its own log,
  so the plugin that was turned off for the timed runs does not stop the coverage measurement either.
