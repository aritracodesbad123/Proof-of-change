"""Local JSON API for the Proof-of-Change operator console (browse runs + start checks).

    python -m poc.console_api --port 8787

Endpoints:
  GET  /api/health
  GET  /api/runs
  GET  /api/runs/<id>
  GET  /api/runs/<id>/report.pdf
  GET  /api/runs/<id>/report.html
  POST /api/checks   JSON {"pr_url": "https://github.com/o/r/pull/N"}
  GET  /api/jobs/<job_id>
  POST /api/jobs/<job_id>/scenarios   HITL approval (approve / extra_scenarios / business_answers)

Serves console/web/dist when built. CORS open for local Vite (5173).
"""
from __future__ import annotations

import json
import os
import re
import select
import signal
import subprocess
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

REPO_ROOT = Path(__file__).resolve().parent.parent
RUNS_ROOT = Path(os.environ.get("POC_OPS_RUNS", REPO_ROOT / "ops" / "runs"))
HOSTED = REPO_ROOT / "reports" / "hosted"
REPORTS_DAILY = Path(os.environ.get("POC_REPORT_DIR") or (REPO_ROOT / "reports" / "daily"))
CONSOLE_JOB_TIMEOUT_S = 45 * 60
OWNER_FILE = "console_owner.txt"
WEB_DIST = REPO_ROOT / "console" / "web" / "dist"
PR_RE = re.compile(r"https?://github\.com/([^/]+/[^/]+)/pull/(\d+)", re.I)
_REPORT_FILE_RE = re.compile(r"^/api/runs/(.+)/report\.(pdf|html)$")

_jobs: dict[str, dict[str, Any]] = {}
# RLock: job finish must not nest Lock via remember_run (that wedged the whole console).
_jobs_lock = threading.RLock()
# ponytail: Render free disk is wiped on sleep/redeploy; keep last finished runs in RAM for this process.
_recent_runs: dict[str, dict[str, Any]] = {}
_RECENT_MAX = 30
_RUN_LOG_RE = re.compile(r"run log:\s*(\S+/ops/runs/[^/\s]+)/REPORT\.md")


def contree_usable() -> bool:
    """True only when Contree can actually start (creds + SDK). Env alone is not enough."""
    if not (os.environ.get("NEBIUS_API_KEY") and os.environ.get("NEBIUS_PROJECT_ID")):
        return False
    try:
        import contree_sdk  # noqa: F401
    except ImportError:
        return False
    return True


def recorded_demo_flags(model_provider: str) -> list[str]:
    """Shorter pytest only for the console's prerecorded sample. Study defaults stay on the parser."""
    if model_provider != "recorded":
        return []
    return ["--runs", "1", "--run-timeout", "300", "--workers", "1"]


def console_daily_run_argv(pr_url: str, model_provider: str, extra_flags: list[str] | None = None) -> list[str]:
    """The command the operator console uses to start one pull-request check.

    ``--console-job`` is how that check may start with operator approval on. An environment
    variable cannot take its place.
    """
    py = REPO_ROOT / ".venv" / "bin" / "python"
    exe = str(py) if py.is_file() else os.environ.get("PYTHON", "python3")
    extra = list(extra_flags or [])
    ops_dir = (os.environ.get("POC_OPS_DIR") or "").strip()
    if ops_dir:
        extra.extend(["--ops-dir", ops_dir])
    report_dir = (os.environ.get("POC_REPORT_DIR") or "").strip()
    if report_dir:
        extra.extend(["--report-dir", report_dir])
    return [exe, str(REPO_ROOT / "ops" / "daily_run.py"),
            "--pr", pr_url.strip(), "--model-provider", model_provider,
            "--swarm", "--console-job", *extra]


_UNSAFE_WARNING = (
    "Warning: POC_UNSAFE_NO_SANDBOX=1 is set, so this check runs with --unsafe-no-sandbox. "
    "Pull-request code will run without a sandbox and can see this machine's files, keys, and network."
)


def _unsafe_opt_in() -> bool:
    """True only when the operator explicitly asked to run pull-request code unsandboxed."""
    return (os.environ.get("POC_UNSAFE_NO_SANDBOX") or "").strip().lower() in ("1", "true", "yes")


def blocks_unsandboxed_run(flags: list[str], note: str | None) -> str | None:
    """The refusal text when these flags would run pull-request code with no sandbox.

    ``--unsafe-no-sandbox`` is the explicit opt-in. ``--sandbox-backend`` selects Contree.
    An empty flag list means local bubblewrap, which is fine only when the note does not
    say the sandbox is missing.
    """
    if "--unsafe-no-sandbox" in flags or "--sandbox-backend" in flags:
        return None
    if note and "will not run pull-request code" in note:
        return note
    return None


def console_run_flags() -> tuple[list[str], str | None]:
    """Extra daily_run flags for the operator console.

    Prefer Contree when it can actually run. Otherwise bubblewrap is the sandbox.
    If neither can start, do not run pull-request code. The only opt-in is
    POC_UNSAFE_NO_SANDBOX=1, which adds --unsafe-no-sandbox and a visible warning.
    """
    force = _unsafe_opt_in()
    if contree_usable():
        if force:
            return ["--sandbox-backend", "contree", "--unsafe-no-sandbox"], (
                "using Contree sandboxes. " + _UNSAFE_WARNING
            )
        return ["--sandbox-backend", "contree"], "using Contree sandboxes"
    ok = False
    why = "sandbox check skipped"
    try:
        from guardrails import sandbox
        ok, why = sandbox.check()
    except Exception as e:  # noqa: BLE001
        ok, why = False, f"{type(e).__name__}: {e}"
    if ok and not force:
        return [], None
    if force:
        return ["--unsafe-no-sandbox"], f"{_UNSAFE_WARNING} ({why})"
    return [], (
        f"sandbox unavailable ({why}). "
        "Proof-of-Change will not run pull-request code without a sandbox. "
        "Install bubblewrap, or set up Contree (a Nebius key, a project id, and contree-sdk). "
        "Setting POC_UNSAFE_NO_SANDBOX=1 runs the code unsandboxed and shows a warning."
    )


def _report_dir_names(run_id: str, folder: str | None = None, rec: dict | None = None) -> list[str]:
    """Candidate directory names under reports/daily/<day>/ for this run."""
    names: list[str] = []
    if folder:
        names.append(Path(folder).name)
    names.append(run_id)
    if rec:
        try:
            from reports.pr_report import normalize
            from reports.pr_report import run_id as pr_run_id
            names.append(pr_run_id(normalize(rec, Path(folder).name if folder else None)))
        except Exception:  # noqa: BLE001
            pass
        pr = rec.get("pr") if isinstance(rec.get("pr"), dict) else {}
        num = pr.get("number")
        repo = str(rec.get("repo") or "")
        lib = rec.get("library") or (repo.split("/")[-1] if repo else "")
        if num is not None and lib:
            names.append(f"{lib}-{num}")
            names.append(f"{str(lib).lower().replace('-', '_')}-{num}")
    # unique, preserve order
    out: list[str] = []
    seen: set[str] = set()
    for n in names:
        if n and n not in seen:
            seen.add(n)
            out.append(n)
    return out


def find_reviewer_report_file(run_id: str, ext: str, *,
                              folder: str | None = None, rec: dict | None = None) -> Path | None:
    """Locate REPORT.pdf|html written by reports/pr_report.render_run."""
    if ext not in ("pdf", "html", "md"):
        return None
    names = _report_dir_names(run_id, folder, rec)
    if not REPORTS_DAILY.is_dir():
        return None
    for name in names:
        for cand in REPORTS_DAILY.glob(f"*/{name}/REPORT.{ext}"):
            if cand.is_file() and cand.stat().st_size > 0:
                return cand
    want = set(names)
    for cand in REPORTS_DAILY.rglob(f"REPORT.{ext}"):
        if cand.parent.name in want and cand.is_file() and cand.stat().st_size > 0:
            return cand
    return None


def report_links(run_id: str, *, folder: str | None = None, rec: dict | None = None) -> dict[str, str | None]:
    """Public API paths for golden-format reviewer reports (None if not generated yet)."""
    from urllib.parse import quote

    q = quote(run_id, safe="")
    pdf = find_reviewer_report_file(run_id, "pdf", folder=folder, rec=rec)
    html = find_reviewer_report_file(run_id, "html", folder=folder, rec=rec)
    return {
        "report_pdf": f"/api/runs/{q}/report.pdf" if pdf else None,
        "report_html": f"/api/runs/{q}/report.html" if html else None,
    }


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def set_run_owner(folder: Path, owner: str) -> None:
    """Sidecar only. The observation record itself is not given an owner field."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / OWNER_FILE
    path.write_text(str(owner).strip() + "\n")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def read_run_owner(folder: Path | None) -> str | None:
    if folder is None:
        return None
    try:
        text = (Path(folder) / OWNER_FILE).read_text().strip()
    except OSError:
        return None
    return text or None


def _visible(owner_id: str | None, *, viewer: str | None, admin: bool) -> bool:
    """No viewer means a unit test listing every run. An admin sees unowned runs too."""
    if admin:
        return True
    if viewer is None:
        return True
    return bool(owner_id) and owner_id == viewer


def _row_from_record(rec: dict, path: Path | None = None) -> dict:
    rid = rec.get("id") or (path.parent.name if path else "unknown")
    pr = rec.get("pr") if isinstance(rec.get("pr"), dict) else {}
    folder = _display_path(path.parent) if path else f"(memory)/{rid}"
    links = report_links(str(rid), folder=folder if path else None, rec=rec)
    return {
        "id": rid,
        "repo": rec.get("repo"),
        "pr": pr.get("number"),
        "url": pr.get("url"),
        "title": (pr.get("title") or rec.get("title")),
        "verdict": rec.get("verdict"),
        "reason": (rec.get("reason") or "")[:240],
        "tested_at_ist": rec.get("tested_at_ist") or rec.get("date_ist"),
        "machine": rec.get("machine") or "local",
        "path": _display_path(path) if path else None,
        "folder": folder,
        "source": "disk" if path else "memory",
        "report_pdf": links["report_pdf"],
        "report_html": links["report_html"],
    }



def remember_run(rec: dict, path: Path | None = None, *, owner: str | None = None) -> dict:
    """Keep a finished PR record in RAM so the console still lists it after Render wipes disk."""
    row = _row_from_record(rec, path)
    rid = row["id"]
    hosted = HOSTED / f"{rid}.html"
    links = report_links(rid, folder=row["folder"], rec=rec)
    if owner is None and path is not None:
        owner = read_run_owner(path.parent)
    snap = {
        "row": row,
        "record": rec,
        "folder": row["folder"],
        "owner": owner,
        "hosted_report": _display_path(hosted) if hosted.is_file() else None,
        "report_pdf": links.get("report_pdf"),
        "report_html": links.get("report_html"),
        "saved_at": time.time(),
    }
    with _jobs_lock:
        _recent_runs[rid] = snap
        while len(_recent_runs) > _RECENT_MAX:
            oldest = min(_recent_runs.items(), key=lambda kv: kv[1].get("saved_at") or 0)
            _recent_runs.pop(oldest[0], None)
    return row


def list_runs(limit: int = 50, owner: str | None = None, *, admin: bool = False) -> list[dict]:
    """Newest `limit` runs only. Does not remember_run every record on each list (disk scan is mtime-bounded).

    ``owner=None`` and ``admin=False`` is the unfiltered list used by unit tests.
    """
    candidates: list[tuple[float, Path]] = []
    if RUNS_ROOT.is_dir():
        for path in RUNS_ROOT.rglob("record.json"):
            try:
                mtime = path.stat().st_mtime
            except OSError:
                continue
            candidates.append((mtime, path))
    candidates.sort(key=lambda x: x[0], reverse=True)

    rows: list[tuple[float, dict]] = []
    seen: set[str] = set()
    # A signed-in list has to see past other people's runs, so it scans the whole tree.
    pool = candidates if (owner is not None or admin) else candidates[: max(limit, 1) * 2]
    for mtime, path in pool:
        # Read a small multiple of limit to skip non-pr_run records without scanning the whole tree into RAM.
        if len(rows) >= limit:
            break
        try:
            rec = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        if rec.get("record_kind") and rec.get("record_kind") != "pr_run":
            continue
        if not _visible(read_run_owner(path.parent), viewer=owner, admin=admin):
            continue
        row = dict(_row_from_record(rec, path))
        seen.add(row["id"])
        rows.append((mtime, row))

    with _jobs_lock:
        mem = list(_recent_runs.values())
    for snap in mem:
        row = snap["row"]
        if row["id"] in seen:
            continue
        if not _visible(snap.get("owner") or (read_run_owner(Path(snap["folder"])) if snap.get("folder") else None),
                       viewer=owner, admin=admin):
            continue
        rows.append((float(snap.get("saved_at") or 0), dict(row)))
    rows.sort(key=lambda x: x[0], reverse=True)
    return [r for _, r in rows[:limit]]


def _tail_bytes(path: Path, n: int = 8192) -> str:
    try:
        data = path.read_bytes()
    except OSError:
        return ""
    if len(data) > n:
        data = data[-n:]
    return data.decode("utf-8", errors="replace")


def submit_job_scenarios(job_id: str, body: dict) -> dict:
    """Validate business answers and write hitl_approval.json for a live job."""
    from poc import hitl

    with _jobs_lock:
        job = _jobs.get(job_id)
        if not job:
            raise KeyError("job not found")
        hitl_path = job.get("hitl_dir")
    if not hitl_path:
        raise ValueError("job has no HITL directory")
    hdir = Path(hitl_path)
    draft = hitl.read_draft(hdir)
    if not draft:
        raise ValueError("no hitl_draft.json yet — wait until claims/probes are drafted")
    err = hitl.validate_approval(draft, body)
    if err:
        raise ValueError(err)
    return hitl.write_approval(hdir, body)


def get_run(run_id: str, owner: str | None = None, *, admin: bool = False) -> dict | None:
    run_id = unquote(run_id)
    for path in RUNS_ROOT.rglob("record.json") if RUNS_ROOT.is_dir() else []:
        try:
            rec = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        if rec.get("id") == run_id or path.parent.name == run_id:
            if not _visible(read_run_owner(path.parent), viewer=owner, admin=admin):
                return None
            remember_run(rec, path)
            rid = str(rec.get("id") or run_id)
            folder = _display_path(path.parent)
            hosted = HOSTED / f"{rid}.html"
            links = report_links(rid, folder=folder, rec=rec)
            return {
                "record": rec,
                "path": _display_path(path),
                "folder": folder,
                "hosted_report": _display_path(hosted) if hosted.is_file() else None,
                **links,
            }
    with _jobs_lock:
        snap = _recent_runs.get(run_id)
    if snap:
        if not _visible(snap.get("owner"), viewer=owner, admin=admin):
            return None
        links = report_links(run_id, folder=snap.get("folder"), rec=snap.get("record"))
        return {
            "record": snap["record"],
            "path": snap["row"].get("path"),
            "folder": snap["folder"],
            "hosted_report": snap.get("hosted_report"),
            "report_pdf": links.get("report_pdf") or snap.get("report_pdf"),
            "report_html": links.get("report_html") or snap.get("report_html"),
            "source": "memory",
        }
    return None


def job_log_and_error(stdout: str, stderr: str, returncode: int) -> tuple[str, str | None]:
    """Build a useful log tail; prefer stderr / Stopped lines when the process failed."""
    out, err = (stdout or "").strip(), (stderr or "").strip()
    parts: list[str] = []
    if returncode and err:
        parts.append("--- stderr ---\n" + err[-3500:])
    if out:
        parts.append("--- stdout ---\n" + out[-3500:])
    elif err and not parts:
        parts.append(err[-4000:])
    tail = "\n\n".join(parts)[-6000:]
    reason = None
    for line in (err + "\n" + out).splitlines():
        s = line.strip()
        if s.startswith("Stopped:") or "PR selection failed" in s or "harness error" in s:
            reason = s
    m = _RUN_LOG_RE.search(out + "\n" + err)
    if m:
        meta_path = Path(m.group(1)) / "run_meta.json"
        try:
            meta = json.loads(meta_path.read_text())
            probs = meta.get("problems") or []
            if probs and not reason:
                reason = "; ".join(str(p) for p in probs[:5])
        except (OSError, json.JSONDecodeError):
            pass
    if returncode and not reason:
        reason = f"check exited {returncode} (see log tail)"
    return tail, reason


def find_record_for_pr(repo: str, pr: int) -> tuple[dict, Path] | None:
    """Newest matching pr_run record on disk for this repo/PR."""
    best: tuple[float, dict, Path] | None = None
    if not RUNS_ROOT.is_dir():
        return None
    for path in RUNS_ROOT.rglob("record.json"):
        try:
            rec = json.loads(path.read_text())
            mtime = path.stat().st_mtime
        except (OSError, json.JSONDecodeError):
            continue
        if rec.get("record_kind") and rec.get("record_kind") != "pr_run":
            continue
        if rec.get("repo") != repo:
            continue
        prd = rec.get("pr") if isinstance(rec.get("pr"), dict) else {}
        if prd.get("number") != pr:
            continue
        if best is None or mtime > best[0]:
            best = (mtime, rec, path)
    if not best:
        return None
    return best[1], best[2]


def _descendant_pids(pid: int) -> list[int]:
    """Deepest children first. Pytest starts its own session, so killing the console group is not enough."""
    ordered: list[int] = []

    def walk(parent: int) -> None:
        try:
            out = subprocess.check_output(["ps", "-o", "pid=", "--ppid", str(parent)], text=True, timeout=5)
        except (OSError, subprocess.SubprocessError):
            return
        for token in out.split():
            if token.isdigit():
                child = int(token)
                walk(child)
                ordered.append(child)

    walk(pid)
    return ordered


def _kill_process_group(pid: int) -> None:
    for child in _descendant_pids(pid):
        try:
            os.kill(child, signal.SIGKILL)
        except OSError:
            pass
    try:
        os.killpg(pid, signal.SIGKILL)
    except OSError:
        try:
            os.kill(pid, signal.SIGKILL)
        except OSError:
            pass


def _read_child(proc: subprocess.Popen, logf, collected: list[str], deadline: float) -> tuple[int, bool]:
    """Read stdout until the child exits or the deadline. A silent child still hits the deadline.

    A stand-in process with no real pipe (tests) is read line by line, the same as before the deadline existed.
    """
    assert proc.stdout is not None
    try:
        fd = proc.stdout.fileno()
    except (AttributeError, OSError, ValueError):
        fd = None
    if not isinstance(fd, int) or fd < 0:
        for line in proc.stdout:
            logf.write(line)
            logf.flush()
            collected.append(line)
            if len(collected) > 4000:
                del collected[:-2000]
        return proc.wait(), False
    while True:
        if time.monotonic() >= deadline:
            _kill_process_group(proc.pid)
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)
            return proc.returncode if proc.returncode is not None else -9, True
        remaining = max(0.0, deadline - time.monotonic())
        ready, _, _ = select.select([fd], [], [], min(1.0, remaining))
        if not ready:
            if proc.poll() is not None:
                break
            continue
        line = proc.stdout.readline()
        if line == "":
            break
        logf.write(line)
        logf.flush()
        collected.append(line)
        if len(collected) > 4000:
            del collected[:-2000]
    return proc.wait(), False


def start_check(pr_url: str, *, model_provider: str = "nebius", owner: str | None = None) -> dict:
    from poc import run_progress, spaces_host

    m = PR_RE.search(pr_url.strip())
    if not m:
        raise ValueError("pr_url must look like https://github.com/owner/repo/pull/123")
    blocked = spaces_host.block_reason(pr_url, model_provider)
    if blocked:
        raise ValueError(blocked)
    playback = spaces_host.playback_only(pr_url, model_provider)
    flags, run_note = console_run_flags()
    if playback:
        # Playback reads a saved sample. It does not clone or run pull-request code.
        flags, run_note = [], spaces_host.SPACES_MESSAGE
    else:
        refused = blocks_unsandboxed_run(flags, run_note)
        if refused:
            raise ValueError(refused)
    job_id = uuid.uuid4().hex[:12]
    # Tests retarget REPO_ROOT. POC_OPS_RUNS (a Space home directory) wins when it is set.
    if (os.environ.get("POC_OPS_RUNS") or "").strip():
        jobs_dir = RUNS_ROOT / "_jobs" / job_id
    else:
        jobs_dir = REPO_ROOT / "ops" / "runs" / "_jobs" / job_id
    jobs_dir.mkdir(parents=True, exist_ok=True)
    progress_path = jobs_dir / "progress.jsonl"
    console_log = jobs_dir / "console.log"
    hitl_dir = jobs_dir
    if progress_path.exists():
        progress_path.unlink()
    if console_log.exists():
        console_log.unlink()
    job = {
        "id": job_id,
        "status": "queued",
        "pr_url": pr_url.strip(),
        "repo": m.group(1),
        "pr": int(m.group(2)),
        "model_provider": model_provider,
        "owner": owner,
        "playback": playback,
        "run_flags": list(flags),
        "run_note": run_note,
        "started_at": None,
        "finished_at": None,
        "exit": None,
        "error": None,
        "warning": None,
        "run_id": None,
        "log_tail": "",
        "progress_path": str(progress_path),
        "console_log": str(console_log),
        "hitl_dir": str(hitl_dir),
        "stages": [],
        "current_stage": "queued",
        "current_agent": None,
        "current_detail": None,
        "swarm": {"ultra": "idle", "lightning": "idle", "super": "idle"},
    }
    with _jobs_lock:
        _jobs[job_id] = job
    # Seed progress file so UI shows queued before the child starts.
    prev = os.environ.get("POC_PROGRESS_PATH")
    os.environ["POC_PROGRESS_PATH"] = str(progress_path)
    try:
        run_progress.emit("queued", detail=f"{m.group(1)}#{m.group(2)}")
    finally:
        if prev is None:
            os.environ.pop("POC_PROGRESS_PATH", None)
        else:
            os.environ["POC_PROGRESS_PATH"] = prev

    def work():
        from poc import run_progress as rp

        env = os.environ.copy()
        env["POC_PROGRESS_PATH"] = str(progress_path)
        # The console asks for operator approval and turns the advisory swarm on itself.
        # --console-job is what lets this single pull-request check start. POC_CONSOLE does not.
        env["POC_HITL"] = "1"
        env["POC_HITL_DIR"] = str(hitl_dir)
        env["POC_CONSOLE"] = "1"
        env["POC_SWARM"] = "1"
        with _jobs_lock:
            job["status"] = "running"
            job["started_at"] = time.time()
        os.environ["POC_PROGRESS_PATH"] = str(progress_path)
        if job.get("playback"):
            try:
                rec = spaces_host.play(lambda stage, detail=None: rp.emit(stage, detail=detail))
                folder = RUNS_ROOT / "playback" / "mlxtend-1229"
                folder.mkdir(parents=True, exist_ok=True)
                (folder / "record.json").write_text(json.dumps(rec))
                if owner:
                    set_run_owner(folder, owner)
                saved = (remember_run(rec, folder / "record.json", owner=owner), rec)
                with _jobs_lock:
                    row, stored = saved
                    job["status"] = "done"
                    job["exit"] = 0
                    job["finished_at"] = time.time()
                    job["run_id"] = row["id"]
                    job["record"] = stored
                    job["folder"] = row["folder"]
                    job["log_tail"] = "Playback of the vetted sample. No pull-request code ran.\n"
                    job.update(report_links(row["id"], folder=row["folder"], rec=stored))
            except Exception as e:  # noqa: BLE001
                rp.emit("failed", detail=f"{type(e).__name__}: {e}"[:200])
                with _jobs_lock:
                    job["status"] = "failed"
                    job["error"] = f"{type(e).__name__}: {e}"
                    job["finished_at"] = time.time()
            return
        rp.emit("fetch_pr", detail="loading pull request")
        flags, note = job.get("run_flags") or [], job.get("run_note")
        if flags is None:
            flags, note = console_run_flags()
        if note:
            with _jobs_lock:
                job["run_note"] = note
                job["warning"] = note if note and "unsafe" in note.lower() else job.get("warning")
            rp.emit("fetch_pr", detail=note[:200])
        refused = blocks_unsandboxed_run(list(flags), note)
        if refused:
            with _jobs_lock:
                job["status"] = "failed"
                job["error"] = refused
                job["finished_at"] = time.time()
            rp.emit("failed", detail=refused[:200])
            return
        child_flags = list(flags)
        child_flags.extend(recorded_demo_flags(model_provider))
        if model_provider == "recorded":
            env["POC_SKIP_COVERAGE"] = "1"
        argv = console_daily_run_argv(pr_url, model_provider, child_flags)
        try:
            # Live tee: write console.log while the check runs; polls read the last ~8KB.
            collected: list[str] = []
            with console_log.open("w", encoding="utf-8") as logf:
                proc = subprocess.Popen(
                    argv, cwd=str(REPO_ROOT), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, env=env, bufsize=1, start_new_session=True,
                )
                returncode, timed_out = _read_child(
                    proc, logf, collected, time.monotonic() + CONSOLE_JOB_TIMEOUT_S,
                )
            stdout_blob = "".join(collected)
            tail, fail_reason = job_log_and_error(stdout_blob, "", returncode)
            if timed_out:
                fail_reason = "timed out"
            # Prefer file tail so the UI matches what was teed.
            file_tail = _tail_bytes(console_log, 8192)
            if file_tail:
                tail = file_tail
            os.environ["POC_PROGRESS_PATH"] = str(progress_path)
            found = find_record_for_pr(m.group(1), int(m.group(2)))
            # A written record means the check produced analysis — surface it even if exit!=0 (problems list).
            ok = (returncode == 0 or found is not None) and not timed_out
            if timed_out:
                rp.emit("failed", detail="timed out")
            elif ok:
                rp.emit("done", detail="check finished" if returncode == 0 else "finished with problems")
            else:
                rp.emit("failed", detail=(fail_reason or f"exit {returncode}")[:200])
            # remember_run takes _jobs_lock — must not run while we hold it (deadlocks Lock).
            saved = None
            if found:
                rec, path = found
                if owner:
                    set_run_owner(path.parent, owner)
                saved = (remember_run(rec, path, owner=owner), rec)
            with _jobs_lock:
                job["exit"] = returncode
                job["log_tail"] = tail
                job["status"] = "timed out" if timed_out else ("done" if ok else "failed")
                job["finished_at"] = time.time()
                if fail_reason and not ok:
                    job["error"] = fail_reason
                elif fail_reason and returncode != 0:
                    job["warning"] = fail_reason
                if saved:
                    row, rec = saved
                    job["run_id"] = row["id"]
                    job["record"] = rec
                    job["folder"] = row["folder"]
                    job.update(report_links(row["id"], folder=row["folder"], rec=rec))
        except Exception as e:  # noqa: BLE001
            os.environ["POC_PROGRESS_PATH"] = str(progress_path)
            rp.emit("failed", detail=f"{type(e).__name__}: {e}"[:200])
            with _jobs_lock:
                job["status"] = "failed"
                job["error"] = f"{type(e).__name__}: {e}"
                job["finished_at"] = time.time()

    threading.Thread(target=work, daemon=True).start()
    return _job_public(job)


def _job_public(job: dict) -> dict:
    from poc import hitl, run_progress

    out = dict(job)
    prog = run_progress.job_progress(job.get("progress_path"))
    out.update(prog)
    # Live log: last ~8KB of the teed console.log on every poll.
    clog = job.get("console_log")
    if clog:
        live = _tail_bytes(Path(clog), 8192)
        if live:
            out["log_tail"] = live
    hdir = job.get("hitl_dir")
    if hdir:
        draft = hitl.read_draft(Path(hdir))
        if draft:
            out["hitl_draft"] = draft
        approval = hitl.read_approval(Path(hdir))
        if approval:
            out["hitl_approval"] = approval
        # Surface mid-check pause even while the worker thread is blocked in wait_for_approval.
        if draft and not approval and out.get("status") not in ("done", "failed"):
            out["status"] = "awaiting_human"
            if out.get("current_stage") != "await_human":
                out["current_stage"] = "await_human"
    out.pop("progress_path", None)
    out.pop("console_log", None)
    out.pop("hitl_dir", None)
    out.pop("owner", None)
    return out


def get_job(job_id: str, owner: str | None = None, *, admin: bool = False) -> dict | None:
    with _jobs_lock:
        j = _jobs.get(job_id)
        if not j:
            return None
        if not _visible(j.get("owner"), viewer=owner, admin=admin):
            return None
        return _job_public(j)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _json(self, code: int, obj: Any, cookies: list[str] | None = None):
        body = json.dumps(obj, default=str).encode()
        self.send_response(code)
        self._cors()
        for cookie in cookies or []:
            self.send_header("Set-Cookie", cookie)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _redirect(self, code: int, location: str, cookies: list[str] | None = None):
        self.send_response(code)
        self._cors()
        for cookie in cookies or []:
            self.send_header("Set-Cookie", cookie)
        self.send_header("Location", location)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _auth(self, method: str, body: dict | None) -> bool:
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        if not path.startswith("/api/auth"):
            return False
        from poc import console_auth
        result = console_auth.handle_request(
            method, path, parse_qs(parsed.query), body, self.headers,
            host=self.headers.get("Host"), proto=self.headers.get("X-Forwarded-Proto"),
        )
        if result.location:
            self._redirect(result.status, result.location, result.cookies)
        else:
            self._json(result.status, result.body if result.body is not None else {}, result.cookies)
        return True

    def _viewer(self) -> dict | None:
        from poc import console_auth
        account = console_auth.service_from_env().account_for_session(
            console_auth.cookie_value(self.headers.get("Cookie"), console_auth.SESSION_COOKIE),
        )
        if not account:
            self._json(401, {"error": "Sign in first."})
            return None
        return account

    def _file(self, path: Path, content_type: str):
        data = path.read_bytes()
        self.send_response(200)
        self._cors()
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_OPTIONS(self):  # noqa: N802
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self):  # noqa: N802
        from poc.pr_text import github_read_token as _github_read_token
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        if self._auth("GET", None):
            return

        if path == "/api/health":
            flags, note = console_run_flags()
            from poc import spaces_host
            spaces_note = spaces_host.health_note()
            if spaces_note:
                note = spaces_note
                flags = []
            chrome = None
            try:
                from reports.reviewer import find_chrome
                chrome = find_chrome()
            except Exception:  # noqa: BLE001
                chrome = None
            return self._json(200, {
                "ok": True,
                "service": "proof-of-change-console",
                "build": "report-pdf-v7",
                "has_git": (REPO_ROOT / ".git").is_dir(),
                "github_token": bool(_github_read_token()),
                "poc_commit_env": bool(
                    (os.environ.get("POC_COMMIT") or os.environ.get("RENDER_GIT_COMMIT") or "").strip()),
                "chrome": bool(chrome),
                "contree_ready": contree_usable(),
                "run_flags": flags,
                "run_note": note,
            })
        if path.startswith("/api"):
            account = self._viewer()
            if not account:
                return None
            admin = account.get("role") == "admin"
            viewer = None if admin else account["id"]
            if path == "/api/runs":
                return self._json(200, {"runs": list_runs(owner=viewer, admin=admin)})
            rm = _REPORT_FILE_RE.match(path)
            if rm:
                rid, ext = unquote(rm.group(1)), rm.group(2)
                got = get_run(rid, owner=viewer, admin=admin)
                if not got:
                    return self._json(404, {"error": "not found"})
                folder = got.get("folder")
                rec = got.get("record")
                fpath = find_reviewer_report_file(rid, ext, folder=folder, rec=rec)
                if not fpath:
                    return self._json(404, {"error": f"REPORT.{ext} not found"})
                ctype = "application/pdf" if ext == "pdf" else "text/html; charset=utf-8"
                return self._file(fpath, ctype)
            if path.startswith("/api/runs/"):
                rid = path[len("/api/runs/"):]
                got = get_run(rid, owner=viewer, admin=admin)
                if not got:
                    return self._json(404, {"error": "not found"})
                return self._json(200, got)
            if path.startswith("/api/jobs/"):
                jid = path[len("/api/jobs/"):]
                job = get_job(jid, owner=viewer, admin=admin)
                if not job:
                    return self._json(404, {"error": "not found"})
                return self._json(200, job)
            return self._json(404, {"error": "not found"})

        # static SPA
        if WEB_DIST.is_dir():
            rel = path.lstrip("/") or "index.html"
            cand = (WEB_DIST / rel).resolve()
            if not str(cand).startswith(str(WEB_DIST.resolve())):
                return self._json(400, {"error": "bad path"})
            if cand.is_file():
                ctype = "text/html" if cand.suffix == ".html" else (
                    "application/javascript" if cand.suffix in (".js", ".mjs") else
                    "text/css" if cand.suffix == ".css" else "application/octet-stream")
                return self._file(cand, ctype)
            index = WEB_DIST / "index.html"
            if index.is_file() and not path.startswith("/api"):
                return self._file(index, "text/html")
        return self._json(404, {"error": "not found", "hint": "build console/web (npm run build) or use Vite on :5173"})

    def do_POST(self):  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            body = json.loads(raw.decode() or "{}")
        except json.JSONDecodeError:
            return self._json(400, {"error": "bad json"})
        if self._auth("POST", body if isinstance(body, dict) else {}):
            return None
        account = self._viewer()
        if not account:
            return None
        admin = account.get("role") == "admin"
        viewer = None if admin else account["id"]
        if path == "/api/checks":
            pr_url = (body.get("pr_url") or "").strip()
            provider = (body.get("model_provider") or "nebius").strip() or "nebius"
            try:
                job = start_check(pr_url, model_provider=provider, owner=account["id"])
            except ValueError as e:
                return self._json(400, {"error": str(e)})
            return self._json(202, job)
        if path.startswith("/api/jobs/") and path.endswith("/scenarios"):
            jid = path[len("/api/jobs/"):-len("/scenarios")].strip("/")
            if get_job(jid, owner=viewer, admin=admin) is None:
                return self._json(404, {"error": "not found"})
            try:
                approval = submit_job_scenarios(jid, body)
            except KeyError:
                return self._json(404, {"error": "not found"})
            except ValueError as e:
                return self._json(400, {"error": str(e)})
            return self._json(200, {"ok": True, "approval": approval})
        return self._json(404, {"error": "not found"})


def serve(host: str = "127.0.0.1", port: int = 8787) -> None:
    httpd = ThreadingHTTPServer((host, port), Handler)
    print(f"Proof-of-Change console API http://{host}:{port}  (UI: Vite :5173 or {WEB_DIST})", flush=True)
    httpd.serve_forever()


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="Proof-of-Change operator console API")
    ap.add_argument("--host", default=os.environ.get("POC_CONSOLE_HOST", "127.0.0.1"))
    ap.add_argument("--port", type=int, default=int(os.environ.get("POC_CONSOLE_PORT", "8787")))
    a = ap.parse_args(argv)
    serve(a.host, a.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
