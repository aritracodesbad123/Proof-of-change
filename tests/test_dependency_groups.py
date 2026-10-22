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
    lines, refused = demo_helper.dependency_group_reqs(_root(tmp_path), "widget-kit")
    assert "python-gitlab==8.6.0" in lines and "requests>=2" in lines
    assert {"alpha", "beta", "pytest==9.1.1"} <= set(lines)
    assert not any(demo_helper.norm(demo_helper.req_name(x)) == "widget-kit" for x in lines)
    assert len(lines) == len(set(lines))
    names = " ".join(r["name"] for r in refused)
    for bad in ("-e ./local", "./vendored", "example.org/x.whl", "--index-url", "git+https://example.org"):
        assert bad in names
    assert not any(demo_helper._refused_line(x) for x in lines)


def test_self_name_from_project_table_when_no_dist_given(tmp_path):
    lines, _ = demo_helper.dependency_group_reqs(_root(tmp_path), "")
    assert "python-gitlab==8.6.0" in lines


def test_no_groups_or_bad_shapes(tmp_path):
    assert demo_helper.dependency_group_reqs(_root(tmp_path, '[project]\nname="w"\n'), "w") == ([], [])
    odd = '[project]\nname="w"\n[dependency-groups]\na = "notalist"\nb = [1, {include-group = 3}, "ok"]\n'
    assert demo_helper.dependency_group_reqs(_root(tmp_path, odd, "odd"), "w") == (["ok"], [])


def _plan(main, pr, docs):
    return demo_helper.build_setup_plan("acme/widget-kit", [main, pr], {"text": ""}, "3.12", "contree", "widget-kit",
                                        python_available=lambda v: None, pypi=lambda n: None,
                                        allow_lookup_packages=False, docs_checkouts=docs, apply_system=False)


def test_product_plan_installs_main_groups_only(tmp_path):
    main = _root(tmp_path)
    pr = _root(tmp_path, PYPROJECT.replace('"pytest==9.1.1"', '"pytest==9.1.1", "evil-from-pr"'), "pr")
    plan = _plan(main, pr, [main])
    assert "python-gitlab==8.6.0" in plan["extra_reqs"] and "evil-from-pr" not in plan["extra_reqs"]
    assert not any(demo_helper._refused_line(x) for x in plan["extra_reqs"])
    assert any("-e ./local" in r["name"] for r in plan["refused"])


def test_study_plan_does_not_install_groups(tmp_path):
    main = _root(tmp_path)
    plan = _plan(main, main, None)
    assert "python-gitlab==8.6.0" not in plan["extra_reqs"]
