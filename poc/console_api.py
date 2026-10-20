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
import subprocess
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

REPO_ROOT = Path(__file__).resolve().parent.parent
RUNS_ROOT = Path(os.environ.get("POC_OPS_RUNS", REPO_ROOT / "ops" / "runs"))
HOSTED = REPO_ROOT / "reports" / "hosted"
REPORTS_DAILY = REPO_ROOT / "reports" / "daily"
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


def console_run_flags() -> tuple[list[str], str | None]:
    """Extra daily_run flags for hosted console (Render blocks bwrap uid maps).

    Prefer Contree when it can actually run. Otherwise, if bubblewrap cannot start here,
    pass --unsafe-no-sandbox so a public-PR demo can still run (recorded in the job note).
    Set POC_UNSAFE_NO_SANDBOX=0 to refuse instead of falling back.
    """
    if contree_usable():
        # Contree is remote; also disable the local bwrap gate (Render blocks uid maps).
        # If Contree checkpoints fail mid-run, daily_run falls back to local — unsafe keeps that path alive.
        return (["--sandbox-backend", "contree", "--unsafe-no-sandbox"],
                "using Contree sandboxes (local bwrap skipped)")
    refuse = (os.environ.get("POC_UNSAFE_NO_SANDBOX") or "").strip().lower() in ("0", "false", "no")
    force = (os.environ.get("POC_UNSAFE_NO_SANDBOX") or "").strip().lower() in ("1", "true", "yes")
    ok = False
    why = "sandbox check skipped"
    try:
        from guardrails import sandbox
        ok, why = sandbox.check()
    except Exception as e:  # noqa: BLE001
        ok, why = False, f"{type(e).__name__}: {e}"
    if ok and not force:
        return [], None
    if refuse:
        return [], (
            f"sandbox unavailable ({why}); install contree-sdk + NEBIUS_PROJECT_ID, "
            "or set POC_UNSAFE_NO_SANDBOX=1"
        )
    # ponytail: auto unsafe on PaaS without working Contree/bwrap — console motif requires a runnable path
    return ["--unsafe-no-sandbox"], f"sandbox unavailable ({why}); running with --unsafe-no-sandbox"


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


def _row_from_record(rec: dict, path: Path | None = None) -> dict:
    rid = rec.get("id") or (path.parent.name if path else "unknown")
    pr = rec.get("pr") if isinstance(rec.get("pr"), dict) else {}
    folder = str(path.parent.relative_to(REPO_ROOT)) if path else f"(memory)/{rid}"
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
        "path": str(path.relative_to(REPO_ROOT)) if path else None,
        "folder": folder,
        "source": "disk" if path else "memory",
        "report_pdf": links["report_pdf"],
        "report_html": links["report_html"],
    }



def run_owner_of(folder: Path) -> str | None:
    try:
        text = (folder / "console_owner.txt").read_text().strip()
    except OSError:
        return None
    return text or None


def set_run_owner(folder: Path, owner: str) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "console_owner.txt").write_text(owner + "\n")


def _can_see(owner: str | None, account: dict | None) -> bool:
    """account None keeps the old unfiltered helpers for tests. The HTTP API always passes an account."""
    if account is None:
        return True
    if account.get("role") == "admin":
        return True
    return bool(owner) and owner == account.get("id")


def remember_run(rec: dict, path: Path | None = None, *, owner: str | None = None) -> dict:
    """Keep a finished PR record in RAM so the console still lists it after Render wipes disk."""
    row = _row_from_record(rec, path)
    if owner:
        row["owner"] = owner
    elif path is not None:
        stamp = run_owner_of(path.parent)
        if stamp:
            row["owner"] = stamp
    rid = row["id"]
    hosted = HOSTED / f"{rid}.html"
    links = report_links(rid, folder=row["folder"], rec=rec)
    snap = {
        "row": row,
        "record": rec,
        "folder": row["folder"],
        "hosted_report": str(hosted.relative_to(REPO_ROOT)) if hosted.is_file() else None,
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


def list_runs(limit: int = 50, account: dict | None = None) -> list[dict]:
    """Newest `limit` runs only. Does not remember_run every record on each list (disk scan is mtime-bounded).

    When `account` is set, a normal user only gets runs they started. An admin also
    sees older runs that have no owner. Unset `account` is the unfiltered helper.
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
    pool = candidates if account is not None else candidates[: max(limit, 1) * 2]
    for mtime, path in pool:
        if len(rows) >= limit:
            break
        try:
            rec = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        if rec.get("record_kind") and rec.get("record_kind") != "pr_run":
            continue
        row = _row_from_record(rec, path)
        stamp = run_owner_of(path.parent)
        if stamp:
            row["owner"] = stamp
        if not _can_see(row.get("owner"), account):
            continue
        seen.add(row["id"])
        rows.append((mtime, row))

    with _jobs_lock:
        mem = list(_recent_runs.values())
    for snap in mem:
        row = snap["row"]
        if row["id"] in seen:
            continue
        if not _can_see(row.get("owner"), account):
            continue
        rows.append((float(snap.get("saved_at") or 0), row))
    rows.sort(key=lambda x: x[0], reverse=True)
    # Copies so a caller can drop the owner field without wiping the in-memory stamp.
    return [dict(row) for _, row in rows[:limit]]


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


def get_run(run_id: str, account: dict | None = None) -> dict | None:
    run_id = unquote(run_id)
    for path in RUNS_ROOT.rglob("record.json") if RUNS_ROOT.is_dir() else []:
        try:
            rec = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        if rec.get("id") == run_id or path.parent.name == run_id:
            stamp = run_owner_of(path.parent)
            if not _can_see(stamp, account):
                return None
            remember_run(rec, path, owner=stamp)
            rid = str(rec.get("id") or run_id)
            folder = str(path.parent.relative_to(REPO_ROOT))
            hosted = HOSTED / f"{rid}.html"
            links = report_links(rid, folder=folder, rec=rec)
            return {
                "record": rec,
                "path": str(path.relative_to(REPO_ROOT)),
                "folder": folder,
                "hosted_report": str(hosted.relative_to(REPO_ROOT)) if hosted.is_file() else None,
                **links,
            }
    with _jobs_lock:
        snap = _recent_runs.get(run_id)
    if snap:
        if not _can_see(snap["row"].get("owner"), account):
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


def start_check(pr_url: str, *, model_provider: str = "nebius", owner: str | None = None) -> dict:
    from poc import run_progress

    m = PR_RE.search(pr_url.strip())
    if not m:
        raise ValueError("pr_url must look like https://github.com/owner/repo/pull/123")
    job_id = uuid.uuid4().hex[:12]
    jobs_dir = REPO_ROOT / "ops" / "runs" / "_jobs" / job_id
    jobs_dir.mkdir(parents=True, exist_ok=True)
    progress_path = jobs_dir / "progress.jsonl"
    console_log = jobs_dir / "console.log"
    hitl_dir = jobs_dir
    if progress_path.exists():
        progress_path.unlink()
    if console_log.exists():
        console_log.unlink()
    flags, run_note = console_run_flags()
    job = {
        "id": job_id,
        "status": "queued",
        "pr_url": pr_url.strip(),
        "repo": m.group(1),
        "pr": int(m.group(2)),
        "model_provider": model_provider,
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
        "owner": owner,
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
        # Console always enables HITL mid-check; bench/CLI leave these unset.
        env["POC_HITL"] = "1"
        env["POC_HITL_DIR"] = str(hitl_dir)
        with _jobs_lock:
            job["status"] = "running"
            job["started_at"] = time.time()
        os.environ["POC_PROGRESS_PATH"] = str(progress_path)
        rp.emit("fetch_pr", detail="loading pull request")
        flags, note = job.get("run_flags") or [], job.get("run_note")
        if flags is None:
            flags, note = console_run_flags()
        if note:
            with _jobs_lock:
                job["run_note"] = note
                job["warning"] = note if "unsafe" in note.lower() else job.get("warning")
            rp.emit("fetch_pr", detail=note[:200])
        argv = [str(REPO_ROOT / ".venv" / "bin" / "python"), str(REPO_ROOT / "ops" / "daily_run.py"),
                "--pr", pr_url.strip(), "--model-provider", model_provider, *flags]
        if not (REPO_ROOT / ".venv" / "bin" / "python").is_file():
            argv[0] = os.environ.get("PYTHON", "python3")
        try:
            # Live tee: write console.log while the check runs; polls read the last ~8KB.
            collected: list[str] = []
            with console_log.open("w", encoding="utf-8") as logf:
                proc = subprocess.Popen(
                    argv, cwd=str(REPO_ROOT), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, env=env, bufsize=1,
                )
                assert proc.stdout is not None
                for line in proc.stdout:
                    logf.write(line)
                    logf.flush()
                    collected.append(line)
                    if len(collected) > 4000:
                        collected = collected[-2000:]
                returncode = proc.wait()
            stdout_blob = "".join(collected)
            tail, fail_reason = job_log_and_error(stdout_blob, "", returncode)
            # Prefer file tail so the UI matches what was teed.
            file_tail = _tail_bytes(console_log, 8192)
            if file_tail:
                tail = file_tail
            os.environ["POC_PROGRESS_PATH"] = str(progress_path)
            found = find_record_for_pr(m.group(1), int(m.group(2)))
            # A written record means the check produced analysis — surface it even if exit!=0 (problems list).
            ok = returncode == 0 or found is not None
            if ok:
                rp.emit("done", detail="check finished" if returncode == 0 else "finished with problems")
            else:
                rp.emit("failed", detail=(fail_reason or f"exit {returncode}")[:200])
            # remember_run takes _jobs_lock — must not run while we hold it (deadlocks Lock).
            saved = None
            if found:
                rec, path = found
                if job.get("owner"):
                    set_run_owner(path.parent, job["owner"])
                saved = (remember_run(rec, path, owner=job.get("owner")), rec)
            with _jobs_lock:
                job["exit"] = returncode
                job["log_tail"] = tail
                job["status"] = "done" if ok else "failed"
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


def get_job(job_id: str, account: dict | None = None) -> dict | None:
    with _jobs_lock:
        j = _jobs.get(job_id)
        if not j:
            return None
        if not _can_see(j.get("owner"), account):
            return None
        return _job_public(j)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-CSRF-Token")

    def _json(self, code: int, obj: Any, *, cookies: list[str] | None = None):
        body = json.dumps(obj, default=str).encode()
        self.send_response(code)
        self._cors()
        for cookie in cookies or []:
            self.send_header("Set-Cookie", cookie)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _secure(self) -> bool:
        from poc.console_accounts import secure_cookie
        return secure_cookie(self.headers.get("X-Forwarded-Proto"))

    def _session_account(self) -> dict | None:
        from poc.console_accounts import SESSION_COOKIE, account_for_session, cookie_value
        return account_for_session(cookie_value(self.headers.get("Cookie"), SESSION_COOKIE))

    def _require_account(self) -> dict | None:
        account = self._session_account()
        if not account:
            self._json(401, {"error": "Sign in first."})
            return None
        return account

    def _require_csrf(self, account: dict) -> bool:
        from poc.console_accounts import CSRF_MESSAGE, session_csrf_ok
        if session_csrf_ok(account, self.headers.get("X-CSRF-Token") or ""):
            return True
        self._json(403, {"error": CSRF_MESSAGE})
        return False

    def _client_ip(self) -> str:
        if self.client_address:
            return str(self.client_address[0])
        return ""

    def _auth_post(self, path: str, body: dict):
        from poc.console_accounts import (
            SESSION_COOKIE,
            AuthError,
            clear_session_cookie,
            cookie_value,
            login,
            logout,
            session_cookie,
            signup,
        )

        header = self.headers.get("X-CSRF-Token") or ""
        try:
            if path == "/api/auth/logout":
                logout(cookie_value(self.headers.get("Cookie"), SESSION_COOKIE))
                return self._json(200, {"ok": True}, cookies=[clear_session_cookie()])
            if path == "/api/auth/signup":
                result = signup(
                    str(body.get("email") or ""),
                    str(body.get("password") or ""),
                    str(body.get("invite") or ""),
                    header,
                )
            else:
                result = login(
                    str(body.get("email") or ""),
                    str(body.get("password") or ""),
                    header,
                    ip=self._client_ip(),
                )
        except AuthError as exc:
            return self._json(exc.status, {"error": str(exc)})
        account = result["account"]
        # The raw session token goes only in the HttpOnly cookie, never in JSON.
        return self._json(
            200,
            {
                "id": account["id"],
                "email": account["email"],
                "role": account["role"],
                "csrf": account["csrf"],
            },
            cookies=[session_cookie(result["session"], secure=self._secure())],
        )

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
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"

        if path == "/api/auth/csrf":
            from poc.console_accounts import AuthError, issue_csrf
            try:
                token = issue_csrf()
            except AuthError as exc:
                return self._json(exc.status, {"error": str(exc)})
            return self._json(200, {"csrf": token})
        if path == "/api/auth/me":
            account = self._session_account()
            if not account:
                return self._json(401, {"error": "Sign in first."})
            return self._json(200, {"id": account["id"], "email": account["email"], "role": account["role"], "csrf": account["csrf"]})

        if path == "/api/health":
            flags, note = console_run_flags()
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
                "github_token": bool(
                    (os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or "").strip()),
                "poc_commit_env": bool(
                    (os.environ.get("POC_COMMIT") or os.environ.get("RENDER_GIT_COMMIT") or "").strip()),
                "chrome": bool(chrome),
                "contree_ready": contree_usable(),
                "run_flags": flags,
                "run_note": note,
            })
        if path.startswith("/api/"):
            account = self._require_account()
            if not account:
                return None
            if path == "/api/runs":
                rows = []
                for row in list_runs(account=account):
                    public = dict(row)
                    public.pop("owner", None)
                    rows.append(public)
                return self._json(200, {"runs": rows})
            rm = _REPORT_FILE_RE.match(path)
            if rm:
                rid, ext = unquote(rm.group(1)), rm.group(2)
                got = get_run(rid, account=account)
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
                got = get_run(rid, account=account)
                if not got:
                    return self._json(404, {"error": "not found"})
                return self._json(200, got)
            if path.startswith("/api/jobs/"):
                jid = path[len("/api/jobs/"):]
                job = get_job(jid, account=account)
                if not job:
                    return self._json(404, {"error": "not found"})
                return self._json(200, job)
            return self._json(404, {"error": "not found"})

        # static SPA — public so the sign-in page can load before a session exists
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
        if path in {"/api/auth/signup", "/api/auth/login", "/api/auth/logout"}:
            return self._auth_post(path, body if isinstance(body, dict) else {})
        account = self._require_account()
        if not account:
            return None
        if not self._require_csrf(account):
            return None
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
            with _jobs_lock:
                owned = _jobs.get(jid)
            if not owned or not _can_see(owned.get("owner"), account):
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
