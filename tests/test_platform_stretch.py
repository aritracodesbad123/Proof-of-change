"""Contree / GitHub App / Serverless / MCP / Tavily surfaces."""
from __future__ import annotations

from pathlib import Path

from poc import contree_sandboxes, github_app, mcp_server, serverless, tavily_docs


def test_contree_falls_back_without_keys(monkeypatch):
    monkeypatch.delenv("NEBIUS_API_KEY", raising=False)
    monkeypatch.delenv("NEBIUS_PROJECT_ID", raising=False)
    monkeypatch.delenv("CONTREE_API_KEY", raising=False)
    backend, note = contree_sandboxes.select("contree")
    assert backend == "local"
    assert "NEBIUS_API_KEY" in note and "NEBIUS_PROJECT_ID" in note


def test_contree_falls_back_without_project_id(monkeypatch):
    monkeypatch.setenv("NEBIUS_API_KEY", "fake")
    monkeypatch.delenv("NEBIUS_PROJECT_ID", raising=False)
    backend, note = contree_sandboxes.select("contree")
    assert backend == "local"
    assert "NEBIUS_PROJECT_ID" in note


def test_contree_require_refuses(monkeypatch):
    monkeypatch.delenv("NEBIUS_API_KEY", raising=False)
    monkeypatch.delenv("NEBIUS_PROJECT_ID", raising=False)
    monkeypatch.setenv("POC_REQUIRE_CONTREE", "1")
    try:
        contree_sandboxes.select("contree")
        assert False, "expected ContreeError"
    except contree_sandboxes.ContreeError as e:
        assert "STOPPED" in str(e) and "NEBIUS_API_KEY" in str(e)


def test_contree_select_with_keys_and_mock_session(monkeypatch, tmp_path):
    monkeypatch.setenv("NEBIUS_API_KEY", "fake")
    monkeypatch.setenv("NEBIUS_PROJECT_ID", "proj-fake")
    # Pretend the SDK is importable even when it is not installed in CI.
    import sys
    import types
    if "contree_sdk" not in sys.modules:
        sys.modules["contree_sdk"] = types.ModuleType("contree_sdk")
    backend, note = contree_sandboxes.select("contree")
    assert backend == "contree"
    assert "contree" in note

    calls = []

    async def runner(shell, disposable, image_ref, timeout, files=None):
        calls.append({"shell": shell, "disposable": disposable, "ref": image_ref, "files": files})
        if not disposable:
            return {"exit_code": 0, "stdout": "", "stderr": "",
                    "uuid": "main-uuid" if image_ref is None else "pr-uuid"}
        return {"exit_code": 0, "stdout": "ready\n", "stderr": "", "uuid": None}

    # ContreeSession._run_on is sync and calls runner; our mock is sync-friendly via ContreeSession
    def sync_runner(shell, disposable, image_ref, timeout, files=None):
        calls.append({"shell": shell, "disposable": disposable, "ref": image_ref, "files": files})
        if not disposable:
            return {"exit_code": 0, "stdout": "", "stderr": "",
                    "uuid": "main-uuid" if image_ref is None else "pr-uuid"}
        return {"exit_code": 0, "stdout": "ready\n", "stderr": "", "uuid": None}

    sess = contree_sandboxes.ContreeSession(runner=sync_runner)
    main = sess.checkpoint_main("printf ready > /work/status.txt")
    assert main["uuid"] == "main-uuid" and main["disposable"] is False
    pr = sess.fork_pr("printf pr > /work/status.txt")
    assert pr["uuid"] == "pr-uuid" and pr["from"] == "main-uuid"
    got = sess.run_op("main", "cat /work/status.txt", disposable=True)
    assert got["exit_code"] == 0 and "ready" in got["stdout"]
    assert any(c["disposable"] is False for c in calls)
    cp = contree_sandboxes.checkpoint_main("abc123deadbeef", tmp_path)
    # without a live session on module state, marker path is created
    assert Path(cp["path"]).is_dir() or cp.get("uuid")


def test_contree_prepare_source_pair_mock():
    def sync_runner(shell, disposable, image_ref, timeout, files=None):
        if not disposable:
            return {"exit_code": 0, "stdout": "", "stderr": "",
                    "uuid": "main-uuid" if image_ref is None else "pr-uuid"}
        return {"exit_code": 0, "stdout": "ok", "stderr": "", "uuid": None}

    sess = contree_sandboxes.prepare_source_pair(
        "owner/repo", "aaa", "bbb", runner=sync_runner)
    assert sess.main_uuid == "main-uuid" and sess.pr_uuid == "pr-uuid"
    d = sess.describe()
    assert d["max_ops"] <= 40 and d["sdk"] == "0.3.6"


def test_github_app_g_ext_and_prove():
    assert github_app.parse_prove("hello") is None
    assert github_app.parse_prove('/prove "adds cache"') == "adds cache"
    assert not github_app.may_post("psf/requests", env={})
    assert github_app.may_post("me/demo", env={"POC_DEMO_REPOS": "me/demo"})
    plan = github_app.handle_event(
        "issue_comment",
        {"action": "created", "comment": {"body": "/prove"}, "repository": {"full_name": "me/demo"},
         "issue": {"number": 3, "pull_request": {}}},
        env={"POC_DEMO_REPOS": "me/demo"})
    assert plan["action"] == "prove" and plan["pr"] == 3


def test_hosted_report_writes_html(tmp_path):
    path = github_app.write_hosted_report(
        {"id": "t1", "verdict": "verified", "reason": "ok", "repo": "me/demo",
         "machine": "local", "behaviour_claims": [], "probes": {"items": []}},
        tmp_path)
    html = path.read_text()
    assert path.is_file() and "Proof-of-Change" in html
    assert "Background (related public bug reports, not used for the verdict)" not in html


def test_hosted_report_labels_related_bug_reports(tmp_path):
    label = "Background (related public bug reports, not used for the verdict)"
    text = '"Window bug" <not a tag>'
    path = github_app.write_hosted_report(
        {"id": "t2", "verdict": "verified", "reason": "ok", "repo": "me/demo",
         "machine": "local", "behaviour_claims": [], "probes": {"items": []},
         "related_reports": {"status": "ok", "text": text, "items": [], "untrusted": True}},
        tmp_path)
    html = path.read_text()
    assert f"<h2>{label}</h2>" in html
    assert "&lt;not a tag&gt;" in html
    assert "<not a tag>" not in html


def test_serverless_orchestrate_dry_run():
    out = serverless.orchestrate(
        {"repo": "me/demo", "pr": 1, "dry_run": True},
        env={"POC_DEMO_REPOS": "me/demo"})
    assert out["ok"] and out["dry_run"]


def test_serverless_orchestrate_enqueues(monkeypatch):
    from poc import console_api

    class FakeThread:
        def __init__(self, target=None, daemon=None):
            self.target = target

        def start(self):
            pass

    monkeypatch.setattr(console_api.threading, "Thread", FakeThread)
    monkeypatch.setattr(console_api, "console_run_flags", lambda *_a, **_k: console_api.ConsoleRunPlan([], None, False, None))
    out = serverless.orchestrate(
        {"pr_url": "https://github.com/me/demo/pull/9", "allow_any_repo": True},
        env={"POC_DEMO_REPOS": ""})
    assert out["ok"] and out["queued"] and out["job"]["pr"] == 9
    assert out["job"]["current_stage"] == "queued"


def test_mcp_tools_and_prove_dry():
    names = {t["name"] for t in mcp_server.list_tools()}
    assert names == {"prove_change", "run_probe"}
    out = mcp_server.dispatch("prove_change", {"repo": "o/r", "pr": 1, "dry_run": True})
    assert out["ok"] and out["dry_run"]


def test_tavily_skipped_without_key(monkeypatch):
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    assert not tavily_docs.available()
    got = tavily_docs.lookup("pandas changelog")
    assert got["ok"] is False
    assert got["error"] == tavily_docs.MISSING_KEY
    assert got.get("refused") is True
    assert got["results"] == []
    assert "skipped" not in got["error"].lower()


def test_contree_smoke_skipped_without_creds(monkeypatch):
    monkeypatch.delenv("NEBIUS_API_KEY", raising=False)
    monkeypatch.delenv("NEBIUS_PROJECT_ID", raising=False)
    out = contree_sandboxes.smoke(env={})
    assert out["skipped"] is True and out["ok"] is False


def test_contree_live_smoke_optional():
    """Live Contree smoke when POC_CONTREE_SMOKE=1 and Nebius credentials are present."""
    import os
    if os.environ.get("POC_CONTREE_SMOKE") not in ("1", "true", "yes"):
        return
    out = contree_sandboxes.smoke()
    assert not out.get("skipped"), out
    assert out.get("ok"), out
