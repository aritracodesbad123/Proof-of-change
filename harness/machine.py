"""Detect the machine type a run executed on (protocol constraint: recorded in every record)."""
from __future__ import annotations

import os
import platform
import shutil
import subprocess


def gxx_version() -> str | None:
    """First line of `g++ --version`, or None when the compiler is not on PATH.

    pandas needs this compiler to build. The value is recorded on the machine; it does not
    change a verdict.
    """
    exe = shutil.which("g++")
    if not exe:
        return None
    try:
        cp = subprocess.run([exe, "--version"], capture_output=True, text=True, timeout=5, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None
    line = ((cp.stdout or cp.stderr or "").splitlines() or [""])[0].strip()
    return line or None


def require_gxx() -> str:
    """Stop setup when g++ is missing. Return the version line when it is present."""
    version = gxx_version()
    if not version:
        raise SystemExit("g++ is not installed. pandas needs a C++ compiler to build. "
                         "Install g++ and run setup again.")
    return version


def detect_machine_type(environ: dict | None = None) -> dict:
    e = os.environ if environ is None else environ
    in_ci = e.get("GITHUB_ACTIONS") == "true"
    return {
        "arch": platform.machine() or "unknown",
        "os": platform.system() or "unknown",
        "platform": platform.platform(),
        "cpu_count": os.cpu_count(),
        "ci": "github-actions" if in_ci else None,
        "runner_name": e.get("RUNNER_NAME"),
        "runner_os": e.get("RUNNER_OS"),
        "runner_arch": e.get("RUNNER_ARCH"),
        "runner_environment": e.get("RUNNER_ENVIRONMENT"),   # github-hosted / self-hosted
        "image": (f"{e['ImageOS']} {e.get('ImageVersion', '')}".strip() if e.get("ImageOS") else None),
        "label": e.get("BR_MACHINE") or ("github-actions" if in_ci else "local"),
        "gxx": gxx_version(),
    }


if __name__ == "__main__":
    import json
    print(json.dumps(detect_machine_type(), indent=1))
