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
_ASSIGNED = re.compile(
    r"(?i)\b(NEBIUS_API_KEY|GITHUB_TOKEN|GH_TOKEN|AUTHORIZATION)\b(\s*[:=]\s*|\s+)(\S+)"
)
_BEARER = re.compile(r"(?i)\bBearer\s+\S+")


def set_key(token: str | None, key: str) -> None:
    """Remember ``key`` for ``token``. Refuses a missing session or a key that cannot be stored safely."""
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
            _keys.pop(token, None)
            return
        _keys[token] = text


def clear_key(token: str | None) -> None:
    if not token:
        return
    with _lock:
        _keys.pop(token, None)


def get_key(token: str | None) -> str | None:
    if not token:
        return None
    with _lock:
        return _keys.get(token)


def has_key(token: str | None) -> bool:
    return bool(get_key(token))


def known_secrets() -> list[str]:
    """Values currently in memory. Used only to strip them from replies."""
    with _lock:
        return [value for value in _keys.values() if value and len(value) >= _MIN_LEN]


def public_status(token: str | None) -> dict[str, bool]:
    """What the API may return. Never the key."""
    return {"nebius_key": has_key(token)}


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
