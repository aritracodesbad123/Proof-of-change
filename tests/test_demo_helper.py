"""Demo helper: setup plan, safe installs, Tavily notes, and one setup-gap rerun. No network."""
from __future__ import annotations

import json
import os
from pathlib import Path
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


def test_pypi_link_back_requires_a_real_github_repo_url():
    assert demo_helper.github_repo_url("https://GitHub.com/Acme/Widget/", "acme", "widget")
    assert demo_helper.github_repo_url("https://github.com/acme/widget.git", "acme", "widget")
    assert demo_helper.github_repo_url("https://www.github.com/acme/widget", "acme", "widget")
    assert demo_helper.github_repo_url("https://github.com/acme/widget/tree/main", "acme", "widget")
    assert demo_helper.github_repo_url("https://github.com/acme/widget?foo=1", "acme", "widget")
    assert demo_helper.github_repo_url("https://github.com/acme/widget#readme", "acme", "widget")
    assert not demo_helper.github_repo_url("https://evil.com/github.com/jaraco/inflect", "jaraco", "inflect")
    assert not demo_helper.github_repo_url("https://notgithub.com/jaraco/inflect", "jaraco", "inflect")
    assert not demo_helper.github_repo_url("https://github.com.evil.com/jaraco/inflect", "jaraco", "inflect")
    assert not demo_helper.github_repo_url("https://github.com/jaraco/inflect-extra", "jaraco", "inflect")
    assert demo_helper.pypi_links_back({"home_page": "https://GitHub.com/Acme/Widget/"}, "acme", "widget")
    assert demo_helper.pypi_links_back({"home_page": "https://github.com/acme/widget.git"}, "acme", "widget")
    assert demo_helper.pypi_links_back({"project_urls": {"Source": "https://github.com/acme/widget?foo=1"}}, "acme", "widget")
    assert demo_helper.pypi_links_back({"info": {"home_page": "https://github.com/acme/widget"}}, "acme", "widget")
    assert demo_helper.pypi_links_back({"home_page": "https://www.github.com/acme/widget/"}, "acme", "widget")
    assert not demo_helper.pypi_links_back({"home_page": "https://evil.com/github.com/jaraco/inflect"}, "jaraco", "inflect")
    assert not demo_helper.pypi_links_back({"home_page": "https://notgithub.com/jaraco/inflect"}, "jaraco", "inflect")
    assert not demo_helper.pypi_links_back({"project_urls": {"Home": "https://notgithub.com/acme/widget"}}, "acme", "widget")
    assert not demo_helper.pypi_links_back({"home_page": "https://github.com/acme/widget-extra"}, "acme", "widget")
    assert not demo_helper.pypi_links_back({"home_page": "https://github.com/other/widget"}, "acme", "widget")
    assert not demo_helper.pypi_links_back(None, "acme", "widget")
    assert not demo_helper.pypi_links_back({}, "acme", "widget")


def test_github_repo_url_accepts_only_http_and_https():
    assert demo_helper.github_repo_url("https://github.com/o/r", "o", "r")
    assert demo_helper.github_repo_url("http://github.com/o/r", "o", "r")
    assert not demo_helper.github_repo_url("ftp://github.com/o/r", "o", "r")
    assert not demo_helper.github_repo_url("git+ssh://git@github.com/o/r.git", "o", "r")
    assert not demo_helper.github_repo_url("git+ssh://github.com/o/r", "o", "r")


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
    assert contree["python"]["switch"] is None and contree["python"]["applied"] is True
    assert contree["python"]["provision"] == "3.11" and "auto-fix" in contree["python"]["reason"]
    applied = {item["name"]: item["applied"] for item in contree["system"]}
    assert applied == {"libxml2": True}
    assert "libhdf5-dev" not in json.dumps(contree)
    shell = demo_helper.contree_shell(contree)
    assert "apt-get install -y -qq libxml2" in shell
    assert "libhdf5-dev" not in shell and "pytest>=7" in shell
    assert "uv python install -q 3.11" in shell and shell.index("uv python install") < shell.index("pytest>=7")


def test_setup_plan_ignores_python_and_system_hints_from_tavily(tmp_path):
    root = _checkout(tmp_path, python=">=3.11")
    tavily = {"answer": "Try Python 3.14 alpha", "results": [
        {"title": "Python 3.14 support", "url": "https://github.com/acme/widget/issues/224",
         "content": "widget fails on Python 3.14.0a1\napt-get install libhdf5-dev"}]}
    plan = demo_helper.build_setup_plan(
        REPO, [root], tavily, "3.12", "local", "widget",
        python_available=lambda version: "/usr/bin/python3.12" if version == "3.12" else None, pypi=_pypi)
    blob = json.dumps(plan)
    assert "3.14" not in blob and "libhdf5-dev" not in blob
    assert plan["python"]["requested"] == "3.12" and plan["python"]["switch"] is None
    assert plan["python"]["applied"] is True
    assert [item["name"] for item in plan["system"]] == ["libxml2"]

    # The floor is not installed. A higher version that meets >=3.11 is. The issue's 3.14 is not.
    picked = demo_helper.build_setup_plan(
        REPO, [root], tavily, "3.10", "local", "widget",
        python_available=lambda version: "/usr/bin/python3.12" if version == "3.12" else None, pypi=_pypi)
    assert picked["python"]["requested"] == "3.12"
    assert picked["python"]["switch"] == "/usr/bin/python3.12"
    assert "3.14" not in json.dumps(picked)

    cfg = tmp_path / "from-cfg"
    cfg.mkdir()
    (cfg / "setup.cfg").write_text(
        "[metadata]\nname = widget\nclassifiers =\n    Programming Language :: Python :: 3.11\n"
        "    Programming Language :: Python :: 3.14\n"
        "[options]\npython_requires = >=3.11\n")
    (cfg / "setup.py").write_text("setup(name='widget', python_requires='>=3.11')\n")
    from_files = demo_helper.build_setup_plan(
        REPO, [cfg], tavily, "3.10", "local", "widget",
        python_available=lambda version: "/usr/bin/python3.11" if version == "3.11" else None,
        pypi=lambda _name: {"requires_python": ">=3.14", "home_page": "https://github.com/other/mystery"})
    assert from_files["python"]["requested"] == "3.11"
    assert "3.14" not in json.dumps(from_files)

    bare = tmp_path / "from-pypi"
    bare.mkdir()
    page = {"requires_python": ">=3.10", "classifiers": ["Programming Language :: Python :: 3.10"],
            "home_page": "https://github.com/acme/widget"}
    from_pypi = demo_helper.build_setup_plan(
        REPO, [bare], tavily, "3.12", "local", "widget", python_available=lambda _version: None,
        pypi=lambda _name: page)
    assert from_pypi["python"]["requested"] == "3.12"
    assert "3.14" not in json.dumps(from_pypi) and "libhdf5-dev" not in json.dumps(from_pypi)


def test_python_switch_applies_to_one_check_only(tmp_path, monkeypatch):
    from ops import daily_run
    monkeypatch.setattr(demo_helper, "find_python",
                        lambda version, which=None: "/opt/python3.11" if version == "3.11" else None)
    a = SimpleNamespace(python="3.10", bench=None, sandbox_backend="local")
    root = _checkout(tmp_path, python=">=3.11")
    plan = daily_run._product_plan(a, {}, "acme/widget", {"dist": "widget"}, [root], pypi=_pypi)
    assert a.python == "3.10"
    assert plan["python"]["switch"] == "/opt/python3.11"
    assert daily_run._check_python(a, plan) == "/opt/python3.11"
    assert daily_run._check_python(a, None) == "3.10"
    seen = {}

    def fake_install(venv, checkout, chosen, log, python, timeout, constraints, extra_reqs=None, **_kw):
        seen["python"] = python
        return True, ""

    monkeypatch.setattr(daily_run, "install_side", fake_install)
    daily_run._install_with_helper(
        a, {}, "main install", tmp_path / "venv", root, None, tmp_path / "log", 10, None, None,
        python=daily_run._check_python(a, plan))
    assert seen["python"] == "/opt/python3.11"
    assert a.python == "3.10"


def test_system_package_installs_on_both_sides_or_neither():
    from ops import daily_run
    calls = []

    def run_side(side, shell):
        calls.append((side, shell.splitlines()[-1]))
        if shell.startswith("apt-get install -s"):
            return 0 if side == "main" else 1
        raise AssertionError(shell)

    rec = {}
    assert daily_run._install_system_package(rec, "libxml2", run_side) is False
    assert all(line.startswith("apt-get install -s") for _side, line in calls)
    assert rec["demo_helper"]["setup"]["label"] == "rerun, setup problem"
    assert rec["demo_helper"]["setup"]["counts_as_verdict"] is False
    assert rec["demo_helper"]["setup"]["detail"] == "pr cannot install libxml2"

    calls.clear()

    def both_then_pr_fails(side, shell):
        calls.append((side, "probe" if shell.startswith("apt-get install -s") else "install" if "install -y" in shell else "remove"))
        if shell.startswith("apt-get install -s"):
            return 0
        if "remove" in shell:
            return 0
        return 0 if side == "main" else 1

    failed = {}
    assert daily_run._install_system_package(failed, "libxml2", both_then_pr_fails) is False
    assert calls == [("main", "probe"), ("pr", "probe"), ("main", "install"), ("pr", "install"), ("main", "remove")]
    assert failed["demo_helper"]["setup"]["label"] == "rerun, setup problem"

    calls.clear()

    def both_ok(side, shell):
        calls.append((side, "probe" if shell.startswith("apt-get install -s") else "install"))
        return 0

    ok_rec = {}
    assert daily_run._install_system_package(ok_rec, "libxml2", both_ok) is True
    assert calls == [("main", "probe"), ("pr", "probe"), ("main", "install"), ("pr", "install")]
    assert "setup" not in (ok_rec.get("demo_helper") or {})


def test_nightly_plan_reads_project_files_and_skips_lookup_packages_without_them(tmp_path):
    from ops import daily_run
    work = tmp_path / "work"
    root = work / "packaging"
    _checkout(root)
    dirs = daily_run._project_file_dirs("acme/widget", {"base_ref": "main"}, work, tmp_path / "unused.log")
    assert dirs == [root]
    a = SimpleNamespace(python="3.12", bench=None, sandbox_backend="local")
    read = daily_run._product_plan(
        a, {}, "acme/widget", {"dist": "widget"}, dirs, pypi=_pypi,
        python_available=lambda _version: None)
    assert "pytest>=7" in read["extra_reqs"]
    assert a.python == "3.12"
    missed = daily_run._product_plan(
        a, {"demo_helper": {"tavily": {"text": "pip install linked-pkg\n"}}},
        "acme/widget", {"dist": "widget"}, [], pypi=_pypi, python_available=lambda _version: None)
    assert "linked-pkg" not in [item["name"] for item in missed["packages"]]
    assert all(item.get("source") != "tavily" for item in missed["packages"])


def test_report_states_the_retry_limits():
    sentence = ("If setup fails, the helper retries the install up to 2 times. "
                "If a test still can't be verified because something is missing or fails to import, it looks up "
                "the cause, installs the fix on both sides and reruns that step, up to 3 tries.")
    assert demo_helper.RETRY_LIMITS == sentence
    assert demo_helper.MAX_SETUP_RETRIES == 2 and demo_helper.MAX_GAP_TRIES == 3
    text = demo_helper.markdown_for({"demo_helper": {"notes": ["Setup plan: ok"]}})
    assert text.count(sentence) == 1
    import reports.pr_report as pr_report
    assert sentence in Path("docs/decisions/2026-10-22-console-check-flow.md").read_text()
    assert pr_report.demo_helper.RETRY_LIMITS == sentence


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
    assert again["reason"].startswith("could not verify: setup gap numpy:")
    assert "No module named 'numpy'" in again["reason"]

    calls.clear()
    blocked = {"verdict": "could_not_verify", "reason": "ModuleNotFoundError: No module named 'numpy'"}
    demo_helper.retry_unverified(blocked, lambda: calls.append("rerun"), lambda *_a: calls.append("install"),
                                 [], "verified. pip install unrelated-pkg", lambda _name: OTHER, REPO, False)
    assert calls == []
    assert blocked["verdict"] == "could_not_verify"
    assert blocked["reason"].startswith("could not verify: setup gap numpy:")
    assert "No module named 'numpy'" in blocked["reason"]


def _probe_record(lines, covered):
    return {
        "verdict": "could_not_verify",
        "reason": "ModuleNotFoundError: No module named 'numpy'",
        "coverage": {"status": "measured", "changed_lines_total": lines, "changed_lines_covered": covered},
        "probes": {"status": "ran", "items": [{
            "id": "p", "source": "model", "status": "ran",
            "probe_changed_line_coverage": {
                "status": "measured", "changed_lines_total": lines, "changed_lines_covered": covered,
                "adequacy": "adequate" if covered else "not_adequate"}}]},
    }


def test_setup_rerun_does_not_accept_a_false_verified():
    """A rerun that says verified is not accepted when fresh probe coverage ran no changed line."""
    calls = []
    rec = _probe_record(12, 4)

    def install_one(side, requirement):
        calls.append((side, requirement))
        return True, "1.26"

    def rerun():
        calls.append("rerun")
        return {"verdict": "verified", "reason": "the tests passed after the install"}

    def recheck():
        calls.append("recheck")
        rec["probes"]["items"][0]["probe_changed_line_coverage"] = {
            "status": "measured", "changed_lines_total": 12, "changed_lines_covered": 0, "adequacy": "not_adequate"}
        return {"verdict": "verified", "reason": "the tests passed after the install"}

    demo_helper.retry_unverified(rec, rerun, install_one, ["numpy>=1.24"], "", lambda _name: None, REPO, False,
                                 recheck_coverage=recheck)
    assert calls == [("main", "numpy>=1.24"), ("pr", "numpy>=1.24"), "rerun", "recheck"]
    assert rec["verdict"] == "could_not_verify"
    assert "changed line" in rec["reason"]


def test_setup_rerun_can_verify_when_fresh_coverage_ran_a_changed_line():
    rec = _probe_record(12, 0)

    def recheck():
        rec["probes"]["items"][0]["probe_changed_line_coverage"] = {
            "status": "measured", "changed_lines_total": 12, "changed_lines_covered": 3, "adequacy": "adequate"}
        return {"verdict": "verified", "reason": "covered after rerun"}

    demo_helper.retry_unverified(
        rec, lambda: {"verdict": "verified", "reason": "the tests passed"},
        lambda *_a: (True, "1"), ["numpy"], "", lambda _name: None, REPO, False, recheck_coverage=recheck)
    assert rec["verdict"] == "verified"
    assert rec["reason"] == "covered after rerun"


def test_setup_rerun_with_no_changed_lines_is_not_verified():
    """No changed lines is not adequate, so a rerun that says verified stays could not verify."""
    rec = _probe_record(0, 0)

    def recheck():
        rec["probes"]["items"][0]["probe_changed_line_coverage"] = {
            "status": "measured", "changed_lines_total": 0, "changed_lines_covered": 0, "adequacy": "not_adequate"}
        return {"verdict": "verified", "reason": "the tests passed"}

    demo_helper.retry_unverified(
        rec, lambda: {"verdict": "verified", "reason": "the tests passed"},
        lambda *_a: (True, "1"), ["numpy"], "", lambda _name: None, REPO, False, recheck_coverage=recheck)
    assert rec["verdict"] == "could_not_verify"
    assert rec["verdict"] != "verified"
    assert "changed line" in rec["reason"]


def test_large_change_skips_probe_coverage_recheck_and_stays_unverified():
    calls = []
    rec = _probe_record(demo_helper.SMALL_CHANGED_LINES + 1, 4)

    def recheck():
        calls.append("recheck")
        return {"verdict": "verified", "reason": "should not be asked"}

    demo_helper.retry_unverified(
        rec, lambda: calls.append("rerun") or {"verdict": "verified", "reason": "tests passed"},
        lambda *_a: (True, "1"), ["numpy"], "", lambda _name: None, REPO, False, recheck_coverage=recheck)
    assert calls == ["rerun"]
    assert rec["verdict"] == "could_not_verify"
    assert "not small" in rec["reason"]


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
    assert missing["reason"].startswith("could not verify: setup gap missing fixture sample.csv")
    assert "sample.csv" in missing["reason"] and "No such file" in missing["reason"]
    conflict = {"verdict": "could_not_verify", "reason": "ResolutionImpossible: version conflict"}
    demo_helper.retry_unverified(conflict, lambda: calls.append("rerun"), lambda *_a: (True, "1"),
                                 ["numpy"], "pip install numpy", lambda _name: LINK, REPO, False)
    assert conflict["reason"].startswith("could not verify: setup gap version conflict")
    assert "ResolutionImpossible" in conflict["reason"]
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
    assert fresh["lines"][0] == "Looked up with Tavily: 1 results"
    assert any(line.startswith("Query: ") for line in fresh["lines"])
    assert any("site:github.com/acme/widget" in line for line in fresh["lines"])
    assert any("site:pypi.org" in line for line in fresh["lines"])
    assert any(line.startswith("Source: widget install — ") for line in fresh["lines"])
    again = demo_helper.lookup_project(REPO, "widget", cache, env={"TAVILY_API_KEY": "present-but-not-logged"}, fetch=fetch)
    assert again["live_call"] is False and again["cached"] is True
    assert "present-but-not-logged" not in (tmp_path / "cache.json").read_text()
    skipped = demo_helper.lookup_project(REPO, "widget", demo_helper.MemoryCache(), env={}, fetch=fetch)
    assert skipped["live_call"] is False and skipped["skipped"] is True
    assert skipped["stop"] is False
    assert "TAVILY_API_KEY" in skipped["lines"][0]
    from poc import tavily_docs
    refused = demo_helper.lookup_project(
        REPO, "widget", demo_helper.MemoryCache(), env={}, fetch=fetch, required=True)
    assert refused["skipped"] is False and refused["stop"] is True
    assert refused["stop_reason"] == tavily_docs.MISSING_KEY
    assert refused["result_count"] == 0
    assert refused["queries"]

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
    assert got["lines"][0] == "Looked up with Tavily: 1 results"
    assert [item["url"] for item in got["results"]] == ["https://github.com/jaraco/inflect"]
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
    assert gap["reason"].startswith("could not verify: setup gap inflection")
    assert "No module named 'inflection'" in gap["reason"]


def test_lookup_counts_each_url_once_and_ranks_setup_sources():
    repo = "https://github.com/jaraco/inflect"
    hits = [
        {"title": "Old release", "url": "https://pypi.org/project/inflect/0.2.4/", "content": "old inflect release"},
        {"title": "mypy.ini", "url": f"{repo}/blob/main/mypy.ini", "content": "inflect type check config"},
        {"title": "ruff.toml", "url": f"{repo}/blob/main/ruff.toml", "content": "inflect lint config"},
        {"title": ".flake8", "url": f"{repo}/blob/main/.flake8", "content": "inflect flake8 config"},
        {"title": "An issue", "url": f"{repo}/issues/1", "content": "inflect bug report"},
        {"title": "README", "url": f"{repo}/blob/main/README.rst#readme", "content": "install inflect from the readme"},
        {"title": "README again", "url": f"{repo}/blob/main/README.rst/", "content": "install inflect from the readme again"},
        {"title": "requirements", "url": f"{repo}/blob/main/requirements.txt", "content": "inflect requirements"},
        {"title": "setup.py", "url": f"{repo}/blob/main/setup.py", "content": "inflect setup.py"},
        {"title": "setup.cfg", "url": f"{repo}/blob/main/setup.cfg", "content": "inflect setup.cfg"},
        {"title": "pyproject", "url": f"{repo}/blob/main/pyproject.toml", "content": "inflect pyproject"},
        {"title": "inflect", "url": "https://pypi.org/project/inflect/", "content": "current inflect page"},
        {"title": "Old again", "url": "https://pypi.org/project/Inflect/7.0.0", "content": "another old inflect release"},
        {"title": "pyrightconfig.json", "url": f"{repo}/blob/main/pyrightconfig.json", "content": "inflect pyright"},
    ]

    def fetch(_query, timeout=8, env=None):
        return {"ok": True, "answer": "install inflect", "query": _query, "results": hits}

    cache = demo_helper.MemoryCache()
    got = demo_helper.lookup_project("jaraco/inflect", "inflect", cache,
                                    env={"TAVILY_API_KEY": "present-but-not-logged"}, fetch=fetch)
    urls = [item["url"] for item in got["results"]]
    assert urls == [
        f"{repo}/blob/main/pyproject.toml",
        f"{repo}/blob/main/setup.cfg",
        f"{repo}/blob/main/setup.py",
        f"{repo}/blob/main/requirements.txt",
        f"{repo}/blob/main/README.rst",
        "https://pypi.org/project/inflect/",
        f"{repo}/issues/1",
    ]
    assert got["lines"][0] == f"Looked up with Tavily: {len(urls)} results"
    sources = [line.split(" — ", 1)[1] for line in got["lines"] if line.startswith("Source: ")]
    assert sources == urls
    assert urls.count("https://pypi.org/project/inflect/") == 1
    blob = json.dumps(got)
    cached = json.dumps(cache._data)
    for dropped in ("0.2.4", "7.0.0", "mypy.ini", "ruff.toml", ".flake8", "pyrightconfig.json",
                    "inflect type check config", "inflect lint config", "old inflect release"):
        assert dropped not in blob
        assert dropped not in cached
    assert "current inflect page" in blob
    assert blob.count("install inflect from the readme again") == 0
    only_old = demo_helper.polish_results([
        {"title": "inflect 0.2.4", "url": "https://pypi.org/project/inflect/0.2.4/#description", "content": "old"},
        {"title": "inflect 7", "url": "https://www.pypi.org/project/Inflect/7.0.0", "content": "newer"},
    ], "inflect")
    assert [item["url"] for item in only_old] == ["https://pypi.org/project/inflect/"]
    folded = demo_helper.polish_results([
        {"title": "a", "url": f"{repo}/issues/1#comment", "content": "inflect"},
        {"title": "b", "url": "https://GitHub.com/jaraco/inflect/issues/1/", "content": "inflect"},
        {"title": ".pylintrc", "url": f"{repo}/blob/main/.pylintrc", "content": "inflect pylint"},
    ], "inflect")
    assert [item["url"] for item in folded] == [f"{repo}/issues/1"]


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


def test_missing_python_is_provisioned_automatically_on_the_local_sandbox(tmp_path):
    root = _checkout(tmp_path, python=">=3.14")
    asked = []
    plan = demo_helper.build_setup_plan(
        REPO, [root], {"text": ""}, "3.12", "local", "widget",
        python_available=lambda _v: None, pypi=_pypi, provision=lambda v: asked.append(v) or v)
    assert asked == ["3.14"]
    assert plan["python"]["applied"] is True and plan["python"]["switch"] == "3.14"
    assert any(line.startswith("Auto-fix: Python 3.14") for line in plan["lines"])
    failed = demo_helper.build_setup_plan(
        REPO, [root], {"text": ""}, "3.12", "local", "widget",
        python_available=lambda _v: None, pypi=_pypi, provision=lambda v: None)
    assert failed["python"]["applied"] is False and "not applied" in failed["python"]["reason"]


def test_injected_lookup_never_downloads(tmp_path, monkeypatch):
    root = _checkout(tmp_path, python=">=3.14")
    monkeypatch.setattr(demo_helper, "provision_python", lambda v: (_ for _ in ()).throw(AssertionError("download")))
    plan = demo_helper.build_setup_plan(REPO, [root], {"text": ""}, "3.12", "local", "widget",
                                        python_available=lambda _v: None, pypi=_pypi)
    assert plan["python"]["applied"] is False


def test_python_version_file_and_ci_config_are_read(tmp_path):
    root = tmp_path / "proj"
    (root / ".github" / "workflows").mkdir(parents=True)
    (root / ".python-version").write_text("3.14.7\n")
    (root / ".github" / "workflows" / "ci.yml").write_text("with:\n  python-version: '3.13'\n")
    (root / "tox.ini").write_text("[tox]\nenvlist = py311, py312\n")
    specs, declared = demo_helper._python_from_checkout(root)
    assert "==3.14.*" in specs
    assert {"3.13", "3.11", "3.12"} <= set(declared)
    assert demo_helper.choose_python(specs, declared, "3.12", lambda _v: None) == "3.14"


def test_contree_python_shell_is_same_for_both_sides_and_rejects_bad_versions():
    shell = demo_helper.contree_python_shell("3.14")
    assert "sys.version_info[:2] == (3, 14)" in shell and "/usr/local/bin/python" in shell
    assert "Auto-fix:" in shell
    import pytest
    for bad in ("3.14; rm -rf /", "latest", ""):
        with pytest.raises(ValueError):
            demo_helper.contree_python_shell(bad)


def test_provision_python_strips_keys_and_validates(monkeypatch):
    monkeypatch.setenv("NEBIUS_API_KEY", "x")
    monkeypatch.setenv("GITHUB_POC_TOKEN", "y")
    seen = {}

    def runner(argv, env):
        seen["argv"], seen["env"] = argv, env
        return 0
    got = demo_helper.provision_python("3.14", which=lambda _n: "/usr/bin/uv", runner=runner, install_dir="/x")
    assert got == "3.14" and seen["argv"] == ["/usr/bin/uv", "python", "install", "-q", "3.14"]
    assert "NEBIUS_API_KEY" not in seen["env"] and "GITHUB_POC_TOKEN" not in seen["env"]
    assert seen["env"]["UV_PYTHON_INSTALL_DIR"] == "/x"
    assert demo_helper.provision_python("3.14;id", which=lambda _n: "/usr/bin/uv", runner=runner) is None
    assert demo_helper.provision_python("3.14", which=lambda _n: None, runner=runner) is None
    assert demo_helper.provision_python("3.14", which=lambda _n: "/usr/bin/uv", runner=lambda a, e: 1,
                                        install_dir="/x") is None


def test_wrong_python_reads_install_errors():
    assert demo_helper.wrong_python("error: the requested interpreter does not satisfy requires-python >=3.14.7") == "3.14"
    assert demo_helper.wrong_python("No interpreter found for Python 3.13 in managed installations") == "3.13"
    assert demo_helper.wrong_python("error: could not build wheels for lxml") is None


def test_study_runs_keep_the_old_python_behaviour(tmp_path):
    root = _checkout(tmp_path, python=">=3.14")
    called = []
    plan = demo_helper.build_setup_plan(REPO, [root], {"text": ""}, "3.12", "contree", "widget",
                                        python_available=lambda _v: None, pypi=_pypi,
                                        provision=lambda v: called.append(v) or v, auto_python=False)
    assert called == [] and plan["python"]["applied"] is False and "rule" not in plan["python"]
    assert "uv python install" not in demo_helper.contree_shell(plan)


def test_missing_python_is_a_hard_gate_with_the_rule_recorded(tmp_path):
    root = _checkout(tmp_path, python=">=3.14")
    plan = demo_helper.build_setup_plan(REPO, [root], {"text": ""}, "3.12", "local", "widget",
                                        python_available=lambda _v: None, pypi=_pypi, provision=lambda v: None)
    assert plan["python"]["gate_failed"] is True
    assert any("Python rule:" in line and "stops as a setup problem" in line for line in plan["lines"])


def test_provision_ignores_mirrors(monkeypatch):
    monkeypatch.setenv("UV_PYTHON_INSTALL_MIRROR", "https://evil.example/")
    monkeypatch.setenv("UV_PYTHON_DOWNLOADS_JSON_URL", "https://evil.example/x.json")
    seen = {}
    demo_helper.provision_python("3.14", which=lambda _n: "/usr/bin/uv",
                                 runner=lambda a, e: seen.update(e) or 0, install_dir="/x")
    assert "UV_PYTHON_INSTALL_MIRROR" not in seen and "UV_PYTHON_DOWNLOADS_JSON_URL" not in seen
    shell = demo_helper.contree_python_shell("3.14")
    assert "unset UV_PYTHON_INSTALL_MIRROR" in shell and demo_helper.UV_PIN in shell


def test_interpreter_the_sandbox_cannot_see_is_replaced_by_a_managed_one(tmp_path, monkeypatch):
    root = _checkout(tmp_path, python=">=3.14")
    monkeypatch.setattr(demo_helper, "_sandbox_can_see", lambda p: str(p).startswith("/usr/"))
    plan = demo_helper.build_setup_plan(REPO, [root], {"text": ""}, "3.12", "local", "widget",
                                        python_available=lambda _v: "/home/u/.local/bin/python3.14", pypi=_pypi,
                                        provision=lambda v: v)
    assert plan["python"]["switch"] == "3.14" and plan["python"]["auto_fix"] is True


def test_sides_with_no_shared_python_stop_as_a_setup_problem(tmp_path):
    main = _checkout(tmp_path / "m", python="<3.12")
    pr = _checkout(tmp_path / "p", python=">=3.13")
    plan = demo_helper.build_setup_plan(REPO, [main, pr], {"text": ""}, "3.12", "contree", "widget",
                                        python_available=lambda _v: None, pypi=None, provision=False)
    py = plan["python"]
    assert py["gate_failed"] is True and py["requested"] is None
    assert py["versions"]["main"]["requirement"] == "<3.12" and py["versions"]["pr"]["requirement"] == ">=3.13"
    assert "setup problem" in py["reason"] and "<3.12" in py["reason"] and ">=3.13" in py["reason"]
    assert "uv python install" not in demo_helper.contree_shell(plan)


def test_not_a_package_and_deps_only_plan(tmp_path):
    assert demo_helper.not_a_package("error: Multiple top-level packages discovered in a flat-layout: ['ee']")
    assert not demo_helper.not_a_package("error: could not resolve numpy")
    app = tmp_path / "app"
    app.mkdir()
    (app / "pyproject.toml").write_text('[project]\nname = "app"\ndependencies = ["django"]\n')
    assert demo_helper.deps_only_plan(app) == {"kind": "uv-sync", "frozen": False, "source": "pyproject.toml"}
    (app / "uv.lock").write_text("")
    assert demo_helper.deps_only_plan(app)["frozen"] is True
    reqs = tmp_path / "reqs"
    reqs.mkdir()
    (reqs / "requirements.txt").write_text("django\n")
    (reqs / "requirements-dev.txt").write_text("pytest\n")
    assert demo_helper.deps_only_plan(reqs)["files"] == ["requirements-dev.txt", "requirements.txt"]
    empty = tmp_path / "empty"
    empty.mkdir()
    assert demo_helper.deps_only_plan(empty) is None


def test_gap_text_reads_the_pytest_collection_error(tmp_path):
    rec = {"verdict": "could_not_verify",
           "reason": "tests produced no results on one side (collection failed; see pytest logs)"}
    assert demo_helper.gap_name(demo_helper.gap_text(rec)) == "setup"
    (tmp_path / "pytest-pr-1.log").write_text("E   ModuleNotFoundError: No module named 'gitlab'\n")
    (tmp_path / "junit-pr-1.xml").write_text(
        "<testsuite><testcase><failure>ModuleNotFoundError: No module named 'gitlab'</failure></testcase></testsuite>")
    text = demo_helper.gap_text(rec, log_dir=tmp_path)
    assert "No module named 'gitlab'" in text
    assert demo_helper.gap_name(text) == "gitlab"
    assert "No module named 'gitlab'" in demo_helper.failure_line(text)
    summary = {"verdict": "could_not_verify", "reason": "collection failed; see pytest logs",
               "per_run": [{"pytest_summary": "E   ModuleNotFoundError: No module named 'requests'\n"}]}
    assert demo_helper.gap_name(demo_helper.gap_text(summary)) == "requests"
    assert demo_helper.gap_name(demo_helper.gap_text(summary, log_dir=tmp_path)) == "requests"


def test_failure_line_keeps_a_system_failure_ahead_of_an_import_error():
    generic = ("tests produced no results on one side (collection failed; see pytest logs)\n"
               "ModuleNotFoundError: No module named 'gitlab'")
    assert "No module named 'gitlab'" in demo_helper.failure_line(generic)
    system = generic + "\nImportError: libEGL.so.1: cannot open shared object file: No such file or directory"
    line = demo_helper.failure_line(system)
    assert "libEGL.so.1" in line and "cannot open shared object" in line


def test_pytest_error_feeds_the_existing_lookup_and_installs_a_declared_module(tmp_path):
    (tmp_path / "pytest-main-1.log").write_text("E   ModuleNotFoundError: No module named 'numpy'\n")
    queries, calls = [], []
    bare = {"verdict": "could_not_verify",
            "reason": "tests produced no results on one side (collection failed; see pytest logs)"}
    demo_helper.retry_unverified(
        bare, lambda: (_ for _ in ()).throw(AssertionError("rerun")),
        lambda *_a: (_ for _ in ()).throw(AssertionError("install")),
        ["numpy>=1.24"], "", None, REPO, False)
    assert bare["reason"].startswith("tests produced no results")

    def lookup(query):
        queries.append(query)
        return {"results": []}

    rec = {"verdict": "could_not_verify",
           "reason": "tests produced no results on one side (collection failed; see pytest logs)"}
    demo_helper.retry_unverified(
        rec, lambda: {"verdict": "verified", "reason": "the tests passed"},
        lambda side, requirement: calls.append((side, requirement)) or (True, "1.26"),
        ["numpy>=1.24"], "", lambda _name: None, REPO, False, lookup=lookup, log_dir=tmp_path)
    assert queries and "No module named 'numpy'" in queries[0]
    assert calls == [("main", "numpy>=1.24"), ("pr", "numpy>=1.24")]
    assert rec["verdict"] == "verified"


def test_lookup_does_not_invent_an_import_to_package_mapping(tmp_path):
    (tmp_path / "pytest-pr-1.log").write_text("E   ModuleNotFoundError: No module named 'gitlab'\n")
    queries, calls = [], []

    def lookup(query):
        queries.append(query)
        return {"results": [{"url": "https://github.com/acme/widget",
                             "content": "acme/widget\npip install python-gitlab\n"}]}

    rec = {"verdict": "could_not_verify",
           "reason": "tests produced no results on one side (collection failed; see pytest logs)",
           "library": "widget"}
    demo_helper.retry_unverified(
        rec, lambda: calls.append("rerun") or {"verdict": "could_not_verify", "reason": "still"},
        lambda side, requirement: calls.append((side, requirement)) or (True, "1"),
        ["python-gitlab>=4"], "", lambda _name: LINK, REPO, False, lookup=lookup, log_dir=tmp_path)
    assert queries and "No module named 'gitlab'" in queries[0]
    assert calls == []
    assert "python-gitlab" not in json.dumps(rec["demo_helper"].get("gap_retry"))
    assert rec["reason"].startswith("could not verify: setup gap gitlab")
    assert "No module named 'gitlab'" in rec["reason"]


def test_missing_library_stays_unverified_when_system_installs_are_on(tmp_path):
    (tmp_path / "pytest-pr-1.log").write_text(
        "E   ImportError: libEGL.so.1: cannot open shared object file: No such file or directory\n")
    asked = []
    rec = {"verdict": "could_not_verify",
           "reason": "tests produced no results on one side (collection failed; see pytest logs)"}
    demo_helper.retry_unverified(
        rec, lambda: asked.append("rerun") or {"verdict": "verified", "reason": "ok"},
        lambda *_a: asked.append("pip") or (True, "1"),
        [], "", lambda _name: LINK, REPO, True,
        install_system=lambda name: asked.append(("apt", name)) or True,
        log_dir=tmp_path, project_text="apt-get install some-os-pkg", apt_check=lambda _name: True)
    assert asked == []
    assert rec["verdict"] == "could_not_verify"
    lim = rec["demo_helper"]["limitations"][0]
    assert "libEGL.so.1" in lim["needed"] and "libEGL.so.1" in lim["error"]
    assert "some-os-pkg" not in json.dumps(lim)
    assert rec["demo_helper"]["gap_retry"]["reran"] is False


def test_missing_shared_library_is_named_in_the_reason(tmp_path):
    (tmp_path / "pytest-pr-1.log").write_text(
        "E   ImportError: libEGL.so.1: cannot open shared object file: No such file or directory\n")
    systems = []
    rec = {"verdict": "could_not_verify",
           "reason": "tests produced no results on one side (collection failed; see pytest logs)"}
    demo_helper.retry_unverified(
        rec, lambda: systems.append("rerun"), lambda *_a: systems.append("pip"),
        [], "", lambda _name: LINK, REPO, False,
        install_system=lambda name: systems.append(("apt", name)) or False,
        log_dir=tmp_path, project_text="", apt_check=lambda _name: False)
    assert systems == []
    assert "libEGL.so.1" in rec["reason"]
    assert "cannot open shared object" in rec["reason"]


def test_pytest_log_secrets_stay_out_of_the_reason(tmp_path, monkeypatch):
    secret = "tvly-test-secret-value"
    monkeypatch.setenv("TAVILY_API_KEY", secret)
    (tmp_path / "pytest-pr-1.log").write_text(
        f"E   ModuleNotFoundError: No module named 'numpy' token={secret}\n")
    rec = {"verdict": "could_not_verify",
           "reason": "tests produced no results on one side (collection failed; see pytest logs)"}
    demo_helper.retry_unverified(rec, None, lambda *_a: (True, "1"), [], "", None, REPO, False, log_dir=tmp_path)
    assert secret not in json.dumps(rec)
    assert "[redacted]" in rec["reason"]
    assert "No module named 'numpy'" in rec["reason"]


def test_declared_requirements_include_extras(tmp_path):
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "app"\ndependencies = ["requests"]\n\n'
        '[project.optional-dependencies]\nci = ["python-gitlab>=4"]\ntest = ["pytest>=7"]\n')
    lines = demo_helper.declared_requirement_lines(tmp_path)
    assert "requests" in lines
    assert any(line.startswith("python-gitlab") for line in lines)
    assert any(line.startswith("pytest") for line in lines)


def test_contree_python_choice_ignores_host_pythons(tmp_path, monkeypatch):
    """A >=3.14 project gets 3.14 installed in Contree even when the host has 3.14 and the image has 3.12,
    and a 3.12 image is not mistaken for the host's 3.14."""
    from ops import daily_run
    from poc import contree_sandboxes
    monkeypatch.setattr(contree_sandboxes, "BASE_IMAGE", "docker.io/library/python:3.12-slim-bookworm")
    monkeypatch.setattr(demo_helper, "find_python", lambda version, which=None: None)
    a = SimpleNamespace(python="3.14", bench=None, sandbox_backend="contree", pr=["x"], product_check=True)
    root = _checkout(tmp_path, python=">=3.14")
    rec = {}
    try:
        plan = daily_run._product_plan(a, rec, "acme/widget", {"dist": "widget"}, [root], pypi=_pypi)
        # The image is picked from requires-python (poc/probe_python.py): a 3.14 image, not the host's 3.14.
        assert rec["contree_python"]["version"] == "3.14"
        assert contree_sandboxes.current_image() == "docker.io/library/python:3.14-slim-bookworm"
        assert plan["python"]["requested"] == "3.14" and plan["python"]["current"] == "3.14"
    finally:
        contree_sandboxes.select_image(None)


def test_contree_lowest_matching_version_not_host_choice(tmp_path, monkeypatch):
    from ops import daily_run
    from poc import contree_sandboxes
    monkeypatch.setattr(contree_sandboxes, "BASE_IMAGE", "docker.io/library/python:3.10-slim")
    monkeypatch.setattr(demo_helper, "find_python",
                        lambda version, which=None: "/usr/bin/python3.13" if version == "3.13" else None)
    a = SimpleNamespace(python="3.13", bench=None, sandbox_backend="contree", pr=["x"], product_check=True)
    root = _checkout(tmp_path, python=">=3.11")
    try:
        plan = daily_run._product_plan(a, {}, "acme/widget", {"dist": "widget"}, [root], pypi=_pypi)
        assert plan["python"]["requested"] == "3.11" and contree_sandboxes.image_python() == "3.11"
    finally:
        contree_sandboxes.select_image(None)


@pytest.mark.parametrize("image,want", [("docker.io/library/python:3.12-slim-bookworm", "3.12"),
                                        ("python:3.14", "3.14"), ("python:3.13.2-slim", "3.13"),
                                        ("example.org/team/base:latest", ""), ("ubuntu:24.04", "")])
def test_image_python_reads_tag(image, want):
    from poc import contree_sandboxes
    assert contree_sandboxes.image_python(image) == want
