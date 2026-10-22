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


def _flat_product(tmp_path, monkeypatch, rec, step, checkout, calls):
    monkeypatch.setattr(daily_run, "install_side", lambda *a, **k: calls.append("install") or _flat_layout(*a, **k))
    monkeypatch.setattr(daily_run, "install_deps_only", lambda *a, **k: calls.append(("deps", a[1], a[2])) or (True, ""))
    a = SimpleNamespace(python="3.14", pr="https://github.com/a/b/pull/1", product_check=True, bench=None)
    return daily_run._install_with_helper(a, rec, step, tmp_path / ("v-" + step.split()[0]), checkout, None,
                                          tmp_path / "log", 10, None, None, max_retries=1)


def test_flat_layout_on_main_falls_back_to_declared_dependencies(tmp_path, monkeypatch):
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "app"\ndependencies = []\n')
    (tmp_path / "uv.lock").write_text("")
    calls, rec = [], {}
    ok, _ = _flat_product(tmp_path, monkeypatch, rec, "main install", tmp_path, calls)
    plan = {"kind": "uv-sync", "frozen": True, "source": "uv.lock"}
    assert ok is True and calls == ["install", ("deps", tmp_path, plan)]
    assert rec["demo_helper"]["deps_only"] == plan
    assert any("project's own folder was put on the import path" in n for n in rec["demo_helper"]["auto_fixes"])


def test_flat_layout_on_main_with_nothing_declared_stays_unsupported(tmp_path, monkeypatch):
    calls, rec = [], {}
    ok, why = _flat_product(tmp_path, monkeypatch, rec, "main install", tmp_path, calls)
    assert ok is False and why == demo_helper.FLAT_LAYOUT_REASON
    assert calls == ["install"] and "deps_only" not in rec.get("demo_helper", {})
    verdict, reason, _flags = daily_run.tests_verdict(None, why, None, None)
    assert verdict == "could_not_verify" and reason == why


def test_flat_layout_on_both_sides_gets_the_same_setup(tmp_path, monkeypatch):
    main, pr = tmp_path / "main", tmp_path / "pr"
    for side in (main, pr):
        side.mkdir()
    (main / "requirements.txt").write_text("")
    (pr / "pyproject.toml").write_text('[project]\nname = "app"\n')
    calls, rec = [], {}
    assert _flat_product(tmp_path, monkeypatch, rec, "main install", main, calls)[0] is True
    assert _flat_product(tmp_path, monkeypatch, rec, "PR install", pr, calls)[0] is True
    deps = [c for c in calls if c != "install"]
    plan = {"kind": "requirements", "files": ["requirements.txt"], "source": "requirements.txt"}
    assert deps == [("deps", main, plan), ("deps", pr, plan)]


def test_flat_layout_on_the_pr_side_only_does_not_fall_back(tmp_path, monkeypatch):
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "app"\n')
    calls, rec = [], {}
    ok, why = _flat_product(tmp_path, monkeypatch, rec, "PR install", tmp_path, calls)
    assert ok is False and why == demo_helper.FLAT_LAYOUT_REASON and calls == ["install"]


def _not_a_python_project(venv, checkout, chosen, lg, py, *rest):
    lg.write_text("error: /src does not appear to be a Python project\n")
    return False, "install failed (1)"


def test_flat_layout_on_the_pr_side_only_is_not_needs_attention(tmp_path, monkeypatch):
    pr = tmp_path / "side-pr"
    pr.mkdir()
    (pr / "pyproject.toml").write_text('[project]\nname = "app"\n')
    log = tmp_path / "setup-pr.log"
    monkeypatch.setattr(daily_run, "install_side", _flat_layout)
    a = SimpleNamespace(python="3.12", pr="https://github.com/acme/widget/pull/1", product_check=True, bench=None)
    rec = {"files": {}, "probes": None}
    ok, why = daily_run._install_with_helper(
        a, rec, "PR install", tmp_path / "venv-pr", pr, None, log, 10, None, None,
        max_retries=daily_run._pr_side_retries(a))
    assert ok is False and why == demo_helper.FLAT_LAYOUT_REASON
    # The blame rule uses two tries plus an "error:" line. Put that count back: the stop above is not stored
    # as a setup failure, and a flat layout must still stay could not verify.
    rec.setdefault("demo_helper", {}).setdefault("setup", {})["attempts"] = 2
    why = daily_run._pr_own_failure(a, rec, "PR install", why, log, same_setup=True)
    daily_run._store_verdict(rec, None, why, None)
    assert rec["verdict"] == "could_not_verify" and why == demo_helper.FLAT_LAYOUT_REASON
    assert "pr_build_failure" not in rec


def test_not_a_python_project_still_installs_declared_dependencies(tmp_path, monkeypatch):
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "app"\ndependencies = []\n')
    (tmp_path / "uv.lock").write_text("")
    monkeypatch.setattr(daily_run, "install_side", _not_a_python_project)
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


def test_retry_python_skips_an_interpreter_the_sandbox_cannot_see():
    from poc import demo_helper
    provisioned = []
    got = demo_helper.retry_python("3.14", find=lambda v: "/home/someone/.local/bin/python3.14",
                                   provision=lambda v: provisioned.append(v) or v,
                                   can_see=lambda p: p.startswith("/usr/"))
    assert got == "3.14" and provisioned == ["3.14"]


def test_retry_python_uses_a_visible_interpreter_without_provisioning():
    from poc import demo_helper
    got = demo_helper.retry_python("3.14", find=lambda v: "/usr/bin/python3.14",
                                   provision=lambda v: (_ for _ in ()).throw(AssertionError("no download")),
                                   can_see=lambda p: p.startswith("/usr/"))
    assert got == "/usr/bin/python3.14"


def test_retry_python_gives_up_when_nothing_visible_and_provision_fails():
    from poc import demo_helper
    assert demo_helper.retry_python("3.14", find=lambda v: "/home/x/python3.14", provision=lambda v: None,
                                    can_see=lambda p: False) is None


def test_disk_full_stops_without_a_retry_and_removes_build_files(tmp_path, monkeypatch):
    calls = []
    venv = tmp_path / "venv-main"
    (venv / "site").mkdir(parents=True)
    (venv / "site" / "wheel").write_text("wheel")
    home = tmp_path / "home-main"
    (home / ".tmp" / "pip-build").mkdir(parents=True)
    (home / ".tmp" / "pip-build" / "part").write_text("temp")
    (home / ".uv-cache").mkdir()
    (home / ".uv-cache" / "wheel").write_text("cache")
    (home / "pip-unpack").mkdir()
    (home / "pip-unpack" / "x").write_text("x")

    def fake_install(_venv, _checkout, _chosen, lg, py, *_rest):
        calls.append(py)
        lg.write_text("ERROR: Could not install wheels\nNo space left on device\n")
        return False, "install failed (1)"

    monkeypatch.setattr(daily_run, "install_side", fake_install)
    a = SimpleNamespace(python="3.12", pr="https://github.com/a/b/pull/1", product_check=True, bench=None)
    ok, why = daily_run._install_with_helper(a, {}, "main install", venv, tmp_path, None, tmp_path / "log",
                                             10, None, None)
    assert ok is False and why == demo_helper.DISK_FULL_REASON
    assert calls == ["3.12"]
    assert not venv.exists()
    assert not (home / ".tmp").exists() and not (home / ".uv-cache").exists()
    assert not (home / "pip-unpack").exists()
    verdict, reason, _flags = daily_run.tests_verdict(None, why, None, None)
    assert verdict == "could_not_verify" and reason == why


def test_disk_full_on_a_study_run_keeps_the_old_retries(tmp_path, monkeypatch):
    calls = []
    kept = tmp_path / "home-main" / ".tmp"
    kept.mkdir(parents=True)
    (kept / "part").write_text("keep")

    def fake_install(_venv, _checkout, _chosen, lg, _py, *_rest):
        calls.append(1)
        lg.write_text("No space left on device\n")
        return False, "install failed (1)"

    monkeypatch.setattr(daily_run, "install_side", fake_install)
    a = SimpleNamespace(python="3.12", pr="https://github.com/a/b/pull/1", product_check=False, bench=None)
    ok, why = daily_run._install_with_helper(a, {}, "main install", tmp_path / "venv-main", tmp_path, None,
                                             tmp_path / "log", 10, None, None)
    assert ok is False and why.startswith("install failed")
    assert len(calls) == demo_helper.MAX_SETUP_RETRIES + 1
    assert (kept / "part").is_file()


def test_required_gpu_dependency_stops_before_install(tmp_path, monkeypatch):
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "app"\ndependencies = ["nvidia-cublas-cu12", "numpy"]\n')
    calls = []
    monkeypatch.setattr(daily_run, "install_side", lambda *a, **k: calls.append("install") or (True, ""))
    a = SimpleNamespace(python="3.12", pr="https://github.com/a/b/pull/1", product_check=True, bench=None)
    ok, why = daily_run._install_with_helper(a, {}, "main install", tmp_path / "v", tmp_path, None, tmp_path / "log",
                                             10, None, None)
    assert ok is False and calls == []
    assert "GPU / CUDA" in why and "nvidia-cublas-cu12" in why
    verdict, reason, _flags = daily_run.tests_verdict(None, why, None, None)
    assert verdict == "could_not_verify" and reason == why


def test_nvidia_name_without_a_cuda_build_does_not_stop_the_install(tmp_path, monkeypatch):
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "app"\ndependencies = ["nvidia-ml-py", "numpy"]\n')
    calls = []
    monkeypatch.setattr(daily_run, "install_side", lambda *a, **k: calls.append("install") or (True, ""))
    a = SimpleNamespace(python="3.12", pr="https://github.com/a/b/pull/1", product_check=True, bench=None)
    ok, why = daily_run._install_with_helper(a, {}, "main install", tmp_path / "v", tmp_path, None, tmp_path / "log",
                                             10, None, None)
    assert ok is True and calls == ["install"]
    assert demo_helper.gpu_only_requirement(tmp_path) is None
    assert not str(why).startswith("unsupported")


def test_optional_cuda_extra_does_not_block_the_install(tmp_path, monkeypatch):
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "app"\ndependencies = ["numpy"]\n\n'
        '[project.optional-dependencies]\ncuda = ["nvidia-cublas-cu12"]\n')
    (tmp_path / "requirements-dev.txt").write_text("cuda-python\n")
    calls = []
    monkeypatch.setattr(daily_run, "install_side", lambda *a, **k: calls.append("install") or (True, ""))
    a = SimpleNamespace(python="3.12", pr="https://github.com/a/b/pull/1", product_check=True, bench=None)
    ok, _why = daily_run._install_with_helper(a, {}, "main install", tmp_path / "v", tmp_path, None, tmp_path / "log",
                                              10, None, None)
    assert ok is True and calls == ["install"]


def test_cuda_wheel_marker_is_a_required_gpu_signal(tmp_path):
    (tmp_path / "requirements.txt").write_text("scuda\n")
    assert demo_helper.gpu_only_requirement(tmp_path) is None
    (tmp_path / "requirements.txt").write_text("torch+cu121\n")
    assert demo_helper.gpu_only_requirement(tmp_path) == "torch+cu121"


def test_study_run_still_installs_when_a_gpu_package_is_required(tmp_path, monkeypatch):
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "app"\ndependencies = ["cuda-python"]\n')
    calls = []
    monkeypatch.setattr(daily_run, "install_side", lambda *a, **k: calls.append("install") or (True, ""))
    a = SimpleNamespace(python="3.12", pr="https://github.com/a/b/pull/1", product_check=False, bench=None)
    ok, why = daily_run._install_with_helper(a, {}, "main install", tmp_path / "v", tmp_path, None, tmp_path / "log",
                                             10, None, None)
    assert ok is True and calls == ["install"] and not str(why).startswith("unsupported")


def test_gap_retry_reads_pytest_logs_and_checkout_extras(tmp_path, monkeypatch):
    root = tmp_path / "src"
    root.mkdir()
    (root / "pyproject.toml").write_text(
        '[project]\nname = "app"\ndependencies = ["requests"]\n\n'
        '[project.optional-dependencies]\nci = ["python-gitlab>=4"]\n')
    (tmp_path / "pytest-pr-1.log").write_text("E   ModuleNotFoundError: No module named 'gitlab'\n")
    seen = {}

    def fake_retry(rec, rerun, install_one, declared, *args, **kwargs):
        seen["declared"] = list(declared)
        seen["log_dir"] = kwargs.get("log_dir")
        return rec

    monkeypatch.setattr("poc.demo_helper.retry_unverified", fake_retry)
    a = SimpleNamespace(bench=None, sandbox_backend="local", pr="https://github.com/acme/widget/pull/1",
                        product_check=True)
    daily_run._retry_setup_gap(a, {}, "acme/widget", tmp_path, {}, None, checkouts=[root])
    assert any(str(req).startswith("python-gitlab") for req in seen["declared"])
    assert seen["log_dir"] == tmp_path


def _pyproject(path, deps):
    path.mkdir(parents=True, exist_ok=True)
    (path / "pyproject.toml").write_text(f'[project]\nname = "app"\ndependencies = {deps}\n')


def test_a_dependency_added_only_by_the_pr_is_not_trusted_or_installed(tmp_path, monkeypatch):
    from poc import tavily_docs
    monkeypatch.setattr(tavily_docs, "available", lambda: False)
    main = tmp_path / "side-main"
    pr = tmp_path / "side-pr"
    _pyproject(main, '["kept"]')
    _pyproject(pr, '["kept", "added-by-pr"]')
    work = tmp_path / "nightly"
    packaging = work / "packaging"
    src = work / "src"
    _pyproject(packaging, '["kept"]')
    _pyproject(src, '["kept", "added-by-pr"]')
    assert daily_run.nightly_main_checkout(work) == packaging
    assert daily_run.declared_checkouts(packaging, src) == [packaging]
    assert daily_run.declared_checkouts(main, pr) == [main]
    (tmp_path / "pytest-pr-1.log").write_text("E   ModuleNotFoundError: No module named 'added_by_pr'\n")
    installed = []

    def fake_run(cmd, *args, **kwargs):
        installed.append([str(part) for part in cmd])
        return 0, 0.0

    monkeypatch.setattr(daily_run, "run", fake_run)
    monkeypatch.setattr(daily_run, "uv_bin", lambda: "uv")
    monkeypatch.setattr(daily_run, "side_home", lambda venv: tmp_path / "home")
    monkeypatch.setattr(daily_run, "base_env", lambda *args, **kwargs: {})
    monkeypatch.setattr(daily_run, "side_sandbox", lambda *args, **kwargs: {})
    monkeypatch.setattr(daily_run, "_dist_version", lambda *args, **kwargs: "1")
    rec = {"verdict": "could_not_verify", "reason": "could not verify: setup gap setup", "pr": {"number": 4},
           "library": "app", "demo_helper": {"setup_plan": {"packages": []}, "tavily": {}}}
    a = SimpleNamespace(bench=None, sandbox_backend="contree", pr="https://github.com/acme/widget/pull/4",
                        product_check=True, build_timeout=30)
    venvs = {"main": tmp_path / "venv-main", "pr": tmp_path / "venv-pr"}
    for selection in (daily_run.declared_checkouts(main, pr),
                      daily_run.declared_checkouts(daily_run.nightly_main_checkout(work), src)):
        installed.clear()
        rec = {"verdict": "could_not_verify", "reason": "could not verify: setup gap setup", "pr": {"number": 4},
               "library": "app", "demo_helper": {"setup_plan": {"packages": []}, "tavily": {}}}
        daily_run._retry_setup_gap(a, rec, "acme/widget", tmp_path, venvs, lambda: {"verdict": "verified",
                                                                                   "reason": "ok"},
                                   checkouts=selection)
        blob = " ".join(" ".join(cmd) for cmd in installed)
        assert "added-by-pr" not in blob and installed == []
        notes = " ".join(rec["demo_helper"].get("notes") or [])
        assert "added_by_pr" in notes and "refused" in notes
