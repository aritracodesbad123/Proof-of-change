"""Demo helper: setup plan, safe installs, Tavily notes, and one setup-gap rerun. No network."""
from __future__ import annotations

import json
import os
from types import SimpleNamespace

import pytest

from ops.daily_run import verdict_for
from poc import contree_sandboxes, demo_helper

REPO = "acme/widget"
LINK = {"home_page": "https://github.com/acme/widget"}
OTHER = {"home_page": "https://github.com/other/mystery"}


def _checkout(root, *, python=">=3.11", requirements="scipy==1.2\nwidget\n"):
    root.mkdir(parents=True, exist_ok=True)
    (root / "pyproject.toml").write_text(
        "[project]\nname = \"widget\"\nrequires-python = \"" + python + "\"\n"
        "dependencies = [\"numpy>=1.20\"]\n\n"
        "[project.optional-dependencies]\ntest = [\"pytest>=7\"]\n")
    (root / "requirements.txt").write_text(requirements)
    vendored = root / ".venv"
    vendored.mkdir()
    (vendored / "requirements.txt").write_text("evilpkg\n")
    (root / "apt.txt").write_text("libxml2\nnot a package\n")
    return root


def _pypi(name):
    if name == "linked-pkg":
        return {"home_page": "https://github.com/acme/widget.git"}
    if name == "mystery-pkg":
        return OTHER
    return None


def _plan(root, *, sandbox="local", current="3.12", text="", python_available=None):
    return demo_helper.build_setup_plan(
        REPO, [root], {"text": text}, current, sandbox, "widget",
        python_available=python_available or (lambda _version: None), pypi=_pypi)


def test_pypi_link_back_matches_the_study_rule():
    assert demo_helper.pypi_links_back({"home_page": "https://GitHub.com/Acme/Widget/"}, "acme", "widget")
    assert demo_helper.pypi_links_back({"home_page": "https://github.com/acme/widget.git"}, "acme", "widget")
    assert demo_helper.pypi_links_back({"project_urls": {"Source": "https://github.com/acme/widget?foo=1"}}, "acme", "widget")
    assert demo_helper.pypi_links_back({"info": {"home_page": "https://github.com/acme/widget"}}, "acme", "widget")
    assert not demo_helper.pypi_links_back({"home_page": "https://github.com/acme/widget-extra"}, "acme", "widget")
    assert not demo_helper.pypi_links_back({"home_page": "https://github.com/other/widget"}, "acme", "widget")
    assert not demo_helper.pypi_links_back(None, "acme", "widget")
    assert not demo_helper.pypi_links_back({}, "acme", "widget")


def test_setup_plan_uses_project_files_and_link_back_only(tmp_path):
    text = "pip install mystery-pkg\npip install linked-pkg\napt-get install libhdf5-dev\nPython 3.11\n"
    plan = _plan(_checkout(tmp_path), text=text)
    extra = plan["extra_reqs"]
    assert "pytest>=7" in extra and "scipy==1.2" in extra and "linked-pkg" in extra
    assert "numpy>=1.20" not in extra and "evilpkg" not in extra and "widget" not in extra and "mystery-pkg" not in extra
    assert all(pkg["sides"] == ["main", "pr"] for pkg in plan["packages"])
    assert any(pkg["name"] == "numpy" and pkg["action"] == "noted" for pkg in plan["packages"])
    assert all(line.startswith("Setup plan:") for line in plan["lines"])
    refused = " ".join(item["reason"] for item in plan["refused"])
    assert "its PyPI page does not link to this GitHub repository" in refused
    assert plan["python"]["applied"] is True and plan["python"]["switch"] is None
    assert all(item["applied"] is False for item in plan["system"])
    local_shell = demo_helper.contree_shell(plan)
    assert "libhdf5-dev" not in local_shell and "apt-get install -y" not in local_shell


def test_python_and_system_hints_follow_the_sandbox(tmp_path):
    root = _checkout(tmp_path, python=">=3.11")
    switched = demo_helper.build_setup_plan(
        REPO, [root], {"text": ""}, "3.10", "local", "widget",
        python_available=lambda version: "/usr/bin/python3.11" if version == "3.11" else None, pypi=_pypi)
    assert switched["python"]["switch"] == "/usr/bin/python3.11" and switched["python"]["applied"] is True
    missing = _plan(root, current="3.10", python_available=lambda _version: None)
    assert missing["python"]["applied"] is False and missing["python"]["switch"] is None
    assert "not applied" in missing["python"]["reason"]
    contree = demo_helper.build_setup_plan(
        REPO, [root], {"text": "apt-get install libhdf5-dev\n"}, "3.10", "contree", "widget",
        python_available=lambda version: "/usr/bin/python3.11", pypi=_pypi)
    assert contree["python"]["switch"] is None and contree["python"]["applied"] is False
    assert "Contree" in contree["python"]["reason"]
    applied = {item["name"]: item["applied"] for item in contree["system"]}
    assert applied["libhdf5-dev"] is True and applied["libxml2"] is True
    shell = demo_helper.contree_shell(contree)
    assert "apt-get install -y -qq libhdf5-dev" in shell or "apt-get install -y -qq libxml2 libhdf5-dev" in shell
    assert "apt-get" in shell and "libhdf5-dev" in shell and "pytest>=7" in shell


def test_same_install_list_on_both_sides_and_both_contree_shells():
    calls = []

    def install_one(side, requirement):
        calls.append((side, requirement))
        return True, "1.2.3"

    logs = demo_helper.install_same(
        [{"requirement": "pytest>=7", "source": "pyproject", "reason": "listed in the test extra", "action": "install"}],
        install_one)
    assert calls == [("main", "pytest>=7"), ("pr", "pytest>=7")]
    assert logs[0]["sides"] == ["main", "pr"] and logs[0]["version"] == "1.2.3"
    extra = "python -m pip install -q 'pytest>=7'"
    shells = []

    def runner(shell, disposable, image_ref, timeout, files=None):
        shells.append(shell)
        if not disposable:
            return {"exit_code": 0, "stdout": "", "stderr": "",
                    "uuid": "main-uuid" if image_ref is None else "pr-uuid"}
        return {"exit_code": 0, "stdout": "", "stderr": "", "uuid": None}

    contree_sandboxes.prepare_source_pair(REPO, "aaa111", "bbb222", runner=runner, extra_shell=extra)
    installs = [shell for shell in shells if "git fetch" in shell]
    assert len(installs) == 2 and extra in installs[0] and extra in installs[1]
    left = contree_sandboxes.install_shell_source(REPO, "aaa111", extra)
    right = contree_sandboxes.install_shell_source(REPO, "bbb222", extra)
    assert left.replace("aaa111", "SHA") == right.replace("bbb222", "SHA")
    plain = contree_sandboxes.install_shell_source(REPO, "abc")
    assert plain == contree_sandboxes.install_shell_source(REPO, "abc", "")
    assert plain == contree_sandboxes.install_shell_source(REPO, "abc", "  \n")
    assert "libhdf5-dev" not in plain
    contree_sandboxes.clear_session()


def test_setup_failure_is_relabelled_and_retried_then_a_real_failure_is_not():
    state = {"n": 0}

    def flaky():
        state["n"] += 1
        if state["n"] < 3:
            return False, "timed out waiting for the index", None
        return True, "", "ready"

    ok, _detail, value, outcome = demo_helper.run_setup("main install", flaky)
    assert ok and value == "ready" and outcome["attempts"] == 3 and outcome["retried"] is True
    assert outcome["counts_as_verdict"] is True

    def broken():
        return False, "install failed (1)", None

    ok, _detail, _value, outcome = demo_helper.run_setup("main install", broken)
    assert ok is False and outcome["attempts"] == 3
    assert outcome["label"] == "rerun, setup problem" and outcome["counts_as_verdict"] is False

    def guard():
        return False, "wrong-commit guard (main side): mismatch", None

    _ok, detail, _value, outcome = demo_helper.run_setup("main install", guard)
    assert outcome["attempts"] == 1 and outcome["counts_as_verdict"] is True
    assert "wrong-commit" in detail

    rec = {}
    demo_helper.note_setup(rec, "main install", {"ok": False, "counts_as_verdict": False, "attempts": 3, "detail": "timeout"})
    assert rec["demo_helper"]["setup"]["label"] == "rerun, setup problem"
    assert demo_helper.counts_as_verdict(rec) is False
    assert demo_helper.shown_outcome(rec) == "rerun, setup problem"


def test_study_run_ignores_the_helper(tmp_path):
    assert demo_helper.active(None) is False
    assert demo_helper.active(SimpleNamespace(bench="bench/benchmark-v0.csv")) is False
    assert demo_helper.active(SimpleNamespace(bench=None)) is True
    fetched = {"n": 0}

    def fetch(*_args, **_kwargs):
        fetched["n"] += 1
        raise AssertionError("study run must not look up")

    rec = {"verdict": "verified", "reason": "same tests"}
    assert demo_helper.begin_check(SimpleNamespace(bench="x"), rec, REPO, "widget", tmp_path,
                                   env={"TAVILY_API_KEY": "not-used"}, fetch=fetch) is None
    assert rec == {"verdict": "verified", "reason": "same tests"} and fetched["n"] == 0
    calls = {"n": 0}

    def once():
        calls["n"] += 1
        return False, "timed out", "kept"

    ok, detail, value, outcome = demo_helper.run_setup("checkout", once, active=False)
    assert calls["n"] == 1 and outcome is None and ok is False and detail == "timed out" and value == "kept"


def test_keys_never_appear_in_notes_cache_or_output(tmp_path, capsys):
    secrets = {
        "NEBIUS_API_KEY": "nebius-secret-value-aaa",
        "TAVILY_API_KEY": "tavily-secret-value-bbb",
        "GITHUB_TOKEN": "github-secret-value-ccc",
        "GITHUB_POC_TOKEN": "github-poc-secret-ddd",
        "GH_TOKEN": "gh-secret-value-eeee",
        "GITHUB_APP_INSTALLATION_TOKEN": "github-app-secret-ffff",
    }

    def fetch(_query, timeout=8, env=None):
        raise RuntimeError(f"boom {env['TAVILY_API_KEY']} bearer {env['GITHUB_TOKEN']}")

    rec = {}
    runner = SimpleNamespace(bench=None, model_provider="nebius")
    demo_helper.begin_check(runner, rec, REPO, "widget", tmp_path, env=secrets, fetch=fetch)
    captured = capsys.readouterr()
    blob = json.dumps(rec)
    cache = tmp_path / "tavily-cache.json"
    cached = cache.read_text() if cache.is_file() else ""
    notes = "\n".join(demo_helper.public_notes(
        [{"stage": "demo_helper", "detail": captured.out}], rec, env=secrets))
    leaked = [name for name, secret in secrets.items()
              if secret in blob or secret in cached or secret in notes or secret in captured.out or secret in captured.err]
    assert leaked == []
    assert rec["demo_helper"]["tavily"]["live_call"] is True
    pre = demo_helper.preflight(tmp_path, env=secrets, model_token="nebius",
                                memory=lambda: {"available_gb": 1.5, "total_gb": 8.0},
                                disk=lambda _path: SimpleNamespace(free=3e9),
                                which=lambda tool: f"/usr/bin/{tool}")
    text = "\n".join(pre["lines"])
    assert "Nebius token: present" in text and "GitHub token: present" in text
    assert all(secret not in text for secret in secrets.values())
    redacted = demo_helper.redact_obj({"api_key": secrets["TAVILY_API_KEY"], "note": secrets["NEBIUS_API_KEY"]}, secrets)
    assert redacted["api_key"] == "[redacted]" and secrets["NEBIUS_API_KEY"] not in json.dumps(redacted)


def test_tavily_notes_do_not_change_a_verdict():
    left = verdict_for(None, "could not verify something")
    right = verdict_for(None, "could not verify something")
    assert left == right
    rec = {"verdict": "verified", "reason": "1 new test passes",
           "demo_helper": {"notes": ["Looked up with Tavily: 1 results"], "tavily": {"text": "could_not_verify verified"}}}
    calls = []
    demo_helper.retry_unverified(rec, lambda: calls.append("ran") or {"verdict": "could_not_verify", "reason": "x"},
                                 lambda *_a: (_ for _ in ()).throw(AssertionError("installed")),
                                 [], "This result is verified and also could_not_verify", lambda _name: LINK,
                                 REPO, False)
    assert calls == [] and rec["verdict"] == "verified"
    attention = {"verdict": "needs_attention", "reason": "ModuleNotFoundError: No module named 'numpy'"}
    demo_helper.retry_unverified(attention, lambda: calls.append("ran"), lambda *_a: (True, "1"),
                                 ["numpy"], "pip install numpy", lambda _name: LINK, REPO, False)
    assert calls == [] and attention["verdict"] == "needs_attention"
    claim = {"verdict": "could_not_verify", "reason": "unverified behaviour claim"}
    demo_helper.retry_unverified(claim, lambda: calls.append("ran"), lambda *_a: (True, "1"),
                                 [], "verified", lambda _name: LINK, REPO, False)
    assert calls == [] and claim["reason"] == "unverified behaviour claim" and claim["verdict"] == "could_not_verify"


def test_unverified_setup_gap_installs_on_both_sides_and_reruns_once():
    calls = []

    def install_one(side, requirement):
        calls.append((side, requirement))
        return True, "1.26"

    def rerun():
        calls.append("rerun")
        return {"verdict": "verified", "reason": "the tests passed after the install"}

    rec = {"verdict": "could_not_verify", "reason": "ModuleNotFoundError: No module named 'numpy'"}
    demo_helper.retry_unverified(rec, rerun, install_one, ["numpy>=1.24"], "pip install something-else",
                                 lambda _name: None, REPO, False)
    assert calls == [("main", "numpy>=1.24"), ("pr", "numpy>=1.24"), "rerun"]
    assert rec["verdict"] == "verified"
    notes = "\n".join(rec["demo_helper"]["notes"])
    assert "Before rerun:" in notes and "After rerun:" in notes
    assert len(rec["demo_helper"]["gap_retry"]["rounds"]) == 2

    calls.clear()
    again = {"verdict": "could_not_verify", "reason": "ModuleNotFoundError: No module named 'numpy'"}

    def still(_side, _requirement):
        calls.append("install")
        return True, "1.26"

    def still_missing():
        calls.append("rerun")
        return {"verdict": "could_not_verify", "reason": "ModuleNotFoundError: No module named 'numpy'"}

    demo_helper.retry_unverified(again, still_missing, still, [], "pip install numpy\nThe change is verified.",
                                 lambda name: LINK if name == "numpy" else None, REPO, False)
    assert calls.count("rerun") == 1
    assert again["verdict"] == "could_not_verify"
    assert again["reason"] == "could not verify: setup gap numpy"

    calls.clear()
    blocked = {"verdict": "could_not_verify", "reason": "ModuleNotFoundError: No module named 'numpy'"}
    demo_helper.retry_unverified(blocked, lambda: calls.append("rerun"), lambda *_a: calls.append("install"),
                                 [], "verified. pip install unrelated-pkg", lambda _name: OTHER, REPO, False)
    assert calls == []
    assert blocked["verdict"] == "could_not_verify"
    assert blocked["reason"] == "could not verify: setup gap numpy"


def test_gap_retry_stops_when_lookup_fails_or_nothing_can_be_installed():
    calls = []

    def boom(_query):
        raise RuntimeError("lookup down")

    rec = {"verdict": "could_not_verify", "reason": "ImportError: No module named 'numpy'"}
    demo_helper.retry_unverified(rec, lambda: calls.append("rerun") or {"verdict": "verified", "reason": "ok"},
                                 lambda side, requirement: calls.append((side, requirement)) or (True, "1"),
                                 ["numpy"], "", lambda _name: None, REPO, False, lookup=boom)
    assert ("main", "numpy") in calls and ("pr", "numpy") in calls and calls.count("rerun") == 1
    missing = {"verdict": "could_not_verify",
               "reason": "FileNotFoundError: [Errno 2] No such file or directory: 'tests/data/sample.csv'"}
    demo_helper.retry_unverified(missing, lambda: calls.append("rerun"), lambda *_a: (True, "1"),
                                 [], "verified", lambda _name: LINK, REPO, False)
    assert calls.count("rerun") == 1
    assert missing["reason"] == "could not verify: setup gap missing fixture sample.csv"
    conflict = {"verdict": "could_not_verify", "reason": "ResolutionImpossible: version conflict"}
    demo_helper.retry_unverified(conflict, lambda: calls.append("rerun"), lambda *_a: (True, "1"),
                                 ["numpy"], "pip install numpy", lambda _name: LINK, REPO, False)
    assert conflict["reason"] == "could not verify: setup gap version conflict"
    labelled = {"verdict": "could_not_verify", "reason": "ModuleNotFoundError: No module named 'numpy'",
                "demo_helper": {"setup": {"counts_as_verdict": False}}}
    before = labelled["reason"]
    demo_helper.retry_unverified(labelled, lambda: calls.append("rerun"), lambda *_a: (True, "1"),
                                 ["numpy"], "", lambda _name: LINK, REPO, False)
    assert labelled["reason"] == before


def test_lookup_records_a_live_call_and_skips_cleanly(tmp_path):
    cache = demo_helper.FileCache(tmp_path / "cache.json")

    def fetch(query, timeout=8, env=None):
        assert timeout == demo_helper.TAVILY_TIMEOUT
        return {"ok": True, "answer": "install widget from the repository", "query": query,
                "results": [{"title": "widget install", "url": "https://github.com/acme/widget",
                             "content": "pip install widget"}]}

    fresh = demo_helper.lookup_project(REPO, "widget", cache, env={"TAVILY_API_KEY": "present-but-not-logged"}, fetch=fetch)
    assert fresh["live_call"] is True and fresh["cached"] is False
    assert fresh["lines"][0] == f"Looked up with Tavily: {len(demo_helper.lookup_queries(REPO, 'widget'))} results"
    assert any(line.startswith("Query: ") for line in fresh["lines"])
    assert any("site:github.com/acme/widget" in line for line in fresh["lines"])
    assert any("site:pypi.org" in line for line in fresh["lines"])
    assert any(line.startswith("Source: widget install — ") for line in fresh["lines"])
    again = demo_helper.lookup_project(REPO, "widget", cache, env={"TAVILY_API_KEY": "present-but-not-logged"}, fetch=fetch)
    assert again["live_call"] is False and again["cached"] is True
    assert "present-but-not-logged" not in (tmp_path / "cache.json").read_text()
    skipped = demo_helper.lookup_project(REPO, "widget", demo_helper.MemoryCache(), env={}, fetch=fetch)
    assert skipped["live_call"] is False and skipped["skipped"] is True
    assert "TAVILY_API_KEY" in skipped["lines"][0]

    def offline(_query, timeout=8, env=None):
        return {"ok": False, "error": "URLError: [Errno -2] Name or service not known", "query": _query, "results": []}

    failed = demo_helper.lookup_project(REPO, "widget", demo_helper.MemoryCache(),
                                       env={"TAVILY_API_KEY": "present-but-not-logged"}, fetch=offline)
    assert failed["live_call"] is True
    assert "no network" in failed["lines"][0]


def test_lookup_queries_name_the_repo_and_drop_unrelated_hits():
    queries = demo_helper.lookup_queries("jaraco/inflect", "inflect")
    joined = "\n".join(queries)
    assert "https://github.com/jaraco/inflect" in joined
    assert "https://pypi.org/project/inflect/" in joined
    assert any("site:github.com/jaraco/inflect" in query for query in queries)
    assert any("site:pypi.org" in query for query in queries)
    assert any("documentation" in query for query in queries)

    def fetch(query, timeout=8, env=None):
        return {"ok": True, "answer": "Try a fork of an unrelated product", "query": query, "results": [
            {"title": "inflect setup", "url": "https://github.com/jaraco/inflect",
             "content": "pip install inflect"},
            {"title": "Inflection, a different library", "url": "https://github.com/example/inflection",
             "content": "pip install inflection"},
            {"title": "Some other product", "url": "https://example.com/other",
             "content": "nothing to do with this repository"},
        ]}

    cache = demo_helper.MemoryCache()
    got = demo_helper.lookup_project("jaraco/inflect", "inflect", cache,
                                    env={"TAVILY_API_KEY": "present-but-not-logged"}, fetch=fetch)
    blob = json.dumps(got)
    cached = json.dumps(cache._data)
    assert got["lines"][0] == f"Looked up with Tavily: {len(queries)} results"
    assert all(item["url"] == "https://github.com/jaraco/inflect" for item in got["results"])
    for dropped in ("example.com/other", "unrelated product", "pip install inflection", "inflect-fork"):
        assert dropped not in blob
        assert dropped not in cached
    assert "inflect setup" in blob
    # A hit is kept when only the body names the project. A fork name that merely starts with the project is not.
    kept = demo_helper.scope_lookup(
        {"answer": "unrelated essay", "results": [
            {"title": "Notes", "url": "https://example.com/notes", "content": "jaraco/inflect needs pytest"},
            {"title": "Fork", "url": "https://github.com/someone/inflect-fork", "content": "my copy"},
            {"title": "Inflection", "url": "https://pypi.org/project/inflection/", "content": "a different library"},
        ]},
        "jaraco/inflect", "inflect")
    assert [item["url"] for item in kept["results"]] == ["https://example.com/notes"]
    assert kept["answer"] is None
    # The same filter runs before a setup-gap lookup is used, so an unrelated install suggestion cannot be applied.
    calls = []
    gap = {"verdict": "could_not_verify", "reason": "ModuleNotFoundError: No module named 'inflection'",
           "library": "inflect"}

    def gap_lookup(_query):
        return {"answer": "pip install inflection", "results": [
            {"title": "Inflection", "url": "https://github.com/example/inflection", "content": "pip install inflection"}]}

    demo_helper.retry_unverified(
        gap, lambda: calls.append("rerun"), lambda *_a: calls.append("install"), [], "",
        lambda _name: {"home_page": "https://github.com/jaraco/inflect"}, "jaraco/inflect", False, lookup=gap_lookup)
    assert calls == []
    assert "pip install inflection" not in json.dumps(gap)
    assert gap["reason"] == "could not verify: setup gap inflection"


def test_report_shows_helper_notes_and_does_not_count_a_setup_problem(tmp_path):
    from ops.daily_run import write_report
    rec = {"repo": "acme/widget", "pr": {"number": 7, "url": "https://example.com/pull/7", "title": "Add a check",
                                         "head_sha": "a" * 40},
           "route": "source-pair", "verdict": "verified", "reason": "1 unchanged",
           "author": "dev", "updated_at_ist": "t", "ci_state": "none", "ci_detail": "-",
           "files": {"package_py": ["widget/a.py"], "compiled": []}, "duration_s": {"total_wall": 3},
           "logs": "missing", "demo_helper": {"notes": [
               "Looked up with Tavily: 2 results",
               "Query: widget python setup install instructions",
               "Source: Install — https://example.com/install",
               "Setup plan: install pytest>=7 (listed in the test extra) on main and pr."]}}
    setup = {"repo": "acme/widget", "pr": {"number": 8, "url": "https://example.com/pull/8", "title": "Break the build",
                                           "head_sha": "b" * 40},
             "route": "source-pair", "verdict": "could_not_verify", "reason": "install failed",
             "author": "dev", "updated_at_ist": "t", "ci_state": "none", "ci_detail": "-",
             "files": {"package_py": [], "compiled": []}, "duration_s": {"total_wall": 3}, "logs": "missing",
             "demo_helper": {"setup": {"label": "rerun, setup problem", "counts_as_verdict": False},
                             "notes": ["rerun, setup problem: main install failed after 3 tries."]}}
    meta = {"date": "2026-10-21", "started_ist": "s", "finished_ist": "f", "wall_min": 1, "runs": 3,
            "machine": "m", "api_calls": 0, "auth": "none"}
    md = write_report(tmp_path, meta, [rec, setup], {}, []).read_text()
    assert "Looked up with Tavily: 2 results" in md and "Setup plan:" in md
    assert "rerun, setup problem" in md and "**rerun, setup problem**" not in md
    audit = demo_helper.check_report([rec, setup], md)
    assert audit["ok"] is True and audit["record_counts"] == {"verified": 1}
    assert audit["report_counts"] == {"verified": 1}
    tampered = md.replace("**verified**", "**needs_attention**", 1)
    bad = demo_helper.check_report([rec, setup], tampered)
    assert bad["ok"] is False
    assert demo_helper.self_check_markdown(audit).startswith("Self-check: the report matches the run records.")
    assert demo_helper.self_check_markdown(bad).startswith("Self-check: the report does not match the run records.")


def _live_opt_in() -> bool:
    flag = os.environ.get("POC_TAVILY_LIVE", "").strip().lower()
    return flag in {"1", "true", "yes", "on"} and bool(os.environ.get("TAVILY_API_KEY", "").strip())


@pytest.mark.skipif(not _live_opt_in(), reason="opt-in live Tavily call: set POC_TAVILY_LIVE=1 and TAVILY_API_KEY")
def test_live_tavily_call_is_recorded_without_the_key():
    got = demo_helper.lookup_project("psf/requests", "requests", demo_helper.MemoryCache())
    blob = json.dumps(got)
    assert os.environ["TAVILY_API_KEY"] not in blob
    assert got["live_call"] is True
    if not got["results"]:
        pytest.fail("live Tavily call returned no results")
