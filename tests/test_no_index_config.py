"""Product-path installs ignore uv/pip config files, the project's [tool.uv.sources] and index env settings."""
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from ops import daily_run
from poc import contree_sandboxes


def _checkout(path: Path) -> Path:
    path.mkdir(parents=True)
    (path / "pyproject.toml").write_text('[project]\nname = "p"\nversion = "0"\n'
                                         '[tool.uv]\nextra-index-url = ["https://example.invalid/s"]\n'
                                         '[tool.uv.sources]\nokpkg = { path = "../okpkg" }\n')
    (path / "uv.toml").write_text('index-url = "https://example.invalid/s"\n')
    for c in (["init", "-q"], ["add", "-A"], ["-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "x"],
              ["tag", "v0"]):
        subprocess.run(["git", "-C", str(path), *c], check=True, capture_output=True)
    return path


def _capture(monkeypatch):
    calls = []

    def fake(c, log, cwd=None, env=None, timeout=None, sbx=None):
        calls.append(([str(x) for x in c], dict(env or {})))
        return 0, 0.0
    monkeypatch.setattr(daily_run, "run", fake)
    monkeypatch.setattr(daily_run, "run_heavy", fake)
    return calls


def test_isolated_install_side_ignores_config_sources_and_index_env(tmp_path, monkeypatch):
    co = _checkout(tmp_path / "co")
    monkeypatch.setattr(daily_run, "base_env",
                        lambda home, install=False, **kw: {"PATH": "/bin", "UV_EXTRA_INDEX_URL": "x",
                                                           "PIP_INDEX_URL": "y", "UV_CACHE_DIR": "c", **kw})
    calls = _capture(monkeypatch)
    ok, _ = daily_run.install_side(tmp_path / "v", co, None, tmp_path / "log", "3.12", 10, None, isolated=True)
    assert ok
    uv = [(c, e) for c, e in calls if Path(c[0]).name == "uv"]
    assert uv and all("--no-config" in c for c, _ in uv)
    assert all("--no-sources" in c for c, _ in uv if c[1:3] == ["pip", "install"])
    for _c, e in uv:
        assert e["UV_NO_CONFIG"] == "1" and e["PIP_CONFIG_FILE"] == "/dev/null" and e["UV_CACHE_DIR"] == "c"
        assert "UV_EXTRA_INDEX_URL" not in e and "PIP_INDEX_URL" not in e


def test_study_install_side_is_unchanged(tmp_path, monkeypatch):
    co = _checkout(tmp_path / "co")
    calls = _capture(monkeypatch)
    daily_run.install_side(tmp_path / "v", co, None, tmp_path / "log", "3.12", 10, None)
    assert calls and not any("--no-config" in c or "--no-sources" in c for c, _ in calls)
    assert not any("PIP_CONFIG_FILE" in e for _c, e in calls)   # UV_NO_CONFIG=1 is already set for every install


def test_no_config_cmd_only_touches_uv():
    assert daily_run.no_config_cmd(["git", "status"]) == ["git", "status"]
    assert daily_run.no_config_cmd(["/x/uv", "venv", "v"])[-1] == "--no-config"
    got = daily_run.no_config_cmd(["uv", "pip", "install", "a"])
    assert got[-2:] == ["--no-config", "--no-sources"]
    assert daily_run.no_config_cmd(got) == got


def test_gap_retry_install_ignores_config(tmp_path, monkeypatch):
    src = (Path(daily_run.__file__)).read_text()
    block = src[src.index("def install_one(side, requirement):"):][:600]
    assert "no_config_cmd(" in block and "no_index_config_env(" in block


def test_contree_product_shell_clears_index_settings_and_config(tmp_path):
    product = contree_sandboxes.install_shell_source("a/b", "x", "python -m pip install -q okpkg",
                                                     deps_only_fallback=True)
    assert product.startswith(contree_sandboxes.NO_INDEX_CONFIG_SHELL)
    assert product.index("is still set") < product.index("pip install")
    assert product.index("export UV_NO_CONFIG=1 PIP_CONFIG_FILE=/dev/null") < product.index("pip install -q okpkg")
    assert product.count("uv sync -q --no-config") == 2
    study = contree_sandboxes.install_shell_source("a/b", "x")
    assert "UV_NO_CONFIG" not in study and "--no-config" not in study


def _run_sh(script_text, tmp_path, env):
    script = tmp_path / "s.sh"
    script.write_text(script_text)
    return subprocess.run(["sh", str(script)], env={"PATH": "/usr/bin:/bin", **env}, capture_output=True, text=True)


_SET = {"UV_EXTRA_INDEX_URL": "x", "UV_INDEX": "y", "UV_DEFAULT_INDEX": "d", "UV_FIND_LINKS": "f", "UV_NO_INDEX": "1",
        "UV_INSECURE_HOST": "h", "UV_INDEX_STRATEGY": "unsafe-best-match", "UV_INDEX_URL": "u", "UV_NO_CONFIG": "0",
        "PIP_INDEX_URL": "i", "PIP_EXTRA_INDEX_URL": "e", "PIP_FIND_LINKS": "f", "PIP_NO_INDEX": "1",
        "PIP_TRUSTED_HOST": "t", "PIP_CONFIG_FILE": "/tmp/evil.conf", "UV_CACHE_DIR": "c"}


def test_contree_isolation_shell_unsets_index_vars(tmp_path):
    assert "sed" not in contree_sandboxes.NO_INDEX_CONFIG_SHELL and "eval" not in contree_sandboxes.NO_INDEX_CONFIG_SHELL
    got = _run_sh(contree_sandboxes.NO_INDEX_CONFIG_SHELL + 'echo REACHED\nenv | grep -E "^(UV|PIP)_" | sort\n',
                  tmp_path, _SET)
    assert got.returncode == 0, got.stdout + got.stderr
    assert got.stdout.split() == ["REACHED", "PIP_CONFIG_FILE=/dev/null", "UV_CACHE_DIR=c", "UV_NO_CONFIG=1"]


@pytest.mark.parametrize("var", ["UV_EXTRA_INDEX_URL", "PIP_TRUSTED_HOST", "UV_INDEX_STRATEGY"])
def test_contree_isolation_check_fails_closed_when_a_var_survives(tmp_path, var):
    # simulated failure: the unset did not take, so the check alone sees the variable and stops before any install
    got = _run_sh("export UV_NO_CONFIG=1 PIP_CONFIG_FILE=/dev/null\n" + contree_sandboxes.NO_INDEX_CONFIG_CHECK
                  + "echo INSTALL\n", tmp_path, {var: "x"})
    assert got.returncode == 1 and "INSTALL" not in got.stdout and f"{var} is still set" in got.stdout


def test_contree_isolation_check_fails_closed_when_exports_did_not_take(tmp_path):
    got = _run_sh(contree_sandboxes.NO_INDEX_CONFIG_CHECK + "echo INSTALL\n", tmp_path, {"PIP_CONFIG_FILE": "/x"})
    assert got.returncode == 1 and "INSTALL" not in got.stdout and "did not take" in got.stdout


def test_contree_isolation_shell_stops_when_unset_fails(tmp_path):
    # a read-only variable cannot be unset: the shell must stop before the install line
    got = _run_sh("readonly UV_EXTRA_INDEX_URL=x\n" + contree_sandboxes.NO_INDEX_CONFIG_SHELL + "echo INSTALL\n",
                  tmp_path, {})
    assert got.returncode != 0 and "INSTALL" not in got.stdout


def test_contree_product_shell_stops_before_installs_on_a_failed_check(tmp_path):
    shell = contree_sandboxes.install_shell_source("a/b", "x", deps_only_fallback=True)
    head = shell[:shell.index("export DEBIAN_FRONTEND")]
    got = _run_sh("readonly PIP_TRUSTED_HOST=t\n" + head + "echo INSTALL\n", tmp_path, {})
    assert got.returncode != 0 and "INSTALL" not in got.stdout


def test_contree_only_declared_installs_run_after_the_isolation_lines():
    extra = daily_run.contree_only_extra_shell(["okpkg"], ["optpkg"])
    shell = contree_sandboxes.install_shell_source("a/b", "x", extra, deps_only_fallback=True)
    assert shell.index("PIP_CONFIG_FILE=/dev/null") < shell.index("pip install -q okpkg")


def test_product_route_passes_isolated_to_install_side(tmp_path, monkeypatch):
    src = Path(daily_run.__file__).read_text()
    import re
    assert len(re.findall(r"install_side\([^)]*\)?[^\n]*\n?[^\n]*isolated=product_route\(a\)\)", src)) == 2


def _own_index_product(tmp_path, monkeypatch, project_text, uv_toml=None, step="main install"):
    (tmp_path / "pyproject.toml").write_text(project_text)
    if uv_toml:
        (tmp_path / "uv.toml").write_text(uv_toml)

    def failing(venv, checkout, chosen, lg, py, *rest, **_kw):
        lg.write_text("error: No solution found when resolving dependencies: okpkg was not found in the package index\n")
        return False, "install failed (1)"
    monkeypatch.setattr(daily_run, "install_side", failing)
    a = SimpleNamespace(python="3.12", pr="https://github.com/a/b/pull/1", product_check=True, bench=None)
    return daily_run._install_with_helper(a, {}, step, tmp_path / "v", tmp_path, None, tmp_path / "log", 10, None,
                                          None, max_retries=1)


_PROJ = '[project]\nname = "p"\nversion = "0"\ndependencies = ["okpkg"]\n'


@pytest.mark.parametrize("step", ["main install", "PR install"])
@pytest.mark.parametrize("extra,uv_toml", [
    ('[tool.uv.sources]\nokpkg = { git = "https://example.invalid/okpkg" }\n', None),
    ('[[tool.uv.index]]\nname = "private"\nurl = "https://example.invalid/simple"\n', None),
    ('[tool.uv]\nextra-index-url = ["https://example.invalid/simple"]\n', None),
    ('[tool.uv.pip]\nfind-links = ["https://example.invalid/f"]\n', None),
    ("", 'index-url = "https://example.invalid/simple"\n'),
])
def test_own_index_install_failure_is_could_not_verify(tmp_path, monkeypatch, extra, uv_toml, step):
    ok, why = _own_index_product(tmp_path, monkeypatch, _PROJ + extra, uv_toml, step)
    assert ok is False and why.startswith("unsupported:") and "its own package index or uv sources" in why
    verdict, reason, _ = daily_run.tests_verdict(None, why, None, None)
    assert verdict == "could_not_verify" and reason == why


def test_plain_install_failure_is_not_blamed_on_an_index(tmp_path, monkeypatch):
    ok, why = _own_index_product(tmp_path, monkeypatch, _PROJ)
    assert ok is False and "own package index" not in why


def test_contree_failure_with_own_index_becomes_the_limitation_reason(tmp_path):
    (tmp_path / "pyproject.toml").write_text(_PROJ + '[[tool.uv.index]]\nname = "p"\nurl = "https://example.invalid/s"\n')
    a = SimpleNamespace(pr="https://github.com/a/b/pull/1", product_check=True, bench=None)
    got = daily_run.own_index_refusal(a, "Contree setup failed", tmp_path, None)
    assert got.startswith("unsupported:") and "[[tool.uv.index]]" in got
    assert daily_run.tests_verdict(None, got, None, None)[0] == "could_not_verify"
    study = SimpleNamespace(pr=None, product_check=False, bench="x")
    assert daily_run.own_index_refusal(study, "Contree setup failed", tmp_path) == "Contree setup failed"
    plain = tmp_path / "plain"
    plain.mkdir()
    assert daily_run.own_index_refusal(a, "Contree setup failed", plain) == "Contree setup failed"


def _helper_calls(monkeypatch, tmp_path, isolated):
    monkeypatch.setattr(daily_run, "base_env",
                        lambda home, install=False, **kw: {"PATH": "/bin", "UV_EXTRA_INDEX_URL": "x",
                                                           "PIP_INDEX_URL": "y", **kw})
    monkeypatch.setattr(daily_run, "side_sandbox", lambda *a, **k: {"rw": []})
    monkeypatch.setattr(daily_run, "PIP_OPTIONAL", {"mod": "wheelpkg"})
    calls = _capture(monkeypatch)
    venvs = {"main": tmp_path / "vm", "pr": tmp_path / "vp"}
    log = tmp_path / "l.log"
    kw = {} if isolated is None else {"isolated": isolated}
    daily_run.install_declared_test_deps(venvs, ["a"], log, 5, **kw)
    daily_run.install_optional_backends(venvs, ["b"], log, 5, **kw)
    daily_run.install_optional_modules(venvs, ["mod"], log, 5, **kw)
    return calls


def test_helpers_hardened_on_product_checks(tmp_path, monkeypatch):
    calls = _helper_calls(monkeypatch, tmp_path, True)
    assert len(calls) == 6
    for c, e in calls:
        assert c[-2:] == ["--no-config", "--no-sources"]
        assert e["UV_NO_CONFIG"] == "1" and e["PIP_CONFIG_FILE"] == daily_run.os.devnull
        assert "UV_EXTRA_INDEX_URL" not in e and "PIP_INDEX_URL" not in e


def test_helpers_unchanged_on_study_route(tmp_path, monkeypatch):
    default = _helper_calls(monkeypatch, tmp_path, None)
    study = _helper_calls(monkeypatch, tmp_path, False)
    assert default == study and len(study) == 6
    for c, e in study:
        assert "--no-config" not in c and "--no-sources" not in c
        assert e == {"PATH": "/bin", "UV_EXTRA_INDEX_URL": "x", "PIP_INDEX_URL": "y", "install": True} or \
            e == {"PATH": "/bin", "UV_EXTRA_INDEX_URL": "x", "PIP_INDEX_URL": "y"}


def test_install_call_sites_gate_on_product_route():
    import inspect
    src = inspect.getsource(daily_run)
    assert 'decl, prdir / "setup-declared.log",\n' in src
    assert src.count("a.build_timeout, product_route(a))") >= 3   # declared, optional backends, optional modules
    plan = src[src.index("def _plan_install"):][:800]
    assert "isolated_install(" in plan and "product_route(a)" in plan


def test_own_index_refusal_keeps_infrastructure_failure(tmp_path, monkeypatch):
    co = _checkout(tmp_path / "co")
    a = SimpleNamespace(pr=1, bench=None, product_check=True)
    why = "infrastructure failure: contree session lost"
    assert daily_run.own_index_refusal(a, why, co) == why
    assert daily_run.own_index_refusal(a, "install failed (1)", co).startswith("unsupported:")


def test_nightly_and_source_build_backends_gated_on_product_route():
    import inspect
    bm = inspect.getsource(daily_run.build_main_env)
    sb = inspect.getsource(daily_run.source_build)
    assert "isolated: bool = False" in bm and "reqs, log, timeout, isolated)" in bm
    assert "isolated: bool = False" in sb and "optional, log, timeout, isolated)" in sb
    tp = inspect.getsource(daily_run.test_pr)
    assert tp.count("isolated=product_route(a)") == 4
    assert inspect.signature(daily_run.build_main_env).parameters["isolated"].default is False
    assert inspect.signature(daily_run.source_build).parameters["isolated"].default is False
