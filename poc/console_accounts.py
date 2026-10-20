"""Console accounts. Passwords are scrypt hashes. Sessions are cookies tied to a secret.

The checker, the benchmarks, and study runs do not use this module. Only the operator
console does.

Environment:
  POC_SESSION_SECRET   long random string. Required before anyone can sign in.
  POC_ACCOUNTS_DB      SQLite file. Default: ops/console-accounts.sqlite
  POC_ADMIN_EMAIL      this email is an admin. No password is stored here.
  POC_SIGNUP_DISABLED  set to 1 to refuse new accounts.
  POC_INVITE_CODE      when set, sign-up must send this code.

Promote an existing account without putting a password in the command:

  python -m poc.console_accounts promote person@example.com
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import os
import re
import secrets
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
SESSION_COOKIE = "poc_session"
SESSION_TTL_S = 14 * 24 * 3600
CSRF_TTL_S = 30 * 60
LOCK_AFTER = 5
LOCK_S = 15 * 60
_SCRYPT_N = 2**14
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_lock = threading.Lock()
_ip_hits: dict[str, list[float]] = {}

SECRET_MESSAGE = "Set POC_SESSION_SECRET to a long random value before anyone can sign in."
SIGNUP_CLOSED = "Sign-up is turned off."
INVITE_REQUIRED = "An invite code is required to create an account."
BAD_LOGIN = "Email or password is wrong."
LOCKED = "Too many sign-in attempts. Try again later."
CSRF_MESSAGE = "Refresh the page and try again."


class AuthError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


def reset_for_tests() -> None:
    _ip_hits.clear()


def db_path() -> Path:
    raw = (os.environ.get("POC_ACCOUNTS_DB") or "").strip()
    return Path(raw) if raw else REPO_ROOT / "ops" / "console-accounts.sqlite"


def session_secret() -> bytes:
    value = (os.environ.get("POC_SESSION_SECRET") or "").strip()
    if len(value) < 16:
        raise AuthError(SECRET_MESSAGE, 503)
    return value.encode("utf-8")


def _flag(name: str) -> bool:
    return (os.environ.get(name) or "").strip().lower() in {"1", "true", "yes"}


def _connect() -> sqlite3.Connection:
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=5)
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS accounts (
            id TEXT PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            password_salt TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL,
            created_at REAL NOT NULL,
            failed_attempts INTEGER NOT NULL DEFAULT 0,
            locked_until REAL NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS sessions (
            token_hash TEXT PRIMARY KEY,
            account_id TEXT NOT NULL,
            csrf TEXT NOT NULL,
            created_at REAL NOT NULL,
            expires_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS csrf_tokens (
            token_hash TEXT PRIMARY KEY,
            expires_at REAL NOT NULL
        );
        """
    )
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return conn


def _hash_password(password: str, salt: bytes | None = None) -> tuple[str, str]:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=_SCRYPT_N, r=8, p=1, dklen=32)
    return salt.hex(), digest.hex()


def _password_ok(password: str, salt_hex: str, expected_hex: str) -> bool:
    digest = hashlib.scrypt(password.encode("utf-8"), salt=bytes.fromhex(salt_hex), n=_SCRYPT_N, r=8, p=1, dklen=32)
    return hmac.compare_digest(digest.hex(), expected_hex)


def _burn(password: str) -> None:
    _hash_password(password or "missing", b"\x11" * 16)


def _token_hash(token: str) -> str:
    return hmac.new(session_secret(), token.encode("utf-8"), hashlib.sha256).hexdigest()


def _eq(a: str, b: str) -> bool:
    left = hashlib.sha256(a.encode("utf-8")).digest()
    right = hashlib.sha256(b.encode("utf-8")).digest()
    return hmac.compare_digest(left, right)


def _email(value: str) -> str:
    text = (value or "").strip().lower()
    if not _EMAIL_RE.match(text) or len(text) > 200:
        raise AuthError("Enter a valid email address.")
    return text


def _password(value: str) -> str:
    if not isinstance(value, str) or len(value) < 8 or len(value) > 128:
        raise AuthError("Use a password of at least 8 characters.")
    return value


def _role_for(email: str, stored: str | None = None) -> str:
    """An admin stays an admin. The env email is promoted the next time they sign in."""
    admin = (os.environ.get("POC_ADMIN_EMAIL") or "").strip().lower()
    if stored == "admin" or (admin and email == admin):
        return "admin"
    return "user"


def _public(row: sqlite3.Row, csrf: str | None = None) -> dict[str, Any]:
    out = {"id": row["id"], "email": row["email"], "role": row["role"]}
    if csrf:
        out["csrf"] = csrf
    return out


def _note_ip(ip: str, now: float) -> None:
    """Count failed sign-ins from one address. Successful sign-ins do not count."""
    hits = [item for item in _ip_hits.get(ip, []) if now - item < 600]
    hits.append(now)
    _ip_hits[ip] = hits
    if len(hits) > 60:
        raise AuthError(LOCKED, 429)


def issue_csrf(now: float | None = None) -> str:
    """Anonymous token for the sign-in forms. It is not a session."""
    session_secret()
    now = time.time() if now is None else now
    token = secrets.token_urlsafe(32)
    with _lock:
        conn = _connect()
        try:
            conn.execute("DELETE FROM csrf_tokens WHERE expires_at < ?", (now,))
            conn.execute(
                "INSERT INTO csrf_tokens (token_hash, expires_at) VALUES (?, ?)",
                (hashlib.sha256(token.encode()).hexdigest(), now + CSRF_TTL_S),
            )
            conn.commit()
        finally:
            conn.close()
    return token


def _csrf_ok(token: str, now: float) -> bool:
    if not token:
        return False
    digest = hashlib.sha256(token.encode()).hexdigest()
    with _lock:
        conn = _connect()
        try:
            row = conn.execute(
                "SELECT expires_at FROM csrf_tokens WHERE token_hash = ?", (digest,)
            ).fetchone()
            return bool(row and float(row["expires_at"]) >= now)
        finally:
            conn.close()


def signup(email: str, password: str, invite: str, csrf: str, *, now: float | None = None) -> dict[str, Any]:
    now = time.time() if now is None else now
    if not _csrf_ok(csrf, now):
        raise AuthError(CSRF_MESSAGE, 403)
    if _flag("POC_SIGNUP_DISABLED"):
        raise AuthError(SIGNUP_CLOSED, 403)
    expected = (os.environ.get("POC_INVITE_CODE") or "").strip()
    if expected and not _eq(invite or "", expected):
        raise AuthError(INVITE_REQUIRED, 403)
    email = _email(email)
    password = _password(password)
    salt, digest = _hash_password(password)
    account_id = secrets.token_hex(16)
    with _lock:
        conn = _connect()
        try:
            exists = conn.execute("SELECT id FROM accounts WHERE email = ?", (email,)).fetchone()
            if exists:
                raise AuthError("An account with that email already exists.", 409)
            conn.execute(
                """INSERT INTO accounts
                   (id, email, password_salt, password_hash, role, created_at, failed_attempts, locked_until)
                   VALUES (?, ?, ?, ?, ?, ?, 0, 0)""",
                (account_id, email, salt, digest, _role_for(email, None), now),
            )
            conn.commit()
            row = conn.execute("SELECT * FROM accounts WHERE id = ?", (account_id,)).fetchone()
        finally:
            conn.close()
    token, session_csrf = _new_session(row["id"], now)
    return {"account": _public(row, session_csrf), "session": token}


def login(email: str, password: str, csrf: str, *, ip: str = "", now: float | None = None) -> dict[str, Any]:
    now = time.time() if now is None else now
    if not _csrf_ok(csrf, now):
        raise AuthError(CSRF_MESSAGE, 403)
    email_text = (email or "").strip().lower()
    password = password if isinstance(password, str) else ""
    failed = False
    locked_out = False
    with _lock:
        conn = _connect()
        try:
            row = conn.execute("SELECT * FROM accounts WHERE email = ?", (email_text,)).fetchone()
            if row is None:
                _burn(password)
                failed = True
            elif float(row["locked_until"] or 0) > now:
                locked_out = True
            elif not _password_ok(password, row["password_salt"], row["password_hash"]):
                attempts = int(row["failed_attempts"] or 0) + 1
                locked = now + LOCK_S if attempts >= LOCK_AFTER else 0
                conn.execute(
                    "UPDATE accounts SET failed_attempts = ?, locked_until = ? WHERE id = ?",
                    (attempts, locked, row["id"]),
                )
                conn.commit()
                failed = True
                locked_out = bool(locked)
            else:
                role = _role_for(row["email"], row["role"])
                conn.execute(
                    "UPDATE accounts SET failed_attempts = 0, locked_until = 0, role = ? WHERE id = ?",
                    (role, row["id"]),
                )
                conn.commit()
                row = conn.execute("SELECT * FROM accounts WHERE id = ?", (row["id"],)).fetchone()
        finally:
            conn.close()
    if locked_out and not failed:
        raise AuthError(LOCKED, 429)
    if failed:
        _note_ip(ip or "local", now)
        if locked_out:
            raise AuthError(LOCKED, 429)
        raise AuthError(BAD_LOGIN, 401)
    token, session_csrf = _new_session(row["id"], now)
    return {"account": _public(row, session_csrf), "session": token}


def _new_session(account_id: str, now: float) -> tuple[str, str]:
    token = secrets.token_urlsafe(32)
    csrf = secrets.token_urlsafe(32)
    with _lock:
        conn = _connect()
        try:
            conn.execute(
                "INSERT INTO sessions (token_hash, account_id, csrf, created_at, expires_at) VALUES (?, ?, ?, ?, ?)",
                (_token_hash(token), account_id, csrf, now, now + SESSION_TTL_S),
            )
            conn.commit()
        finally:
            conn.close()
    return token, csrf


def logout(token: str | None) -> None:
    if not token:
        return
    try:
        digest = _token_hash(token)
    except AuthError:
        return
    with _lock:
        conn = _connect()
        try:
            conn.execute("DELETE FROM sessions WHERE token_hash = ?", (digest,))
            conn.commit()
        finally:
            conn.close()


def account_for_session(token: str | None, *, now: float | None = None) -> dict[str, Any] | None:
    if not token:
        return None
    now = time.time() if now is None else now
    try:
        digest = _token_hash(token)
    except AuthError:
        return None
    with _lock:
        conn = _connect()
        try:
            row = conn.execute(
                """SELECT accounts.id, accounts.email, accounts.role, sessions.csrf, sessions.expires_at
                   FROM sessions JOIN accounts ON accounts.id = sessions.account_id
                   WHERE sessions.token_hash = ?""",
                (digest,),
            ).fetchone()
            if not row or float(row["expires_at"]) < now:
                return None
            role = _role_for(row["email"], row["role"])
            if role != row["role"]:
                conn.execute("UPDATE accounts SET role = ? WHERE id = ?", (role, row["id"]))
                conn.commit()
            return {"id": row["id"], "email": row["email"], "role": role, "csrf": row["csrf"]}
        finally:
            conn.close()


def session_csrf_ok(account: dict[str, Any] | None, header: str) -> bool:
    if not account or not header:
        return False
    return hmac.compare_digest(str(account.get("csrf") or ""), header)


def promote(email: str) -> str:
    """Mark an existing account as admin. Does not set or print a password."""
    text = _email(email)
    with _lock:
        conn = _connect()
        try:
            row = conn.execute("SELECT id FROM accounts WHERE email = ?", (text,)).fetchone()
            if not row:
                raise AuthError("No account with that email. They need to sign up first.", 404)
            conn.execute("UPDATE accounts SET role = 'admin' WHERE id = ?", (row["id"],))
            conn.commit()
        finally:
            conn.close()
    return text


def cookie_value(header: str | None, name: str) -> str | None:
    if not header:
        return None
    for part in header.split(";"):
        part = part.strip()
        if part.startswith(name + "="):
            return part.split("=", 1)[1]
    return None


def session_cookie(token: str, *, secure: bool) -> str:
    flags = f"HttpOnly; Path=/; SameSite=Lax; Max-Age={SESSION_TTL_S}"
    if secure:
        flags += "; Secure"
    return f"{SESSION_COOKIE}={token}; {flags}"


def clear_session_cookie() -> str:
    return f"{SESSION_COOKIE}=; HttpOnly; Path=/; Max-Age=0; SameSite=Lax"


def secure_cookie(proto: str | None) -> bool:
    if _flag("POC_COOKIE_SECURE"):
        return True
    return (proto or "").split(",")[0].strip().lower() == "https"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Console account tools")
    sub = parser.add_subparsers(dest="cmd", required=True)
    promote_cmd = sub.add_parser("promote", help="make an existing account an admin")
    promote_cmd.add_argument("email")
    args = parser.parse_args(argv)
    if args.cmd == "promote":
        try:
            email = promote(args.email)
        except AuthError as exc:
            print(exc)
            return 1
        print(f"{email} is now an admin.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
