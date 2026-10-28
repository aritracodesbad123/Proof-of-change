"""Fix 51: every run is findable under ops/runs/<date>/."""
import datetime as dt
import json

from ops import daily_run as dr

T = dt.datetime(2026, 10, 28, 12, 5, 0)


def test_run_elsewhere_leaves_one_pointer(tmp_path):
    index, rdir = tmp_path / "runs", tmp_path / "elsewhere" / "runs" / "adhoc-click"
    rdir.mkdir(parents=True)
    dest = dr.leave_run_pointer(rdir, T, index)
    assert dest == index / "2026-10-28" / "RUN_POINTERS.jsonl"
    dr.leave_run_pointer(rdir, T, index)  # idempotent
    lines = [json.loads(x) for x in dest.read_text().splitlines()]
    assert lines == [{"run_dir": str(rdir.resolve()), "started_ist": "2026-10-28 12:05:00"}]


def test_dated_run_in_the_index_needs_no_pointer(tmp_path):
    index = tmp_path / "runs"
    for name in ("2026-10-28", "2026-10-28-check-120500-pr1"):
        assert dr.leave_run_pointer(index / name, T, index) is None
    assert not (index / "2026-10-28" / "RUN_POINTERS.jsonl").exists()


def test_undated_name_in_the_index_gets_a_pointer(tmp_path):
    index = tmp_path / "runs"
    assert dr.leave_run_pointer(index / "adhoc-isort", T, index) == index / "2026-10-28" / "RUN_POINTERS.jsonl"


def test_pointer_failure_never_fails_the_run(tmp_path):
    index = tmp_path / "file"
    index.write_text("not a folder")
    assert dr.leave_run_pointer(tmp_path / "x", T, index) is None
