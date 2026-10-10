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
    assert SCHEMA_PATH.parts[-3:] == ("harness", "schema", "observation.schema.json")
    assert SCHEMA_SHA256 == "5a3c3d36b7730ce74d0f23b03c88ea862ea35cc327c7d79481fca8b972e8383e"


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
