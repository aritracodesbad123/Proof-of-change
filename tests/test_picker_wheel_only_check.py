"""Picker: the default branch's requirements must resolve to ready-built wheels (mocked dry runs)."""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).parent.parent
spec = importlib.util.spec_from_file_location("daily_run", ROOT / "ops" / "daily_run.py")
dr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dr)

PASS_OUT = "certifi==2026.10.19\n    # via requests\nrequests==2.34.2\n"
SDIST_OUT = ("error: No solution found when resolving dependencies\n"
             "  cause: Because sdistpkg==2.9.9 has no usable wheels and you require sdistpkg==2.9.9, we can conclude "
             "that your requirements are unsatisfiable.\n\n"
             "hint: Wheels are required for `sdistpkg` because building from source is disabled for all packages\n")
RESOLVE_OUT = ("error: No solution found when resolving dependencies\n"
               "  cause: Because missingpkg was not found in the package registry and you require missingpkg, we "
               "can conclude that your requirements are unsatisfiable.\n")


def fake(rc, out, seen=None):
    def runner(cmd, env, text):
        if seen is not None:
            seen.append((cmd, env, text))
        return rc, out
    return runner


def test_wheel_only_pass_and_isolated_command(monkeypatch):
    monkeypatch.setenv("UV_INDEX_URL", "https://example.invalid/simple")
    seen = []
    assert dr.wheel_only_skip(["requests>=2", "numpy"], "3.12", fake(0, PASS_OUT, seen)) is None
    cmd, env, text = seen[0]
    c = [str(x) for x in cmd]
    assert c[1:3] == ["pip", "compile"]
    assert c[c.index("--only-binary") + 1] == ":all:"
    assert c[c.index("--python-version") + 1] == "3.12"
    assert "--no-config" in c
    assert "UV_INDEX_URL" not in env and env["UV_NO_CONFIG"] == "1"
    assert text.split() == ["requests>=2", "numpy"]


def test_source_build_is_skipped_with_package_name():
    assert dr.wheel_only_skip(["sdistpkg==2.9.9"], "3.12", fake(1, SDIST_OUT)) == "skipped: needs compiling (sdistpkg)"


def test_transitive_source_build_names_the_package():
    out = "  cause: Because only depx==1.0 is available and depx==1.0 has no usable wheels, we can conclude ...\n"
    assert dr.wheel_only_skip(["top"], "3.12", fake(1, out)) == "skipped: needs compiling (depx)"


def test_resolver_error_is_skipped():
    why = dr.wheel_only_skip(["missingpkg"], "3.12", fake(1, RESOLVE_OUT))
    assert why.startswith("skipped: requirements do not resolve to ready-built wheels (")
    assert "No solution found" in why


def test_no_requirements_runs_nothing():
    assert dr.wheel_only_skip([], "3.12", fake(1, "should not run")) is None


def test_plain_req_drops_options_urls_and_paths():
    for bad in ["-r other.txt", "--index-url https://x", "-e .", "pkg @ https://x/p.whl", "git+https://x/r.git",
                "./local", "# comment", ""]:
        assert dr._plain_req(bad) is None
    assert dr._plain_req("pkg>=1 ; python_version>'3.8'  # note") == "pkg>=1 ; python_version>'3.8'"


class FakeGH:
    def __init__(self, files):
        self.files = files

    def json(self, path):
        return [{"number": 7, "title": "t", "updated_at": "2026-10-22T00:00:00Z", "draft": False,
                 "head": {"sha": "a" * 40}, "base": {"sha": "b" * 40, "ref": "main"}, "html_url": "u",
                 "user": {"login": "x"}, "body": ""}]

    def get(self, url, accept=None, api=True, timeout=60):
        name = url.split("/contents/")[1].split("?")[0]
        if name not in self.files:
            raise FileNotFoundError(name)
        return self.files[name].encode()

    def diff(self, repo, n):
        return "diff --git a/pkg/m.py b/pkg/m.py\n+x\n"

    def ci_state(self, repo, sha):
        return "passing", "ok"


def test_select_prs_skips_and_selects():
    gh = FakeGH({"pyproject.toml": '[project]\ndependencies = ["sdistpkg==2.9.9"]\n'})
    cfg = {"pkg": "pkg"}
    chosen, sk = dr.select_prs(gh, "o/r", cfg, {}, None, 3, 5, None, python="3.12", wheel_runner=fake(1, SDIST_OUT))
    assert chosen == [] and sk[0]["why"] == "skipped: needs compiling (sdistpkg)"
    seen = []
    chosen, sk = dr.select_prs(gh, "o/r", cfg, {}, None, 3, 5, None, python="3.12", wheel_runner=fake(0, PASS_OUT, seen))
    assert [c["pr"] for c in chosen] == [7] and seen[0][2].split() == ["sdistpkg==2.9.9"]
    chosen, _ = dr.select_prs(gh, "o/r", cfg, {}, None, 3, 5, None)   # no python: unchanged behaviour
    assert [c["pr"] for c in chosen] == [7]
