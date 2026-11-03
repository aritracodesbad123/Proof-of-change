"""Print the stored verdict and the verdict under the flagged-claim rule.

A flagged probe claim is needs attention even when no test was collected on either side.
This reads a directory of record.json files (subfolders included) and prints, for each,
the verdict stored in the file and the verdict this code gives. It then lists the ones
that move.

Usage: python scripts/rejudge_gate_order.py RECORD_DIR

Nothing from a pull request is run again. Printed paths are relative to RECORD_DIR.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from evals.checks import derive_verdict  # noqa: E402


def _rel(path: Path, root: Path) -> str:
    """A path under root, with no absolute prefix. A path outside root is just the file name."""
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.name


def _load(path: Path):
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None
    if isinstance(data, dict):
        return [data]
    if isinstance(data, list):
        return [item if isinstance(item, dict) else None for item in data]
    return None


def _stored(rec: dict) -> str:
    verdict = rec.get("verdict")
    return verdict if isinstance(verdict, str) and verdict else "(none)"


def _new(rec: dict) -> str:
    try:
        return derive_verdict(rec, rec.get("baseline"))
    except Exception as exc:
        return "ERROR:" + type(exc).__name__


def report(directory: Path) -> list[str]:
    """One line per record.json, then the records whose verdict moves."""
    root = Path(directory)
    lines, moved = [], []
    paths = sorted(root.rglob("record.json")) if root.is_dir() else []
    n = 0
    for path in paths:
        rel = _rel(path, root)
        records = _load(path)
        if records is None:
            lines.append(f"  {rel}: stored (unreadable), new rule (unreadable)")
            continue
        for i, rec in enumerate(records):
            n += 1
            label = rel if len(records) == 1 else f"{rel}#{i}"
            if not isinstance(rec, dict):
                lines.append(f"  {label}: stored (unreadable), new rule (unreadable)")
                continue
            stored, new = _stored(rec), _new(rec)
            lines.append(f"  {label}: stored {stored}, new rule {new}")
            if stored != new:
                moved.append(f"  {label}: {stored} -> {new}")
    out = [f"records: {n}", *lines, "moved:"]
    out.extend(moved or ["  none"])
    return out


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print(__doc__)
        return 2
    directory = Path(argv[0])
    if not directory.is_dir():
        print("not a directory")
        return 2
    for line in report(directory):
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
