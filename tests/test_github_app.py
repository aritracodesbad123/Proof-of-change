"""GitHub App: webhook, G-ext, dry-run apply, mocked posts, hosted HTML."""
from __future__ import annotations

import hashlib
import hmac
from pathlib import Path

from poc import github_app


def test_verify_webhook():
    secret, body = "s3cret", b'{"ok":true}'
    sig = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    assert github_app.verify_webhook(body, sig, secret)
    assert not github_app.verify_webhook(body, "sha256=dead", secret)
    assert not github_app.verify_webhook(body, sig, None)


def test_refuse_non_demo(monkeypatch):
    monkeypatch.setenv("POC_DEMO_REPOS", "me/demo")
    plan = github_app.handle_event(
        "issue_comment",
        {"action": "created", "comment": {"body": "/prove"}, "repository": {"full_name": "psf/requests"},
         "issue": {"number": 1, "pull_request": {}}},
        env={"POC_DEMO_REPOS": "me/demo"})
    assert plan["action"] == "refuse"


def test_prove_on_a_plain_issue_is_ignored():
    plan = github_app.handle_event(
        "issue_comment",
        {"action": "created", "comment": {"body": "/prove"}, "repository": {"full_name": "me/demo"},
         "issue": {"number": 4}},
        env={"POC_DEMO_REPOS": "me/demo"})
    assert plan["action"] == "ignore"
    assert "pull request" in plan["why"]


def test_prove_on_a_pull_request_still_plans():
    plan = github_app.handle_event(
        "issue_comment",
        {"action": "created", "comment": {"body": "/prove"}, "repository": {"full_name": "me/demo"},
         "issue": {"number": 9, "pull_request": {}}},
        env={"POC_DEMO_REPOS": "me/demo"})
    assert plan == {"action": "prove", "repo": "me/demo", "claim": "", "pr": 9}


def test_pull_request_plan():
    plan = github_app.handle_event(
        "pull_request",
        {"action": "opened", "repository": {"full_name": "me/demo"},
         "pull_request": {"number": 9, "head": {"sha": "abc"}}},
        env={"POC_DEMO_REPOS": "me/demo"})
    assert plan == {"action": "run", "repo": "me/demo", "event": "pull_request", "pr": 9, "head_sha": "abc"}


def test_apply_dry_run_writes_hosted(tmp_path, monkeypatch):
    monkeypatch.setenv("POC_DEMO_REPOS", "me/demo")
    monkeypatch.delenv("GITHUB_APP_INSTALLATION_TOKEN", raising=False)
    rec = {"id": "pr-me-demo-1", "verdict": "verified", "reason": "ok", "repo": "me/demo",
           "pr": {"number": 1, "head_sha": "deadbeef"}, "behaviour_claims": [{"id": "c1", "text": "x"}],
           "probes": {"items": []}, "explanation": {"text": "summary line"}}
    plan = {"action": "prove", "repo": "me/demo", "pr": 1, "record": rec, "head_sha": "deadbeef"}
    out = github_app.apply(plan, dry_run=True, env={"POC_DEMO_REPOS": "me/demo"}, hosted_dir=tmp_path)
    assert out["ok"] and out["dry_run"]
    path = Path(out["github_app"]["report_path"])
    assert path.is_file() and "verified" in path.read_text() and "Behavior map" in path.read_text()


def test_apply_posts_with_mock(tmp_path, monkeypatch):
    monkeypatch.setenv("POC_DEMO_REPOS", "me/demo")
    monkeypatch.setenv("GITHUB_APP_INSTALLATION_TOKEN", "tok")
    monkeypatch.setenv("POC_REPORT_BASE_URL", "https://example.test/r")
    posts = []

    def fake_http(method, url, *, token, body=None, extra_headers=None):
        posts.append({"method": method, "url": url, "body": body})
        if "check-runs" in url:
            return {"id": 11, "html_url": "https://github.com/me/demo/runs/11"}
        return {"id": 22, "html_url": "https://github.com/me/demo/issues/1#issuecomment-22"}

    monkeypatch.setattr(github_app, "_http_json", fake_http)
    rec = {"id": "pr-me-demo-2", "verdict": "needs_attention", "reason": "diff", "repo": "me/demo",
           "pr": {"number": 2, "head_sha": "cafebabe"}, "behaviour_claims": [], "probes": {"items": []}}
    plan = {"action": "run", "repo": "me/demo", "pr": 2, "record": rec, "head_sha": "cafebabe"}
    out = github_app.apply(plan, dry_run=False, env={
        "POC_DEMO_REPOS": "me/demo", "GITHUB_APP_INSTALLATION_TOKEN": "tok",
        "POC_REPORT_BASE_URL": "https://example.test/r"},
        runner=lambda argv: 0, hosted_dir=tmp_path)
    assert out["ok"] and not out["dry_run"]
    assert out["github_app"]["check_run_id"] == 11
    assert any("check-runs" in p["url"] for p in posts)
    assert any("comments" in p["url"] for p in posts)
    assert posts[0]["body"]["conclusion"] in ("success", "neutral")
    assert posts[0]["body"]["conclusion"] != "failure"


def test_check_run_never_failure():
    p = github_app.check_run_payload("me/demo", "sha", "could_not_verify", "why",
                                     env={"POC_DEMO_REPOS": "me/demo"})
    assert p["conclusion"] == "neutral"
    p2 = github_app.check_run_payload("me/demo", "sha", "verified", "ok",
                                      env={"POC_DEMO_REPOS": "me/demo"})
    assert p2["conclusion"] == "success"


def test_installation_token_from_env(monkeypatch):
    monkeypatch.setenv("GITHUB_APP_INSTALLATION_TOKEN", "inst-tok")
    assert github_app.installation_token() == "inst-tok"


def test_report_url_for():
    assert github_app.report_url_for(Path("x.html"), env={}) is None
    assert github_app.report_url_for(Path("x.html"), env={"POC_REPORT_BASE_URL": "https://h/t/"}) == "https://h/t/x.html"
