"""Product and demo helper for console and daily checks.

A study run (benchmark mode) never calls this for effect: ``active`` is false, and the
callers keep their original install path. Nothing here chooses a verdict. Notes are
background. A package is installed only when the project's own files list it, or when
a search suggestion's PyPI page links back to the same GitHub repository.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import sys
import urllib.parse
import urllib.request
from pathlib import Path, PurePosixPath

from evals.label_study_pairs import split_repo

SETUP_LABEL = "rerun, setup problem"
MAX_SETUP_RETRIES = 2  # further install attempts after the first failure
MAX_GAP_TRIES = 3  # setup-gap fix-and-rerun tries after the first run; a PR-caused test failure is never retried
MAX_GAP_ROUNDS = MAX_GAP_TRIES + 1  # the first run plus up to 3 setup-gap reruns
RETRY_LIMITS = (
    "If setup fails, the helper retries the install up to 2 times. "
    "If a test still can't be verified because something is missing or fails to import, it looks up the cause, "
    "installs the fix on both sides and reruns that step, up to 3 tries."
)
TAVILY_TIMEOUT = 8
PYPI_TIMEOUT = 8
MAX_SUGGESTIONS = 8
# Probe line coverage is measured again after a setup rerun only when the change is this small.
# A larger change skips that measurement, and the rerun cannot raise could_not_verify to verified.
SMALL_CHANGED_LINES = 200
SIDES = ("main", "pr")
TEST_EXTRAS = ("test", "tests", "testing")
SECRET_ENVS = (
    "NEBIUS_API_KEY",
    "TAVILY_API_KEY",
    "GITHUB_TOKEN",
    "GITHUB_POC_TOKEN",
    "GH_TOKEN",
    "GITHUB_APP_INSTALLATION_TOKEN",
)
GITHUB_TOKEN_ENVS = (
    "GITHUB_TOKEN",
    "GITHUB_POC_TOKEN",
    "GH_TOKEN",
    "GITHUB_APP_INSTALLATION_TOKEN",
)
SECRET_KEYS = {"api_key", "apikey", "token", "authorization"}
VERDICTS = {"verified", "needs_attention", "could_not_verify", "no_code_change"}
SKIP_DIRS = {".git", ".venv", "venv", "node_modules", "__pycache__"}
APT_FILES = ("apt.txt", "system-requirements.txt", "requirements-apt.txt")
_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_APT = re.compile(r"^[a-z0-9][a-z0-9.+-]{1,60}$")
_PY_VER = re.compile(r"(\d+)\.(\d+)")
_GAP_MARKERS = (
    "importerror",
    "modulenotfounderror",
    "no module named",
    "cannot open shared object",
    "error while loading shared libraries",
    "library not loaded",
    "filenotfounderror",
    "no such file or directory",
    "missing fixture",
    "test data",
    "resolutionimpossible",
    "version conflict",
    "conflicting dependencies",
    "fails to load",
    "failed to load",
)
_SETUP_MARKERS = (
    "install failed",
    "setup failed",
    "could not be set up",
    "build failed",
    "source checkout",
    "git step failed",
    "checkout of",
    "timed out",
    "timeout",
    "network",
    "urlerror",
    "connection",
    "no network",
    "oom",
    "signal 9",
    "killed",
    "too much memory",
    "infrastructure failure",
)
# Product-check stops. These are signals in an install log or a requirement line, not repository names.
_DISK_FULL = re.compile(r"no space left on device|errno 28|disk quota exceeded", re.I)
_FLAT_LAYOUT = re.compile(r"multiple top-level packages discovered in a flat-layout", re.I)
# A CUDA build, not every name that contains "nvidia": nvidia-*-cu*, cuda-*, or a +cu wheel.
_GPU_REQ = re.compile(r"(?i)(?:^|[^A-Za-z0-9])(?:nvidia-[a-z0-9._-]*-cu\d*|cuda-[a-z0-9._-]+)|\+cu\d+")
_PYTEST_ERROR = re.compile(
    r"(?i)(?:module)?notfounderror:[^\n<]{0,180}|filenotfounderror:[^\n<]{0,180}|"
    r"no module named ['\"]?[\w.]+|importerror:[^\n<]{0,180}|"
    r"cannot open shared object file[^\n<]{0,120}|error while loading shared libraries:[^\n<]{0,120}|"
    r"library not loaded:[^\n<]{0,120}|error collecting [^\n<]{0,160}|"
    r"no such file or directory:[^\n<]{0,160}|resolutionimpossible:[^\n<]{0,160}|"
    r"version conflict[^\n<]{0,80}"
)
DISK_FULL_REASON = ("unsupported: the install ran out of disk space, so its temporary build files were removed "
                    "and nothing was tested")
FLAT_LAYOUT_REASON = ("unsupported: this project isn't installable as a Python package "
                      "(multiple top-level packages in a flat layout)")


def active(runner) -> bool:
    """True for a console or daily check. False for a study run and for a missing runner."""
    if runner is None:
        return False
    return not bool(getattr(runner, "bench", None))


def norm(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def req_name(req: str) -> str:
    return re.split(r"[\[<>=!~;,@\s]", (req or "").strip(), maxsplit=1)[0]


def safe_apt_name(name: str) -> bool:
    return bool(_APT.fullmatch(name or ""))


def redact(text: str, env: dict | None = None) -> str:
    """Replace known secret values. The values are never written back out."""
    env = os.environ if env is None else env
    out = "" if text is None else str(text)
    for name in SECRET_ENVS:
        raw = env.get(name)
        secret = str(raw).strip() if raw else ""
        if len(secret) >= 4:
            out = out.replace(secret, "[redacted]")
    out = re.sub(r"(?i)(bearer\s+)\S{4,}", r"\1[redacted]", out)

    def _hide(match):
        value = match.group(2)
        if value.rstrip(".").lower() in {"present", "missing", "true", "false", "none"}:
            return match.group(0)
        return match.group(1) + "[redacted]"

    out = re.sub(
        r"(?i)((?:api[_-]?key|token|authorization)['\"]?\s*[:=]\s*['\"]?)([^\s'\"]{4,})",
        _hide,
        out,
    )
    return out


def redact_obj(value, env: dict | None = None):
    if isinstance(value, str):
        return redact(value, env)
    if isinstance(value, dict):
        out = {}
        for key, item in value.items():
            if str(key).lower() in SECRET_KEYS:
                out[key] = "[redacted]"
            else:
                out[key] = redact_obj(item, env)
        return out
    if isinstance(value, list):
        return [redact_obj(item, env) for item in value]
    return value


def _unique(lines: list[str]) -> list[str]:
    out, seen = [], set()
    for line in lines:
        if line and line not in seen:
            seen.add(line)
            out.append(line)
    return out


def announce(lines, env: dict | None = None) -> list[str]:
    """Print helper lines and record them for the console. Secrets are removed first."""
    clean = [redact(str(line), env) for line in lines if str(line).strip()]
    for line in clean:
        print(line, flush=True)
    if clean:
        from poc import run_progress
        run_progress.emit("demo_helper", detail="\n".join(clean)[:2000])
    return clean


def public_notes(events, record=None, env: dict | None = None) -> list[str]:
    lines: list[str] = []
    for event in events or []:
        if isinstance(event, dict) and event.get("stage") == "demo_helper" and event.get("detail"):
            lines.extend(str(event["detail"]).splitlines())
    notes = ((record or {}).get("demo_helper") or {}).get("notes") if isinstance(record, dict) else None
    if isinstance(notes, list):
        lines.extend(str(line) for line in notes)
    return _unique([redact(line, env) for line in lines])


def _memory() -> dict | None:
    try:
        text = Path("/proc/meminfo").read_text()
        total = int(re.search(r"MemTotal:\s+(\d+)", text).group(1))
        avail = re.search(r"MemAvailable:\s+(\d+)", text)
        available = int(avail.group(1)) if avail else total
    except (OSError, AttributeError, ValueError):
        return None
    return {"total_gb": round(total / 1024 / 1024, 1), "available_gb": round(available / 1024 / 1024, 1)}


def preflight(path, env: dict | None = None, tools=("git", "python3", "uv"), model_token=None,
              memory=None, disk=None, which=None) -> dict:
    """Report tokens, memory, disk, and tools. Token values are never included."""
    env = os.environ if env is None else env
    lines = []
    github = any(str(env.get(name) or "").strip() for name in GITHUB_TOKEN_ENVS)
    lines.append(f"Setup check: GitHub token: {'present' if github else 'missing'}.")
    if model_token == "nebius":
        present = bool(str(env.get("NEBIUS_API_KEY") or "").strip())
        lines.append(f"Setup check: Nebius token: {'present' if present else 'missing'}.")
    mem = memory() if memory else _memory()
    if mem:
        lines.append(f"Setup check: free memory {mem['available_gb']} GB (of {mem['total_gb']} GB).")
    else:
        lines.append("Setup check: free memory could not be read.")
    if disk:
        usage = disk(path)
    else:
        usage = shutil.disk_usage(path)
    free = round(getattr(usage, "free", usage) / 1e9, 1)
    lines.append(f"Setup check: free disk {free} GB.")
    which = which or shutil.which
    ok = True
    for tool in tools:
        if which(tool):
            lines.append(f"Demo helper: {tool} is installed.")
        else:
            ok = False
            lines.append(f"Demo helper: {tool} is not installed.")
    return {"ok": ok, "lines": [redact(line, env) for line in lines]}


class MemoryCache:
    def __init__(self):
        self._data = {}

    def get(self, key):
        value = self._data.get(key)
        return json.loads(json.dumps(value)) if isinstance(value, dict) else value

    def put(self, key, value):
        self._data[key] = json.loads(json.dumps(value))


class FileCache:
    def __init__(self, path):
        self.path = Path(path)
        self._data = {}
        if self.path.is_file():
            try:
                loaded = json.loads(self.path.read_text())
                if isinstance(loaded, dict):
                    self._data = loaded
            except (OSError, json.JSONDecodeError):
                self._data = {}

    def get(self, key):
        value = self._data.get(key)
        return json.loads(json.dumps(value)) if isinstance(value, dict) else None

    def put(self, key, value):
        self._data[key] = value
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(self._data))
        except OSError as exc:
            # The cache is only a speed-up, so the check goes on, but the failed write is reported, not hidden.
            print(f"WARNING: could not write the lookup cache {self.path.name}: {type(exc).__name__}: {exc}",
                  file=sys.stderr, flush=True)


def live_fetch(query: str, timeout: float = TAVILY_TIMEOUT, env: dict | None = None) -> dict:
    from poc import tavily_docs
    return tavily_docs.lookup(query, timeout=timeout, env=env)


def _networkish(text: str) -> bool:
    low = (text or "").lower()
    return any(word in low for word in ("timed out", "timeout", "urlerror", "network", "nodename",
                                        "unreachable", "connection", "errno"))


def _project_name(repo: str, project: str) -> str:
    return (project or "").strip() or ((repo or "").split("/")[-1] or "project")


def lookup_queries(repo: str, project: str) -> list[str]:
    """Name this distribution and this GitHub repository, and stay on their own sites.

    An open search was returning forks and unrelated products. Each query includes the
    PyPI distribution name and the repository URL, and is limited to that repository,
    its docs on GitHub, or its page on pypi.org.
    """
    name = _project_name(repo, project)
    parts = split_repo(repo or "")
    if not parts:
        return [f"{name} python setup install instructions"]
    owner, repo_name = parts
    github = f"https://github.com/{owner}/{repo_name}"
    pypi = f"https://pypi.org/project/{name}/"
    repo_site = f"site:github.com/{owner}/{repo_name}"
    return [
        f"{name} python setup install instructions {github} {repo_site}",
        f"{name} python documentation install {github} {repo_site}",
        f"{name} python install requirements {pypi} {github} site:pypi.org",
    ]


def _project_needles(repo: str, project: str) -> list[str]:
    """Names a kept result must mention: the distribution, or owner/repo."""
    needles = []
    name = _project_name(repo, project)
    if name and name != "project":
        needles.append(name)
    parts = split_repo(repo or "")
    if parts:
        owner, repo_name = parts
        needles.append(f"{owner}/{repo_name}")
        needles.append(f"github.com/{owner}/{repo_name}")
    return needles


def _mentions_project(text: str, needles: list[str]) -> bool:
    """Whole-name match. A dot, hyphen, or underscore is part of the name, so inflect is not inflection or inflect-fork."""
    if not text:
        return False
    for needle in needles:
        if needle and re.search(rf"(?<![A-Za-z0-9._-]){re.escape(needle)}(?![A-Za-z0-9._-])", text, re.I):
            return True
    return False


def _relevant_result(item: dict, needles: list[str]) -> bool:
    blob = "\n".join(str(item.get(key) or "") for key in ("title", "url", "content"))
    return _mentions_project(blob, needles)


# Lint and type-check config. These are not install instructions.
_LINT_FILES = frozenset({
    "mypy.ini", ".mypy.ini", "ruff.toml", ".ruff.toml", ".flake8",
    ".pylintrc", "pylintrc", "pyrightconfig.json", ".pyrightconfig.json", ".isort.cfg",
})
_SETUP_RANK = {"pyproject.toml": 0, "setup.cfg": 1, "setup.py": 2}
_RANK_REQUIREMENTS = 3
_RANK_INSTALL_DOC = 4
_RANK_PYPI = 5
_RANK_OTHER = 6
_PYPI_HOSTS = frozenset({"pypi.org", "pypi.python.org"})
_DOC_STEMS = frozenset({"readme", "install", "installation", "installing"})


def _path_parts(url: str) -> list[str]:
    path = urllib.parse.unquote(urllib.parse.urlsplit(url or "").path or "")
    return [part for part in path.split("/") if part]


def _title_tail(title: str) -> str:
    return (title or "").strip().replace("\\", "/").split("/")[-1].strip().lower()


def _names_a_lint_file(url: str, title: str) -> bool:
    names = [part.lower() for part in _path_parts(url)]
    tail = _title_tail(title)
    if tail:
        names.append(tail)
    return any(name in _LINT_FILES for name in names)


def _doc_stem(name: str) -> str:
    low = (name or "").lower()
    for suffix in (".markdown", ".html", ".rst", ".txt", ".md"):
        if low.endswith(suffix):
            return low[: -len(suffix)]
    return low


def _url_is_install_doc(url: str) -> bool:
    parts = [part.lower() for part in _path_parts(url)]
    base = parts[-1] if parts else ""
    stem = _doc_stem(base)
    if stem in _DOC_STEMS:
        return True
    docs = {"docs", "doc", "documentation"}
    extra = _DOC_STEMS | {"setup", "getting-started", "quickstart"}
    return any(part in docs for part in parts[:-1]) and stem in extra


def _title_is_install_doc(title: str) -> bool:
    low = (title or "").strip().lower()
    return low in _DOC_STEMS or _doc_stem(_title_tail(title)) in _DOC_STEMS


def _source_rank(url: str, title: str) -> int:
    parts = [part.lower() for part in _path_parts(url)]
    names = [parts[-1]] if parts else []
    tail = _title_tail(title)
    if tail and tail not in names:
        names.append(tail)
    for name in names:
        if name in _SETUP_RANK:
            return _SETUP_RANK[name]
    if any(name.startswith("requirements") for name in names) or any(part.startswith("requirements") for part in parts):
        return _RANK_REQUIREMENTS
    if _url_is_install_doc(url):
        return _RANK_INSTALL_DOC
    host = (urllib.parse.urlsplit(url or "").hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    if host in _PYPI_HOSTS and len(parts) >= 2 and parts[0] == "project":
        return _RANK_PYPI
    if _title_is_install_doc(title):
        return _RANK_INSTALL_DOC
    return _RANK_OTHER


def _canonical_url(url: str, project: str) -> tuple[str, bool]:
    """One address per page. A versioned PyPI release page becomes /project/<name>/."""
    raw = (url or "").strip()
    if not raw:
        return "", False
    parsed = urllib.parse.urlsplit(raw)
    host = (parsed.hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    path = re.sub(r"/{2,}", "/", urllib.parse.unquote(parsed.path or ""))
    if host in _PYPI_HOSTS:
        parts = [part for part in path.split("/") if part]
        if len(parts) >= 2 and parts[0].lower() == "project":
            dist = parts[1]
            if project and dist.lower() == project.lower():
                dist = project
            else:
                dist = dist.lower()
            return f"https://pypi.org/project/{dist}/", len(parts) > 2
    if len(path) > 1:
        path = path.rstrip("/")
    scheme = (parsed.scheme or "https").lower()
    netloc = host
    if parsed.port and parsed.port not in {80, 443}:
        netloc = f"{host}:{parsed.port}"
    return urllib.parse.urlunsplit((scheme, netloc, path, parsed.query, "")), False


def polish_results(items: list, project: str = "") -> list[dict]:
    """Drop lint config, fold old PyPI releases into the current page, and list setup sources once, first."""
    ranked = []
    for index, item in enumerate(items or []):
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "")
        url = str(item.get("url") or "")
        if _names_a_lint_file(url, title):
            continue
        canonical, rewritten = _canonical_url(url, project)
        rank = _source_rank(canonical or url, title)
        ranked.append((rank, int(rewritten), index, item, canonical))
    ranked.sort(key=lambda row: (row[0], row[1], row[2]))
    seen: set[str] = set()
    out = []
    for _rank, _rewritten, _index, item, canonical in ranked:
        key = canonical.lower() if canonical else "title:" + str(item.get("title") or "").lower()
        if key in seen:
            continue
        seen.add(key)
        kept = dict(item)
        if canonical:
            kept["url"] = canonical
        out.append(kept)
    return out


def scope_lookup(payload: dict, repo: str, project: str = "") -> dict:
    """Drop hits that never name this project. They are not shown, logged, or used."""
    if not isinstance(payload, dict):
        return payload
    needles = _project_needles(repo, project)
    kept = [item for item in (payload.get("results") or []) if isinstance(item, dict) and _relevant_result(item, needles)]
    out = dict(payload)
    out["results"] = polish_results(kept, _project_name(repo, project))
    answer = out.get("answer")
    if answer and not _mentions_project(str(answer), needles):
        out["answer"] = None
    return out


def _result_lines(queries: list[str], results: list[dict], errors: list[str], live: bool) -> list[str]:
    n = len(results)
    if n:
        lines = [f"Looked up with Tavily: {n} results"]
    elif live and any(_networkish(err) for err in errors):
        lines = ["Looked up with Tavily: the lookup failed (no network)."]
    elif live and errors:
        lines = ["Looked up with Tavily: the lookup failed."]
    else:
        lines = [f"Looked up with Tavily: {n} results"]
    lines.extend(f"Query: {query}" for query in queries)
    for item in results:
        title = item.get("title") or item.get("url") or "result"
        lines.append(f"Source: {title} — {item.get('url') or ''}")
    return lines


def product_runner(runner) -> bool:
    """True for a product check. False for a study run, the daily study, and a missing runner.

    Matches ``ops.daily_run.product_route``: a single pull request with the product-check flag, and not a
    benchmark. A study run keeps the lookup optional.
    """
    if runner is None or getattr(runner, "bench", None):
        return False
    if not getattr(runner, "pr", None):
        return False
    return bool(getattr(runner, "product_check", False))


def lookup_stop_reason(rec: dict | None) -> str | None:
    """The plain reason a product check must stop, or None when the lookup did not stop it."""
    if not isinstance(rec, dict):
        return None
    tavily = (rec.get("demo_helper") or {}).get("tavily") if isinstance(rec.get("demo_helper"), dict) else None
    if not isinstance(tavily, dict) or not tavily.get("stop"):
        return None
    reason = str(tavily.get("stop_reason") or "").strip()
    return reason or None


def _lookup_body(queries, results, *, ok, skipped, refused, failed, stop, stop_reason, live, cached,
                 text, errors, lines) -> dict:
    return {
        "ok": ok, "skipped": skipped, "refused": refused, "failed": failed, "stop": stop,
        "stop_reason": stop_reason, "live_call": live, "cached": cached, "queries": list(queries),
        "results": [{"title": item["title"], "url": item["url"], "query": item["query"]} for item in results],
        "result_count": len(results), "text": text, "errors": list(errors), "lines": list(lines),
    }


def lookup_project(repo: str, project: str, cache, env: dict | None = None, fetch=None,
                   required: bool = False) -> dict:
    """Look up setup instructions. A live call is recorded only when a fetch actually runs.

    ``required`` is a product check. A missing key then refuses, and a failed lookup stops the check.
    A study run and the daily study pass ``required`` false and keep the earlier skip.
    """
    from poc import tavily_docs
    env = os.environ if env is None else env
    queries = lookup_queries(repo, project)
    if not str(env.get("TAVILY_API_KEY") or "").strip():
        if required:
            line = tavily_docs.MISSING_KEY
            return _lookup_body(
                queries, [], ok=False, skipped=False, refused=True, failed=True, stop=True,
                stop_reason=line, live=False, cached=False, text="", errors=[line], lines=[line])
        return _lookup_body(
            queries, [], ok=False, skipped=True, refused=False, failed=False, stop=False, stop_reason="",
            live=False, cached=False, text="", errors=[],
            lines=["Tavily lookup skipped: TAVILY_API_KEY is not set."])
    fetch = fetch or live_fetch
    gathered, answers, errors = [], [], []
    live = False
    cached_any = False
    fresh_any = False
    for query in queries:
        hit = cache.get(query) if cache is not None else None
        if isinstance(hit, dict):
            cached_any = True
            payload = hit
        else:
            try:
                payload = fetch(query, timeout=TAVILY_TIMEOUT, env=env)
            except Exception as exc:  # noqa: BLE001 — the message may contain the key; redact it
                payload = {"ok": False, "error": redact(f"{type(exc).__name__}: {exc}", env),
                           "query": query, "results": []}
            if not isinstance(payload, dict):
                payload = {"ok": False, "error": "lookup returned nothing", "query": query, "results": []}
            live = True
            fresh_any = True
            stored = redact_obj(scope_lookup(dict(payload), repo, project), env)
            stored["live_call"] = False
            if cache is not None:
                cache.put(query, stored)
            payload = stored
        payload = redact_obj(scope_lookup(payload, repo, project), env)
        if payload.get("answer"):
            answers.append(str(payload["answer"]))
        for item in payload.get("results") or []:
            if not isinstance(item, dict):
                continue
            gathered.append({"title": item.get("title") or "", "url": item.get("url") or "", "query": query,
                             "content": item.get("content") or ""})
        if payload.get("error"):
            errors.append(str(payload["error"]))
    results = polish_results(gathered, _project_name(repo, project))
    texts = []
    for answer in answers:
        if answer not in texts:
            texts.append(answer)
    for item in results:
        if item.get("content"):
            texts.append(str(item["content"]))
    lines = [redact(line, env) for line in _result_lines(queries, results, errors, live)]
    clean_errors = [redact(err, env) for err in errors]
    text = redact("\n".join(texts), env)
    failed = bool(clean_errors)
    stop = bool(required and failed)
    stop_reason = ""
    if stop:
        why = clean_errors[0] if clean_errors else "the lookup returned nothing usable"
        stop_reason = why if why.lower().startswith("could not verify") else (
            f"could not verify: the setup lookup failed: {why}")
        if stop_reason not in lines:
            lines = [stop_reason, *lines]
    return _lookup_body(
        queries, results, ok=not failed, skipped=False, refused=False, failed=failed, stop=stop,
        stop_reason=stop_reason, live=live, cached=cached_any and not fresh_any, text=text,
        errors=clean_errors, lines=lines)


def begin_check(runner, rec: dict, repo: str, project: str, cache_dir, env: dict | None = None, fetch=None):
    """Preflight and Tavily lookup before either side is installed. No-op on a study run."""
    if not active(runner):
        return None
    env = os.environ if env is None else env
    try:
        if (rec.get("demo_helper") or {}).get("tavily"):
            return rec["demo_helper"]
        info = preflight(cache_dir or ".", env=env, model_token=getattr(runner, "model_provider", None))
        cache = FileCache(Path(cache_dir) / "tavily-cache.json") if cache_dir else MemoryCache()
        from poc import run_progress
        run_progress.emit("setup_lookup", detail="Looking up how this project is set up (Python, config, libraries)")
        looked = lookup_project(repo, project, cache, env=env, fetch=fetch, required=product_runner(runner))
        block = rec.setdefault("demo_helper", {})
        block["preflight"] = {"ok": info["ok"]}
        block["tavily"] = looked
        notes = list(block.get("notes") or [])
        notes.extend(info["lines"])
        notes.extend(looked["lines"])
        block["notes"] = _unique([redact(line, env) for line in notes])
        announce(info["lines"] + looked["lines"], env=env)
        return block
    except Exception as exc:  # noqa: BLE001 — do not print the message; it might contain a key
        detail = redact(f"{type(exc).__name__}: {exc}", env)
        if product_runner(runner):
            reason = f"could not verify: the setup lookup failed: {detail}"
            block = rec.setdefault("demo_helper", {})
            block["tavily"] = _lookup_body(
                [], [], ok=False, skipped=False, refused=False, failed=True, stop=True,
                stop_reason=reason, live=False, cached=False, text="", errors=[detail], lines=[reason])
            notes = list(block.get("notes") or [])
            notes.append(reason)
            block["notes"] = _unique([redact(line, env) for line in notes])
            announce([reason], env=env)
            return block
        announce([f"Demo helper: {type(exc).__name__}"], env=env)
        return None


def _req_lines(text: str) -> list[str]:
    out = []
    for raw in (text or "").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or line.startswith(("-", ".", "--")):
            continue
        name = req_name(line)
        if _NAME.fullmatch(name):
            out.append(line)
    return out


def _read(path: Path) -> str:
    try:
        return path.read_text(errors="replace")
    except OSError:
        return ""


def _pyproject(path: Path) -> dict:
    if not path.is_file():
        return {}
    import tomllib
    try:
        return tomllib.loads(_read(path))
    except Exception:  # noqa: BLE001 — a broken project file is skipped, not fatal
        return {}


def _add_pkg(found: list[dict], seen: set, requirement: str, *, kind: str, action: str, source: str,
             reason: str, self_dist: str) -> None:
    name = req_name(requirement)
    if not _NAME.fullmatch(name) or (self_dist and norm(name) == norm(self_dist)):
        return
    key = norm(name)
    if key in seen and action == "noted":
        return
    if key in seen:
        return
    seen.add(key)
    found.append({"requirement": requirement, "name": name, "kind": kind, "action": action, "source": source,
                  "reason": reason, "sides": ["main", "pr"]})


def declared_packages(checkout, self_dist: str = "", skip_files=()) -> list[dict]:
    """Packages the checkout lists. Runtime deps are noted. Test extras and requirements are installed.

    ``skip_files``: requirement files not to read (a product check passes the aggregate files of a component app)."""
    root = Path(checkout)
    skip = {Path(f).resolve() for f in skip_files or ()}
    found: list[dict] = []
    seen: set = set()
    data = _pyproject(root / "pyproject.toml")
    project = data.get("project") if isinstance(data.get("project"), dict) else {}
    for req in project.get("dependencies") or []:
        if isinstance(req, str):
            _add_pkg(found, seen, req, kind="runtime", action="noted", source="pyproject",
                     reason="runtime dependency, installed with the project", self_dist=self_dist)
    for bucket, label in ((project.get("optional-dependencies"), "pyproject"), (data.get("dependency-groups"), "pyproject")):
        if not isinstance(bucket, dict):
            continue
        for extra, reqs in bucket.items():
            if norm(str(extra)) not in TEST_EXTRAS or not isinstance(reqs, list):
                continue
            for req in reqs:
                if isinstance(req, str):
                    _add_pkg(found, seen, req, kind="test-extra", action="install", source=label,
                             reason=f"listed in the {extra} extra", self_dist=self_dist)
    cfg = root / "setup.cfg"
    if cfg.is_file():
        import configparser
        parser = configparser.ConfigParser()
        try:
            parser.read_string(_read(cfg))
        except (configparser.Error, OSError):
            parser = None
        if parser is not None:
            if parser.has_option("options", "install_requires"):
                for req in _req_lines(parser.get("options", "install_requires")):
                    _add_pkg(found, seen, req, kind="runtime", action="noted", source="setup.cfg",
                             reason="runtime dependency, installed with the project", self_dist=self_dist)
            if parser.has_section("options.extras_require"):
                for extra, value in parser.items("options.extras_require"):
                    if norm(extra) not in TEST_EXTRAS:
                        continue
                    for req in _req_lines(value):
                        _add_pkg(found, seen, req, kind="test-extra", action="install", source="setup.cfg",
                                 reason=f"listed in the {extra} extra", self_dist=self_dist)
    setup_py = _read(root / "setup.py")
    for req in re.findall(r"""['\"]([^'\"]+)['\"]""", _section(setup_py, "install_requires")):
        _add_pkg(found, seen, req, kind="runtime", action="noted", source="setup.py",
                 reason="runtime dependency, installed with the project", self_dist=self_dist)
    for extra in TEST_EXTRAS:
        blob = _section(setup_py, extra)
        for req in re.findall(r"""['\"]([^'\"]+)['\"]""", blob):
            _add_pkg(found, seen, req, kind="test-extra", action="install", source="setup.py",
                     reason=f"listed in the {extra} extra", self_dist=self_dist)
    for path in _requirement_files(root):
        if path.resolve() in skip:
            continue
        for req in _req_lines(_read(path)):
            _add_pkg(found, seen, req, kind="requirements", action="install", source=path.name,
                     reason=f"listed in {path.name}", self_dist=self_dist)
    return found


def _collect_reqs(found: list[str], seen: set, lines) -> None:
    for line in lines or []:
        if not isinstance(line, str):
            continue
        name = req_name(line)
        key = norm(name)
        if _NAME.fullmatch(name) and key not in seen:
            seen.add(key)
            found.append(line.strip())


def declared_requirement_lines(checkout) -> list[str]:
    """Every requirement the project declares, extras included.

    The gap step uses this to recognise a name the error already produced. It does not install them.
    """
    root = Path(checkout)
    found: list[str] = []
    seen: set = set()
    data = _pyproject(root / "pyproject.toml")
    project = data.get("project") if isinstance(data.get("project"), dict) else {}
    _collect_reqs(found, seen, project.get("dependencies"))
    for bucket in (project.get("optional-dependencies"), data.get("dependency-groups")):
        if not isinstance(bucket, dict):
            continue
        for reqs in bucket.values():
            if isinstance(reqs, list):
                _collect_reqs(found, seen, reqs)
    cfg = root / "setup.cfg"
    if cfg.is_file():
        import configparser
        parser = configparser.ConfigParser()
        try:
            parser.read_string(_read(cfg))
        except (configparser.Error, OSError):
            parser = None
        if parser is not None:
            if parser.has_option("options", "install_requires"):
                _collect_reqs(found, seen, _req_lines(parser.get("options", "install_requires")))
            if parser.has_section("options.extras_require"):
                for _extra, value in parser.items("options.extras_require"):
                    _collect_reqs(found, seen, _req_lines(value))
    setup_py = _read(root / "setup.py")
    _collect_reqs(found, seen, re.findall(r"""['\"]([^'\"]+)['\"]""", _section(setup_py, "install_requires")))
    extras_blob = _section(setup_py, "extras_require")
    for match in re.finditer(r"""['\"][^'\"]+['\"]\s*:\s*\[([^\]]*)\]""", extras_blob):
        _collect_reqs(found, seen, re.findall(r"""['\"]([^'\"]+)['\"]""", match.group(1)))
    for path in _requirement_files(root):
        _collect_reqs(found, seen, _req_lines(_read(path)))
    return found


def _plain_req_lines(text: str):
    for raw in (text or "").splitlines():
        line = raw.split("#", 1)[0].strip()
        if line and not line.startswith(("-", ".", "--")):
            yield line


def _iter_required_lines(checkout):
    """Required dependency lines, including local version markers such as +cu. Extras are not included."""
    root = Path(checkout)
    data = _pyproject(root / "pyproject.toml")
    project = data.get("project") if isinstance(data.get("project"), dict) else {}
    for line in project.get("dependencies") or []:
        if isinstance(line, str):
            yield line
    cfg = root / "setup.cfg"
    if cfg.is_file():
        import configparser
        parser = configparser.ConfigParser()
        try:
            parser.read_string(_read(cfg))
        except (configparser.Error, OSError):
            parser = None
        if parser is not None and parser.has_option("options", "install_requires"):
            yield from _plain_req_lines(parser.get("options", "install_requires"))
    setup_py = _read(root / "setup.py")
    yield from re.findall(r"""['\"]([^'\"]+)['\"]""", _section(setup_py, "install_requires"))
    base = root / "requirements.txt"
    if base.is_file():
        yield from _plain_req_lines(_read(base))


def gpu_only_requirement(checkout) -> str | None:
    """A required dependency that is a CUDA build, or None.

    The signal is the requirement name: an nvidia-*-cu* package, a cuda-* package, or a +cu wheel.
    A name that only contains "nvidia" is not a CUDA build. Optional extras are ignored.
    """
    for line in _iter_required_lines(checkout):
        if _GPU_REQ.search(line):
            name = req_name(line)
            return name or line.strip()
    return None


def gpu_reason(name: str) -> str:
    return (f"unsupported: this project needs a GPU / CUDA build (it requires {name}), "
            "so it was not installed")


def disk_full(text: str) -> bool:
    return bool(_DISK_FULL.search(text or ""))


def flat_layout(text: str) -> bool:
    return bool(_FLAT_LAYOUT.search(text or ""))


def _section(text: str, name: str) -> str:
    match = re.search(rf"{re.escape(name)}\s*=\s*(\[[^\]]*\]|\{{[^\}}]*\}})", text or "", re.S)
    return match.group(1) if match else ""


def _requirement_files(root: Path) -> list[Path]:
    out = []
    if not root.is_dir():
        return out
    for dirpath, dirnames, filenames in os.walk(root):
        rel = Path(dirpath).relative_to(root)
        dirnames[:] = [name for name in dirnames if name not in SKIP_DIRS and len(rel.parts) < 2]
        if len(rel.parts) > 2:
            continue
        for name in sorted(filenames):
            if name.startswith("requirements") and name.endswith(".txt"):
                out.append(Path(dirpath) / name)
    return out


# ---------------------------------------------------------------- component apps (product checks only)
COMPONENT_MANIFEST = "manifest.json"
_COMPONENT_DEPTH = 5


def component_dirs(root) -> dict[str, list[str]]:
    """Folders (relative, posix) that hold a JSON manifest declaring a ``requirements`` list, with that list.

    This is the project's own per-component metadata; nothing here names a project or a package."""
    root = Path(root)
    out: dict[str, list[str]] = {}
    if not root.is_dir():
        return out
    for dirpath, dirnames, filenames in os.walk(root):
        rel = Path(dirpath).relative_to(root)
        dirnames[:] = sorted(n for n in dirnames if n not in SKIP_DIRS and not n.startswith(".")
                             and len(rel.parts) < _COMPONENT_DEPTH)
        if COMPONENT_MANIFEST not in filenames or not rel.parts:
            continue
        if (Path(dirpath) / COMPONENT_MANIFEST).is_symlink():
            continue   # a manifest that points elsewhere is not the component's own metadata
        try:
            data = json.loads(_read(Path(dirpath) / COMPONENT_MANIFEST) or "null")
        except ValueError:
            continue
        reqs = data.get("requirements") if isinstance(data, dict) else None
        if isinstance(reqs, list) and all(isinstance(r, str) for r in reqs):
            out[rel.as_posix()] = [r.strip() for r in reqs if r.strip()]
    return out


def aggregate_requirement_files(root, components: dict[str, list[str]]) -> list[Path]:
    """Top-level requirements files that collect many components' requirements (requirements_all-style).

    A file is an aggregate when lines from at least two different components' manifests appear in it and those
    lines are at least half of the file. Decided from the content, never from the file name. A project with fewer
    than three components, or whose only requirements file this is, has no aggregate (that file is its core)."""
    root = Path(root)
    if len(components) < 3:
        return []
    candidates = sorted(root.glob("requirements*.txt")) if root.is_dir() else []
    if len([p for p in candidates if p.is_file()]) < 2:
        return []
    owner: dict[str, set] = {}
    for comp, reqs in components.items():
        for req in reqs:
            owner.setdefault(norm(req_name(req)), set()).add(comp)
    out = []
    for path in candidates:
        lines = _req_lines(_read(path))
        if not lines:
            continue
        hit = [norm(req_name(line)) for line in lines if norm(req_name(line)) in owner]
        comps = set().union(*(owner[h] for h in hit)) if hit else set()
        if len(comps) >= 2 and 2 * len(hit) >= len(lines):
            out.append(path)
    return out


def component_for_changes(changed, components: dict[str, list[str]], ignore=()) -> str | None:
    """The single component every changed file belongs to, or None.

    A file belongs to a component when it is inside that component's folder, or inside ``tests/<path>`` or
    ``tests/<name>`` for that component (tests kept in a mirrored tree, at the top level or under the component's
    parent package). A folder elsewhere that merely shares the name does not count. Files in ``ignore`` (aggregate
    files that a requirement bump regenerates) are not counted. A path with a ``..`` part, any other file, or two
    components gives None."""
    ignore = set(ignore)
    found = set()
    counted = 0
    for raw in changed or []:
        path = PurePosixPath(str(raw).lstrip("/"))
        if ".." in path.parts:
            return None
        if path.as_posix() in ignore:
            continue
        counted += 1
        text = path.as_posix()
        inside = [c for c in components if text.startswith(c + "/")]
        if inside:
            found.add(max(inside, key=len))
            continue
        depth = {c: max((len(t) for t in _test_roots(c) if text.startswith(t + "/")), default=0) for c in components}
        best = max(depth.values(), default=0)
        tied = [c for c, d in depth.items() if d and d == best]
        if len(tied) != 1:
            return None
        found.add(tied[0])
    return next(iter(found)) if counted and len(found) == 1 else None


def _test_roots(comp: str) -> list[str]:
    """Mirrored test folders for a component: tests/<path>, tests/<path below the top package>, tests/<name>."""
    parts = PurePosixPath(comp).parts
    return list(dict.fromkeys("tests/" + "/".join(parts[i:]) for i in range(len(parts))))


def lint_only_requirement_files(root, ignore=()) -> list[Path]:
    """Top-level requirements files that only pin the project's lint hooks (pre-commit style), decided from content:
    every requirement in the file is named in the project's own .pre-commit-config.yaml. No file or package names."""
    root = Path(root)
    config = root / ".pre-commit-config.yaml"
    if not config.is_file() or config.is_symlink():
        return []
    hooks = re.sub(r"[-_.]+", "-", _read(config).lower())
    skip = {Path(p).name for p in ignore}
    out = []
    for path in sorted(root.glob("requirements*.txt")):
        if path.name in skip or not path.is_file():
            continue
        raw = list(_requirement_lines(_read(path)))
        lines = _req_lines(_read(path))
        if lines and len(lines) == len(raw) and all(
                re.search(rf"(?<![a-z0-9]){re.escape(norm(req_name(line)))}(?![a-z0-9])", hooks) for line in lines):
            out.append(path)
    return out


def _scope_refused(root: Path, comp: str | None, reqs, skip) -> list[str]:
    """Lines that would install from outside the official index: the component's manifest lines, every line of the
    core requirements files that are still installed, and every line of each file they include with -r/-c,
    followed recursively (cycles stop), even when an included file is on a skip list. An include with a ``..``
    part, or one that resolves outside the project (symlinks included), or that is missing, is itself refused."""
    bad = [f"{comp}/{COMPONENT_MANIFEST}: {line[:120]}" for line in reqs if _refused_line(line)] if comp else []
    root = Path(root).resolve()
    skip = {Path(p).resolve() for p in skip}
    done: set = set()

    def label(path: Path) -> str:
        return path.relative_to(root).as_posix()

    def walk(path: Path) -> None:
        if path in done:
            return
        done.add(path)
        for line in _requirement_lines(_read(path)):
            inc = _INCLUDE.match(line)
            if not inc:
                if _refused_line(line):
                    bad.append(f"{label(path)}: {line[:120]}")
                continue
            target = inc.group(1)
            if ".." in PurePosixPath(target).parts or target.startswith(("/", "~")) or "://" in target:
                bad.append(f"{label(path)}: {line[:120]} (include outside the project)")
                continue
            full = (path.parent / target).resolve()
            if not full.is_relative_to(root) or not full.is_file():
                bad.append(f"{label(path)}: {line[:120]} (include outside the project or missing)")
                continue
            walk(full)

    for path in _requirement_files(root):
        full = path.resolve()
        if full in skip:
            continue
        if not full.is_relative_to(root):
            bad.append(f"{path.name}: resolves outside the project")
            continue
        walk(full)
    return bad


def component_scope(main_checkout, changed) -> dict | None:
    """For a component app: which component the PR touches, its requirements (from MAIN's manifest), and the
    aggregate files never to install. None when the project is not a component app (no aggregate file).

    Any manifest or core line that installs from outside the official index (direct URL, VCS, local path or an
    index option) stops the check with an ``unsupported:`` reason; nothing is installed."""
    root = Path(main_checkout)
    components = component_dirs(root)
    if len(components) < 3:
        return None
    aggregates = aggregate_requirement_files(root, components)
    if not aggregates:
        return None
    names = [p.relative_to(root).as_posix() for p in aggregates]
    lint = lint_only_requirement_files(root, ignore=names)
    comp = component_for_changes(changed, components, ignore=names)
    reqs = list(components.get(comp, [])) if comp else []
    reason = "" if comp else (
        "unsupported: this project keeps per-component requirements and an aggregate requirements file "
        f"({', '.join(names)}), and the pull request's changed files do not belong to exactly one component, "
        "so the aggregate file was not installed")
    if comp:
        bad = _scope_refused(root, comp, reqs, [*aggregates, *lint])
        if bad:
            reason = ("unsupported: these requirement lines install from outside the official package index, "
                      "which product checks do not allow, so nothing was installed: " + "; ".join(bad[:5]))
    return {"component": comp if not reason else None, "touched": comp, "requirements": reqs if not reason else [],
            "aggregates": aggregates, "aggregate_names": names, "lint_only": lint,
            "lint_only_names": [p.relative_to(root).as_posix() for p in lint], "reason": reason}


def _apt_from_tree(root: Path) -> list[str]:
    found = []
    if not root.is_dir():
        return found
    for dirpath, dirnames, filenames in os.walk(root):
        rel = Path(dirpath).relative_to(root)
        dirnames[:] = [name for name in dirnames if name not in SKIP_DIRS and len(rel.parts) < 2]
        for name in filenames:
            if name not in APT_FILES:
                continue
            for line in _read(Path(dirpath) / name).splitlines():
                pkg = line.split("#", 1)[0].strip()
                if safe_apt_name(pkg) and pkg not in found:
                    found.append(pkg)
    return found


def pip_suggestions(text: str) -> list[str]:
    found = []
    pattern = r"(?:^|\n)\s*(?:python\s+-m\s+|uv\s+)?pip3?\s+install\s+([^\n#]+)"
    for match in re.finditer(pattern, text or "", re.I):
        for tok in match.group(1).split():
            if tok.startswith(("-", ".", "/")) or "/" in tok or tok.startswith("git+") or tok.endswith(".txt"):
                continue
            name = req_name(tok)
            if _NAME.fullmatch(name) and norm(name) not in {norm(item) for item in found}:
                found.append(name)
            if len(found) >= MAX_SUGGESTIONS:
                return found
    return found


_PY_CLAUSE = re.compile(r"^(==|!=|~=|>=|<=|>|<)\s*(\d+)\.(\d+)(?:\.\d+)*(?:\.\*)?$")
_PY_CLASSIFIER = re.compile(r"Programming Language\s*::\s*Python\s*::\s*(\d+)\.(\d+)\b", re.I)
_PY_PROBE = [(3, minor) for minor in range(6, 21)]


def _py_clauses(text: str) -> list[tuple[str, tuple[int, int]]]:
    clauses = []
    for part in re.split(r"\s*,\s*", (text or "").strip()):
        match = _PY_CLAUSE.fullmatch(part.strip())
        if match:
            clauses.append((match.group(1), (int(match.group(2)), int(match.group(3)))))
    return clauses


def _py_satisfies(minor: tuple[int, int], clauses: list[tuple[str, tuple[int, int]]]) -> bool:
    for op, bound in clauses:
        if op == ">=" and minor < bound:
            return False
        if op == ">" and minor <= bound:
            return False
        if op == "<=" and minor > bound:
            return False
        if op == "<" and minor >= bound:
            return False
        if op == "==" and minor != bound:
            return False
        if op == "!=" and minor == bound:
            return False
        if op == "~=" and (minor < bound or minor[0] != bound[0]):
            return False
    return True


def _classifier_versions(text: str) -> list[str]:
    found = []
    for match in _PY_CLASSIFIER.finditer(text or ""):
        version = f"{match.group(1)}.{match.group(2)}"
        if version not in found:
            found.append(version)
    return found


def _python_from_checkout(root: Path) -> tuple[list[str], list[str]]:
    """requires-python and classifier versions from pyproject.toml, setup.cfg, and setup.py."""
    specs: list[str] = []
    declared: list[str] = []
    project = _pyproject(root / "pyproject.toml").get("project")
    if isinstance(project, dict):
        if isinstance(project.get("requires-python"), str):
            specs.append(project["requires-python"])
        for item in project.get("classifiers") or []:
            if isinstance(item, str):
                declared.extend(_classifier_versions(item))
    cfg = root / "setup.cfg"
    if cfg.is_file():
        import configparser
        parser = configparser.ConfigParser()
        try:
            parser.read_string(_read(cfg))
        except (configparser.Error, OSError):
            parser = None
        if parser is not None and parser.has_option("options", "python_requires"):
            specs.append(parser.get("options", "python_requires"))
        if parser is not None and parser.has_option("metadata", "classifiers"):
            declared.extend(_classifier_versions(parser.get("metadata", "classifiers")))
    pinned = _read(root / ".python-version").strip().splitlines()
    if pinned and re.fullmatch(r"\d+\.\d+(\.\d+)?", pinned[0].strip()):
        minor = _minor(pinned[0].strip())
        if minor:
            specs.append(f"=={minor[0]}.{minor[1]}.*")
    for name in ("tox.ini", "noxfile.py"):
        declared.extend(_ci_versions(_read(root / name)))
    workflows = root / ".github" / "workflows"
    if workflows.is_dir():
        for wf in sorted(workflows.glob("*.y*ml"))[:20]:
            declared.extend(_ci_versions(_read(wf)))
    setup_py = _read(root / "setup.py")
    for match in re.finditer(r"""python_requires\s*=\s*['\"]([^'\"]+)['\"]""", setup_py):
        specs.append(match.group(1))
    declared.extend(_classifier_versions(setup_py))
    return specs, declared


def _ci_versions(text: str) -> list[str]:
    """Python versions a test or CI config names (python-version: "3.14", py314, python3.14)."""
    found: list[str] = []
    for match in re.finditer(r"(?:python-version\W+|python|\bpy)(3)\.?(1\d|[6-9])\b", text or ""):
        version = f"{match.group(1)}.{match.group(2)}"
        if version not in found:
            found.append(version)
    return found


def _python_from_pypi(info) -> tuple[list[str], list[str]]:
    if not isinstance(info, dict):
        return [], []
    body = info.get("info") if isinstance(info.get("info"), dict) else info
    specs = [body["requires_python"]] if isinstance(body.get("requires_python"), str) else []
    declared: list[str] = []
    for item in body.get("classifiers") or []:
        if isinstance(item, str):
            declared.extend(_classifier_versions(item))
    return specs, declared


def _python_requirement(checkouts, repo: str, self_dist: str, pypi) -> tuple[list[str], list[str]]:
    """Versions the project itself declares. Lookup text is not a source."""
    specs: list[str] = []
    declared: list[str] = []
    dist = (self_dist or "").strip()
    for checkout in checkouts or []:
        root = Path(checkout)
        file_specs, file_declared = _python_from_checkout(root)
        specs.extend(file_specs)
        declared.extend(file_declared)
        if not dist:
            project = _pyproject(root / "pyproject.toml").get("project")
            if isinstance(project, dict) and isinstance(project.get("name"), str):
                dist = project["name"].strip()
    parts = split_repo(repo or "")
    owner, repo_name = parts if parts else ("", "")
    if dist and pypi and owner and repo_name:
        try:
            info = pypi(dist)
        except Exception:  # noqa: BLE001 — a metadata miss leaves the project files in charge
            info = None
        if pypi_links_back(info, owner, repo_name):
            page_specs, page_declared = _python_from_pypi(info)
            specs.extend(page_specs)
            declared.extend(page_declared)
    return specs, declared


def choose_python(specs: list[str], declared: list[str], current: str, python_available) -> str | None:
    """A version that satisfies requires-python and, when one is installed, is available.

    The current interpreter wins when it already satisfies the requirement. Otherwise the
    lowest declared or in-range version that is installed is used. Nothing is taken from
    a web page.
    """
    clauses: list[tuple[str, tuple[int, int]]] = []
    for text in specs:
        clauses.extend(_py_clauses(text))
    declared_versions = []
    for item in declared:
        minor = _minor(item)
        if minor and _py_satisfies(minor, clauses):
            version = f"{minor[0]}.{minor[1]}"
            if version not in declared_versions:
                declared_versions.append(version)
    if not clauses and not declared_versions:
        return None
    current_minor = _minor(current)
    current_version = f"{current_minor[0]}.{current_minor[1]}" if current_minor else ""
    current_ok = bool(current_minor) and _py_satisfies(current_minor, clauses)
    if current_ok and clauses:
        return current_version
    if current_ok and declared_versions:
        oldest = min(declared_versions, key=lambda item: _minor(item) or (0, 0))
        if current_version in declared_versions or current_minor >= (_minor(oldest) or (0, 0)):
            return current_version
    if declared_versions:
        candidates = declared_versions
    else:
        candidates = [f"{major}.{minor}" for major, minor in _PY_PROBE if _py_satisfies((major, minor), clauses)]
    candidates = sorted(set(candidates), key=lambda item: _minor(item) or (0, 0))
    if not candidates:
        return None
    for version in candidates:
        if python_available and python_available(version):
            return version
    return candidates[0]


def _minor(version: str) -> tuple[int, int] | None:
    match = _PY_VER.search(version or "")
    if not match:
        return None
    return int(match.group(1)), int(match.group(2))


def find_python(version: str, which=None):
    if not re.fullmatch(r"\d+\.\d+", version or ""):
        return None
    which = which or shutil.which
    return which(f"python{version}")


def _tavily_text(tavily) -> str:
    if not tavily:
        return ""
    if isinstance(tavily, str):
        return tavily
    if not isinstance(tavily, dict):
        return ""
    parts = [str(tavily.get("text") or ""), str(tavily.get("answer") or "")]
    for item in tavily.get("results") or []:
        if isinstance(item, dict):
            parts.append(str(item.get("content") or ""))
    return "\n".join(part for part in parts if part)


def fetch_pypi(name: str, timeout: float = PYPI_TIMEOUT):
    """Public PyPI JSON. None when the index cannot be read. No key is sent."""
    if not _NAME.fullmatch(name or ""):
        return None
    url = "https://pypi.org/pypi/" + urllib.parse.quote(name) + "/json"
    req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "proof-of-change"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            data = json.loads(resp.read().decode())
    except Exception:  # noqa: BLE001 — a miss, a 404, or no network all mean "do not install"
        return None
    info = data.get("info") if isinstance(data, dict) else None
    return info if isinstance(info, dict) else None


def github_repo_url(value: str, owner: str, repo: str) -> bool:
    """True when an http or https URL's host is github.com and its first two path segments are owner/repo.

    www.github.com is the same host. The match ignores case and one trailing .git.
    A lookalike host, a path that only contains the repository text, or any other scheme is not a match.
    """
    if not isinstance(value, str) or not owner or not repo:
        return False
    try:
        parsed = urllib.parse.urlsplit(value.strip())
    except ValueError:
        return False
    if (parsed.scheme or "").lower() not in {"http", "https"}:
        return False
    host = (parsed.hostname or "").lower()
    if host not in {"github.com", "www.github.com"}:
        return False
    parts = [urllib.parse.unquote(part) for part in (parsed.path or "").split("/") if part]
    if len(parts) < 2:
        return False
    got_owner, got_repo = parts[0], parts[1]
    if got_repo.lower().endswith(".git"):
        got_repo = got_repo[:-4]
    return got_owner.lower() == owner.lower() and got_repo.lower() == repo.lower()


def pypi_links_back(info, owner: str, repo: str) -> bool:
    """True when this project's PyPI page links to that GitHub repository. info may be the info object or the full JSON."""
    if not isinstance(info, dict) or not owner or not repo:
        return False
    body = info.get("info") if isinstance(info.get("info"), dict) else info
    values = []
    home = body.get("home_page")
    if isinstance(home, str):
        values.append(home)
    urls = body.get("project_urls")
    if isinstance(urls, dict):
        values.extend(value for value in urls.values() if isinstance(value, str))
    return any(github_repo_url(value, owner, repo) for value in values)


def _sandbox_can_see(path: str) -> bool:
    """True when the local sandbox mounts this interpreter (/usr is mounted read-only; home folders are not)."""
    try:
        from guardrails import sandbox
        if not sandbox.enabled():
            return True
    except Exception:  # noqa: BLE001
        pass
    real = os.path.realpath(str(path))
    return real.startswith("/usr/") or not os.path.isabs(str(path))


def retry_python(version: str, *, find=None, provision=None, can_see=None) -> str | None:
    """Interpreter for the wrong-Python install retry: one the local sandbox can see, or one we provisioned.

    A python{version} on PATH outside the sandbox mounts (a home folder, a venv link) is skipped, because the
    sandboxed `uv venv -p` would fail with "No interpreter found"."""
    find = find or find_python
    provision = provision or provision_python
    can_see = can_see or _sandbox_can_see
    path = find(version)
    if path and can_see(path):
        return path
    return provision(version)


PYTHON_RULE = ("one Python version is used on both sides: the lowest version that meets the requirements of both "
               "main and the pull request; if none meets both, the check stops as a setup problem and records both")


def _python_decision(requested: str | None, current: str, sandbox: str, python_available, requirement: str = "",
                     provision=None, auto_python: bool = True) -> dict:
    if not requested:
        return {"requested": None, "current": current, "applied": False, "switch": None,
                "reason": "no Python version was requested"}
    current_minor = _minor(current)
    wanted = _minor(requested)
    if current_minor and wanted and current_minor == wanted:
        met = requirement or requested
        return {"requested": requested, "current": current, "applied": True, "switch": None,
                "reason": f"Python {current} already meets {met}"}
    if sandbox == "contree" and not auto_python:
        return {"requested": requested, "current": current, "applied": False, "switch": None,
                "reason": "not applied: the Contree image keeps its Python"}
    if sandbox == "contree":
        return {"requested": requested, "current": current, "applied": True, "switch": None,
                "provision": requested, "auto_fix": True,
                "reason": (f"auto-fix: the project needs Python {requested} and the sandbox image has "
                           f"{current or 'another version'}, so Python {requested} is installed in the sandbox "
                           "during setup, the same on main and pr")}
    path = python_available(requested) if python_available else None
    if path and auto_python and not _sandbox_can_see(path):
        path = None   # an interpreter outside /usr is not mounted in the sandbox; use a managed one instead
    if path:
        return {"requested": requested, "current": current, "applied": True, "switch": path,
                "reason": f"switched the local sandbox to {path}"}
    got = provision(requested) if provision else None
    if got:
        return {"requested": requested, "current": current, "applied": True, "switch": got,
                "provision": requested, "auto_fix": True,
                "reason": (f"auto-fix: Python {requested} was missing, so it was downloaded and installed "
                           "for this check, the same on main and pr")}
    return {"requested": requested, "current": current, "applied": False, "switch": None,
            "reason": f"not applied: python{requested} is not available to the local sandbox"}


# Generic signs that a failure needs an OS package (a missing header, shared library, tool or executable).
# These name no package and no project; the package names always come from the project's own files or pages.
_SYSTEM_FAILURE = re.compile(
    r"(cannot open shared object file|error while loading shared libraries|library not loaded|"
    r"fatal error: [^\s:]+\.h|executable not found|command not found|: not found|"
    r"no such file or directory: '[^'/]+'|unable to execute|c compiler cannot create executables|"
    r"could not find [^\n]*(?:library|headers?)|package [^\n]* was not found in the pkg-config|"
    r"cannot find -l\S+|ld: library not found|error: command '[^']+' failed: no such file or directory|"
    r"\b(?:cc|gcc|g\+\+|clang|make|cmake|gfortran|rustc|cargo)\b[^\n]{0,40}(?:not found|no such file))", re.I)
_APT_INSTALL = re.compile(r"\bapt(?:-get)?\s+(?:-\S+\s+)*install\s+((?:(?:-\S+|[A-Za-z0-9][A-Za-z0-9.+:-]*)[ \t]*)+)")
INSTALL_DOC_NAMES = ("readme", "contributing", "install", "installation", "building", "development",
                     "dockerfile", "pyproject.toml", "setup.cfg", "setup.py", "tox.ini", "environment.yml",
                     "environment.yaml", "noxfile.py", "makefile") + tuple(APT_FILES)
_DOC_MAX = 400_000


def is_install_doc_path(path) -> bool:
    """True for a path the setup lookup reads as an install doc: top-level README, CONTRIBUTING, install pages,
    Dockerfile and packaging files, the same names under docs/, doc/ or ci/, and CI workflow files."""
    parts = [seg for seg in str(path or "").replace("\\", "/").split("/") if seg]
    if not parts:
        return False
    low = parts[-1].lower()
    if len(parts) == 3 and tuple(parts[:2]) == (".github", "workflows"):
        return low.endswith((".yml", ".yaml"))
    if len(parts) > 2 or (len(parts) == 2 and parts[0] not in ("docs", "doc", "ci", ".github")):
        return False
    return any(low == n or low.startswith(n + ".") or low.startswith(n + "-") for n in INSTALL_DOC_NAMES)


def project_install_docs(checkouts) -> dict:
    """Read the project's own install docs from this run's checkout: README, CONTRIBUTING, install pages,
    CI workflows, Dockerfile and packaging files. Returns the text and the files it came from."""
    parts, sources, size = [], [], 0
    for checkout in checkouts or []:
        root = Path(checkout)
        if not root.is_dir():
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            rel = Path(dirpath).relative_to(root)
            in_ci = rel.parts[:2] == (".github", "workflows")
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and (len(rel.parts) < 2 or in_ci)
                           and (d in (".github", "workflows", "docs", "doc", "ci") or len(rel.parts) == 0)]
            for name in filenames:
                low = name.lower()
                wanted = in_ci and low.endswith((".yml", ".yaml"))
                wanted = wanted or any(low == n or low.startswith(n + ".") or low.startswith(n + "-")
                                       for n in INSTALL_DOC_NAMES)
                if not wanted:
                    continue
                path = Path(dirpath) / name
                label = str(path.relative_to(root))
                if label in sources:
                    continue
                text = _read(path)[:50_000]
                if size + len(text) > _DOC_MAX:
                    break
                size += len(text)
                parts.append(text)
                sources.append(label)
    return {"text": "\n".join(parts), "sources": sources}


def os_packages_in(text: str) -> list[str]:
    """Package names from apt install lines in a text. Only names are taken; the command is never run."""
    found: list[str] = []
    for match in _APT_INSTALL.finditer(text or ""):
        for word in match.group(1).split():
            word = word.strip().strip("\\").split("=", 1)[0].lower()
            if word.startswith("-") or word in ("install", "sudo") or not safe_apt_name(word):
                continue
            if word not in found:
                found.append(word)
    return found


def is_system_failure(text: str) -> bool:
    return bool(_SYSTEM_FAILURE.search(text or ""))


def missing_system_pieces(text: str) -> list[str]:
    """The library, header or tool an error says is missing.

    Each name is taken from the error text. Nothing here is a distribution package, and nothing is chosen from a list.
    """
    found: list[str] = []

    def add(name: str) -> None:
        name = (name or "").strip().strip("'\"`,.;")
        if not name or len(name) > 80 or name.lower() in {"error", "fatal", "command", "the"}:
            return
        if "/" in name:
            name = name.rsplit("/", 1)[-1]
        if name and name not in found:
            found.append(name)

    blob = text or ""
    for match in re.finditer(r"lib[\w.+-]+\.so(?:\.\d+)*", blob):
        add(match.group(0))
    for match in re.finditer(r"(?i)fatal error:\s*([^\s:]+\.h)\b", blob):
        add(match.group(1))
    for match in re.finditer(r"(?i)cannot find -l([A-Za-z0-9_+.-]+)", blob):
        add("-l" + match.group(1))
    for match in re.finditer(r"(?i)package\s+([A-Za-z0-9_+.-]+)\s+was not found", blob):
        add(match.group(1))
    for match in re.finditer(r"(?i)([A-Za-z0-9_+./-]{1,60})\s+executable not found", blob):
        add(match.group(1))
    for match in re.finditer(r"(?i)command not found:\s*([A-Za-z0-9_+./-]+)", blob):
        add(match.group(1))
    for match in re.finditer(r"(?i)(?:^|[\s'\"])([A-Za-z0-9_+.-]{1,40}):\s*(?:command )?not found\b", blob):
        add(match.group(1))
    for match in re.finditer(r"(?i)command\s+'([^']+)'\s+failed", blob):
        add(match.group(1))
    return found[:8]


def failure_line(text: str) -> str:
    """The line the per-run lookup diagnoses.

    A missing OS library, header or tool still wins, because that is what the system-package step reads.
    Otherwise a pytest or collection error is used, so a generic first line does not hide it.
    """
    lines = [line.strip() for line in (text or "").splitlines() if line.strip()]
    for line in lines:
        if _SYSTEM_FAILURE.search(line):
            return line[:300]
    for line in lines:
        if _PYTEST_ERROR.search(line):
            return line[:300]
    return lines[0][:300] if lines else ""


def trusted_url(url: str, repo: str, declared_urls=()) -> bool:
    """Rule (a): install steps come only from the project's own GitHub repository (not its whole organisation),
    its GitHub Pages site for that repository, or a homepage or docs site the project itself declares.
    Every other site is ignored."""
    try:
        parsed = urllib.parse.urlparse(str(url or ""))
    except ValueError:
        return False
    host = (parsed.hostname or "").lower()
    if parsed.scheme not in ("https", "http") or not host:
        return False
    parts = split_repo(repo or "")
    owner, name = (parts[0].lower(), parts[1].lower()) if parts else ("", "")
    segs = [seg.lower() for seg in parsed.path.split("/") if seg]
    if owner and name and host in ("github.com", "raw.githubusercontent.com"):
        return len(segs) >= 2 and segs[0] == owner and segs[1] in (name, name + ".git")
    if owner and name and host == f"{owner}.github.io":
        return name == host or (bool(segs) and segs[0] == name)
    for declared in declared_urls or ():
        try:
            dparsed = urllib.parse.urlparse(str(declared))
        except ValueError:
            continue
        dhost = (dparsed.hostname or "").lower()
        if not dhost or dhost in ("pypi.org", "raw.githubusercontent.com"):
            continue
        if dhost == "github.com" or dhost.endswith(".github.io"):
            continue   # GitHub links are covered by the repository rule above, never widened to the organisation
        if dhost in _SHARED_DOC_HOSTS:
            dsegs = [seg.lower() for seg in dparsed.path.split("/") if seg]
            if host == dhost and dsegs and segs[:1] == dsegs[:1]:
                return True
            continue
        if host == dhost or host.endswith("." + dhost):
            return True
    return False


# Hosts shared by many projects: a declared link there trusts only that project's own path, never the whole host.
_SHARED_DOC_HOSTS = ("readthedocs.org", "gitlab.com", "bitbucket.org", "sourceforge.net")


def declared_urls(checkout) -> list[str]:
    """Homepage and docs links the project itself declares in its packaging files (main's checkout)."""
    found: list[str] = []
    root = Path(checkout) if checkout else None
    if root is None or not root.is_dir():
        return found
    data = _pyproject(root / "pyproject.toml")
    project = data.get("project") if isinstance(data.get("project"), dict) else {}
    urls = project.get("urls") if isinstance(project.get("urls"), dict) else {}
    found.extend(str(v) for v in urls.values() if isinstance(v, str))
    poetry = ((data.get("tool") or {}).get("poetry") or {}) if isinstance(data.get("tool"), dict) else {}
    for key in ("homepage", "documentation", "repository"):
        if isinstance(poetry.get(key), str):
            found.append(poetry[key])
    cfg = root / "setup.cfg"
    if cfg.is_file():
        import configparser
        parser = configparser.ConfigParser()
        try:
            parser.read_string(_read(cfg))
            if parser.has_option("metadata", "url"):
                found.append(parser.get("metadata", "url").strip())
            if parser.has_option("metadata", "project_urls"):
                for line in parser.get("metadata", "project_urls").splitlines():
                    if "=" in line:
                        found.append(line.split("=", 1)[1].strip())
        except (configparser.Error, OSError):
            pass
    return [u for u in dict.fromkeys(found) if u.startswith(("https://", "http://"))]


def pypi_declared_urls(info) -> list[str]:
    """Docs and homepage links on the project's own PyPI page (only used once that page links back)."""
    data = (info or {}).get("info") if isinstance(info, dict) else None
    if not isinstance(data, dict):
        return []
    urls = [data.get("home_page"), data.get("docs_url"), *((data.get("project_urls") or {}).values())]
    return [str(u) for u in urls if isinstance(u, str) and u.startswith(("https://", "http://"))]


def declared_names(checkout) -> set[str]:
    """Every Python package the project declares: runtime deps, every extra, dependency groups and requirement files.
    Names are normalised. Read from main's checkout only."""
    root = Path(checkout) if checkout else None
    names: set[str] = set()
    if root is None or not root.is_dir():
        return names

    def add(req):
        if isinstance(req, str):
            name = req_name(req)
            if _NAME.fullmatch(name or ""):
                names.add(norm(name))

    for item in declared_packages(root):
        add(item.get("requirement") or item.get("name"))
    data = _pyproject(root / "pyproject.toml")
    project = data.get("project") if isinstance(data.get("project"), dict) else {}
    for bucket in (project.get("optional-dependencies"), data.get("dependency-groups")):
        if isinstance(bucket, dict):
            for reqs in bucket.values():
                for req in reqs if isinstance(reqs, list) else []:
                    add(req)
    cfg = root / "setup.cfg"
    if cfg.is_file():
        import configparser
        parser = configparser.ConfigParser()
        try:
            parser.read_string(_read(cfg))
            if parser.has_section("options.extras_require"):
                for _extra, value in parser.items("options.extras_require"):
                    for req in _req_lines(value):
                        add(req)
        except (configparser.Error, OSError):
            pass
    setup_py = _read(root / "setup.py")
    for req in re.findall(r"""['\"]([^'\"]+)['\"]""", _section(setup_py, "extras_require")):
        add(req)
    return names


def install_docs_changed(main_checkout, pr_checkout) -> list[str]:
    """Install-doc files (the ones the setup lookup reads) whose content differs between main and the PR."""
    if not main_checkout or not pr_checkout:
        return []
    main_root, pr_root = Path(main_checkout), Path(pr_checkout)
    if not main_root.is_dir() or not pr_root.is_dir():
        return []
    labels = list(dict.fromkeys(project_install_docs([main_root])["sources"]
                                + project_install_docs([pr_root])["sources"]))
    changed = []
    for label in labels:
        a, b = main_root / label, pr_root / label
        if a.is_file() != b.is_file() or (a.is_file() and _read(a) != _read(b)):
            changed.append(label)
    return changed


def trusted_lookup(payload, repo: str, declared_urls=()) -> dict:
    """Keep only results from trusted pages; drop the free-text answer, which has no source page."""
    if not isinstance(payload, dict):
        return {"results": [], "sources": []}
    kept = [item for item in payload.get("results") or []
            if isinstance(item, dict) and trusted_url(item.get("url"), repo, declared_urls)]
    return {"results": kept, "answer": None, "sources": [item.get("url") for item in kept]}


def apt_available(name: str, run=None) -> bool:
    """Rule (b): an OS package must exist in the distro archive (apt-cache policy shows a candidate)."""
    import subprocess
    if not safe_apt_name(name):
        return False
    run = run or (lambda cmd: subprocess.run(cmd, capture_output=True, text=True, timeout=30))
    try:
        out = run(["apt-cache", "policy", name])
    except Exception:  # noqa: BLE001 — no apt means the package cannot be confirmed
        return False
    text = getattr(out, "stdout", "") or ""
    m = re.search(r"Candidate:\s*(\S+)", text)
    return bool(m and m.group(1) != "(none)")


def system_fix_for(error_text: str, lookup_text: str = "", project_text: str = "", apt_check=None,
                   lookup_sources=()) -> dict:
    """OS packages for a failure that needs one, proposed by this run's own sources.

    Candidates come from the project's install docs (``project_text``) and from trusted lookup pages
    (``lookup_text``). A name is kept only when it exists in the distro archive. Nothing is mapped by hand.
    """
    if not is_system_failure(error_text):
        return {"install": [], "refused": [], "sources": []}
    apt_check = apt_check or apt_available
    install, refused, sources = [], [], []
    for text, source in ((project_text, "project install docs"), (lookup_text, "trusted lookup pages")):
        for name in os_packages_in(text):
            if name in install or any(r["name"] == name for r in refused):
                continue
            if apt_check(name):
                install.append(name)
                if source not in sources:
                    sources.append(source)
            else:
                refused.append({"name": name, "reason": "not found in the distro archive"})
    return {"install": install, "refused": refused,
            "sources": sources + [u for u in lookup_sources or () if u not in sources]}


def note_limitation(rec: dict, needed: list[str], error: str, why: str) -> dict:
    """Record what this sandbox could not do, in plain words, with the packages and the real error."""
    block = rec.setdefault("demo_helper", {})
    item = {"kind": "OS packages", "needed": list(needed), "error": (error or "")[:300], "why": why,
            "plain": (f"This check needs the system package(s) {', '.join(needed)}, but {why}. "
                      f"The error was: {(error or '').strip()[:200]}")}
    lims = block.setdefault("limitations", [])
    if item not in lims:
        lims.append(item)
    return item


def _system_decision(names: list[str], sandbox: str, apply_system: bool = True) -> list[dict]:
    """Whether each system package is installed in the sandbox.

    A product check passes ``apply_system=False``. Those packages stay unapplied on every sandbox, including
    Contree, so the shell never runs an OS install. A study plan keeps the earlier behaviour: Contree applies a
    safe name, and the local sandbox does not.
    """
    out = []
    for name in names:
        if not safe_apt_name(name):
            out.append({"name": name, "applied": False, "sides": ["main", "pr"],
                        "reason": "not applied: the name is not a safe system package name"})
        elif apply_system and sandbox == "contree":
            out.append({"name": name, "applied": True, "sides": ["main", "pr"],
                        "reason": "applied in the Contree sandbox"})
        elif not apply_system:
            out.append({"name": name, "applied": False, "sides": ["main", "pr"],
                        "reason": "not applied: this check does not install system packages"})
        else:
            out.append({"name": name, "applied": False, "sides": ["main", "pr"],
                        "reason": "not applied: the local sandbox cannot install system packages"})
    return out


def build_setup_plan(repo: str, checkouts, tavily, current_python: str, sandbox: str, self_dist: str = "",
                     python_available=None, pypi=None, allow_lookup_packages: bool = True,
                     provision=None, auto_python: bool = True, docs_checkouts=None,
                     apply_system: bool = True, changed_files=None) -> dict:
    """One plan for both sides. Only project-listed packages and link-back suggestions are added.

    ``docs_checkouts`` (a product check passes main's checkout only) is where listed packages and system-package
    files are read from, so a PR cannot add a package that then lands on main too. None reads every checkout."""
    docs_from = list(checkouts or []) if docs_checkouts is None else list(docs_checkouts)
    # changed_files (product checks only, with docs_checkouts): for a component app, install the core requirements
    # plus the one touched component's manifest requirements, read from main, and never the aggregate file.
    scope = None
    if changed_files is not None and docs_checkouts is not None and docs_from:
        scope = component_scope(docs_from[0], changed_files)
    skip_files = [*scope["aggregates"], *scope["lint_only"]] if scope else ()
    if python_available is not None and provision is None:
        provision = False   # an injected interpreter lookup (tests) never downloads anything
    python_available = find_python if python_available is None else python_available
    pypi = fetch_pypi if pypi is None else pypi
    packages: list[dict] = []
    seen: set = set()
    for checkout in docs_from:
        for item in declared_packages(checkout, self_dist, skip_files=skip_files):
            key = norm(item["name"])
            if key in seen:
                continue
            seen.add(key)
            packages.append(item)
    text = _tavily_text(tavily)
    refused = []
    groups_blocked = ""
    if docs_checkouts is not None:
        # Product check: every dependency group in main's files, through the deps-only refusal rules.
        for checkout in docs_from:
            group_lines, group_refused, group_problems = dependency_group_reqs(checkout, self_dist)
            refused += group_refused
            if group_refused or group_problems:
                # fail closed: nothing from the groups is installed and the check stops as could not verify
                groups_blocked = dependency_groups_reason(group_refused, group_problems)
                continue
            for req in group_lines:
                _add_pkg(packages, seen, req, kind="dependency-group", action="install", source="pyproject",
                         reason="listed in a dependency group", self_dist=self_dist)
    scope_blocked = ""
    if scope:
        if scope["component"]:
            for req in scope["requirements"]:
                _add_pkg(packages, seen, req, kind="component", action="install", source=COMPONENT_MANIFEST,
                         reason=f"listed in the manifest of {scope['component']}, the component this PR changes",
                         self_dist=self_dist)
        else:
            scope_blocked = scope["reason"]
    parts = split_repo(repo or "")
    owner, repo_name = parts if parts else ("", "")
    suggestions = pip_suggestions(text) if allow_lookup_packages else []
    for name in suggestions:
        if norm(name) in seen or (self_dist and norm(name) == norm(self_dist)):
            continue
        try:
            info = pypi(name) if pypi else None
        except Exception:  # noqa: BLE001 — a lookup error is a refusal, not an install
            info = None
        if pypi_links_back(info, owner, repo_name):
            seen.add(norm(name))
            packages.append({"requirement": name, "name": name, "kind": "tavily", "action": "install",
                             "source": "tavily", "reason": "PyPI page links to this GitHub repository",
                             "sides": ["main", "pr"]})
        elif info is None:
            refused.append({"name": name, "reason": "no network or the package was not found"})
        else:
            refused.append({"name": name, "reason": "its PyPI page does not link to this GitHub repository"})
    spec_texts, declared_versions = _python_requirement(checkouts, repo, self_dist, pypi)
    requested = choose_python(spec_texts, declared_versions, current_python or "", python_available)
    conflict = None
    if auto_python and requested is None and spec_texts and len(list(checkouts or [])) > 1:
        sides = {}
        for side, checkout in zip(SIDES, list(checkouts)[:2]):
            side_specs, side_declared = _python_requirement([checkout], repo, self_dist, None)
            sides[side] = {"requirement": ", ".join(side_specs) or "none",
                           "version": choose_python(side_specs, side_declared, current_python or "", None)}
        conflict = sides
    requirement = ", ".join(dict.fromkeys(item.strip() for item in spec_texts if item and item.strip()))
    system_names = []
    for checkout in docs_from:
        for name in _apt_from_tree(Path(checkout)):
            if name not in system_names:
                system_names.append(name)
    python = _python_decision(requested, current_python or "", sandbox or "local", python_available, requirement,
                              provision=(provision_python if provision is None else (provision or None))
                              if auto_python else None, auto_python=auto_python)
    if auto_python and requested:
        python["rule"] = PYTHON_RULE
        python["gate_failed"] = not python.get("applied")
    if conflict:
        python = {"requested": None, "current": current_python or "", "applied": False, "switch": None,
                  "rule": PYTHON_RULE, "gate_failed": True, "versions": conflict,
                  "reason": (f"setup problem: main needs Python {conflict['main']['requirement']} "
                             f"(would use {conflict['main']['version'] or 'none'}) and the pull request needs "
                             f"{conflict['pr']['requirement']} (would use {conflict['pr']['version'] or 'none'}); "
                             "no single version meets both, so nothing was tested")}
    system = _system_decision(system_names, sandbox or "local", apply_system=apply_system)
    extra = [item["requirement"] for item in packages if item["action"] == "install"]
    lines = ["Setup plan: the same packages on main and pr."]
    for item in packages:
        if item["action"] == "install":
            lines.append(f"Setup plan: install {item['requirement']} ({item['reason']}) on main and pr.")
        else:
            lines.append(f"Setup plan: {item['name']} is noted, installed with the project.")
    if requested:
        lines.append(f"Setup plan: Python {requested}: {python['reason']}")
    if conflict:
        lines.append(f"Setup plan: Python: {python['reason']}")
    if python.get("auto_fix"):
        lines.append(f"Auto-fix: Python {requested} is set up automatically for this check (no flag needed).")
    if python.get("rule"):
        lines.append(f"Setup plan: Python rule: {python['rule']}.")
    for item in system:
        lines.append(f"Setup plan: system package {item['name']}: {item['reason']}")
    for item in refused:
        lines.append(f"Setup plan: refused {item['name']}: {item['reason']}")
    if groups_blocked:
        lines.append(f"Setup plan: stopped: {groups_blocked}")
    if scope:
        lines.append("Setup plan: not installing the aggregate requirements file(s) "
                     + ", ".join(scope["aggregate_names"]) + (f"; only the core requirements and {scope['component']}'s "
                                                             "own requirements, read from main" if scope["component"] else ""))
    if scope and scope["lint_only_names"]:
        lines.append("Setup plan: not installing lint-only requirements file(s) " + ", ".join(scope["lint_only_names"]))
    if scope_blocked:
        lines.append(f"Setup plan: stopped: {scope_blocked}")
    return {"packages": packages, "scope_blocked": scope_blocked,
            "component": (scope or {}).get("component"),
            "aggregate_names": list((scope or {}).get("aggregate_names") or []), "extra_reqs": extra, "python": python, "system": system,
            "refused": refused, "groups_blocked": groups_blocked, "lines": lines}


def attach_plan(rec: dict, plan: dict) -> None:
    block = rec.setdefault("demo_helper", {})
    block["setup_plan"] = {key: value for key, value in plan.items() if key != "lines"}
    block["notes"] = _unique([*(block.get("notes") or []), *plan.get("lines", [])])


def write_run_files(plan: dict, out_dir) -> dict:
    """Write this run's requirements.txt and setup-plan.json. Nothing in them is written per repository by hand:
    every line comes from the project's own files or from a link-back lookup suggestion in ``plan``."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    reqs = [str(req).strip() for req in plan.get("extra_reqs") or [] if str(req).strip()]
    head = ["# Written for this run by the setup lookup. Installed together on main and pr."]
    for item in plan.get("packages") or []:
        if item.get("action") == "install":
            head.append(f"# {item['requirement']}: {item.get('reason') or 'setup plan'}")
    req_path = out / "requirements.txt"
    req_path.write_text("\n".join(head + reqs) + "\n", encoding="utf-8")
    plan_path = out / "setup-plan.json"
    plan_path.write_text(json.dumps(redact_obj({k: v for k, v in plan.items()}), indent=2, default=str),
                         encoding="utf-8")
    return {"requirements": str(req_path.name), "plan": str(plan_path.name), "count": len(reqs)}


def plan_steps(plan: dict) -> dict[str, str]:
    """Plain-words lines for the three setup steps in the console flowchart."""
    packages = [item for item in plan.get("packages") or [] if item.get("action") == "install"]
    noted = [item for item in plan.get("packages") or [] if item.get("action") != "install"]
    found = len(plan.get("packages") or [])
    lookup = f"Found {found} setup item(s) in the project's files and the web lookup."
    if plan.get("refused"):
        lookup += " Refused: " + ", ".join(f"{r['name']} ({r['reason']})" for r in plan["refused"][:5]) + "."
    py = plan.get("python") or {}
    if py.get("switch"):
        python = f"Using Python {py['switch']}: {py.get('reason') or 'the project asks for it'}."
    elif py.get("requested"):
        python = f"Python {py['requested']}: {py.get('reason') or ''}".strip()
    else:
        python = "Kept the default Python; the project does not ask for another one."
    if packages:
        deps = "Wrote requirements.txt and installed it on main and pr: " + ", ".join(
            item["requirement"] for item in packages[:12]) + "."
    else:
        deps = "Nothing extra to install; the project's own install covers it."
    if noted:
        deps += f" {len(noted)} more come with the project install."
    return {"setup_lookup": lookup, "setup_python": python, "install_deps": deps}


def contree_shell(plan: dict | None) -> str:
    """Extra shell for both Contree checkpoints. Empty when the plan adds nothing the sandbox may apply."""
    if not plan:
        return ""
    lines = []
    wanted = (plan.get("python") or {}).get("provision")
    if wanted and re.fullmatch(r"\d+\.\d+", str(wanted)) and (plan.get("python") or {}).get("switch") is None:
        lines.append(contree_python_shell(str(wanted)))
    # Only an applied package is installed. A product check leaves every system package unapplied, so this
    # writes no apt-get line on Contree either.
    apt = [item["name"] for item in plan.get("system") or [] if item.get("applied") and safe_apt_name(item["name"])]
    if apt:
        quoted = " ".join(shlex_quote(name) for name in apt)
        lines.append(f"export DEBIAN_FRONTEND=noninteractive\napt-get update -qq && apt-get install -y -qq {quoted} >/dev/null")
    reqs = [req for req in (plan.get("extra_reqs") or []) if str(req).strip()]
    if reqs:
        lines.append("python -m pip install -q " + " ".join(shlex_quote(req) for req in reqs))
    return "\n".join(lines)


# uv verifies each managed CPython download against the SHA-256 in its own built-in manifest.
UV_PIN = "uv==0.13.1"
_MIRROR_VARS = ("UV_PYTHON_INSTALL_MIRROR", "UV_PYTHON_DOWNLOADS_JSON_URL", "UV_PYPY_INSTALL_MIRROR")


def contree_python_shell(version: str) -> str:
    """Setup shell (network on, before tests) that makes `python` the wanted version in a Contree checkpoint.

    uv downloads a standalone CPython into /opt/poc-python. A small wrapper puts it first on PATH as
    `python`, so every later step (pip installs, pytest, probes) uses it. The PR checkpoint is forked
    from main, so both sides use the same interpreter. No-op when `python` already is that version.
    """
    if not re.fullmatch(r"\d+\.\d+", version or ""):
        raise ValueError(f"not a Python version: {version!r}")
    major, minor = version.split(".")
    return (
        f"if ! python -c 'import sys; sys.exit(0 if sys.version_info[:2] == ({major}, {minor}) else 1)'; then\n"
        f"  echo 'Auto-fix: installing Python {version} for this check (the project needs it)'\n"
        "  unset UV_PYTHON_INSTALL_MIRROR UV_PYTHON_DOWNLOADS_JSON_URL UV_PYPY_INSTALL_MIRROR\n"
        f"  python -m pip install -q {UV_PIN}\n"
        f"  UV_PYTHON_INSTALL_DIR=/opt/poc-python/install python -m uv python install -q {version}\n"
        f"  UV_PYTHON_INSTALL_DIR=/opt/poc-python/install python -m uv venv -q --seed -p {version} /opt/poc-python/venv\n"
        "  printf '#!/bin/sh\\nexec /opt/poc-python/venv/bin/python \"$@\"\\n' > /usr/local/bin/python\n"
        "  chmod 0755 /usr/local/bin/python\n"
        "  hash -r\n"
        f"  python -c 'import sys; assert sys.version_info[:2] == ({major}, {minor}), sys.version'\n"
        "fi"
    )


def provision_python(version: str, *, which=None, runner=None, install_dir: str | None = None) -> str | None:
    """Install a uv-managed CPython for the local sandbox. Runs in the orchestrator before any project code.

    Returns the version string for `uv venv -p` (the managed install directory is mounted read-only in
    the sandbox), or None when it cannot be installed. Only the interpreter is downloaded; project
    packages still come from the project's own files.
    """
    if not re.fullmatch(r"\d+\.\d+", version or ""):
        return None
    which = which or shutil.which
    uv = which("uv")
    if not uv:
        return None
    if runner is None:
        import subprocess

        def runner(argv, env):
            try:
                return subprocess.run(argv, env=env, capture_output=True, text=True, timeout=900).returncode
            except (OSError, subprocess.SubprocessError):
                return 1
    env = dict(os.environ)
    if install_dir is None:
        try:
            from guardrails.sandbox import python_install_dir
            install_dir = python_install_dir()
        except Exception:  # noqa: BLE001
            install_dir = None
    if install_dir:
        env["UV_PYTHON_INSTALL_DIR"] = install_dir
    for key in _MIRROR_VARS:   # only uv's own managed builds, never a mirror or a list a caller supplies
        env.pop(key, None)
    for key in list(env):   # no keys reach the download
        if any(word in key.upper() for word in ("TOKEN", "KEY", "SECRET", "PASSWORD")):
            env.pop(key)
    if runner([uv, "python", "install", "-q", version], env) != 0:
        return None
    return version


_NOT_A_PACKAGE = re.compile(
    r"multiple top-level packages discovered in a flat-layout|failed to build `|does not appear to be a python project|"
    r"neither 'setup\.py' nor 'pyproject\.toml' found|no `project` table found|package-mode = false", re.I)


def not_a_package(log_text: str) -> bool:
    """True when an install failed because the project itself cannot be built as a package."""
    return bool(_NOT_A_PACKAGE.search(log_text or ""))


def deps_only_plan(checkout, exclude=()) -> dict | None:
    """How to install only what the project declares, without building the project itself.

    uv.lock (with pyproject): ``uv sync --no-install-project --frozen``. pyproject with [project]
    dependencies: ``uv sync --no-install-project``. Otherwise requirements*.txt files. None when the
    project declares nothing usable. ``exclude``: requirements file names never to install (a product check on a
    component app passes its aggregate files).
    """
    root = Path(checkout)
    skip = {PurePosixPath(str(n)).name for n in exclude or ()}
    pyproject = _pyproject(root / "pyproject.toml")
    if (root / "pyproject.toml").is_file() and isinstance(pyproject.get("project"), dict):
        frozen = (root / "uv.lock").is_file()
        return {"kind": "uv-sync", "frozen": frozen,
                "source": "uv.lock" if frozen else "pyproject.toml"}
    reqs = sorted(p.name for p in root.glob("requirements*.txt") if p.is_file() and p.name not in skip)
    if reqs:
        return {"kind": "requirements", "files": reqs, "source": ", ".join(reqs)}
    return None


_OFF_INDEX_OPTION = re.compile(
    r"^(?:--index-url|--extra-index-url|-i|-f|--find-links|-e|--editable|--trusted-host|--no-index)(?:[\s=]|$)")
_URL_LINE = re.compile(r"(?:^|[\s@])(?:git\+|hg\+|svn\+|bzr\+)?[a-z][a-z0-9+.-]*://", re.I)
_INCLUDE = re.compile(r"^(?:-r|--requirement|-c|--constraint)(?:\s+|=)?(\S+)")


def _local_path_line(line: str) -> bool:
    """A requirement line that names a local folder or file (``.``, ``./x``, ``../x``, ``/x``, ``~/x``, ``x.whl``)."""
    head = line.split(";")[0].split()[0] if line.split() else ""
    return (head in (".", "..") or head.startswith(("./", "../", "/", "~", "file:"))
            or head.endswith((".whl", ".tar.gz", ".zip")) or "/" in head.split("[")[0])


def _refused_line(line: str) -> bool:
    """One requirement line installs from outside the official index (option, URL, git, editable or local path)."""
    return bool(_OFF_INDEX_OPTION.match(line) or _URL_LINE.search(line) or _local_path_line(line))


def _requirement_lines(text: str):
    for raw in text.splitlines():
        line = raw.split(" #")[0].strip()
        if line and not line.startswith("#"):
            yield line


_OWN_INDEX_KEYS = ("index", "index-url", "extra-index-url", "default-index", "find-links", "no-index", "sources",
                   "trusted-host", "insecure-host")


def own_index_config(root) -> list[str]:
    """Settings in a project that ask for its own package index, find-links or uv sources: [tool.uv.sources],
    [[tool.uv.index]], a uv workspace, index keys in [tool.uv] or [tool.uv.pip], and the same keys in uv.toml.
    Product checks ignore all of these, so a project that needs them cannot be installed there."""
    root = Path(root)
    found = list(unsafe_uv_project(root))
    uv = (_pyproject(root / "pyproject.toml").get("tool") or {}).get("uv") or {}
    for label, table in (("pyproject.toml [tool.uv]", uv), ("pyproject.toml [tool.uv.pip]", (uv or {}).get("pip"))):
        if isinstance(table, dict):
            keys = [k for k in _OWN_INDEX_KEYS if k in table and not (label.endswith("[tool.uv]")
                                                                     and k in ("index", "sources"))]
            if keys:
                found.append(f"{label}: " + ", ".join(keys))
    uvtoml = _pyproject(root / "uv.toml")
    for label, table in (("uv.toml", uvtoml), ("uv.toml [pip]", uvtoml.get("pip"))):
        if isinstance(table, dict):
            keys = [k for k in _OWN_INDEX_KEYS if k in table]
            if keys:
                found.append(f"{label}: " + ", ".join(keys))
    return found


def own_index_reason(found: list[str]) -> str:
    """Could-not-verify reason for a product check whose project needs its own index or uv sources."""
    shown = "; ".join(found[:3]) + (" and more" if len(found) > 3 else "")
    return ("unsupported: the project needs its own package index or uv sources (" + shown + "). Product checks "
            "install only from the official package index and ignore those settings, so the project could not be "
            "installed and nothing was tested")


def unsafe_uv_project(root) -> list[str]:
    """pyproject settings that make a uv-sync plan install from outside the official index: any
    ``[tool.uv.sources]`` entry (path, git, URL, workspace member) or any ``[[tool.uv.index]]`` entry."""
    uv = (_pyproject(Path(root) / "pyproject.toml").get("tool") or {}).get("uv") or {}
    bad = []
    if isinstance(uv, dict):
        if uv.get("sources"):
            bad.append("pyproject.toml: [tool.uv.sources] " + ", ".join(sorted(map(str, uv["sources"])))[:120])
        if uv.get("index"):
            bad.append("pyproject.toml: [[tool.uv.index]]")
        if uv.get("workspace"):
            bad.append("pyproject.toml: [tool.uv.workspace]")
    return bad


def unsafe_exported_lines(path, label: str = "uv export") -> list[str]:
    """The same line rules applied to a ``uv export`` output file. A workspace member comes out as ``-e ./x``, so
    main's members can never be installed into the PR side to hide the PR's change."""
    try:
        text = Path(path).read_text(errors="replace")
    except OSError:
        return [f"{label}: (export output missing)"]
    return [f"{label}: {line[:120]}" for line in _requirement_lines(text) if _refused_line(line)]


def unsafe_requirement_lines(root, plan: dict | None, _seen=None, _top=None) -> list[str]:
    """Requirement lines in a deps-only plan's files that install from outside the official index.

    Refused: --index-url, --extra-index-url, -i, -f/--find-links, -e/--editable, --trusted-host, --no-index, git+ or
    any URL, and local paths (``.`` included). Files pulled in with -r/-c (``-r x``, ``-r=x``, ``-rx``) are checked
    too; an include that is a URL, absolute, uses ``..`` or resolves outside the project is itself refused. A uv-sync
    plan is refused here when pyproject has [tool.uv.sources], [[tool.uv.index]] or a workspace; its exported lines
    are checked after ``uv export`` (``unsafe_exported_lines``). Empty list: nothing refused."""
    if not plan:
        return []
    if plan.get("kind") == "uv-sync":
        return unsafe_uv_project(root)
    if plan.get("kind") != "requirements":
        return []
    root = Path(root)
    top = root.resolve() if _top is None else _top
    seen = set() if _seen is None else _seen
    bad: list[str] = []
    for name in plan.get("files") or []:
        path = (root / name).resolve()
        if not path.is_relative_to(top):   # e.g. a top-level requirements file that is a symlink out of the project
            bad.append(f"{name}: (leads outside the project)")
            continue
        if path in seen:
            continue
        seen.add(path)
        try:
            text = path.read_text(errors="replace")
        except OSError:
            continue
        for line in _requirement_lines(text):
            inc = _INCLUDE.match(line)
            if inc:
                target = inc.group(1)
                dest = (path.parent / target).resolve()
                if (_URL_LINE.search(target) or Path(target).is_absolute() or ".." in Path(target).parts
                        or target.startswith("~") or not dest.is_relative_to(top)):
                    bad.append(f"{name}: {line[:120]}")
                else:
                    bad += unsafe_requirement_lines(path.parent, {"kind": "requirements", "files": [target]},
                                                    seen, top)
                continue
            if _refused_line(line):
                bad.append(f"{name}: {line[:120]}")
    return bad


def dependency_group_reqs(checkout, self_dist: str = "") -> tuple[list[str], list[dict], list[str]]:
    """Every PEP 735 [dependency-groups] line in this checkout's pyproject, as (lines, refused, problems).

    No group name is special: all groups are read. ``{include-group = "x"}`` entries are followed; a group that
    includes itself, directly or in a loop, is read once. A line naming the project itself (for example
    ``proj[all]``) is replaced by the lines of those extras from [project.optional-dependencies], followed the same
    way, so the project itself is never installed from the index. Every resulting line goes through the deps-only
    refusal rules (index options, URLs, git, editable, local paths). ``refused`` holds refused lines and
    ``problems`` holds tables that PEP 735 does not allow (a missing included group, names that clash after
    normalization, entries that are neither a string nor an include-group table). A product check that gets
    either back stops as could not verify (see dependency_groups_reason); nothing from the groups is installed."""
    data = _pyproject(Path(checkout) / "pyproject.toml")
    groups = data.get("dependency-groups")
    if groups is None:
        return [], [], []
    if not isinstance(groups, dict):
        return [], [], ["[dependency-groups] is not a table"]
    if not groups:
        return [], [], []
    project = data.get("project") if isinstance(data.get("project"), dict) else {}
    extras = project.get("optional-dependencies") if isinstance(project.get("optional-dependencies"), dict) else {}
    selves = {norm(n) for n in (self_dist, project.get("name") or "") if n}
    out: list[str] = []
    refused: list[dict] = []
    problems: list[str] = []
    by_key: dict = {}
    for g in groups:
        key = norm(str(g))
        if key in by_key:
            problems.append(f'group names "{by_key[key]}" and "{g}" are the same after normalization')
        else:
            by_key[key] = str(g)
    seen_groups: set = set()
    seen_extras: set = set()

    def add_line(req: str, where: str) -> None:
        line = req.strip()
        if not line:
            return
        if _refused_line(line) or line.startswith("-"):
            refused.append({"name": line[:120], "reason": f"dependency group {where}: points outside the official "
                                                          "package index, so it was not installed"})
            return
        name = req_name(line)
        if name and norm(name) in selves:
            for extra in extra_names(line):
                add_extra(extra)
            return
        if line not in out:
            out.append(line)

    def add_extra(extra: str) -> None:
        key = norm(extra)
        if key in seen_extras:
            return
        seen_extras.add(key)
        for name, reqs in extras.items():
            if norm(str(name)) == key and isinstance(reqs, list):
                for req in reqs:
                    if isinstance(req, str):
                        add_line(req, f"extra {name}")

    def add_group(name: str, via: str = "") -> None:
        key = norm(name)
        if key not in by_key:
            problems.append(f'include-group "{name}" in group "{via}" names a group that does not exist')
            return
        if key in seen_groups:
            return
        seen_groups.add(key)
        real = by_key[key]
        entries = groups.get(real)
        if not isinstance(entries, list):
            problems.append(f'group "{real}" is not a list')
            return
        for entry in entries:
            if isinstance(entry, str):
                add_line(entry, real)
            elif isinstance(entry, dict) and set(entry) == {"include-group"} and isinstance(entry["include-group"], str):
                add_group(entry["include-group"], real)
            else:
                problems.append(f'group "{real}" has an entry that is neither a requirement nor an include-group '
                                f"({str(entry)[:60]})")

    for g in list(by_key.values()):
        add_group(g)
    return out, refused, list(dict.fromkeys(problems))


def dependency_groups_reason(refused: list[dict], problems: list[str]) -> str:
    """The could-not-verify reason when a product check's dependency groups can't be installed as written."""
    if refused:
        names = [r["name"] for r in refused]
        shown = "; ".join(names[:3]) + (" and more" if len(names) > 3 else "")
        return ("unsupported: the project's dependency groups list lines that point outside the official package "
                f"index ({shown}), so nothing was installed and nothing was tested")
    shown = "; ".join(problems[:3]) + (" and more" if len(problems) > 3 else "")
    return ("unsupported: the project's dependency groups can't be read as PEP 735 describes "
            f"({shown}), so nothing was installed and nothing was tested")


def extra_names(req: str) -> list[str]:
    """'pkg[a, b]; marker' -> ['a', 'b']."""
    m = re.match(r"^[A-Za-z0-9._-]+\s*\[([^\]]*)\]", req.strip())
    return [x.strip() for x in m.group(1).split(",") if x.strip()] if m else []


def drop_index_env(env: dict) -> dict:
    """The env without settings that point uv or pip at another index: UV_*INDEX*, UV_*FIND_LINKS*,
    UV_*INSECURE_HOST*, PIP_*INDEX*, PIP_*FIND_LINKS*, PIP_*TRUSTED_HOST*."""
    def off(key: str) -> bool:
        k = key.upper()
        if k.startswith("UV_"):
            return any(w in k for w in ("INDEX", "FIND_LINKS", "INSECURE_HOST"))
        if k.startswith("PIP_"):
            return any(w in k for w in ("INDEX", "FIND_LINKS", "TRUSTED_HOST"))
        return False
    return {k: v for k, v in env.items() if not off(k)}


def unsafe_requirements_reason(lines: list[str]) -> str:
    """The could-not-verify reason when the deps-only fallback refuses off-index requirement lines."""
    shown = "; ".join(lines[:3]) + (" and more" if len(lines) > 3 else "")
    return ("unsupported: the project's declared dependencies point outside the official package index "
            f"({shown}), so they were not installed and nothing was tested")


_WRONG_PYTHON = re.compile(
    r"(?:requires-python|requires a different python|no interpreter found|python_requires|"
    r"does not satisfy|not compatible with python|requires python)[^\n]*?(3\.(?:1\d|[6-9]))", re.I)


def wrong_python(log_text: str) -> str | None:
    """The Python minor version an install error says it needs, or None when the error is something else."""
    match = _WRONG_PYTHON.search(log_text or "")
    return match.group(1) if match else None


def install_system_both(run_side, name: str) -> dict:
    """Install one system package on main and pr, or on neither.

    Probe both sides first. Install only when both probes succeed. If an install then
    fails, remove the package from any side that received it.
    """
    if not safe_apt_name(name):
        return {"ok": False, "installed": [], "label": SETUP_LABEL,
                "detail": f"not a safe system package name: {name}"}
    quoted = shlex_quote(name)
    probe = f"apt-get install -s -y -qq {quoted}"
    install = f"export DEBIAN_FRONTEND=noninteractive\napt-get update -qq && apt-get install -y -qq {quoted} >/dev/null"
    remove = f"apt-get remove -y -qq {quoted} >/dev/null"

    def _code(side: str, shell: str):
        try:
            return run_side(side, shell), ""
        except Exception as exc:  # noqa: BLE001 — a sandbox error means this side cannot install
            return 1, type(exc).__name__

    for side in SIDES:
        code, err = _code(side, probe)
        if code != 0:
            detail = f"{side} cannot install {name}" + (f" ({err})" if err else "")
            return {"ok": False, "installed": [], "label": SETUP_LABEL, "detail": detail}
    installed: list[str] = []
    for side in SIDES:
        code, err = _code(side, install)
        if code != 0:
            for done in installed:
                _code(done, remove)
            detail = f"{side} install of {name} failed" + (f" ({err})" if err else "")
            return {"ok": False, "installed": [], "label": SETUP_LABEL, "detail": detail}
        installed.append(side)
    return {"ok": True, "installed": ["main", "pr"], "label": None,
            "detail": f"installed {name} on main and pr"}


def shlex_quote(value: str) -> str:
    import shlex
    return shlex.quote(str(value))


def install_same(packages, install_one) -> list[dict]:
    """Install each requirement on main, then on pr. The list and the order are the same on both sides."""
    logs = []
    for spec in packages:
        if isinstance(spec, str):
            req, source, reason = spec, "plan", "setup plan"
        else:
            if spec.get("action") not in (None, "install"):
                continue
            req, source, reason = spec["requirement"], spec.get("source") or "plan", spec.get("reason") or "setup plan"
        versions = {}
        for side in SIDES:
            ok, version = install_one(side, req)
            versions[side] = version if ok else f"failed ({version})"
        main_v, pr_v = versions.get("main"), versions.get("pr")
        logs.append({"package": req_name(req), "requirement": req,
                     "version": main_v if main_v == pr_v else f"main {main_v}, pr {pr_v}",
                     "versions": versions, "source": source, "reason": reason, "sides": ["main", "pr"]})
    return logs


def note_installs(rec: dict, logs: list[dict]) -> None:
    if not logs:
        return
    block = rec.setdefault("demo_helper", {})
    block.setdefault("installs", []).extend(logs)
    notes = list(block.get("notes") or [])
    for row in logs:
        notes.append(f"Installed {row['package']} {row['version']} from {row['source']} ({row['reason']}) on main and pr.")
    block["notes"] = _unique(notes)


def note_auto_fix(rec: dict, line: str) -> None:
    """Record one automatic setup fix in plain words; it shows in the report notes."""
    block = rec.setdefault("demo_helper", {})
    block.setdefault("auto_fixes", []).append(line)
    block["notes"] = _unique([*(block.get("notes") or []), line])
    announce([line])


def is_setup_failure(detail: str) -> bool:
    low = (detail or "").lower()
    return any(marker in low for marker in _SETUP_MARKERS)


def _unpack(result):
    if isinstance(result, tuple) and len(result) == 3:
        return bool(result[0]), "" if result[1] is None else str(result[1]), result[2]
    if isinstance(result, tuple) and len(result) == 2:
        return bool(result[0]), "" if result[1] is None else str(result[1]), None
    raise TypeError("setup function must return (ok, detail) or (ok, detail, value)")


def run_setup(step: str, fn, *, active: bool = True, cleanup=None, max_retries: int = MAX_SETUP_RETRIES,
              env: dict | None = None):
    """Retry a setup step. Inactive callers get one call and the original detail."""
    if not active:
        ok, detail, value = _unpack(fn())
        return ok, detail, value, None
    tries = max_retries + 1
    ok, detail, value = False, "", None
    for attempt in range(tries):
        if attempt and cleanup:
            cleanup()
        if attempt:
            from poc import run_progress
            run_progress.emit("retry", detail=f"{step}: try {attempt + 1} of {tries} after a setup problem: {redact(detail, env)[:200]}")
        try:
            ok, detail, value = _unpack(fn())
        except Exception as exc:  # noqa: BLE001
            ok, detail, value = False, f"{type(exc).__name__}: {exc}", None
        detail = redact(detail, env)
        if ok or not is_setup_failure(detail):
            return ok, detail, value, {"ok": ok, "label": None, "counts_as_verdict": True,
                                       "attempts": attempt + 1, "detail": detail,
                                       "retried": attempt > 0 and ok, "step": step}
    return False, detail, value, {"ok": False, "label": SETUP_LABEL, "counts_as_verdict": False,
                                  "attempts": tries, "detail": detail, "retried": False, "step": step}


def note_setup(rec: dict, step: str, outcome) -> None:
    if not outcome:
        return
    block = rec.setdefault("demo_helper", {})
    notes = list(block.get("notes") or [])
    if outcome.get("counts_as_verdict") is False:
        block["setup"] = {"label": SETUP_LABEL, "counts_as_verdict": False, "step": step,
                          "attempts": outcome.get("attempts"), "detail": outcome.get("detail")}
        line = f"{SETUP_LABEL}: {step} failed after {outcome.get('attempts')} tries."
        notes.append(line)
        block["notes"] = _unique(notes)
        announce([line])
        return
    if outcome.get("retried") and outcome.get("ok"):
        line = f"Demo helper: {step} succeeded after a setup retry."
        notes.append(line)
        block["notes"] = _unique(notes)
        announce([line])


PR_BUILD_LABEL = "the PR's own build failure"


def note_pr_build_failure(rec: dict, step: str, why: str, needs_attention: bool = False, error: str = "") -> str:
    """Main installed fine and only the PR side failed to build: the PR's own failure, not a setup problem.
    It is labelled that way and never retried as setup. Returns the reason line for the record."""
    reason = f"the PR's own build failed (main installed fine): {why}"
    rec["pr_build_failure"] = {"step": step, "why": str(why)[:400], "needs_attention": bool(needs_attention),
                               "error": (error or "")[:300]}
    block = rec.setdefault("demo_helper", {})
    block["setup"] = {"label": PR_BUILD_LABEL, "counts_as_verdict": True, "step": step, "pr_own_failure": True,
                      "detail": str(why)[:400]}
    line = f"{PR_BUILD_LABEL}: main installed fine, the {step} failed; not retried as a setup problem."
    block["notes"] = _unique([*(block.get("notes") or []), line])
    announce([line])
    return reason


def counts_as_verdict(rec: dict) -> bool:
    setup = (rec.get("demo_helper") or {}).get("setup") or {}
    return setup.get("counts_as_verdict") is not False


def shown_outcome(rec: dict) -> str:
    if not counts_as_verdict(rec):
        return SETUP_LABEL
    return rec.get("verdict")


def is_setup_gap(verdict, text: str) -> bool:
    if verdict != "could_not_verify":
        return False
    low = (text or "").lower()
    return any(marker in low for marker in _GAP_MARKERS)


def _keep_bit(bits: list[str], bit: str, limit: int) -> None:
    """Keep the longer of two overlapping error lines, and stop at `limit` lines."""
    if not bit or len(bits) >= limit and all(earlier not in bit for earlier in bits):
        return
    for i, earlier in enumerate(bits):
        if bit in earlier:
            return
        if earlier in bit:
            bits[i] = bit
            return
    if len(bits) < limit:
        bits.append(bit)


def pytest_error_text(log_dir=None, record: dict | None = None, limit: int = 4000) -> str:
    """Import and collection errors from pytest logs, junit files, and per-run summaries.

    Secrets are removed before the text is returned.
    """
    blobs: list[str] = []
    if isinstance(record, dict):
        for entry in record.get("per_run") or []:
            if isinstance(entry, dict) and entry.get("pytest_summary"):
                blobs.append(str(entry["pytest_summary"]))
    root = Path(log_dir) if log_dir else None
    if root is not None and root.is_dir():
        files = sorted(root.glob("pytest-*.log")) + sorted(root.glob("junit-*.xml"))
        for path in files[:12]:
            try:
                blobs.append(path.read_text(errors="replace"))
            except OSError:
                continue
    bits: list[str] = []
    for blob in blobs:
        for match in _PYTEST_ERROR.finditer(blob):
            _keep_bit(bits, " ".join(match.group(0).split()), 8)
        if len(bits) >= 8:
            break
    return redact("\n".join(bits))[:limit]


def gap_text(rec: dict, log_dir=None) -> str:
    """Reason, probe errors, comparison messages, and the pytest or collection error."""
    parts = [str(rec.get("reason") or "")]
    probes = rec.get("probes") or {}
    items = probes.get("items") if isinstance(probes, dict) else probes
    if isinstance(items, list):
        for item in items:
            if isinstance(item, dict):
                parts.append(str(item.get("error") or item.get("detail") or ""))
    comparison = rec.get("comparison") or {}
    if isinstance(comparison, dict):
        messages = comparison.get("messages") or {}
        if isinstance(messages, dict):
            parts.extend(str(value) for value in messages.values())
    # Log files are read only when a caller passes a directory. The study path calls this with no directory,
    # so its gap text stays the reason, the probes and the comparison messages.
    if log_dir is not None:
        logged = pytest_error_text(log_dir, rec)
        if logged:
            parts.append(logged)
    return "\n".join(part for part in parts if part)


def _modules(text: str) -> list[str]:
    found = []
    for match in re.finditer(r"No module named ['\"]([^'\"]+)['\"]", text or ""):
        top = match.group(1).split(".")[0]
        if top and top not in found:
            found.append(top)
    for match in re.finditer(r"No module named ([A-Za-z_][A-Za-z0-9_]*)", text or ""):
        if match.group(1) not in found:
            found.append(match.group(1))
    return found


def _libs(text: str) -> list[str]:
    return list(dict.fromkeys(re.findall(r"(lib[\w.+-]+\.so(?:\.\d+)*)", text or "")))


def _files(text: str) -> list[str]:
    found = []
    for match in re.finditer(r"No such file or directory: ['\"]([^'\"]+)['\"]", text or ""):
        found.append(match.group(1))
    for match in re.finditer(r"missing fixture ['\"]?([^\s'\"]+)", text or "", re.I):
        found.append(match.group(1))
    return found


def gap_name(text: str) -> str:
    modules = _modules(text)
    if modules:
        return modules[0]
    libs = _libs(text)
    if libs:
        return libs[0]
    files = _files(text)
    if files:
        return f"missing fixture {Path(files[0]).name}"
    low = (text or "").lower()
    if any(marker in low for marker in ("version conflict", "conflicting dependencies", "resolutionimpossible")):
        return "version conflict"
    if any(marker in low for marker in ("importerror", "modulenotfounderror", "no module named")):
        return "import"
    return "setup"


def _declared_req(module: str, declared) -> str | None:
    for item in declared or []:
        req = item if isinstance(item, str) else item.get("requirement", "")
        if req and norm(req_name(req)) == norm(module):
            return req
    return None


def error_excerpt(text: str, limit: int = 240) -> str:
    """The real error lines, shortened and with secrets removed."""
    found: list[str] = []
    for match in _PYTEST_ERROR.finditer(text or ""):
        _keep_bit(found, " ".join(match.group(0).split()), 3)
        if len(found) >= 3:
            break
    if not found:
        for raw in (text or "").splitlines():
            line = raw.strip()
            low = line.lower()
            if any(marker in low for marker in ("no such file", "version conflict", "resolutionimpossible",
                                                "conflicting dependencies")):
                if line not in found:
                    found.append(line)
            if len(found) >= 3:
                break
    return redact(" | ".join(found))[:limit]


def _gap_reason(name: str, detail: str = "") -> str:
    """could_not_verify reason that keeps the real error next to the short name."""
    base = f"could not verify: setup gap {name}"
    excerpt = error_excerpt(detail)
    if excerpt and excerpt not in base:
        return f"{base}: {excerpt}"
    return base


def _lookup_text(extra) -> str:
    if not isinstance(extra, dict):
        return ""
    parts = [str(extra.get("answer") or ""), str(extra.get("text") or "")]
    for item in extra.get("results") or []:
        if isinstance(item, dict):
            parts.append(str(item.get("content") or ""))
    return "\n".join(part for part in parts if part)


def change_is_small(rec: dict) -> bool:
    """True when the recorded change is small enough to measure probe line coverage again."""
    total = (rec.get("coverage") or {}).get("changed_lines_total")
    if isinstance(total, bool) or not isinstance(total, int):
        return False
    return total <= SMALL_CHANGED_LINES


def _has_probe_items(rec: dict) -> bool:
    probes = rec.get("probes") or {}
    return bool(isinstance(probes, dict) and probes.get("items"))


def probe_coverage_supports_verified(rec: dict) -> bool:
    """True when a fresh measurement shows a changed line ran.

    A measurement with no changed lines is not adequate, so it does not support verified.
    """
    items = (rec.get("probes") or {}).get("items") or []
    if not items:
        return True
    totals = []
    covered = False
    for item in items:
        if not isinstance(item, dict):
            continue
        cov = item.get("probe_changed_line_coverage") or {}
        if cov.get("status") != "measured":
            continue
        total = cov.get("changed_lines_total") or 0
        totals.append(total)
        if (cov.get("changed_lines_covered") or 0) > 0:
            covered = True
    if not totals:
        return False
    if max(totals) == 0:
        return False
    return covered


def _coverage_blocks_verified(rec: dict, after_verdict: str, recheck_coverage) -> tuple[str, str] | None:
    """A replacement verdict when a rerun must not be taken as verified, or None to keep the rerun result.

    Probe line coverage is recomputed only when the change is small. Otherwise the measurement is skipped.
    """
    if after_verdict != "verified" or not _has_probe_items(rec):
        return None
    if not change_is_small(rec):
        return ("could_not_verify",
                "could not verify: probe line coverage was not recomputed after the setup rerun "
                "because the change is not small")
    if recheck_coverage is None:
        return ("could_not_verify",
                "could not verify: probe line coverage was not recomputed after the setup rerun")
    got = recheck_coverage() or {}
    fresh = got.get("verdict")
    if fresh in ("needs_attention", "could_not_verify"):
        return fresh, got.get("reason") or rec.get("reason") or ""
    if not probe_coverage_supports_verified(rec):
        return ("could_not_verify",
                "could not verify: probe line coverage after the setup rerun does not show a changed line ran")
    if fresh == "verified" and got.get("reason"):
        return "verified", got["reason"]
    return None


def _gap_specs(text: str, declared, tavily_text: str, pypi, owner: str, repo_name: str, notes: list) -> list[dict]:
    suggested = set(pip_suggestions(tavily_text or ""))
    specs = []
    for module in _modules(text):
        declared_req = _declared_req(module, declared)
        if declared_req:
            specs.append({"requirement": declared_req, "source": "project", "reason": "named by the error and listed in the project"})
            continue
        if module in suggested or norm(module) in {norm(item) for item in suggested}:
            try:
                info = pypi(module) if pypi else None
            except Exception:  # noqa: BLE001
                info = None
            if pypi_links_back(info, owner, repo_name):
                specs.append({"requirement": module, "source": "tavily",
                              "reason": "named by the error and its PyPI page links to this GitHub repository"})
            else:
                notes.append(f"Setup plan: refused {module}: its PyPI page does not link to this GitHub repository")
        else:
            notes.append(f"Setup plan: refused {module}: not listed by the project and not a link-back suggestion")
    return specs


def _emit_retry(detail: str) -> None:
    from poc import run_progress
    run_progress.emit("retry", detail=detail[:400])


def retry_unverified_study(rec: dict, rerun, install_one, declared, tavily_text: str, pypi, repo: str,
                     allow_system: bool = False, install_system=None, lookup=None, recheck_coverage=None) -> dict:
    """Study and daily-study path, unchanged from before the product check flow.

    One rerun when a could-not-verify result is a setup gap. Tavily text alone never changes the verdict.

    This is the only step that can raise could_not_verify to verified. When the record has probes, that raise
    waits for a fresh probe line-coverage measurement. The measurement runs only when the change is small.
    A larger change skips it, and the verdict stays could_not_verify.

    ``allow_system`` and ``install_system`` are unused. They stay so older callers still pass, and this step
    does not install an OS package.
    """
    _ = (allow_system, install_system)
    block = rec.setdefault("demo_helper", {})
    notes = list(block.get("notes") or [])
    setup = block.get("setup") or {}
    if setup.get("counts_as_verdict") is False:
        notes.append("Demo helper: setup failure already labelled; the probe was not rerun.")
        block["notes"] = _unique(notes)
        return rec
    text = gap_text(rec)
    if not is_setup_gap(rec.get("verdict"), text):
        block["notes"] = _unique(notes)
        return rec
    name = gap_name(text)
    if lookup is not None:
        try:
            extra = lookup(f"{repo} {name} python install")
        except Exception:  # noqa: BLE001 — keep going with the error text and the project files
            extra = None
        if isinstance(extra, dict):
            extra = scope_lookup(extra, repo, str(rec.get("library") or ""))
        tavily_text = (tavily_text or "") + "\n" + _lookup_text(extra)
    before = {"round": 1, "verdict": rec.get("verdict"), "reason": rec.get("reason")}
    parts = split_repo(repo or "")
    owner, repo_name = parts if parts else ("", "")
    suggested = set(pip_suggestions(tavily_text or ""))
    specs = []
    for module in _modules(text):
        declared_req = _declared_req(module, declared)
        if declared_req:
            specs.append({"requirement": declared_req, "source": "project", "reason": "named by the error and listed in the project"})
            continue
        if module in suggested or norm(module) in {norm(item) for item in suggested}:
            try:
                info = pypi(module) if pypi else None
            except Exception:  # noqa: BLE001
                info = None
            if pypi_links_back(info, owner, repo_name):
                specs.append({"requirement": module, "source": "tavily",
                              "reason": "named by the error and its PyPI page links to this GitHub repository"})
            else:
                notes.append(f"Setup plan: refused {module}: its PyPI page does not link to this GitHub repository")
        else:
            notes.append(f"Setup plan: refused {module}: not listed by the project and not a link-back suggestion")
    # A system package comes from the project's own files, applied with the setup plan.
    # Lookup text never adds one, even when the error names a missing library.
    if not specs:
        rec["verdict"] = "could_not_verify"
        rec["reason"] = _gap_reason(name)
        notes.append(f"Before rerun: {before['verdict']}: {before['reason']}")
        notes.append(f"After rerun: not rerun. {rec['reason']}")
        block["notes"] = _unique(notes)
        block["gap_retry"] = {"reran": False, "rounds": [before], "installed": []}
        return rec
    if rerun is None:
        rec["verdict"] = "could_not_verify"
        rec["reason"] = _gap_reason(name)
        notes.append(rec["reason"])
        block["notes"] = _unique(notes)
        block["gap_retry"] = {"reran": False, "rounds": [before], "installed": []}
        return rec
    logs = install_same(specs, install_one) if specs else []
    note_installs(rec, logs)
    notes = list(block.get("notes") or [])
    installed = [row for row in logs if not str(row["versions"].get("main", "")).startswith("failed")
                 and not str(row["versions"].get("pr", "")).startswith("failed")]
    if not installed:
        rec["verdict"] = "could_not_verify"
        rec["reason"] = _gap_reason(name)
        notes.append(f"Before rerun: {before['verdict']}: {before['reason']}")
        notes.append(f"After rerun: not rerun. {rec['reason']}")
        block["notes"] = _unique(notes)
        block["gap_retry"] = {"reran": False, "rounds": [before], "installed": logs}
        return rec
    outcome = rerun() or {}
    after_verdict = outcome.get("verdict", rec.get("verdict"))
    after_reason = outcome.get("reason", rec.get("reason"))
    after_text = f"{after_verdict}\n{after_reason}"
    if is_setup_gap(after_verdict, after_text):
        rec["verdict"] = "could_not_verify"
        rec["reason"] = _gap_reason(gap_name(after_reason or text))
    else:
        held = _coverage_blocks_verified(rec, after_verdict, recheck_coverage)
        if held:
            rec["verdict"], rec["reason"] = held
        else:
            rec["verdict"] = after_verdict
            rec["reason"] = after_reason
    notes.append(f"Before rerun: {before['verdict']}: {before['reason']}")
    notes.append(f"After rerun: {rec['verdict']}: {rec['reason']}")
    block["notes"] = _unique(notes)
    block["gap_retry"] = {"reran": True, "rounds": [before, {"round": 2, "verdict": rec["verdict"], "reason": rec["reason"]}],
                          "installed": logs}
    return rec



def retry_unverified(rec: dict, rerun, install_one, declared, tavily_text: str, pypi, repo: str,
                     allow_system: bool = False, install_system=None, lookup=None, recheck_coverage=None,
                     max_tries: int = MAX_GAP_TRIES, declared_urls=(), apt_check=None,
                     project_text: str = "", log_dir=None) -> dict:
    """Up to ``max_tries`` reruns when a could-not-verify result is a setup or import gap.

    Each try: look the error up (Tavily, when a lookup is given), install the fix on main and pr, rerun the step.
    Every try is logged in ``gap_retry.tries``. A needs-attention result (a PR-caused test failure) is never retried.
    Tavily text alone never changes the verdict. This is the only step that can raise could_not_verify to
    verified, and that raise still waits for a fresh probe line-coverage measurement when the record has probes.

    ``allow_system`` and ``install_system`` are unused. A missing system library, header or build tool is a
    could-not-verify limitation. This step does not install an OS package on any sandbox.
    """
    _ = (allow_system, install_system)
    block = rec.setdefault("demo_helper", {})
    notes = list(block.get("notes") or [])
    setup = block.get("setup") or {}
    if setup.get("counts_as_verdict") is False:
        notes.append("Demo helper: setup failure already labelled; the probe was not rerun.")
        block["notes"] = _unique(notes)
        return rec
    if rec.get("pr_build_failure"):
        notes.append("Demo helper: main installed fine and only the PR side failed to build; that is the PR's own "
                     "failure, so it was not retried as a setup problem.")
        block["notes"] = _unique(notes)
        return rec
    text = gap_text(rec, log_dir=log_dir)
    if not is_setup_gap(rec.get("verdict"), text):
        block["notes"] = _unique(notes)
        return rec
    parts = split_repo(repo or "")
    owner, repo_name = parts if parts else ("", "")
    apt_check = apt_check or apt_available
    rounds = [{"round": 1, "verdict": rec.get("verdict"), "reason": rec.get("reason")}]
    tries: list[dict] = []
    all_logs: list[dict] = []
    reran = False
    lookup_text = tavily_text or ""
    tried: set[str] = set()
    for attempt in range(1, max(0, max_tries) + 1):
        name = gap_name(text)
        query = f"{repo} {name} install {failure_line(text)}"[:380]
        looked = False
        sources: list[str] = []
        if lookup is not None:
            try:
                extra = lookup(query)
            except Exception:  # noqa: BLE001 — keep going with the error text and the project files
                extra = None
            if isinstance(extra, dict):
                extra = trusted_lookup(scope_lookup(extra, repo, str(rec.get("library") or "")), repo, declared_urls)
                looked = True
                sources = list(extra.get("sources") or [])
            lookup_text = lookup_text + "\n" + _lookup_text(extra)
        specs = _gap_specs(text, declared, lookup_text, pypi, owner, repo_name, notes)
        repeat = [spec for spec in specs if norm(req_name(spec["requirement"])) in tried]
        specs = [spec for spec in specs if norm(req_name(spec["requirement"])) not in tried]
        tried.update(norm(req_name(spec["requirement"])) for spec in specs)
        entry = {"try": attempt, "problem": name, "lookup": query if looked else None, "sources": sources,
                 "planned": [spec["requirement"] for spec in specs], "installed": [], "rerun": False}
        # A missing library, header or build tool stops here on every sandbox, including Contree.
        if not specs and is_system_failure(text):
            pieces = missing_system_pieces(text)
            if not pieces:
                line = failure_line(text)
                pieces = [line[:120]] if line else []
            entry["result"] = "needs a system library, header or build tool; this check does not install OS packages"
            entry["planned"] = list(pieces)
            note_limitation(rec, pieces, failure_line(text),
                            "this check does not install system libraries, headers or build tools")
            tries.append(entry)
            _emit_retry(f"Try {attempt} of {max_tries}: {name}: {entry['result']}")
            break
        if specs is not None and (not specs or rerun is None):
            if not specs and repeat:
                entry["result"] = "already installed on an earlier try and still missing"
            else:
                entry["result"] = "nothing safe to install" if not specs else "no rerun available"
            tries.append(entry)
            _emit_retry(f"Try {attempt} of {max_tries}: {name}: {entry['result']}")
            break
        if specs is not None:
            logs = install_same(specs, install_one)
            note_installs(rec, logs)
            notes = list(block.get("notes") or [])
            all_logs.extend(logs)
            good = [row for row in logs if not str(row["versions"].get("main", "")).startswith("failed")
                    and not str(row["versions"].get("pr", "")).startswith("failed")]
            entry["installed"] = [f"{row['package']} {row['version']}" for row in good]
            if not good:
                entry["result"] = "install failed on main or pr"
                tries.append(entry)
                _emit_retry(f"Try {attempt} of {max_tries}: {name}: {entry['result']}")
                break
            _emit_retry(f"Try {attempt} of {max_tries}: installed {', '.join(entry['installed'])} on main and pr; rerunning")
        outcome = rerun() or {}
        reran = True
        entry["rerun"] = True
        after_verdict = outcome.get("verdict", rec.get("verdict"))
        after_reason = outcome.get("reason", rec.get("reason"))
        after_text = f"{after_verdict}\n{after_reason}"
        if is_setup_gap(after_verdict, after_text):
            kept = text
            named = gap_name(after_reason or kept)
            rec["verdict"] = "could_not_verify"
            rec["reason"] = _gap_reason(named, after_reason or kept)
            entry["result"] = f"still a setup gap: {named}"
            # A rerun that only repeats a generic reason must not drop the pytest error the lookup diagnoses.
            text = after_text if error_excerpt(after_reason or "") else f"{after_text}\n{kept}"
        else:
            held = _coverage_blocks_verified(rec, after_verdict, recheck_coverage)
            if held:
                rec["verdict"], rec["reason"] = held
            else:
                rec["verdict"], rec["reason"] = after_verdict, after_reason
            entry["result"] = f"fixed: {rec['verdict']}"
        rounds.append({"round": attempt + 1, "verdict": rec["verdict"], "reason": rec["reason"]})
        tries.append(entry)
        if not entry["result"].startswith("still"):
            break
    if not reran or is_setup_gap(rec.get("verdict"), f"{rec.get('verdict')}\n{rec.get('reason')}"):
        rec["verdict"] = "could_not_verify"
        rec["reason"] = _gap_reason(gap_name(text), text)
    notes.append(f"Before rerun: {rounds[0]['verdict']}: {rounds[0]['reason']}")
    if reran:
        notes.append(f"After rerun: ({len(tries)} of {max_tries} tries) {rec['verdict']}: {rec['reason']}")
    else:
        notes.append(f"After rerun: not rerun. {rec['reason']}")
    block["notes"] = _unique(notes)
    block["gap_retry"] = {"reran": reran, "rounds": rounds, "installed": all_logs, "tries": tries,
                          "max_tries": max_tries}
    return rec


def _table_cells(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def check_report(records, markdown: str) -> dict:
    """Compare the summary table with the records. A setup problem is not a verdict count."""
    mismatches = []
    report_counts: dict = {}
    lines = {}
    for line in (markdown or "").splitlines():
        if not line.startswith("| ["):
            continue
        cells = _table_cells(line)
        if len(cells) < 4:
            continue
        label = cells[0]
        key = label.split("]", 1)[0].lstrip("[").split("](")[0]
        lines[key] = line
        verdict = cells[3].replace("**", "").strip()
        if verdict == SETUP_LABEL:
            continue
        if verdict in VERDICTS:
            report_counts[verdict] = report_counts.get(verdict, 0) + 1
        else:
            mismatches.append(f"unrecognised verdict cell: {verdict}")
    record_counts: dict = {}
    for rec in records or []:
        tag = f"{rec.get('repo')}#{_pr_number(rec)}"
        if not counts_as_verdict(rec):
            row = lines.get(tag, "")
            if SETUP_LABEL not in row or any(f"**{name}**" in row for name in VERDICTS):
                mismatches.append(f"{tag}: setup problem should be shown as {SETUP_LABEL}")
            continue
        verdict = rec.get("verdict")
        record_counts[verdict] = record_counts.get(verdict, 0) + 1
        reason = rec.get("reason") or ""
        gap = "could not verify: setup gap"
        if gap in reason and reason not in (markdown or "") and gap not in (markdown or ""):
            mismatches.append(f"{tag}: report is missing the setup gap")
        for note in ((rec.get("demo_helper") or {}).get("notes") or []):
            if note.startswith("Looked up with Tavily") or note.startswith("Setup plan:"):
                if note not in (markdown or ""):
                    mismatches.append(f"{tag}: report is missing {note[:80]}")
    if record_counts != report_counts:
        mismatches.append(f"verdict counts differ: records {record_counts} report {report_counts}")
    return {"ok": not mismatches, "mismatches": mismatches, "record_counts": record_counts, "report_counts": report_counts}


def _pr_number(rec: dict):
    pr = rec.get("pr")
    if isinstance(pr, dict):
        return pr.get("number")
    return pr


def self_check_markdown(audit: dict) -> str:
    if audit.get("ok"):
        return "Self-check: the report matches the run records.\n"
    lines = ["Self-check: the report does not match the run records."]
    lines.extend(f"- {item}" for item in audit.get("mismatches") or [])
    return "\n".join(lines) + "\n"


def markdown_for(rec: dict) -> str:
    helper = rec.get("demo_helper") or {}
    notes = helper.get("notes") if isinstance(helper, dict) else None
    if not notes:
        return ""
    lines = ["", "#### Demo helper", "",
             "These notes are background for the console and the daily check. They do not change the verdict.",
             "", RETRY_LIMITS, ""]
    lines.extend(f"- {note}" for note in notes)
    lines.append("")
    return "\n".join(lines)


def attach_self_check(path, meta: dict, records, runner) -> dict | None:
    """Append the self-check when this product run recorded helper notes. Study runs are unchanged."""
    if not active(runner):
        return None
    if not any(isinstance(rec.get("demo_helper"), dict) and (rec.get("demo_helper") or {}).get("notes") for rec in records):
        return None
    file = Path(path)
    text = file.read_text() if file.is_file() else ""
    audit = check_report(records, text)
    block = self_check_markdown(audit)
    file.write_text(text + "\n" + block)
    meta["demo_helper_self_check"] = {key: audit[key] for key in ("ok", "mismatches", "record_counts", "report_counts")}
    announce(block.splitlines())
    return audit
