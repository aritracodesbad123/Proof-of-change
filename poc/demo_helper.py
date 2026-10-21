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
import urllib.parse
import urllib.request
from pathlib import Path

from evals.label_study_pairs import split_repo

SETUP_LABEL = "rerun, setup problem"
MAX_SETUP_RETRIES = 2  # further install attempts after the first failure
MAX_GAP_ROUNDS = 2  # the first run plus one setup-gap rerun of that test
RETRY_LIMITS = (
    "If setup fails, the helper retries the install up to 2 times. "
    "If a test still can't be verified because something is missing, it installs what's missing and reruns that test once."
)
TAVILY_TIMEOUT = 8
PYPI_TIMEOUT = 8
MAX_SUGGESTIONS = 8
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
        except OSError:
            return


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


def lookup_project(repo: str, project: str, cache, env: dict | None = None, fetch=None) -> dict:
    """Look up setup instructions. A live call is recorded only when a fetch actually runs."""
    env = os.environ if env is None else env
    queries = lookup_queries(repo, project)
    if not str(env.get("TAVILY_API_KEY") or "").strip():
        return {"ok": False, "skipped": True, "live_call": False, "cached": False, "queries": queries,
                "results": [], "text": "", "errors": [],
                "lines": ["Tavily lookup skipped: TAVILY_API_KEY is not set."]}
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
    lines = _result_lines(queries, results, errors, live)
    return {"ok": bool(results) and not errors, "skipped": False, "live_call": live,
            "cached": cached_any and not fresh_any, "queries": queries,
            "results": [{"title": item["title"], "url": item["url"], "query": item["query"]} for item in results],
            "text": redact("\n".join(texts), env), "errors": [redact(err, env) for err in errors],
            "lines": [redact(line, env) for line in lines]}


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
        looked = lookup_project(repo, project, cache, env=env, fetch=fetch)
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


def declared_packages(checkout, self_dist: str = "") -> list[dict]:
    """Packages the checkout lists. Runtime deps are noted. Test extras and requirements are installed."""
    root = Path(checkout)
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
        for req in _req_lines(_read(path)):
            _add_pkg(found, seen, req, kind="requirements", action="install", source=path.name,
                     reason=f"listed in {path.name}", self_dist=self_dist)
    return found


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
    setup_py = _read(root / "setup.py")
    for match in re.finditer(r"""python_requires\s*=\s*['\"]([^'\"]+)['\"]""", setup_py):
        specs.append(match.group(1))
    declared.extend(_classifier_versions(setup_py))
    return specs, declared


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
    """True when the URL's host is github.com and its first two path segments are owner/repo.

    www.github.com is the same host. The match ignores case and one trailing .git.
    A lookalike host, or a path that only contains the repository text, is not a match.
    """
    if not isinstance(value, str) or not owner or not repo:
        return False
    try:
        parsed = urllib.parse.urlsplit(value.strip())
    except ValueError:
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


def _python_decision(requested: str | None, current: str, sandbox: str, python_available, requirement: str = "") -> dict:
    if not requested:
        return {"requested": None, "current": current, "applied": False, "switch": None,
                "reason": "no Python version was requested"}
    current_minor = _minor(current)
    wanted = _minor(requested)
    if current_minor and wanted and current_minor == wanted:
        met = requirement or requested
        return {"requested": requested, "current": current, "applied": True, "switch": None,
                "reason": f"Python {current} already meets {met}"}
    if sandbox == "contree":
        return {"requested": requested, "current": current, "applied": False, "switch": None,
                "reason": "not applied: the Contree image keeps its Python"}
    path = python_available(requested) if python_available else None
    if path:
        return {"requested": requested, "current": current, "applied": True, "switch": path,
                "reason": f"switched the local sandbox to {path}"}
    return {"requested": requested, "current": current, "applied": False, "switch": None,
            "reason": f"not applied: python{requested} is not available to the local sandbox"}


def _system_decision(names: list[str], sandbox: str) -> list[dict]:
    out = []
    for name in names:
        if not safe_apt_name(name):
            out.append({"name": name, "applied": False, "sides": ["main", "pr"],
                        "reason": "not applied: the name is not a safe system package name"})
        elif sandbox == "contree":
            out.append({"name": name, "applied": True, "sides": ["main", "pr"],
                        "reason": "applied in the Contree sandbox"})
        else:
            out.append({"name": name, "applied": False, "sides": ["main", "pr"],
                        "reason": "not applied: the local sandbox cannot install system packages"})
    return out


def build_setup_plan(repo: str, checkouts, tavily, current_python: str, sandbox: str, self_dist: str = "",
                     python_available=None, pypi=None, allow_lookup_packages: bool = True) -> dict:
    """One plan for both sides. Only project-listed packages and link-back suggestions are added."""
    python_available = find_python if python_available is None else python_available
    pypi = fetch_pypi if pypi is None else pypi
    packages: list[dict] = []
    seen: set = set()
    for checkout in checkouts or []:
        for item in declared_packages(checkout, self_dist):
            key = norm(item["name"])
            if key in seen:
                continue
            seen.add(key)
            packages.append(item)
    text = _tavily_text(tavily)
    refused = []
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
    requirement = ", ".join(dict.fromkeys(item.strip() for item in spec_texts if item and item.strip()))
    system_names = []
    for checkout in checkouts or []:
        for name in _apt_from_tree(Path(checkout)):
            if name not in system_names:
                system_names.append(name)
    python = _python_decision(requested, current_python or "", sandbox or "local", python_available, requirement)
    system = _system_decision(system_names, sandbox or "local")
    extra = [item["requirement"] for item in packages if item["action"] == "install"]
    lines = ["Setup plan: the same packages on main and pr."]
    for item in packages:
        if item["action"] == "install":
            lines.append(f"Setup plan: install {item['requirement']} ({item['reason']}) on main and pr.")
        else:
            lines.append(f"Setup plan: {item['name']} is noted, installed with the project.")
    if requested:
        lines.append(f"Setup plan: Python {requested}: {python['reason']}")
    for item in system:
        lines.append(f"Setup plan: system package {item['name']}: {item['reason']}")
    for item in refused:
        lines.append(f"Setup plan: refused {item['name']}: {item['reason']}")
    return {"packages": packages, "extra_reqs": extra, "python": python, "system": system,
            "refused": refused, "lines": lines}


def attach_plan(rec: dict, plan: dict) -> None:
    block = rec.setdefault("demo_helper", {})
    block["setup_plan"] = {key: value for key, value in plan.items() if key != "lines"}
    block["notes"] = _unique([*(block.get("notes") or []), *plan.get("lines", [])])


def contree_shell(plan: dict | None) -> str:
    """Extra shell for both Contree checkpoints. Empty when the plan adds nothing the sandbox may apply."""
    if not plan:
        return ""
    lines = []
    apt = [item["name"] for item in plan.get("system") or [] if item.get("applied") and safe_apt_name(item["name"])]
    if apt:
        quoted = " ".join(shlex_quote(name) for name in apt)
        lines.append(f"export DEBIAN_FRONTEND=noninteractive\napt-get update -qq && apt-get install -y -qq {quoted} >/dev/null")
    reqs = [req for req in (plan.get("extra_reqs") or []) if str(req).strip()]
    if reqs:
        lines.append("python -m pip install -q " + " ".join(shlex_quote(req) for req in reqs))
    return "\n".join(lines)


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


def gap_text(rec: dict) -> str:
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
    return "\n".join(parts)


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


def _gap_reason(name: str) -> str:
    return f"could not verify: setup gap {name}"


def _lookup_text(extra) -> str:
    if not isinstance(extra, dict):
        return ""
    parts = [str(extra.get("answer") or ""), str(extra.get("text") or "")]
    for item in extra.get("results") or []:
        if isinstance(item, dict):
            parts.append(str(item.get("content") or ""))
    return "\n".join(part for part in parts if part)


def retry_unverified(rec: dict, rerun, install_one, declared, tavily_text: str, pypi, repo: str,
                     allow_system: bool, install_system=None, lookup=None) -> dict:
    """One rerun when a could-not-verify result is a setup gap. Tavily text alone never changes the verdict."""
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
        rec["verdict"] = after_verdict
        rec["reason"] = after_reason
    notes.append(f"Before rerun: {before['verdict']}: {before['reason']}")
    notes.append(f"After rerun: {rec['verdict']}: {rec['reason']}")
    block["notes"] = _unique(notes)
    block["gap_retry"] = {"reran": True, "rounds": [before, {"round": 2, "verdict": rec["verdict"], "reason": rec["reason"]}],
                          "installed": logs}
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
