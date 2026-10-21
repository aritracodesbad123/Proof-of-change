"""Nebius key pasted into the operator console. It stays in this process only.

The key is kept against the sign-in cookie for this server process. It is not written to
disk, not put in a log line, and not returned by the API. An empty value clears it.
"""
from __future__ import annotations

import re
import threading

_MIN_LEN = 8
_MAX_LEN = 500
_lock = threading.Lock()
_keys: dict[str, str] = {}
_tavily_keys: dict[str, str] = {}
_contree_projects: dict[str, str] = {}
_ASSIGNED = re.compile(
    r"(?i)\b(NEBIUS_API_KEY|TAVILY_API_KEY|GITHUB_TOKEN|GH_TOKEN|AUTHORIZATION)\b(\s*[:=]\s*|\s+)(\S+)"
)
_BEARER = re.compile(r"(?i)\bBearer\s+\S+")


def _remember(bucket: dict[str, str], token: str | None, key: str) -> None:
    """Remember ``key`` for ``token`` in ``bucket``. An empty value clears it. Never writes disk."""
    if not token or not str(token).strip():
        raise ValueError("Sign in first.")
    text = str(key)
    if any(ch in text for ch in "\r\n\x00"):
        raise ValueError("The key was not stored.")
    text = text.strip()
    if len(text) > _MAX_LEN:
        raise ValueError("The key was not stored.")
    with _lock:
        if not text:
            bucket.pop(token, None)
            return
        bucket[token] = text


def set_key(token: str | None, key: str) -> None:
    """Remember a Nebius key for ``token``. Refuses a missing session or a key that cannot be stored safely."""
    _remember(_keys, token, key)


def set_tavily_key(token: str | None, key: str) -> None:
    """Remember a Tavily key for ``token``. Same memory-only rules as the Nebius key."""
    _remember(_tavily_keys, token, key)


def set_contree_project(token: str | None, project_id: str) -> None:
    """Remember a Contree project ID for ``token``. Memory only, like the keys."""
    _remember(_contree_projects, token, project_id)


def get_contree_project(token: str | None) -> str | None:
    if not token:
        return None
    with _lock:
        return _contree_projects.get(token)


def clear_key(token: str | None) -> None:
    if not token:
        return
    with _lock:
        _keys.pop(token, None)
        _tavily_keys.pop(token, None)
        _contree_projects.pop(token, None)


def get_key(token: str | None) -> str | None:
    if not token:
        return None
    with _lock:
        return _keys.get(token)


def get_tavily_key(token: str | None) -> str | None:
    if not token:
        return None
    with _lock:
        return _tavily_keys.get(token)


def has_key(token: str | None) -> bool:
    return bool(get_key(token))


def has_tavily_key(token: str | None) -> bool:
    return bool(get_tavily_key(token))


def known_secrets() -> list[str]:
    """Values currently in memory. Used only to strip them from replies."""
    with _lock:
        values = list(_keys.values()) + list(_tavily_keys.values()) + list(_contree_projects.values())
    return [value for value in values if value and len(value) >= _MIN_LEN]


def public_status(token: str | None) -> dict[str, bool]:
    """What the API may return. Never the key."""
    return {"nebius_key": has_key(token), "tavily_key": has_tavily_key(token),
            "contree_project": bool(get_contree_project(token))}


def scrub(text: str, secrets: list[str] | None = None) -> str:
    """Remove key values from text that might be logged, stored, or posted."""
    if not text:
        return text
    out = _BEARER.sub("Bearer [redacted]", text)
    out = _ASSIGNED.sub(lambda m: f"{m.group(1)}{m.group(2)}[redacted]", out)
    seen: set[str] = set()
    for secret in list(secrets or []) + known_secrets():
        if not secret or len(secret) < _MIN_LEN or secret in seen:
            continue
        seen.add(secret)
        out = out.replace(secret, "[redacted]")
    return out
