import json

import pytest

from evals.run_evals import run as run_evals
from harness import run as hr
from harness.machine import detect_machine_type, gxx_version, require_gxx


def test_machine_type_ci_env():
    mt = detect_machine_type({"GITHUB_ACTIONS": "true", "RUNNER_NAME": "GitHub Actions 3", "RUNNER_OS": "Linux",
                              "RUNNER_ARCH": "X64", "ImageOS": "ubuntu24", "ImageVersion": "20261001.1"})
    assert mt["ci"] == "github-actions" and mt["image"] == "ubuntu24 20261001.1" and mt["arch"] and mt["os"]
    assert "gxx" in mt


def test_gxx_missing_stops_setup(monkeypatch):
    monkeypatch.setattr("harness.machine.shutil.which", lambda _name: None)
    assert gxx_version() is None
    with pytest.raises(SystemExit, match="g\\+\\+"):
        require_gxx()


def test_gxx_version_is_recorded_on_the_machine(monkeypatch):
    monkeypatch.setattr("harness.machine.shutil.which", lambda _name: "/usr/bin/g++")

    class _Done:
        stdout = "g++ (Ubuntu 13.3.0) 13.3.0\nCopyright line\n"
        stderr = ""

    monkeypatch.setattr("harness.machine.subprocess.run", lambda *_a, **_k: _Done())
    assert gxx_version() == "g++ (Ubuntu 13.3.0) 13.3.0"
    assert require_gxx() == "g++ (Ubuntu 13.3.0) 13.3.0"
    mt = detect_machine_type({})
    assert mt["gxx"] == "g++ (Ubuntu 13.3.0) 13.3.0"
    assert mt["ci"] is None


def test_build_command_forces_protocol(tmp_path):
    mt = detect_machine_type({})
    cmd = hr.build_command(tmp_path / "br_run.py", ["--upstream", "pandas"], tmp_path, mt)
    assert cmd[cmd.index("--runs") + 1] == "3" and "--root" in cmd and "--machine" in cmd
    with pytest.raises(SystemExit):
        hr.build_command(tmp_path / "br_run.py", ["--runs", "1"], tmp_path, mt)


def test_enrich_makes_legacy_record_valid(legacy_records):
    from guardrails.schema import validate_record
    rec = hr.enrich(legacy_records[0], detect_machine_type({}))
    assert validate_record(rec) == []


def test_dry_run(capsys):
    assert hr.main(["--dry-run", "--upstream", "pandas"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["env"]["OMP_NUM_THREADS"] == "1"


def test_report_from_eval_results(tmp_path, legacy_records):
    """The eval result JSON is a valid input to the single report generator (CI uses this path)."""
    from reports.generate import main
    obs = tmp_path / "o.jsonl"
    obs.write_text("\n".join(json.dumps(r) for r in legacy_records) + "\n")
    ev = tmp_path / "ev.json"
    ev.write_text(json.dumps(run_evals(obs, None, True)))
    assert main([str(ev), "--out", str(tmp_path / "rep"), "--formats", "md,html"]) == 0
    md = (tmp_path / "rep" / "SUMMARY.md").read_text()
    assert md.count("COULD NOT VERIFY / Re-run") == 2  # legacy records fail strict evals -> not trustworthy
