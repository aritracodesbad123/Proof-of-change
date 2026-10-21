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


def test_deps_only_install_runs_uv_sync_in_the_sandbox_and_adds_the_path(tmp_path, monkeypatch):
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
