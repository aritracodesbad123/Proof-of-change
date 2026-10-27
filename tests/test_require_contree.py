"""Hosted product routes (GitHub App, hosted console, request worker) run pull-request code only in Contree."""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "ops"))

from poc import console_api, contree_sandboxes, github_app  # noqa: E402
import daily_run  # noqa: E402
import request_worker  # noqa: E402


def _backend(argv):
    i = argv.index("--sandbox-backend")
    return argv[i + 1]


def test_app_check_argv_requires_contree():
    argv = github_app.check_argv("https://github.com/me/demo/pull/3", {})
    assert _backend(argv) == "contree"
    assert "--require-contree" in argv
    assert "--unsafe-no-sandbox" not in argv


def test_request_worker_argv_requires_contree(tmp_path):
    argv = request_worker.default_check_argv("python", tmp_path, "https://github.com/me/demo/pull/3")
    assert _backend(argv) == "contree"
    assert "--require-contree" in argv
    assert "--unsafe-no-sandbox" not in argv


def test_refusal_when_contree_cannot_start_no_credentials():
    a = SimpleNamespace(sandbox_backend="local")
    stop = daily_run.contree_required_refusal(a, env={"PATH": "/usr/bin"})
    assert stop and "Contree unavailable" in stop and "could not verify" in stop
    assert stop.startswith("STOPPED:")
    assert contree_sandboxes.backend() != "contree"


def test_refusal_ignores_missing_require_env(monkeypatch):
    """No local fallback even though POC_REQUIRE_CONTREE is not set in the environment."""
    monkeypatch.delenv(contree_sandboxes.REQUIRE_ENV, raising=False)
    a = SimpleNamespace(sandbox_backend="contree")
    stop = daily_run.contree_required_refusal(a, env={"NEBIUS_API_KEY": "", "NEBIUS_PROJECT_ID": ""})
    assert stop and "Contree unavailable" in stop


def test_refusal_when_sdk_missing(monkeypatch):
    import builtins
    real = builtins.__import__

    def fake(name, *args, **kwargs):
        if name == "contree_sdk":
            raise ImportError("no sdk")
        return real(name, *args, **kwargs)
    monkeypatch.setattr(builtins, "__import__", fake)
    a = SimpleNamespace(sandbox_backend="contree")
    stop = daily_run.contree_required_refusal(a, env={"NEBIUS_API_KEY": "k-test", "NEBIUS_PROJECT_ID": "p-test"})
    assert stop and "Contree unavailable" in stop
    assert "k-test" not in stop and "p-test" not in stop


def test_hosted_console_refuses_without_contree(monkeypatch):
    monkeypatch.setenv("POC_HOSTED", "1")
    monkeypatch.delenv("CODESPACES", raising=False)
    monkeypatch.delenv("POC_UNSAFE_NO_SANDBOX", raising=False)
    monkeypatch.setattr(console_api, "contree_usable", lambda *_a, **_k: False)
    import guardrails.sandbox as sb
    monkeypatch.setattr(sb, "check", lambda: (True, "bwrap ok"))
    plan = console_api.console_run_flags()
    assert plan.refused is True
    assert plan.flags == []
    assert "Contree unavailable" in plan.note


def test_hosted_console_ignores_unsafe_opt_in(monkeypatch):
    monkeypatch.setenv("POC_HOSTED", "1")
    monkeypatch.setenv("POC_UNSAFE_NO_SANDBOX", "1")
    monkeypatch.delenv("CODESPACES", raising=False)
    monkeypatch.setattr(console_api, "contree_usable", lambda *_a, **_k: False)
    plan = console_api.console_run_flags()
    assert plan.refused is True and "--unsafe-no-sandbox" not in plan.flags


def test_hosted_console_requires_contree_when_usable(monkeypatch):
    monkeypatch.setenv("POC_HOSTED", "1")
    monkeypatch.delenv("CODESPACES", raising=False)
    monkeypatch.setattr(console_api, "contree_usable", lambda *_a, **_k: True)
    plan = console_api.console_run_flags()
    assert plan.flags == ["--sandbox-backend", "contree", "--require-contree"]
    assert plan.refused is False


def test_local_console_default_unchanged(monkeypatch):
    for k in ("POC_HOSTED", "RENDER", "RENDER_SERVICE_ID", "SPACE_ID", "POC_UNSAFE_NO_SANDBOX"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setattr(console_api, "contree_usable", lambda *_a, **_k: True)
    assert console_api.console_run_flags().flags == ["--sandbox-backend", "contree"]


def test_daily_run_knows_the_flag():
    text = (ROOT / "ops" / "daily_run.py").read_text()
    assert '"--require-contree"' in text
