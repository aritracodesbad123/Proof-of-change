"""Product-path installs ignore uv/pip config files, the project's [tool.uv.sources] and index env settings."""
import subprocess
from pathlib import Path

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
    assert product.index("export UV_NO_CONFIG=1 PIP_CONFIG_FILE=/dev/null") < product.index("pip install -q okpkg")
    assert product.count("uv sync -q --no-config") == 2
    study = contree_sandboxes.install_shell_source("a/b", "x")
    assert "UV_NO_CONFIG" not in study and "--no-config" not in study


def test_contree_isolation_shell_unsets_index_vars(tmp_path):
    script = tmp_path / "s.sh"
    script.write_text(contree_sandboxes.NO_INDEX_CONFIG_SHELL + 'env | grep -E "^(UV|PIP)_" | sort\n')
    env = {"PATH": "/usr/bin:/bin", "UV_EXTRA_INDEX_URL": "x", "UV_INDEX": "y", "UV_DEFAULT_INDEX": "d",
           "UV_FIND_LINKS": "f", "UV_NO_INDEX": "1", "UV_INSECURE_HOST": "h", "PIP_INDEX_URL": "i",
           "PIP_EXTRA_INDEX_URL": "e", "PIP_FIND_LINKS": "f", "PIP_NO_INDEX": "1", "PIP_TRUSTED_HOST": "t",
           "UV_CACHE_DIR": "c"}
    out = subprocess.run(["sh", str(script)], env=env, capture_output=True, text=True, check=True).stdout.split()
    assert out == ["PIP_CONFIG_FILE=/dev/null", "UV_CACHE_DIR=c", "UV_NO_CONFIG=1"]


def test_contree_only_declared_installs_run_after_the_isolation_lines():
    extra = daily_run.contree_only_extra_shell(["okpkg"], ["optpkg"])
    shell = contree_sandboxes.install_shell_source("a/b", "x", extra, deps_only_fallback=True)
    assert shell.index("PIP_CONFIG_FILE=/dev/null") < shell.index("pip install -q okpkg")


def test_product_route_passes_isolated_to_install_side(tmp_path, monkeypatch):
    src = Path(daily_run.__file__).read_text()
    assert src.count("isolated=product_route(a))") == 2
