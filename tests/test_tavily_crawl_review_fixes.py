"""Review fixes for the repository crawl: finish() on a Tavily stop, code-only GitHub scope, redacted repair search,
symlink-safe and namespace-aware import origin, versioned cache key, untrusted version pins, commit matching.
Tavily is always mocked; no key is real."""
import inspect
import json
import subprocess
import time
from types import SimpleNamespace

import pytest

from ops import daily_run
from poc import demo_helper, tavily_crawl

REPO = "acme/widget"
SHA = "b" * 40


@pytest.fixture(autouse=True)
def _no_keys(monkeypatch, tmp_path):
    for name in ("TAVILY_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY", "XAI_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv(tavily_crawl.CACHE_ENV, str(tmp_path / "cache"))


# 1. A Tavily stop on the product route still goes through finish(): record.json, PDF step and cleanup.
def test_tavily_unavailable_product_route_writes_could_not_verify_record(tmp_path, monkeypatch):
    monkeypatch.setattr(daily_run, "_CONTREE_ONLY", False, raising=False)
    monkeypatch.setattr(demo_helper, "begin_check", lambda *a, **k: None)
    side_main = tmp_path / "work" / "side-main"
    side_main.mkdir(parents=True)
    (side_main / "pyproject.toml").write_text('[project]\nname = "widget"\n')
    sp = {"ok": True, "main_sha": SHA, "pr_sha": "c" * 40, "comparison_basis": "base tip"}
    monkeypatch.setattr(daily_run, "source_pair", lambda *a, **k: dict(sp))
    installs = []
    monkeypatch.setattr(daily_run, "_install_with_helper", lambda *a, **k: installs.append(a) or (False, "x"))
    a = SimpleNamespace(bench=None, pr=7, product_check=True, python="python3", build_timeout=60, swarm=False,
                        provider=None, model_skipped="no model in this test")
    rec = {"pr": {"number": 7, "base_sha": SHA}, "verdict": None, "reason": "", "freeze": {},
           "files": {"package_py": ["widget/x.py"], "compiled": [], "other": [], "tests": []}}
    item = {"pr": 7, "base_ref": "main", "head_sha": "c" * 40}
    prdir, work = tmp_path / "out", tmp_path / "work"
    prdir.mkdir()
    out = daily_run.test_source_pair(REPO, {"dist": "widget", "pkg": "widget"}, item, prdir, work, a, rec)
    assert installs == []   # stopped before any install
    assert out["verdict"] == "could_not_verify" and "Tavily unavailable" in out["reason"]
    finished = daily_run.finish(out, prdir, work, time.time(), a)
    record = json.loads((prdir / "record.json").read_text())
    assert record["verdict"] == "could_not_verify" and "Tavily unavailable" in record["reason"]
    assert finished["verdict"] == "could_not_verify"


def test_source_pair_is_only_reached_through_finish():
    src = inspect.getsource(daily_run)
    lines = [line.strip() for line in src.splitlines()]
    calls = [x for x in lines if "test_source_pair(" in x and not x.startswith(("def ", "#"))]
    assert calls and all(c.startswith("return finish(test_source_pair(") for c in calls)


# 2. On GitHub only code at the base commit is in scope.
@pytest.mark.parametrize("path,ok", [
    (f"/acme/widget/tree/{SHA}", True),
    (f"/acme/widget/blob/{SHA}/CONTRIBUTING.md", True),
    ("/acme/widget", False),
    ("/acme/widget/issues/12", False),
    ("/acme/widget/pull/3", False),
    ("/acme/widget/discussions/9", False),
    ("/acme/widget/wiki/Setup", False),
    ("/acme/widget/blob/main/CONTRIBUTING.md", False),
    (f"/acme/widget/blob/{SHA}x/README.md", False),
    (f"/other/widget/blob/{SHA}/README.md", False),
])
def test_github_scope_is_tree_or_blob_at_base_commit(path, ok):
    assert tavily_crawl.in_scope("https://github.com" + path, REPO, SHA) is ok


# Repair search is redacted before it reaches Tavily.
def test_repair_search_is_redacted(monkeypatch):
    secret = "sk-test-not-a-real-secret-123456"
    monkeypatch.setenv("OPENAI_API_KEY", secret)
    rec = {"verdict": "could_not_verify", "reason": f"setup gap\nE   ModuleNotFoundError: token={secret} x"}
    queries = []
    demo_helper.retry_unverified(rec, lambda: {"verdict": "could_not_verify", "reason": rec["reason"]},
                                 lambda side, req: (False, ""), [], "", lambda name: None, REPO,
                                 lookup=lambda q: queries.append(q) or {"ok": True, "results": []},
                                 crawl_context="", product_repair=True)
    assert queries and all(secret not in q for q in queries)


# Import origin: the checkout path resolved inside the sandbox; namespace packages get their own status.
class _Sess:
    def __init__(self, by_side):
        self.by_side, self.codes = by_side, []

    def run_argv(self, side, argv, **kw):
        self.codes.append(argv[-1])
        return {"exit_code": 0, "stdout": json.dumps(self.by_side[side]) + "\n"}


def test_import_origin_uses_real_checkout_path_inside_sandbox():
    real = "/mnt/data/src"
    sess = _Sess({s: {"root": real, "file": f"{real}/widget/__init__.py", "namespace": False, "paths": []}
                  for s in ("main", "pr")})
    rec = {}
    assert daily_run._check_own_checkout(sess, rec, "widget") is None
    assert rec["contree"]["own_checkout"]["status"] == "ok"
    assert "os.path.realpath('/work/src')" in sess.codes[0]
    outside = _Sess({s: {"root": real, "file": "/usr/lib/site-packages/widget/__init__.py", "namespace": False,
                         "paths": []} for s in ("main", "pr")})
    assert "separately installed copy" in daily_run._check_own_checkout(outside, {}, "widget")


def test_namespace_package_has_its_own_status():
    ns = {"root": "/work/src", "file": "", "namespace": True, "paths": ["/work/src/widget"]}
    rec = {}
    assert daily_run._check_own_checkout(_Sess({"main": ns, "pr": ns}), rec, "widget") is None
    oc = rec["contree"]["own_checkout"]
    assert oc["status"].startswith("namespace package") and oc["pr"].startswith("namespace package")
    away = {"root": "/work/src", "file": "", "namespace": True, "paths": ["/usr/lib/site-packages/widget"]}
    rec = {}
    assert "separately installed copy" in daily_run._check_own_checkout(_Sess({"main": ns, "pr": away}), rec, "widget")
    assert rec["contree"]["own_checkout"]["status"] == "outside the checkout"


def test_namespace_package_detected_for_real(tmp_path):
    (tmp_path / "nspkg").mkdir()
    code = daily_run._ORIGIN_CODE.format(root=str(tmp_path), module="nspkg")
    out = subprocess.run(["python3", "-c", code], cwd=tmp_path, capture_output=True, text=True, check=True)
    info = json.loads(out.stdout.strip().splitlines()[-1])
    assert info["namespace"] is True and info["paths"] == [str(tmp_path.resolve() / "nspkg")]


# Cache key carries a code version.
def test_cache_key_has_version(tmp_path, monkeypatch):
    a = tavily_crawl._cache_path(tmp_path, REPO, SHA, "")
    monkeypatch.setattr(tavily_crawl, "CRAWL_VERSION", "999")
    assert tavily_crawl._cache_path(tmp_path, REPO, SHA, "") != a


# Version pins from web pages are dropped unless the project's own files list that exact version.
def test_crawled_version_pins_dropped_unless_project_pins_them(tmp_path):
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "widget"\ndependencies = ["attrs", "pluggy==1.5.0"]\n')
    steps = tavily_crawl.parse_steps("pip install attrs==21.1 pluggy==1.5.0 pluggy==9.9", "https://x")
    rows = {s["value"]: s for s in tavily_crawl.merge_steps(steps, tmp_path)}
    kept = [s["value"] for s in tavily_crawl.merge_steps(steps, tmp_path) if s["used"]]
    assert "attrs" in kept and "attrs==21.1" not in kept   # pin dropped, package kept
    assert "pluggy==1.5.0" in kept                         # the project's own exact pin
    assert "pluggy==9.9" not in kept
    shell = tavily_crawl.steps_shell(tavily_crawl.merge_steps(steps, tmp_path))
    assert "21.1" not in shell and "9.9" not in shell
    assert rows


# Crawl base commit and checkout commit are both recorded and must match.
def _git_checkout(path):
    path.mkdir()
    run = lambda *a: subprocess.run(["git", "-C", str(path), *a], check=True, capture_output=True, text=True)  # noqa
    run("init", "-q")
    (path / "pyproject.toml").write_text('[project]\nname = "widget"\n')
    run("add", ".")
    run("-c", "user.name=t", "-c", "user.email=t@example.com", "commit", "-qm", "x")
    return run("rev-parse", "HEAD").stdout.strip()


def test_crawl_and_checkout_commits_recorded_and_matched(tmp_path, monkeypatch):
    co = tmp_path / "co"
    sha = _git_checkout(co)
    calls = []
    monkeypatch.setattr(tavily_crawl, "crawl_repo", lambda repo, base, *a, **k: calls.append(base) or
                        {"ok": True, "stop": False, "steps": [], "shell": "", "calls": 1, "credits": 1.0,
                         "pages_crawled": [], "pages_extracted": [], "errors": [], "context": ""})
    rec = {"pr": {"base_sha": "f" * 40, "tested_main_sha": sha}}
    plan = {}
    stored = daily_run._repo_crawl(rec, REPO, plan, co)
    assert calls == [sha]   # the crawl reads the commit that is tested
    assert stored["crawl_base_sha"] == sha and stored["checkout_sha"] == sha and stored["commits_match"] is True
    assert "crawl_stop" not in plan

    rec = {"pr": {"base_sha": "f" * 40}}
    plan = {}
    stored = daily_run._repo_crawl(rec, REPO, plan, co)
    assert stored["commits_match"] is False and stored["checkout_sha"] == sha
    assert plan["crawl_stop"] and stored["applied_in_sandbox"] is False
