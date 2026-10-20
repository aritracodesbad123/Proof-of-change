"""Console accounts: email codes, and Google / GitHub sign-in.

Password sign-in always asks for a second code by email. A provider sign-in does not:
Google or GitHub has already checked the person. Access tokens are used for that one
request and are not stored. Codes and tokens are never written to the log.

SMTP settings (all required before a password sign-in can email a code):
  POC_SMTP_HOST, POC_SMTP_PORT (default 587), POC_SMTP_USER, POC_SMTP_PASSWORD, POC_SMTP_FROM

Test-only sink (off unless set, and refused when RENDER or RENDER_SERVICE_ID is set):
  POC_OTP_TEST_SINK=1 keeps the latest code in this process for tests. It is not returned
  by the API and it is not logged.

Provider settings. A missing id or secret hides that button.
  GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET
  GITHUB_CLIENT_ID, GITHUB_CLIENT_SECRET
  POC_PUBLIC_URL  optional origin. Otherwise the request host is used.
  Callback paths to register at the provider:
    /api/auth/google/callback
    /api/auth/github/callback

New accounts can be closed with POC_SIGNUP_DISABLED=1. POC_INVITE_CODE, when set, is
required only when a new account is created.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import smtplib  # br-allow-external: console emails a one-time sign-in code
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from email.message import EmailMessage
from pathlib import Path
from typing import Any, Callable

REPO_ROOT = Path(__file__).resolve().parent.parent
CODE_TTL_S = 10 * 60
STATE_TTL_S = 10 * 60
MAX_ATTEMPTS = 5
RESEND_GAP_S = 60
RESEND_PER_HOUR = 5
SESSION_COOKIE = "poc_session"
OAUTH_COOKIE = "poc_oauth"
GOOGLE_CALLBACK_PATH = "/api/auth/google/callback"
GITHUB_CALLBACK_PATH = "/api/auth/github/callback"
GOOGLE_AUTH = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN = "https://oauth2.googleapis.com/token"
GOOGLE_CERTS = "https://www.googleapis.com/oauth2/v3/certs"
GOOGLE_ISSUERS = {"https://accounts.google.com", "accounts.google.com"}
GITHUB_AUTH = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN = "https://github.com/login/oauth/access_token"
GITHUB_USER = "https://api.github.com/user"
GITHUB_EMAILS = "https://api.github.com/user/emails"
_SCRYPT_N = 2**14
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_SHA256_DIGESTINFO = bytes.fromhex("3031300d060960864801650304020105000420")

SMTP_ADMIN_MESSAGE = (
    "Email is not set up, so sign-in is refused. An administrator needs to set "
    "SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, and SMTP_FROM "
    "(POC_SMTP_HOST, POC_SMTP_PORT, POC_SMTP_USER, POC_SMTP_PASSWORD, and POC_SMTP_FROM also work)."
)
RENDER_SINK_MESSAGE = (
    "The test-only code sink is refused on Render. Set the SMTP variables. Codes are never shown."
)
STATE_ERROR = "That sign-in attempt is not valid. Start again."
UNVERIFIED_ERROR = "The provider did not give a verified email, so sign-in was refused."
SIGNUP_CLOSED = "Sign-up is turned off. An existing account can still sign in."
INVITE_REQUIRED = "An invite code is required to create an account."


class AuthError(Exception):
    def __init__(self, message: str, status: int = 400, *, persist: bool = False):
        super().__init__(message)
        self.status = status
        self.persist = persist


class MemoryMailer:
    """Test double. Holds messages in memory. The API never reads this back to the browser."""

    def __init__(self) -> None:
        self.outbox: list[dict[str, str]] = []

    def send(self, to: str, subject: str, text: str) -> None:
        self.outbox.append({"to": to, "subject": subject, "text": text})

    def codes_for(self, to: str) -> list[str]:
        found: list[str] = []
        for msg in self.outbox:
            if msg["to"] != to:
                continue
            found.extend(re.findall(r"(?m)^(\d{6})$", msg["text"]))
        return found


class SmtpMailer:
    def __init__(self, host: str, port: int, user: str, password: str, sender: str,
                 client_factory: Callable[..., Any] | None = None):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.sender = sender
        self.client_factory = client_factory

    def send(self, to: str, subject: str, text: str) -> None:
        msg = EmailMessage()
        msg["From"] = self.sender
        msg["To"] = to
        msg["Subject"] = subject
        msg.set_content(text)
        try:
            if self.client_factory is not None:
                client = self.client_factory(self.host, self.port)
            elif self.port == 465:
                client = smtplib.SMTP_SSL(self.host, self.port, timeout=20)  # br-allow-external: console emails a one-time sign-in code
            else:
                client = smtplib.SMTP(self.host, self.port, timeout=20)  # br-allow-external: console emails a one-time sign-in code
            with client as smtp:
                if self.client_factory is None and self.port != 465:
                    smtp.starttls()
                if self.user:
                    smtp.login(self.user, self.password)
                smtp.send_message(msg)
        except AuthError:
            raise
        except Exception:
            # The message body holds the code. Do not attach this exception.
            raise AuthError("The code could not be emailed. Try again in a minute.", 502) from None


class Transport:
    def post_form(self, url: str, fields: dict[str, str], headers: dict[str, str]) -> dict[str, Any]:
        body = urllib.parse.urlencode(fields).encode()
        req = urllib.request.Request(
            url, data=body, headers=headers,
            method="POST",  # br-allow-external: OAuth code exchange for console sign-in
        )
        return _read_json(req)

    def get_json(self, url: str, headers: dict[str, str]) -> Any:
        req = urllib.request.Request(url, headers=headers)
        return _read_json(req)


def _read_json(req: urllib.request.Request) -> Any:
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:  # noqa: S310
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        # Drop the body. A provider error page must not be logged or returned.
        raise AuthError("The provider could not complete sign-in. Start again.", 502) from exc
    except AuthError:
        raise
    except Exception:
        raise AuthError("The provider could not complete sign-in. Start again.", 502) from None


def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _b64url_decode(text: str) -> bytes:
    pad = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + pad)


def _kdf(secret: str, salt: bytes) -> str:
    return hashlib.scrypt(secret.encode("utf-8"), salt=salt, n=_SCRYPT_N, r=8, p=1, dklen=32).hex()


def _eq(a: str, b: str) -> bool:
    left = hashlib.sha256(a.encode("utf-8")).digest()
    right = hashlib.sha256(b.encode("utf-8")).digest()
    return hmac.compare_digest(left, right)


def _pick(env: os._Environ[str] | dict[str, str], *names: str, default: str = "") -> str:
    for name in names:
        value = (env.get(name) or "").strip()
        if value:
            return value
    return default


def _flag(env: os._Environ[str] | dict[str, str], name: str) -> bool:
    return (env.get(name) or "").strip().lower() in {"1", "true", "yes"}


def _session_digest(token: str) -> str:
    """Hash the session cookie. A long SECRET_KEY (or POC_SESSION_SECRET) is mixed in when set."""
    raw = token.encode()
    secret = _pick(os.environ, "SECRET_KEY", "POC_SESSION_SECRET")
    if len(secret) >= 16:
        return hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
    return hashlib.sha256(raw).hexdigest()


def _smtp(env: os._Environ[str] | dict[str, str]) -> dict[str, str]:
    return {
        "host": _pick(env, "SMTP_HOST", "POC_SMTP_HOST"),
        "port": _pick(env, "SMTP_PORT", "POC_SMTP_PORT", default="587"),
        "user": _pick(env, "SMTP_USER", "POC_SMTP_USER"),
        "password": _pick(env, "SMTP_PASSWORD", "POC_SMTP_PASSWORD"),
        "sender": _pick(env, "SMTP_FROM", "POC_SMTP_FROM"),
    }


def _github(env: os._Environ[str] | dict[str, str]) -> tuple[str, str]:
    return (
        _pick(env, "GITHUB_OAUTH_CLIENT_ID", "GITHUB_CLIENT_ID"),
        _pick(env, "GITHUB_OAUTH_CLIENT_SECRET", "GITHUB_CLIENT_SECRET"),
    )


def _role(account: dict[str, Any]) -> str:
    if account.get("role") == "admin":
        return "admin"
    admin = _pick(os.environ, "POC_ADMIN_EMAIL").lower()
    if admin and str(account.get("email") or "").lower() == admin:
        return "admin"
    return "user"


def on_render(env: os._Environ[str] | dict[str, str]) -> bool:
    return bool((env.get("RENDER") or "").strip() or (env.get("RENDER_SERVICE_ID") or "").strip())


def test_sink_requested(env: os._Environ[str] | dict[str, str]) -> bool:
    return _flag(env, "POC_OTP_TEST_SINK")


def smtp_configured(env: os._Environ[str] | dict[str, str]) -> bool:
    mail = _smtp(env)
    return all(mail[key] for key in ("host", "user", "password", "sender"))


def provider_config(env: os._Environ[str] | dict[str, str] | None = None) -> dict[str, bool]:
    env = os.environ if env is None else env
    google = bool((env.get("GOOGLE_CLIENT_ID") or "").strip() and (env.get("GOOGLE_CLIENT_SECRET") or "").strip())
    github_id, github_secret = _github(env)
    github = bool(github_id and github_secret)
    return {
        "google": google,
        "github": github,
        "signup_disabled": _flag(env, "POC_SIGNUP_DISABLED"),
        "invite_required": bool((env.get("POC_INVITE_CODE") or "").strip()),
    }


def _new_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def _code_mail(code: str, purpose: str) -> tuple[str, str]:
    if purpose == "signup":
        subject = "Confirm your Proof-of-Change email"
        lead = "Use this code to confirm your email and activate the account."
    else:
        subject = "Your Proof-of-Change sign-in code"
        lead = "Use this code to finish signing in."
    text = (
        f"{lead}\n\n{code}\n\n"
        "The code expires in 10 minutes and works once. "
        "If you did not ask for it, you can ignore this email.\n"
    )
    return subject, text


def rs256_verify(message: bytes, signature: bytes, n: int, e: int) -> bool:
    """PKCS#1 v1.5 SHA-256 check. Used for Google ID tokens."""
    k = (n.bit_length() + 7) // 8
    if k < 64 or len(signature) != k:
        return False
    sig_int = int.from_bytes(signature, "big")
    if sig_int <= 0 or sig_int >= n:
        return False
    em = pow(sig_int, e, n).to_bytes(k, "big")
    digest = hashlib.sha256(message).digest()
    prefix = b"\x00\x01"
    padding = b"\xff" * (k - len(_SHA256_DIGESTINFO) - len(digest) - 3)
    expected = prefix + padding + b"\x00" + _SHA256_DIGESTINFO + digest
    if len(expected) != len(em):
        return False
    return hmac.compare_digest(em, expected)


def _jwk_int(part: str) -> int:
    return int.from_bytes(_b64url_decode(part), "big")


def verify_google_id_token(token: str, *, client_id: str, nonce: str, now: float, keys: list[dict[str, Any]]) -> dict[str, Any]:
    parts = (token or "").split(".")
    if len(parts) != 3:
        raise AuthError("Google did not confirm this sign-in.", 401)
    try:
        header = json.loads(_b64url_decode(parts[0]))
        payload = json.loads(_b64url_decode(parts[1]))
        signature = _b64url_decode(parts[2])
    except (json.JSONDecodeError, ValueError):
        raise AuthError("Google did not confirm this sign-in.", 401) from None
    if header.get("alg") != "RS256":
        raise AuthError("Google did not confirm this sign-in.", 401)
    kid = header.get("kid")
    key = next((item for item in keys if item.get("kid") == kid), None)
    if not key or "n" not in key or "e" not in key:
        raise AuthError("Google did not confirm this sign-in.", 401)
    message = f"{parts[0]}.{parts[1]}".encode()
    if not rs256_verify(message, signature, _jwk_int(key["n"]), _jwk_int(key["e"])):
        raise AuthError("Google did not confirm this sign-in.", 401)
    iss = payload.get("iss")
    if iss not in GOOGLE_ISSUERS:
        raise AuthError("Google did not confirm this sign-in.", 401)
    aud = payload.get("aud")
    audiences = aud if isinstance(aud, list) else [aud]
    if client_id not in audiences:
        raise AuthError("Google did not confirm this sign-in.", 401)
    try:
        exp = float(payload["exp"])
    except (KeyError, TypeError, ValueError):
        raise AuthError("Google did not confirm this sign-in.", 401) from None
    if now > exp + 60:
        raise AuthError("Google did not confirm this sign-in.", 401)
    if not _eq(str(payload.get("nonce") or ""), nonce):
        raise AuthError("Google did not confirm this sign-in.", 401)
    if payload.get("email_verified") is not True:
        raise AuthError(UNVERIFIED_ERROR, 401)
    email = str(payload.get("email") or "").strip().lower()
    sub = str(payload.get("sub") or "").strip()
    if not _EMAIL_RE.match(email) or not sub:
        raise AuthError(UNVERIFIED_ERROR, 401)
    return {"email": email, "sub": sub}


class Store:
    def __init__(self, path: Path):
        self.path = path
        self._lock = threading.Lock()

    def _empty(self) -> dict[str, Any]:
        return {"accounts": {}, "challenges": {}, "sessions": {}, "oauth_states": {}}

    def load(self) -> dict[str, Any]:
        if not self.path.is_file():
            return self._empty()
        try:
            data = json.loads(self.path.read_text())
        except (OSError, json.JSONDecodeError):
            return self._empty()
        for key in ("accounts", "challenges", "sessions", "oauth_states"):
            data.setdefault(key, {})
        return data

    def save(self, data: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(data))
        os.chmod(tmp, 0o600)
        os.replace(tmp, self.path)

    def update(self, fn: Callable[[dict[str, Any]], Any]) -> Any:
        with self._lock:
            data = self.load()
            try:
                result = fn(data)
            except AuthError as exc:
                # A wrong code must be remembered. A rejected sign-in that did not
                # change the store is left on disk as it was.
                if exc.persist:
                    self.save(data)
                raise
            self.save(data)
            return result


_store: Store | None = None
_sink = MemoryMailer()
_transport: Transport | None = None


def reset_for_tests() -> None:
    global _store, _transport
    _store = None
    _transport = None
    _sink.outbox.clear()


def test_sink() -> MemoryMailer:
    return _sink


def set_transport_for_tests(transport: Transport | None) -> None:
    global _transport
    _transport = transport


def get_store() -> Store:
    global _store
    path = Path(os.environ.get("POC_ACCOUNTS_FILE", str(REPO_ROOT / "ops" / "console-accounts.json")))
    if _store is None or _store.path != path:
        _store = Store(path)
    return _store


def _normalize_email(email: str) -> str:
    text = (email or "").strip().lower()
    if not _EMAIL_RE.match(text) or len(text) > 200:
        raise AuthError("Enter a valid email address.")
    return text


def _check_password(password: str) -> str:
    if not isinstance(password, str) or len(password) < 8 or len(password) > 128:
        raise AuthError("Use a password of at least 8 characters.")
    return password


class AuthService:
    def __init__(self, store: Store | None = None, *, env: dict[str, str] | None = None,
                 now: Callable[[], float] | None = None, mailer: MemoryMailer | SmtpMailer | None = None,
                 transport: Transport | None = None):
        self.store = store or get_store()
        self._env = env
        self.now = now or time.time
        self.mailer = mailer
        self.transport = transport

    def env(self) -> dict[str, str] | os._Environ[str]:
        return os.environ if self._env is None else self._env

    def _now(self) -> float:
        return float(self.now())

    def _transport(self) -> Transport:
        if self.transport is not None:
            return self.transport
        if _transport is not None:
            return _transport
        return Transport()

    def _mailer(self) -> MemoryMailer | SmtpMailer:
        if self.mailer is not None:
            return self.mailer
        return build_mailer(self.env())

    def _check_invite(self, invite: str, *, creating: bool) -> None:
        expected = (self.env().get("POC_INVITE_CODE") or "").strip()
        if not creating or not expected:
            return
        if not _eq(invite or "", expected):
            raise AuthError(INVITE_REQUIRED, 403)

    def _signup_closed(self) -> bool:
        return _flag(self.env(), "POC_SIGNUP_DISABLED")

    def signup(self, email: str, password: str, invite: str = "") -> dict[str, str]:
        email = _normalize_email(email)
        password = _check_password(password)
        if self._signup_closed():
            raise AuthError(SIGNUP_CLOSED, 403)
        self._mailer()  # refuse before creating anything when email cannot be sent

        def apply(data: dict[str, Any]) -> dict[str, str]:
            account = data["accounts"].get(email)
            creating = account is None
            if account and account.get("active"):
                raise AuthError("An account with that email already exists. Sign in instead.")
            self._check_invite(invite, creating=creating or not (account and account.get("active")))
            if account is None:
                account = _new_account(email, self._now())
                data["accounts"][email] = account
            salt = secrets.token_bytes(16)
            account["password_salt"] = salt.hex()
            account["password_hash"] = _kdf(password, salt)
            return self._send_code(data, account, "signup")

        return self.store.update(apply)

    def login(self, email: str, password: str) -> dict[str, str]:
        email_text = (email or "").strip().lower()
        self._mailer()
        password = password if isinstance(password, str) else ""

        def apply(data: dict[str, Any]) -> dict[str, str]:
            account = data["accounts"].get(email_text)
            if account is None or not account.get("password_hash"):
                _burn_password(password)
                raise AuthError("Email or password is wrong.", 401)
            salt = bytes.fromhex(account["password_salt"])
            ok = hmac.compare_digest(_kdf(password, salt), account["password_hash"])
            if not ok:
                raise AuthError("Email or password is wrong.", 401)
            if not account.get("active"):
                raise AuthError("Confirm your email with the code we sent before signing in.", 403)
            return self._send_code(data, account, "login")

        return self.store.update(apply)

    def _send_code(self, data: dict[str, Any], account: dict[str, Any], purpose: str) -> dict[str, str]:
        now = self._now()
        sends = [float(item) for item in account.get("sends") or [] if now - float(item) < 3600]
        if sends and now - sends[-1] < RESEND_GAP_S:
            raise AuthError("Wait a minute before sending another code.", 429)
        if len(sends) >= RESEND_PER_HOUR:
            raise AuthError("Too many codes were sent this hour. Try again later.", 429)
        code = _new_code()
        salt = secrets.token_bytes(16)
        challenge_id = secrets.token_urlsafe(18)
        # Drop older open codes for this account so only the latest one can succeed.
        for cid, challenge in list(data["challenges"].items()):
            if challenge.get("email") == account["email"] and not challenge.get("used"):
                data["challenges"].pop(cid, None)
        data["challenges"][challenge_id] = {
            "id": challenge_id,
            "email": account["email"],
            "purpose": purpose,
            "salt": salt.hex(),
            "code_hash": _kdf(code, salt),
            "expires_at": now + CODE_TTL_S,
            "attempts": 0,
            "voided": False,
            "used": False,
        }
        subject, text = _code_mail(code, purpose)
        self._mailer().send(account["email"], subject, text)
        sends.append(now)
        account["sends"] = sends
        return {"ok": "true", "step": "code", "challenge_id": challenge_id, "purpose": purpose}

    def resend(self, challenge_id: str) -> dict[str, str]:
        self._mailer()

        def apply(data: dict[str, Any]) -> dict[str, str]:
            challenge = data["challenges"].get(challenge_id or "")
            if not challenge:
                raise AuthError("That sign-in step has expired. Start again.", 400)
            if challenge.get("used"):
                raise AuthError("That code was already used. Start again.", 400)
            account = data["accounts"].get(challenge["email"])
            if not account:
                raise AuthError("That sign-in step has expired. Start again.", 400)
            data["challenges"].pop(challenge_id, None)
            return self._send_code(data, account, challenge.get("purpose") or "login")

        return self.store.update(apply)

    def verify(self, challenge_id: str, code: str) -> dict[str, str]:
        presented = re.sub(r"\s+", "", code or "")

        def apply(data: dict[str, Any]) -> dict[str, str]:
            challenge = data["challenges"].get(challenge_id or "")
            if not challenge:
                raise AuthError("That code is not valid.", 401)
            if challenge.get("used"):
                raise AuthError("That code was already used. Request a new one.", 401)
            if challenge.get("voided") or int(challenge.get("attempts") or 0) >= MAX_ATTEMPTS:
                challenge["voided"] = True
                raise AuthError("That code is no longer valid. Request a new one.", 401)
            if self._now() > float(challenge["expires_at"]):
                raise AuthError("That code has expired. Request a new one.", 401)
            salt = bytes.fromhex(challenge["salt"])
            candidate = presented if re.fullmatch(r"\d{6}", presented) else "000000"
            digest = _kdf(candidate, salt)
            matched = hmac.compare_digest(digest, challenge["code_hash"]) and candidate == presented
            if not matched:
                challenge["attempts"] = int(challenge.get("attempts") or 0) + 1
                if challenge["attempts"] >= MAX_ATTEMPTS:
                    challenge["voided"] = True
                    raise AuthError("That code is no longer valid. Request a new one.", 401, persist=True)
                raise AuthError("That code is not right.", 401, persist=True)
            challenge["used"] = True
            account = data["accounts"][challenge["email"]]
            if challenge.get("purpose") == "signup":
                account["active"] = True
            token = _issue_session(data, account, self._now())
            return {"ok": "true", "email": account["email"], "account_id": account["id"], "session": token}

        return self.store.update(apply)

    def logout(self, token: str | None) -> None:
        if not token:
            return
        digest = _session_digest(token)

        def apply(data: dict[str, Any]) -> None:
            data["sessions"].pop(digest, None)

        self.store.update(apply)

    def account_for_session(self, token: str | None) -> dict[str, Any] | None:
        if not token:
            return None
        digest = _session_digest(token)
        data = self.store.load()
        session = data["sessions"].get(digest)
        if not session:
            return None
        for account in data["accounts"].values():
            if account.get("id") == session.get("account_id"):
                return {"id": account["id"], "email": account["email"], "role": _role(account)}
        return None

    def oauth_start(self, provider: str, *, redirect_base: str, invite: str = "") -> dict[str, str]:
        if provider not in {"google", "github"}:
            raise AuthError("That sign-in provider is not configured.", 404)
        flags = provider_config(self.env())
        if not flags[provider]:
            raise AuthError("That sign-in provider is not configured.", 404)
        state = secrets.token_urlsafe(32)
        verifier = secrets.token_urlsafe(64)
        nonce = secrets.token_urlsafe(32)
        redirect_uri = redirect_base.rstrip("/") + (GOOGLE_CALLBACK_PATH if provider == "google" else GITHUB_CALLBACK_PATH)
        state_hash = hashlib.sha256(state.encode()).hexdigest()
        now = self._now()

        def apply(data: dict[str, Any]) -> None:
            data["oauth_states"][state_hash] = {
                "provider": provider,
                "verifier": verifier,
                "nonce": nonce,
                "invite": invite or "",
                "redirect_uri": redirect_uri,
                "expires_at": now + STATE_TTL_S,
            }

        self.store.update(apply)
        if provider == "google":
            query = {
                "client_id": self.env()["GOOGLE_CLIENT_ID"].strip(),
                "redirect_uri": redirect_uri,
                "response_type": "code",
                "scope": "openid email profile",
                "state": state,
                "nonce": nonce,
                "code_challenge": _b64url(hashlib.sha256(verifier.encode()).digest()),
                "code_challenge_method": "S256",
            }
            location = GOOGLE_AUTH + "?" + urllib.parse.urlencode(query)
        else:
            client_id, _secret = _github(self.env())
            query = {
                "client_id": client_id,
                "redirect_uri": redirect_uri,
                "scope": "user user:email",
                "state": state,
                "allow_signup": "true",
            }
            location = GITHUB_AUTH + "?" + urllib.parse.urlencode(query)
        return {"location": location, "state": state}

    def oauth_callback(self, provider: str, *, query_state: str, cookie_state: str, code: str) -> dict[str, str]:
        if not query_state or not cookie_state or not _eq(query_state, cookie_state):
            raise AuthError(STATE_ERROR, 400)
        state_hash = hashlib.sha256(query_state.encode()).hexdigest()

        def take(data: dict[str, Any]) -> dict[str, Any] | None:
            record = data["oauth_states"].pop(state_hash, None)
            return record

        record = self.store.update(take)
        if not record or record.get("provider") != provider or self._now() > float(record.get("expires_at") or 0):
            raise AuthError(STATE_ERROR, 400)
        if not code:
            raise AuthError(STATE_ERROR, 400)
        if provider == "google":
            identity = self._google_identity(code, record)
        elif provider == "github":
            identity = self._github_identity(code, record)
        else:
            raise AuthError(STATE_ERROR, 400)
        return self._finish_provider(provider, identity, record.get("invite") or "")

    def _google_identity(self, code: str, record: dict[str, Any]) -> dict[str, str]:
        env = self.env()
        fields = {
            "code": code,
            "client_id": env["GOOGLE_CLIENT_ID"].strip(),
            "client_secret": env["GOOGLE_CLIENT_SECRET"].strip(),
            "redirect_uri": record["redirect_uri"],
            "grant_type": "authorization_code",
            "code_verifier": record["verifier"],
        }
        token = self._transport().post_form(GOOGLE_TOKEN, fields, {"Accept": "application/json"})
        id_token = str(token.get("id_token") or "")
        certs = self._transport().get_json(GOOGLE_CERTS, {})
        keys = certs.get("keys") if isinstance(certs, dict) else None
        if not isinstance(keys, list):
            raise AuthError("Google did not confirm this sign-in.", 401)
        claims = verify_google_id_token(
            id_token, client_id=env["GOOGLE_CLIENT_ID"].strip(), nonce=record["nonce"], now=self._now(), keys=keys,
        )
        return {"email": claims["email"], "provider_id": claims["sub"]}

    def _github_identity(self, code: str, record: dict[str, Any]) -> dict[str, str]:
        env = self.env()
        client_id, client_secret = _github(env)
        fields = {
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": record["redirect_uri"],
        }
        token = self._transport().post_form(
            GITHUB_TOKEN, fields, {"Accept": "application/json"},
        )
        access = str(token.get("access_token") or "")
        if not access:
            raise AuthError("GitHub did not complete sign-in. Start again.", 401)
        auth = {"Authorization": f"Bearer {access}", "Accept": "application/json", "User-Agent": "proof-of-change-console"}
        user = self._transport().get_json(GITHUB_USER, auth)
        emails = self._transport().get_json(GITHUB_EMAILS, auth)
        # The token stays in this local variable and is not written to the store.
        del access
        if not isinstance(user, dict) or not isinstance(emails, list):
            raise AuthError(UNVERIFIED_ERROR, 401)
        primary = next((item for item in emails if isinstance(item, dict) and item.get("primary") is True), None)
        if not primary or primary.get("verified") is not True:
            raise AuthError(UNVERIFIED_ERROR, 401)
        email = str(primary.get("email") or "").strip().lower()
        provider_id = str(user.get("id") or "").strip()
        if not _EMAIL_RE.match(email) or not provider_id:
            raise AuthError(UNVERIFIED_ERROR, 401)
        return {"email": email, "provider_id": provider_id}

    def _finish_provider(self, provider: str, identity: dict[str, str], invite: str) -> dict[str, str]:
        email = identity["email"]
        provider_id = identity["provider_id"]

        def apply(data: dict[str, Any]) -> dict[str, str]:
            linked = _find_provider(data, provider, provider_id)
            by_email = data["accounts"].get(email)
            if linked and by_email and linked["id"] != by_email["id"]:
                raise AuthError("This provider is already linked to a different account.", 409)
            if linked:
                token = _issue_session(data, linked, self._now())
                return {"ok": "true", "email": linked["email"], "account_id": linked["id"], "session": token}
            if by_email:
                providers = by_email.setdefault("providers", {})
                current = providers.get(provider)
                if current and current != provider_id:
                    raise AuthError("This account is already linked to a different provider user.", 409)
                providers[provider] = provider_id
                by_email["active"] = True
                token = _issue_session(data, by_email, self._now())
                return {"ok": "true", "email": by_email["email"], "account_id": by_email["id"], "session": token}
            if self._signup_closed():
                raise AuthError(SIGNUP_CLOSED, 403)
            self._check_invite(invite, creating=True)
            account = _new_account(email, self._now())
            account["active"] = True
            account["providers"] = {provider: provider_id}
            data["accounts"][email] = account
            token = _issue_session(data, account, self._now())
            return {"ok": "true", "email": email, "account_id": account["id"], "session": token}

        return self.store.update(apply)


def _new_account(email: str, now: float) -> dict[str, Any]:
    return {
        "id": secrets.token_hex(16),
        "email": email,
        "active": False,
        "created_at": now,
        "sends": [],
        "providers": {},
    }


def _burn_password(password: str) -> None:
    """Spend the same password hash work when the account is missing."""
    _kdf(password or "missing", b"\x11" * 16)


def _issue_session(data: dict[str, Any], account: dict[str, Any], now: float) -> str:
    token = secrets.token_urlsafe(32)
    digest = _session_digest(token)
    data["sessions"][digest] = {"account_id": account["id"], "created_at": now}
    return token


def _find_provider(data: dict[str, Any], provider: str, provider_id: str) -> dict[str, Any] | None:
    for account in data["accounts"].values():
        providers = account.get("providers") or {}
        if providers.get(provider) == provider_id:
            return account
    return None


def build_mailer(env: os._Environ[str] | dict[str, str]) -> MemoryMailer | SmtpMailer:
    if on_render(env) and test_sink_requested(env):
        if not smtp_configured(env):
            raise AuthError(RENDER_SINK_MESSAGE, 503)
        # The sink is refused even when SMTP is also set. Mail goes through SMTP only.
    elif test_sink_requested(env):
        return _sink
    if not smtp_configured(env):
        raise AuthError(SMTP_ADMIN_MESSAGE, 503)
    mail = _smtp(env)
    try:
        port = int(mail["port"])
    except ValueError:
        raise AuthError(SMTP_ADMIN_MESSAGE, 503) from None
    return SmtpMailer(mail["host"], port, mail["user"], mail["password"], mail["sender"])


def public_base(env: dict[str, str] | os._Environ[str], host: str | None, proto: str | None) -> str:
    explicit = (env.get("POC_PUBLIC_URL") or "").strip().rstrip("/")
    if explicit:
        return explicit
    host_text = (host or "").split(",")[0].strip()
    proto_text = (proto or "http").split(",")[0].strip() or "http"
    if not host_text:
        raise AuthError("Set POC_PUBLIC_URL to the address people use to open the console.", 500)
    return f"{proto_text}://{host_text}"


def cookie_value(header: str | None, name: str) -> str | None:
    if not header:
        return None
    for part in header.split(";"):
        part = part.strip()
        if part.startswith(name + "="):
            return urllib.parse.unquote(part.split("=", 1)[1])
    return None


def _secure(env: dict[str, str] | os._Environ[str], proto: str | None) -> bool:
    if _flag(env, "POC_COOKIE_SECURE"):
        return True
    return (proto or "").split(",")[0].strip().lower() == "https"


def session_cookie(token: str, *, secure: bool) -> str:
    flags = "HttpOnly; Path=/; SameSite=Lax"
    if secure:
        flags += "; Secure"
    return f"{SESSION_COOKIE}={token}; {flags}"


def clear_cookie(name: str) -> str:
    return f"{name}=; HttpOnly; Path=/; Max-Age=0; SameSite=Lax"


def oauth_cookie(state: str, *, secure: bool) -> str:
    flags = "HttpOnly; Path=/; Max-Age=600; SameSite=Lax"
    if secure:
        flags += "; Secure"
    return f"{OAUTH_COOKIE}={state}; {flags}"


def service_from_env() -> AuthService:
    return AuthService(get_store())


def session_cookie_present(cookies: list[str]) -> bool:
    for item in cookies:
        if not item.startswith(SESSION_COOKIE + "="):
            continue
        if "Max-Age=0" in item:
            continue
        value = item.split(";", 1)[0].split("=", 1)[1]
        if value:
            return True
    return False


class HttpResult:
    def __init__(self, status: int, body: dict[str, Any] | None = None, *,
                 location: str | None = None, cookies: list[str] | None = None):
        self.status = status
        self.body = body
        self.location = location
        self.cookies = cookies or []


def _public_body(result: dict[str, str]) -> dict[str, str]:
    """Drop the session token. It travels only in the cookie."""
    return {key: value for key, value in result.items() if key not in {"session", "account_id"}}


def handle_request(method: str, path: str, query: dict[str, list[str]], body: dict[str, Any] | None,
                   headers: Any, *, host: str | None, proto: str | None) -> HttpResult:
    svc = service_from_env()
    env = svc.env()
    secure = _secure(env, proto)
    cookie_header = headers.get("Cookie") if headers is not None else None
    try:
        if method == "GET" and path == "/api/auth/providers":
            return HttpResult(200, provider_config(env))
        if method == "GET" and path == "/api/auth/me":
            account = svc.account_for_session(cookie_value(cookie_header, SESSION_COOKIE))
            if not account:
                return HttpResult(401, {"error": "Sign in first."})
            return HttpResult(200, {"email": account["email"], "id": account["id"], "role": account.get("role") or "user"})
        if method == "POST" and path == "/api/auth/logout":
            svc.logout(cookie_value(cookie_header, SESSION_COOKIE))
            return HttpResult(200, {"ok": True}, cookies=[clear_cookie(SESSION_COOKIE)])
        if method == "POST" and path == "/api/auth/signup":
            result = svc.signup(
                str((body or {}).get("email") or ""),
                str((body or {}).get("password") or ""),
                str((body or {}).get("invite_code") or ""),
            )
            return HttpResult(200, _public_body(result))
        if method == "POST" and path == "/api/auth/login":
            result = svc.login(str((body or {}).get("email") or ""), str((body or {}).get("password") or ""))
            return HttpResult(200, _public_body(result))
        if method == "POST" and path == "/api/auth/verify":
            result = svc.verify(str((body or {}).get("challenge_id") or ""), str((body or {}).get("code") or ""))
            token = result["session"]
            return HttpResult(200, _public_body(result), cookies=[session_cookie(token, secure=secure)])
        if method == "POST" and path == "/api/auth/resend":
            result = svc.resend(str((body or {}).get("challenge_id") or ""))
            return HttpResult(200, _public_body(result))
        if method == "GET" and path in {"/api/auth/google/start", "/api/auth/github/start"}:
            provider = "google" if path.endswith("/google/start") else "github"
            invite = (query.get("invite_code") or [""])[0]
            started = svc.oauth_start(provider, redirect_base=public_base(env, host, proto), invite=invite)
            return HttpResult(302, location=started["location"], cookies=[oauth_cookie(started["state"], secure=secure)])
        if method == "GET" and path in {GOOGLE_CALLBACK_PATH, GITHUB_CALLBACK_PATH}:
            provider = "google" if "google" in path else "github"
            try:
                result = svc.oauth_callback(
                    provider,
                    query_state=(query.get("state") or [""])[0],
                    cookie_state=cookie_value(cookie_header, OAUTH_COOKIE) or "",
                    code=(query.get("code") or [""])[0],
                )
            except AuthError as exc:
                location = "/?auth_error=" + urllib.parse.quote(str(exc))
                return HttpResult(302, location=location, cookies=[clear_cookie(OAUTH_COOKIE)])
            token = result["session"]
            cookies = [session_cookie(token, secure=secure), clear_cookie(OAUTH_COOKIE)]
            return HttpResult(302, location="/", cookies=cookies)
    except AuthError as exc:
        return HttpResult(exc.status, {"error": str(exc)})
    return HttpResult(404, {"error": "not found"})


def promote_account(email: str) -> None:
    """Mark an existing account as admin. Does not set or change a password."""
    key = _normalize_email(email)

    def apply(data: dict[str, Any]) -> None:
        account = data["accounts"].get(key)
        if not account:
            raise AuthError("That account does not exist.", 404)
        account["role"] = "admin"

    get_store().update(apply)


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args[:1] != ["promote"] or len(args) != 2:
        print("usage: python -m poc.console_auth promote EMAIL", file=sys.stderr)
        return 2
    try:
        promote_account(args[1])
    except AuthError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print("promoted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
