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


def _no_reportlab(monkeypatch):
    from poc import pdf_maker
    real = pdf_maker.importlib.import_module
    monkeypatch.setattr(pdf_maker.importlib, "import_module",
                        lambda n: missing(n) if n == "reportlab" else real(n))


def test_console_refuses_to_start_without_reportlab(monkeypatch, capsys):
    from poc import console_api
    _no_reportlab(monkeypatch)
    monkeypatch.setattr(console_api, "serve", lambda *a, **k: (_ for _ in ()).throw(AssertionError("served")))
    assert console_api.main(["--port", "0"]) == 1
    assert "reportlab" in capsys.readouterr().err


def test_github_app_refuses_to_start_without_reportlab(monkeypatch, capsys):
    from poc import github_app
    _no_reportlab(monkeypatch)
    monkeypatch.setattr(github_app, "serve", lambda *a, **k: (_ for _ in ()).throw(AssertionError("served")))
    assert github_app.main(["--port", "0"]) == 1
    assert "reportlab" in capsys.readouterr().err


def test_one_shared_refusal_line():
    from poc import pdf_maker
    assert daily_run.pdf_maker_start_refusal(args(), importer=missing) == pdf_maker.REFUSAL
    assert pdf_maker.missing_refusal(lambda n: object()) is None
