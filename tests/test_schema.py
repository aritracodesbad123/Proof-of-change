import copy

from guardrails.schema import validate_record


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
    for s in ("cpu_count", "real_break", "side must be", "matches_expected", "missing field 'upstream'"):
        assert s in errs


def test_machine_type_needs_arch_and_os(upset):
    r = copy.deepcopy(upset)
    r["machine_type"] = {"label": "x"}
    assert any("arch" in e for e in validate_record(r))
