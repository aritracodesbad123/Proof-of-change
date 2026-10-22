"""Benchmark case manifest: one JSON file per case under bench/cases/ (schema in docs/benchmark-manifest.md).

    python -m bench.manifest bench/cases          # validate every case file, print problems, exit 1 if any
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

SCHEMA = "poc-bench-case/1"
CATEGORIES = ("known_safe", "known_regression_tests_catch", "known_regression_tests_miss", "setup_failure", "ambiguous")
REGRESSION = ("known_regression_tests_catch", "known_regression_tests_miss")
VERDICTS = ("verified", "needs_attention", "could_not_verify", "no_code_change")
# The verdict a correct check gives per category (None: any verdict is acceptable, the case is reported, not scored).
EXPECTED_FOR = {"known_safe": "verified", "known_regression_tests_catch": "needs_attention",
                "known_regression_tests_miss": "needs_attention", "setup_failure": "could_not_verify", "ambiguous": None}
ALLOWED_REPOS = ("psf/requests", "python-attrs/attrs", "pallets/click", "PyCQA/isort", "python-jsonschema/jsonschema",
                 "urllib3/urllib3", "andialbrecht/sqlparse", "pytoolz/toolz", "pallets/markupsafe", "Textualize/rich",
                 "prettytable/prettytable", "jazzband/prettytable", "mahmoud/boltons", "pytest-dev/pytest",
                 "Delgan/loguru", "lincolnloop/python-qrcode", "pyinvoke/invoke")
REQUIRED = ("schema", "id", "repo", "pr_url", "base_sha", "head_sha", "category", "expected_verdict", "rationale", "source")
SHA = re.compile(r"^[0-9a-f]{40}$")
ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


def validate(case: dict) -> list[str]:
    """Problems with one case (empty list = valid)."""
    if not isinstance(case, dict):
        return ["case is not a JSON object"]
    p = [f"missing field: {k}" for k in REQUIRED if k not in case]
    if p:
        return p
    if case["schema"] != SCHEMA:
        p.append(f"schema must be {SCHEMA!r}")
    if not isinstance(case["id"], str) or not ID.match(case["id"]):
        p.append("id must be 1-64 chars of letters, digits, '.', '_' or '-'")
    if case["repo"] not in ALLOWED_REPOS:
        p.append(f"repo {case['repo']!r} is not in the benchmark repo list")
    m = re.match(r"^https://github\.com/([^/]+/[^/]+)/pull/(\d+)$", str(case["pr_url"]))
    if not m:
        p.append("pr_url must be https://github.com/OWNER/REPO/pull/N")
    elif m.group(1).lower() != str(case["repo"]).lower():
        p.append("pr_url is not in repo")
    for k in ("base_sha", "head_sha"):
        if not isinstance(case[k], str) or not SHA.match(case[k]):
            p.append(f"{k} must be a full 40-character lowercase commit id")
    if case["base_sha"] == case["head_sha"]:
        p.append("base_sha and head_sha are the same commit")
    if case["category"] not in CATEGORIES:
        p.append(f"category must be one of {', '.join(CATEGORIES)}")
    elif case["expected_verdict"] not in VERDICTS:
        p.append(f"expected_verdict must be one of {', '.join(VERDICTS)}")
    else:
        want = EXPECTED_FOR[case["category"]]
        if want and case["expected_verdict"] != want:
            p.append(f"category {case['category']} expects verdict {want}")
    for k in ("rationale", "source"):
        if not isinstance(case[k], str) or not case[k].strip():
            p.append(f"{k} must be a non-empty string")
    if "fixture" in case and not isinstance(case["fixture"], bool):
        p.append("fixture must be true or false")
    if "patch" in case and not (isinstance(case["patch"], str) and case["patch"].endswith((".patch", ".diff"))):
        p.append("patch must be a path to a .patch or .diff file")
    return p


def load_cases(path: Path) -> tuple[list[dict], dict[str, list[str]]]:
    """Cases from a file or a folder of *.json files, plus problems by file. Duplicate ids are a problem."""
    files = sorted(path.glob("*.json")) if path.is_dir() else [path]
    cases, problems, seen = [], {}, set()
    for f in files:
        try:
            c = json.loads(f.read_text())
        except (OSError, ValueError) as e:
            problems[str(f)] = [f"unreadable: {e}"]
            continue
        p = validate(c)
        if not p and c["id"] in seen:
            p = [f"duplicate id {c['id']}"]
        if p:
            problems[str(f)] = p
        else:
            seen.add(c["id"])
            cases.append(c)
    return cases, problems


def main(argv=None) -> int:
    path = Path((argv if argv is not None else sys.argv[1:] or ["bench/cases"])[0])
    cases, problems = load_cases(path)
    for f, ps in problems.items():
        for x in ps:
            print(f"{f}: {x}")
    print(f"{len(cases)} valid case(s), {len(problems)} file(s) with problems")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
