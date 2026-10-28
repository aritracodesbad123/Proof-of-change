"""Hosted console: Contree keys come only from private server settings, every check is charged to the caps,
and no value is ever shown, logged or echoed."""
from __future__ import annotations

import io
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "ops"))

import daily_run  # noqa: E402

from poc import console_api, session_key  # noqa: E402

SERVER_KEY = "server-nebius-key-0123456789"
SERVER_PROJECT = "server-project-id-0123456789"
TYPED_KEY = "typed-nebius-key-9876543210"
TYPED_PROJECT = "typed-project-id-9876543210"


def _hosted(monkeypatch, key=SERVER_KEY, project=SERVER_PROJECT):
    monkeypatch.setenv("POC_HOSTED", "1")
    monkeypatch.delenv("CODESPACES", raising=False)
    for name, value in (("NEBIUS_API_KEY", key), ("NEBIUS_PROJECT_ID", project)):
        if value is None:
            monkeypatch.delenv(name, raising=False)
        else:
            monkeypatch.setenv(name, value)


def test_hosted_contree_reads_only_server_settings(monkeypatch):
    _hosted(monkeypatch)
    session_key.set_key("tok-a", TYPED_KEY)
    session_key.set_contree_project("tok-a", TYPED_PROJECT)
    assert console_api.contree_credentials("tok-a") == (SERVER_KEY, SERVER_PROJECT)


def test_hosted_contree_ignores_typed_values_when_server_unset(monkeypatch):
    _hosted(monkeypatch, key=None, project=None)
    session_key.set_key("tok-b", TYPED_KEY)
    session_key.set_contree_project("tok-b", TYPED_PROJECT)
    assert console_api.contree_credentials("tok-b") == ("", "")
    assert console_api.contree_usable("tok-b") is False


def test_hosted_start_form_does_not_store_typed_project(monkeypatch):
    _hosted(monkeypatch)
    console_api.apply_start_fields("tok-c", {"contree_project_id": TYPED_PROJECT,
                                             "nebius_project_id": TYPED_PROJECT})
    assert not session_key.get_contree_project("tok-c")


def test_local_console_still_uses_typed_values(monkeypatch):
    for name in ("POC_HOSTED", "RENDER", "RENDER_SERVICE_ID", "SPACE_ID"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("NEBIUS_API_KEY", SERVER_KEY)
    session_key.set_key("tok-d", TYPED_KEY)
    session_key.set_contree_project("tok-d", TYPED_PROJECT)
    assert console_api.contree_credentials("tok-d") == (TYPED_KEY, TYPED_PROJECT)


def test_hosted_values_are_scrubbed_from_logs(monkeypatch):
    _hosted(monkeypatch)
    base = {"PATH": "/usr/bin", "POC_HOSTED": "1", "NEBIUS_API_KEY": SERVER_KEY,
            "NEBIUS_PROJECT_ID": SERVER_PROJECT}
    env, secrets = console_api.child_environment(base, "recorded", "tok-e", contree=True)
    assert env["NEBIUS_API_KEY"] == SERVER_KEY and env["NEBIUS_PROJECT_ID"] == SERVER_PROJECT
    assert SERVER_KEY in secrets and SERVER_PROJECT in secrets
    raw = io.StringIO()
    console_api._ScrubWriter(raw, secrets).write(f"key={SERVER_KEY} project {SERVER_PROJECT}\n")
    out = raw.getvalue()
    assert SERVER_KEY not in out and SERVER_PROJECT not in out


def test_hosted_refusal_messages_never_echo_values(monkeypatch):
    _hosted(monkeypatch)
    monkeypatch.setattr(console_api, "contree_usable", lambda *_a, **_k: False)
    plan = console_api.console_run_flags("tok-f")
    assert plan.refused and "Contree unavailable" in plan.note
    for text in (plan.note, console_api.refusal_message("tok-f"), console_api.CREDIT_CAP_MISSING):
        assert SERVER_KEY not in text and SERVER_PROJECT not in text
    _hosted(monkeypatch, key=None, project=None)
    assert "private server settings" in console_api.refusal_message("tok-f")


def test_hosted_needs_tavily_credit_cap(tmp_path):
    stop = console_api.hosted_budget_refusal({"POC_DAILY_CAP": "3"}, path=tmp_path / "d.json")
    assert stop == console_api.CREDIT_CAP_MISSING


def test_hosted_daily_cap_counts_every_check(tmp_path):
    env = {"POC_DAILY_CAP": "2", "POC_TAVILY_CREDIT_CAP": "900"}
    path = tmp_path / "d.json"
    assert console_api.hosted_budget_refusal(env, path=path, now=0) is None
    assert console_api.hosted_budget_refusal(env, path=path, now=10) is None
    stop = console_api.hosted_budget_refusal(env, path=path, now=20)
    assert stop and console_api.DAILY_CAP_REACHED in stop
    assert console_api.hosted_budget_refusal(env, path=path, now=86400 * 2) is None   # a new IST day


def test_require_contree_with_unsafe_is_refused():
    a = SimpleNamespace(require_contree=True, unsafe_no_sandbox=True)
    assert "cannot be used together" in daily_run.both_sandbox_flags_refusal(a)
    assert daily_run.both_sandbox_flags_refusal(SimpleNamespace(require_contree=True, unsafe_no_sandbox=False)) is None


def test_daily_run_refuses_both_flags_before_any_work():
    env = {"PATH": "/usr/bin:/bin"}
    proc = subprocess.run([sys.executable, str(ROOT / "ops" / "daily_run.py"), "--pr",
                           "https://github.com/me/demo/pull/3", "--require-contree", "--unsafe-no-sandbox"],
                          cwd=str(ROOT), env=env, capture_output=True, text=True, timeout=120)
    assert proc.returncode != 0
    assert "cannot be used together" in proc.stderr


def test_hosted_typed_key_is_neither_stored_nor_used(monkeypatch):
    _hosted(monkeypatch)
    console_api.apply_start_fields("tok-g", {"nebius_api_key": TYPED_KEY, "tavily_api_key": TYPED_KEY,
                                             "contree_project_id": TYPED_PROJECT})
    assert not session_key.get_key("tok-g")
    assert not session_key.get_tavily_key("tok-g")
    assert not session_key.get_contree_project("tok-g")
    # Even a key already in the session is not used on hosted.
    session_key.set_key("tok-g", TYPED_KEY)
    base = {"PATH": "/usr/bin", "POC_HOSTED": "1", "NEBIUS_API_KEY": SERVER_KEY,
            "NEBIUS_PROJECT_ID": SERVER_PROJECT}
    for contree in (False, True):
        env, _ = console_api.child_environment(base, "nebius", "tok-g", contree=contree)
        assert env["NEBIUS_API_KEY"] == SERVER_KEY
        assert TYPED_KEY not in env.values()
    assert console_api.resolve_console_provider("nebius", "tok-g") == ("nebius", None)


@pytest.mark.real_key_gate
def test_hosted_without_server_key_has_no_key(monkeypatch):
    _hosted(monkeypatch, key=None, project=None)
    session_key.set_key("tok-h", TYPED_KEY)
    assert console_api._has_typed_key("tok-h") is False
