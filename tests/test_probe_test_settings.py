"""Behavioural probes get the project's own test settings, read generically from its pytest config and conftest."""
from pathlib import Path

from ops import daily_run
from poc import test_settings


def test_pytest_ini_env_django_settings_and_pythonpath(tmp_path):
    (tmp_path / "common").mkdir()
    (tmp_path / "pytest.ini").write_text(
        "[pytest]\npythonpath = . common missing\nenv =\n    DEBUG=1\n    TEST=1\n"
        "DJANGO_SETTINGS_MODULE = app.settings\n")
    got = test_settings.project_test_env(tmp_path)
    assert got["env"] == {"DEBUG": "1", "TEST": "1", "DJANGO_SETTINGS_MODULE": "app.settings"}
    assert got["pythonpath"] == [str(tmp_path.resolve()), str((tmp_path / "common").resolve())]
    assert got["source"] == ["pytest.ini"]


def test_pyproject_ini_options_with_ds_in_addopts_and_env_prefixes(tmp_path):
    (tmp_path / "pyproject.toml").write_text(
        '[tool.pytest.ini_options]\naddopts = "-q --ds=site.test_settings"\n'
        'env = ["D:LEVEL=info", "R:RAW=$HOME", "URL=http://x/${LEVEL}"]\n')
    got = test_settings.project_test_env(tmp_path, base={"LEVEL": "warn"})
    assert got["env"]["DJANGO_SETTINGS_MODULE"] == "site.test_settings"
    assert "LEVEL" not in got["env"]            # D: keeps a value that is already set
    assert got["env"]["RAW"] == "$HOME"          # R: is not expanded
    assert got["env"]["URL"] == "http://x/warn"


def test_setup_cfg_tool_pytest_and_first_config_wins(tmp_path):
    (tmp_path / "setup.cfg").write_text("[tool:pytest]\nenv =\n    MODE=test\n")
    assert test_settings.project_test_env(tmp_path)["env"] == {"MODE": "test"}
    (tmp_path / "pytest.ini").write_text("[pytest]\nenv =\n    MODE=ini\n")
    assert test_settings.project_test_env(tmp_path)["env"] == {"MODE": "ini"}


def test_conftest_literal_env_is_read_without_running_it(tmp_path):
    (tmp_path / "conftest.py").write_text(
        "import os\nraise SystemExit('must not run')\n"
        "os.environ['DJANGO_SETTINGS_MODULE'] = 'proj.settings.test'\n"
        "os.environ.setdefault('FEATURE', 'off')\nos.environ['DYN'] = compute()\n")
    got = test_settings.project_test_env(tmp_path)
    assert got["env"] == {"DJANGO_SETTINGS_MODULE": "proj.settings.test", "FEATURE": "off"}
    assert got["source"] == ["conftest.py"]


def test_config_cannot_steer_runner_variables(tmp_path):
    (tmp_path / "pytest.ini").write_text("[pytest]\nenv =\n    PATH=/evil\n    LD_PRELOAD=x.so\n    OK=1\n")
    assert test_settings.project_test_env(tmp_path)["env"] == {"OK": "1"}


def test_no_config_adds_nothing(tmp_path):
    assert test_settings.apply({"A": "1"}, tmp_path) == {"A": "1"}
    assert test_settings.apply({"A": "1"}, None) == {"A": "1"}


def test_probe_env_uses_the_side_checkout_next_to_the_venv(tmp_path):
    venv = tmp_path / "venv-main"
    (venv / "bin").mkdir(parents=True)
    side = tmp_path / "side-main"
    side.mkdir()
    (side / "pytest.ini").write_text("[pytest]\nenv =\n    TEST=1\nDJANGO_SETTINGS_MODULE = app.settings\n")
    env = daily_run.probe_env(venv)
    assert env["TEST"] == "1" and env["DJANGO_SETTINGS_MODULE"] == "app.settings"
    assert env["HOME"] == str(daily_run.side_home(venv))


def test_contree_probe_gets_the_same_settings_as_exports(tmp_path):
    (tmp_path / "pytest.ini").write_text("[pytest]\nenv =\n    TEST=1\n    MSG=a b\n")
    assert test_settings.shell_exports(tmp_path) == "export TEST=1\nexport MSG='a b'\n"
    assert test_settings.shell_exports(None) == ""


def test_run_probes_passes_the_project_env_to_each_side(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from poc import probes, freeze
    for side in ("main", "pr"):
        (tmp_path / f"venv-{side}" / "bin").mkdir(parents=True)
        (tmp_path / f"side-{side}").mkdir()
        (tmp_path / f"side-{side}" / "pytest.ini").write_text(f"[pytest]\nenv =\n    SIDE={side}\n")
    seen = {}

    def fake_run_probe(path, pythons, prdir, cwds, envs, **k):
        seen.update({s: e.get("SIDE") for s, e in envs.items()})
        return {"id": "p", "observations": []}
    monkeypatch.setattr(probes, "run_probe", fake_run_probe)
    monkeypatch.setattr(freeze, "verify", lambda *a, **k: None)
    monkeypatch.setattr(daily_run, "_contree_ready", lambda: False)
    probe = tmp_path / "p.py"
    probe.write_text("")
    plan = [{"path": str(probe), "source": "model", "freeze": {"generator": "g"}}]
    daily_run.run_probes("o/r", 1, {s: tmp_path / f"venv-{s}" / "bin/python" for s in ("main", "pr")},
                         tmp_path, tmp_path, SimpleNamespace(runs=1), plan, "t")
    assert seen == {"main": "main", "pr": "pr"}
