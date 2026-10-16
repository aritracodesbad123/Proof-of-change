"""Contree / GitHub App / Serverless / MCP / Tavily surfaces (Phases B–D)."""
from __future__ import annotations

from pathlib import Path

from poc import contree_sandboxes, github_app, mcp_server, serverless, tavily_docs


def test_contree_falls_back_without_key(monkeypatch):
    monkeypatch.delenv("CONTREE_API_KEY", raising=False)
    backend, note = contree_sandboxes.select("contree")
    assert backend == "local"
    assert "CONTREE_API_KEY" in note


def test_contree_select_with_key(monkeypatch, tmp_path):
    monkeypatch.setenv("CONTREE_API_KEY", "fake")
    backend, note = contree_sandboxes.select("contree")
    assert backend == "contree"
    cp = contree_sandboxes.checkpoint_main("abc123deadbeef", tmp_path)
    assert cp["backend"] == "contree" and Path(cp["path"]).is_dir()
    pr = contree_sandboxes.fork_pr(cp, "def456cafebabe", tmp_path)
    assert pr["kind"] == "pr"


def test_github_app_g_ext_and_prove():
    assert github_app.parse_prove("hello") is None
    assert github_app.parse_prove('/prove "adds cache"') == "adds cache"
    assert not github_app.may_post("psf/requests", env={})
    assert github_app.may_post("me/demo", env={"POC_DEMO_REPOS": "me/demo"})
    plan = github_app.handle_event(
        "issue_comment",
        {"action": "created", "comment": {"body": "/prove"}, "repository": {"full_name": "me/demo"},
         "issue": {"number": 3}},
        env={"POC_DEMO_REPOS": "me/demo"})
    assert plan["action"] == "prove" and plan["pr"] == 3


def test_hosted_report_writes_html(tmp_path):
    path = github_app.write_hosted_report(
        {"id": "t1", "verdict": "verified", "reason": "ok", "repo": "me/demo",
         "machine": "local", "behaviour_claims": [], "probes": {"items": []}},
        tmp_path)
    assert path.is_file() and "Proof-of-Change" in path.read_text()


def test_serverless_orchestrate_dry_run():
    out = serverless.orchestrate(
        {"repo": "me/demo", "pr": 1, "dry_run": True},
        env={"POC_DEMO_REPOS": "me/demo"})
    assert out["ok"] and out["dry_run"]


def test_mcp_tools_and_prove_dry():
    names = {t["name"] for t in mcp_server.list_tools()}
    assert names == {"prove_change", "run_probe"}
    out = mcp_server.dispatch("prove_change", {"repo": "o/r", "pr": 1, "dry_run": True})
    assert out["ok"] and out["dry_run"]


def test_tavily_skipped_without_key(monkeypatch):
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    assert not tavily_docs.available()
    assert tavily_docs.lookup("pandas changelog")["ok"] is False
