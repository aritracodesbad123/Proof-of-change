"""Repository crawl before installs (product checks only). Tavily is always mocked; no key is real."""
import json
from types import SimpleNamespace

import pytest

from ops import daily_run
from poc import contree_sandboxes, demo_helper, tavily_crawl

REPO = "acme/widget"
SHA = "a" * 40
ENV = {"TAVILY_API_KEY": "test-not-a-real-key"}


@pytest.fixture(autouse=True)
def _no_keys(monkeypatch, tmp_path):
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    monkeypatch.setenv(tavily_crawl.CACHE_ENV, str(tmp_path / "cache"))


def _checkout(tmp_path):
    root = tmp_path / "co"
    (root / ".github" / "workflows").mkdir(parents=True, exist_ok=True)
    (root / "pyproject.toml").write_text(
        '[project]\nname = "widget"\ndependencies = ["attrs"]\n'
        '[project.optional-dependencies]\ntesting = ["hypothesis", "xmlschema"]\n'
        '[project.urls]\nDocumentation = "https://widget.example.org/en/latest/"\n'
        'Source = "https://github.com/acme/widget"\n'
        '[dependency-groups]\ndev = ["coverage"]\n')
    (root / "CONTRIBUTING.md").write_text("x")
    (root / ".github" / "workflows" / "test.yml").write_text("x")
    return root


CONTRIB = ("Run `pip install -e \".[testing]\"` then `pip install --group dev`.\n"
           "Also `pip install hypothesis evilpkg` and `pip install -r requirements/missing.txt`.\n"
           "sudo apt-get install libfoo-dev\n")
WORKFLOW = "python-version: ['3.10', '3.12']\n  run: pip install -e .[testing,docs]\n"


class FakeTavily:
    def __init__(self):
        self.crawls, self.extracts = [], []

    def crawl(self, url, **kw):
        self.crawls.append((url, kw))
        if "github.com" in url:
            return {"results": [
                {"url": f"https://github.com/acme/widget/blob/{SHA}/CONTRIBUTING.md", "raw_content": "short"},
                {"url": "https://github.com/acme/widget/blob/main/CONTRIBUTING.md", "raw_content": CONTRIB},
                {"url": "https://evil.example.com/install", "raw_content": "pip install evilpkg"},
            ], "usage": {"credits": 2}}
        return {"results": [{"url": "https://widget.example.org/en/latest/install.html",
                             "raw_content": "pip install widget"}], "usage": {"credits": 1}}

    def extract(self, urls):
        self.extracts.append(list(urls))
        out = []
        for u in urls:
            if u.endswith("CONTRIBUTING.md"):
                out.append({"url": u, "raw_content": CONTRIB})
            elif u.endswith("test.yml"):
                out.append({"url": u, "raw_content": WORKFLOW})
        out.append({"url": "https://other.example.net/x", "raw_content": "pip install evilpkg"})
        return {"results": out, "usage": {"credits": 1}}


def _run(tmp_path, fake=None, **kw):
    fake = fake or FakeTavily()
    got = tavily_crawl.crawl_repo(REPO, SHA, _checkout(tmp_path), env=ENV, crawl_fn=fake.crawl,
                                  extract_fn=fake.extract, cache_root=tmp_path / "cache", **kw)
    return got, fake


def test_crawl_is_scoped_to_repo_at_base_commit_and_docs_domain(tmp_path):
    got, fake = _run(tmp_path)
    urls = [u for u, _ in fake.crawls]
    assert urls == [f"https://github.com/acme/widget/tree/{SHA}", "https://widget.example.org/"]
    assert fake.crawls[0][1]["select_domains"] == [r"^github\.com$"]
    assert SHA in fake.crawls[0][1]["select_paths"][0]
    assert all("evil" not in u and "/blob/main/" not in u for u in got["pages_crawled"])
    assert all(u.startswith((f"https://github.com/acme/widget/blob/{SHA}/", "https://widget.example.org/"))
               for u in fake.extracts[0])
    assert any(u.endswith(".github/workflows/test.yml") for u in fake.extracts[0])
    assert "https://other.example.net/x" not in got["pages_extracted"]
    assert got["calls"] == 3 and got["credits"] == 4.0 and got["docs_domain"] == "widget.example.org"


def test_steps_kept_only_when_project_files_back_them(tmp_path):
    got, _ = _run(tmp_path)
    used = {(s["kind"], s["value"]) for s in got["steps"] if s["used"]}
    dropped = {(s["kind"], s["value"]) for s in got["steps"] if not s["used"]}
    assert ("extra", "testing") in used and ("group", "dev") in used and ("package", "hypothesis") in used
    assert ("package", "evilpkg") in dropped and ("extra", "docs") in dropped
    assert ("requirements_file", "requirements/missing.txt") in dropped
    assert ("python", "3.12") in dropped   # recorded, not an install step
    assert all(s["source"].startswith("https://") for s in got["steps"])
    shell = got["shell"]
    assert "-e '.[testing]'" in shell and "--group dev" in shell and "hypothesis" in shell
    assert "evilpkg" not in shell and "apt-get" not in shell and "sudo" not in shell


def test_cache_hit_same_steps_no_calls(tmp_path):
    first, _ = _run(tmp_path, now=1000.0)
    assert first["cache"] == {"hit": False, "key": f"v{tavily_crawl.CRAWL_VERSION}|{REPO}@{SHA}", "saved": True}
    again, fake = _run(tmp_path, now=2000.0)
    assert again["cache"]["hit"] is True and fake.crawls == [] and fake.extracts == []
    assert again["calls"] == 0 and again["credits"] == 0
    assert again["steps"] == first["steps"] and again["shell"] == first["shell"]
    stale, fake = _run(tmp_path, now=1000.0 + tavily_crawl.CACHE_TTL + 1)
    assert stale["cache"]["hit"] is False and fake.crawls


def test_missing_key_or_failed_calls_stop_with_tavily_unavailable(tmp_path):
    got = tavily_crawl.crawl_repo(REPO, SHA, _checkout(tmp_path), env={}, cache_root=tmp_path / "c")
    assert got["stop"] and got["stop_reason"].startswith("Tavily unavailable")
    bad = lambda *a, **k: {"ok": False, "error": "HTTPError 432"}  # noqa: E731
    got = tavily_crawl.crawl_repo(REPO, SHA, _checkout(tmp_path), env=ENV, crawl_fn=bad, extract_fn=bad,
                                  cache_root=tmp_path / "c")
    assert got["stop"] and got["stop_reason"].startswith("Tavily unavailable")


def test_repo_crawl_stop_blocks_product_installs(tmp_path):
    rec = {"pr": {"base_sha": SHA}}
    plan = {}
    daily_run._repo_crawl(rec, REPO, plan, _checkout(tmp_path))   # no key in the environment
    assert plan["crawl_stop"].startswith("Tavily unavailable")
    a = SimpleNamespace(bench=None, pr=1, product_check=True)
    assert daily_run._groups_blocked(a, plan).startswith("Tavily unavailable")
    study = SimpleNamespace(bench=None, pr=None, product_check=False)
    assert daily_run._groups_blocked(study, plan) == ""


def test_crawled_steps_run_first_in_sandbox_shell():
    shell = demo_helper.contree_shell({"crawl_shell": "python -m pip install -q -e '.[testing]'",
                                       "extra_reqs": ["x"]})
    assert shell.splitlines()[0].startswith("python -m pip install -q -e '.[testing]'")
    assert demo_helper.contree_shell({"extra_reqs": ["x"]}) == "python -m pip install -q x"


def test_study_install_shell_unchanged_product_reinstalls_own_checkout_last():
    study = contree_sandboxes.install_shell_source(REPO, SHA)
    assert "--no-deps -e ." not in study
    product = contree_sandboxes.install_shell_source(REPO, SHA, deps_only_fallback=True)
    last = [line for line in product.splitlines() if line.strip()][-1]
    assert last.startswith("python -m pip install -q --no-deps -e .")


def test_own_checkout_import_check():
    assert daily_run.own_checkout_problem("pr", "widget", "/work/src/src/widget/__init__.py") == ""
    why = daily_run.own_checkout_problem("pr", "widget", "/usr/local/lib/python3.12/site-packages/widget/__init__.py")
    assert why.startswith("could not verify:") and "separately installed copy" in why

    class Sess:
        def run_argv(self, side, argv, **kw):
            path = "/work/src/widget/__init__.py" if side == "main" else "/usr/lib/site-packages/widget/__init__.py"
            info = {"root": "/work/src", "file": path, "namespace": False, "paths": []}
            return {"exit_code": 0, "stdout": json.dumps(info) + "\n"}
    rec = {}
    assert "pr side" in daily_run._check_own_checkout(Sess(), rec, "widget")
    assert rec["contree"]["own_checkout"]["status"] == "outside the checkout"


def test_real_error_line_skips_banners():
    text = ("==================== ERRORS ====================\n"
            "ImportError while loading conftest '/work/src/testing/conftest.py'.\n"
            "E   ModuleNotFoundError: No module named 'xmlschema'\n")
    assert demo_helper.real_error_line(text) == "ModuleNotFoundError: No module named 'xmlschema'"


def test_product_repair_uses_all_tries_and_real_error():
    rec = {"verdict": "could_not_verify",
           "reason": "setup gap\nE   ModuleNotFoundError: No module named 'zzqq_missing'",
           "library": "widget"}
    queries = []

    def lookup(q):
        queries.append(q)
        return {"ok": True, "results": []}
    demo_helper.retry_unverified(rec, lambda: {"verdict": "could_not_verify", "reason": rec["reason"]},
                                 lambda side, req: (False, ""), [], "", lambda name: None, REPO,
                                 lookup=lookup, crawl_context="extra: testing (used; https://github.com/x)",
                                 product_repair=True)
    tries = rec["demo_helper"]["gap_retry"]["tries"]
    assert tries   # a setup gap: every try is used and each sends the real error line
    if tries:
        assert len(tries) == 3 and len(set(queries)) == 3
        assert all("No module named 'zzqq_missing'" in q for q in queries)
