"""CI check: every saved sample/fixture report in the repo turns into a non-empty PDF with the built-in PDF maker
(the fallback that needs no browser), so a check can always deliver a PDF."""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from reports import reviewer

REPO = Path(__file__).resolve().parents[1]
SAMPLES = sorted(REPO / f for f in subprocess.run(["git", "-C", str(REPO), "ls-files", "*REPORT.html", "*SUMMARY.html"],
                                                   capture_output=True, text=True).stdout.split())


def test_samples_found():
    assert SAMPLES, "no saved REPORT.html/SUMMARY.html samples found"


@pytest.mark.parametrize("html", SAMPLES, ids=[str(p.relative_to(REPO)) for p in SAMPLES])
def test_sample_report_makes_a_pdf(html, tmp_path, monkeypatch):
    monkeypatch.setattr(reviewer, "find_chrome", lambda: None)  # exercise the browser-free maker every time
    out = tmp_path / "r.pdf"
    assert reviewer.to_pdf(str(html), str(out)) is None
    assert out.read_bytes().startswith(b"%PDF") and out.stat().st_size > 500
