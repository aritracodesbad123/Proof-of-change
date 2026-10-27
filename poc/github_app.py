"""GitHub App surface for Proof-of-Change (REQUIREMENTS §4 steps 0/10).

Posts only to allowlisted demo/mirror repos (G-ext). Never blocks merges: check runs are
neutral/success advice only. Local HTML reports stay the offline path.

Wire a real App: set GITHUB_APP_INSTALLATION_TOKEN (or App JWT env) + GITHUB_WEBHOOK_SECRET and
POC_DEMO_REPOS=owner/repo,... then: python -m poc.github_app
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any, Callable

DEMO_REPOS_ENV = "POC_DEMO_REPOS"
REPORT_BASE_ENV = "POC_REPORT_BASE_URL"
TOKEN_ENV = "GITHUB_APP_INSTALLATION_TOKEN"
WEBHOOK_SECRET_ENV = "GITHUB_WEBHOOK_SECRET"
API = "https://api.github.com"
PROVE_RE = re.compile(r"^/prove(?:\s+(.+))?$", re.I | re.M)
REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_HOSTED = REPO_ROOT / "reports" / "hosted"


class GitHubAppError(RuntimeError):
    """Safe error for App/post failures; never include tokens or PEM material."""


def demo_repos(env: dict | None = None) -> set[str]:
    env = os.environ if env is None else env
    raw = env.get(DEMO_REPOS_ENV) or ""
    return {r.strip().lower() for r in raw.split(",") if r.strip()}


def may_post(repo: str, env: dict | None = None) -> bool:
    """G-ext: write only to allowlisted demo/mirror repos."""
    return repo.lower() in demo_repos(env)


def verify_webhook(body: bytes, signature: str | None, secret: str | None) -> bool:
    if not secret or not signature:
        return False
    sig = signature.removeprefix("sha256=")
    dig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(dig, sig)


def parse_prove(comment_body: str) -> str | None:
    """Return optional claim text from a /prove comment, or None if not a prove command."""
    m = PROVE_RE.search(comment_body or "")
    if not m:
        return None
    claim = (m.group(1) or "").strip().strip('"').strip("'")
    return claim or ""


def check_run_payload(repo: str, head_sha: str, verdict: str, summary: str, report_url: str | None = None,
                      env: dict | None = None) -> dict:
    """GitHub check-run body. Conclusion is always success/neutral — never failure (non-blocking)."""
    if not may_post(repo, env):
        raise PermissionError(f"refusing to post check run on non-demo repo {repo!r}")
    conclusion = "neutral" if verdict != "verified" else "success"
    body = {
        "name": "Proof-of-Change",
        "head_sha": head_sha,
        "status": "completed",
        "conclusion": conclusion,
        "output": {
            "title": f"Proof-of-Change: {verdict}",
            "summary": (summary or "")[:65000],
        },
    }
    if report_url:
        body["details_url"] = report_url
    return body


def summary_comment(verdict: str, reason: str, report_url: str | None = None, *,
                    pdf_url: str | None = None, pdf_preparing: bool = False, pdf_failed: bool = False) -> str:
    lines = [f"**Proof-of-Change:** `{verdict}`", "", reason or "(no reason)", ""]
    if report_url:
        lines.append(f"[Full report]({report_url})")
    if pdf_url:
        lines.append(f"[PDF report]({pdf_url})")
    elif pdf_failed:
        lines.append(FAILED_TEXT)
    elif pdf_preparing:
        lines.append(PREPARING_TEXT)
    lines.append("_Advice only — this never blocks a merge._")
    return "\n".join(lines)


def handle_event(event: str, payload: dict, env: dict | None = None) -> dict:
    """Dispatcher: returns an action plan; does not call GitHub until apply()."""
    env = os.environ if env is None else env
    repo = ((payload.get("repository") or {}).get("full_name") or "")
    if event == "issue_comment" and payload.get("action") == "created":
        body = ((payload.get("comment") or {}).get("body") or "")
        claim = parse_prove(body)
        if claim is None:
            return {"action": "ignore", "why": "not a /prove comment"}
        issue = payload.get("issue") or {}
        # A comment on a plain issue is not a pull request. GitHub includes
        # issue.pull_request only when the comment is on a pull request.
        if not isinstance(issue.get("pull_request"), dict):
            return {"action": "ignore", "why": "a /prove comment on an issue is ignored; comment on the pull request"}
        if not may_post(repo, env):
            return {"action": "refuse", "why": f"repo {repo} not in {DEMO_REPOS_ENV}"}
        return {"action": "prove", "repo": repo, "claim": claim, "pr": issue.get("number")}
    if event == "pull_request" and payload.get("action") in ("opened", "synchronize", "reopened"):
        if not may_post(repo, env):
            return {"action": "refuse", "why": f"repo {repo} not in {DEMO_REPOS_ENV}"}
        pr = (payload.get("pull_request") or {})
        return {"action": "run", "repo": repo, "event": event,
                "pr": (pr.get("number") or (payload.get("number"))),
                "head_sha": (pr.get("head") or {}).get("sha")}
    if event == "check_suite" and payload.get("action") in ("requested", "rerequested"):
        if not may_post(repo, env):
            return {"action": "refuse", "why": f"repo {repo} not in {DEMO_REPOS_ENV}"}
        suite = payload.get("check_suite") or {}
        prs = suite.get("pull_requests") or []
        pr_n = prs[0].get("number") if prs else None
        return {"action": "run", "repo": repo, "event": event, "pr": pr_n,
                "head_sha": suite.get("head_sha")}
    return {"action": "ignore", "why": f"unhandled event {event}"}


def _pem(env: dict) -> str | None:
    raw = env.get("GITHUB_APP_PRIVATE_KEY")
    if not raw:
        return None
    p = Path(raw)
    if p.is_file():
        return p.read_text()
    return raw.replace("\\n", "\n")


def installation_token(env: dict | None = None) -> str | None:
    """Installation token from GITHUB_APP_INSTALLATION_TOKEN, or mint via App JWT (needs PyJWT)."""
    env = os.environ if env is None else env
    tok = (env.get(TOKEN_ENV) or "").strip()
    if tok:
        return tok
    app_id = (env.get("GITHUB_APP_ID") or "").strip()
    inst = (env.get("GITHUB_APP_INSTALLATION_ID") or "").strip()
    pem = _pem(env)
    if not (app_id and inst and pem):
        return None
    try:
        import jwt  # PyJWT
    except ImportError as e:
        raise GitHubAppError(
            "GITHUB_APP_ID/PRIVATE_KEY set but PyJWT is missing; "
            "pip install -e '.[github]' or set GITHUB_APP_INSTALLATION_TOKEN"
        ) from e
    now = int(time.time())
    payload = {"iat": now - 60, "exp": now + 9 * 60, "iss": app_id}
    try:
        encoded = jwt.encode(payload, pem, algorithm="RS256")
    except Exception as e:  # noqa: BLE001
        raise GitHubAppError(f"App JWT mint failed: {type(e).__name__}") from None
    if isinstance(encoded, bytes):
        encoded = encoded.decode()
    url = f"{API}/app/installations/{inst}/access_tokens"
    raw = _http_json("POST", url, token=None, body={}, extra_headers={
        "Authorization": f"Bearer {encoded}",
        "Accept": "application/vnd.github+json",
    })
    token = (raw or {}).get("token")
    if not token:
        raise GitHubAppError("installation token response had no token field")
    return str(token)


def _http_json(method: str, url: str, *, token: str | None, body: dict | None = None,
               extra_headers: dict | None = None) -> dict:
    data = None if body is None else json.dumps(body).encode()
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "proof-of-change",
               "X-GitHub-Api-Version": "2022-11-28"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if data is not None:
        headers["Content-Type"] = "application/json"
    if extra_headers:
        headers.update(extra_headers)
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read().decode()
            return json.loads(raw) if raw.strip() else {}
    except urllib.error.HTTPError as e:
        raise GitHubAppError(f"GitHub API {method} failed: HTTP {e.code}") from None
    except urllib.error.URLError as e:
        raise GitHubAppError(f"GitHub API {method} failed: {type(e.reason).__name__}") from None


def post_check_run(repo: str, payload: dict, token: str, env: dict | None = None) -> dict:
    if not may_post(repo, env):
        raise PermissionError(f"refusing to post check run on non-demo repo {repo!r}")
    # br-allow-external: G-ext demo-repo check runs only (may_post); never upstream
    return _http_json("POST", f"{API}/repos/{repo}/check-runs", token=token, body=payload)


def post_pr_comment(repo: str, pr: int, body: str, token: str, env: dict | None = None) -> dict:
    if not may_post(repo, env):
        raise PermissionError(f"refusing to post comment on non-demo repo {repo!r}")
    # br-allow-external: G-ext demo-repo PR comments only (may_post); never upstream
    return _http_json("POST", f"{API}/repos/{repo}/issues/{int(pr)}/comments", token=token,
                      body={"body": body})


COMMENT_FILE = "github_comment.json"
PREPARING_TEXT = "PDF preparing…"
FAILED_TEXT = "PDF could not be generated."


def report_url_for(path: Path, env: dict | None = None) -> str | None:
    env = os.environ if env is None else env
    base = (env.get(REPORT_BASE_ENV) or "").rstrip("/")
    if not base:
        return None
    return f"{base}/{path.name}"


def patch_pr_comment(repo: str, comment_id: int, body: str, token: str, env: dict | None = None) -> dict:
    if not may_post(repo, env):
        raise PermissionError(f"refusing to edit comment on non-demo repo {repo!r}")
    # br-allow-external: G-ext edit of the App's own demo-repo PR comment only (may_post); never upstream
    return _http_json("PATCH", f"{API}/repos/{repo}/issues/comments/{int(comment_id)}", token=token,
                      body={"body": body})


def patch_check_run(repo: str, check_run_id: int, payload: dict, token: str, env: dict | None = None) -> dict:
    if not may_post(repo, env):
        raise PermissionError(f"refusing to edit check run on non-demo repo {repo!r}")
    # br-allow-external: G-ext edit of the App's own demo-repo check run only (may_post); never upstream
    return _http_json("PATCH", f"{API}/repos/{repo}/check-runs/{int(check_run_id)}", token=token, body=payload)


def remember_posts(report_dir: Path, *, repo: str, pr: int, comment_id, comment_body: str, check_run_id,
                   check_title: str, check_summary: str, pdf_url: str | None) -> Path | None:
    """Save the App's own comment and check run that say 'PDF preparing…', for an in-place edit later."""
    if not pdf_url or not (comment_id or check_run_id):
        return None
    p = Path(report_dir) / COMMENT_FILE
    p.write_text(json.dumps({"repo": repo, "pr": int(pr), "comment_id": comment_id, "comment_body": comment_body,
                             "check_run_id": check_run_id, "check_title": check_title,
                             "check_summary": check_summary, "pdf_url": pdf_url, "done": None}))
    return p


def _log_error(msg: str, *args) -> None:
    import logging
    logging.getLogger("proof_of_change.github_app").error(msg, *args)


EDIT_RETRY_DELAYS_S = (2, 5, 15)


def update_posts_for_pdf(report_dir: str | Path, state: str, env: dict | None = None,
                         patch_comment: Callable[..., dict] | None = None,
                         patch_check: Callable[..., dict] | None = None,
                         delays=EDIT_RETRY_DELAYS_S, sleep: Callable[[float], Any] = time.sleep) -> bool:
    """When the PDF is ready (or has finally failed), edit the App's saved comment and check run in place.

    'PDF preparing…' becomes the PDF link, or 'PDF could not be generated.' Nothing happens without a saved
    id, after a previous edit (idempotent), or without a token. Only the saved items on the saved demo-repo
    PR are touched; nothing new is posted. A failed edit (GitHub, network or token error) is retried with a
    short bounded backoff; 'done' is saved only after every edit succeeded, so a later resume or the
    background sweep (PendingEditSweeper) tries again.
    Progress of each edit is saved, so a retry never edits the same item twice.
    """
    from reports import pdf_status
    if state not in (pdf_status.READY, pdf_status.ERROR):
        return False
    env = os.environ if env is None else env
    p = Path(report_dir) / COMMENT_FILE
    try:
        info = json.loads(p.read_text())
    except (OSError, ValueError):
        return False
    if not isinstance(info, dict) or info.get("done") or not (info.get("comment_id") or info.get("check_run_id")):
        return False
    repo, url = str(info.get("repo") or ""), str(info.get("pdf_url") or "")
    if not repo or not url:
        return False
    new_text = f"[PDF report]({url})" if state == pdf_status.READY else FAILED_TEXT
    waits = list(delays or ())
    attempt = 0
    while True:
        attempt += 1
        try:
            token = installation_token(env)
            if not token:
                raise GitHubAppError("no App token")
            if info.get("comment_id") and PREPARING_TEXT in str(info.get("comment_body") or ""):
                body = str(info["comment_body"]).replace(PREPARING_TEXT, new_text, 1)
                (patch_comment or patch_pr_comment)(repo, int(info["comment_id"]), body, token, env=env)
                info["comment_body"] = body
                p.write_text(json.dumps(info))
            if info.get("check_run_id") and not info.get("check_done"):
                line = f"PDF: {url}" if state == pdf_status.READY else FAILED_TEXT
                summary = (str(info.get("check_summary") or "") + "\n\n" + line)[:65000]
                (patch_check or patch_check_run)(repo, int(info["check_run_id"]), {
                    "output": {"title": str(info.get("check_title") or "Proof-of-Change"), "summary": summary}},
                    token, env=env)
                info["check_done"] = True
                p.write_text(json.dumps(info))
            break
        except PermissionError as e:  # not a demo repo: retrying cannot help
            _log_error("PDF %s but the App comment/check run may not be edited: %s", state, type(e).__name__)
            return False
        except (GitHubAppError, OSError, ValueError) as e:
            if not waits:
                _log_error("PDF %s but the App comment/check run could not be edited after %d tries: %s; "
                           "will retry on next resume", state, attempt, type(e).__name__)
                return False
            sleep(waits.pop(0))
    info["done"] = state
    p.write_text(json.dumps(info))
    return True


def posts_pending(report_dir: str | Path) -> bool:
    """True while the App's saved comment/check run still waits for its PDF edit (done is null)."""
    try:
        info = json.loads((Path(report_dir) / COMMENT_FILE).read_text())
    except (OSError, ValueError):
        return False
    return isinstance(info, dict) and not info.get("done") and bool(info.get("comment_id") or info.get("check_run_id"))


# Background sweep: a long-running App retries pending edits (done is null) on a timer, so a comment
# never waits for a restart after the short backoff above gave up. It gives up after a set limit.
EDIT_SWEEP_INTERVAL_S = 300          # every 5 minutes
EDIT_SWEEP_MAX_ATTEMPTS = 12         # about an hour of sweeps
EDIT_SWEEP_MAX_AGE_S = 6 * 3600      # or 6 hours after the first sweep saw it pending
GAVE_UP = "gave_up"


def _sweep_roots(roots=None) -> list[Path]:
    if roots is not None:
        return [Path(r) for r in roots]
    return [Path(os.environ.get("POC_REPORT_DIR") or (REPO_ROOT / "reports" / "daily"))]


def sweep_pending_posts(roots=None, *, env: dict | None = None, now: float | None = None,
                        update: Callable[..., bool] | None = None,
                        max_attempts: int = EDIT_SWEEP_MAX_ATTEMPTS,
                        max_age_s: float = EDIT_SWEEP_MAX_AGE_S) -> dict:
    """One sweep: retry each pending edit once (no in-sweep waits); give up past the limit. Never raises."""
    from reports import pdf_status
    now = time.time() if now is None else now
    update = update_posts_for_pdf if update is None else update
    out = {"done": [], "retrying": [], "gave_up": []}
    try:
        for root in _sweep_roots(roots):
            if not root.is_dir():
                continue
            for cp in root.rglob(COMMENT_FILE):
                d = cp.parent
                try:
                    if not posts_pending(d):
                        continue
                    state = pdf_status.read_state(d)
                    if state not in (pdf_status.READY, pdf_status.ERROR):
                        continue  # PDF still preparing: its own retry will edit
                    info = json.loads(cp.read_text())
                    first = info.get("sweep_first_at")
                    first = float(now if first is None else first)
                    attempts = int(info.get("sweep_attempts") or 0)
                    if attempts >= max_attempts or now - first > max_age_s:
                        # One last edit that swaps "PDF preparing…" for the plain failure text, so the
                        # PR comment and check run don't stay on "preparing". Never raises.
                        try:
                            final_ok = bool(update(d, pdf_status.ERROR, env=env, delays=()))
                        except Exception as e:  # noqa: BLE001
                            _log_error("Final PDF edit failed for %s: %s", d.name, type(e).__name__)
                            final_ok = False
                        try:
                            info = json.loads(cp.read_text())  # keep progress the final edit saved
                        except (OSError, ValueError):
                            pass
                        info.update(done=GAVE_UP, final_edit_ok=final_ok, final_error=(
                            f"comment/check-run edit gave up after {attempts} sweep attempts"
                            f" over {int(now - first)}s"))
                        cp.write_text(json.dumps(info))
                        _log_error("Gave up editing the App comment/check run for report %s after %d sweep "
                                   "attempts; final failure-text edit %s", d.name, attempts,
                                   "succeeded" if final_ok else f"failed, it still says '{PREPARING_TEXT}'")
                        out["gave_up"].append(d.name)
                        continue
                    info.update(sweep_first_at=first, sweep_attempts=attempts + 1)
                    cp.write_text(json.dumps(info))
                    if update(d, state, env=env, delays=()):
                        out["done"].append(d.name)
                    else:
                        out["retrying"].append(d.name)
                except Exception as e:  # noqa: BLE001 - a sweep must never raise
                    _log_error("PDF edit sweep failed for %s: %s", d.name, type(e).__name__)
    except Exception as e:  # noqa: BLE001
        _log_error("PDF edit sweep failed: %s", type(e).__name__)
    return out


class PendingEditSweeper:
    """Daemon thread running sweep_pending_posts every interval; stop() ends it cleanly."""

    def __init__(self, interval_s: float = EDIT_SWEEP_INTERVAL_S, sweep: Callable[[], Any] | None = None,
                 stop_event=None):
        import threading
        self.interval_s = interval_s
        self.sweep = sweep or sweep_pending_posts
        self.stop_event = stop_event or threading.Event()
        self.thread = threading.Thread(target=self.run, name="poc-pdf-edit-sweep", daemon=True)

    def run(self) -> None:
        while not self.stop_event.wait(self.interval_s):
            try:
                self.sweep()
            except Exception as e:  # noqa: BLE001
                _log_error("PDF edit sweep failed: %s", type(e).__name__)

    def start(self) -> "PendingEditSweeper":
        self.thread.start()
        return self

    def stop(self, timeout: float = 5) -> None:
        self.stop_event.set()
        if self.thread.is_alive():
            self.thread.join(timeout)


PDF_PREPARING_MARK = "<!--pdf-preparing:{name}-->"


def reviewer_report_dir(rec: dict) -> Path | None:
    """Folder holding this record's REPORT.html / REPORT.pdf / pdf_status.json, if one was written."""
    try:
        from poc import console_api
        html = console_api.find_reviewer_report_file(str(rec.get("id") or ""), "html", rec=rec)
    except Exception:  # noqa: BLE001 - a missing report folder only means no PDF line
        return None
    return html.parent if html else None


def _pdf_block(rid: str, report_dir: Path | None, out_dir: Path) -> tuple[str, str | None]:
    """(HTML snippet, PDF state). Copies a ready PDF next to the hosted page; else shows 'PDF preparing…'."""
    if report_dir is None:
        return "", None
    from reports import pdf_status
    state = pdf_status.read_state(report_dir)
    if state == pdf_status.READY:
        import shutil
        shutil.copyfile(report_dir / pdf_status.PDF_FILE, out_dir / f"{rid}.pdf")
        return f'<p><a href="{_esc(rid)}.pdf">PDF report</a></p>', state
    if state == pdf_status.ERROR:
        return f'<p class="pdf-failed">{FAILED_TEXT}</p>', state
    if state == pdf_status.PREPARING:
        mark = PDF_PREPARING_MARK.format(name=_esc(report_dir.name))
        return f'<p class="pdf-preparing">PDF preparing…</p>{mark}', pdf_status.PREPARING
    return "", None


def publish_failed_pdf(report_dir: str | Path, hosted_dir: str | Path | None = None) -> int:
    """All retries failed: swap 'PDF preparing…' for a clear failure line on hosted pages."""
    report_dir = Path(report_dir)
    hosted_dir = Path(hosted_dir) if hosted_dir is not None else DEFAULT_HOSTED
    if not hosted_dir.is_dir():
        return 0
    mark = PDF_PREPARING_MARK.format(name=_esc(report_dir.name))
    n = 0
    for page in hosted_dir.glob("*.html"):
        text = page.read_text(encoding="utf-8", errors="replace")
        if mark not in text:
            continue
        page.write_text(text.replace(f'<p class="pdf-preparing">PDF preparing…</p>{mark}',
                                     f'<p class="pdf-failed">{FAILED_TEXT}</p>'))
        n += 1
    return n


def publish_pdf_outcome(report_dir: str | Path, state: str, hosted_dir: str | Path | None = None,
                        env: dict | None = None) -> None:
    """Background retry finished: update hosted pages, then the App's own comment and check run."""
    from reports import pdf_status
    if state == pdf_status.READY:
        publish_ready_pdf(report_dir, hosted_dir)
    elif state == pdf_status.ERROR:
        publish_failed_pdf(report_dir, hosted_dir)
    update_posts_for_pdf(report_dir, state, env)


def publish_ready_pdf(report_dir: str | Path, hosted_dir: str | Path | None = None) -> int:
    """Called when a background retry finishes: swap 'PDF preparing…' for the real link on hosted pages."""
    from reports import pdf_status
    report_dir = Path(report_dir)
    hosted_dir = Path(hosted_dir) if hosted_dir is not None else DEFAULT_HOSTED
    pdf = report_dir / pdf_status.PDF_FILE
    if not hosted_dir.is_dir() or not (pdf.is_file() and pdf.stat().st_size > 0):
        return 0
    mark = PDF_PREPARING_MARK.format(name=_esc(report_dir.name))
    n = 0
    for page in hosted_dir.glob("*.html"):
        text = page.read_text(encoding="utf-8", errors="replace")
        if mark not in text:
            continue
        import shutil
        shutil.copyfile(pdf, hosted_dir / f"{page.stem}.pdf")
        page.write_text(text.replace(f'<p class="pdf-preparing">PDF preparing…</p>{mark}',
                                     f'<p><a href="{_esc(page.stem)}.pdf">PDF report</a></p>'))
        n += 1
    return n


def write_hosted_report(rec: dict, out_dir: Path | None = None, report_dir: Path | None = None) -> Path:
    """Static behavior-map HTML for one PR record (hosted or opened locally)."""
    out_dir = Path(out_dir) if out_dir is not None else DEFAULT_HOSTED
    out_dir.mkdir(parents=True, exist_ok=True)
    rid = rec.get("id") or "run"
    path = out_dir / f"{rid}.html"
    pdf_html, _ = _pdf_block(str(rid), report_dir, out_dir)
    claims = rec.get("behaviour_claims") or []
    probes = ((rec.get("probes") or {}).get("items") or [])
    agents = rec.get("agents") or {}
    rows_c = "".join(
        f"<tr><td>{c.get('id','')}</td><td>{_esc(c.get('text') or c.get('claim') or '')}</td>"
        f"<td>{_esc(c.get('status') or '')}</td></tr>" for c in claims)
    rows_p = "".join(
        f"<tr><td>{_esc(p.get('id'))}</td><td>{_esc(p.get('about'))}</td>"
        f"<td>{_esc(', '.join(p.get('labels') or []))}</td></tr>" for p in probes[:40])
    expl = (rec.get("explanation") or {}).get("text") or ""
    from poc import related_reports
    background = rec.get("related_reports") if isinstance(rec.get("related_reports"), dict) else None
    background_text = str((background or {}).get("text") or "").strip()
    background_html = ""
    if background_text:
        background_html = (
            f"<h2>{_esc(related_reports.REPORT_LABEL)}</h2><p>{_esc(background_text)}</p>"
        )
    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Proof-of-Change {_esc(rid)}</title>
<style>
body{{font-family:system-ui,sans-serif;margin:2rem;max-width:960px;line-height:1.45}}
.banner{{padding:1rem;border-radius:8px;background:#f0f4f8}}
table{{border-collapse:collapse;width:100%}} th,td{{border:1px solid #ccc;padding:.4rem;text-align:left}}
.meta{{color:#555;font-size:.9rem}}
</style></head><body>
<h1>Proof-of-Change</h1>
<div class="banner"><strong>{_esc(rec.get('verdict'))}</strong> — {_esc(rec.get('reason'))}</div>
{pdf_html}
<p class="meta">Repo {_esc(rec.get('repo'))} · machine {_esc(rec.get('machine') or 'local')} ·
sandbox {_esc(rec.get('sandbox_backend') or 'local')}</p>
<h2>Behavior map</h2>
<p>Claims → probes. Model labels are advisory; code owns the verdict.</p>
<h3>Claims</h3>
<table><tr><th>Id</th><th>Claim</th><th>Status</th></tr>{rows_c or '<tr><td colspan=3>none</td></tr>'}</table>
<h3>Probes</h3>
<table><tr><th>Id</th><th>About</th><th>Labels</th></tr>{rows_p or '<tr><td colspan=3>none</td></tr>'}</table>
<h2>Summary</h2>
<p>{_esc(expl) or '(no model summary)'}</p>
<p class="meta">Agents: {_esc(json.dumps(agents.get('roles') or agents.get('status') or 'none'))}</p>
{background_html}
</body></html>"""
    path.write_text(html)
    return path


def _load_latest_record(repo: str, pr: int) -> dict | None:
    """Best-effort: newest record.json under ops/runs matching this PR."""
    runs = REPO_ROOT / "ops" / "runs"
    if not runs.is_dir():
        return None
    needle = f"-{pr}"
    repo_slug = repo.replace("/", "-")
    candidates: list[Path] = []
    for rec_path in runs.rglob("record.json"):
        try:
            rec = json.loads(rec_path.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        if rec.get("repo") == repo and (rec.get("pr") or {}).get("number") == pr:
            candidates.append(rec_path)
        elif repo_slug in rec_path.parent.name and needle in rec_path.parent.name:
            candidates.append(rec_path)
    if not candidates:
        return None
    newest = max(candidates, key=lambda p: p.stat().st_mtime)
    return json.loads(newest.read_text())


def check_argv(pr_url: str, env: dict | None = None) -> list[str]:
    """Arguments for one product check started by the GitHub App.

    ``--related-reports`` is quoted background for the advisory AI. ``--swarm`` turns the
    advisory swarm on for every App check. A study run uses neither. The App does not set
    ``POC_SWARM`` in the environment, so nothing else in the process is turned on.
    """
    env = os.environ if env is None else env
    from poc import related_reports
    provider = env.get("POC_MODEL_PROVIDER") or "nebius"
    return ["--pr", pr_url, "--model-provider", provider, "--swarm", *related_reports.product_flags()]


def apply(plan: dict, *, dry_run: bool | None = None, env: dict | None = None,
          runner: Callable[..., int] | None = None, hosted_dir: Path | None = None) -> dict[str, Any]:
    """Execute a handle_event plan: run daily_run for the PR, write hosted HTML, post check+comment if token."""
    env = os.environ if env is None else env
    action = plan.get("action")
    if action in ("ignore", "refuse"):
        return {"ok": True, **plan}
    if action not in ("prove", "run"):
        return {"ok": False, "error": f"unknown action {action!r}", "plan": plan}
    repo = plan.get("repo")
    pr = plan.get("pr")
    if not repo or not pr:
        return {"ok": False, "error": "plan needs repo and pr", "plan": plan}
    if not may_post(str(repo), env):
        return {"ok": False, "action": "refuse", "why": f"repo {repo} not in {DEMO_REPOS_ENV}"}

    token = None
    try:
        token = installation_token(env)
    except GitHubAppError as e:
        return {"ok": False, "error": str(e), "plan": plan}
    force_dry = dry_run if dry_run is not None else (not token)
    if force_dry and dry_run is None and not token:
        note = "no installation token: dry_run only (set GITHUB_APP_INSTALLATION_TOKEN or App JWT env)"
    else:
        note = None

    pr_url = f"https://github.com/{repo}/pull/{int(pr)}"
    argv = check_argv(pr_url, env)
    if plan.get("claim"):
        # claim text is advisory for logs; daily_run reads claims from PR body
        pass

    run_exit = None
    if force_dry:
        # still allow a pre-supplied record via plan["record"]
        rec = plan.get("record")
    else:
        from poc import tavily_docs
        missing = tavily_docs.missing_key_line(env)
        if missing:
            print(missing, file=sys.stderr)
            return {"ok": False, "error": missing, "action": action, "repo": repo, "pr": pr, "dry_run": False}
        if runner is not None:
            run_exit = runner(argv)
        else:
            from ops import daily_run
            run_exit = daily_run.main(argv)
        rec = plan.get("record") or _load_latest_record(str(repo), int(pr))

    if not isinstance(rec, dict):
        out = {"ok": run_exit == 0 if run_exit is not None else force_dry, "action": action,
               "repo": repo, "pr": pr, "dry_run": force_dry, "run_exit": run_exit,
               "note": note or "no record.json found after run"}
        return out

    rdir = reviewer_report_dir(rec)
    report_path = write_hosted_report(rec, hosted_dir or DEFAULT_HOSTED, report_dir=rdir)
    url = report_url_for(report_path, env)
    hosted_pdf = report_path.with_suffix(".pdf")
    pdf_url = report_url_for(hosted_pdf, env) if hosted_pdf.is_file() else None
    from reports import pdf_status
    pdf_preparing = rdir is not None and not hosted_pdf.is_file() and pdf_status.read_state(rdir) in (
        pdf_status.PREPARING, pdf_status.ERROR)
    pdf_failed = rdir is not None and not hosted_pdf.is_file() and pdf_status.read_state(rdir) == pdf_status.ERROR
    pdf_preparing = pdf_preparing and not pdf_failed
    later_pdf_url = report_url_for(hosted_pdf, env) if pdf_preparing else None
    verdict = str(rec.get("verdict") or "could_not_verify")
    reason = str(rec.get("reason") or "")
    head = plan.get("head_sha") or (rec.get("pr") or {}).get("head_sha") or ""
    gh_meta: dict[str, Any] = {"report_path": str(report_path), "report_url": url, "dry_run": force_dry,
                               "pdf_url": pdf_url, "pdf_preparing": pdf_preparing}

    if force_dry or not token:
        gh_meta["note"] = note or "dry_run: check run and comment not posted"
        rec["github_app"] = gh_meta
        rec["posted_upstream"] = False
        return {"ok": True, "action": action, "repo": repo, "pr": pr, "dry_run": True,
                "verdict": verdict, "github_app": gh_meta, "run_exit": run_exit}

    try:
        payload = check_run_payload(str(repo), str(head), verdict, reason, url, env=env)
        check = post_check_run(str(repo), payload, token, env=env)
        comment_body = summary_comment(verdict, reason, url, pdf_url=pdf_url, pdf_preparing=pdf_preparing,
                                       pdf_failed=pdf_failed)
        comment = post_pr_comment(str(repo), int(pr), comment_body, token, env=env)
    except (GitHubAppError, PermissionError) as e:
        gh_meta["error"] = str(e)
        return {"ok": False, "action": action, "repo": repo, "pr": pr, "github_app": gh_meta,
                "run_exit": run_exit}

    gh_meta["check_run_id"] = check.get("id")
    gh_meta["check_run_url"] = check.get("html_url")
    gh_meta["comment_id"] = comment.get("id")
    gh_meta["comment_url"] = comment.get("html_url")
    if pdf_preparing and rdir is not None:
        out = payload.get("output") or {}
        remember_posts(rdir, repo=str(repo), pr=int(pr), comment_id=comment.get("id"), comment_body=comment_body,
                       check_run_id=check.get("id"), check_title=str(out.get("title") or ""),
                       check_summary=str(out.get("summary") or ""), pdf_url=later_pdf_url)
        late = pdf_status.read_state(rdir)
        if late in (pdf_status.READY, pdf_status.ERROR):  # the retry finished while we were posting
            publish_pdf_outcome(rdir, late, hosted_dir or DEFAULT_HOSTED, env)
    rec["github_app"] = gh_meta
    rec["posted_upstream"] = True
    return {"ok": True, "action": action, "repo": repo, "pr": pr, "dry_run": False,
            "verdict": verdict, "github_app": gh_meta, "run_exit": run_exit}


def _esc(s) -> str:
    return (str(s) if s is not None else "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


class _WebhookHandler(BaseHTTPRequestHandler):
    env: dict = os.environ  # overridden in serve()
    apply_fn: Callable = staticmethod(apply)

    def log_message(self, fmt, *args):  # quieter
        pass

    def do_GET(self):  # noqa: N802
        if self.path.split("?")[0] in ("/health", "/"):
            body = json.dumps({"ok": True, "service": "proof-of-change-github-app"}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_error(404)

    def do_POST(self):  # noqa: N802
        if self.path.split("?")[0] != "/webhook":
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b""
        secret = self.env.get(WEBHOOK_SECRET_ENV)
        sig = self.headers.get("X-Hub-Signature-256")
        if not verify_webhook(raw, sig, secret):
            self.send_error(401, "bad signature")
            return
        event = self.headers.get("X-GitHub-Event") or ""
        try:
            payload = json.loads(raw.decode() or "{}")
        except json.JSONDecodeError:
            self.send_error(400, "bad json")
            return
        plan = handle_event(event, payload, self.env)
        # Acknowledge quickly; MVP runs apply inline (document timeout risk).
        # ponytail: sync apply; async queue if webhooks time out under long PR runs
        result = {"plan": plan}
        if plan.get("action") in ("prove", "run"):
            result = self.apply_fn(plan, env=self.env)
        body = json.dumps(result, default=str).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def require_report_base(env: dict | None = None) -> str:
    """Hosted App mode needs a public report address, or PR comments would carry no working links."""
    env = os.environ if env is None else env
    base = (env.get(REPORT_BASE_ENV) or "").strip()
    if not base:
        raise SystemExit(f"refusing to start: {REPORT_BASE_ENV} is not set (public address of the hosted reports)")
    return base


def serve(host: str = "0.0.0.0", port: int = 8080, env: dict | None = None) -> None:
    env = os.environ if env is None else env
    require_report_base(env)
    from reports import pdf_status
    pdf_status.resume_pending()  # folders still 'preparing' from before a restart

    class H(_WebhookHandler):
        pass

    H.env = env
    H.apply_fn = apply
    httpd = HTTPServer((host, port), H)
    sweeper = PendingEditSweeper().start()
    print(f"proof-of-change github app listening on http://{host}:{port}  POST /webhook  GET /health", flush=True)
    try:
        httpd.serve_forever()
    finally:
        sweeper.stop()
        httpd.server_close()


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="Proof-of-Change GitHub App webhook server")
    ap.add_argument("--host", default=os.environ.get("POC_WEBHOOK_HOST", "0.0.0.0"))
    ap.add_argument("--port", type=int, default=int(os.environ.get("POC_WEBHOOK_PORT", "8080")))
    a = ap.parse_args(argv)
    serve(a.host, a.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
