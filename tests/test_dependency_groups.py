"""PEP 735 dependency groups: read from main only, all groups, include-group followed, self extras expanded,
every line through the deps-only refusal rules, product checks only."""
from poc import demo_helper

PYPROJECT = '''
[project]
name = "Widget-Kit"
dependencies = ["numpy"]

[project.optional-dependencies]
gitlab = ["python-gitlab==8.6.0"]
web = ["requests>=2", "widget-kit[gitlab]"]
all = ["widget-kit[gitlab,web]"]
bad = ["thing @ git+https://example.org/thing.git"]

[dependency-groups]
integration = ["widget_kit[all]"]
loop-a = [{include-group = "loop-b"}, "alpha"]
loop-b = [{include-group = "loop-a"}, {include-group = "loop-b"}, "beta"]
dev = [{include-group = "integration"}, "pytest==9.1.1", "-e ./local", "./vendored", "x @ https://example.org/x.whl",
       "--index-url https://mirror.example.org/simple", "widget-kit[bad]"]
'''


def _root(tmp_path, text=PYPROJECT, name="main"):
    root = tmp_path / name
    root.mkdir()
    (root / "pyproject.toml").write_text(text)
    return root


def test_all_groups_read_includes_followed_self_extras_expanded(tmp_path):
    lines, refused, problems = demo_helper.dependency_group_reqs(_root(tmp_path), "widget-kit")
    assert "python-gitlab==8.6.0" in lines and "requests>=2" in lines
    assert {"alpha", "beta", "pytest==9.1.1"} <= set(lines)
    assert not any(demo_helper.norm(demo_helper.req_name(x)) == "widget-kit" for x in lines)
    assert len(lines) == len(set(lines))
    names = " ".join(r["name"] for r in refused)
    for bad in ("-e ./local", "./vendored", "example.org/x.whl", "--index-url", "git+https://example.org"):
        assert bad in names
    assert not any(demo_helper._refused_line(x) for x in lines)
    assert problems == []


def test_self_name_from_project_table_when_no_dist_given(tmp_path):
    lines, _, _ = demo_helper.dependency_group_reqs(_root(tmp_path), "")
    assert "python-gitlab==8.6.0" in lines


def test_no_groups(tmp_path):
    assert demo_helper.dependency_group_reqs(_root(tmp_path, '[project]\nname="w"\n'), "w") == ([], [], [])


def _problems(tmp_path, groups, name="g"):
    return demo_helper.dependency_group_reqs(_root(tmp_path, '[project]\nname="w"\n[dependency-groups]\n' + groups,
                                                   name), "w")[2]


def test_missing_include_group_is_a_problem_naming_it(tmp_path):
    problems = _problems(tmp_path, 'a = [{include-group = "nowhere"}, "ok"]\n')
    assert len(problems) == 1 and '"nowhere"' in problems[0]


def test_names_clashing_after_normalization_are_a_problem(tmp_path):
    problems = _problems(tmp_path, 'test-stuff = ["a"]\nTest_Stuff = ["b"]\n')
    assert len(problems) == 1 and "test-stuff" in problems[0] and "Test_Stuff" in problems[0]


def test_badly_shaped_entries_are_problems(tmp_path):
    assert _problems(tmp_path, 'a = [1, "ok"]\n', "num")
    assert _problems(tmp_path, 'a = [{other = "x"}, "ok"]\n', "tbl")
    assert _problems(tmp_path, 'a = [{include-group = 3}]\n', "inc")
    assert _problems(tmp_path, 'a = [{include-group = "b", extra = 1}]\nb = ["x"]\n', "more")
    assert _problems(tmp_path, 'a = "notalist"\n', "str")
    assert _problems(tmp_path, 'a = 1\n', "int")


def test_extra_referring_back_to_project_itself(tmp_path):
    text = ('[project]\nname = "pkg"\n[project.optional-dependencies]\ndev = ["d1"]\n'
            'all = ["pkg[dev]", "a1", "PKG[all]"]\n[dependency-groups]\nci = ["pkg[all]"]\n')
    lines, refused, problems = demo_helper.dependency_group_reqs(_root(tmp_path, text), "")
    assert sorted(lines) == ["a1", "d1"] and refused == [] and problems == []


def _plan(main, pr, docs):
    return demo_helper.build_setup_plan("acme/widget-kit", [main, pr], {"text": ""}, "3.12", "contree", "widget-kit",
                                        python_available=lambda v: None, pypi=lambda n: None,
                                        allow_lookup_packages=False, docs_checkouts=docs, apply_system=False)


CLEAN = PYPROJECT.split("dev = [")[0] + 'dev = [{include-group = "integration"}, "pytest==9.1.1"]\n'


def test_product_plan_installs_main_groups_only(tmp_path):
    main = _root(tmp_path, CLEAN)
    pr = _root(tmp_path, CLEAN.replace('"pytest==9.1.1"', '"pytest==9.1.1", "evil-from-pr"'), "pr")
    plan = _plan(main, pr, [main])
    assert "python-gitlab==8.6.0" in plan["extra_reqs"] and "evil-from-pr" not in plan["extra_reqs"]
    assert plan["groups_blocked"] == ""


def test_study_plan_does_not_install_groups(tmp_path):
    main = _root(tmp_path)
    plan = _plan(main, main, None)
    assert "python-gitlab==8.6.0" not in plan["extra_reqs"]


def test_refused_group_line_blocks_whole_product_plan(tmp_path):
    main = _root(tmp_path)
    plan = _plan(main, main, [main])
    assert plan["groups_blocked"].startswith("unsupported:") and "-e ./local" in plan["groups_blocked"]
    assert "pytest==9.1.1" not in plan["extra_reqs"] and "python-gitlab==8.6.0" not in plan["extra_reqs"]


def test_problem_blocks_product_plan_and_names_group(tmp_path):
    main = _root(tmp_path, '[project]\nname="w"\n[dependency-groups]\na = [{include-group = "gone"}, "ok"]\n')
    plan = _plan(main, main, [main])
    assert plan["groups_blocked"].startswith("unsupported:") and '"gone"' in plan["groups_blocked"]
    assert "ok" not in plan["extra_reqs"]


def test_clean_groups_do_not_block(tmp_path):
    main = _root(tmp_path, '[project]\nname="w"\n[dependency-groups]\na = ["ok"]\n')
    plan = _plan(main, main, [main])
    assert plan["groups_blocked"] == "" and "ok" in plan["extra_reqs"]


class _A:
    route = "product"
    python = "3.12"


def test_every_install_route_stops_on_blocked_groups(tmp_path, monkeypatch):
    from ops import daily_run
    monkeypatch.setattr(daily_run, "product_route", lambda a: True)
    plan = {"groups_blocked": "unsupported: x"}
    assert daily_run._groups_blocked(_A(), plan) == "unsupported: x"
    rec = {"demo_helper": {"setup_plan": plan}}
    ran = []
    monkeypatch.setattr(daily_run, "install_side", lambda *a, **k: ran.append(1) or (True, ""))
    ok, why = daily_run._install_with_helper(_A(), rec, "main install", tmp_path / "v", tmp_path, None,
                                             tmp_path / "l.log", 10, None, [])
    assert (ok, why) == (False, "unsupported: x") and ran == []
    monkeypatch.setattr(daily_run, "product_route", lambda a: False)
    assert daily_run._groups_blocked(_A(), plan) == ""
