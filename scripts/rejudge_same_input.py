"""Print the verdict before and after the same-input guard.

Before is this code with the guard turned off: an agreeing differs observation is excused whenever any other
differs claim is proven, and a cross-run may settle that claim. After is the guard on. An agreeing observation
is excused only when no other claim is proven different on its input, and a cross-run will not settle a differs
claim whose agreeing observations sit on such an input.

Usage: python scripts/rejudge_same_input.py

Nothing from a pull request is run again. Printed paths are relative to the repository root.
"""
import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from evals.checks import derive_verdict  # noqa: E402
from ops import daily_run as dr  # noqa: E402
from ops.daily_run import compare_sides, is_test_file, verdict_for  # noqa: E402
from poc import claim_hygiene, probes  # noqa: E402

COV = {"status": "measured", "changed_lines_total": 1, "changed_lines_covered": 1, "adequacy": "adequate"}
_REAL = probes.other_claim_proven_on_input

# Pull requests named in the 2026-11-03 held-out set. A row is printed only when a stored record matches
# both the library token and the pull-request number.
HELD_OUT = (
    ("ce", (556, 557, 559)),
    ("altair", (4189, 4203)),
    ("requests", (7068, 7413)),
    ("rich", (4157,)),
    ("isort", (2778, 2748, 2674)),
    ("click", (3902,)),
    ("jsonschema", (1561, 1515)),
    ("invoke", (1097, 1098, 1099)),
    ("pingouin", (554,)),
)


def _guard(on: bool) -> None:
    probes.other_claim_proven_on_input = _REAL if on else (lambda *a, **k: False)


def _rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return path.name


def _identity(data: dict) -> tuple[str, str]:
    pr = data.get("pr")
    num = pr.get("number") if isinstance(pr, dict) else pr
    repo = str(data.get("repo") or (pr.get("repo") if isinstance(pr, dict) else "") or data.get("library") or "")
    return repo, "" if num is None else str(num)


def _library_tokens(repo: str) -> set[str]:
    parts = []
    for chunk in repo.replace("\\", "/").split("/"):
        for bit in chunk.replace("_", "-").split("-"):
            if bit:
                parts.append(bit.lower())
    return set(parts)


def _is_held(repo: str, num) -> bool:
    try:
        n = int(num)
    except (TypeError, ValueError):
        return False
    tokens = _library_tokens(repo)
    return any(lib in tokens and n in nums for lib, nums in HELD_OUT)


def _spec_files(spec, cross_run: bool):
    files = list(spec["files"])
    if not cross_run:
        files = [f for f in files if not is_test_file(str(f))] or ["pkg/mod.py"]
    return {"all": files, "package_py": list(spec.get("package_py") or []), "compiled": [],
            "other": [f for f in files if f not in (spec.get("package_py") or [])]}


def _spec_probes(spec):
    items = []
    for raw in spec["probes"]:
        body = {"id": raw["id"], "target": raw.get("target", "o/r#1"), "about": raw.get("about", "x"),
                "claims": raw["claims"]}
        item = probes.entry(body, {"main": [raw["main"]] * 3, "pr": [raw["pr"]] * 3}, None, [],
                            raw.get("source", "model"), None)
        item["status"] = "ran"
        item["probe_changed_line_coverage"] = dict(COV)
        items.append(item)
    return {"status": "ran", "items": items}


def _cell(value):
    if isinstance(value, dict):
        outcome = value["outcome"]
        message = value.get("message") or ""
        if outcome in ("failed", "error") and not message:
            message = "assertion failed"
        return outcome, message
    if value in ("failed", "error"):
        return value, "assertion failed"
    return value, ""


def _comparison(spec):
    def runs(rows):
        built = []
        for i in range(3):
            one = {}
            for key, value in rows.items():
                cell = value[i] if isinstance(value, list) else value
                one[key] = _cell(cell)
            built.append(one)
        return built

    return compare_sides({"main": runs(spec["tests"]["main"]), "pr": runs(spec["tests"]["pr"])})


def judge_spec(spec, cross_run: bool) -> dict:
    files = _spec_files(spec, cross_run)
    cmp = _comparison(spec)
    pp = _spec_probes(spec)
    v, _reason, fl = verdict_for(cmp, None, None, files, pp)
    advisory = probes.summarize(pp["items"]).get("advisory_agreeing_differs") or []
    return {"verdict": v, "settled": "cross_run_settled" in fl or bool(advisory),
            "cross": "cross_run_settled" in fl, "advisory": list(advisory)}


def judge_record(rec: dict) -> dict:
    pp = dr.rejudge_probes(rec.get("probes"), bool(rec.get("product_check")), broad_gate=dr.broad_gate_for(rec))
    v, _reason, fl = verdict_for(rec.get("comparison"), None if rec.get("comparison") else (rec.get("reason") or "no comparison"),
                                 rec.get("exit_check"), rec.get("files"), pp, rec.get("behaviour_claims"), rec.get("baseline"),
                                 docstring_only=bool(rec.get("docstring_only")))
    final = derive_verdict(rec, rec.get("baseline"), pp)
    advisory = ((pp or {}).get("summary") or {}).get("advisory_agreeing_differs") or []
    return {"verdict": final, "probe_verdict": v, "settled": "cross_run_settled" in fl or bool(advisory),
            "cross": "cross_run_settled" in fl, "advisory": list(advisory)}


def _linked(rec: dict) -> dict:
    pr = copy.deepcopy(rec["probes"])
    pr["items"] = [probes.rejudge_entry(it) for it in pr["items"]]
    return probes.apply_status(claim_hygiene.apply(pr))


def linking_verdict(rec: dict) -> dict:
    """The attrs #1647 path the agreeing-differs rule settled: claim linking, then a passing test comparison."""
    pr = _linked(rec)
    cmp = compare_sides({"main": [{"t::a": ("passed", ""), "t::b": ("passed", "")}] * 3,
                         "pr": [{"t::a": ("passed", ""), "t::b": ("passed", "")}] * 3})
    v, _reason, fl = verdict_for(cmp, None, probe_results=pr)
    advisory = (pr.get("summary") or {}).get("advisory_agreeing_differs") or []
    return {"verdict": v, "settled": "cross_run_settled" in fl or bool(advisory),
            "cross": "cross_run_settled" in fl, "advisory": list(advisory)}


def linked_stored_verdict(rec: dict) -> dict:
    """Claim linking, then the record's own test comparison and behaviour claims."""
    pr = _linked(rec)
    v, _reason, fl = verdict_for(rec.get("comparison"), None, rec.get("exit_check"), rec.get("files"), pr,
                                 rec.get("behaviour_claims"), rec.get("baseline"))
    advisory = (pr.get("summary") or {}).get("advisory_agreeing_differs") or []
    return {"verdict": v, "settled": "cross_run_settled" in fl or bool(advisory),
            "cross": "cross_run_settled" in fl, "advisory": list(advisory)}


def _pair(judge):
    try:
        _guard(False)
        before = judge()
    except Exception as e:
        before = {"verdict": "ERROR:" + type(e).__name__, "settled": False, "cross": False, "advisory": [], "error": str(e)}
    try:
        _guard(True)
        after = judge()
    except Exception as e:
        after = {"verdict": "ERROR:" + type(e).__name__, "settled": False, "cross": False, "advisory": [], "error": str(e)}
    finally:
        _guard(True)
    return before, after


def _line(label, path, before, after) -> str:
    extra = ""
    if before.get("probe_verdict") and before.get("probe_verdict") != before.get("verdict"):
        extra = f"  (probe verdict {before['probe_verdict']} -> {after.get('probe_verdict')})"
    bits = []
    if before.get("advisory"):
        bits.append("before advisory " + ",".join(before["advisory"]))
    elif after.get("advisory"):
        bits.append("after advisory " + ",".join(after["advisory"]))
    if before.get("cross") or after.get("cross"):
        bits.append("cross-run")
    mark = ("  [" + "; ".join(bits) + "]") if bits else ""
    return f"  {label}: {before.get('verdict')} -> {after.get('verdict')}{extra}{mark}  [{path}]"


def _record_paths() -> list[Path]:
    roots = [ROOT / "benchmarks", ROOT / "replay", ROOT / "reports", ROOT / "tests" / "fixtures"]
    found = []
    for root in roots:
        if root.is_dir():
            found.extend(root.rglob("record.json"))
    return sorted(found)


def _load(path: Path):
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _is_record(data: dict) -> bool:
    probes_d = data.get("probes")
    has_items = isinstance(probes_d, dict) and bool(probes_d.get("items"))
    return has_items and ("verdict" in data or isinstance(data.get("comparison"), dict))


def _settled_verdict(row: dict) -> bool:
    """The old rules moved this off needs attention (an agreeing claim excused, or a cross-run)."""
    return bool(row.get("settled")) and row.get("verdict") != "needs_attention"


def collect() -> list[str]:
    """One printed line per judged record, then the counts."""
    lines = []
    stay, flip, modelled = [], [], []

    def take(label, path, before, after, count: bool):
        lines.append(_line(label, path, before, after))
        if not count:
            return
        changed = before.get("verdict") != after.get("verdict")
        if _settled_verdict(before) and not changed:
            stay.append(f"{label}: {before.get('verdict')}")
        elif changed:
            flip.append(f"{label}: {before.get('verdict')} -> {after.get('verdict')}")

    spec = _load(ROOT / "tests/fixtures/same_input_guard/barcode-162.json")
    for cross, title in ((False, "python-barcode #162 modelled, no cross-run"),
                         (True, "python-barcode #162 modelled, passing cross-run")):
        before, after = _pair(lambda c=cross: judge_spec(spec, c))
        take(title, "tests/fixtures/same_input_guard/barcode-162.json", before, after, count=False)
        modelled.append(f"{title}: {before.get('verdict')} -> {after.get('verdict')}")

    named = [
        ("loguru #1536", ROOT / "tests/fixtures/agreeing_differs/loguru-1536.json"),
        ("toolz #654", ROOT / "tests/fixtures/agreeing_differs/toolz-654.json"),
        ("attrs #1647 derive_verdict", ROOT / "tests/fixtures/claim_linking/attrs-1647.json"),
    ]
    for label, path in named:
        data = _load(path)
        before, after = _pair(lambda d=data: judge_record(d))
        take(label, _rel(path), before, after, count=True)
    attrs = _load(ROOT / "tests/fixtures/claim_linking/attrs-1647.json")
    before, after = _pair(lambda: linking_verdict(attrs))
    take("attrs #1647 linking test", "tests/fixtures/claim_linking/attrs-1647.json", before, after, count=True)
    before, after = _pair(lambda: linked_stored_verdict(attrs))
    take("attrs #1647 linked, stored comparison", "tests/fixtures/claim_linking/attrs-1647.json", before, after, count=True)

    judged_paths = {p.resolve() for _label, p in named}
    judged_paths.add((ROOT / "tests/fixtures/claim_linking/attrs-1647.json").resolve())
    judged_paths.add((ROOT / "tests/fixtures/same_input_guard/barcode-162.json").resolve())
    for path in sorted((ROOT / "tests/fixtures").rglob("*.json")):
        if path.resolve() in judged_paths or path.parent.name == "narrow_cross_run":
            continue
        data = _load(path)
        if not data or not _is_record(data):
            continue
        before, after = _pair(lambda d=data: judge_record(d))
        if before.get("verdict") != after.get("verdict") or _settled_verdict(before):
            take(f"fixture {_rel(path)}", _rel(path), before, after, count=True)

    for path in sorted((ROOT / "tests/fixtures/narrow_cross_run").glob("*.json")):
        data = _load(path)
        if not data or not isinstance(data.get("probes"), list):
            continue
        before, after = _pair(lambda d=data: judge_spec(d, True))
        if before.get("verdict") != after.get("verdict") or _settled_verdict(before):
            take(f"narrow {path.stem}", _rel(path), before, after, count=True)

    held_hits = []
    record_changes = []
    n_records = n_seen = 0
    for path in _record_paths():
        n_seen += 1
        data = _load(path)
        if not data or not _is_record(data):
            continue
        n_records += 1
        repo, num = _identity(data)
        before, after = _pair(lambda d=data: judge_record(d))
        rel = _rel(path)
        changed = before.get("verdict") != after.get("verdict")
        if changed:
            record_changes.append(f"{repo} #{num}: {before.get('verdict')} -> {after.get('verdict')}  [{rel}]")
        if changed or _settled_verdict(before):
            take(f"{repo} #{num}", rel, before, after, count=True)
        if _is_held(repo, num):
            held_hits.append(f"{repo} #{num}  [{rel}]")

    lines.append("")
    lines.append(f"stored record.json files: {n_seen}; rejudged (probe results present): {n_records}")
    if record_changes:
        lines.append("stored record.json verdict changes:")
        lines.extend(f"  {row}" for row in record_changes)
    else:
        lines.append("stored record.json verdict changes: none")

    lines.append("")
    lines.append("2026-11-03 held-out set:")
    found_pairs = set()
    if held_hits:
        lines.extend(f"  found {row}" for row in held_hits)
        for row in held_hits:
            repo, num = row.split("  [")[0].rsplit(" #", 1)
            found_pairs.add((frozenset(_library_tokens(repo)), int(num)))
    else:
        lines.append("  no matching record.json in the repo")
    missing = [f"{lib} #{n}" for lib, nums in HELD_OUT for n in nums
               if not any(lib in tokens and n == num for tokens, num in found_pairs)]
    lines.append("  not in the repo: " + (", ".join(missing) if missing else "none"))

    lines.append("")
    lines.append(f"stay settled: {len(stay)}")
    for label in stay:
        lines.append(f"  {label}")
    lines.append(f"flip back: {len(flip)}")
    for label in flip:
        lines.append(f"  {label}")
    if not flip:
        lines.append("  none")
    lines.append("modelled miss (python-barcode #162):")
    for label in modelled:
        lines.append(f"  {label}")
    return lines


def main() -> int:
    for line in collect():
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
