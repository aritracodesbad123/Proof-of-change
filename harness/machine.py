"""Detect the machine type a run executed on (Jonathan's constraint: recorded in every record)."""
from __future__ import annotations

import os
import platform


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
        "label": e.get("BR_MACHINE") or ("github-actions" if in_ci else "box"),
    }


if __name__ == "__main__":
    import json
    print(json.dumps(detect_machine_type(), indent=1))
