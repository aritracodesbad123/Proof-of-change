"""The project's own pytest ``addopts``, minus the flags our test command sets itself.

A product check keeps the project's pytest settings (for example a plugin loaded with ``-p``). Our command also sets
reporting, worker, timeout and coverage flags. When the project's addopts set the same flags, pytest would apply
both, so we pass the project's addopts back with only those flags removed (``-o addopts=<filtered>``).

The filter works by flag name, the same for every project. Both ``--flag value`` and ``--flag=value`` are handled,
as are joined short forms such as ``-n4``, ``-rfE`` and ``-vv``.
"""
from __future__ import annotations

import configparser
import shlex
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python < 3.11
    tomllib = None  # type: ignore[assignment]

# Long flags our command sets, with whether they take a value. "optional" means pytest-cov style nargs="?":
# the next word is the value only when it does not start with "-".
_LONG = {
    "--numprocesses": "value", "--maxprocesses": "value", "--dist": "value",
    "--junitxml": "value", "--junit-xml": "value", "--junit-prefix": "value",
    "--quiet": "none", "--verbose": "none", "--verbosity": "value",
    "--tb": "value", "--color": "value", "--timeout": "value", "--timeout-method": "value",
    "--cov": "optional", "--cov-report": "value", "--cov-config": "value", "--cov-fail-under": "value",
    "--cov-context": "value", "--cov-branch": "none", "--cov-append": "none", "--cov-reset": "none",
    "--no-cov": "none", "--no-cov-on-fail": "none",
}
_LONG_PREFIXES = ("--cov",)          # any other --cov* flag pytest-cov adds: --cov-xyz=value or a bare flag
_SHORT_VALUE = {"-n", "-r"}          # short flags that take a value, joined (-n4) or separate (-n 4)
_SHORT_COUNT = {"-q", "-v"}          # short flags that may repeat (-qq, -vv)
_INI_KEYS = {"junit_family"}         # -o / --override-ini keys our command sets


def _ini_key(text: str) -> str:
    return text.split("=", 1)[0].strip()


def strip_overridden(tokens: list[str]) -> tuple[list[str], list[str]]:
    """Return (kept, removed) for a tokenised addopts list."""
    kept, removed = [], []
    i = 0
    while i < len(tokens):
        t = tokens[i]
        nxt = tokens[i + 1] if i + 1 < len(tokens) else None
        name, eq, _ = t.partition("=")
        if t.startswith("--"):
            kind = _LONG.get(name)
            if kind is None and name.startswith(_LONG_PREFIXES):
                kind = "none" if not eq else "value"
            if kind is not None:
                if eq or kind == "none":
                    removed.append(t); i += 1; continue
                if kind == "value" and nxt is not None:
                    removed += [t, nxt]; i += 2; continue
                if kind == "optional" and nxt is not None and not nxt.startswith("-"):
                    removed += [t, nxt]; i += 2; continue
                removed.append(t); i += 1; continue
            if name == "--override-ini":
                val = t[len("--override-ini="):] if eq else nxt
                if val is not None and _ini_key(val) in _INI_KEYS:
                    removed += [t] if eq else [t, nxt]; i += 1 if eq else 2; continue
        elif t.startswith("-") and len(t) >= 2:
            head = t[:2]
            if head == "-o":
                val = t[2:] or nxt
                if val is not None and _ini_key(val) in _INI_KEYS:
                    removed += [t] if t[2:] else [t, nxt]; i += 1 if t[2:] else 2; continue
            elif head in _SHORT_VALUE:
                if len(t) > 2:
                    removed.append(t); i += 1; continue
                if nxt is not None:
                    removed += [t, nxt]; i += 2; continue
                removed.append(t); i += 1; continue
            elif head in _SHORT_COUNT and set(t[1:]) == {t[1]}:
                removed.append(t); i += 1; continue
        kept.append(t)
        i += 1
    return kept, removed


def _split(value) -> list[str]:
    if isinstance(value, list):
        return [str(v) for v in value]
    return shlex.split(str(value or ""))


def _ini(path: Path, section: str):
    cp = configparser.ConfigParser(interpolation=None)
    try:
        cp.read(path, encoding="utf-8")
    except (configparser.Error, UnicodeDecodeError):
        return None
    if not cp.has_section(section):
        return None
    return cp.get(section, "addopts", fallback="")


def _toml(path: Path, keys: tuple[str, ...]):
    if tomllib is None:
        return None
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeDecodeError):
        return None
    for k in keys:
        data = data.get(k) if isinstance(data, dict) else None
    return data if isinstance(data, dict) else None


def find_addopts(root: Path | None) -> tuple[str | None, list[str]]:
    """(config file name, addopts tokens) from the project's pytest config, in pytest's own file order.

    The first file that is a pytest config wins, even with no addopts. (None, []) when there is no config."""
    if root is None:
        return None, []
    root = Path(root)
    for name in ("pytest.toml", ".pytest.toml"):
        p = root / name
        if p.is_file():
            t = _toml(p, ("pytest",))
            return name, _split((t or {}).get("addopts", ""))
    for name in ("pytest.ini", ".pytest.ini"):
        p = root / name
        if p.is_file():  # pytest.ini is the config file even without a [pytest] section
            return name, _split(_ini(p, "pytest") or "")
    p = root / "pyproject.toml"
    if p.is_file():
        native = _toml(p, ("tool", "pytest"))
        ini_opts = (native or {}).get("ini_options")
        if isinstance(ini_opts, dict):
            return "pyproject.toml", _split(ini_opts.get("addopts", ""))
        if native:
            return "pyproject.toml", _split(native.get("addopts", ""))
    for name, section in (("tox.ini", "pytest"), ("setup.cfg", "tool:pytest")):
        p = root / name
        if p.is_file():
            v = _ini(p, section)
            if v is not None:
                return name, _split(v)
    return None, []


def filtered_override(root: Path | None) -> list[str]:
    """Extra pytest arguments for a product check: [] when nothing needs removing, else ["-o", "addopts=..."]."""
    _, tokens = find_addopts(root)
    kept, removed = strip_overridden(tokens)
    if not removed:
        return []
    return ["-o", "addopts=" + shlex.join(kept)]
