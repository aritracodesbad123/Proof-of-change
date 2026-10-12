"""Benchmark mode (ops/bench.py, ops/daily_run.py --bench): inputs parsing, SHA choice, answer-key refusal, checkout of
a merge commit's two sides, one result JSON per case. Uses synthetic inputs and a local git repo (no network)."""
import builtins
import io
import json
import subprocess
from pathlib import Path

import pytest

from guardrails import sandbox
from ops import bench
from ops import daily_run as dr

ROOT = Path(__file__).resolve().parent.parent
SYN = ROOT / "tests" / "fixtures" / "bench" / "inputs-synthetic.csv"
V0 = ROOT / "bench" / "benchmark-v0.csv"


@pytest.fixture(autouse=True)
def restore_sandbox():
    was = sandbox.enabled()
    yield
    sandbox.configure(was)    # dr.main(--unsafe-no-sandbox) switches it off for the process


def test_parses_inputs_and_picks_the_right_shas():
    rows = bench.select(bench.read_inputs(SYN), "B02,B01")
    assert [r["id"] for r in rows] == ["B02", "B01"]
    assert bench.sides(rows[1]) == {"main": "1" * 40, "pr": "2" * 40}
    assert bench.sides(rows[0]) == {"main": "4" * 40, "pr": "5" * 40}


def test_vendored_v0_inputs():
    rows = bench.read_inputs(V0)
    assert len(rows) == 19 and [r["id"] for r in rows][:1] == ["B01"] and rows[-1]["id"] == "B19"
    b01, b14 = bench.select(rows, ["B01", "B14"])
    assert (b01["repo"], b01["pr"]) == ("psf/requests", "6655")
    assert bench.sides(b01) == {"main": "eea3bbf9ac635f465ee6c9903dc57c677952dafd",
                                "pr": "a58d7f2ffb4d00b46dca2d70a3932a0b37e22fac"}
    assert b14["repo"] == "marshmallow-code/marshmallow"
    assert not set(bench.ANSWER_COLUMNS) & set(rows[0])


def test_any_case_id_format_and_any_answers_name(tmp_path):
    p = tmp_path / "pairs.csv"
    p.write_text(SYN.read_text().replace("B01,", "R-numpy-2.3,", 1))
    assert bench.read_inputs(p)[0]["id"] == "R-numpy-2.3"
    for name in ("release-answers.csv", "my_answers_v2.csv"):
        with pytest.raises(bench.AnswerKeyRefused):
            bench.guard_path(tmp_path / name)


def test_unknown_id_is_an_error():
    with pytest.raises(bench.BenchInputError, match="B99"):
        bench.select(bench.read_inputs(SYN), "B01,B99")


def test_refuses_files_named_answers(tmp_path):
    p = tmp_path / "benchmark-v0-answers.csv"
    p.write_text(SYN.read_text())          # even with valid inputs content
    with pytest.raises(bench.AnswerKeyRefused):
        bench.read_inputs(p)
    link = tmp_path / "inputs.csv"
    link.symlink_to(p)                     # and through an innocent-looking symlink
    with pytest.raises(bench.AnswerKeyRefused):
        bench.read_inputs(link)
    up = tmp_path / "ANSWERS.csv"
    up.write_text(SYN.read_text())
    with pytest.raises(bench.AnswerKeyRefused):
        bench.read_inputs(up)


def test_refuses_inputs_with_answer_columns(tmp_path):
    p = tmp_path / "mixed.csv"
    lines = SYN.read_text().splitlines()
    p.write_text(lines[0] + ",label\n" + "\n".join(ln + ",regression" for ln in lines[1:]) + "\n")
    with pytest.raises(bench.AnswerKeyRefused, match="label"):
        bench.read_inputs(p)


@pytest.mark.parametrize("bad,match", [("1111111111111111111111111111111111111111", None), ("abc", "full commit SHA")])
def test_rejects_short_shas(tmp_path, bad, match):
    p = tmp_path / "in.csv"
    p.write_text(SYN.read_text().replace("1111111111111111111111111111111111111111", bad, 1))
    if match:
        with pytest.raises(bench.BenchInputError, match=match):
            bench.read_inputs(p)
    else:
        assert bench.read_inputs(p)


def test_cli_refuses_answers_file(tmp_path, capsys):
    p = tmp_path / "x-answers.csv"
    p.write_text(SYN.read_text())
    assert dr.main(["--bench", str(p), "--ids", "B01", "--unsafe-no-sandbox"]) == 2
    assert "never read an answer key" in capsys.readouterr().err


def test_package_path_and_result_name():
    assert bench.package_path({"shipped_source_files": "src/requests/adapters.py;tox.ini", "repo": "psf/requests"}) \
        == "src/requests"
    assert bench.package_path({"shipped_source_files": "widgets/table.py", "repo": "o/widgets"}) == "widgets"
    assert bench.package_path({"shipped_source_files": "", "repo": "o/my-lib"}) == "my_lib"
    assert bench.result_name("B01", None) == "B01-full.json"
    assert bench.result_name("B01", "tests+diff") == "B01-tests_diff.json"


# ---------------------------------------------------------------- local git repo with a merge commit
def git(cwd, *args):
    return subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True, check=True).stdout.strip()


@pytest.fixture
def merged_repo(tmp_path):
    """A repo whose main has a merge commit: first parent = base, merge = base + a change to widgets/core.py."""
    r = tmp_path / "upstream"
    (r / "widgets").mkdir(parents=True)
    git(tmp_path, "init", "-q", "-b", "main", str(r))
    git(r, "config", "user.email", "t@example.com")
    git(r, "config", "user.name", "t")
    git(r, "config", "uploadpack.allowAnySHA1InWant", "true")
    (r / "widgets" / "__init__.py").write_text("")
    (r / "widgets" / "core.py").write_text("def f():\n    return 1\n")
    git(r, "add", "-A")
    git(r, "commit", "-q", "-m", "base")
    base = git(r, "rev-parse", "HEAD")
    git(r, "checkout", "-q", "-b", "feature")
    (r / "widgets" / "core.py").write_text("def f():\n    return 2\n")
    git(r, "commit", "-q", "-am", "change")
    git(r, "checkout", "-q", "main")
    (r / "README").write_text("x\n")
    git(r, "add", "-A")
    git(r, "commit", "-q", "-m", "other")
    first_parent = git(r, "rev-parse", "HEAD")
    git(r, "merge", "-q", "--no-ff", "-m", "Merge feature", "feature")
    merge = git(r, "rev-parse", "HEAD")
    return {"path": r, "base": base, "first_parent": first_parent, "merge": merge}


def row_for(m, first_parent=None):
    return {"id": "B01", "repo": "example-org/widgets", "pr": "4100", "pr_url": "https://github.com/example-org/widgets/pull/4100",
            "pr_title": "Change f", "merged_at_ist": "", "main_sha_merge_first_parent": first_parent or m["first_parent"],
            "pr_side_sha_merge_commit": m["merge"], "pr_head_sha": "", "shipped_source_files": "widgets/core.py"}


def test_checkout_builds_main_from_first_parent_and_pr_from_merge(tmp_path, merged_repo, monkeypatch):
    monkeypatch.setattr(bench, "CLONE_URL", str(merged_repo["path"]))
    work = tmp_path / "work"
    work.mkdir()
    co = bench.checkout(dr, row_for(merged_repo), work, tmp_path / "git.log")
    assert co["ok"], co
    assert git(work / "side-main", "rev-parse", "HEAD") == merged_repo["first_parent"]
    assert git(work / "side-pr", "rev-parse", "HEAD") == merged_repo["merge"]
    assert (work / "side-main" / "widgets" / "core.py").read_text().endswith("return 1\n")
    assert (work / "side-pr" / "widgets" / "core.py").read_text().endswith("return 2\n")
    assert co["files"] == ["widgets/core.py"] and co["first_parent_verified"]
    assert dr.source_pair("example-org/widgets", {"bench_sides": co}, work, tmp_path / "x.log", "3.12", 1) is co


def test_checkout_refuses_inconsistent_first_parent(tmp_path, merged_repo, monkeypatch):
    monkeypatch.setattr(bench, "CLONE_URL", str(merged_repo["path"]))
    work = tmp_path / "work"
    work.mkdir()
    co = bench.checkout(dr, row_for(merged_repo, first_parent=merged_repo["base"]), work, tmp_path / "git.log")
    assert not co["ok"] and "inconsistent" in co["why"]


def test_run_writes_one_result_per_id_and_never_opens_the_answer_key(tmp_path, merged_repo, monkeypatch):
    inputs = tmp_path / "inputs.csv"
    rows = [row_for(merged_repo), dict(row_for(merged_repo), id="B02", pr="4101")]
    cols = list(rows[0])
    inputs.write_text(",".join(cols) + "\n" + "\n".join(",".join(r[c] for c in cols) for r in rows) + "\n")
    (tmp_path / "benchmark-v0-answers.csv").write_text("id,label\nB01,regression\n")
    monkeypatch.setattr(bench, "CLONE_URL", str(merged_repo["path"]))
    monkeypatch.setattr(bench, "pr_text", lambda _dr, row: {"title": row["pr_title"], "body": "Changes f.",
                                                             "author": "someone", "base_ref": "main", "source": "test"})
    seen = []

    def fake_pair(repo, cfg, item, prdir, work, a, rec):
        sp = dr.source_pair(repo, item, work, prdir / "git.log", a.python, 1)
        seen.append((sp["main_sha"], sp["pr_sha"], item["files"]["package_py"], cfg["pkg"]))
        rec.update(verdict="verified", reason="stub")
        return rec
    monkeypatch.setattr(dr, "test_source_pair", fake_pair)
    real_open, real_io_open = builtins.open, io.open

    def guarded(f, *a, **k):
        if "answers" in str(f):
            raise AssertionError(f"answer key opened: {f}")
        return real_open(f, *a, **k)
    monkeypatch.setattr(builtins, "open", guarded)
    monkeypatch.setattr(io, "open", guarded)
    out = tmp_path / "bench-v0"
    rc = dr.main(["--bench", str(inputs), "--ids", "B01,B02", "--bench-out", str(out), "--unsafe-no-sandbox",
                  "--work-dir", str(tmp_path / "w"), "--python", "3"])
    monkeypatch.setattr(builtins, "open", real_open)
    monkeypatch.setattr(io, "open", real_io_open)
    assert rc == 0
    files = sorted(p.name for p in out.glob("*.json"))
    assert files == ["B01-full.json", "B02-full.json"]
    res = json.loads((out / "B01-full.json").read_text())
    assert res["bench"]["id"] == "B01" and res["bench"]["answer_key_read"] is False
    assert res["bench"]["first_parent_verified"] and res["pr"]["merge_commit"] == merged_repo["merge"]
    assert res["verdict"] == "verified" and res["tested"]["main"].startswith("first parent of the merge commit")
    assert seen[0] == (merged_repo["first_parent"], merged_repo["merge"], ["widgets/core.py"], "widgets")
    assert (out / "logs" / "B01-full" / "record.json").exists()
