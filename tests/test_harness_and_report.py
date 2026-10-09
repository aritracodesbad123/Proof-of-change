import json

import pytest

from evals.run_evals import run as run_evals
from harness import run as hr
from harness.machine import detect_machine_type
from reports.generate import render


def test_machine_type_ci_env():
    mt = detect_machine_type({"GITHUB_ACTIONS": "true", "RUNNER_NAME": "GitHub Actions 3", "RUNNER_OS": "Linux",
                              "RUNNER_ARCH": "X64", "ImageOS": "ubuntu24", "ImageVersion": "20261001.1"})
    assert mt["ci"] == "github-actions" and mt["image"] == "ubuntu24 20261001.1" and mt["arch"] and mt["os"]


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


def test_report_sections(tmp_path, legacy_records):
    obs = tmp_path / "o.jsonl"
    obs.write_text("\n".join(json.dumps(r) for r in legacy_records) + "\n")
    md = render(run_evals(obs, None, True))
    for s in ("Recommendation: **REJECT**", "What went right", "What went wrong", "How to fix", "Golden eval coverage",
              "machine_type"):
        assert s in md
