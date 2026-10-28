"""GitHub App webhook: signature first, duplicates skipped by delivery ID, checks queued and answered with 202,
one worker running one check at a time, and every App check counted in the console's daily cap."""
import hashlib
import hmac
import json
import multiprocessing
import threading
import time
import urllib.error
import urllib.request

import pytest

from poc import console_api, github_app

SECRET = "test-webhook-secret"
KEYS = ("NEBIUS_API_KEY", "NEBIUS_PROJECT_ID", "TAVILY_API_KEY", "GITHUB_TOKEN", "GH_TOKEN",
        "GITHUB_APP_INSTALLATION_TOKEN", "GITHUB_APP_ID", "GITHUB_APP_PRIVATE_KEY")


@pytest.fixture(autouse=True)
def _no_keys(monkeypatch):
    for k in KEYS:
        monkeypatch.delenv(k, raising=False)


def _payload(pr=7):
    return {"action": "opened", "repository": {"full_name": "demo/repo"},
            "pull_request": {"number": pr, "head": {"sha": "abc"}}}


def _post(port, payload, delivery, secret=SECRET):
    raw = json.dumps(payload).encode()
    sig = "sha256=" + hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
    url = f"http://127.0.0.1:{port}/webhook"
    req = urllib.request.Request(url, data=raw, method="POST", headers={  # br-allow-external: local test server
        "X-Hub-Signature-256": sig, "X-GitHub-Event": "pull_request", "X-GitHub-Delivery": delivery,
        "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, {}


class _Server:
    def __init__(self, tmp_path, checks):
        env = {"GITHUB_WEBHOOK_SECRET": SECRET, "POC_DEMO_REPOS": "demo/repo"}
        checks.env = env
        self.httpd = github_app.make_server("127.0.0.1", 0, env, checks=checks, state=tmp_path / "state")
        self.port = self.httpd.server_address[1]
        self.t = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.t.start()

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()


def test_bad_signature_is_refused_and_nothing_is_queued(tmp_path):
    checks = github_app.CheckQueue({}, apply_fn=lambda plan, env: {"ok": True}, refusal_fn=lambda env: None)
    srv = _Server(tmp_path, checks)
    try:
        status, _ = _post(srv.port, _payload(), "d-1", secret="wrong")
        assert status == 401
        assert checks.q.qsize() == 0
        assert not (tmp_path / "state" / "deliveries.txt").exists()
    finally:
        srv.close()


def test_replies_202_before_the_check_finishes(tmp_path):
    release = threading.Event()
    done = []

    def slow_apply(plan, env):
        release.wait(10)
        done.append(plan["pr"])
        return {"ok": True}

    checks = github_app.CheckQueue({}, apply_fn=slow_apply, refusal_fn=lambda env: None).start()
    srv = _Server(tmp_path, checks)
    try:
        t0 = time.monotonic()
        status, body = _post(srv.port, _payload(7), "d-202")
        assert status == 202 and body["queued"] is True
        assert time.monotonic() - t0 < 2 and done == []
        release.set()
        checks.q.join()
        assert done == [7]
    finally:
        release.set()
        srv.close()
        checks.stop()


def test_duplicate_delivery_is_skipped_even_after_a_restart(tmp_path):
    ran = []
    checks = github_app.CheckQueue({}, apply_fn=lambda plan, env: ran.append(plan["pr"]) or {"ok": True},
                                   refusal_fn=lambda env: None).start()
    srv = _Server(tmp_path, checks)
    try:
        assert _post(srv.port, _payload(), "same-id")[0] == 202
        status, body = _post(srv.port, _payload(), "same-id")
        assert status == 200 and body["duplicate"] is True
    finally:
        srv.close()
    srv2 = _Server(tmp_path, checks)  # a new process reads the same state file
    try:
        assert _post(srv2.port, _payload(), "same-id")[1].get("duplicate") is True
        assert _post(srv2.port, _payload(), "other-id")[0] == 202
        checks.q.join()
        assert ran == [7, 7]
    finally:
        srv2.close()
        checks.stop()


def test_missing_delivery_id_is_refused(tmp_path):
    checks = github_app.CheckQueue({}, apply_fn=lambda plan, env: {"ok": True}, refusal_fn=lambda env: None)
    srv = _Server(tmp_path, checks)
    try:
        assert _post(srv.port, _payload(), "")[0] == 400
    finally:
        srv.close()


def test_one_worker_runs_one_check_at_a_time():
    running, peak, order = [0], [0], []
    lock = threading.Lock()

    def apply_fn(plan, env):
        with lock:
            running[0] += 1
            peak[0] = max(peak[0], running[0])
        time.sleep(0.05)
        order.append(plan["pr"])
        with lock:
            running[0] -= 1
        return {"ok": True}

    checks = github_app.CheckQueue({}, apply_fn=apply_fn, refusal_fn=lambda env: None).start()
    for n in range(1, 5):
        checks.put({"action": "run", "repo": "demo/repo", "pr": n})
    checks.q.join()
    checks.stop()
    assert peak[0] == 1 and order == [1, 2, 3, 4]


def test_app_checks_count_toward_the_console_daily_cap(tmp_path, monkeypatch):
    monkeypatch.setattr(console_api, "RUNS_ROOT", tmp_path)
    env = {"POC_HOSTED": "1", "POC_DAILY_CAP": "2", "POC_TAVILY_CREDIT_CAP": "100"}
    assert console_api.hosted_budget_refusal(env) is None          # one console check
    ran = []
    checks = github_app.CheckQueue(env, apply_fn=lambda plan, env: ran.append(plan["pr"]) or {"ok": True})
    first = checks.run_one({"action": "run", "repo": "demo/repo", "pr": 1})
    second = checks.run_one({"action": "run", "repo": "demo/repo", "pr": 2})
    assert first["ok"] and ran == [1]
    assert second["action"] == "refuse" and console_api.DAILY_CAP_REACHED in second["why"]
    assert console_api.hosted_budget_refusal(env) is not None       # the console sees the same count


def test_a_local_app_run_is_not_capped(tmp_path, monkeypatch):
    monkeypatch.setattr(console_api, "RUNS_ROOT", tmp_path)
    for k in ("POC_HOSTED", "RENDER", "RENDER_SERVICE_ID", "SPACE_ID", "SYSTEM"):
        monkeypatch.delenv(k, raising=False)
    assert github_app.daily_cap_refusal({}) is None


def _charge(path, n, out):
    env = {"POC_DAILY_CAP": "3", "POC_TAVILY_CREDIT_CAP": "100"}
    for _ in range(n):
        out.put(console_api.hosted_budget_refusal(env, path=path) is None)


def test_daily_counter_holds_across_processes(tmp_path):
    ctx = multiprocessing.get_context("fork")
    out = ctx.Queue()
    path = tmp_path / "_console_daily.json"
    procs = [ctx.Process(target=_charge, args=(path, 3, out)) for _ in range(6)]
    for p in procs:
        p.start()
    for p in procs:
        p.join(30)
    results = [out.get(timeout=5) for _ in range(18)]
    assert results.count(True) == 3
