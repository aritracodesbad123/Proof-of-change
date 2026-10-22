"""Behavioural probes get the project's own test settings, read generically from its pytest config and conftest."""

from types import SimpleNamespace

from ops import daily_run
from poc import test_settings


def test_pytest_ini_env_django_settings_and_pythonpath(tmp_path):
    (tmp_path / "common").mkdir()
    (tmp_path / "pytest.ini").write_text(
        "[pytest]\npythonpath = . common missing\nenv =\n    DEBUG=1\n    TEST=1\n"
        "DJANGO_SETTINGS_MODULE = app.settings\n")
    got = test_settings.project_test_env(tmp_path)
    assert got["env"] == {"DEBUG": "1", "TEST": "1", "DJANGO_SETTINGS_MODULE": "app.settings"}
    assert got["pythonpath"] == [".", "common"]
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
    (tmp_path / "pytest.ini").write_text(
        "[pytest]\nenv =\n    PATH=/evil\n    LD_PRELOAD=x.so\n    LD_AUDIT=a\n    PYTHONSAFEPATH=1\n"
        "    PYTHONPATH=/x\n    python_foo=1\n    COVERAGE_PROCESS_START=c\n    PYTEST_ADDOPTS=-x\n    OK=1\n")
    assert test_settings.project_test_env(tmp_path)["env"] == {"OK": "1"}


def test_no_config_adds_nothing(tmp_path):
    assert test_settings.apply({"A": "1"}, tmp_path) == {"A": "1"}
    assert test_settings.apply({"A": "1"}, None) == {"A": "1"}


def _sides(tmp_path, main_ini, pr_ini=None):
    for side, ini in (("main", main_ini), ("pr", pr_ini if pr_ini is not None else main_ini)):
        (tmp_path / f"venv-{side}" / "bin").mkdir(parents=True)
        (tmp_path / f"side-{side}" / "lib").mkdir(parents=True)
        (tmp_path / f"side-{side}" / "pytest.ini").write_text(ini)
    return {s: tmp_path / f"venv-{s}" for s in ("main", "pr")}


PRODUCT = SimpleNamespace(pr="https://github.com/o/r/pull/1", product_check=True, bench=None, runs=1)
STUDY = SimpleNamespace(pr=None, product_check=False, bench=None, runs=1)
MAIN_INI = "[pytest]\npythonpath = lib\nenv =\n    SIDE=main\nDJANGO_SETTINGS_MODULE = app.settings\n"


def test_both_sides_get_main_settings_and_a_pr_config_change_is_flagged(tmp_path):
    venvs = _sides(tmp_path, MAIN_INI, "[pytest]\nenv =\n    SIDE=pr\n")
    settings = daily_run.probe_settings(PRODUCT, venvs)
    envs = {s: daily_run.probe_env(v, settings) for s, v in venvs.items()}
    assert envs["main"]["SIDE"] == envs["pr"]["SIDE"] == "main"
    assert envs["main"]["DJANGO_SETTINGS_MODULE"] == envs["pr"]["DJANGO_SETTINGS_MODULE"] == "app.settings"
    # same relative pythonpath, each joined to its own checkout
    assert envs["main"]["PYTHONPATH"] == str((tmp_path / "side-main" / "lib").resolve())
    assert envs["pr"]["PYTHONPATH"] == str((tmp_path / "side-pr" / "lib").resolve())
    assert settings["pr_changed"] == ["pytest.ini"]
    summ = test_settings.summary(settings)
    assert summ["source"] == ["pytest.ini"] and summ["variables"] == ["DJANGO_SETTINGS_MODULE", "SIDE"]
    assert "main" not in str(summ["variables"]) and "app.settings" not in str(summ)   # names, never values


def test_pr_change_to_django_settings_module_is_flagged(tmp_path):
    venvs = _sides(tmp_path, MAIN_INI)
    for side, text in (("main", "A = 1\n"), ("pr", "A = 2\n")):
        (tmp_path / f"side-{side}" / "app").mkdir()
        (tmp_path / f"side-{side}" / "app" / "settings.py").write_text(text)
    assert daily_run.probe_settings(PRODUCT, venvs)["pr_changed"] == ["app/settings.py"]


def test_study_mode_probe_env_is_unchanged(tmp_path):
    venvs = _sides(tmp_path, MAIN_INI)
    assert daily_run.probe_settings(STUDY, venvs) is None
    for v in venvs.values():
        assert daily_run.probe_env(v, None) == daily_run.base_env(daily_run.side_home(v))


def test_contree_probe_gets_env_and_pythonpath(tmp_path):
    venvs = _sides(tmp_path, "[pytest]\npythonpath = . lib\nenv =\n    TEST=1\n    MSG=a b\n")
    shell = test_settings.shell_exports(daily_run.probe_settings(PRODUCT, venvs))
    assert "export TEST=1\n" in shell and "export MSG='a b'\n" in shell
    assert "export PYTHONPATH=/work/src:/work/src/lib" in shell
    assert test_settings.shell_exports(None) == ""


def test_contree_probe_command_carries_the_exports(tmp_path, monkeypatch):
    from poc import contree_sandboxes
    seen = {}

    class Sess:
        def run_op(self, side, shell, **k):
            seen[side] = shell
            return {"exit_code": 0, "stdout": "", "stderr": ""}
    monkeypatch.setattr(contree_sandboxes, "session", lambda: Sess())
    venvs = _sides(tmp_path, "[pytest]\npythonpath = lib\nenv =\n    TEST=1\n")
    daily_run._CONTREE_CHECKOUTS["settings"] = daily_run.probe_settings(PRODUCT, venvs)
    try:
        p = tmp_path / "probe.py"
        p.write_text("")
        for side in ("main", "pr"):
            daily_run._contree_probe_once(side, p, 10)
    finally:
        daily_run._CONTREE_CHECKOUTS.clear()
    assert seen["main"] == seen["pr"] and "export PYTHONPATH=/work/src/lib" in seen["main"]


def _run_probes(tmp_path, monkeypatch, a, venvs):
    from poc import freeze, probes
    seen = {}

    def fake_run_probe(path, pythons, prdir, cwds, envs, **k):
        seen.update(envs)
        return {"id": "p", "observations": []}
    monkeypatch.setattr(probes, "run_probe", fake_run_probe)
    monkeypatch.setattr(freeze, "verify", lambda *x, **k: None)
    monkeypatch.setattr(daily_run, "_contree_ready", lambda: False)
    probe = tmp_path / "p.py"
    probe.write_text("")
    plan = [{"path": str(probe), "source": "model", "freeze": {"generator": "g"}}]
    out = daily_run.run_probes("o/r", 1, {s: v / "bin/python" for s, v in venvs.items()}, tmp_path, tmp_path, a,
                               plan, "t")
    return out, seen


def test_run_probes_product_check_records_source_and_names(tmp_path, monkeypatch):
    venvs = _sides(tmp_path, MAIN_INI, "[pytest]\nenv =\n    SIDE=pr\n")
    out, seen = _run_probes(tmp_path, monkeypatch, PRODUCT, venvs)
    assert seen["main"]["SIDE"] == seen["pr"]["SIDE"] == "main"
    assert out["test_settings"]["source"] == ["pytest.ini"]
    assert out["test_settings"]["variables"] == ["DJANGO_SETTINGS_MODULE", "SIDE"]
    assert out["test_settings"]["pr_changed"] == ["pytest.ini"]


def test_run_probes_study_output_is_unchanged(tmp_path, monkeypatch):
    venvs = _sides(tmp_path, MAIN_INI)
    out, seen = _run_probes(tmp_path, monkeypatch, STUDY, venvs)
    assert "test_settings" not in out
    assert set(out) == {"status", "items", "summary"}
    for s, v in venvs.items():
        assert seen[s] == daily_run.base_env(daily_run.side_home(v))
