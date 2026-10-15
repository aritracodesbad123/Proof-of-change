import copy

from guardrails.schema import SCHEMA_PATH, SCHEMA_SHA256, validate_record


def test_ci_records_valid(ci_records):
    for r in ci_records:
        assert validate_record(r) == []


def test_legacy_records_valid_without_ci_fields(legacy_records):
    for r in legacy_records:
        assert validate_record(r, require_ci_fields=False) == []


def test_legacy_records_rejected_in_strict_mode(legacy_records):
    errs = validate_record(legacy_records[0])
    assert any("machine_type" in e for e in errs)


def test_bad_types_and_values(upset):
    r = copy.deepcopy(upset)
    r["cpu_count"] = "8"
    r["classification"]["real_break"] = -1
    r["per_run"][0]["side"] = "middle"
    r["matches_expected"] = "maybe"
    del r["upstream"]
    errs = " ".join(validate_record(r))
    for s in ("cpu_count", "real_break", "side: must be one of", "matches_expected", "missing field 'upstream'"):
        assert s in errs


def test_machine_type_needs_arch_and_os(upset):
    r = copy.deepcopy(upset)
    r["machine_type"] = {"label": "x"}
    assert any("arch" in e for e in validate_record(r))


def test_schema_is_the_shared_file():
    from guardrails.schema import COMPATIBLE_SCHEMA_SHA256, SCHEMA_REVISION
    assert SCHEMA_PATH.parts[-3:] == ("harness", "schema", "observation.schema.json")
    assert SCHEMA_SHA256 == "a0042eef48d97408b9f8b3479f2c7f26530c453b3d506df836dd8ef6af21d716"  # rev 10
    assert SCHEMA_REVISION == 10
    got = sorted(COMPATIBLE_SCHEMA_SHA256.values(), key=lambda s: int(s.split()[-1]))
    assert got == [f"rev {n}" for n in range(1, 11)]
    assert COMPATIBLE_SCHEMA_SHA256["5a3c3d36b7730ce74d0f23b03c88ea862ea35cc327c7d79481fca8b972e8383e"] == "rev 1"
    readme = (SCHEMA_PATH.parent / "README.md").read_text()
    assert all(sha in readme for sha in COMPATIBLE_SCHEMA_SHA256)  # documented


def test_rev1_records_still_valid_under_current_rev(golden_v1_records):
    from guardrails.schema import schema_reference_note
    for r in golden_v1_records:
        assert r["schema_sha256"].startswith("5a3c3d36")  # the golden records were written against rev 1
        assert validate_record(r, require_v1=True) == []
        assert "valid under current rev 10" in schema_reference_note(r)


def test_rev2_optional_fields(golden_v1_records):
    import json

    from conftest import REPO
    ex = json.loads((REPO / "evals" / "fixtures" / "record_rev2_example.json").read_text())
    assert validate_record(ex, require_v1=True) == []
    for f in ("pr", "claims", "old_output", "golden_check", "reviewer_decision", "upstream_commit_old", "upstream_commit_new"):
        assert f in ex and all(f not in r for r in golden_v1_records)  # optional: absent in rev 1 records
    bad = copy.deepcopy(ex)
    bad["reviewer_decision"]["decision"] = "maybe"
    bad["pr"]["number"] = "29677"
    bad["claims"]["claims"][0]["check"]["kind"] = "guess"
    bad["golden_check"]["passed"] = True
    errs = " ".join(validate_record(bad))
    for s in ("reviewer_decision.decision", "pr.number", "claims.claims[0].check.kind", "golden_check.passed"):
        assert s in errs, s


def test_golden_v1_records_valid_in_v1_mode(golden_v1_records):
    assert len(golden_v1_records) == 3
    for r in golden_v1_records:
        assert validate_record(r, require_v1=True) == []


def test_v1_mode_requires_runner_fields(upset):
    errs = " ".join(validate_record(upset, require_v1=True))
    for f in ("schema_version", "accepted", "gates", "network", "report"):
        assert f"missing field '{f}'" in errs
    assert validate_record(upset) == []  # pre-v1 harness record is still fine in ci mode


def test_record_declaring_v1_is_always_checked_in_v1_mode(g_pandas):
    r = copy.deepcopy(g_pandas)
    del r["gates"]
    assert any("gates" in e for e in validate_record(r))


def test_schema_reference_by_checksum_not_path(g_sklearn):
    # the record names a path in another checkout; it must not be opened, only the sha256 compared
    r = copy.deepcopy(g_sklearn)
    r["schema_path"] = "/nonexistent/checkout/harness/schema/observation.schema.json"
    assert validate_record(r, require_v1=True) == []
    r["schema_sha256"] = "0" * 64
    assert any("schema_sha256" in e for e in validate_record(r, require_v1=True))


def test_shared_schema_rules(g_sklearn):
    r = copy.deepcopy(g_sklearn)
    r["thread_env"]["OMP_NUM_THREADS"] = "4"
    r["date_ist"] = "10 Oct 2026"
    r["runs_per_side"] = True  # booleans are not integers
    errs = " ".join(validate_record(r))
    for s in ("thread_env.OMP_NUM_THREADS", "date_ist", "runs_per_side"):
        assert s in errs
    r = copy.deepcopy(g_sklearn)
    r["classification"] = None  # only allowed when the runner refused to classify
    assert any("accepted is false" in e for e in validate_record(r))
    r["accepted"] = False
    assert validate_record(r) == []


def test_rev4_coverage_fields_optional_and_typed():
    """rev 4 adds optional coverage-gate fields; they validate when present and are type-checked."""
    import copy
    import json

    from conftest import REPO
    rec = json.loads((REPO / "tests/fixtures/day1/pr_run_numpy_32910.json").read_text())
    assert validate_record(rec) == []
    for k in ("changed_lines_total", "changed_lines_covered", "coverage", "coverage_gate"):
        assert k not in rec  # a pre-gate record: the fields are optional
    from poc import coverage_gate
    gated = coverage_gate.apply(rec)
    assert validate_record(gated) == []
    bad = copy.deepcopy(gated)
    bad["coverage_gate"]["confidence"] = "maybe"
    assert validate_record(bad)
    bad = copy.deepcopy(gated)
    bad["changed_lines_total"] = -1
    assert validate_record(bad)
