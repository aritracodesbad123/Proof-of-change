"""Every folder the services write to comes from a setting, so the app code can stay read-only on a deploy."""
from pathlib import Path

import pytest

from poc import console_api, github_app

ROOT = Path(__file__).resolve().parent.parent
SETTINGS = ("POC_HOSTED_REPORTS_DIR", "POC_OPS_RUNS", "POC_OPS_DIR", "POC_REPORT_DIR", "POC_HEAVY_BUILD_DIR")


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    for k in SETTINGS + ("NEBIUS_API_KEY", "NEBIUS_PROJECT_ID", "TAVILY_API_KEY", "GITHUB_TOKEN"):
        monkeypatch.delenv(k, raising=False)


def test_defaults_are_unchanged():
    assert github_app.hosted_reports_dir({}) == ROOT / "reports" / "hosted"
    assert github_app.ops_runs_dir({}) == ROOT / "ops" / "runs"
    argv = github_app.check_argv("https://github.com/me/demo/pull/3", {})
    assert "--ops-dir" not in argv and "--report-dir" not in argv


def test_app_writes_hosted_reports_to_the_setting(tmp_path, monkeypatch):
    monkeypatch.setenv("POC_HOSTED_REPORTS_DIR", str(tmp_path / "hosted"))
    path = github_app.write_hosted_report({"id": "r1"})
    assert path == tmp_path / "hosted" / "r1.html" and path.is_file()


def test_console_reads_hosted_reports_from_the_same_setting(tmp_path, monkeypatch):
    monkeypatch.setenv("POC_HOSTED_REPORTS_DIR", str(tmp_path / "hosted"))
    assert console_api._hosted_dir() == tmp_path / "hosted"
    assert not hasattr(console_api, "HOSTED")  # no fixed path left in the console


def test_app_finds_records_and_points_the_check_at_the_data_folders(tmp_path):
    env = {"POC_OPS_RUNS": str(tmp_path / "runs"), "POC_OPS_DIR": str(tmp_path),
           "POC_REPORT_DIR": str(tmp_path / "reports" / "daily")}
    assert github_app.ops_runs_dir(env) == tmp_path / "runs"
    argv = github_app.check_argv("https://github.com/me/demo/pull/3", env)
    assert argv[argv.index("--ops-dir") + 1] == str(tmp_path)
    assert argv[argv.index("--report-dir") + 1] == str(tmp_path / "reports" / "daily")
    assert "--require-contree" in argv


def test_service_files_put_every_write_under_var_lib():
    for name in ("proof-of-change-console.service", "proof-of-change-app.service"):
        unit = (ROOT / "deploy" / "nebius" / name).read_text()
        for k in SETTINGS:
            line = next(ln for ln in unit.splitlines() if ln.startswith(f"Environment={k}="))
            assert line.split("=", 2)[2].startswith("/var/lib/proof-of-change"), (name, k)
    setup = (ROOT / "deploy" / "nebius" / "setup.sh").read_text()
    assert "ln -s" not in setup
    assert '"$DATA/reports/hosted"' in setup and '"$DATA/work/heavy-builds"' in setup


def test_healthcheck_probes_each_data_folder_as_the_service_user():
    hc = (ROOT / "deploy" / "nebius" / "healthcheck.sh").read_text()
    assert "runuser -u proof-of-change" in hc and "rm -f" in hc
    for d in ("runs", "reports/daily", "reports/hosted", "work/heavy-builds", "github-app"):
        assert f"/var/lib/proof-of-change/{d}" in hc


def test_console_job_folders_follow_the_run_folders(tmp_path, monkeypatch):
    class FakeThread:
        def __init__(self, target=None, daemon=None):
            pass

        def start(self):
            pass

    code_root, runs = tmp_path / "code", tmp_path / "data" / "runs"
    (code_root / "ops").mkdir(parents=True)
    (code_root / "ops" / "daily_run.py").write_text("# stub\n")
    monkeypatch.setattr(console_api.threading, "Thread", FakeThread)
    monkeypatch.setattr(console_api, "console_run_flags",
                        lambda *_a, **_k: console_api.ConsoleRunPlan([], None, False, None))
    monkeypatch.setattr(console_api, "REPO_ROOT", code_root)
    monkeypatch.setattr(console_api, "RUNS_ROOT", runs)
    job = console_api.start_check("https://github.com/me/demo/pull/3", model_provider="none")
    assert (runs / "_jobs" / job["id"]).is_dir()
    assert not (code_root / "ops" / "runs").exists()  # nothing written into the code folder
    assert 'REPO_ROOT / "ops" / "runs" / "_jobs"' not in (ROOT / "poc" / "console_api.py").read_text()
