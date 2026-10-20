"""Per-account runs. The observation record is not given an owner field."""
import json

from poc import console_api


def test_a_user_misses_an_unowned_run_and_an_admin_sees_it(tmp_path, monkeypatch):
    monkeypatch.setattr(console_api, "RUNS_ROOT", tmp_path)
    monkeypatch.setattr(console_api, "REPO_ROOT", tmp_path)
    console_api._recent_runs.clear()
    folder = tmp_path / "day" / "run-x"
    folder.mkdir(parents=True)
    (folder / "record.json").write_text(json.dumps({
        "record_kind": "pr_run", "id": "run-x", "repo": "me/demo", "verdict": "verified",
        "pr": {"number": 1, "url": "https://github.com/me/demo/pull/1", "title": "t"},
    }))
    assert console_api.list_runs(owner="user-a") == []
    assert console_api.get_run("run-x", owner="user-a") is None
    assert [row["id"] for row in console_api.list_runs(admin=True)] == ["run-x"]
    assert console_api.get_run("run-x", admin=True)["record"]["id"] == "run-x"
    assert "owner" not in json.loads((folder / "record.json").read_text())


def test_promote_sets_admin_without_a_password(tmp_path, monkeypatch):
    monkeypatch.setenv("POC_ACCOUNTS_FILE", str(tmp_path / "accounts.json"))
    from poc import console_auth
    console_auth.reset_for_tests()
    store = console_auth.get_store()

    def plant(data):
        data["accounts"]["ada@example.com"] = {
            "id": "ada", "email": "ada@example.com", "active": True, "password_hash": "scrypt-hash",
        }

    store.update(plant)
    assert console_auth.main(["promote", "ada@example.com"]) == 0
    saved = store.load()["accounts"]["ada@example.com"]
    assert saved["role"] == "admin"
    assert saved["password_hash"] == "scrypt-hash"
    assert "password" not in saved
    assert console_auth.main(["promote", "missing@example.com"]) == 1
