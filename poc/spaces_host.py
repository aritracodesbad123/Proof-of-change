"""Host rules for the operator console when no sandbox can start.

A container often cannot start bubblewrap (no unprivileged user namespaces).
Pull-request code must not run in that case: an unsandboxed process could see secret
keys and the network. The one exception is a playback of the pre-vetted sample
(rasbt/mlxtend#1229). That playback does not clone, install, or execute the pull request,
and it runs on any host, not only a Hugging Face Space.
"""
from __future__ import annotations

import os
import time
from typing import Any, Callable

VETTED_REPO = "rasbt/mlxtend"
VETTED_PR = 1229
VETTED_URL = "https://github.com/rasbt/mlxtend/pull/1229"

SPACES_MESSAGE = (
    "This Space cannot start a sandbox (bubblewrap or user namespaces are unavailable). "
    "A pull request is not run here, because that would execute untrusted code without a sandbox, "
    "where it could see secret keys and the network. "
    "The prerecorded sample, mlxtend pull 1229, still plays back from the vetted fixture. "
    "That playback does not run the pull-request code."
)

PLAYBACK_MESSAGE = (
    "No sandbox is available, so this check does not run pull-request code. "
    "The prerecorded sample, mlxtend pull 1229, plays back from the vetted fixture. "
    "That playback does not run the pull-request code."
)


def on_spaces(env: os._Environ[str] | dict[str, str] | None = None) -> bool:
    env = os.environ if env is None else env
    return bool((env.get("SPACE_ID") or "").strip())


def is_vetted_sample(pr_url: str) -> bool:
    text = (pr_url or "").strip().rstrip("/")
    return text.lower() == VETTED_URL.lower()


def sandbox_open() -> tuple[bool, str]:
    """True when pull-request code can run somewhere isolated (Contree, or local bubblewrap)."""
    if (os.environ.get("NEBIUS_API_KEY") or "").strip() and (os.environ.get("NEBIUS_PROJECT_ID") or "").strip():
        try:
            import contree_sdk  # noqa: F401
        except ImportError:
            pass
        else:
            return True, "Contree sandboxes are available"
    import guardrails.sandbox as sandbox
    try:
        return sandbox.check()
    except Exception as exc:  # noqa: BLE001
        return False, f"sandbox unavailable: {type(exc).__name__}: {exc}"


def playback_only(pr_url: str, model_provider: str) -> bool:
    """Play back the vetted sample on any host when no sandbox can start.

    The playback does not clone, install, or execute pull-request code.
    """
    if model_provider != "recorded" or not is_vetted_sample(pr_url):
        return False
    ok, _why = sandbox_open()
    return not ok


def block_reason(pr_url: str, model_provider: str) -> str | None:
    """Refuse every check a Space cannot sandbox, except the vetted playback."""
    if not on_spaces():
        return None
    ok, why = sandbox_open()
    if ok:
        return None
    if playback_only(pr_url, model_provider):
        return None
    return SPACES_MESSAGE + f" ({why})"


def health_note() -> str | None:
    if not on_spaces():
        return None
    ok, why = sandbox_open()
    if ok:
        return None
    return SPACES_MESSAGE + f" ({why})"


def vetted_record() -> dict[str, Any]:
    """Display record for the playback. The verdict is the stored sample result, not a new computation."""
    return {
        "schema_version": "1",
        "record_kind": "pr_run",
        "id": "playback-rasbt-mlxtend-1229",
        "repo": VETTED_REPO,
        "library": "mlxtend",
        "verdict": "needs_attention",
        "reason": (
            "Played back from the vetted sample (mlxtend pull 1229). "
            "No pull-request code ran, and no keys or network were used. "
            "The stored sample verdict is needs_attention."
        ),
        "playback": True,
        "pr": {
            "repo": VETTED_REPO,
            "number": VETTED_PR,
            "url": VETTED_URL,
            "title": "Fix feature_importance_permutation permuting the wrong columns for feature_groups",
            "head_sha": "296459ec1712",
        },
        "tested": {"main": "vetted sample", "pr": "vetted sample"},
        "main_side": {"source": "vetted sample playback"},
        "pr_side": {"source": "vetted sample playback"},
        "per_run": [{"side": "old", "run": 1, "passed": 1}, {"side": "new", "run": 1, "passed": 1}],
        "comparison": {"status": "playback"},
        "probes": {"items": [{"id": "groups-columns", "about": "vetted sample", "observations": [{"name": "cols"}]}]},
        "behaviour_claims": [{"id": "C1", "text": "Feature groups permute their own columns."}],
        "agents": {"status": "skipped", "roles": {}},
        "model_skipped": True,
        "duration_s": {"tests": 0, "total_wall": 0},
    }


def play(emit: Callable[..., None], pause: Callable[[float], None] | None = None) -> dict[str, Any]:
    """Walk the display stages, then return the vetted record. No subprocess and no network."""
    sleep = pause or time.sleep
    steps = (
        ("fetch_pr", "loading the vetted sample"),
        ("install_main", "sample original (no install)"),
        ("install_pr", "sample change (no install)"),
        ("pytest", "before run 1/1"),
        ("pytest", "after run 1/1"),
        ("pytest", "before coverage"),
        ("probes", "vetted probe results"),
        ("verdict", "stored sample verdict"),
        ("done", "playback finished"),
    )
    for stage, detail in steps:
        emit(stage, detail=detail)
        sleep(0.05)
    return vetted_record()
