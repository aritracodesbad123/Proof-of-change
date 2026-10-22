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
