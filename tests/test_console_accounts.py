"""Console accounts: sign-up, sessions, and server-side run isolation."""
from __future__ import annotations

import json
import sqlite3
import threading
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer

import pytest

from poc import console_accounts, console_api

PASSWORD = "S3cret-plain-password!"


@pytest.fixture
def api(tmp_path, monkeypatch):
    monkeypatch.setenv("POC_SESSION_SECRET", "test-secret-value-16chars")
    monkeypatch.setenv("POC_ACCOUNTS_DB", str(tmp_path / "accounts.sqlite"))
    monkeypatch.delenv("POC_ADMIN_EMAIL", raising=False)
    monkeypatch.delenv("POC_SIGNUP_DISABLED", raising=False)
    monkeypatch.delenv("POC_INVITE_CODE", raising=False)
    monkeypatch.delenv("POC_COOKIE_SECURE", raising=False)
    console_accounts.reset_for_tests()
    console_api._jobs.clear()
    console_api._recent_runs.clear()
    monkeypatch.setattr(console_api, "RUNS_ROOT", tmp_path / "runs")
    monkeypatch.setattr(console_api, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(console_api, "REPORTS_DAILY", tmp_path / "reports" / "daily")
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), console_api.Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield httpd.server_address[1], tmp_path
    finally:
        httpd.shutdown()
        httpd.server_close()
        console_api._jobs.clear()
        console_api._recent_runs.clear()


def _call(port, method, path, body=None, cookie=None, csrf=None):
    conn = HTTPConnection("127.0.0.1", port, timeout=15)
    headers = {}
    raw = None
    if body is not None:
        raw = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
        headers["Content-Length"] = str(len(raw))
    if cookie:
        headers["Cookie"] = f"poc_session={cookie}"
    if csrf:
        headers["X-CSRF-Token"] = csrf
    conn.request(method, path, body=raw, headers=headers)
    resp = conn.getresponse()
    payload = resp.read()
    cookies = resp.headers.get_all("Set-Cookie") or []
    conn.close()
    return resp.status, payload, cookies


def _json(payload):
    return json.loads(payload.decode() or "{}")


def _session(cookies):
    for item in cookies:
        if item.startswith("poc_session=") and "Max-Age=0" not in item:
            return item, item.split(";", 1)[0].split("=", 1)[1]
    return "", ""


def _csrf(port):
    status, payload, _cookies = _call(port, "GET", "/api/auth/csrf")
    assert status == 200, payload
    return _json(payload)["csrf"]


def _signup(port, email, password=PASSWORD, invite=""):
    token = _csrf(port)
    status, payload, cookies = _call(
        port,
        "POST",
        "/api/auth/signup",
        {"email": email, "password": password, "invite": invite},
        csrf=token,
    )
    return status, _json(payload), cookies, payload


def _login(port, email, password=PASSWORD):
    token = _csrf(port)
    status, payload, cookies = _call(
        port, "POST", "/api/auth/login", {"email": email, "password": password}, csrf=token
    )
    return status, _json(payload), cookies, payload


def _write_run(root, run_id, owner, marker):
    folder = root / "runs" / "2026-10-20" / run_id
    folder.mkdir(parents=True)
    (folder / "record.json").write_text(json.dumps({
        "record_kind": "pr_run",
        "id": run_id,
        "repo": "me/demo",
        "verdict": "verified",
        "reason": marker,
        "pr": {"number": 7, "url": "https://github.com/me/demo/pull/7", "title": run_id},
        "tested_at_ist": "2026-10-20 12:00 IST",
        "behaviour": {"nodes": [{"id": "only-this-map", "label": marker}]},
    }))
    if owner:
        (folder / "console_owner.txt").write_text(owner + "\n")
    report = root / "reports" / "daily" / "2026-10-20" / run_id
    report.mkdir(parents=True)
    (report / "REPORT.pdf").write_bytes(f"%PDF {marker}".encode())
    (report / "REPORT.html").write_bytes(f"<p>{marker}</p>".encode())


def test_signup_and_login_set_a_session_cookie(api):
    port, _root = api
    status, body, cookies, raw = _signup(port, "ada@example.com")
    assert status == 200, raw
    assert body["email"] == "ada@example.com"
    assert body["role"] == "user"
    assert "password" not in body
    assert PASSWORD.encode() not in raw
    header, token = _session(cookies)
    assert "HttpOnly" in header
    assert "SameSite=Lax" in header
    assert token and token.encode() not in raw
    me_status, me_raw, _ = _call(port, "GET", "/api/auth/me", cookie=token)
    assert me_status == 200
    assert _json(me_raw)["email"] == "ada@example.com"

    out_status, out_raw, out_cookies = _call(
        port, "POST", "/api/auth/logout", {}, cookie=token, csrf=body["csrf"]
    )
    assert out_status == 200, out_raw
    assert any("Max-Age=0" in item for item in out_cookies)
    gone, _, _ = _call(port, "GET", "/api/auth/me", cookie=token)
    assert gone == 401

    status, logged, cookies, raw = _login(port, "ada@example.com")
    assert status == 200, raw
    assert logged["id"] == body["id"]
    header, token = _session(cookies)
    assert "HttpOnly" in header and token


def test_wrong_password_and_missing_csrf_do_not_sign_in(api):
    port, _root = api
    assert _signup(port, "ada@example.com")[0] == 200
    status, body, cookies, raw = _login(port, "ada@example.com", password="not-the-password")
    assert status == 401, raw
    assert "wrong" in body["error"]
    assert _session(cookies)[1] == ""
    assert PASSWORD.encode() not in raw

    status, payload, cookies = _call(
        port, "POST", "/api/auth/login", {"email": "ada@example.com", "password": PASSWORD}
    )
    assert status == 403, payload
    assert _session(cookies)[1] == ""

    open_runs, _, _ = _call(port, "GET", "/api/runs")
    assert open_runs == 401
    health, _, _ = _call(port, "GET", "/api/health")
    assert health == 200


def test_a_user_cannot_open_another_users_run(api):
    port, root = api
    ada_status, ada, ada_cookies, raw = _signup(port, "ada@example.com")
    assert ada_status == 200, raw
    bea_status, bea, bea_cookies, raw = _signup(port, "bea@example.com")
    assert bea_status == 200, raw
    ada_cookie = _session(ada_cookies)[1]
    bea_cookie = _session(bea_cookies)[1]
    _write_run(root, "run-ada", ada["id"], "only-ada")
    _write_run(root, "run-bea", bea["id"], "only-bea")
    _write_run(root, "run-old", None, "only-admin-old")
    console_api._jobs["job-ada"] = {
        "id": "job-ada",
        "status": "running",
        "owner": ada["id"],
        "pr_url": "https://github.com/me/demo/pull/7",
        "log_tail": "only-ada-log",
        "console_log": str(root / "missing.log"),
        "progress_path": str(root / "missing.jsonl"),
        "hitl_dir": str(root / "hitl-ada"),
    }

    listed, listed_raw, _ = _call(port, "GET", "/api/runs", cookie=bea_cookie)
    assert listed == 200, listed_raw
    ids = {row["id"] for row in _json(listed_raw)["runs"]}
    assert ids == {"run-bea"}
    assert b"only-ada" not in listed_raw
    assert b"only-admin-old" not in listed_raw

    paths = [
        "/api/runs/run-ada",
        "/api/runs/run-ada/report.pdf",
        "/api/runs/run-ada/report.html",
        "/api/runs/run-old",
        "/api/jobs/job-ada",
    ]
    for path in paths:
        status, payload, _ = _call(port, "GET", path, cookie=bea_cookie)
        assert status == 404, (path, payload)
        assert b"only-ada" not in payload
        assert b"only-admin-old" not in payload

    status, payload, _ = _call(
        port,
        "POST",
        "/api/jobs/job-ada/scenarios",
        {"approve": [], "extra_scenarios": [], "business_answers": {}, "skip_business_followup": True},
        cookie=bea_cookie,
        csrf=bea["csrf"],
    )
    assert status == 404, payload
    assert b"only-ada" not in payload

    own, own_raw, _ = _call(port, "GET", "/api/runs/run-ada", cookie=ada_cookie)
    assert own == 200, own_raw
    assert b"only-ada" in own_raw
    pdf, pdf_raw, _ = _call(port, "GET", "/api/runs/run-ada/report.pdf", cookie=ada_cookie)
    assert pdf == 200 and pdf_raw.startswith(b"%PDF only-ada")
    html, html_raw, _ = _call(port, "GET", "/api/runs/run-ada/report.html", cookie=ada_cookie)
    assert html == 200 and b"only-ada" in html_raw
    job, job_raw, _ = _call(port, "GET", "/api/jobs/job-ada", cookie=ada_cookie)
    assert job == 200 and b"only-ada-log" in job_raw
    assert b'"owner"' not in job_raw


def test_admin_sees_every_run_including_unowned(api, monkeypatch):
    port, root = api
    monkeypatch.setenv("POC_ADMIN_EMAIL", "admin@example.com")
    user_status, user, user_cookies, raw = _signup(port, "ada@example.com")
    assert user_status == 200, raw
    admin_status, admin, admin_cookies, raw = _signup(port, "admin@example.com")
    assert admin_status == 200, raw
    assert admin["role"] == "admin"
    _write_run(root, "run-ada", user["id"], "only-ada")
    _write_run(root, "run-old", None, "only-admin-old")
    status, payload, _ = _call(port, "GET", "/api/runs", cookie=_session(admin_cookies)[1])
    assert status == 200, payload
    ids = {row["id"] for row in _json(payload)["runs"]}
    assert ids == {"run-ada", "run-old"}
    opened, opened_raw, _ = _call(port, "GET", "/api/runs/run-old", cookie=_session(admin_cookies)[1])
    assert opened == 200 and b"only-admin-old" in opened_raw
    hidden, hidden_raw, _ = _call(port, "GET", "/api/runs/run-old", cookie=_session(user_cookies)[1])
    assert hidden == 404 and b"only-admin-old" not in hidden_raw

    console_accounts.promote("ada@example.com")
    again, again_body, _cookies, raw = _login(port, "ada@example.com")
    assert again == 200 and again_body["role"] == "admin", raw
    promoted, promoted_raw, _ = _call(port, "GET", "/api/runs/run-old", cookie=_session(_cookies)[1])
    assert promoted == 200 and b"only-admin-old" in promoted_raw


def test_signup_can_be_turned_off_and_can_require_an_invite(api, monkeypatch):
    port, _root = api
    monkeypatch.setenv("POC_SIGNUP_DISABLED", "1")
    status, body, cookies, raw = _signup(port, "ada@example.com")
    assert status == 403, raw
    assert "turned off" in body["error"]
    assert _session(cookies)[1] == ""

    monkeypatch.delenv("POC_SIGNUP_DISABLED")
    monkeypatch.setenv("POC_INVITE_CODE", "demo-invite")
    refused, refused_body, refused_cookies, raw = _signup(port, "ada@example.com", invite="nope")
    assert refused == 403, raw
    assert "invite" in refused_body["error"].lower()
    assert _session(refused_cookies)[1] == ""
    allowed, allowed_body, allowed_cookies, raw = _signup(port, "ada@example.com", invite="demo-invite")
    assert allowed == 200, raw
    assert allowed_body["email"] == "ada@example.com"
    assert _session(allowed_cookies)[1]


def test_passwords_are_stored_only_as_hashes(api):
    port, root = api
    status, _body, _cookies, raw = _signup(port, "ada@example.com")
    assert status == 200, raw
    db = root / "accounts.sqlite"
    blob = db.read_bytes()
    assert PASSWORD.encode() not in blob
    conn = sqlite3.connect(db)
    try:
        columns = [row[1] for row in conn.execute("PRAGMA table_info(accounts)")]
        assert "password" not in columns
        salt, digest = conn.execute(
            "SELECT password_salt, password_hash FROM accounts WHERE email = ?",
            ("ada@example.com",),
        ).fetchone()
    finally:
        conn.close()
    assert salt and digest and digest != PASSWORD
    assert len(digest) == 64
    assert all(ch in "0123456789abcdef" for ch in digest)


def test_five_wrong_passwords_lock_the_account(api):
    port, _root = api
    assert _signup(port, "ada@example.com")[0] == 200
    for _ in range(4):
        status, body, _cookies, raw = _login(port, "ada@example.com", password="not-the-password")
        assert status == 401, raw
        assert "wrong" in body["error"]
    status, body, cookies, raw = _login(port, "ada@example.com", password="not-the-password")
    assert status == 429, raw
    assert "later" in body["error"]
    assert _session(cookies)[1] == ""
    status, body, cookies, raw = _login(port, "ada@example.com")
    assert status == 429, raw
    assert _session(cookies)[1] == ""
