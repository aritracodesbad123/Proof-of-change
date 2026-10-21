"""Take "Request a check" issues one at a time and run a normal sandboxed check.

Run this on the project Linux machine (not in GitHub Actions):

    GITHUB_TOKEN=... POC_GITHUB_REPOSITORY=owner/repo python ops/request_worker.py

The token is read from the environment and sent only as a request header. It is never
printed and never included in an issue comment. Each loop writes a heartbeat the
offline notice can read. The check itself is ``ops/daily_run.py --pr <url>`` with the
default flags, so pull-request code stays sandboxed.

The worker does not start a check between 10:40 and 12:30 IST, stops after the daily
cap (default 5, ``POC_DAILY_CAP``), and skips while the study lock says a study run
needs the machine (``POC_STUDY_LOCK``, default ``ops/study.lock``).
"""
from __future__ import annotations

import argparse
import base64
import fcntl
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from poc.session_key import scrub

ROOT = Path(__file__).resolve().parent.parent
IST = ZoneInfo("Asia/Kolkata")
API = "https://api.github.com"
REQUEST_LABEL = "request-a-check"
DONE_LABEL = "request-done"
RUNNING_LABEL = "request-running"
HEARTBEAT_BRANCH = "checker-heartbeat"
HEARTBEAT_PATH = ".github/checker-heartbeat.json"
QUIET_MARKER = "The checker does not start between 10:40 and 12:30 IST."
STUDY_MARKER = "A study run has this machine, so this request stays in the queue."
CAP_MARKER = "The daily check limit is used."
LOOKUP_MARKER = "The checker could not read that repository just now."
RESULTS_PAGE = "https://aritracodesbad123.github.io/Proof-of-change/"
PR_URL = re.compile(
    r"https://github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)/pull/(\d+)(?=$|[/?#\s])"
)
PYTHON_ROOTS = {"pyproject.toml", "setup.py", "setup.cfg"}


class GitHubError(RuntimeError):
    pass


@dataclass
class Settings:
    cap: int = 5
    quiet_start: tuple[int, int] = (10, 40)
    quiet_end: tuple[int, int] = (12, 30)
    study_lock: Path = ROOT / "ops" / "study.lock"
    results_url: str = RESULTS_PAGE
    max_checkin_age_s: int = 20 * 60
    repo: str = ""
    state_path: Path = ROOT / "ops" / "request-worker-state.json"
    python: str = sys.executable
    root: Path = ROOT


@dataclass
class CheckResult:
    verdict: str
    reason: str
    report_markdown: str | None
    run_id: str
    ok: bool


def _parse_hhmm(text: str, fallback: tuple[int, int]) -> tuple[int, int]:
    parts = (text or "").strip().split(":")
    if len(parts) != 2:
        return fallback
    try:
        hour, minute = int(parts[0]), int(parts[1])
    except ValueError:
        return fallback
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return fallback
    return hour, minute


def settings_from_env(env: dict[str, str] | None = None) -> Settings:
    env = os.environ if env is None else env
    cap_raw = (env.get("POC_DAILY_CAP") or "").strip()
    try:
        cap = int(cap_raw) if cap_raw else 5
    except ValueError:
        cap = 5
    age_raw = (env.get("POC_CHECKER_MAX_AGE_S") or "").strip()
    try:
        age = int(age_raw) if age_raw else 20 * 60
    except ValueError:
        age = 20 * 60
    lock = (env.get("POC_STUDY_LOCK") or "").strip()
    state = (env.get("POC_REQUEST_STATE") or "").strip()
    return Settings(
        cap=cap,
        quiet_start=_parse_hhmm(env.get("POC_QUIET_START") or "", (10, 40)),
        quiet_end=_parse_hhmm(env.get("POC_QUIET_END") or "", (12, 30)),
        study_lock=Path(lock) if lock else ROOT / "ops" / "study.lock",
        results_url=(env.get("POC_RESULTS_URL") or RESULTS_PAGE).strip() or RESULTS_PAGE,
        max_checkin_age_s=age,
        repo=(env.get("POC_GITHUB_REPOSITORY") or env.get("GITHUB_REPOSITORY") or "").strip(),
        state_path=Path(state) if state else ROOT / "ops" / "request-worker-state.json",
    )


def in_quiet_window(now: datetime, start: tuple[int, int] = (10, 40),
                    end: tuple[int, int] = (12, 30)) -> bool:
    """True from start through end, inclusive of those minutes, in India Standard Time."""
    local = now.astimezone(IST)
    minutes = local.hour * 60 + local.minute
    return (start[0] * 60 + start[1]) <= minutes <= (end[0] * 60 + end[1])


def study_needs_slot(path: Path | None) -> bool:
    """True when the lock file exists and is not an explicit off switch (0, false, no, off, empty)."""
    if path is None or not path.is_file():
        return False
    text = path.read_text(errors="replace").strip().lower()
    return text not in {"", "0", "false", "no", "off"}


def checker_is_offline(checked_in_at: str | None, now: datetime, max_age_s: int = 20 * 60) -> bool:
    """True when the worker has no check-in, or the last one is older than ``max_age_s``."""
    if not checked_in_at or max_age_s < 0:
        return True
    try:
        then = datetime.strptime(checked_in_at, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=ZoneInfo("UTC"))
    except ValueError:
        return True
    age = (now.astimezone(ZoneInfo("UTC")) - then).total_seconds()
    return age < 0 or age > max_age_s


def heartbeat_document(now: datetime) -> dict[str, str]:
    return {"checked_in_at": now.astimezone(ZoneInfo("UTC")).strftime("%Y-%m-%dT%H:%M:%SZ")}


def ist_day(now: datetime) -> str:
    return now.astimezone(IST).date().isoformat()


def started_today(state: dict, now: datetime) -> int:
    if state.get("date_ist") != ist_day(now):
        return 0
    try:
        return int(state.get("started") or 0)
    except (TypeError, ValueError):
        return 0


def note_started(state: dict, now: datetime) -> dict:
    count = started_today(state, now) + 1
    return {"date_ist": ist_day(now), "started": count}


def cap_reached(started: int, cap: int) -> bool:
    return started >= cap


def parse_pr_link(text: str) -> tuple[str, str, int] | None:
    match = PR_URL.search(text or "")
    if not match:
        return None
    return match.group(1), match.group(2), int(match.group(3))


def python_library(facts: dict | None, root_names: list[str] | None = None) -> bool:
    """A public repository whose language is Python, or whose root has a Python project file."""
    if not facts or facts.get("private") is True:
        return False
    if str(facts.get("language") or "").lower() == "python":
        return True
    names = {str(name).lower() for name in (root_names if root_names is not None else facts.get("root") or [])}
    return bool(names & PYTHON_ROOTS)


def labels_of(issue: dict) -> set[str]:
    found = set()
    for label in issue.get("labels") or []:
        if isinstance(label, str):
            found.add(label)
        elif isinstance(label, dict) and label.get("name"):
            found.add(str(label["name"]))
    return found


def another_running(issues: list[dict]) -> bool:
    return any(RUNNING_LABEL in labels_of(issue) for issue in issues)


def queue_order(issues: list[dict]) -> list[dict]:
    """Open requests that are not finished, oldest first."""
    waiting = []
    for issue in issues:
        names = labels_of(issue)
        if REQUEST_LABEL not in names or DONE_LABEL in names:
            continue
        if str(issue.get("state") or "open") != "open":
            continue
        waiting.append(issue)
    waiting.sort(key=lambda issue: str(issue.get("created_at") or ""))
    return waiting


def default_check_argv(python: str, root: Path, pr_url: str) -> list[str]:
    """The normal check: default flags, sandboxed. No unsandboxed switch."""
    return [python, str(root / "ops" / "daily_run.py"), "--pr", pr_url]


def already_said(comments: list[str], marker: str) -> bool:
    return any(marker in (body or "") for body in comments)


def verdict_comment(verdict: str, reason: str, report_url: str | None, results_url: str,
                    secrets: list[str]) -> str:
    report = report_url or results_url
    lines = [
        f"Verdict: {verdict}",
        "",
        reason.strip() or "The check finished without a written reason.",
        "",
        f"Report: {report}",
        f"Results page: {results_url}",
    ]
    return scrub("\n".join(lines), secrets)


def _safe_id(text: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", text).strip("-")
    return (cleaned or "check")[:80]


def load_state(path: Path) -> dict:
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def save_state(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2) + "\n")


class GitHubClient:
    """Issue replies, the heartbeat file, and report pages. The token stays in the header."""

    def __init__(self, repo: str, token: str, opener=urllib.request.urlopen):
        self.repo = repo
        self.token = token
        self.opener = opener

    def scrubbed(self, text: str) -> str:
        return scrub(text, [self.token])

    def _url(self, suffix: str) -> str:
        return f"{API}/repos/{self.repo}/{suffix.lstrip('/')}"

    def _request(self, method: str, url: str, body: dict | None = None, accept_missing: bool = False):
        data = None if body is None else json.dumps(body).encode()
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "proof-of-change-request-worker",
            "X-GitHub-Api-Version": "2022-11-28",
            "Authorization": f"Bearer {self.token}",
        }
        if data is not None:
            headers["Content-Type"] = "application/json"
        # br-allow-external: request worker replies on the asking issue, writes a heartbeat, and publishes the report
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with self.opener(req, timeout=60) as resp:
                raw = resp.read().decode()
                return getattr(resp, "status", 200), json.loads(raw) if raw.strip() else {}
        except urllib.error.HTTPError as exc:
            if accept_missing and exc.code == 404:
                return 404, {}
            detail = ""
            try:
                detail = exc.read().decode()[:300]
            except Exception:  # noqa: BLE001
                detail = ""
            raise GitHubError(self.scrubbed(f"GitHub API failed: HTTP {exc.code} {detail}")) from None
        except urllib.error.URLError as exc:
            raise GitHubError(self.scrubbed(f"GitHub API failed: {type(exc.reason).__name__}")) from None

    def list_open_requests(self) -> list[dict]:
        _status, payload = self._request(
            "GET", self._url(f"issues?state=open&labels={REQUEST_LABEL}&per_page=50"),
        )
        return payload if isinstance(payload, list) else []

    def comments(self, number: int) -> list[str]:
        _status, payload = self._request("GET", self._url(f"issues/{int(number)}/comments?per_page=100"))
        if not isinstance(payload, list):
            return []
        return [str(item.get("body") or "") for item in payload if isinstance(item, dict)]

    def comment(self, number: int, body: str) -> None:
        self._request(
            "POST", self._url(f"issues/{int(number)}/comments"),
            {"body": self.scrubbed(body)},
        )

    def add_labels(self, number: int, labels: list[str]) -> None:
        self._request("POST", self._url(f"issues/{int(number)}/labels"), {"labels": labels})

    def remove_label(self, number: int, label: str) -> None:
        self._request(
            "DELETE", self._url(f"issues/{int(number)}/labels/{label}"), accept_missing=True,
        )

    def repo_facts(self, owner: str, name: str) -> dict | None:
        status, payload = self._request("GET", f"{API}/repos/{owner}/{name}", accept_missing=True)
        if status == 404 or not isinstance(payload, dict):
            return None
        roots: list[str] = []
        if str(payload.get("language") or "").lower() != "python":
            code, listing = self._request(
                "GET", f"{API}/repos/{owner}/{name}/contents/", accept_missing=True,
            )
            if code != 404 and isinstance(listing, list):
                roots = [str(item.get("name") or "") for item in listing if isinstance(item, dict)]
        payload = dict(payload)
        payload["root"] = roots
        return payload

    def _branch_sha(self, branch: str) -> str | None:
        status, payload = self._request(
            "GET", self._url(f"git/ref/heads/{branch}"), accept_missing=True,
        )
        if status == 404:
            return None
        return ((payload.get("object") or {}).get("sha")) if isinstance(payload, dict) else None

    def ensure_heartbeat_branch(self) -> None:
        if self._branch_sha(HEARTBEAT_BRANCH):
            return
        status, repo = self._request("GET", self._url(""))
        default = str((repo or {}).get("default_branch") or "main") if status != 404 else "main"
        sha = self._branch_sha(default)
        if not sha:
            raise GitHubError("The heartbeat branch could not be created.")
        self._request("POST", self._url("git/refs"), {"ref": f"refs/heads/{HEARTBEAT_BRANCH}", "sha": sha})

    def _put_file(self, path: str, text: str, message: str) -> str:
        self.ensure_heartbeat_branch()
        content = base64.b64encode(self.scrubbed(text).encode()).decode()
        body: dict = {"message": message, "content": content, "branch": HEARTBEAT_BRANCH}
        status, current = self._request(
            "GET", self._url(f"contents/{path}?ref={HEARTBEAT_BRANCH}"), accept_missing=True,
        )
        if status != 404 and isinstance(current, dict) and current.get("sha"):
            body["sha"] = current["sha"]
        self._request("PUT", self._url(f"contents/{path}"), body)
        return f"https://github.com/{self.repo}/blob/{HEARTBEAT_BRANCH}/{path}"

    def heartbeat(self, now: datetime) -> None:
        self._put_file(HEARTBEAT_PATH, json.dumps(heartbeat_document(now)), "checker heartbeat")

    def publish_report(self, run_id: str, markdown: str) -> str:
        path = f"reports/{_safe_id(run_id)}/REPORT.md"
        return self._put_file(path, markdown, "check report")


def run_check(pr_url: str, settings: Settings, secrets: list[str]) -> CheckResult:
    """Run the normal check. Stdout is scrubbed before it can be shown."""
    argv = default_check_argv(settings.python, settings.root, pr_url)
    proc = subprocess.run(
        argv, cwd=str(settings.root), capture_output=True, text=True, check=False,
    )
    output = scrub((proc.stdout or "") + "\n" + (proc.stderr or ""), secrets)
    record = None
    report = None
    parsed = parse_pr_link(pr_url)
    if parsed:
        from poc import console_api
        found = console_api.find_record_for_pr(f"{parsed[0]}/{parsed[1]}", parsed[2])
        if found:
            record, path = found
            md = console_api.find_reviewer_report_file(
                str(record.get("id") or path.parent.name), "md", folder=str(path.parent), rec=record,
            )
            if md and md.is_file():
                report = scrub(md.read_text(errors="replace"), secrets)
    if record and record.get("verdict"):
        return CheckResult(
            verdict=str(record.get("verdict")),
            reason=scrub(str(record.get("reason") or ""), secrets),
            report_markdown=report,
            run_id=str(record.get("id") or "check"),
            ok=True,
        )
    tail = ""
    for line in output.splitlines():
        if line.strip().startswith("STOPPED:") or "Stopped:" in line:
            tail = line.strip()
    if not tail:
        tail = output.strip()[-400:]
    return CheckResult(
        verdict="could_not_verify",
        reason=tail or f"The check exited {proc.returncode}.",
        report_markdown=report,
        run_id="check",
        ok=False,
    )


def _wait(client, number: int, comments: list[str], marker: str, results_url: str,
          secrets: list[str]) -> None:
    if already_said(comments, marker):
        return
    client.comment(number, scrub(f"{marker}\n\nResults page: {results_url}", secrets))


def process_queue(client, settings: Settings, now: datetime, state: dict, *,
                  run=run_check, secrets: list[str] | None = None) -> dict:
    """Handle at most one request. Returns the daily-cap state (possibly updated)."""
    secrets = list(secrets or [])
    try:
        client.heartbeat(now)
    except GitHubError as exc:
        print(scrub(str(exc), secrets), file=sys.stderr)
    issues = client.list_open_requests()
    if another_running(issues):
        print("a check is already running")
        return state
    waiting = [issue for issue in queue_order(issues) if RUNNING_LABEL not in labels_of(issue)]
    if not waiting:
        print("no open requests")
        return state
    issue = waiting[0]
    number = int(issue["number"])
    comments = client.comments(number)
    body = str(issue.get("body") or "")
    parsed = parse_pr_link(body)
    if not parsed:
        if not already_said(comments, "not a public GitHub pull request"):
            client.comment(number, scrub(
                "That is not a public GitHub pull request for a Python library. "
                "Open a new request with one https link, like https://github.com/owner/repo/pull/123.\n\n"
                f"Results page: {settings.results_url}",
                secrets,
            ))
        client.add_labels(number, [DONE_LABEL])
        print(f"closed invalid request {number}")
        return state
    if study_needs_slot(settings.study_lock):
        _wait(client, number, comments, STUDY_MARKER, settings.results_url, secrets)
        print("study lock holds the machine")
        return state
    if in_quiet_window(now, settings.quiet_start, settings.quiet_end):
        _wait(client, number, comments, QUIET_MARKER, settings.results_url, secrets)
        print("quiet window")
        return state
    if cap_reached(started_today(state, now), settings.cap):
        _wait(client, number, comments, CAP_MARKER, settings.results_url, secrets)
        print("daily cap")
        return state
    owner, name, _pr = parsed
    try:
        facts = client.repo_facts(owner, name)
    except GitHubError as exc:
        if not already_said(comments, LOOKUP_MARKER):
            client.comment(number, scrub(
                f"{LOOKUP_MARKER} It will try again.\n\nResults page: {settings.results_url}",
                secrets,
            ))
        print(scrub(str(exc), secrets))
        return state
    if not python_library(facts):
        client.comment(number, scrub(
            "That link is not a public Python library, so it was not checked. "
            "Request a check only for a public Python project.\n\n"
            f"Results page: {settings.results_url}",
            secrets,
        ))
        client.add_labels(number, [DONE_LABEL])
        print(f"closed non-python request {number}")
        return state
    url = f"https://github.com/{owner}/{name}/pull/{_pr}"
    state = note_started(state, now)
    save_state(settings.state_path, state)
    client.add_labels(number, [RUNNING_LABEL])
    print(f"starting {url}")
    try:
        result = run(url, settings, secrets)
    except Exception as exc:  # noqa: BLE001
        result = CheckResult(
            verdict="could_not_verify",
            reason=scrub(f"{type(exc).__name__}", secrets),
            report_markdown=None,
            run_id="check",
            ok=False,
        )
    report_url = None
    if result.report_markdown:
        try:
            report_url = client.publish_report(result.run_id, scrub(result.report_markdown, secrets))
        except GitHubError as exc:
            print(scrub(str(exc), secrets), file=sys.stderr)
    client.comment(
        number,
        verdict_comment(result.verdict, result.reason, report_url, settings.results_url, secrets),
    )
    client.remove_label(number, RUNNING_LABEL)
    client.add_labels(number, [DONE_LABEL])
    print(f"finished {number} {result.verdict}")
    return state


def _token(env: dict[str, str]) -> str:
    return (env.get("GITHUB_TOKEN") or env.get("GH_TOKEN") or "").strip()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Run requested pull-request checks from GitHub issues.")
    ap.add_argument("--once", action="store_true", help="handle the queue a single time and exit")
    ap.add_argument("--poll", type=int, default=60, help="seconds between queue checks")
    args = ap.parse_args(argv)
    settings = settings_from_env()
    token = _token(os.environ)
    if not token or not settings.repo or "/" not in settings.repo:
        print("Set GITHUB_TOKEN and POC_GITHUB_REPOSITORY (owner/repo). The token is not printed.", file=sys.stderr)
        return 2
    secrets = [token]
    host_key = (os.environ.get("NEBIUS_API_KEY") or "").strip()
    if len(host_key) >= 8:
        secrets.append(host_key)
    lock_path = settings.state_path.with_suffix(".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_handle = lock_path.open("a+")
    try:
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print("another worker is already running")
        return 0
    client = GitHubClient(settings.repo, token)
    while True:
        state = load_state(settings.state_path)
        try:
            process_queue(client, settings, datetime.now(IST), state, secrets=secrets)
        except GitHubError as exc:
            print(scrub(str(exc), secrets), file=sys.stderr)
        if args.once:
            return 0
        time.sleep(max(15, args.poll))


if __name__ == "__main__":
    raise SystemExit(main())
