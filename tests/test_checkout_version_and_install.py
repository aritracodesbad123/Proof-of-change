"""Product checks: the checkout gets a real version (tags first, pretend version only when no tag is reachable),
the editable reinstall's exit code and output are kept, a failed editable install falls back to the checkout's own
source path, and a package that still does not import from the checkout stops the check loudly."""
import json
import os
import subprocess
import sys
from pathlib import Path

from ops import daily_run
from poc import contree_sandboxes

REPO, SHA = "octo/widget", "a" * 40


def _git(cwd, *args):
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@e", *args], cwd=cwd, check=True,
                   capture_output=True)


def _version_shell(tmp_path):
    report = tmp_path / "install.txt"
    return contree_sandboxes.CHECKOUT_VERSION_SHELL.replace(contree_sandboxes.INSTALL_REPORT, str(report)), report


def _run(shell, cwd, extra=""):
    env = dict(os.environ)
    env["PATH"] = str(Path(sys.executable).parent) + os.pathsep + env.get("PATH", "")
    return subprocess.run(["bash", "-c", shell + extra], cwd=cwd, capture_output=True, text=True, env=env)


def _origin_with_tag(tmp_path):
    origin = tmp_path / "origin"
    origin.mkdir()
    _git(origin, "init", "-q")
    (origin / "pyproject.toml").write_text('[project]\nname = "my-widget"\n')
    _git(origin, "add", ".")
    _git(origin, "commit", "-qm", "one")
    _git(origin, "tag", "v1.2.3")
    _git(origin, "commit", "-q", "--allow-empty", "-m", "two")
    return origin


def test_product_shell_fetches_tags_and_history_study_shell_unchanged():
    product = contree_sandboxes.install_shell_source(REPO, SHA, deps_only_fallback=True)
    assert f"git fetch -q --filter=tree:0 --tags origin {SHA}" in product
    assert contree_sandboxes.CHECKOUT_VERSION_SHELL in product
    study = contree_sandboxes.install_shell_source(REPO, SHA)
    assert "--tags" not in study and "PRETEND" not in study and f"git fetch -q --depth 1 origin {SHA}" in study


def test_same_install_text_on_both_sides_apart_from_the_commit():
    main = contree_sandboxes.install_shell_source(REPO, "b" * 40, deps_only_fallback=True)
    pr = contree_sandboxes.install_shell_source(REPO, "c" * 40, deps_only_fallback=True)
    assert main.replace("b" * 40, "X") == pr.replace("c" * 40, "X")


def test_reachable_tag_is_used_and_no_pretend_version(tmp_path):
    origin = _origin_with_tag(tmp_path)
    shell, report = _version_shell(tmp_path)
    r = _run(shell, origin, 'env | grep -c PRETEND || true')
    assert r.returncode == 0, r.stderr
    assert report.read_text().startswith("version_source=tag v1.2.3-1-g")
    assert r.stdout.strip().endswith("0")


def test_no_tag_in_history_uses_latest_remote_tag_scoped_to_project(tmp_path):
    origin = _origin_with_tag(tmp_path)
    clone = tmp_path / "clone"
    clone.mkdir()
    _git(clone, "init", "-q")
    _git(clone, "remote", "add", "origin", str(origin))
    _git(clone, "fetch", "-q", "--depth", "1", "origin", "HEAD")  # shallow, no tags: what 0.1.dev1 came from
    _git(clone, "checkout", "-q", "FETCH_HEAD")
    shell, report = _version_shell(tmp_path)
    r = _run(shell, clone, 'echo "$SETUPTOOLS_SCM_PRETEND_VERSION_FOR_MY_WIDGET|${SETUPTOOLS_SCM_PRETEND_VERSION-}"')
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == "1.2.3|"
    assert report.read_text().strip() == "version_source=no tag in history; pretend version 1.2.3 from latest tag v1.2.3"


def test_editable_failure_is_recorded_and_src_layout_put_on_path(tmp_path):
    work = tmp_path / "work"
    (work / "src" / "src" / "widget").mkdir(parents=True)
    site = tmp_path / "site"
    site.mkdir()
    shell = (contree_sandboxes.EDITABLE_REINSTALL_SHELL
             .replace("/work/", f"{work}/")
             .replace("python -m pip install --no-deps -e .", "sh -c 'echo build failed; exit 7'")
             .replace("sp=$(python -c \"import sysconfig;print(sysconfig.get_paths()['purelib'])\")", f"sp={site}"))
    open(work / "poc-install.txt", "w").close()
    r = _run(shell, work / "src")
    assert r.returncode == 0, r.stderr
    rep = (work / "poc-install.txt").read_text()
    assert "editable_exit=7" in rep and f"editable_fallback=source path {work}/src/src" in rep
    assert (work / "poc-editable.log").read_text().strip() == "build failed"
    assert (site / "_poc_own_checkout.pth").read_text().strip() == f"{work}/src/src"


class _Sess:
    """Import-origin probe fails (package missing); install report says the editable install failed."""

    def __init__(self, origin_ok: bool, editable_exit: str):
        self.origin_ok, self.editable_exit, self.calls = origin_ok, editable_exit, []

    def run_argv(self, side, argv, **kw):
        self.calls.append((side, argv, kw.get("cwd")))
        code = argv[-1]
        if argv[0] == "tail":
            return {"exit_code": 0, "stdout": "error: Cannot update time stamp\n"}
        if "pip_show" in code:
            return {"exit_code": 0, "stdout": "python=/usr/local/bin/python\nversion_source=tag 1.0\n"
                                              f"editable_exit={self.editable_exit}\npip_show_exit=1\n"}
        if self.origin_ok:
            return {"exit_code": 0, "stdout": json.dumps({"root": "/work/src", "file": "/work/src/src/w/__init__.py",
                                                          "namespace": False, "paths": []})}
        return {"exit_code": 1, "stdout": "", "stderr": "ModuleNotFoundError"}


def test_failed_install_and_not_importable_stops_loudly_with_evidence(capsys):
    rec = {}
    why = daily_run._check_own_checkout(_Sess(False, "1"), rec, "w")
    assert why and "did not install (editable install exit 1)" in why
    oc = rec["contree"]["own_checkout"]
    assert oc["status"] == "not installed"
    assert oc["install"]["main"]["python"] == "/usr/local/bin/python"
    assert "time stamp" in oc["install"]["pr"]["editable_output_tail"]
    assert "Checkout install (main): python=/usr/local/bin/python" in capsys.readouterr().out


def test_not_importable_after_good_install_is_recorded_not_ok():
    rec = {}
    assert daily_run._check_own_checkout(_Sess(False, "0"), rec, "w") is None
    assert rec["contree"]["own_checkout"]["status"] == "not importable (recorded only)"


def test_install_report_read_with_the_test_python_from_the_checkout():
    sess = _Sess(True, "0")
    rec = {}
    assert daily_run._check_own_checkout(sess, rec, "w") is None
    rep = [c for c in sess.calls if "pip_show" in c[1][-1]]
    assert {c[0] for c in rep} == {"main", "pr"}
    assert all(c[1][0] == "python" and c[2] == "/work/src" for c in rep)
    assert rec["contree"]["own_checkout"]["install"]["pr"]["version_source"] == "tag 1.0"


def test_parse_install_report_ignores_noise():
    assert daily_run.parse_install_report("x\nversion_source=tag v1=2\nBad Key=1\n") == {"version_source": "tag v1=2"}
