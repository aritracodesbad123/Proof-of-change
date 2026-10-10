"""Release notes scoped to one version (poc/release_notes.py), on a saved copy of scikit-learn's whats_new/v1.5.html."""
import re
from pathlib import Path

import pytest

from poc import release_notes as rn

PAGE = (Path(__file__).parent / "fixtures" / "release_notes" / "sklearn-whats_new-v1.5.html").read_text()
SCOPE_150 = "ONLY the section id=version-1-5-0; the same page also lists later patch releases, which are " \
            "scorer-only answers and must be stripped"


def sentences(text):
    return {s for s in (" ".join(x.split()) for x in re.split(r"[.\n]", text)) if len(s) > 40}


def test_keeps_only_the_1_5_0_section():
    t = rn.trim(PAGE, SCOPE_150)
    assert t.startswith("Version 1.5.0")
    assert "May 2024" in t and len(t) > 5000
    later = rn.trim(PAGE, "ONLY the section id=version-1-5-1") + rn.trim(PAGE, "ONLY the section id=version-1-5-2")
    assert later.strip()
    leaked = sentences(later) & sentences(t)
    assert not leaked, sorted(leaked)[:3]
    assert "Version 1.5.1" not in t and "Version 1.5.2" not in t
    assert "1.5.1" not in t and "1.5.2" not in t        # not even a stray mention or a sidebar link


def test_the_page_really_has_the_later_sections():
    whole = rn.trim(PAGE, "whole page (single-version page)")
    assert "Version 1.5.1" in whole and "Version 1.5.2" in whole and "Version 1.5.0" in whole


def test_scope_parsing():
    assert rn.parse_scope(SCOPE_150) == {"kind": "section", "id": "version-1-5-0"}
    assert rn.parse_scope("whole page (single-version page)") == {"kind": "page"}
    with pytest.raises(rn.ScopeError):
        rn.parse_scope("the good bits")
    with pytest.raises(rn.ScopeError, match="not found"):
        rn.trim(PAGE, "ONLY the section id=version-9-9-9")


def test_nested_other_version_sections_are_dropped():
    html = ("<main><section id='version-2-0-0'><h2>Version 2.0.0</h2><p>Kept.</p>"
            "<section id='version-2-0-1'><h2>Version 2.0.1</h2><p>Later fix.</p></section>"
            "<p>Also kept.</p></section><nav>Version 2.0.1 link</nav></main>")
    t = rn.trim(html, "ONLY the section id=version-2-0-0")
    assert "Kept." in t and "Also kept." in t and "2.0.1" not in t


def test_read_pairs_refuses_answer_files(tmp_path):
    p = tmp_path / "release-answers.csv"
    p.write_text("pair_id,notes_scope\nRP01,whole page\n")
    with pytest.raises(PermissionError):
        rn.read_pairs(p)
    q = tmp_path / "release-pairs.csv"
    q.write_text("pair_id,library,notes_scope\nRP03,scikit-learn,\"ONLY the section id=version-1-5-0; x\"\n")
    assert rn.parse_scope(rn.read_pairs(q)[0]["notes_scope"])["id"] == "version-1-5-0"
