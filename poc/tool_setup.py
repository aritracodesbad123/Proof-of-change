"""Make sure the tools Proof-of-Change shells out to are present before a check starts.

The list comes from Proof-of-Change's own declared requirements (pyproject.toml [project] dependencies), never from
version strings written here. Anything missing is installed with one pip call, retried up to 3 times; then a
plain-words error. What was installed is recorded so the report can say it in plain words.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import sysconfig
import time
from importlib import metadata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RETRIES = 3
SYSTEM_TOOLS = ("git",)  # not pip-installable; checked only

_last: dict | None = None


class ToolSetupError(RuntimeError):
    pass


def declared_requirements(pyproject: Path = ROOT / "pyproject.toml") -> list[str]:
    try:
        import tomllib
        return list(tomllib.loads(pyproject.read_text()).get("project", {}).get("dependencies", []))
    except (OSError, ValueError):
        return []


def allowlist() -> list[str]:
    """Our own tools, exactly pinned (name==version), from our own pyproject. Nothing else is ever installed."""
    return [r.strip() for r in declared_requirements() if re.fullmatch(r"[A-Za-z0-9_.-]+==[^\s;,]+", r.strip())]


def _name(req: str) -> str:
    return re.split(r"[\s<>=!~;\[]", req.strip(), maxsplit=1)[0]


def _pin(req: str) -> str | None:
    m = re.search(r"==\s*([^\s;,]+)", req)
    return m.group(1) if m else None


def _add_script_dirs() -> None:
    dirs = [sysconfig.get_path("scripts"), str(Path.home() / ".local" / "bin")]
    try:
        dirs.insert(1, sysconfig.get_path("scripts", f"{os.name}_user"))
    except KeyError:
        pass
    path = os.environ.get("PATH", "").split(os.pathsep)
    for d in dirs:
        if d and d not in path:
            path.append(d)
    os.environ["PATH"] = os.pathsep.join(path)


def _satisfied(req: str) -> bool:
    name = _name(req)
    try:
        have = metadata.version(name)
    except metadata.PackageNotFoundError:
        # not installed as a Python package here, but its command is already on this machine (a system uv): use it
        return _which(name) is not None
    pin = _pin(req)
    if pin and have != pin:
        return False
    # a requirement that ships a command of the same name (uv) must also be runnable
    return _which(name) is not None or not _ships_command(name)


def _ships_command(name: str) -> bool:
    try:
        files = metadata.distribution(name).files or []
    except metadata.PackageNotFoundError:
        return False
    return any(Path(str(f)).name == name and "bin" in str(f) for f in files)


def _which(tool: str) -> str | None:
    found = shutil.which(tool)
    if found:
        return found
    if tool == "uv":  # the uv wheel also tells where its binary is, even when the scripts dir is not on PATH
        try:
            from uv import find_uv_bin  # type: ignore
            return find_uv_bin()
        except Exception:
            return None
    return None


def _pip_install(reqs: list[str]) -> subprocess.CompletedProcess:
    cmd = [sys.executable, "-m", "pip", "install", "-q", "--disable-pip-version-check", *reqs]
    return subprocess.run(cmd, capture_output=True, text=True)


def ensure_tools(requirements: list[str] | None = None, retries: int = RETRIES, installer=None,
                 sleep=time.sleep, log=print) -> dict:
    """Install every missing declared requirement in one pip call (up to `retries` tries). Returns
    {"installed": [...], "tries": n, "note": plain words}. Raises ToolSetupError in plain words on failure."""
    global _last
    allow = allowlist()
    reqs = list(allow) if requirements is None else list(requirements)
    refused = [r for r in reqs if r.strip() not in allow]
    if refused:  # never install anything a checked repo or PR asks for: only our own pinned tools
        log(f"Tool setup: refused {', '.join(refused)}: not one of Proof-of-Change's own pinned tools")
        reqs = [r for r in reqs if r.strip() in allow]
    installer = installer or _pip_install
    _add_script_dirs()
    missing = [r for r in reqs if not _satisfied(r)]
    tries, detail = 0, ""
    while missing and tries < retries:
        tries += 1
        log(f"Tool setup: installing missing {', '.join(missing)} (try {tries} of {retries})")
        p = installer(missing)
        detail = ((p.stderr or "") + (p.stdout or "")).strip()[-400:]
        importlib_invalidate()
        _add_script_dirs()
        still = [r for r in missing if not _satisfied(r)]
        if not still:
            break
        if tries < retries:
            sleep(2 * tries)
    still = [r for r in reqs if not _satisfied(r)]
    if still:
        raise ToolSetupError(
            f"Proof-of-Change needs {', '.join(still)} and could not install it after {tries} tries. "
            f"Check this machine's internet connection, then run: {Path(sys.executable).name} -m pip install "
            f"{' '.join(still)}" + (f"\nLast installer output: {detail}" if detail else ""))
    no_sys = [t for t in SYSTEM_TOOLS if shutil.which(t) is None]
    if no_sys:
        raise ToolSetupError(f"Proof-of-Change needs {', '.join(no_sys)}, which is not installed on this machine. "
                             "Install it with the system package manager and start again.")
    installed = [r for r in missing]
    note = (f"Installed missing tools before starting: {', '.join(installed)}." if installed
            else "All required tools were already installed.")
    _last = {"installed": installed, "tries": tries, "note": note, "refused": refused}
    if installed:
        log(f"Tool setup: {note}")
    return dict(_last)


def importlib_invalidate() -> None:
    import importlib
    importlib.invalidate_caches()


def last_result() -> dict | None:
    return dict(_last) if _last else None


def uv_bin() -> str:
    """The one place every uv call gets its path from. Installs it from the declared requirements if missing."""
    # Prefer the bare name when it is on PATH: sandboxed commands resolve it inside the sandbox's own view.
    if shutil.which("uv"):
        return "uv"
    found = _which("uv")
    if found:
        return found
    ensure_tools()
    if shutil.which("uv"):
        return "uv"
    found = _which("uv")
    if not found:
        raise ToolSetupError("Proof-of-Change could not find uv even after installing it. "
                             f"Run: {Path(sys.executable).name} -m pip install -e . and start again.")
    return found
