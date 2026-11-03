"""A dotted test id maps to the longest prefix that is a real .py file.

``tests.x.TestCls::t`` used to become ``tests/x/TestCls.py``, so it never matched the edited file ``tests/x.py``.
The class, nested class, function and parameter id stay after the module path.
"""
from ops.daily_run import _edited_test_file, resolve_test_id


def _with_module(tmp_path):
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "x.py").write_text("class TestCls:\n    pass\n")
    return tmp_path


def test_class_id_maps_to_the_module_file(tmp_path):
    root = _with_module(tmp_path)
    assert resolve_test_id("tests.x.TestCls::t", root=root) == "tests/x.py::TestCls::t"


def test_nested_class_id_maps_to_the_module_file(tmp_path):
    root = _with_module(tmp_path)
    assert resolve_test_id("tests.x.Outer.Inner::t", root=root) == "tests/x.py::Outer::Inner::t"


def test_plain_function_id_maps_to_the_module_file(tmp_path):
    root = _with_module(tmp_path)
    assert resolve_test_id("tests.x::test_fn", root=root) == "tests/x.py::test_fn"


def test_parametrised_id_keeps_the_parameter(tmp_path):
    root = _with_module(tmp_path)
    assert resolve_test_id("tests.x.TestCls::t[a.b]", root=root) == "tests/x.py::TestCls::t[a.b]"


def test_the_longest_real_py_file_is_the_module(tmp_path):
    """A file named TestCls.py is a module, not a class inside tests/x.py."""
    nested = tmp_path / "tests" / "x"
    nested.mkdir(parents=True)
    (tmp_path / "tests" / "x.py").write_text("class TestCls:\n    pass\n")
    (nested / "TestCls.py").write_text("# module\n")
    assert resolve_test_id("tests.x.TestCls::t", root=tmp_path) == "tests/x/TestCls.py::t"


def test_a_package_init_is_the_module_when_no_py_file_sits_beside_it(tmp_path):
    package = tmp_path / "tests" / "x"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("class TestCls:\n    pass\n")
    assert resolve_test_id("tests.x.TestCls::t", root=tmp_path) == "tests/x/__init__.py::TestCls::t"


def test_without_a_real_file_the_dotted_name_stays_a_path(tmp_path):
    assert resolve_test_id("tests.x.TestCls::t", root=tmp_path) == "tests/x/TestCls.py::t"


def test_an_edited_path_counts_when_the_checkout_is_not_mounted():
    assert resolve_test_id("tests.x.TestCls::t", known=["tests/x.py"]) == "tests/x.py::TestCls::t"
    assert _edited_test_file("tests.x.TestCls::t", ["tests/x.py"]) == "tests/x.py"
    assert _edited_test_file("tests.x.Outer.Inner::t[a]", ["tests/x.py"]) == "tests/x.py"
    assert _edited_test_file("tests.test_x.TestCls::t", ["pkg/tests/test_x.py"]) == "pkg/tests/test_x.py"
