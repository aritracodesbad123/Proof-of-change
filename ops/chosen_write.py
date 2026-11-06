#!/usr/bin/env python3
"""Write a chosen-PRs file only when the daily reader's parser still sees the selection.

The daily run (``ops/daily_run.py``) reads that file with ``parse_chosen``. This module uses
that same function. It does not re-render the note, and it does not keep a cleaned copy that
dropped a pull request the selection still names.

    python -m ops.chosen_write check PATH [--intended selection.json] [--now 2026-11-06T04:30:00Z]
    python -m ops.chosen_write write PATH --intended selection.json --from-file note.md

On success the command prints the parse as JSON. On failure it exits 2, prints the parse the
reader actually kept, and writes the same no-go summary PDF a refused run leaves
(``<file>.no-go/SUMMARY.pdf``) with the reason and how to fix the heading. A marker beside the
note makes the daily run stop before it selects anything. The previous note is not replaced.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ops import daily_run  # noqa: E402
from poc import pdf_always  # noqa: E402

MARKER_SUFFIX = ".write-failed.json"
SELECTION_SUFFIX = ".selection.json"
LOG_SUFFIX = ".preflight.log"
_FIELDS = ("head_sha", "base_sha", "install", "test_cmd")
_HOW = ("Name it as `owner/name #N`, `owner/name PR #N`, or `owner/name pull request #N`, "
        "or put `**Open PR:** #N` under the repository. "
        "A head or base commit is read from a Head or Base line in that same section. "
        "An install or test command is read from a `- Install:` or `- Test:` line with the command in backticks. "
        "A number that appears only inside a URL is not read.")


class ChosenWriteError(ValueError):
    """The note was not written. ``parsed`` is what the daily reader returned."""

    def __init__(self, message: str, parsed: dict | None = None, problems: list[str] | None = None):
        super().__init__(message)
        self.parsed = parsed or {}
        self.problems = list(problems or [])


def marker_path(path: Path) -> Path:
    return Path(str(path) + MARKER_SUFFIX)


def selection_path(path: Path) -> Path:
    return Path(str(path) + SELECTION_SUFFIX)


def log_path(path: Path) -> Path:
    return Path(str(path) + LOG_SUFFIX)


def no_go_dir(path: Path) -> Path:
    """Folder of the no-go summary written when this note is refused. Not a run folder."""
    return path.parent / f"{path.name}.no-go"


def parse_text(text: str) -> dict:
    """``parse_chosen`` on this text. The temporary file is not the note being written."""
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "chosen.md"
        path.write_text(text)
        return daily_run.parse_chosen(path)


def _rows(parsed: dict) -> list[tuple]:
    rows = []
    for repo, items in parsed.items():
        for row in items:
            rows.append((str(repo), int(row["pr"]), {field: row.get(field) for field in _FIELDS}))
    return rows


def _intended_rows(intended) -> list[tuple] | None:
    """None when the caller did not pass a selection. A present selection is a list of rows.

    A row keeps only the fields the caller set, so an omitted head commit is not a disagreement
    with a commit the reader found. A field that is present, including null, must match.
    """
    if intended is None:
        return None
    if isinstance(intended, dict):
        items = []
        for repo, rows in intended.items():
            if not isinstance(rows, list):
                raise ChosenWriteError("intended selection entries must be lists of pull requests")
            for row in rows:
                if not isinstance(row, dict):
                    raise ChosenWriteError("each intended pull request must be an object")
                items.append({"repo": repo, **row})
    elif isinstance(intended, list):
        items = intended
    else:
        raise ChosenWriteError("intended selection must be an object or a list")
    out = []
    for row in items:
        if not isinstance(row, dict) or not row.get("repo") or row.get("pr") is None:
            raise ChosenWriteError("each intended pull request needs a repo and a pr number")
        kept = {field: row[field] for field in _FIELDS if field in row}
        out.append((str(row["repo"]), int(row["pr"]), kept))
    return out


def unread_sections(text: str) -> list[str]:
    """Sections the daily reader splits off and then drops.

    A dropped section is how a cleaned parse can keep the other pull requests and lose one.
    Prose before the first numbered section is not a section. A section the reader accepts,
    including every heading form it already understands, is not listed here.
    """
    problems = []
    for sec in daily_run._library_sections(text):
        if daily_run._section_blocks(sec):
            continue
        line = sec.lstrip("\n").split("\n", 1)[0].strip() or "(blank section)"
        problems.append(f"a section was not read as a pull request: {line!r}. {_HOW}")
    if not daily_run._library_sections(text) and text.strip():
        problems.append(f"no numbered section (`## 1. ...`) was found. {_HOW}")
    return problems


def assess(text: str, intended) -> tuple[dict, list[str]]:
    """Return ``(parse, problems)``. An empty problem list means the note may be kept."""
    parsed = parse_text(text)
    problems = unread_sections(text)
    wanted = _intended_rows(intended)
    if wanted is None:
        if text.strip() and not parsed and not problems:
            problems.append(f"the reader found no pull request. {_HOW}")
        return parsed, problems
    got = _rows(parsed)
    got_keys = [(repo, pr) for repo, pr, _fields in got]
    want_keys = [(repo, pr) for repo, pr, _fields in wanted]
    for repo, pr in want_keys:
        if got_keys.count((repo, pr)) == 0:
            problems.append(f"{repo}#{pr} is in the selection but the reader did not find it")
    for repo, pr in got_keys:
        if want_keys.count((repo, pr)) == 0:
            problems.append(f"{repo}#{pr} is in the file but not in the selection")
    if len(got_keys) != len(set(got_keys)):
        problems.append("the reader found the same pull request more than once")
    by_key = {}
    for repo, pr, fields in got:
        by_key.setdefault((repo, pr), fields)
    for repo, pr, fields in wanted:
        have = by_key.get((repo, pr))
        if have is None:
            continue
        for field, value in fields.items():
            if have.get(field) != value:
                problems.append(
                    f"{repo}#{pr} {field} is {have.get(field)!r} in the file and {value!r} in the selection")
    if text.strip() and not parsed and not any("did not find it" in p for p in problems):
        problems.append(f"the reader found no pull request. {_HOW}")
    return parsed, problems


def _message(problems: list[str], parsed: dict, path: Path) -> str:
    shown = "; ".join(problems[:8])
    found = ", ".join(f"{repo}#{pr}" for repo, pr, _fields in _rows(parsed)) or "nothing"
    extra = "" if len(problems) <= 8 else f" ({len(problems) - 8} more)"
    return ("Stopped: the chosen-PRs file was not accepted. "
            f"{shown}{extra}. The reader got: {found}. "
            "The previous file was left unchanged. "
            f"No-go summary: {path.name}.no-go/SUMMARY.pdf. "
            "Fix the heading or the commit, then write the note again.")


def _brief(parsed: dict) -> str:
    found = ", ".join(f"{repo}#{pr}" for repo, pr, _fields in _rows(parsed)) or "nothing"
    return f"reader accepted {found}"


def _stamp(now: dt.datetime | None) -> str:
    when = now or dt.datetime.now(dt.timezone.utc)
    if when.tzinfo is None:
        when = when.replace(tzinfo=dt.timezone.utc)
    return when.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _atomic(path: Path, data: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    except Exception:
        if tmp.exists():
            tmp.unlink()
        raise


def _dump(obj) -> str:
    return json.dumps(obj, indent=2, sort_keys=True) + "\n"


def _log(path: Path, line: str, now: dt.datetime | None) -> None:
    log = log_path(path)
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("a", encoding="utf-8") as handle:
        handle.write(f"{_stamp(now)} {line}\n")


def _write_marker(path: Path, message: str, problems: list[str], parsed: dict, intended) -> None:
    _atomic(marker_path(path), _dump({
        "ok": False, "error": message, "problems": problems, "parsed": parsed, "intended": intended}))


def _surface(path: Path, message: str) -> None:
    """The same no-go PDF a refused daily run leaves, written here so the reason is not only a log line."""
    try:
        pdf_always.nogo_summary(no_go_dir(path), path.name, message)
    except OSError:
        pass


def _clear_surface(path: Path) -> None:
    folder = no_go_dir(path)
    if folder.is_dir():
        shutil.rmtree(folder)


def read_failure(path: Path) -> str | None:
    """The stop line recorded beside ``path``, or None when the last write was accepted."""
    marker = marker_path(path)
    if not marker.is_file():
        return None
    try:
        data = json.loads(marker.read_text(encoding="utf-8"))
        err = str(data.get("error") or "").strip() if isinstance(data, dict) else ""
    except (OSError, json.JSONDecodeError):
        err = ""
    if not err:
        err = f"Stopped: {marker.name} is present but could not be read, so the chosen-PRs file is not trusted."
    elif not err.startswith("Stopped:"):
        err = "Stopped: " + err
    return err


def write_chosen(path: Path, text: str, intended, *, now: dt.datetime | None = None) -> dict:
    """Write ``text`` unchanged when it parses to ``intended``. Otherwise raise and leave ``path`` as it was.

    The returned dict is the daily reader's parse. The same parse is stored as JSON beside the note
    (``<file>.selection.json``) so a later check can see a mismatch. The JSON is that parse, not a
    second rendering of the note.
    """
    path = Path(path)
    if intended is None:
        raise ChosenWriteError("a write needs the intended selection; otherwise a dropped pull request can be kept")
    try:
        parsed, problems = assess(text, intended)
    except ChosenWriteError:
        raise
    except OSError as exc:
        message = (f"Stopped: the chosen-PRs file could not be read back ({type(exc).__name__}). "
                   "The previous file was left unchanged. "
                   f"No-go summary: {path.name}.no-go/SUMMARY.pdf.")
        _surface(path, message)
        _write_marker(path, message, [message], {}, intended)
        _log(path, "FAILED " + message, now)
        raise ChosenWriteError(message, parsed={}, problems=[message]) from exc
    if problems:
        message = _message(problems, parsed, path)
        _surface(path, message)
        _write_marker(path, message, problems, parsed, intended)
        _log(path, "FAILED " + message, now)
        raise ChosenWriteError(message, parsed=parsed, problems=problems)
    try:
        _atomic(path, text)
        _atomic(selection_path(path), _dump(parsed))
    except OSError as exc:
        message = (f"Stopped: the chosen-PRs file write did not finish ({type(exc).__name__}). "
                   "A partial file is not the selection. The daily run will stop until a write finishes. "
                   f"No-go summary: {path.name}.no-go/SUMMARY.pdf.")
        _surface(path, message)
        _write_marker(path, message, [message], parsed, intended)
        _log(path, "FAILED " + message, now)
        raise ChosenWriteError(message, parsed=parsed, problems=[message]) from exc
    marker = marker_path(path)
    if marker.exists():
        marker.unlink()
    _clear_surface(path)
    _log(path, "OK " + _brief(parsed), now)
    return parsed


def _saved_selection(path: Path):
    saved = selection_path(path)
    if not saved.is_file():
        return None
    try:
        return json.loads(saved.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ChosenWriteError(
            f"Stopped: the saved selection beside {path.name} could not be read ({type(exc).__name__}).") from exc


def check_chosen(path: Path, intended=None, *, now: dt.datetime | None = None) -> dict:
    """Parse ``path`` with the daily reader. Fail when a write marker is present or the parse disagrees.

    With no ``intended``, a saved ``<file>.selection.json`` from the last accepted write is the selection.
    """
    path = Path(path)
    blocked = read_failure(path)
    if not path.is_file():
        message = blocked or (f"Stopped: {path.name} is missing, so there is no chosen-PRs file to read. "
                              f"No-go summary: {path.name}.no-go/SUMMARY.pdf.")
        _surface(path, message)
        _log(path, "FAILED " + message, now)
        raise ChosenWriteError(message, parsed={}, problems=[message])
    if intended is None:
        try:
            intended = _saved_selection(path)
        except ChosenWriteError as exc:
            _log(path, "FAILED " + str(exc), now)
            raise
    parsed, problems = assess(path.read_text(encoding="utf-8"), intended)
    if blocked:
        message = blocked
    elif problems:
        message = _message(problems, parsed, path)
    else:
        _clear_surface(path)
        _log(path, "OK " + _brief(parsed), now)
        return parsed
    _surface(path, message)
    _log(path, "FAILED " + message, now)
    raise ChosenWriteError(message, parsed=parsed, problems=problems or [message])


def run_stop(path: Path, chosen: dict) -> str | None:
    """Stop line for the daily run: a failed write, otherwise the reader's own empty-file stop.

    Verdict rules are not involved. A missing marker leaves the previous empty-file behaviour as it was.
    """
    failed = read_failure(path)
    if failed:
        return failed
    return daily_run.empty_chosen_stop(path, chosen)


def _print_parse(parsed: dict) -> None:
    sys.stdout.write(_dump(parsed))


def _parse_now(text: str | None) -> dt.datetime | None:
    if not text:
        return None
    raw = text.strip().replace("Z", "+00:00")
    try:
        when = dt.datetime.fromisoformat(raw)
    except ValueError as exc:
        raise SystemExit(f"Stopped: --now must be an ISO time ({exc}).") from exc
    return when


def _load_intended(path: str | None):
    if not path:
        return None
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"Stopped: could not read the intended selection ({type(exc).__name__}).") from exc


def main(argv=None) -> int:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--now", default=None, help="ISO time for the preflight log (tests and a simulated run)")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    check = sub.add_parser("check", parents=[common],
                           help="parse an existing chosen-PRs file and fail if it does not match")
    check.add_argument("path")
    check.add_argument("--intended", default=None, help="JSON selection; default is the snapshot saved at the last write")
    write = sub.add_parser("write", parents=[common],
                           help="write the note only when the reader agrees with the selection")
    write.add_argument("path")
    write.add_argument("--intended", required=True, help="JSON selection the note must parse back to")
    write.add_argument("--from-file", default=None, help="markdown to write; stdin when omitted")
    args = ap.parse_args(argv)
    now = _parse_now(args.now)
    try:
        if args.cmd == "check":
            parsed = check_chosen(Path(args.path), _load_intended(args.intended), now=now)
        else:
            if args.from_file:
                text = Path(args.from_file).read_text(encoding="utf-8")
            else:
                text = sys.stdin.read()
            parsed = write_chosen(Path(args.path), text, _load_intended(args.intended), now=now)
    except ChosenWriteError as exc:
        print(str(exc), file=sys.stderr)
        _print_parse(exc.parsed)
        return 2
    _print_parse(parsed)
    return 0


if __name__ == "__main__":
    sys.exit(main())
