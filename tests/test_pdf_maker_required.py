"""A product check refuses to start, with a plain line, when the built-in PDF maker (reportlab) can't be imported."""
from __future__ import annotations

import tomllib
import types
from pathlib import Path

from ops import daily_run


def args(**kw):
    base = dict(pr=["https://github.com/o/r/pull/1"], product_check=True, bench=False, select_only=False,
                report_only=False, no_report=False)
    base.update(kw)
    return types.SimpleNamespace(**base)


def missing(name):
    raise ModuleNotFoundError(f"No module named '{name}'")


def test_missing_reportlab_refuses():
    line = daily_run.pdf_maker_start_refusal(args(), importer=missing)
    assert line and line.startswith("refusing:") and "reportlab" in line


def test_present_reportlab_starts():
    assert daily_run.pdf_maker_start_refusal(args(), importer=lambda n: object()) is None


def test_not_product_or_no_report_not_refused():
    assert daily_run.pdf_maker_start_refusal(args(product_check=False, pr=None), importer=missing) is None
    assert daily_run.pdf_maker_start_refusal(args(no_report=True), importer=missing) is None


def test_reportlab_is_a_declared_dependency():
    deps = tomllib.loads((Path(__file__).resolve().parents[1] / "pyproject.toml").read_text())["project"]["dependencies"]
    assert any(d.split("=")[0].split(">")[0].strip().lower() == "reportlab" for d in deps)
