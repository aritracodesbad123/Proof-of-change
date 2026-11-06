"""Real chosen-PR headings: `owner/name #N: title` and `owner/name PR #N`, with head and base SHAs from the section."""
from pathlib import Path

import pytest

from ops import daily_run

FIX = Path(__file__).parent / "fixtures" / "chosen"


@pytest.mark.parametrize("name,expected", [
    ("chosen-2026-11-04.md", {
        "psf/requests": (7413, "418c76b8aa7be2255ecd2d045f761e6411ba0acb", "04d750509b90da728e53aee8d7516426e5a1a293"),
        "Textualize/rich": (3163, None, "50d2a457c8ea273c14a0053b00493473b86dbe21"),
        "python-attrs/attrs": (1641, None, "644b4e165bfbeee7e127de6fcbda08b64014316f")}),
    ("chosen-2026-11-05.md", {
        "PyCQA/isort": (2781, None, "841e43126cd2ca74751b421afd00d90ca36932e5"),
        "mahmoud/boltons": (732, None, "d31d821d56c8f7756af9c30a864077f2e5855321"),
        "encode/httpx": (3741, None, "b5addb64f0161ff6bfe94c124ef76f6a1fba5254")}),
    ("chosen-2026-11-06.md", {
        "Delgan/loguru": (1515, "6c91de2c42d38e010a68d9618dc6aa4ba01e1372", "0412a60d6aff63a4ed009c7445993b42d294c2f1"),
        "andialbrecht/sqlparse": (944, "51894597437c480e268c67439a0208772be6f5d0",
                                  "09dbe1eec31ed1b3cd05366748865f11ba427d32"),
        "pyinvoke/invoke": (1097, "f887e02c1959ab9add3428ae3ab740c71cd41938",
                            "0da941e176f4e0b28d8a69b8ac089cdbac2874e4")}),
])
def test_real_chosen_files(name, expected):
    chosen = daily_run.parse_chosen(FIX / name)
    assert set(chosen) == set(expected)
    for repo, (pr, head, base) in expected.items():
        [row] = chosen[repo]
        assert row["pr"] == pr
        if head:
            assert row["head_sha"] == head
        assert row["base_sha"] == base


@pytest.mark.parametrize("heading", ["acme/widget #12", "acme/widget PR #12", "acme/widget pr #12: title",
                                     "acme/widget pull request #12", "acme/widget #12: a title"])
def test_both_heading_forms(tmp_path, heading):
    p = tmp_path / "d.md"
    p.write_text(f"## 1. {heading}\n- Head: {'a' * 40}\n- Base: {'b' * 40}\n")
    [row] = daily_run.parse_chosen(p)["acme/widget"]
    assert (row["pr"], row["head_sha"], row["base_sha"]) == (12, "a" * 40, "b" * 40)


def test_head_sha_backtick_form_still_read(tmp_path):
    p = tmp_path / "d.md"
    p.write_text(f"## 1. acme/widget #3\nHead SHA: `{'c' * 40}`\n")
    [row] = daily_run.parse_chosen(p)["acme/widget"]
    assert row["head_sha"] == "c" * 40 and row["base_sha"] is None
