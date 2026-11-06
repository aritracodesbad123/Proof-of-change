"""New tests are evidence only when the base interpreter actually ran them.

Each side installs the requirements its own checkout declares. The base pytest process is that side's
interpreter, not the runner's. A missing base collection or load is a named limitation, not a pass.
Nothing here contacts GitHub or a live project.
"""
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from ops import daily_run as dr
from poc import demo_helper, probes

SHA = "ab" * 20
INI = "[pytest]\npython_files = *\n"
OLD = '''
class Parser_:
    class parse_argv:
        class positional_arguments:
            def omitted_positional_arg_raises_ParseError(self):
                assert True
'''
NEW = '''
from pytest import mark
class Parser_:
    class parse_argv:
        class positional_arguments:
            def omitted_positional_arg_raises_ParseError(self):
                assert True

            @mark.parametrize("cli_name,attr_name", [("param-1", "param_1"), ("plain", None)])
            def omitted_positionals_report_cli_names(self, cli_name, attr_name):
                from pkg.mod import answer
                assert answer() == 2

            @mark.skip(reason="later")
            def skipped_case(self):
                assert False
'''
PASS = '''
from pytest import mark
class Parser_:
    class parse_argv:
        class positional_arguments:
            def omitted_positional_arg_raises_ParseError(self):
                assert True

            @mark.parametrize("cli_name,attr_name", [("param-1", "param_1"), ("plain", None)])
            def omitted_positionals_report_cli_names(self, cli_name, attr_name):
                from pkg.mod import answer
                assert answer() == 2
'''
LOAD = '''
from pytest import mark
class Parser_:
    class parse_argv:
        class positional_arguments:
            def omitted_positional_arg_raises_ParseError(self):
                assert True

            def reports_names(self):
                import only_side
                from pkg.mod import answer
                assert only_side.MARKER == "pr"
                assert answer() == 2
'''
BOOM = "import missing_module_xyz\n"


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _checkout(root: Path, requirements: list[str], dev_extra: list[str]) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "dev-requirements.txt").write_text("\n".join(requirements) + "\n")
    extra = ", ".join(f'"{item}"' for item in dev_extra)
    (root / "pyproject.toml").write_text(
        '[project]\nname = "pkg"\nversion = "0"\n'
        f"[project.optional-dependencies]\ndev = [{extra}]\n")
    return root


def _declared(root: Path) -> list[str]:
    return [item["requirement"] for item in demo_helper.declared_packages(root, "pkg") if item["action"] == "install"]


def _install(venv: Path, checkout: Path, home: Path, monkey_env: dict) -> list[str]:
    """Install this checkout's declared requirements with pip, host index config removed."""
    specs = _declared(checkout)
    saved = {key: os.environ.get(key) for key in monkey_env}
    os.environ.update(monkey_env)
    try:
        subprocess.check_call([sys.executable, "-m", "venv", str(venv)])
        env = dr.no_index_config_env(dr.base_env(home, install=True))
        pip_specs = [spec for spec in specs if spec.split("[", 1)[0].startswith("pytest")]
        local = checkout / "vendor" / "only-side"
        if any(spec.split("[", 1)[0] == "only-side" for spec in specs) and local.is_dir():
            pip_specs.append(str(local))
        if pip_specs:
            subprocess.check_call([str(venv / "bin" / "python"), "-m", "pip", "install", "-q", *pip_specs], env=env)
    finally:
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
    return specs


@pytest.fixture(scope="module")
def sides(tmp_path_factory):
    root = tmp_path_factory.mktemp("sides")
    base = _checkout(root / "decl-base", ["pytest>=8", "pytest-timeout>=2", "pytest-relaxed>=2"], ["toolx==1"])
    pr = _checkout(root / "decl-pr", ["pytest>=8", "pytest-timeout>=2", "pytest-relaxed>=2", "only-side"], ["toolx==2"])
    bare = _checkout(root / "decl-bare", ["pytest>=8", "pytest-timeout>=2"], ["toolx==1"])
    pkg = root / "vendor" / "only-side"
    _write(pkg / "pyproject.toml", '[project]\nname = "only-side"\nversion = "1"\n')
    _write(pkg / "only_side" / "__init__.py", 'MARKER = "pr"\n')
    # The pull-request checkout is the one that declares the local package.
    _write(pr / "vendor" / "only-side" / "pyproject.toml", (pkg / "pyproject.toml").read_text())
    _write(pr / "vendor" / "only-side" / "only_side" / "__init__.py", 'MARKER = "pr"\n')
    host = {"PIP_INDEX_URL": "http://127.0.0.1:9/simple", "PIP_CONFIG_FILE": "/tmp/host-pip.conf"}
    base_specs = _install(root / "venv-base", base, root / "home-base", host)
    pr_specs = _install(root / "venv-pr", pr, root / "home-pr", host)
    bare_specs = _install(root / "venv-bare", bare, root / "home-bare", host)
    return {"base": base, "pr": pr, "bare": bare, "venv_base": root / "venv-base", "venv_pr": root / "venv-pr",
            "venv_bare": root / "venv-bare", "base_specs": base_specs, "pr_specs": pr_specs, "bare_specs": bare_specs,
            "host": host}


def _tree(root: Path, answer: str, checks: str, extra: str | None = None) -> None:
    _write(root / "pytest.ini", INI)
    _write(root / "pkg" / "__init__.py", "")
    _write(root / "pkg" / "mod.py", f"def answer():\n    return {answer}\n")
    _write(root / "tests" / "__init__.py", "")
    _write(root / "tests" / "parser_parser.py", checks)
    _write(root / "tests" / "test_old.py", "def test_old():\n    assert True\n")
    _write(root / "tests" / "leave_me.py", "import missing_module_xyz\n")
    if extra:
        _write(root / "tests" / "other_changed.py", extra)


def _files(extra: bool) -> dict:
    names = ["pkg/mod.py", "tests/parser_parser.py", "tests/test_old.py"]
    if extra:
        names.append("tests/other_changed.py")
    return {"all": names, "package_py": ["pkg/mod.py"], "compiled": [], "other": ["tests/parser_parser.py"]}


def _run(tmp: Path, sides: dict, base_checks: str, pr_checks: str, *, base_venv: str, answer: tuple[str, str],
         extra: bool = False, probes_on: bool = False, sha: str | None = SHA, targets_include_parser: bool = False):
    work = tmp / "work"
    main, pr = work / "side-main", work / "side-pr"
    _tree(main, answer[0], base_checks, BOOM if extra else None)
    _tree(pr, answer[1], pr_checks, BOOM if extra else None)
    venvs = {"main": sides[base_venv], "pr": sides["venv_pr"]}
    files = _files(extra)
    rec = {"files": files, "base_ref": "2.2", "pr": {"tested_main_sha": sha} if sha else {}, "product_check": False}
    if probes_on:
        claims = [{"id": "C1", "text": "Results stay the same after this change.", "covers": ["value"], "expect": "same"}]
        spec = {"id": "model-p1", "source": "model", "claims": claims}
        obs = probes.judge(spec, {"main": [{"value": "1"}] * 3, "pr": [{"value": "2"}] * 3})
        rec["probes"] = {"items": [{"id": "model-p1", "claims": claims, "observations": obs}]}
    rundir = tmp / "run"
    rundir.mkdir()
    pr_targets = ["tests/test_old.py"] + (["tests/parser_parser.py"] if targets_include_parser else [])
    targets = {"main": ["tests/test_old.py"], "pr": pr_targets}
    args = SimpleNamespace(runs=1, workers="0", test_timeout=60, run_timeout=180, build_timeout=60,
                           pr="https://example.test/pull/1", product_check=False, bench=None)
    from guardrails import sandbox
    was = sandbox.enabled()
    sandbox.configure(False)
    try:
        cmp, cnv, ex = dr.execute_tests(rec, venvs, targets, rundir, work, args, cwds={"main": main, "pr": pr})
    finally:
        sandbox.configure(was)
    before = dr.verdict_for(cmp, cnv, ex, files, rec.get("probes"))
    dr._store_verdict(rec, cmp, cnv, ex)
    stored_before_gate = rec["verdict"]
    rec = dr.gate(rec)
    return rec, cmp, before, stored_before_gate, rundir, main


def _names(ids) -> str:
    return "\n".join(str(item) for item in ids or [])


def test_each_side_declares_and_installs_its_own_requirements(sides):
    """The install list comes from that checkout. Host index settings are not part of the install env."""
    assert "pytest-relaxed>=2" in sides["base_specs"]
    assert "only-side" in sides["pr_specs"] and "only-side" not in sides["base_specs"]
    assert "pytest-relaxed>=2" not in sides["bare_specs"]
    reqs, _cons = dr.pr_side_own_installs(["toolx==1"], sides["base"], sides["pr"], None, "pkg")
    assert reqs == ["toolx==2"]
    env = dr.no_index_config_env(dr.base_env(sides["base"].parent / "home-env", install=True))
    assert "PIP_INDEX_URL" not in env
    assert env.get("PIP_CONFIG_FILE") == os.devnull
    base_py = sides["venv_base"] / "bin" / "python"
    assert base_py.is_file()
    assert not list(sides["venv_base"].glob("lib/python*/site-packages/runner.pth"))
    got = subprocess.check_output([str(base_py), "-c", "import pytest_relaxed,sys; print(sys.prefix)"], text=True)
    assert str(sides["venv_base"]) in got
    bare = subprocess.run([str(sides["venv_bare"] / "bin" / "python"), "-c", "import pytest_relaxed"],
                          capture_output=True, text=True)
    assert bare.returncode != 0


def test_nested_parser_failure_on_the_base_is_fixed_without_a_branch_sentence(tmp_path, sides):
    rec, cmp, before, stored, rundir, main = _run(
        tmp_path, sides, OLD, NEW, base_venv="venv_base", answer=("1", "2"), targets_include_parser=True)
    info = cmp["new_test_evidence"]
    assert info["tested_main_sha"] == SHA and info["base_ref"] == "2.2"
    assert any("param-1" in item for item in info["fixed_ids"])
    assert any("param-1" in item for item in cmp["fixed"])
    assert not any("omitted_positional_arg_raises_ParseError" in item for item in info["new_ids"])
    assert not any("skipped_case" in item for item in info["passed_on_base"])
    assert any("skipped_case" in item for item in info["skipped"])
    assert "leave_me.py" not in " ".join(item["path"] for item in info["limitations"])
    assert rec.get("already_on_base") is None
    assert "2.2" not in (rec.get("reason") or "")
    assert "fix appears already present" not in (rec.get("reason") or "")
    assert dr.changed_test_files(rec["files"]) == ["tests/test_old.py"]
    log = next(rundir.glob("pytest-cross-main-*-tests_parser_parser.py.log"))
    assert str(sides["venv_base"] / "bin" / "python") in log.read_text(errors="replace")
    assert "reports_names" not in (main / "tests" / "parser_parser.py").read_text()
    assert stored == before[0]


def test_base_without_the_collector_is_a_named_limitation(tmp_path, sides):
    rec, cmp, _before, _stored, _rundir, _main = _run(
        tmp_path, sides, OLD, NEW, base_venv="venv_bare", answer=("1", "2"), targets_include_parser=True)
    info = cmp["new_test_evidence"]
    paths = [item["path"] for item in info["limitations"]]
    assert "tests/parser_parser.py" in paths
    assert cmp["new_tests_passing"] == 0 and cmp["new_tests_passing_ids"] == []
    assert not info["reproduced"] and not info["fixed_ids"]
    assert rec["verdict"] == "could_not_verify"
    assert "tests/parser_parser.py" in rec["reason"]
    assert rec.get("already_on_base") is None
    assert dr.changed_test_files(rec["files"]) == ["tests/test_old.py"]


def test_flagged_preservation_probe_stays_needs_attention(tmp_path, sides):
    rec, cmp, before, stored, _rundir, _main = _run(
        tmp_path, sides, OLD, PASS, base_venv="venv_base", answer=("2", "2"), probes_on=True)
    assert before[0] == "needs_attention"
    assert stored == "needs_attention" and rec["verdict"] == "needs_attention"
    assert rec["probes"]["items"][0]["id"] == "model-p1"
    assert rec.get("already_on_base") is None
    assert "already pass" not in (rec.get("reason") or "")
    assert any("param-1" in item for item in cmp["new_test_evidence"]["passed_on_base"])


def test_no_probe_sentence_matches_verdict_for_and_names_the_commit(tmp_path, sides):
    rec, cmp, before, stored, _rundir, _main = _run(
        tmp_path, sides, OLD, PASS, base_venv="venv_base", answer=("2", "2"))
    assert stored == before[0] == "verified"
    assert rec["already_on_base"] == f"new tests already pass on the tested base {SHA}"
    assert "2.2" not in rec["already_on_base"]
    # The existing probe-coverage gate can lower a verified result when no probe ran. The sentence does not.
    assert dr.new_test_limitation_gate(
        {"verdict": stored, "reason": rec.get("reason") or "", "comparison": rec.get("comparison")})["verdict"] == "verified"


def test_other_changed_file_collection_failure_blocks_verified(tmp_path, sides):
    rec, cmp, _before, _stored, _rundir, _main = _run(
        tmp_path, sides, OLD, PASS, base_venv="venv_base", answer=("2", "2"), extra=True)
    paths = [item["path"] for item in cmp["new_test_evidence"]["limitations"]]
    assert "tests/other_changed.py" in paths
    assert rec["verdict"] == "could_not_verify"
    assert "tests/other_changed.py" in rec["reason"]
    assert rec.get("already_on_base") is None
    assert "leave_me.py" not in " ".join(paths)


def test_assertion_failure_stays_fixed_beside_the_other_file(tmp_path, sides):
    rec, cmp, _before, _stored, _rundir, _main = _run(
        tmp_path, sides, OLD, NEW, base_venv="venv_base", answer=("1", "2"), extra=True)
    assert any("param-1" in item for item in cmp["fixed"])
    assert any("param-1" in item for item in cmp["new_test_evidence"]["fixed_ids"])
    assert rec["verdict"] != "verified"
    assert "tests/other_changed.py" in rec["reason"]
    assert rec.get("already_on_base") is None


def test_base_load_error_is_not_a_new_pass_or_a_fix(tmp_path, sides):
    rec, cmp, _before, _stored, _rundir, _main = _run(
        tmp_path, sides, OLD, LOAD, base_venv="venv_base", answer=("1", "2"), targets_include_parser=True)
    info = cmp["new_test_evidence"]
    blob = _names(cmp["new_tests_passing_ids"]) + _names(cmp["fixed"]) + _names(info["fixed_ids"])
    assert "reports_names" not in blob
    assert cmp["new_tests_passing"] == 0
    assert info["reproduced"] is False
    assert any(item["path"] == "tests/parser_parser.py" for item in info["limitations"])
    assert rec["verdict"] == "could_not_verify"
    assert rec.get("already_on_base") is None


def test_overlay_when_the_parent_is_a_file_is_named(tmp_path, sides):
    work = tmp_path / "work"
    main, pr = work / "side-main", work / "side-pr"
    _write(main / "pkg" / "mod.py", "def answer():\n    return 1\n")
    _write(main / "tests", "not-a-directory\n")
    _write(main / "tests_old_holder" / "test_old.py", "def test_old():\n    assert True\n")
    _tree(pr, "2", "def test_ok():\n    assert True\n")
    # The base tree's tests path is a file. Keep a real test file beside it so the timed run has a result.
    _write(main / "keep" / "test_old.py", "def test_old():\n    assert True\n")
    _write(pr / "keep" / "test_old.py", "def test_old():\n    assert True\n")
    files = {"all": ["tests/checks.py", "keep/test_old.py"], "package_py": [], "compiled": []}
    # checks.py is the pull-request file under the blocked parent.
    _write(pr / "tests" / "checks.py", "def test_ok():\n    assert True\n")
    _write(pr / "pytest.ini", INI)
    _write(main / "pytest.ini", INI)
    rec = {"files": files, "base_ref": "2.2", "pr": {"tested_main_sha": SHA}}
    rundir = tmp_path / "run"
    rundir.mkdir()
    args = SimpleNamespace(runs=1, workers="0", test_timeout=60, run_timeout=120, build_timeout=60,
                           pr="https://example.test/pull/1", product_check=False, bench=None)
    from guardrails import sandbox
    was = sandbox.enabled()
    sandbox.configure(False)
    try:
        cmp, cnv, ex = dr.execute_tests(
            rec, {"main": sides["venv_base"], "pr": sides["venv_pr"]},
            {"main": ["keep/test_old.py"], "pr": ["keep/test_old.py"]}, rundir, work, args,
            cwds={"main": main, "pr": pr})
    finally:
        sandbox.configure(was)
    assert cnv is None and cmp is not None
    info = cmp["new_test_evidence"]
    assert any(item["path"] == "tests/checks.py" and item["kind"] == "overlay" and item["detail"] == "FileExistsError"
               for item in info["limitations"])
    assert info["passed_on_base"] == []
    dr._store_verdict(rec, cmp, cnv, ex)
    rec = dr.gate(rec)
    assert rec["verdict"] != "verified"
    assert "tests/checks.py" in rec["reason"]
    assert rec.get("already_on_base") is None


def test_shared_test_that_does_not_run_on_the_base_is_not_a_new_pass(tmp_path, sides):
    """A test both sides collect is not a new pass when the base run never executes it.

    The fixture lives only on the pull request. The test file is overlaid alone, so the base import of that
    fixture fails. The ordinary comparison must not keep the pull-request pass."""
    work = tmp_path / "work"
    main, pr = work / "side-main", work / "side-pr"
    shared = '''
def test_shared(only_pr):
    assert only_pr == 1

class Parser_:
    class parse_argv:
        class positional_arguments:
            def omitted_positional_arg_raises_ParseError(self):
                assert True
'''
    added = shared + '''
            def reports_new(self):
                assert True
'''
    _tree(main, "1", shared)
    _tree(pr, "1", added)
    _write(pr / "tests" / "conftest.py", "import pytest\n\n@pytest.fixture\ndef only_pr():\n    return 1\n")
    files = _files(False)
    record = {"files": files, "base_ref": "2.2", "pr": {"tested_main_sha": SHA}}
    rundir = tmp_path / "run"
    rundir.mkdir()
    args = SimpleNamespace(runs=1, workers="0", test_timeout=60, run_timeout=180, build_timeout=60,
                           pr="https://example.test/pull/1", product_check=False, bench=None)
    from guardrails import sandbox
    was = sandbox.enabled()
    sandbox.configure(False)
    try:
        cmp, cnv, ex = dr.execute_tests(
            record, {"main": sides["venv_base"], "pr": sides["venv_pr"]},
            {"main": ["tests/test_old.py"], "pr": ["tests/test_old.py", "tests/parser_parser.py"]},
            rundir, work, args, cwds={"main": main, "pr": pr})
    finally:
        sandbox.configure(was)
    assert cnv is None and cmp is not None
    info = cmp["new_test_evidence"]
    blob = _names(cmp["new_tests_passing_ids"]) + _names(cmp["fixed"]) + _names(info["fixed_ids"])
    assert "test_shared" not in blob
    assert any(item["path"] == "tests/parser_parser.py" for item in info["limitations"])
    assert any("test_shared" in item for item in info["not_executed"])
    dr._store_verdict(record, cmp, cnv, ex)
    record = dr.gate(record)
    assert record["verdict"] != "verified"
    assert record.get("already_on_base") is None


def test_a_mismatched_tested_sha_is_not_used_as_the_base(tmp_path, sides):
    work = tmp_path / "work"
    main, pr = work / "side-main", work / "side-pr"
    _tree(main, "2", OLD)
    _tree(pr, "2", PASS)
    env = {**os.environ, "GIT_AUTHOR_NAME": "test", "GIT_AUTHOR_EMAIL": "test@example.com",
           "GIT_COMMITTER_NAME": "test", "GIT_COMMITTER_EMAIL": "test@example.com"}
    subprocess.check_call(["git", "init", "-q"], cwd=main, env=env)
    subprocess.check_call(["git", "add", "."], cwd=main, env=env)
    subprocess.check_call(["git", "commit", "-q", "-m", "base"], cwd=main, env=env)
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=main, text=True).strip()
    assert head and head != SHA
    record = {"files": _files(False), "base_ref": "2.2", "pr": {"tested_main_sha": SHA}}
    rundir = tmp_path / "run"
    rundir.mkdir()
    args = SimpleNamespace(runs=1, workers="0", test_timeout=60, run_timeout=120, build_timeout=60,
                           pr="https://example.test/pull/1", product_check=False, bench=None)
    from guardrails import sandbox
    was = sandbox.enabled()
    sandbox.configure(False)
    try:
        cmp, cnv, ex = dr.execute_tests(
            record, {"main": sides["venv_base"], "pr": sides["venv_pr"]},
            {"main": ["tests/test_old.py"], "pr": ["tests/test_old.py"]}, rundir, work, args,
            cwds={"main": main, "pr": pr})
    finally:
        sandbox.configure(was)
    info = cmp["new_test_evidence"]
    assert any(item["kind"] == "base_checkout" for item in info["limitations"])
    assert info["passed_on_base"] == [] and info["tested_main_sha"] == ""
    dr._store_verdict(record, cmp, cnv, ex)
    record = dr.gate(record)
    assert record.get("already_on_base") is None
    assert record["verdict"] != "verified"
