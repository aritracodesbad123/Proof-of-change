"""Console accounts: email codes, provider sign-in, and per-account runs."""
from __future__ import annotations

import base64
import hashlib
import http.client
import json
import os
import threading
import time
from urllib.parse import parse_qs, unquote, urlparse

import pytest

from poc import console_api, console_auth

# Test-only RSA key. It is not a production secret.
_N = int(
    "22067375574104645780190337088660245518386630871877669682523814424637647532377699217029266772201689710336618134639004881707128982244537113381278713683897900250805863606006028398213134560480097303345624317804016703763603451296555815008175099969598438964189097241986219373772760349799999113194132298600036786744962342336094609167799698855424972141006732776307083821670949107347524661198172046112057761451513234223282802794833312778853885374079696172239631823267051476301792450650168687532284908035569187810909609536436645127198738699414334756599821396800400765709437424579439894882830788181895616238537365914670442520639"
)
_E = 65537
_D = int(
    "9323169027932259405905063528684090026028781129682238384493654511139959163529608080484533210584959420551069643422068246443197595631137614841349705720991302792230925346825425596287965214731421550935888413011222919910257322752409870513661843775397506404930799685440826329107329828119036200095758611925891001568269252800796712799740586202386203402411835488714600647507172258046392764215341951579594338394897394838521156316601979716599797341742253047819557754095223493315786500887524767727839790237897659844152424054440407505637701588429758411698779999665140708020542245280523096096235650933899885102125620055121754023825"
)
_SHA256_INFO = bytes.fromhex("3031300d060960864801650304020105000420")


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _jwk() -> dict:
    n_len = (_N.bit_length() + 7) // 8
    e_len = (_E.bit_length() + 7) // 8
    return {"kty": "RSA", "alg": "RS256", "kid": "test-key", "n": _b64(_N.to_bytes(n_len, "big")), "e": _b64(_E.to_bytes(e_len, "big"))}


def _sign(payload: dict) -> str:
    header = _b64(json.dumps({"alg": "RS256", "kid": "test-key"}, separators=(",", ":")).encode())
    body = _b64(json.dumps(payload, separators=(",", ":")).encode())
    message = f"{header}.{body}".encode()
    k = (_N.bit_length() + 7) // 8
    digest = hashlib.sha256(message).digest()
    pad = b"\xff" * (k - len(_SHA256_INFO) - len(digest) - 3)
    em = b"\x00\x01" + pad + b"\x00" + _SHA256_INFO + digest
    sig = pow(int.from_bytes(em, "big"), _D, _N).to_bytes(k, "big")
    return f"{header}.{body}.{_b64(sig)}"


class ScriptedProviders(console_auth.Transport):
    def __init__(self):
        self.google_tokens: list[str] = []
        self.github_user: dict = {"id": 4242}
        self.github_emails: list = []
        self.seen_tokens: list[str] = []

    def post_form(self, url, fields, headers):
        if "googleapis" in url:
            return {"id_token": self.google_tokens.pop(0), "access_token": "google-access-should-not-stick"}
        self.seen_tokens.append("github-access-should-not-stick")
        return {"access_token": "github-access-should-not-stick", "token_type": "bearer"}

    def get_json(self, url, headers):
        if "certs" in url:
            return {"keys": [_jwk()]}
        if url.endswith("/emails"):
            return self.github_emails
        return self.github_user


@pytest.fixture
def accounts(tmp_path, monkeypatch):
    monkeypatch.setenv("POC_ACCOUNTS_FILE", str(tmp_path / "accounts.json"))
    for key in (
        "RENDER", "RENDER_SERVICE_ID", "POC_OTP_TEST_SINK", "POC_SIGNUP_DISABLED", "POC_INVITE_CODE",
        "POC_SMTP_HOST", "POC_SMTP_PORT", "POC_SMTP_USER", "POC_SMTP_PASSWORD", "POC_SMTP_FROM",
        "GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "GITHUB_CLIENT_ID", "GITHUB_CLIENT_SECRET", "POC_PUBLIC_URL",
        "CODESPACES", "POC_SINGLE_USER",
    ):
        monkeypatch.delenv(key, raising=False)
    console_auth.reset_for_tests()
    clock = {"t": 1_700_000_000.0}
    mailer = console_auth.MemoryMailer()
    store = console_auth.Store(tmp_path / "accounts.json")
    svc = console_auth.AuthService(store, env=os.environ, now=lambda: clock["t"], mailer=mailer)
    yield svc, mailer, clock, store
    console_auth.reset_for_tests()


def _code(mailer, email):
    codes = mailer.codes_for(email)
    assert codes, "expected an emailed code"
    return codes[-1]


def test_signup_and_login_require_a_code_and_grant_no_session_early(accounts):
    svc, mailer, clock, store = accounts
    email = "ada@example.com"
    started = svc.signup(email, "correct-horse")
    assert "session" not in started
    assert store.load()["sessions"] == {}
    assert store.load()["accounts"][email]["active"] is False
    code = _code(mailer, email)
    assert code not in store.path.read_text()
    signed = svc.verify(started["challenge_id"], code)
    assert signed["session"]
    assert store.load()["accounts"][email]["active"] is True
    svc.logout(signed["session"])
    clock["t"] += 61
    again = svc.login(email, "correct-horse")
    assert "session" not in again
    assert len(store.load()["sessions"]) == 0
    login_code = _code(mailer, email)
    assert login_code != code
    done = svc.verify(again["challenge_id"], login_code)
    assert done["email"] == email
    assert svc.account_for_session(done["session"])["email"] == email


def test_wrong_expired_reused_and_locked_codes(accounts):
    svc, mailer, clock, store = accounts
    email = "ada@example.com"
    started = svc.signup(email, "correct-horse")
    code = _code(mailer, email)
    with pytest.raises(console_auth.AuthError, match="not right"):
        svc.verify(started["challenge_id"], "000000")
    assert store.load()["accounts"][email]["active"] is False
    assert store.load()["sessions"] == {}
    clock["t"] += console_auth.CODE_TTL_S + 1
    with pytest.raises(console_auth.AuthError, match="expired"):
        svc.verify(started["challenge_id"], code)
    assert store.load()["sessions"] == {}
    clock["t"] += 61
    resent = svc.resend(started["challenge_id"])
    fresh = _code(mailer, email)
    assert fresh != code
    with pytest.raises(console_auth.AuthError, match="not right"):
        svc.verify(resent["challenge_id"], code)
    first = svc.verify(resent["challenge_id"], fresh)
    with pytest.raises(console_auth.AuthError, match="already used"):
        svc.verify(resent["challenge_id"], fresh)
    assert len(store.load()["sessions"]) == 1
    assert first["session"]


def test_resend_limits_and_five_wrong_tries(accounts):
    svc, mailer, clock, _store = accounts
    email = "ada@example.com"
    started = svc.signup(email, "correct-horse")
    with pytest.raises(console_auth.AuthError, match="Wait a minute"):
        svc.resend(started["challenge_id"])
    challenge = started["challenge_id"]
    for _ in range(4):
        clock["t"] += 61
        challenge = svc.resend(challenge)["challenge_id"]
    clock["t"] += 61
    with pytest.raises(console_auth.AuthError, match="Too many codes"):
        svc.resend(challenge)
    # A fresh account for the lockout, so the hour limit above does not apply.
    other = svc.signup("bea@example.com", "correct-horse")
    real = _code(mailer, "bea@example.com")
    for _ in range(4):
        with pytest.raises(console_auth.AuthError, match="not right"):
            svc.verify(other["challenge_id"], "111111")
    with pytest.raises(console_auth.AuthError, match="no longer valid"):
        svc.verify(other["challenge_id"], "111111")
    with pytest.raises(console_auth.AuthError, match="no longer valid"):
        svc.verify(other["challenge_id"], real)
    assert svc.store.load()["sessions"] == {}
    assert svc.store.load()["accounts"]["bea@example.com"]["active"] is False


def test_smtp_missing_refuses_login_and_render_refuses_the_test_sink(accounts, monkeypatch, caplog):
    svc, mailer, _clock, _store = accounts
    bare = console_auth.AuthService(svc.store, env=os.environ, now=lambda: 1_700_000_000.0)
    with pytest.raises(console_auth.AuthError, match="POC_SMTP_HOST") as missing:
        bare.login("ada@example.com", "correct-horse")
    assert not __import__("re").search(r"\d{6}", str(missing.value))
    monkeypatch.setenv("POC_OTP_TEST_SINK", "1")
    monkeypatch.setenv("RENDER", "true")
    with pytest.raises(console_auth.AuthError, match="refused on Render"):
        bare.login("ada@example.com", "correct-horse")
    assert console_auth.test_sink().outbox == []
    monkeypatch.delenv("RENDER")
    monkeypatch.setenv("POC_OTP_TEST_SINK", "1")
    # The sink is explicit and off unless requested. It still must not echo the code through the API result.
    sunk = bare.signup("ada@example.com", "correct-horse")
    code = console_auth.test_sink().codes_for("ada@example.com")[-1]
    assert code not in json.dumps(sunk)
    assert code not in caplog.text
    assert mailer.outbox == []


def test_codes_are_compared_and_not_logged(accounts, caplog, monkeypatch):
    svc, mailer, _clock, store = accounts
    seen: list[tuple[str, str]] = []
    real = console_auth.hmac.compare_digest

    def spy(a, b):
        seen.append((a if isinstance(a, str) else "", b if isinstance(b, str) else ""))
        return real(a, b)

    monkeypatch.setattr(console_auth.hmac, "compare_digest", spy)
    started = svc.signup("ada@example.com", "correct-horse")
    code = _code(mailer, "ada@example.com")
    caplog.set_level("DEBUG")
    with pytest.raises(console_auth.AuthError):
        svc.verify(started["challenge_id"], "999999")
    assert seen, "a wrong code still goes through a constant-time compare"
    assert code not in caplog.text
    assert code not in store.path.read_text()


def test_google_login_skips_the_email_code(accounts, monkeypatch):
    svc, mailer, _clock, store = accounts
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "google-client")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "google-secret")
    script = ScriptedProviders()
    console_auth.set_transport_for_tests(script)
    started = console_auth.handle_request(
        "GET", "/api/auth/google/start", {}, None, {"Host": "127.0.0.1:5173"},
        host="127.0.0.1:5173", proto="http",
    )
    assert started.status == 302
    location = urlparse(started.location or "")
    params = parse_qs(location.query)
    assert params["code_challenge_method"] == ["S256"]
    assert params["state"]
    assert "openid" in params["scope"][0]
    state = params["state"][0]
    nonce = next(iter(store.load()["oauth_states"].values()))["nonce"]
    script.google_tokens.append(_sign({
        "iss": "https://accounts.google.com",
        "aud": "google-client",
        "exp": int(time.time()) + 600,
        "nonce": nonce,
        "email": "ada@example.com",
        "email_verified": True,
        "sub": "google-sub-1",
    }))
    done = console_auth.handle_request(
        "GET", "/api/auth/google/callback",
        {"code": ["auth-code"], "state": [state]}, None,
        {"Host": "127.0.0.1:5173", "Cookie": f"poc_oauth={state}"},
        host="127.0.0.1:5173", proto="http",
    )
    assert done.status == 302 and done.location == "/"
    assert console_auth.session_cookie_present(done.cookies)
    saved = store.path.read_text()
    assert "google-access-should-not-stick" not in saved
    assert "eyJ" not in saved
    assert store.load()["accounts"]["ada@example.com"]["providers"]["google"] == "google-sub-1"
    assert store.load()["accounts"]["ada@example.com"]["active"] is True
    assert mailer.outbox == []


def test_bad_or_missing_state_and_unverified_email(accounts, monkeypatch):
    _svc, mailer, _clock, store = accounts
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "google-client")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "google-secret")
    monkeypatch.setenv("GITHUB_CLIENT_ID", "github-client")
    monkeypatch.setenv("GITHUB_CLIENT_SECRET", "github-secret")
    script = ScriptedProviders()
    console_auth.set_transport_for_tests(script)
    missing = console_auth.handle_request(
        "GET", "/api/auth/google/callback", {}, None, {"Host": "127.0.0.1:5173"},
        host="127.0.0.1:5173", proto="http",
    )
    assert missing.status == 302 and "auth_error" in (missing.location or "")
    assert not console_auth.session_cookie_present(missing.cookies)
    mismatch = console_auth.handle_request(
        "GET", "/api/auth/google/callback",
        {"code": ["x"], "state": ["a" * 20]}, None,
        {"Host": "127.0.0.1:5173", "Cookie": "poc_oauth=" + ("b" * 20)},
        host="127.0.0.1:5173", proto="http",
    )
    assert mismatch.status == 302 and not console_auth.session_cookie_present(mismatch.cookies)
    started = console_auth.handle_request(
        "GET", "/api/auth/github/start", {}, None, {"Host": "127.0.0.1:5173"},
        host="127.0.0.1:5173", proto="http",
    )
    params = parse_qs(urlparse(started.location or "").query)
    assert "user:email" in params["scope"][0] and "user" in params["scope"][0].split()
    state = params["state"][0]
    script.github_user = {"id": 99, "email": "other@example.com"}
    script.github_emails = [
        {"email": "other@example.com", "primary": False, "verified": True},
        {"email": "ada@example.com", "primary": True, "verified": False},
    ]
    refused = console_auth.handle_request(
        "GET", "/api/auth/github/callback",
        {"code": ["gh-code"], "state": [state]}, None,
        {"Host": "127.0.0.1:5173", "Cookie": f"poc_oauth={state}"},
        host="127.0.0.1:5173", proto="http",
    )
    assert "verified" in (refused.location or "")
    assert store.load()["accounts"] == {}
    assert "github-access-should-not-stick" not in store.path.read_text()
    assert mailer.outbox == []


def test_provider_links_a_verified_email_and_obeys_signup_settings(accounts, monkeypatch):
    svc, mailer, _clock, store = accounts
    email = "ada@example.com"
    started = svc.signup(email, "correct-horse")
    svc.verify(started["challenge_id"], _code(mailer, email))
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "google-client")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "google-secret")
    script = ScriptedProviders()
    console_auth.set_transport_for_tests(script)

    def google_as(address: str, sub: str, *, verified: bool = True, invite: str = ""):
        start = console_auth.handle_request(
            "GET", "/api/auth/google/start", {"invite_code": [invite]} if invite else {}, None,
            {"Host": "127.0.0.1:5173"}, host="127.0.0.1:5173", proto="http",
        )
        state = parse_qs(urlparse(start.location or "").query)["state"][0]
        nonce = store.load()["oauth_states"][hashlib.sha256(state.encode()).hexdigest()]["nonce"]
        script.google_tokens.append(_sign({
            "iss": "https://accounts.google.com", "aud": "google-client", "exp": int(time.time()) + 600,
            "nonce": nonce, "email": address, "email_verified": verified, "sub": sub,
        }))
        return console_auth.handle_request(
            "GET", "/api/auth/google/callback", {"code": ["c"], "state": [state]}, None,
            {"Host": "127.0.0.1:5173", "Cookie": f"poc_oauth={state}"},
            host="127.0.0.1:5173", proto="http",
        )

    unverified = google_as(email, "sub-x", verified=False)
    assert "verified" in (unverified.location or "")
    assert "providers" not in store.load()["accounts"][email] or store.load()["accounts"][email]["providers"] == {}
    linked = google_as(email, "sub-ada")
    assert console_auth.session_cookie_present(linked.cookies)
    assert len(store.load()["accounts"]) == 1
    assert store.load()["accounts"][email]["providers"]["google"] == "sub-ada"
    monkeypatch.setenv("POC_SIGNUP_DISABLED", "1")
    closed = google_as("new@example.com", "sub-new")
    assert "turned off" in unquote(closed.location or "")
    assert "new@example.com" not in store.load()["accounts"]
    monkeypatch.delenv("POC_SIGNUP_DISABLED")
    monkeypatch.setenv("POC_INVITE_CODE", "let-me-in")
    needs_invite = google_as("new@example.com", "sub-new")
    assert "invite" in (needs_invite.location or "").lower()
    invited = google_as("new@example.com", "sub-new", invite="let-me-in")
    assert console_auth.session_cookie_present(invited.cookies)
    assert store.load()["accounts"]["new@example.com"]["active"] is True


def test_unconfigured_provider_is_hidden_from_the_api():
    flags = console_auth.provider_config({})
    assert flags["google"] is False and flags["github"] is False
    flags = console_auth.provider_config({"GITHUB_CLIENT_ID": "id", "GITHUB_CLIENT_SECRET": "secret"})
    assert flags["github"] is True and flags["google"] is False


def test_provider_login_keeps_run_isolation(accounts, monkeypatch, tmp_path):
    _svc, _mailer, _clock, store = accounts
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "google-client")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "google-secret")
    script = ScriptedProviders()
    console_auth.set_transport_for_tests(script)

    def login(address: str, sub: str) -> str:
        start = console_auth.handle_request(
            "GET", "/api/auth/google/start", {}, None, {"Host": "127.0.0.1:8787"},
            host="127.0.0.1:8787", proto="http",
        )
        state = parse_qs(urlparse(start.location or "").query)["state"][0]
        nonce = store.load()["oauth_states"][hashlib.sha256(state.encode()).hexdigest()]["nonce"]
        script.google_tokens.append(_sign({
            "iss": "accounts.google.com", "aud": "google-client", "exp": int(time.time()) + 600,
            "nonce": nonce, "email": address, "email_verified": True, "sub": sub,
        }))
        done = console_auth.handle_request(
            "GET", "/api/auth/google/callback", {"code": ["c"], "state": [state]}, None,
            {"Host": "127.0.0.1:8787", "Cookie": f"poc_oauth={state}"},
            host="127.0.0.1:8787", proto="http",
        )
        cookie = next(item for item in done.cookies if item.startswith("poc_session="))
        return cookie.split(";", 1)[0]

    cookie_a = login("ada@example.com", "sub-a")
    cookie_b = login("bea@example.com", "sub-b")
    id_a = store.load()["accounts"]["ada@example.com"]["id"]
    id_b = store.load()["accounts"]["bea@example.com"]["id"]
    monkeypatch.setattr(console_api, "RUNS_ROOT", tmp_path / "runs")
    monkeypatch.setattr(console_api, "REPO_ROOT", tmp_path)
    folder = tmp_path / "runs" / "day" / "run-a"
    folder.mkdir(parents=True)
    (folder / "record.json").write_text(json.dumps({
        "record_kind": "pr_run", "id": "run-a", "repo": "me/demo", "verdict": "verified",
        "reason": "ok", "pr": {"number": 1, "url": "https://github.com/me/demo/pull/1", "title": "t"},
    }))
    console_api.set_run_owner(folder, id_a)
    assert [row["id"] for row in console_api.list_runs(owner=id_a)] == ["run-a"]
    assert console_api.list_runs(owner=id_b) == []
    assert console_api.get_run("run-a", owner=id_b) is None

    class FakeThread:
        def __init__(self, target=None, daemon=None):
            self.target = target

        def start(self):
            pass

    real_thread = console_api.threading.Thread
    monkeypatch.setattr(console_api.threading, "Thread", FakeThread)
    monkeypatch.setattr(console_api, "console_run_flags", lambda *_a, **_k: console_api.ConsoleRunPlan([], None, False, None))
    (tmp_path / "ops" / "runs" / "_jobs").mkdir(parents=True)
    (tmp_path / "ops" / "daily_run.py").write_text("# stub\n")
    job = console_api.start_check("https://github.com/me/demo/pull/3", model_provider="none", owner=id_a)
    monkeypatch.setattr(console_api.threading, "Thread", real_thread)
    assert console_api.get_job(job["id"], owner=id_b) is None
    assert console_api.get_job(job["id"], owner=id_a)["id"] == job["id"]

    server = console_api.ThreadingHTTPServer(("127.0.0.1", 0), console_api.Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        conn = http.client.HTTPConnection("127.0.0.1", server.server_address[1], timeout=5)
        conn.request("GET", "/api/runs", headers={"Cookie": cookie_a})
        body = json.loads(conn.getresponse().read())
        assert [row["id"] for row in body["runs"]] == ["run-a"]
        conn.request("GET", "/api/runs", headers={"Cookie": cookie_b})
        other = json.loads(conn.getresponse().read())
        assert other["runs"] == []
        conn.request("POST", "/api/auth/login", body=b"{}", headers={"Content-Type": "application/json"})
        login = conn.getresponse()
        blob = login.read()
        assert login.status == 503
        assert b"poc_session=" not in b"".join(login.headers.get_all("Set-Cookie") or [])
        assert b"run-a" not in blob
    finally:
        server.shutdown()


def test_password_login_http_sets_no_cookie_until_the_code_matches(accounts, monkeypatch):
    svc, mailer, _clock, _store = accounts
    email = "ada@example.com"
    started = svc.signup(email, "correct-horse")
    svc.verify(started["challenge_id"], _code(mailer, email))
    monkeypatch.setenv("POC_OTP_TEST_SINK", "1")
    server = console_api.ThreadingHTTPServer(("127.0.0.1", 0), console_api.Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        conn = http.client.HTTPConnection("127.0.0.1", server.server_address[1], timeout=5)
        payload = json.dumps({"email": email, "password": "correct-horse"}).encode()
        conn.request("POST", "/api/auth/login", body=payload, headers={"Content-Type": "application/json"})
        response = conn.getresponse()
        raw = response.read()
        assert response.status == 200
        cookies = response.headers.get_all("Set-Cookie") or []
        assert not any(item.startswith("poc_session=") and "Max-Age=0" not in item for item in cookies)
        body = json.loads(raw)
        code = console_auth.test_sink().codes_for(email)[-1]
        assert code.encode() not in raw
        check = json.dumps({"challenge_id": body["challenge_id"], "code": code}).encode()
        conn.request("POST", "/api/auth/verify", body=check, headers={"Content-Type": "application/json"})
        verified = conn.getresponse()
        assert verified.status == 200
        assert any(item.startswith("poc_session=") for item in (verified.headers.get_all("Set-Cookie") or []))
    finally:
        server.shutdown()


def _me(monkeypatch, env_name: str | None = None, env_value: str | None = None, visibility: str | None = "private"):
    monkeypatch.delenv("CODESPACES", raising=False)
    monkeypatch.delenv("POC_SINGLE_USER", raising=False)
    if env_name:
        monkeypatch.setenv(env_name, env_value or "")
    monkeypatch.setattr(console_auth, "codespace_port_visibility", lambda: visibility)
    console_auth.reset_port_cache()
    return console_auth.handle_request("GET", "/api/auth/me", {}, None, {}, host="127.0.0.1", proto="http")


def test_sign_in_stays_required_on_other_hosts(accounts, monkeypatch):
    result = _me(monkeypatch)
    assert result.status == 401
    assert result.body["error"] == "Sign in first."
    assert console_auth.viewer_account(None) is None
    assert console_auth.request_session_token(None) is None
    for value in ("", "0", "false", "no", "off"):
        result = _me(monkeypatch, "CODESPACES", value)
        assert result.status == 401
        result = _me(monkeypatch, "POC_SINGLE_USER", value)
        assert result.status == 401


def test_other_hosts_do_not_ask_about_the_codespace_port(accounts, monkeypatch):
    monkeypatch.delenv("CODESPACES", raising=False)
    monkeypatch.delenv("POC_SINGLE_USER", raising=False)
    calls = []
    monkeypatch.setattr(console_auth.subprocess, "run", lambda *args, **kwargs: calls.append(args))
    assert console_auth.sign_in_skip() == (False, None)
    assert calls == []


def test_codespace_and_single_user_skip_sign_in_when_the_port_is_not_public(accounts, monkeypatch):
    for name, value in (("CODESPACES", "true"), ("POC_SINGLE_USER", "1"), ("POC_SINGLE_USER", "yes")):
        result = _me(monkeypatch, name, value, "private")
        assert result.status == 200
        assert result.body["id"] == "local"
        assert result.body["role"] == "admin"
        assert console_auth.request_session_token(None) == console_auth.LOCAL_SESSION
    result = _me(monkeypatch, "CODESPACES", "true", None)
    assert result.status == 401 and result.body["error"] == console_auth.PORT_UNKNOWN_MESSAGE
    result = _me(monkeypatch, "CODESPACES", "true", "org")
    assert result.status == 200


def test_a_public_port_refuses_to_skip_sign_in(accounts, monkeypatch):
    result = _me(monkeypatch, "CODESPACES", "true", "public")
    assert result.status == 401
    assert result.body["error"] == console_auth.PORT_PUBLIC_MESSAGE
    assert "back to private" in result.body["error"]
    assert console_auth.viewer_account(None) is None
    result = _me(monkeypatch, "POC_SINGLE_USER", "1", "public")
    assert result.status == 401
    assert console_auth.port_refusal('[{"port": 8787, "visibility": "public"}]') == console_auth.PORT_PUBLIC_MESSAGE
    assert console_auth.port_refusal('[{"port": 8787, "visibility": "private"}]') is None
    assert console_auth.port_refusal('[{"port": 22, "visibility": "public"}]') is None
    assert console_auth.port_refusal("") is None
    assert console_auth.port_refusal("not json") is None


def test_codespace_http_serves_without_a_session_and_still_hides_a_pasted_key(accounts, monkeypatch):
    monkeypatch.setenv("POC_SINGLE_USER", "1")
    monkeypatch.setattr(console_auth, "codespace_port_visibility", lambda: "private")
    server = console_api.ThreadingHTTPServer(("127.0.0.1", 0), console_api.Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    secret = "nebius-session-secret-value"
    try:
        conn = http.client.HTTPConnection("127.0.0.1", server.server_address[1], timeout=5)
        conn.request("GET", "/api/auth/me")
        me = conn.getresponse()
        me_body = json.loads(me.read().decode())
        assert me.status == 200 and me_body["email"] == "local"
        payload = json.dumps({"nebius_api_key": secret}).encode()
        conn.request("POST", "/api/session/key", body=payload, headers={"Content-Type": "application/json"})
        saved = conn.getresponse()
        raw = saved.read()
        assert saved.status == 200
        assert secret.encode() not in raw
        assert json.loads(raw)["nebius_key"] is True
    finally:
        session_key_clear()
        server.shutdown()


def session_key_clear():
    from poc import session_key
    session_key.clear_key(console_auth.LOCAL_SESSION)


def test_http_sign_in_stays_required_when_the_port_is_public(accounts, monkeypatch):
    monkeypatch.setenv("CODESPACES", "true")
    monkeypatch.setattr(console_auth, "codespace_port_visibility", lambda: "public")
    server = console_api.ThreadingHTTPServer(("127.0.0.1", 0), console_api.Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        conn = http.client.HTTPConnection("127.0.0.1", server.server_address[1], timeout=5)
        conn.request("GET", "/api/runs")
        response = conn.getresponse()
        body = json.loads(response.read().decode())
        assert response.status == 401
        assert body["error"] == console_auth.PORT_PUBLIC_MESSAGE
    finally:
        server.shutdown()


def _single_user_server(accounts, monkeypatch):
    monkeypatch.setenv("POC_SINGLE_USER", "1")
    monkeypatch.setattr(console_auth, "codespace_port_visibility", lambda: "private")
    server = console_api.ThreadingHTTPServer(("127.0.0.1", 0), console_api.Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def _post(port, path, body, cookie=None):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    headers = {"Content-Type": "application/json"}
    if cookie:
        headers["Cookie"] = cookie
    conn.request("POST", path, body=json.dumps(body).encode(), headers=headers)
    resp = conn.getresponse()
    return resp.status, resp.read()


@pytest.mark.real_key_gate
def test_one_submit_starts_a_check_with_keys_and_keeps_them_in_memory_only(accounts, monkeypatch, tmp_path):
    from poc import session_key
    secret = "nebius-start-form-secret"
    project = "project-start-form-id"
    seen = {}

    def fake_start(pr_url, **kwargs):
        token = kwargs["session_token"]
        seen["key"] = session_key.get_key(token)
        seen["project"] = session_key.get_contree_project(token)
        seen["approval"] = kwargs["approval"]
        return {"id": "job123", "status": "queued", "pr_url": pr_url}

    monkeypatch.setattr(console_api, "start_check", fake_start)
    before = {p for p in tmp_path.rglob("*")}
    server = _single_user_server(accounts, monkeypatch)
    try:
        port = server.server_address[1]
        status, raw = _post(port, "/api/checks", {
            "pr_url": "https://github.com/o/r/pull/1", "approval": True,
            "nebius_api_key": secret, "contree_project_id": project,
        })
        assert status == 202
        assert json.loads(raw)["id"] == "job123"
        assert secret.encode() not in raw and project.encode() not in raw
        assert seen == {"key": secret, "project": project, "approval": True}
        # A refresh may bring a different or stale cookie: the single-user slot keeps the key.
        status, raw = _post(port, "/api/checks", {"pr_url": "https://github.com/o/r/pull/2"},
                            cookie=f"{console_auth.SESSION_COOKIE}=stale-after-refresh")
        assert status == 202 and seen["key"] == secret
        assert {p for p in tmp_path.rglob("*")} == before
    finally:
        session_key_clear()
        server.shutdown()


@pytest.mark.real_key_gate
def test_refused_start_returns_a_plain_reason(accounts, monkeypatch):
    _clear_contree_env(monkeypatch)
    monkeypatch.delenv("POC_UNSAFE_NO_SANDBOX", raising=False)
    monkeypatch.setattr(console_api, "contree_usable", lambda *a, **k: False)
    import guardrails.sandbox as sb
    monkeypatch.setattr(sb, "check", lambda *a, **k: (False, "bwrap: No permissions to create a new namespace"))
    monkeypatch.setattr(console_api.subprocess, "Popen", lambda *a, **k: (_ for _ in ()).throw(AssertionError("ran")))
    server = _single_user_server(accounts, monkeypatch)
    try:
        port = server.server_address[1]
        status, raw = _post(port, "/api/checks", {
            "pr_url": "https://github.com/me/demo/pull/3", "model_provider": "recorded",
            "nebius_api_key": "nebius-refused-secret",
        })
        body = json.loads(raw)
        assert status == 400 and body["refused"] is True, body
        assert body["error"] == "No sandbox available: add your Nebius project ID."
        assert b"nebius-refused-secret" not in raw and "bwrap" not in body["error"]
        status, raw = _post(port, "/api/checks", {"pr_url": "not a link"})
        assert status == 400 and "not a pull request" in json.loads(raw)["error"]
        status, raw = _post(port, "/api/checks", {"pr_url": ""})
        assert status == 400 and json.loads(raw)["error"] == "Add a pull request link."
    finally:
        session_key_clear()
        server.shutdown()


def _clear_contree_env(monkeypatch):
    for name in ("NEBIUS_API_KEY", "NEBIUS_PROJECT_ID", "CONTREE_PROJECT_ID", "POC_UNSAFE_NO_SANDBOX", "SPACE_ID"):
        monkeypatch.delenv(name, raising=False)


@pytest.mark.real_key_gate
def test_form_key_and_project_turn_on_contree_only_mode(accounts, monkeypatch):
    """Both typed into the form: the check runs with --sandbox-backend contree, Contree mocked, bwrap down."""
    import sys
    import types
    _clear_contree_env(monkeypatch)
    monkeypatch.setitem(sys.modules, "contree_sdk", types.ModuleType("contree_sdk"))
    import guardrails.sandbox as sb
    monkeypatch.setattr(sb, "check", lambda *a, **k: (False, "bwrap down"))
    captured = {}

    class FakeProc:
        pid = 0

    def fake_popen(cmd, *args, **kwargs):
        captured["cmd"] = cmd
        captured["env"] = kwargs.get("env") or {}
        raise RuntimeError("stop after capture")

    monkeypatch.setattr(console_api.subprocess, "Popen", fake_popen)
    secret, project = "nebius-contree-only-key", "contree-only-project-id"
    server = _single_user_server(accounts, monkeypatch)
    try:
        port = server.server_address[1]
        status, raw = _post(port, "/api/checks", {
            "pr_url": "https://github.com/me/demo/pull/7", "approval": False,
            "nebius_api_key": secret, "contree_project_id": project,
        })
        assert status == 202, raw
        body = json.loads(raw)
        assert body["run_flags"][:2] == ["--sandbox-backend", "contree"]
        assert secret.encode() not in raw and project.encode() not in raw
        import time
        for _ in range(50):
            if "cmd" in captured:
                break
            time.sleep(0.05)
        assert "--sandbox-backend" in captured["cmd"] and "contree" in captured["cmd"]
        assert "NEBIUS_API_KEY" not in __import__("os").environ
    finally:
        session_key_clear()
        server.shutdown()


@pytest.mark.real_key_gate
def test_both_given_but_contree_cannot_start_does_not_ask_for_them_again(accounts, monkeypatch):
    import sys
    _clear_contree_env(monkeypatch)
    monkeypatch.setitem(sys.modules, "contree_sdk", None)   # import fails: SDK missing
    import guardrails.sandbox as sb
    monkeypatch.setattr(sb, "check", lambda *a, **k: (False, "bwrap down"))
    monkeypatch.setattr(console_api.subprocess, "Popen", lambda *a, **k: (_ for _ in ()).throw(AssertionError("ran")))
    server = _single_user_server(accounts, monkeypatch)
    try:
        status, raw = _post(server.server_address[1], "/api/checks", {
            "pr_url": "https://github.com/me/demo/pull/8",
            "nebius_api_key": "nebius-sdk-missing-key", "contree_project_id": "project-sdk-missing",
        })
        body = json.loads(raw)
        assert status == 400 and body["refused"] is True
        assert "are set" in body["error"] and "Contree software is not installed" in body["error"]
        assert "add your" not in body["error"]
        assert b"nebius-sdk-missing-key" not in raw and b"project-sdk-missing" not in raw
    finally:
        session_key_clear()
        server.shutdown()


def test_sign_in_stays_on_when_port_visibility_cannot_be_read(monkeypatch):
    monkeypatch.setenv("CODESPACES", "true")
    console_auth.reset_port_cache()
    monkeypatch.setattr(console_auth.shutil, "which", lambda _name: None)          # gh missing
    assert console_auth.sign_in_skip() == (False, console_auth.PORT_UNKNOWN_MESSAGE)
    assert console_auth.request_session_token(None) is None
    console_auth.reset_port_cache()
    monkeypatch.setattr(console_auth.shutil, "which", lambda _name: "/usr/bin/gh")

    class Failed:
        returncode, stdout = 1, ""

    monkeypatch.setattr(console_auth.subprocess, "run", lambda *a, **k: Failed())  # gh failing
    assert console_auth.sign_in_skip() == (False, console_auth.PORT_UNKNOWN_MESSAGE)
    console_auth.reset_port_cache()


@pytest.mark.real_key_gate
def test_server_nebius_env_is_never_used_for_a_user_check(accounts, monkeypatch):
    """Server env has a key and project; the session has none: refused, asked for the key, nothing runs."""
    import sys
    import types
    _clear_contree_env(monkeypatch)
    monkeypatch.setenv("NEBIUS_API_KEY", "server-nebius-key-should-not-be-used")
    monkeypatch.setenv("NEBIUS_PROJECT_ID", "server-project-should-not-be-used")
    monkeypatch.setenv("CONTREE_PROJECT_ID", "server-contree-project-unused")
    monkeypatch.setitem(sys.modules, "contree_sdk", types.ModuleType("contree_sdk"))
    import guardrails.sandbox as sb
    monkeypatch.setattr(sb, "check", lambda *a, **k: (False, "bwrap down"))
    monkeypatch.setattr(console_api.subprocess, "Popen", lambda *a, **k: (_ for _ in ()).throw(AssertionError("ran")))
    assert console_api.contree_credentials(console_auth.LOCAL_SESSION) == ("", "")
    assert console_api.resolve_console_provider("nebius", console_auth.LOCAL_SESSION)[0] == "recorded"
    env, secrets = console_api.child_environment(dict(__import__("os").environ), "nebius", console_auth.LOCAL_SESSION)
    assert "NEBIUS_API_KEY" not in env and "NEBIUS_PROJECT_ID" not in env and "CONTREE_PROJECT_ID" not in env
    assert "server-nebius-key-should-not-be-used" in secrets
    server = _single_user_server(accounts, monkeypatch)
    try:
        status, raw = _post(server.server_address[1], "/api/checks", {"pr_url": "https://github.com/me/demo/pull/9"})
        body = json.loads(raw)
        assert status == 400 and body["refused"] is True
        assert body["error"] == console_api.NO_KEY_MESSAGE
        assert "are set" not in body["error"]
        assert b"server-nebius-key" not in raw and b"server-project" not in raw
    finally:
        session_key_clear()
        server.shutdown()


def test_signed_in_accounts_keep_separate_keys_and_never_use_the_local_slot(monkeypatch):
    from poc import session_key
    for name in ("CODESPACES", "POC_SINGLE_USER"):
        monkeypatch.delenv(name, raising=False)
    assert console_auth.sign_in_skip()[0] is False
    tok_a = console_auth.request_session_token("session-cookie-account-a")
    tok_b = console_auth.request_session_token("session-cookie-account-b")
    assert tok_a == "session-cookie-account-a" and tok_b == "session-cookie-account-b"
    assert console_auth.LOCAL_SESSION not in (tok_a, tok_b)
    assert console_auth.request_session_token(None) is None
    try:
        console_api.apply_start_fields(tok_a, {"nebius_api_key": "account-a-key-123", "contree_project_id": "proj-a-123"})
        console_api.apply_start_fields(tok_b, {"nebius_api_key": "account-b-key-456"})
        assert console_api.contree_credentials(tok_a) == ("account-a-key-123", "proj-a-123")
        assert console_api.contree_credentials(tok_b) == ("account-b-key-456", "")
        assert session_key.get_key(console_auth.LOCAL_SESSION) is None
        with pytest.raises(ValueError):
            console_api.apply_start_fields(console_auth.request_session_token(None), {"nebius_api_key": "no-session-key"})
    finally:
        session_key.clear_key(tok_a)
        session_key.clear_key(tok_b)


@pytest.mark.real_key_gate
def test_unknown_pr_without_a_typed_key_is_refused_and_nothing_runs(accounts, monkeypatch):
    _clear_contree_env(monkeypatch)
    monkeypatch.setenv("NEBIUS_API_KEY", "server-key-does-not-count")
    ran = []
    monkeypatch.setattr(console_api.subprocess, "Popen", lambda *a, **k: ran.append(a) or (_ for _ in ()).throw(AssertionError("ran")))
    server = _single_user_server(accounts, monkeypatch)
    try:
        for provider in ("nebius", "recorded", "none"):
            status, raw = _post(server.server_address[1], "/api/checks",
                                {"pr_url": "https://github.com/someone/unknown/pull/42", "model_provider": provider})
            body = json.loads(raw)
            assert status == 400 and body["refused"] is True
            assert body["error"] == "Add your Nebius API key to run a live check."
        assert ran == []
    finally:
        session_key_clear()
        server.shutdown()
