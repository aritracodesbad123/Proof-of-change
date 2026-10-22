"""Product checks on a component app install the core requirements plus the touched component's own requirements,
read from main, and never the aggregate requirements file."""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from ops import daily_run
from poc import demo_helper

COMPONENTS = {"one": ["lib-one==1.0"], "two": ["lib-two==2.0"], "three": ["lib-three==3.0"]}


def _app(root: Path, manifests=None) -> Path:
    root.mkdir(parents=True)
    (root / "requirements.txt").write_text("core-lib==1.0\n")
    (root / "requirements_test.txt").write_text("-r requirements.txt\ntest-lib==1.0\n")
    every = [r for reqs in COMPONENTS.values() for r in reqs]
    (root / "requirements_all.txt").write_text("-r requirements.txt\n" + "\n".join(every) + "\n")
    (root / "requirements_test_all.txt").write_text("-r requirements_test.txt\n" + "\n".join(every) + "\n")
    for name, reqs in (manifests or COMPONENTS).items():
        d = root / "app" / "components" / name
        d.mkdir(parents=True)
        (d / "manifest.json").write_text(json.dumps({"domain": name, "requirements": reqs}))
        (d / "__init__.py").write_text("")
    return root


def _plan(main, pr, changed, docs=True):
    return demo_helper.build_setup_plan(
        "acme/big-app", [main, pr], {"text": ""}, "3.12", "contree", "big-app",
        python_available=lambda v: None, pypi=lambda n: None, allow_lookup_packages=False,
        docs_checkouts=[main] if docs else None, apply_system=False, changed_files=changed)


def test_detects_component_from_changed_files(tmp_path):
    comps = demo_helper.component_dirs(_app(tmp_path / "m"))
    assert set(comps) == {f"app/components/{n}" for n in COMPONENTS}
    assert demo_helper.component_for_changes(
        ["app/components/two/sensor.py", "tests/components/two/test_sensor.py"], comps) == "app/components/two"
    assert demo_helper.component_for_changes(["app/components/two/x.py", "app/components/one/y.py"], comps) is None
    assert demo_helper.component_for_changes(["app/core.py", "app/components/two/x.py"], comps) is None
    assert demo_helper.component_for_changes([], comps) is None
    # regenerated aggregate files do not count against the single component
    assert demo_helper.component_for_changes(
        ["app/components/two/manifest.json", "requirements_all.txt"], comps,
        ignore=["requirements_all.txt"]) == "app/components/two"


def test_aggregate_files_found_from_content_not_name(tmp_path):
    root = _app(tmp_path / "m")
    (root / "requirements_misc.txt").write_text("lib-one==1.0\nlib-two==2.0\n")   # aggregates, any name
    names = [p.name for p in demo_helper.aggregate_requirement_files(root, demo_helper.component_dirs(root))]
    assert names == ["requirements_all.txt", "requirements_misc.txt", "requirements_test_all.txt"]


def test_product_plan_installs_core_plus_component_and_never_the_aggregate(tmp_path):
    main = _app(tmp_path / "main")
    plan = _plan(main, _app(tmp_path / "pr"), ["app/components/two/sensor.py", "requirements_all.txt"])
    assert plan["component"] == "app/components/two" and plan["scope_blocked"] == ""
    reqs = set(plan["extra_reqs"])
    assert {"core-lib==1.0", "test-lib==1.0", "lib-two==2.0"} <= reqs
    assert not reqs & {"lib-one==1.0", "lib-three==3.0"}
    assert all(p["source"] not in ("requirements_all.txt", "requirements_test_all.txt") for p in plan["packages"])


def test_component_requirements_come_from_main_not_the_pr(tmp_path):
    main = _app(tmp_path / "main")
    pr = _app(tmp_path / "pr", manifests={**COMPONENTS, "two": ["pr-only-lib==9.9"]})
    plan = _plan(main, pr, ["app/components/two/manifest.json", "app/components/two/sensor.py"])
    assert "lib-two==2.0" in plan["extra_reqs"] and "pr-only-lib==9.9" not in plan["extra_reqs"]


def test_no_single_component_stops_as_unsupported_without_the_aggregate(tmp_path):
    main = _app(tmp_path / "main")
    plan = _plan(main, _app(tmp_path / "pr"), ["app/core.py", "app/components/one/x.py"])
    assert plan["component"] is None and plan["scope_blocked"].startswith("unsupported:")
    assert not set(plan["extra_reqs"]) & {"lib-one==1.0", "lib-two==2.0", "lib-three==3.0"}


def test_ordinary_project_and_study_plan_unchanged(tmp_path):
    main = tmp_path / "plain"
    main.mkdir()
    (main / "requirements.txt").write_text("a==1\n")
    (main / "requirements-dev.txt").write_text("b==1\n")
    scoped = _plan(main, main, ["src/x.py"])
    before = _plan(main, main, None)
    assert scoped["extra_reqs"] == before["extra_reqs"] and set(before["extra_reqs"]) == {"a==1", "b==1"}
    assert scoped["scope_blocked"] == "" and scoped["component"] is None
    app = _app(tmp_path / "app")
    study = _plan(app, app, None, docs=False)          # study: no changed files, every checkout read as before
    assert "lib-one==1.0" in study["extra_reqs"] and study["scope_blocked"] == ""


def test_scope_block_stops_installs_on_product_only(monkeypatch):
    plan = {"groups_blocked": "", "scope_blocked": "unsupported: y"}
    monkeypatch.setattr(daily_run, "product_route", lambda a: True)
    assert daily_run._groups_blocked(SimpleNamespace(), plan) == "unsupported: y"
    monkeypatch.setattr(daily_run, "product_route", lambda a: False)
    assert daily_run._groups_blocked(SimpleNamespace(), plan) == ""


def test_product_plan_passes_changed_files_only_on_product(tmp_path, monkeypatch):
    seen = []

    def fake(*args, **kwargs):
        seen.append(kwargs.get("changed_files"))
        return {"packages": [], "extra_reqs": [], "system": [], "lines": [], "python": {}}

    monkeypatch.setattr(demo_helper, "build_setup_plan", fake)
    monkeypatch.setattr(demo_helper, "project_install_docs", lambda d: {"sources": [], "text": ""})
    main = tmp_path / "main"
    main.mkdir()
    rec = {"pr": {"number": 1}, "files": {"all": ["app/components/two/x.py"]}}
    for product in (True, False):
        monkeypatch.setattr(daily_run, "product_route", lambda a, p=product: p)
        daily_run._product_plan(SimpleNamespace(python="3.12"), dict(rec), "acme/big-app", {}, [main],
                                pypi=lambda n: None)
    assert seen == [["app/components/two/x.py"], None]


# ---------------------------------------------------------------- review follow-ups
def test_manifest_direct_url_line_stops_the_check(tmp_path):
    bad = {**COMPONENTS, "two": ["evil @ https://x.invalid/e.whl"]}
    main = _app(tmp_path / "main", manifests=bad)
    plan = _plan(main, _app(tmp_path / "pr"), ["app/components/two/sensor.py"])
    assert plan["scope_blocked"].startswith("unsupported:") and "x.invalid" in plan["scope_blocked"]
    assert not any("x.invalid" in r for r in plan["extra_reqs"]) and plan["component"] is None


def test_core_off_index_line_stops_the_check(tmp_path):
    main = _app(tmp_path / "main")
    (main / "requirements.txt").write_text("core-lib==1.0\ngit+https://x.invalid/r.git#egg=r\n")
    plan = _plan(main, _app(tmp_path / "pr"), ["app/components/two/sensor.py"])
    assert plan["scope_blocked"].startswith("unsupported:") and "requirements.txt" in plan["scope_blocked"]
    (main / "requirements.txt").write_text("core-lib==1.0\n--extra-index-url https://x.invalid/simple\n")
    assert _plan(main, main, ["app/components/two/x.py"])["scope_blocked"].startswith("unsupported:")


def test_deps_only_plan_excludes_aggregate_files(tmp_path):
    main = _app(tmp_path / "main")
    plan = _plan(main, main, ["app/components/two/x.py"])
    names = plan["aggregate_names"]
    assert set(names) == {"requirements_all.txt", "requirements_test_all.txt"}
    got = demo_helper.deps_only_plan(main, exclude=names)
    assert got["files"] == ["requirements.txt", "requirements_test.txt"]
    assert "requirements_all.txt" in demo_helper.deps_only_plan(main)["files"]   # default unchanged


def test_daily_run_flat_and_contree_paths_get_aggregate_names(tmp_path, monkeypatch):
    rec = {"demo_helper": {"setup_plan": {"aggregate_names": ["requirements_all.txt"]}}}
    assert daily_run._aggregate_names(rec) == ["requirements_all.txt"]
    assert daily_run._aggregate_names({}) == []
    from poc import contree_sandboxes
    shell = contree_sandboxes.install_shell_source("acme/big-app", "abc", deps_only_fallback=True,
                                                   deps_exclude=["requirements_all.txt", "requirements_test_all.txt"])
    assert 'case "$f" in requirements_all.txt|requirements_test_all.txt) continue;; esac;' in shell
    assert contree_sandboxes.deps_only_shell() == contree_sandboxes.DEPS_ONLY_SHELL
    assert "case" not in contree_sandboxes.DEPS_ONLY_SHELL
    weird = contree_sandboxes.deps_only_shell(["requirements_$(x).txt"])
    assert "'requirements_$(x).txt')" in weird


def test_contree_fallback_shell_skips_aggregate_when_run(tmp_path):
    import subprocess

    from poc import contree_sandboxes
    for name in ("requirements.txt", "requirements_all.txt"):
        (tmp_path / name).write_text("")
    body = contree_sandboxes.deps_only_shell(["requirements_all.txt"])
    loop = body[body.index("for f in"):body.index("done;") + 5]
    script = loop.replace("python -m pip install -q -r", "echo")
    out = subprocess.run(["sh", "-c", script], cwd=tmp_path, capture_output=True, text=True).stdout.split()
    assert out == ["requirements.txt"]


def test_dotdot_path_is_refused(tmp_path):
    comps = demo_helper.component_dirs(_app(tmp_path / "m"))
    assert demo_helper.component_for_changes(["app/components/two/../one/x.py"], comps) is None
    assert demo_helper.component_for_changes(["tests/components/two/../../../app/core.py"], comps) is None


def test_same_named_folder_elsewhere_does_not_count(tmp_path):
    comps = demo_helper.component_dirs(_app(tmp_path / "m"))
    assert demo_helper.component_for_changes(["docs/two/page.md"], comps) is None
    assert demo_helper.component_for_changes(["tests/two/test_x.py"], comps) == "app/components/two"
    assert demo_helper.component_for_changes(["tests/components/two/test_x.py"], comps) == "app/components/two"


def test_symlinked_manifest_is_not_a_component(tmp_path):
    root = _app(tmp_path / "m")
    other = tmp_path / "elsewhere.json"
    other.write_text(json.dumps({"requirements": ["x==1"]}))
    d = root / "app" / "components" / "four"
    d.mkdir()
    (d / "manifest.json").symlink_to(other)
    assert "app/components/four" not in demo_helper.component_dirs(root)


def test_small_plugin_project_is_not_flagged(tmp_path):
    root = tmp_path / "small"
    root.mkdir()
    (root / "requirements.txt").write_text("lib-one==1.0\nlib-two==2.0\n")
    for name, reqs in (("one", ["lib-one==1.0"]), ("two", ["lib-two==2.0"])):
        d = root / "plugins" / name
        d.mkdir(parents=True)
        (d / "manifest.json").write_text(json.dumps({"requirements": reqs}))
    comps = demo_helper.component_dirs(root)
    assert demo_helper.aggregate_requirement_files(root, comps) == []        # only 2 components
    (root / "plugins" / "three").mkdir()
    (root / "plugins" / "three" / "manifest.json").write_text(json.dumps({"requirements": []}))
    comps = demo_helper.component_dirs(root)
    assert demo_helper.aggregate_requirement_files(root, comps) == []        # its only requirements file
    plan = _plan(root, root, ["plugins/one/x.py"])
    assert set(plan["extra_reqs"]) == {"lib-one==1.0", "lib-two==2.0"} and plan["scope_blocked"] == ""


def test_lint_only_requirement_file_is_skipped_from_content(tmp_path):
    main = _app(tmp_path / "main")
    (main / ".pre-commit-config.yaml").write_text(
        "repos:\n  - repo: https://github.com/example/lint-tool-pre-commit\n    hooks: [{id: lint-tool}]\n"
        "  - repo: https://github.com/example/spell_checker\n")
    (main / "requirements_lint_pins.txt").write_text("lint-tool==1.0\nspell-checker==2.0\n")
    (main / "requirements_other.txt").write_text("lint-tool==1.0\nreal-lib==1.0\n")    # not lint-only
    plan = _plan(main, main, ["app/components/two/x.py"])
    assert "lint-tool==1.0" in plan["extra_reqs"]          # still pulled in by requirements_other.txt
    assert "spell-checker==2.0" not in plan["extra_reqs"] and "real-lib==1.0" in plan["extra_reqs"]
    names = [p.name for p in demo_helper.lint_only_requirement_files(main)]
    assert names == ["requirements_lint_pins.txt"]
    (main / ".pre-commit-config.yaml").unlink()
    assert demo_helper.lint_only_requirement_files(main) == []


def test_constraint_file_not_named_requirements_is_checked(tmp_path):
    main = _app(tmp_path / "main")
    (main / "app" / "constraints.txt").write_text("pinned==1.0\nevil @ https://x.invalid/e.whl\n")
    (main / "requirements.txt").write_text("-c app/constraints.txt\ncore-lib==1.0\n")
    plan = _plan(main, main, ["app/components/two/x.py"])
    assert plan["scope_blocked"].startswith("unsupported:") and "app/constraints.txt" in plan["scope_blocked"]
    assert plan["component"] is None and "lib-two==2.0" not in plan["extra_reqs"]


def test_included_lint_only_file_is_still_checked(tmp_path):
    main = _app(tmp_path / "main")
    (main / ".pre-commit-config.yaml").write_text("repos:\n  - repo: https://github.com/example/lint-tool\n")
    (main / "requirements_lint_pins.txt").write_text("lint-tool==1.0\n")
    assert [p.name for p in demo_helper.lint_only_requirement_files(main)] == ["requirements_lint_pins.txt"]
    assert _plan(main, main, ["app/components/two/x.py"])["scope_blocked"] == ""
    (main / "requirements_lint_pins.txt").write_text("lint-tool @ https://x.invalid/lint.whl\n")
    assert [p.name for p in demo_helper.lint_only_requirement_files(main)] == ["requirements_lint_pins.txt"]
    (main / "requirements_test.txt").write_text("-r requirements.txt\n-r requirements_lint_pins.txt\ntest-lib==1.0\n")
    plan = _plan(main, main, ["app/components/two/x.py"])
    assert plan["scope_blocked"].startswith("unsupported:") and "requirements_lint_pins.txt" in plan["scope_blocked"]


def test_include_outside_the_project_is_refused(tmp_path):
    outside = tmp_path / "outside.txt"
    outside.write_text("fine==1.0\n")
    for include in ("-r ../outside.txt", "-c sub/../requirements.txt", "-r link.txt"):
        main = _app(tmp_path / f"m{abs(hash(include))}")
        (main / "link.txt").symlink_to(outside)
        (main / "requirements.txt").write_text(f"{include}\ncore-lib==1.0\n")
        plan = _plan(main, main, ["app/components/two/x.py"])
        assert plan["scope_blocked"].startswith("unsupported:"), include


def test_include_cycle_terminates(tmp_path):
    main = _app(tmp_path / "main")
    (main / "requirements.txt").write_text("-r requirements_test.txt\ncore-lib==1.0\n")
    assert _plan(main, main, ["app/components/two/x.py"])["scope_blocked"] == ""
