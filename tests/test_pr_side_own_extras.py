"""The PR side installs its own declared extras, and main's freeze never overrides a pin the PR declares."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ops"))
import daily_run  # noqa: E402


def _side(root: Path, dev: list[str], deps=()) -> Path:
    root.mkdir(parents=True)
    body = ", ".join(f'"{r}"' for r in dev)
    dep = ", ".join(f'"{r}"' for r in deps)
    (root / "pyproject.toml").write_text(
        f'[project]\nname = "demo"\nversion = "1"\ndependencies = [{dep}]\n'
        f'[project.optional-dependencies]\ndev = [{body}]\n')
    return root


def _cons(tmp: Path, lines: list[str]) -> Path:
    p = tmp / "constraints.txt"
    p.write_text("\n".join(lines) + "\n")
    return p


def test_each_side_pins_a_tool_differently(tmp_path):
    main = _side(tmp_path / "main", ["toolx==2.0", "pytest>=7"])
    pr = _side(tmp_path / "pr", ["toolx==3.1", "pytest>=7"])
    cons = _cons(tmp_path, ["toolx==2.0", "pytest==8.0.0", "unrelated==1.2"])
    reqs, out = daily_run.pr_side_own_installs(["toolx==2.0", "pytest>=7", "fromlookup"], main, pr, cons, "demo")
    assert "toolx==3.1" in reqs and "toolx==2.0" not in reqs
    assert "fromlookup" in reqs
    text = out.read_text()
    assert "toolx" not in text and "pytest" not in text   # the PR declares both itself
    assert "unrelated==1.2" in text                      # everything else stays pinned to main


def test_pr_lowers_a_pin(tmp_path):
    main = _side(tmp_path / "main", ["twine==7.0.0 ; python_version>='3.11'", "build==1.6.1"])
    pr = _side(tmp_path / "pr", ["twine==6.2.0 ; python_version>='3.11'", "build==1.3.0"])
    cons = _cons(tmp_path, ["twine==7.0.0", "build==1.6.1", "packaging==25.0"])
    reqs, out = daily_run.pr_side_own_installs(
        ["twine==7.0.0 ; python_version>='3.11'", "build==1.6.1"], main, pr, cons, "demo")
    assert reqs == ["twine==6.2.0 ; python_version>='3.11'", "build==1.3.0"]
    assert out.read_text().split() == ["packaging==25.0"]


def test_same_pins_keep_the_same_install(tmp_path):
    main = _side(tmp_path / "main", ["toolx==2.0"])
    pr = _side(tmp_path / "pr", ["toolx==2.0"])
    reqs, out = daily_run.pr_side_own_installs(["toolx==2.0"], main, pr, None, "demo")
    assert reqs == ["toolx==2.0"] and out is None


def test_pr_drops_a_tool_from_its_extra(tmp_path):
    main = _side(tmp_path / "main", ["toolx==2.0", "tooly==1.0"])
    pr = _side(tmp_path / "pr", ["tooly==1.0"])
    reqs, _ = daily_run.pr_side_own_installs(["toolx==2.0", "tooly==1.0"], main, pr, None, "demo")
    assert reqs == ["tooly==1.0"]


def test_runtime_pin_declared_by_pr_is_not_constrained(tmp_path):
    main = _side(tmp_path / "main", [], deps=["libz==1.0"])
    pr = _side(tmp_path / "pr", [], deps=["libz==0.9"])
    cons = _cons(tmp_path, ["libz==1.0", "other==2"])
    _, out = daily_run.pr_side_own_installs(None, main, pr, cons, "demo")
    assert out.read_text().split() == ["other==2"]
