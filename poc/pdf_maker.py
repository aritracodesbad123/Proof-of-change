"""One shared start-up check: the built-in PDF maker (reportlab) must be importable.

Chrome can hang or be missing; reportlab is the PDF fallback, so the daily runner's product checks, the hosted
console and the GitHub App all refuse to start without it rather than finishing a check with no PDF.
"""
from __future__ import annotations

import importlib
from typing import Callable

REFUSAL = ("refusing: a product check needs the built-in PDF maker (the reportlab package, listed in "
           "pyproject.toml) so the PDF never fails; install the project's dependencies and start again.")


def missing_refusal(importer: Callable[[str], object] | None = None) -> str | None:
    """The one plain refusal line when reportlab can't be imported, else None."""
    try:
        (importer or importlib.import_module)("reportlab")
    except Exception:  # noqa: BLE001
        return REFUSAL
    return None
