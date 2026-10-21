from types import SimpleNamespace

from ops import daily_run
from poc import demo_helper


def test_failed_python_setup_stops_before_any_install(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(daily_run, "install_side", lambda *a, **k: calls.append(a) or (True, ""))
    rec = {"demo_helper": {"setup_plan": {"python": {"requested": "3.14", "gate_failed": True,
                                                     "reason": "not applied"}}}}
    a = SimpleNamespace(python="3.12", pr="https://github.com/a/b/pull/1", product_check=True, bench=None)
    ok, why = daily_run._install_with_helper(a, rec, "main install", tmp_path / "v", tmp_path, None,
                                             tmp_path / "log", 10, None, None)
    assert ok is False and calls == [] and "setup problem" in why
    assert rec["demo_helper"]["setup"]["counts_as_verdict"] is False


def test_wrong_python_error_installs_it_and_retries_once(tmp_path, monkeypatch):
    log = tmp_path / "log"
    seen = []

    def fake_install(venv, checkout, chosen, lg, py, *rest):
        seen.append(py)
        if py == "3.12":
            lg.write_text("error: the current Python does not satisfy requires-python >=3.14.7\n")
            return False, "install failed"
        return True, ""
    monkeypatch.setattr(daily_run, "install_side", fake_install)
    monkeypatch.setattr(demo_helper, "find_python", lambda v: None)
    monkeypatch.setattr(demo_helper, "provision_python", lambda v: v)
    rec = {}
    a = SimpleNamespace(python="3.12", pr="https://github.com/a/b/pull/1", product_check=True, bench=None)
    ok, _ = daily_run._install_with_helper(a, rec, "main install", tmp_path / "v", tmp_path, None, log, 10, None, None)
    assert ok is True and seen == ["3.12", "3.14"]
    assert any(n.startswith("Auto-fix:") for n in rec["demo_helper"]["auto_fixes"])
    study = SimpleNamespace(python="3.12", pr="https://github.com/a/b/pull/1", product_check=False, bench=None)
    seen.clear()
    ok, _ = daily_run._install_with_helper(study, {}, "main install", tmp_path / "v", tmp_path, None, log, 10, None,
                                           None)
    assert ok is False and set(seen) == {"3.12"}


def _flat_layout(venv, checkout, chosen, lg, py, *rest):
    lg.write_text("error: Multiple top-level packages discovered in a flat-layout: ['ee', 'posthog']\n")
    return False, "install failed (1)"


def test_flat_layout_installs_declared_dependencies_only(tmp_path, monkeypatch):
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "app"\ndependencies = []\n')
    (tmp_path / "uv.lock").write_text("")
    monkeypatch.setattr(daily_run, "install_side", _flat_layout)
    got = []
    monkeypatch.setattr(daily_run, "install_deps_only", lambda *a, **k: got.append(a[2]) or (True, ""))
    rec = {}
    a = SimpleNamespace(python="3.14", pr="https://github.com/a/b/pull/1", product_check=True, bench=None)
    ok, _ = daily_run._install_with_helper(a, rec, "main install", tmp_path / "v", tmp_path, None, tmp_path / "log",
                                           10, None, None)
    assert ok is True and got == [{"kind": "uv-sync", "frozen": True, "source": "uv.lock"}]
    assert any("only the dependencies it declares (uv.lock)" in n for n in rec["demo_helper"]["auto_fixes"])


def test_flat_layout_is_left_alone_on_study_runs(tmp_path, monkeypatch):
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "app"\n')
    monkeypatch.setattr(daily_run, "install_side", _flat_layout)
    monkeypatch.setattr(daily_run, "install_deps_only", lambda *a, **k: (_ for _ in ()).throw(AssertionError()))
    a = SimpleNamespace(python="3.12", pr="https://github.com/a/b/pull/1", product_check=False, bench=None)
    ok, _ = daily_run._install_with_helper(a, {}, "main install", tmp_path / "v", tmp_path, None, tmp_path / "log",
                                           10, None, None)
    assert ok is False


def _git_checkout(path):
    import subprocess
    path.mkdir(parents=True, exist_ok=True)
    (path / "app.py").write_text("x = 1\n")
    for c in (["init", "-q"], ["add", "-A"], ["-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "c"]):
        subprocess.run(["git", "-C", str(path), *c], check=True, capture_output=True)
    return path


def test_deps_only_install_runs_uv_sync_in_the_sandbox_and_adds_the_path(tmp_path, monkeypatch):
    _git_checkout(tmp_path / "src")
    cmds = []

    def fake_run(c, log, cwd=None, env=None, timeout=None, sbx=None):
        assert cwd == tmp_path / "src"
        cmds.append([str(x) for x in c])
        if c[1] == "venv":
            (tmp_path / "v" / "lib" / "python3.14" / "site-packages").mkdir(parents=True)
        assert sbx is not None
        return 0, 0.0
    monkeypatch.setattr(daily_run, "run", fake_run)
    ok, _ = daily_run.install_deps_only(tmp_path / "v", tmp_path / "src", {"kind": "uv-sync", "frozen": True},
                                        tmp_path / "log", "3.14", 10)
    assert ok is True
    assert any(c[:2] == ["uv", "export"] and "--no-emit-project" in c and "--frozen" in c for c in cmds)
    assert any(c[:3] == ["uv", "pip", "install"] and "-r" in c for c in cmds)
    pth = tmp_path / "v" / "lib" / "python3.14" / "site-packages" / "poc-project-path.pth"
    assert pth.read_text().strip() == str(tmp_path / "src")


def test_contree_shell_has_the_deps_only_fallback_only_when_asked():
    from poc import contree_sandboxes
    plain = contree_sandboxes.install_shell_source("a/b", "x")
    product = contree_sandboxes.install_shell_source("a/b", "x", deps_only_fallback=True)
    assert "--no-install-project" not in plain and "--no-install-project" in product


def test_commit_guard_accepts_a_deps_only_checkout_at_the_right_commit(tmp_path, monkeypatch):
    venv, co = tmp_path / "v", tmp_path / "co"
    site = venv / "lib" / "python3.14" / "site-packages"
    site.mkdir(parents=True)
    co.mkdir()
    (site / "poc-project-path.pth").write_text(str(co) + "\n")
    monkeypatch.setattr(daily_run, "_checkout_head", lambda _c: "a" * 40)
    ok, info = daily_run.check_installed_commit(venv, "x", "a" * 40, co)
    assert ok is True and info["deps_only"] is True
    ok, _ = daily_run.check_installed_commit(venv, "x", "b" * 40, co)
    assert ok is False
    (site / "poc-project-path.pth").write_text(str(tmp_path / "elsewhere") + "\n")
    ok, _ = daily_run.check_installed_commit(venv, "x", "a" * 40, co)
    assert ok is False


def _fake_install(tmp_path, during):
    def fake_run(c, log, cwd=None, env=None, timeout=None, sbx=None):
        if c[1] == "venv":
            (tmp_path / "v" / "lib" / "python3.14" / "site-packages").mkdir(parents=True, exist_ok=True)
        if c[1] == "export":
            (tmp_path / "src" / ".poc-declared-deps.txt").write_text("django\n")
        if c[:3] == ["uv", "pip", "install"] and "-r" in c:
            during()
        return 0, 0.0
    return fake_run


def test_a_file_changed_during_install_is_a_setup_problem(tmp_path, monkeypatch):
    src = _git_checkout(tmp_path / "src")
    monkeypatch.setattr(daily_run, "run", _fake_install(tmp_path, lambda: (src / "app.py").write_text("x = 2\n")))
    ok, why = daily_run.install_deps_only(tmp_path / "v", src, {"kind": "uv-sync", "frozen": True},
                                          tmp_path / "log", "3.14", 10)
    assert ok is False and why.startswith("setup problem:") and "app.py" in why
    assert not (tmp_path / "v" / "lib" / "python3.14" / "site-packages" / "poc-project-path.pth").exists()


def test_an_untracked_file_from_install_is_a_setup_problem_but_our_deps_file_is_not(tmp_path, monkeypatch):
    src = _git_checkout(tmp_path / "src")
    monkeypatch.setattr(daily_run, "run", _fake_install(tmp_path, lambda: (src / "planted.py").write_text("")))
    ok, why = daily_run.install_deps_only(tmp_path / "v", src, {"kind": "uv-sync", "frozen": True},
                                          tmp_path / "log", "3.14", 10)
    assert ok is False and "planted.py" in why and ".poc-declared-deps.txt" not in why


def test_a_planted_pth_is_replaced_by_ours(tmp_path, monkeypatch):
    src = _git_checkout(tmp_path / "src")
    site = tmp_path / "v" / "lib" / "python3.14" / "site-packages"

    def plant():
        site.mkdir(parents=True, exist_ok=True)
        (site / "poc-project-path.pth").write_text("/somewhere/else\nimport os\n")
    monkeypatch.setattr(daily_run, "run", _fake_install(tmp_path, plant))
    ok, _ = daily_run.install_deps_only(tmp_path / "v", src, {"kind": "uv-sync", "frozen": True},
                                        tmp_path / "log", "3.14", 10)
    assert ok is True
    assert (site / "poc-project-path.pth").read_text() == str(src) + "\n"
    planted_link = site / "poc-project-path.pth"
    planted_link.unlink()
    planted_link.symlink_to(tmp_path / "target.txt")
    daily_run.write_project_path(tmp_path / "v", src)
    assert not planted_link.is_symlink() and planted_link.read_text() == str(src) + "\n"


def test_contree_deps_only_shell_checks_the_tree_and_writes_the_path_last():
    from poc import contree_sandboxes
    shell = contree_sandboxes.install_shell_source("a/b", "x", deps_only_fallback=True)
    assert "git status --porcelain --untracked-files=all" in shell
    assert shell.index("git status --porcelain") < shell.index("poc-project-path.pth")
    assert 'rm -f "$SP/poc-project-path.pth"' in shell
