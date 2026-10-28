"""Display and operations fixes. None of these change a verdict on an existing fixture."""
import copy
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from guardrails.schema import validate_record
from ops import daily_run
from poc import coverage_gate
from poc.pr_text import github_read_token
from reports import pr_report

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"


def _probe_item(status: str) -> dict:
    return {"id": "p1", "source": "diff", "target": "pkg.fn", "claims": [], "runs_per_side": 1, "status": status,
            "observations": [{"name": "pkg.fn.out", "state": "same", "label": "no_difference"}]}


def test_crashed_and_rejected_probe_status_validate():
    rec = json.loads((FIXTURES / "day1" / "pr_run_numpy_32910.json").read_text())
    rec["probes"] = {"status": "rejected", "items": [_probe_item("crashed"), _probe_item("rejected")]}
    assert validate_record(rec) == []


def test_fixture_verdicts_match_the_previous_normalize():
    """The previous report normalize was the coverage gate alone. Verdicts on saved fixtures stay that verdict."""
    found = 0
    for path in sorted(FIXTURES.rglob("*.json")):
        data = json.loads(path.read_text())
        if not isinstance(data, dict) or "verdict" not in data:
            continue
        if "final_verdict" in path.parts:
            continue   # a record gated at run time: views show its stored verdict (tests/test_final_verdict.py)
        found += 1
        got = pr_report.normalize(copy.deepcopy(data))["verdict"]
        previous = coverage_gate.apply(copy.deepcopy(data))["verdict"]
        assert got == previous, path
    assert found >= 2


def test_already_downgraded_ai_probe_stays_could_not_verify():
    rec = {"verdict": "could_not_verify", "verdict_before_ai_probe_gate": "verified",
           "verdict_before_coverage_gate": "verified", "baseline": "full", "probes": {"items": []},
           "reason": "not verified: no AI-written probe ran any changed line, so the change was not exercised"}
    assert coverage_gate.apply(copy.deepcopy(rec))["verdict"] == "verified"
    assert pr_report.normalize(rec)["verdict"] == "could_not_verify"


def test_uncovered_diff_differences_are_listed_and_do_not_change_the_verdict(tmp_path):
    rec = {"verdict": "verified", "reason": "same", "repo": "o/r", "pr": 1, "title": "t", "baseline": "full",
           "probes": {"status": "ran", "items": [{
               "id": "diff-1", "source": "diff", "target": "pkg.fn", "claims": [], "runs_per_side": 1,
               "observations": [{"name": "pkg.fn.out", "state": "differs", "label": "unmentioned",
                                 "main": 1, "pr": 2, "diffs": [{"field": "value", "main": 1, "pr": 2}]}]
           }]}}
    rows = pr_report.uncovered_diff_differences(rec)
    assert [r["name"] for r in rows] == ["pkg.fn.out"]
    report, _meta = pr_report.build(rec, tmp_path, tmp_path)
    blob = json.dumps(report.blocks)
    assert "Differences no claim covers" in blob and "pkg.fn.out" in blob
    assert rec["verdict"] == "verified"


def test_github_token_order_and_absence_from_untrusted_env(monkeypatch, tmp_path):
    monkeypatch.setenv("GITHUB_TOKEN", "primary-token")
    monkeypatch.setenv("GITHUB_POC_TOKEN", "poc-token")
    monkeypatch.setenv("GH_TOKEN", "gh-token")
    assert github_read_token() == "primary-token"
    assert daily_run.GitHub(None).token == "primary-token"
    monkeypatch.delenv("GITHUB_TOKEN")
    assert github_read_token() == "poc-token"
    env = daily_run.base_env(tmp_path / "home", install=True)
    assert "GITHUB_TOKEN" not in env and "GITHUB_POC_TOKEN" not in env and "GH_TOKEN" not in env
    assert "poc-token" not in env.values()


def _http_error(url, code, headers):
    return urllib.error.HTTPError(url, code, "limited", headers, None)


def test_rate_limit_waits_until_reset_and_retries(monkeypatch, capsys):
    calls = {"n": 0}

    def urlopen(req, timeout=60):
        calls["n"] += 1
        if calls["n"] == 1:
            raise _http_error(req.full_url, 403, {"X-RateLimit-Remaining": "0",
                                                   "X-RateLimit-Reset": str(int(time.time()) + 1)})
        class Resp:
            headers = {"X-RateLimit-Remaining": "10"}

            def read(self):
                return b"ok"

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False
        return Resp()

    slept = []
    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(daily_run.time, "sleep", lambda s: slept.append(s))
    body = daily_run.GitHub(None).get("https://api.github.com/rate_limit")
    assert body == b"ok" and calls["n"] == 2
    assert slept and slept[0] <= 5
    assert "waiting" in capsys.readouterr().err


def test_rate_limit_does_not_wait_when_remaining_is_not_zero(monkeypatch):
    def urlopen(req, timeout=60):
        raise _http_error(req.full_url, 403, {"X-RateLimit-Remaining": "5"})

    slept = []
    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(daily_run.time, "sleep", lambda s: slept.append(s))
    with pytest.raises(RuntimeError):
        daily_run.GitHub(None).get("https://api.github.com/rate_limit")
    assert slept == []


def test_rate_limit_does_not_wait_past_the_cap(monkeypatch, capsys):
    def urlopen(req, timeout=60):
        raise _http_error(req.full_url, 429, {"X-RateLimit-Remaining": "0",
                                               "X-RateLimit-Reset": str(int(time.time()) + 10_000)})

    slept = []
    monkeypatch.setenv("POC_GITHUB_RATE_LIMIT_MAX_WAIT_S", "30")
    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(daily_run.time, "sleep", lambda s: slept.append(s))
    with pytest.raises(RuntimeError):
        daily_run.GitHub(None).get("https://api.github.com/rate_limit")
    assert slept == []
    assert "not waiting" in capsys.readouterr().err


def test_heavy_build_limit_and_compiler_jobs():
    assert daily_run.heavy_build_limit(configured=4, ram=16) == 2
    assert daily_run.heavy_build_limit(configured=4, ram=4) == 1
    assert daily_run.heavy_build_limit(configured=4, ram=None) == 1
    assert daily_run.heavy_build_limit(configured=1, ram=64) == 1
    assert daily_run.compiler_jobs(ram=None, configured=8) == 1
    assert daily_run.compiler_jobs(ram=16, configured=8) == 8
    assert daily_run.compiler_jobs(ram=6, configured=8) == 3


def test_timeout_is_not_an_oom_kill():
    assert daily_run.is_oom_kill(-9, "")
    assert daily_run.is_oom_kill(137, "")
    assert daily_run.is_oom_kill(1, "cc: Killed signal terminated program")
    assert not daily_run.is_oom_kill("timeout", "Killed signal terminated program")
    assert not daily_run.is_oom_kill(1, "error: compiler failed")


def test_oom_retries_once_then_records_infrastructure_failure(monkeypatch, tmp_path):
    monkeypatch.setenv("POC_HEAVY_BUILD_DIR", str(tmp_path / "slots"))
    monkeypatch.setenv("POC_BUILD_JOBS", "1")
    n = {"i": 0}

    def fake_run(cmd, log, **kw):
        n["i"] += 1
        return -9, 0.2

    monkeypatch.setattr(daily_run, "run", fake_run)
    rc, _secs = daily_run.run_heavy(["uv", "pip", "install", "src"], tmp_path / "log", env={"PATH": "/bin"})
    assert rc == "oom" and n["i"] == 2

    def once(cmd, log, **kw):
        n["i"] += 1
        return (-9, 0.2) if n["i"] == 1 else (0, 0.1)

    n["i"] = 0
    monkeypatch.setattr(daily_run, "run", once)
    rc, _secs = daily_run.run_heavy(["uv", "pip", "install", "src"], tmp_path / "log2", env={"PATH": "/bin"})
    assert rc == 0 and n["i"] == 2

    def always_killed(cmd, log, **kw):
        if "--no-cache" in " ".join(map(str, cmd)):
            return -9, 0.2
        return 0, 0.1

    monkeypatch.setattr(daily_run, "run", always_killed)
    cfg = {"dist": "demo", "pkg": "demo", "deps": [], "test_deps": []}
    built = daily_run.source_build("o/r", {"pr": 2}, cfg, tmp_path / "venv2", tmp_path, tmp_path / "build2.log",
                                   "3.12", 30)
    assert built["ok"] is False
    assert built["infrastructure_failure"] == {"kind": "oom", "action": "retry"}
    assert built["why"].startswith("infrastructure failure:")
    assert "source build of PR head failed" not in built["why"]


def test_second_process_blocks_on_the_heavy_build_slot(tmp_path):
    lockdir = tmp_path / "locks"
    ready = tmp_path / "ready"
    script = tmp_path / "hold.py"
    script.write_text(
        "import time\n"
        "from pathlib import Path\n"
        "from ops.daily_run import HeavyBuildSlots\n"
        f"slot = HeavyBuildSlots(Path({str(lockdir)!r}), 1)\n"
        "slot.acquire()\n"
        f"Path({str(ready)!r}).write_text('ok')\n"
        "time.sleep(30)\n")
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    log = tmp_path / "hold.err"
    with log.open("w") as fh:
        proc = subprocess.Popen([sys.executable, str(script)], cwd=ROOT, env=env, stdout=fh, stderr=fh)
    try:
        for _ in range(150):
            if ready.exists() or proc.poll() is not None:
                break
            time.sleep(0.2)
        assert ready.exists(), log.read_text()[-2000:]
        holder = daily_run.HeavyBuildSlots(lockdir, 1)
        with pytest.raises(TimeoutError):
            holder.acquire(wait_s=0.3)
    finally:
        proc.kill()
        proc.wait(timeout=10)
    daily_run.HeavyBuildSlots(lockdir, 1).acquire(wait_s=2)


def test_optional_backend_reqs_skip_pytest_and_the_project():
    lines = ["pytest>=7; extra == 'test'", 'scipy>=1.8; extra == "test"', "numpy; extra == 'dev'",
             "hypothesis; extra == 'tests'", "myproj[complete]; extra == 'test'",
             "Requires-Dist: h5py; extra == \"testing\""]
    assert daily_run.reqs_for_test_extras(lines, "myproj") == ["scipy>=1.8", "hypothesis", "h5py"]


def test_optional_backend_reqs_from_pyproject(tmp_path):
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "demo"\n[project.optional-dependencies]\n'
        'test = ["pytest", "zarr"]\ndev = ["ruff"]\n')
    assert daily_run.optional_backend_reqs(tmp_path, "demo") == ["zarr"]
    assert daily_run.optional_backend_reqs(tmp_path / "missing", "demo") == []


def test_optional_backends_skip_a_failure_and_keep_going(monkeypatch, tmp_path):
    def fake_run(cmd, log, **kw):
        if "zarr" in map(str, cmd):
            return 1, 0.1
        return 0, 0.1

    monkeypatch.setattr(daily_run, "run", fake_run)
    info = daily_run.install_optional_backends(
        {"main": tmp_path / "venv-main", "pr": tmp_path / "venv-pr"}, ["zarr", "h5netcdf"], tmp_path / "log", 30)
    assert info["installed"] == ["h5netcdf"]
    assert {s["side"] for s in info["skipped"]} == {"main", "pr"}
    assert all(s["req"] == "zarr" for s in info["skipped"])


def test_failed_test_extra_retries_without_it(monkeypatch, tmp_path):
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "demo"\n[project.optional-dependencies]\ntest = ["zarr"]\n')
    calls = []

    def fake_run(cmd, log, **kw):
        text = " ".join(map(str, cmd))
        calls.append(text)
        if "[test]" in text:
            return 1, 0.1
        return 0, 0.1

    monkeypatch.setattr(daily_run, "run", fake_run)
    monkeypatch.setenv("POC_HEAVY_BUILD_DIR", str(tmp_path / "slots"))
    ok, why = daily_run.install_side(tmp_path / "venv-pr", tmp_path, None, tmp_path / "log", "3.12", 60, None)
    assert ok, why
    assert any("[test]" in c for c in calls)
    assert any("pip" in c and "install" in c and "[test]" not in c for c in calls)
    assert not any(c.rstrip().endswith("zarr") for c in calls)


def test_test_extra_bundle_failure_does_not_fail_the_env(monkeypatch, tmp_path):
    calls = []

    def fake_run(cmd, log, **kw):
        text = " ".join(map(str, cmd))
        calls.append(text)
        if "[test]" in text:
            return 1, 0.1
        if "zarr>=" in text:
            return 1, 0.1
        return 0, 0.1

    monkeypatch.setattr(daily_run, "run", fake_run)
    monkeypatch.setattr(daily_run, "dist_extras", lambda *a, **k: ["test"])
    monkeypatch.setattr(daily_run, "metadata_requires",
                        lambda *a, **k: ['zarr>=2; extra == "test"', "pytest; extra == 'test'"])
    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: (_ for _ in ()).throw(OSError("no network")))
    cfg = {"dist": "demo", "pkg": "demo", "deps": [], "test_deps": [], "optional_test_deps": ["scipy"]}
    out = daily_run.build_main_env(cfg, tmp_path / "venv", tmp_path / "setup.log", "3.12", 30, tmp_path / "wheels")
    assert out["ok"] is False
    assert "nightly wheel" in out["why"]
    assert "test extras" not in out["why"]
    assert any("zarr>=" in c for c in calls)
    assert any(c.rstrip().endswith("scipy") or " scipy" in c for c in calls)


def test_infrastructure_failure_is_a_rerun_in_the_report(monkeypatch):
    monkeypatch.setattr(pr_report.rv, "replay_failure", lambda *a, **k: None)
    decision = pr_report.decide(
        {"verdict": "could_not_verify", "reason": "infrastructure failure: compiler ran out of memory",
         "infrastructure_failure": {"kind": "oom", "action": "retry"}}, [])
    assert decision["action"] == "Re-run"
    assert "infrastructure" in decision["conf_why"]
    assert decision["verdict"] == "COULD NOT VERIFY"


def test_max_heavy_builds_flag_is_advertised():
    proc = subprocess.run([sys.executable, "-m", "ops.daily_run", "--help"], cwd=ROOT, capture_output=True, text=True)
    assert proc.returncode == 0
    assert "--max-heavy-builds" in proc.stdout
