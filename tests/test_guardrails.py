import sys

from guardrails.isolation import assert_single_thread, check_env_isolation, run_with_timeout, single_thread_env
from guardrails.no_external import scan


def test_single_thread_env():
    env = single_thread_env({"OMP_NUM_THREADS": "8", "PYTHONPATH": "/x"})
    assert assert_single_thread(env) == []
    assert "PYTHONPATH" not in env
    assert assert_single_thread({"OMP_NUM_THREADS": "4"})


def test_env_isolation(tmp_path):
    assert check_env_isolation(tmp_path, tmp_path / "venv-old", tmp_path / "venv-new") == []
    assert check_env_isolation(tmp_path, tmp_path / "v", tmp_path / "v")
    assert check_env_isolation(tmp_path, "/tmp/elsewhere", tmp_path / "venv-new")


def test_timeout_kills_process():
    r = run_with_timeout([sys.executable, "-c", "import time; time.sleep(30)"], timeout_s=1)
    assert r["rc"] == "timeout" and r["seconds"] < 10
    assert run_with_timeout([sys.executable, "-c", "print('hi')"], 10)["rc"] == 0


def test_repo_has_no_external_side_effects():
    from pathlib import Path
    assert scan(Path(__file__).parent.parent) == []


def test_scanner_catches_writes(tmp_path):
    (tmp_path / "bad.py").write_text("import requests\nrequests.post('https://x')\n")  # br-allow-external: scanner test input
    (tmp_path / "bad.sh").write_text("gh issue create -t x\ngit push origin main\n")  # br-allow-external: scanner test input
    (tmp_path / "ok.py").write_text("requests.post('x')  # br-allow-external: reviewed test double\n")
    hits = scan(tmp_path)
    assert len(hits) == 3
