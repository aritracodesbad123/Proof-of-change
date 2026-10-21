"""Write the benchmark case folders (cases/<ID>/before, after, claim.txt, recorded.json).

Each case holds only what a check is allowed to see: the code before and after the PR, the PR's claim, and the
recorded evidence a real run would have produced (per-run test outcomes, probe observations, install errors).
Expected verdicts live in answer_key.json, which only score.py reads. Re-run with: python -m evals.bench12.build_cases
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
CASES = HERE / "cases"

BASE_PKG = '''def add(a, b):
    return a + b


def clip(x, lo, hi):
    if x < lo:
        return lo
    return x


def mean(xs):
    return sum(xs) / len(xs)
'''
BASE_TESTS = '''from toypkg import add, clip, mean


def test_add():
    assert add(2, 3) == 5


def test_clip_low():
    assert clip(-1, 0, 10) == 0


def test_mean():
    assert mean([1, 2, 3]) == 2
'''
PKG = "toypkg/__init__.py"
TESTS = "tests/test_toypkg.py"
CLIP_FIX = BASE_PKG.replace("        return lo\n    return x", "        return lo\n    if x > hi:\n        return hi\n    return x")
T_CLIP_HIGH = "\n\ndef test_clip_high():\n    assert clip(11, 0, 10) == 10\n"
T_TIMING = "\n\ndef test_timing():\n    import random\n    assert random.random() < 0.5\n"
ADD_OFF = BASE_PKG.replace("    return a + b", "    return a + b + (1 if a == 0 else 0)")

CLIP_PROBE = {"main": [{"clip_high": 11}] * 3, "pr": [{"clip_high": 10}] * 3,
              "claims": [{"id": "C1", "expect": "differs", "covers": ["clip_high"]}],
              "changed_lines_total": 1, "changed_lines_covered": 1}
OLD = {"add": "PPP", "clip_low": "PPP", "mean": "PPP"}


def runs(extra: dict, both: dict | None = None) -> dict:
    """{test: [main, pr]} with the three base tests P x3 on both sides unless overridden."""
    out = {t: [v, v] for t, v in OLD.items()}
    out.update(extra)
    return out


def case(cid, claim, before, after, recorded):
    return cid, claim, before, after, recorded


C = [
    case("S01", "Fix clip so values above hi are clipped to hi.",
         {PKG: BASE_PKG, TESTS: BASE_TESTS}, {PKG: CLIP_FIX, TESTS: BASE_TESTS + T_CLIP_HIGH},
         {"runs": runs({"clip_high": ["---", "PPP"]}), "probe": CLIP_PROBE}),
    case("S01b", "Fix clip so values above hi are clipped to hi.",
         {PKG: BASE_PKG, TESTS: BASE_TESTS}, {PKG: CLIP_FIX, TESTS: BASE_TESTS + T_CLIP_HIGH},
         {"runs": runs({"clip_high": ["---", "PPP"]}), "probe": None}),
    case("S02", "Refactor add for readability; no behaviour change.",
         {PKG: BASE_PKG, TESTS: BASE_TESTS + "\n\ndef test_add_zero():\n    assert add(0, 4) == 4\n"},
         {PKG: ADD_OFF, TESTS: BASE_TESTS + "\n\ndef test_add_zero():\n    assert add(0, 4) == 4\n"},
         {"runs": runs({"add_zero": ["PPP", "FFF"]}), "probe": None}),
    case("S03", "Add the new helper dependency.",
         {PKG: BASE_PKG, "pyproject.toml": '[project]\nname = "toypkg"\nversion = "0.1"\ndependencies = []\n'},
         {PKG: BASE_PKG.replace("def mean(xs):\n", "def mean(xs):\n    # arithmetic mean\n"),
          "pyproject.toml": '[project]\nname = "toypkg"\nversion = "0.1"\ndependencies = ["toypkg-missing-dep==99.0"]\n'},
         {"install_error": "install failed: No matching distribution found for toypkg-missing-dep==99.0"}),
    case("S04", "Ship type information.", {},
         {"toypkg/py.typed": "", "toypkg/__init__.pyi":
          "def add(a: int, b: int) -> int: ...\ndef clip(x: float, lo: float, hi: float) -> float: ...\n"
          "def mean(xs: list[float]) -> float: ...\n"}, {}),
    case("S05", "Fix clip so values above hi are clipped to hi.",
         {PKG: BASE_PKG, TESTS: BASE_TESTS + T_TIMING}, {PKG: CLIP_FIX, TESTS: BASE_TESTS + T_TIMING + T_CLIP_HIGH},
         {"runs": runs({"timing": ["PFP", "FPP"], "clip_high": ["---", "PPP"]}), "probe": CLIP_PROBE}),
    case("S06", "Speed up mean.",
         {PKG: BASE_PKG, TESTS: BASE_TESTS + "\n\ndef test_mean_float():\n    assert mean([1, 2]) == 1.5\n"},
         {PKG: "import random\n\n\n" + BASE_PKG.replace("    return sum(xs) / len(xs)",
          "    return sum(xs) / len(xs) if random.random() > 0.4 else sum(xs) // len(xs)"),
          TESTS: BASE_TESTS + "\n\ndef test_mean_float():\n    assert mean([1, 2]) == 1.5\n"},
         {"runs": runs({"mean_float": ["PPP", "PFF"]}), "probe": None}),
    case("S07", "Speed up mean.",
         {PKG: BASE_PKG, TESTS: BASE_TESTS + "\n\ndef test_mean_float():\n    assert mean([1, 2]) == 1.5\n"},
         {PKG: "import random\n\n\n" + BASE_PKG.replace("    return sum(xs) / len(xs)",
          "    return sum(xs) / len(xs) if random.random() > 0.4 else sum(xs) // len(xs)"),
          TESTS: BASE_TESTS + "\n\ndef test_mean_float():\n    assert mean([1, 2]) == 1.5\n"},
         {"runs": runs({"mean_float": ["PPP", "PFE"]}), "probe": None}),
    case("S08", "Fix clip's top bound and fix mean on an empty list.",
         {PKG: BASE_PKG, TESTS: BASE_TESTS}, {PKG: CLIP_FIX, TESTS: BASE_TESTS + T_CLIP_HIGH},
         {"runs": runs({"clip_high": ["---", "PPP"]}),
          "probe": dict(CLIP_PROBE, claims=CLIP_PROBE["claims"] + [
              {"id": "C2", "expect": "differs", "covers": ["mean_empty"]}])}),
    case("S08b", "Refactor add; results are unchanged.",
         {PKG: BASE_PKG, TESTS: BASE_TESTS}, {PKG: ADD_OFF, TESTS: BASE_TESTS},
         {"runs": runs({}), "probe": {"main": [{"add_zero": 4}] * 3, "pr": [{"add_zero": 5}] * 3,
                                      "claims": [{"id": "C1", "expect": "same", "covers": ["add_zero"]}],
                                      "changed_lines_total": 1, "changed_lines_covered": 1}}),
    case("S09", "Fix clip so values above hi are clipped.",
         {PKG: BASE_PKG, TESTS: BASE_TESTS + T_CLIP_HIGH + "\n\ndef test_add_neg():\n    assert add(5, -2) == 3\n"},
         {PKG: CLIP_FIX.replace("    return a + b", "    return a + b if b >= 0 else a - b"),
          TESTS: BASE_TESTS + T_CLIP_HIGH + "\n\ndef test_add_neg():\n    assert add(5, -2) == 3\n"},
         {"runs": runs({"clip_high": ["FFF", "PPP"], "add_neg": ["PPP", "FFF"]}), "probe": CLIP_PROBE}),
    case("S10", "Handle zeros in mean.",
         {PKG: BASE_PKG, TESTS: BASE_TESTS + "\n\ndef test_mean_zero():\n    assert mean([0, 2]) == 1\n"},
         {PKG: BASE_PKG.replace("def mean(xs):\n", "def mean(xs):\n    while len(xs) > 0 and xs[0] == 0:\n        pass\n"),
          TESTS: BASE_TESTS + "\n\ndef test_mean_zero():\n    assert mean([0, 2]) == 1\n"},
         {"runs": runs({"mean_zero": ["PPP", "FFF"]}), "probe": None,
          "note": "PR runs of test_mean_zero failed by pytest-timeout (recorded as failed)"}),
    case("S10b", "Handle zeros in mean.",
         {PKG: BASE_PKG}, {PKG: BASE_PKG.replace("def mean(xs):\n", "def mean(xs):\n    # zeros handled\n")},
         {"install_error": "install timed out after 600s (whole process tree killed)"}),
    case("S12", "Fix a typo in the README.",
         {"README.md": "# toypkg\n\nA tiny pakage.\n"}, {"README.md": "# toypkg\n\nA tiny package.\n"},
         {"runs": runs({}), "probe": None}),
    case("S13", "Fix clip so values above hi are clipped to hi.",
         {PKG: BASE_PKG, TESTS: BASE_TESTS + T_TIMING}, {PKG: CLIP_FIX, TESTS: BASE_TESTS + T_TIMING + T_CLIP_HIGH},
         {"runs": runs({"timing": ["PFP", "PPP"], "clip_high": ["---", "PPP"]}), "probe": CLIP_PROBE}),
]
EXTRA = "import toyextra  # noqa: F401  (optional module, missing on the first run)\n\n\n"
for cid, total, covered, ctotal in (("S11", 3, 0, 3), ("S11b", 3, 1, 250), ("S11c", 0, 0, 3)):
    C.append(case(cid, "Fix clip so values above hi are clipped to hi.",
                  {PKG: BASE_PKG}, {PKG: EXTRA + CLIP_FIX},
                  {"first_run": {"verdict": "could_not_verify", "reason": "setup gap: No module named 'toyextra'"},
                   "rerun": {"verdict": "verified", "reason": "rerun after installing toyextra: tests pass"},
                   "changed_lines_total": ctotal,
                   "probe_changed_line_coverage": {"changed_lines_total": total, "changed_lines_covered": covered}}))


def main() -> None:
    if CASES.exists():
        shutil.rmtree(CASES)
    for cid, claim, before, after, recorded in C:
        d = CASES / cid
        for side, files in (("before", before), ("after", after)):
            (d / side).mkdir(parents=True, exist_ok=True)
            for rel, text in files.items():
                p = d / side / rel
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(text)
        (d / "claim.txt").write_text(claim + "\n")
        (d / "recorded.json").write_text(json.dumps(recorded, indent=1, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
