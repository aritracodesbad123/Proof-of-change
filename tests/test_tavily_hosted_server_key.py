"""A hosted console uses the server Tavily key. A Codespace still uses its own."""
from poc import console_api, related_reports, session_key, tavily_docs

SERVER = "server-tavily-key-000"
TYPED = "typed-tavily-key-111"


def _env(**extra):
    base = {"PATH": "/usr/bin", "TAVILY_API_KEY": SERVER}
    base.update(extra)
    return base


def test_hosted_uses_the_server_key_and_ignores_a_typed_one():
    session_key.set_tavily_key("hosted-b", TYPED)
    try:
        env, secrets = console_api.child_environment(_env(), "recorded", "hosted-b")
        assert env["TAVILY_API_KEY"] == SERVER
        assert TYPED not in env.values()
        assert SERVER in secrets and TYPED in secrets
    finally:
        session_key.clear_key("hosted-b")


def test_hosted_without_a_server_key_has_nothing_to_look_up(capsys):
    session_key.set_tavily_key("hosted-a", TYPED)
    try:
        env, secrets = console_api.child_environment({"PATH": "/usr/bin"}, "recorded", "hosted-a")
        assert "TAVILY_API_KEY" not in env
        assert TYPED in secrets
        called = []
        out = related_reports.collect({"title": "x", "repo": "a/b"}, env=env, fetch=lambda q: called.append(q))
        assert out["status"] == "refused" and not called
        assert out["reason"] == tavily_docs.MISSING_KEY
        logged = capsys.readouterr().out
        assert tavily_docs.MISSING_KEY in logged
        assert SERVER not in logged and TYPED not in logged
    finally:
        session_key.clear_key("hosted-a")


def test_hosted_start_does_not_store_a_typed_key(monkeypatch):
    monkeypatch.delenv("CODESPACES", raising=False)
    session_key.clear_key("hosted-e")
    console_api.apply_start_fields("hosted-e", {"tavily_api_key": TYPED, "nebius_api_key": "nebius-typed-key-222"})
    assert session_key.get_tavily_key("hosted-e") is None
    assert session_key.get_key("hosted-e") == "nebius-typed-key-222"
    session_key.clear_key("hosted-e")


def test_codespace_keeps_the_secret_and_a_typed_key(monkeypatch):
    session_key.clear_key("cs-c")
    for flags in ({"CODESPACES": "true"}, {"CODESPACES": "true", "POC_SINGLE_USER": "1"}):
        env, secrets = console_api.child_environment(_env(**flags), "recorded", "cs-c")
        assert env["TAVILY_API_KEY"] == SERVER
        assert SERVER in secrets
    monkeypatch.setenv("CODESPACES", "true")
    console_api.apply_start_fields("cs-c", {"tavily_api_key": TYPED})
    try:
        env, secrets = console_api.child_environment(_env(CODESPACES="true"), "recorded", "cs-c")
        assert env["TAVILY_API_KEY"] == TYPED
        assert SERVER in secrets and TYPED in secrets
    finally:
        session_key.clear_key("cs-c")


def test_single_user_flag_without_codespace_still_uses_the_server_key():
    # POC_SINGLE_USER is honoured only inside a Codespace, so this stays a hosted console.
    session_key.set_tavily_key("hosted-d", TYPED)
    try:
        env, secrets = console_api.child_environment(_env(POC_SINGLE_USER="true"), "recorded", "hosted-d")
        assert env["TAVILY_API_KEY"] == SERVER
        assert TYPED not in env.values()
        assert SERVER in secrets
    finally:
        session_key.clear_key("hosted-d")
