"""POC_INSTALL_OVERRIDES: the same overrides file reaches the install command (and the sandbox, read-only)."""
from ops import daily_run as dr


def _capture(monkeypatch):
    seen = []
    monkeypatch.setattr(dr, "run", lambda c, log, env=None, timeout=None, sbx=None, **_kw: seen.append((c, sbx)) or (0, 0.1))
    return seen


def test_overrides_file_is_passed_and_mounted(tmp_path, monkeypatch):
    ov = tmp_path / "overrides.txt"
    ov.write_text("scikit-umfpack; python_version < '0'\n")
    monkeypatch.setenv("POC_INSTALL_OVERRIDES", str(ov))
    seen = _capture(monkeypatch)
    ok, _ = dr.install_side(tmp_path / "venv-pr", tmp_path, None, tmp_path / "log", "3.12", 60, None)
    cmd, sbx = seen[-1]
    assert ok and "--override" in cmd and cmd[cmd.index("--override") + 1] == str(ov)
    assert ov in sbx["ro"] or str(ov) in map(str, sbx["ro"])


def test_missing_or_unset_overrides_change_nothing(tmp_path, monkeypatch):
    monkeypatch.setenv("POC_INSTALL_OVERRIDES", str(tmp_path / "nope.txt"))
    seen = _capture(monkeypatch)
    dr.install_side(tmp_path / "venv-pr", tmp_path, None, tmp_path / "log", "3.12", 60, None)
    assert "--override" not in seen[-1][0]
    monkeypatch.delenv("POC_INSTALL_OVERRIDES")
    seen.clear()
    dr.install_side(tmp_path / "venv-main", tmp_path, None, tmp_path / "log", "3.12", 60, None)
    assert "--override" not in seen[-1][0]
