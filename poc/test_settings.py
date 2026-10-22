"""The project's own test settings, so behavioural probes run the way the project's pytest runs do.

Read as files only (nothing from the project is imported or run here):

* the first pytest config file pytest itself would use: pytest.ini, pyproject.toml [tool.pytest.ini_options]
  (or [tool.pytest]), tox.ini [pytest], setup.cfg [tool:pytest];
* from it: pytest-env ``env`` entries (``KEY=VALUE``, with the ``D:`` default-only and ``R:`` raw prefixes),
  the pytest-django ``DJANGO_SETTINGS_MODULE`` key or ``--ds`` in ``addopts``, and ``pythonpath`` entries;
* plain literal environment assignments at the top level of the root conftest.py
  (``os.environ["K"] = "V"`` and ``os.environ.setdefault("K", "V")``).

Nothing is specific to one repository.
"""
from __future__ import annotations

import ast
import configparser
import os
import re
import shlex
from pathlib import Path

try:   # Python 3.11+
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    tomllib = None

_KEY = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_VAR = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}|\$([A-Za-z_][A-Za-z0-9_]*)")
# Never let a project's test config steer how our runner or the sandbox behaves.
_BLOCKED = {"PATH", "HOME", "PYTHONHOME", "PYTHONSTARTUP", "LD_PRELOAD", "LD_LIBRARY_PATH", "PYTHONPATH",
            "TMPDIR", "SHELL", "USER"}


def _lines(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [str(v).strip() for v in value if str(v).strip()]
    return [ln.strip() for ln in str(value).splitlines() if ln.strip() and not ln.strip().startswith("#")]


def _ini(path: Path, section: str) -> dict | None:
    cp = configparser.ConfigParser(interpolation=None, strict=False)
    try:
        cp.read(path, encoding="utf-8")
    except (configparser.Error, OSError, UnicodeDecodeError):
        return None
    if not cp.has_section(section):
        return None
    return {k.lower() if k.lower() != "django_settings_module" else "DJANGO_SETTINGS_MODULE": v
            for k, v in cp.items(section)}


def _toml(path: Path) -> dict | None:
    if tomllib is None:
        return None
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeDecodeError):
        return None
    tool = (data.get("tool") or {}).get("pytest")
    if not isinstance(tool, dict):
        return None
    opts = tool.get("ini_options") if isinstance(tool.get("ini_options"), dict) else tool
    return {("DJANGO_SETTINGS_MODULE" if str(k).lower() == "django_settings_module" else str(k).lower()): v
            for k, v in opts.items()}


def pytest_config(checkout: Path) -> tuple[str | None, dict]:
    """(file name, options) of the config pytest would pick at the checkout root, or (None, {})."""
    root = Path(checkout)
    for name, read in (("pytest.ini", lambda p: _ini(p, "pytest")),
                       ("pyproject.toml", _toml),
                       ("tox.ini", lambda p: _ini(p, "pytest")),
                       ("setup.cfg", lambda p: _ini(p, "tool:pytest"))):
        p = root / name
        if p.is_file():
            got = read(p)
            if got is not None:
                return name, got
    return None, {}


def _expand(value: str, env: dict) -> str:
    return _VAR.sub(lambda m: env.get(m.group(1) or m.group(2), ""), value)


def _env_entries(opts: dict) -> list[tuple[str, str, bool, bool]]:
    """pytest-env entries as (key, value, default_only, raw)."""
    out = []
    for line in _lines(opts.get("env")):
        default_only = raw = False
        while len(line) > 2 and line[1] == ":" and line[0] in "DRdr":
            if line[0] in "Dd":
                default_only = True
            else:
                raw = True
            line = line[2:]
        if "=" not in line:
            continue
        key, value = (s.strip() for s in line.split("=", 1))
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
            value = value[1:-1]
        if _KEY.match(key):
            out.append((key, value, default_only, raw))
    return out


def _ds_from_addopts(addopts) -> str | None:
    text = " ".join(_lines(addopts)) if not isinstance(addopts, str) else addopts
    try:
        parts = shlex.split(text)
    except ValueError:
        parts = text.split()
    for i, part in enumerate(parts):
        if part.startswith("--ds="):
            return part.split("=", 1)[1]
        if part == "--ds" and i + 1 < len(parts):
            return parts[i + 1]
    return None


def conftest_env(checkout: Path) -> dict:
    """Literal top-level os.environ assignments in the root conftest.py (static read, nothing is executed)."""
    path = Path(checkout) / "conftest.py"
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, ValueError, UnicodeDecodeError):
        return {}

    def is_environ(node) -> bool:
        return (isinstance(node, ast.Attribute) and node.attr == "environ"
                and isinstance(node.value, ast.Name) and node.value.id == "os")

    def lit(node):
        return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None

    got: dict = {}
    for stmt in tree.body:
        if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1:
            t = stmt.targets[0]
            if isinstance(t, ast.Subscript) and is_environ(t.value):
                k, v = lit(t.slice), lit(stmt.value)
                if k and v is not None and _KEY.match(k):
                    got[k] = v
        elif isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
            f = stmt.value.func
            args = stmt.value.args
            if (isinstance(f, ast.Attribute) and f.attr == "setdefault" and is_environ(f.value) and len(args) == 2):
                k, v = lit(args[0]), lit(args[1])
                if k and v is not None and _KEY.match(k):
                    got.setdefault(k, v)
    return got


def project_test_env(checkout: Path | None, base: dict | None = None) -> dict:
    """{"env": {...}, "pythonpath": [abs paths], "source": [...]} to add to a probe's environment.

    base is the environment the probe would get anyway; D: entries do not override a key already in it.
    """
    out: dict = {"env": {}, "pythonpath": [], "source": []}
    if checkout is None or not Path(checkout).is_dir():
        return out
    root = Path(checkout)
    seen = dict(base or {})
    name, opts = pytest_config(root)
    if name:
        for key, value, default_only, raw in _env_entries(opts):
            if key in _BLOCKED or (default_only and key in seen):
                continue
            value = value if raw else _expand(value, seen)
            out["env"][key] = seen[key] = value
        ds = opts.get("DJANGO_SETTINGS_MODULE") or _ds_from_addopts(opts.get("addopts") or "")
        if isinstance(ds, str) and ds.strip() and "DJANGO_SETTINGS_MODULE" not in out["env"]:
            out["env"]["DJANGO_SETTINGS_MODULE"] = ds.strip()
        pp = opts.get("pythonpath")
        entries = pp if isinstance(pp, list) else (str(pp).split() if pp else [])
        for e in entries:
            p = (root / str(e)).resolve()
            if p.is_dir() and (p == root.resolve() or root.resolve() in p.parents):
                out["pythonpath"].append(str(p))
        out["source"].append(name)
    from_conftest = {k: v for k, v in conftest_env(root).items() if k not in _BLOCKED and k not in out["env"]}
    if from_conftest:
        out["env"].update(from_conftest)
        out["source"].append("conftest.py")
    return out


def apply(env: dict, checkout: Path | None) -> dict:
    """A copy of env with the project's test settings added (PYTHONPATH gets the config's pythonpath entries)."""
    got = project_test_env(checkout, env)
    new = dict(env)
    new.update(got["env"])
    if got["pythonpath"]:
        new["PYTHONPATH"] = os.pathsep.join(got["pythonpath"] + ([env["PYTHONPATH"]] if env.get("PYTHONPATH") else []))
    return new


def shell_exports(checkout: Path | None) -> str:
    """`export K=V` lines (for a remote run where the checkout lives at the same relative layout)."""
    got = project_test_env(checkout)
    return "".join(f"export {k}={shlex.quote(v)}\n" for k, v in got["env"].items())
