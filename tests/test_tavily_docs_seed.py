"""The docs-site seed is crawled only when the repository gives too few setup steps, saved crawls stay valid,
and the worst case still counts both seeds. Tavily is always mocked; no key is real."""
import hashlib
import json
import time

import pytest

from poc import tavily_budget, tavily_crawl
from tests.test_tavily_repo_crawl import ENV, REPO, SHA, FakeTavily, _checkout


@pytest.fixture(autouse=True)
def _no_keys(monkeypatch, tmp_path):
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    monkeypatch.delenv(tavily_budget.CAP_ENV, raising=False)
    monkeypatch.setenv(tavily_crawl.CACHE_ENV, str(tmp_path / "cache"))


class ThinRepo(FakeTavily):
    """The repository pages give no setup step, so the docs site is needed."""

    def crawl(self, url, **kw):
        self.crawls.append((url, kw))
        if "github.com" in url:
            return {"results": [{"url": f"https://github.com/acme/widget/blob/{SHA}/README.md",
                                 "raw_content": "A widget."}], "usage": {"credits": 2}}
        return {"results": [{"url": "https://widget.example.org/en/latest/dev.html",
                             "raw_content": 'pip install -e ".[testing]"'}], "usage": {"credits": 2}}

    def extract(self, urls):
        self.extracts.append(list(urls))
        return {"results": [], "usage": {"credits": 1}}


def _crawl(tmp_path, fake):
    return tavily_crawl.crawl_repo(REPO, SHA, _checkout(tmp_path), env=ENV, crawl_fn=fake.crawl,
                                   extract_fn=fake.extract, cache_root=tmp_path / "cache")


def test_docs_seed_skipped_when_the_repository_gives_enough_steps(tmp_path):
    fake = FakeTavily()
    got = _crawl(tmp_path, fake)
    assert [u for u, _ in fake.crawls] == [f"https://github.com/acme/widget/tree/{SHA}"]
    repo_d, docs_d = got["seed_decisions"]
    assert repo_d["crawled"] and not docs_d["crawled"]
    assert docs_d["url"] == "https://widget.example.org/" and docs_d["why"].startswith("skipped:")
    assert got["seeds"] == [f"https://github.com/acme/widget/tree/{SHA}"]


def test_docs_seed_crawled_when_the_repository_gives_too_few_steps(tmp_path):
    fake = ThinRepo()
    got = _crawl(tmp_path, fake)
    assert [u for u, _ in fake.crawls] == [f"https://github.com/acme/widget/tree/{SHA}",
                                           "https://widget.example.org/"]
    assert all(d["crawled"] for d in got["seed_decisions"])
    assert "fewer than" in got["seed_decisions"][1]["why"]
    assert got["credits"] == 5.0


def test_existing_saved_crawl_is_still_hit_without_any_call(tmp_path):
    # An entry written in the format already on disk (no seed_decisions), under the unchanged key formula.
    co = _checkout(tmp_path)
    docs = tavily_crawl.docs_host(co)
    key = f"v{tavily_crawl.CRAWL_VERSION}|{REPO.lower()}@{SHA.lower()}|{docs}"
    root = tmp_path / "cache"
    root.mkdir()
    path = root / (hashlib.sha256(key.encode()).hexdigest()[:32] + ".json")
    assert tavily_crawl._cache_path(root, REPO, SHA, docs) == path
    assert tavily_crawl.CRAWL_VERSION == "2"
    seeds = [f"https://github.com/acme/widget/tree/{SHA}", "https://widget.example.org/"]
    path.write_text(json.dumps({"saved_at": time.time(), "repo": REPO, "base_sha": SHA, "seeds": seeds,
                                "pages": {f"https://github.com/acme/widget/blob/{SHA}/CONTRIBUTING.md": "x"},
                                "full": {}}))

    def boom(*_a, **_k):
        raise AssertionError("a saved crawl must not call Tavily")

    got = tavily_crawl.crawl_repo(REPO, SHA, co, env=ENV, crawl_fn=boom, extract_fn=boom, cache_root=root)
    assert got["cache"]["hit"] and got["calls"] == 0 and got["seeds"] == seeds
    assert [d["url"] for d in got["seed_decisions"]] == seeds and all(d["crawled"] for d in got["seed_decisions"])


def test_new_entry_keeps_the_key_and_is_hit_next_time(tmp_path):
    _crawl(tmp_path, FakeTavily())
    again = FakeTavily()
    got = _crawl(tmp_path, again)
    assert got["cache"]["hit"] and again.crawls == [] and not got["seed_decisions"][1]["crawled"]


def test_worst_case_still_counts_the_conditional_docs_seed():
    bodies = tavily_crawl.worst_case_bodies()
    assert len(bodies["crawl"]) == len(tavily_crawl.seeds(REPO, SHA, "docs.example.org")) == 2
    per_seed = tavily_budget.request_credits("/crawl", bodies["crawl"][0])
    assert per_seed == 16
    repo_only = tavily_budget.worst_case(crawl_bodies=bodies["crawl"][:1])
    assert tavily_budget.REPO_ONLY_CHECK == repo_only == 8 + 16 + 3 == 27
    assert tavily_budget.WORST_CASE_CHECK == repo_only + per_seed == 43


class BarePipRepo(ThinRepo):
    """The repository only says `pip install attrs hypothesis`: two declared packages, no extra or group."""

    def crawl(self, url, **kw):
        if "github.com" in url:
            self.crawls.append((url, kw))
            return {"results": [{"url": f"https://github.com/acme/widget/blob/{SHA}/README.md",
                                 "raw_content": "Install: `pip install attrs hypothesis`"}], "usage": {"credits": 2}}
        return super().crawl(url, **kw)


def test_bare_multi_package_pip_line_does_not_skip_the_docs_seed(tmp_path):
    fake = BarePipRepo()
    got = _crawl(tmp_path, fake)
    backed = [s for s in got["steps"] if s["used"] and s["kind"] == "package"]
    assert len(backed) >= tavily_crawl.MIN_REPO_STEPS   # enough steps by count alone
    assert [u for u, _ in fake.crawls][-1] == "https://widget.example.org/"
    docs_d = got["seed_decisions"][1]
    assert docs_d["crawled"] and "no extra, dependency group or requirements file" in docs_d["why"]
