"""Tavily repository crawl for a product check.

Before either side is installed, a product check crawls the pull request's own GitHub repository at the PR's base
commit, plus the project's own documentation site when its packaging metadata lists one. No other domain is
crawled. The crawl targets install, contributing, development and testing pages and the CI workflow files. Tavily
Extract then pulls the full text of the key pages. Concrete setup steps are read from that text and kept only when
the project's own files back them (an extra, a dependency group or a requirements file that exists, or a package
the project itself declares). Kept steps go into the sandbox install before the default install. Nothing here
installs anything, and nothing here is specific to one project.

A study run never calls this. The key is sent only in the Authorization header and is never written to a record.
"""
from __future__ import annotations

import json
import os
import re
import shlex
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

KEY_ENV = "TAVILY_API_KEY"
CRAWL_API = "https://api.tavily.com/crawl"
EXTRACT_API = "https://api.tavily.com/extract"
UNAVAILABLE = "Tavily unavailable"
CRAWL_LIMIT = 40
EXTRACT_MAX = 12
TIMEOUT = 150
CACHE_ENV = "POC_TAVILY_CRAWL_CACHE"
CACHE_TTL = 7 * 24 * 3600   # seconds; the base commit pins the content, the TTL only bounds staleness of docs pages

INSTRUCTIONS = (
    "Find the pages that explain how to set this project up for development and run its test suite: install and "
    "development setup, contributing guides, testing guides, test dependencies, extras or dependency groups, the "
    "supported Python versions, pytest configuration, and the CI workflow files that install and test it.")

# Generic names for setup pages and files. No project names.
_KEY_PAGE = re.compile(
    r"(?i)(install|contribut|develop|hacking|testing|/tests?\b|getting[-_]?started|setup\.cfg|setup\.py|"
    r"pyproject\.toml|tox\.ini|noxfile\.py|pytest\.ini|requirements[^/]*\.(txt|in)|"
    r"\.github/workflows/[^/]+\.ya?ml|readme)")
_LOCAL_FILES = ("pyproject.toml", "setup.cfg", "setup.py", "tox.ini", "noxfile.py", "pytest.ini",
                "CONTRIBUTING.md", "CONTRIBUTING.rst", "CONTRIBUTING.txt", "README.md", "README.rst",
                "docs/contributing.rst", "docs/contributing.md", "docs/development.rst", "docs/development.md",
                "docs/installation.rst", "docs/installation.md", "docs/testing.rst", "docs/testing.md")
_NOT_DOCS_HOSTS = ("github.com", "pypi.org", "twitter.com", "x.com", "gitter.im", "discord.gg", "tidelift.com",
                   "opencollective.com", "github.io")


def available(env: dict | None = None) -> bool:
    env = os.environ if env is None else env
    return bool(str(env.get(KEY_ENV) or "").strip())


def _post(api: str, body: dict, env: dict, timeout: float) -> dict:
    secret = str(env.get(KEY_ENV) or "").strip()
    req = urllib.request.Request(
        api, data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {secret}"},
        method="POST")  # br-allow-external: Tavily repository crawl for a product check
    try:
        with urllib.request.urlopen(req, timeout=timeout + 15) as r:  # noqa: S310
            raw = r.read()
    except Exception as e:  # noqa: BLE001
        message = f"{type(e).__name__}: {e}"
        if secret:
            message = message.replace(secret, "[redacted]")
        return {"ok": False, "error": message, "results": []}
    try:
        data = json.loads(raw or b"")
    except json.JSONDecodeError:
        return {"ok": False, "error": "the response was not valid JSON", "results": []}
    if not isinstance(data, dict):
        return {"ok": False, "error": "the response was not valid", "results": []}
    data["ok"] = True
    return data


def crawl(url: str, *, select_domains, select_paths=None, instructions: str = INSTRUCTIONS,
          limit: int = CRAWL_LIMIT, max_depth: int = 2, env: dict | None = None, timeout: float = TIMEOUT) -> dict:
    env = os.environ if env is None else env
    body = {"url": url, "instructions": instructions, "max_depth": max_depth, "max_breadth": 40, "limit": limit,
            "select_domains": list(select_domains), "allow_external": False, "extract_depth": "basic",
            "format": "markdown", "chunks_per_source": 3, "timeout": timeout, "include_usage": True}
    if select_paths:
        body["select_paths"] = list(select_paths)
    return _post(CRAWL_API, body, env, timeout)


def extract(urls, *, env: dict | None = None, timeout: float = 60) -> dict:
    env = os.environ if env is None else env
    body = {"urls": list(urls), "extract_depth": "basic", "format": "markdown", "include_usage": True,
            "timeout": timeout}
    return _post(EXTRACT_API, body, env, timeout)


# ---------------------------------------------------------------- scope
def split_repo(repo: str):
    parts = [p for p in (repo or "").strip().strip("/").split("/") if p]
    if len(parts) != 2 or not all(re.fullmatch(r"[A-Za-z0-9_.-]+", p) for p in parts):
        return None
    return parts[0], parts[1]


def docs_host(checkout) -> str:
    """The project's own documentation host from its packaging metadata, or "". Only a link labelled as docs
    (or a Read the Docs host) counts, and code hosts and package indexes never do."""
    root = Path(checkout) if checkout else None
    if root is None or not root.is_dir():
        return ""
    labelled: list[tuple[str, str]] = []
    py = root / "pyproject.toml"
    if py.is_file():
        try:
            import tomllib
            data = tomllib.loads(py.read_text(encoding="utf-8", errors="replace"))
        except Exception:  # noqa: BLE001
            data = {}
        urls = ((data.get("project") or {}).get("urls") or {}) if isinstance(data.get("project"), dict) else {}
        if isinstance(urls, dict):
            labelled.extend((str(k), str(v)) for k, v in urls.items() if isinstance(v, str))
        poetry = ((data.get("tool") or {}).get("poetry") or {}) if isinstance(data.get("tool"), dict) else {}
        if isinstance(poetry, dict) and isinstance(poetry.get("documentation"), str):
            labelled.append(("documentation", poetry["documentation"]))
    cfg = root / "setup.cfg"
    if cfg.is_file():
        import configparser
        parser = configparser.ConfigParser()
        try:
            parser.read_string(cfg.read_text(encoding="utf-8", errors="replace"))
            if parser.has_option("metadata", "project_urls"):
                for line in parser.get("metadata", "project_urls").splitlines():
                    if "=" in line:
                        k, v = line.split("=", 1)
                        labelled.append((k.strip(), v.strip()))
        except (configparser.Error, OSError):
            pass
    for label, url in labelled:
        host = (urlparse(url).hostname or "").lower()
        if not host or any(host == h or host.endswith("." + h) for h in _NOT_DOCS_HOSTS):
            continue
        if "doc" in label.lower() or host.endswith(".readthedocs.io"):
            return host
    return ""


def in_scope(url: str, repo: str, base_sha: str, docs: str = "") -> bool:
    parts = split_repo(repo)
    p = urlparse(url or "")
    host = (p.hostname or "").lower()
    if p.scheme != "https" or not parts:
        return False
    if host == "github.com":
        owner, name = parts
        path = p.path.lower()
        prefix = f"/{owner}/{name}".lower()
        if not (path == prefix or path.startswith(prefix + "/")):
            return False
        if "/tree/" in path or "/blob/" in path:
            return bool(base_sha) and re.match(rf"{re.escape(prefix)}/(tree|blob)/{re.escape(base_sha.lower())}(/|$)",
                                               path) is not None
        return True
    return bool(docs) and host == docs


def seeds(repo: str, base_sha: str, docs: str = "") -> list[dict]:
    owner, name = split_repo(repo)
    out = [{"url": f"https://github.com/{owner}/{name}/tree/{base_sha}",
            "select_domains": [r"^github\.com$"],
            "select_paths": [rf"/{re.escape(owner)}/{re.escape(name)}/(tree|blob)/{re.escape(base_sha)}(/.*)?"]}]
    if docs:
        out.append({"url": f"https://{docs}/", "select_domains": [rf"^{re.escape(docs)}$"], "select_paths": None})
    return out


def local_key_urls(repo: str, base_sha: str, checkout) -> list[str]:
    """Blob URLs, at the base commit, for the setup files the checkout really has, so Extract always reads them."""
    owner, name = split_repo(repo)
    root = Path(checkout) if checkout else None
    if root is None or not root.is_dir():
        return []
    rels = [rel for rel in _LOCAL_FILES if (root / rel).is_file()]
    wf = root / ".github" / "workflows"
    if wf.is_dir():
        rels.extend(sorted(str(p.relative_to(root)) for p in wf.iterdir()
                           if p.suffix in (".yml", ".yaml") and re.search(r"(?i)test|ci|main|python|build", p.name)))
    return [f"https://github.com/{owner}/{name}/blob/{base_sha}/{rel}" for rel in rels]


# ---------------------------------------------------------------- steps
_PIP = r"(?:python3?\s+-m\s+)?(?:uv\s+)?pip3?\s+install"
_EXTRAS = re.compile(_PIP + r"[^\n`]*?(?:-e\s+|--editable[ =])?[\"']?\.\[([A-Za-z0-9_,\- ]+)\][\"']?")
_REQFILE = re.compile(_PIP + r"[^\n`]*?(?:-r|--requirement)[ =][\"']?([\w./\-]+\.(?:txt|in))")
_GROUP = re.compile(r"(?:" + _PIP + r"|uv\s+sync)[^\n`]*?--(?:group|only-group)[ =][\"']?([A-Za-z0-9_.\-]+)")
_UV_EXTRA = re.compile(r"uv\s+sync[^\n`]*?--extra[ =][\"']?([A-Za-z0-9_.\-]+)")
_PKG_LINE = re.compile(_PIP + r"\s+([^\n`|&;]+)")
_PYVER = re.compile(r"python-version[\"']?\s*:\s*\[?([^\]\n]+)")
_PYTEST_CFG = re.compile(r"(?i)\[(tool\.pytest\.ini_options|pytest|tool:pytest)\]")


def parse_steps(text: str, url: str) -> list[dict]:
    """Setup steps written in one page. Each step names the URL it came from."""
    steps: list[dict] = []

    def add(kind, value):
        value = str(value).strip().strip("'\"")
        if value and not any(s["kind"] == kind and s["value"] == value for s in steps):
            steps.append({"kind": kind, "value": value, "source": url})

    text = text or ""
    for m in _EXTRAS.finditer(text):
        for extra in m.group(1).split(","):
            add("extra", extra.strip())
    for m in _UV_EXTRA.finditer(text):
        add("extra", m.group(1))
    for m in _REQFILE.finditer(text):
        add("requirements_file", m.group(1).lstrip("./") if m.group(1).startswith("./") else m.group(1))
    for m in _GROUP.finditer(text):
        add("group", m.group(1))
    for m in _PKG_LINE.finditer(text):
        for tok in shlex.split(m.group(1), posix=True) if _balanced(m.group(1)) else []:
            if tok.startswith("-") or "/" in tok or ":" in tok or tok.startswith(".") or "[" in tok and tok.startswith("."):
                continue
            if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.\-]*(\[[A-Za-z0-9_,\-]+\])?([<>=!~]=?[\w.*]+)?", tok):
                add("package", tok)
    for m in _PYVER.finditer(text):
        for v in re.findall(r"\b3\.\d{1,2}\b", m.group(1)):
            add("python", v)
    if _PYTEST_CFG.search(text):
        add("pytest_config", "pytest settings section")
    return steps


def _balanced(s: str) -> bool:
    try:
        shlex.split(s)
        return True
    except ValueError:
        return False


def _checkout_facts(checkout) -> dict:
    root = Path(checkout) if checkout else None
    facts = {"extras": set(), "groups": set(), "files": set(), "declared": set(), "self": ""}
    if root is None or not root.is_dir():
        return facts
    py = root / "pyproject.toml"
    if py.is_file():
        try:
            import tomllib
            data = tomllib.loads(py.read_text(encoding="utf-8", errors="replace"))
        except Exception:  # noqa: BLE001
            data = {}
        proj = data.get("project") if isinstance(data.get("project"), dict) else {}
        facts["self"] = _norm(str(proj.get("name") or ""))
        facts["extras"].update(_norm(k) for k in (proj.get("optional-dependencies") or {}))
        groups = data.get("dependency-groups") if isinstance(data.get("dependency-groups"), dict) else {}
        facts["groups"].update(groups)
        for req in proj.get("dependencies") or []:
            facts["declared"].add(_req_name(req))
        for reqs in (proj.get("optional-dependencies") or {}).values():
            facts["declared"].update(_req_name(r) for r in reqs or [] if isinstance(r, str))
        for reqs in groups.values():
            facts["declared"].update(_req_name(r) for r in reqs or [] if isinstance(r, str))
    cfg = root / "setup.cfg"
    if cfg.is_file():
        import configparser
        parser = configparser.ConfigParser()
        try:
            parser.read_string(cfg.read_text(encoding="utf-8", errors="replace"))
            if parser.has_section("options.extras_require"):
                for key in parser.options("options.extras_require"):
                    facts["extras"].add(_norm(key))
                    facts["declared"].update(_req_name(line) for line in
                                             parser.get("options.extras_require", key).splitlines() if line.strip())
            if parser.has_option("metadata", "name"):
                facts["self"] = facts["self"] or _norm(parser.get("metadata", "name"))
        except (configparser.Error, OSError):
            pass
    for path in list(root.glob("*requirements*.txt")) + list(root.glob("requirements/*.txt")) + \
            list(root.glob("*/requirements*.txt")):
        rel = str(path.relative_to(root))
        facts["files"].add(rel)
        try:
            for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
                line = line.split("#", 1)[0].strip()
                if line and not line.startswith("-"):
                    facts["declared"].add(_req_name(line))
        except OSError:
            pass
    facts["declared"].discard("")
    return facts


def _norm(name: str) -> str:
    return re.sub(r"[-_.]+", "-", (name or "").strip()).lower()


def _req_name(req: str) -> str:
    m = re.match(r"\s*([A-Za-z0-9][A-Za-z0-9_.\-]*)", req or "")
    return _norm(m.group(1)) if m else ""


def merge_steps(steps: list[dict], checkout) -> list[dict]:
    """Keep a crawled step only when the project's own files back it. Each step gets ``used`` and ``why``."""
    facts = _checkout_facts(checkout)
    out = []
    for step in steps:
        kind, value = step["kind"], step["value"]
        row = dict(step)
        if kind == "extra":
            ok = _norm(value) in facts["extras"]
            row["used"], row["why"] = ok, ("extra declared by the project" if ok
                                          else "not an extra the project's files declare")
        elif kind == "group":
            ok = value in facts["groups"]
            row["used"], row["why"] = ok, ("dependency group declared by the project" if ok
                                          else "not a dependency group the project's files declare")
        elif kind == "requirements_file":
            ok = value in facts["files"] or (Path(checkout) / value).is_file() if checkout else False
            safe = ok and ".." not in value and not value.startswith("/")
            row["used"], row["why"] = bool(safe), ("requirements file present in the repository" if safe
                                                   else "file not present in the repository at the base commit")
        elif kind == "package":
            name = _req_name(value)
            if name and name == facts["self"]:
                row["used"], row["why"] = False, "the project itself; the checkout is installed instead"
            else:
                ok = bool(name) and name in facts["declared"]
                row["used"], row["why"] = ok, ("package the project itself declares" if ok
                                              else "not declared in the project's own files, so not installed")
        else:
            row["used"], row["why"] = False, "recorded for the setup plan; not an install step"
        out.append(row)
    return out


def steps_shell(rows: list[dict]) -> str:
    """Install lines for the kept steps. A failed line is reported and does not stop the install."""
    lines = []
    extras = [r["value"] for r in rows if r.get("used") and r["kind"] == "extra"]
    if extras:
        spec = ".[" + ",".join(dict.fromkeys(extras)) + "]"
        lines.append(f"python -m pip install -q -e {shlex.quote(spec)} || echo 'crawled step failed: {spec}'")
    for r in rows:
        if not r.get("used"):
            continue
        if r["kind"] == "group":
            lines.append(f"python -m pip install -q --group {shlex.quote(r['value'])} "
                         f"|| echo 'crawled step failed: group {r['value']}'")
        elif r["kind"] == "requirements_file":
            lines.append(f"python -m pip install -q -r {shlex.quote(r['value'])} "
                         f"|| echo 'crawled step failed: {r['value']}'")
    pkgs = [r["value"] for r in rows if r.get("used") and r["kind"] == "package"]
    if pkgs:
        lines.append("python -m pip install -q " + " ".join(shlex.quote(p) for p in dict.fromkeys(pkgs))
                     + " || echo 'crawled step failed: packages'")
    return "\n".join(lines)


def _credits(payload: dict) -> float:
    usage = payload.get("usage") if isinstance(payload, dict) else None
    try:
        return float((usage or {}).get("credits") or 0)
    except (TypeError, ValueError):
        return 0.0


def cache_dir(env: dict | None = None) -> Path:
    env = os.environ if env is None else env
    raw = str(env.get(CACHE_ENV) or "").strip()
    return Path(raw) if raw else Path.home() / ".cache" / "proof-of-change" / "tavily-crawl"


def _cache_path(root: Path, repo: str, base_sha: str, docs: str) -> Path:
    import hashlib
    key = f"{repo.lower()}@{base_sha.lower()}|{docs}"
    return Path(root) / (hashlib.sha256(key.encode()).hexdigest()[:32] + ".json")


def _cache_read(path: Path, now: float, ttl: float):
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict) or now - float(data.get("saved_at") or 0) > ttl:
        return None
    return data


def _cache_write(path: Path, data: dict) -> bool:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data))
        tmp.replace(path)
        return True
    except OSError:
        return False


def crawl_repo(repo: str, base_sha: str, checkout, env: dict | None = None, crawl_fn=None, extract_fn=None,
               cache_root=None, ttl: float = CACHE_TTL, now: float | None = None) -> dict:
    """Crawl, extract and merge. ``stop`` is true (with ``stop_reason`` starting "Tavily unavailable") when the key
    is missing or every Tavily call failed. The returned block holds no page text, only URLs, steps and counts."""
    env = os.environ if env is None else env
    block = {"ok": False, "stop": False, "stop_reason": "", "base_sha": base_sha, "docs_domain": "", "seeds": [],
             "pages_crawled": [], "pages_extracted": [], "steps": [], "shell": "", "calls": 0, "credits": 0.0,
             "errors": [], "context": "", "cache": {"hit": False, "key": "", "saved": False}}
    if not available(env):
        block.update(stop=True, stop_reason=f"{UNAVAILABLE}: {KEY_ENV} is not set")
        return block
    if not split_repo(repo) or not re.fullmatch(r"[0-9a-fA-F]{7,40}", base_sha or ""):
        block.update(stop=True, stop_reason=f"{UNAVAILABLE}: the repository or base commit could not be read")
        return block
    import time
    now = time.time() if now is None else now
    docs = docs_host(checkout)
    root = cache_dir(env) if cache_root is None else Path(cache_root)
    cpath = _cache_path(root, repo, base_sha, docs)
    block["cache"]["key"] = f"{repo}@{base_sha}"
    hit = _cache_read(cpath, now, ttl)
    if hit is not None:
        # Same project version: the same pages give the same steps, with no Tavily call and no credits.
        block.update(docs_domain=docs, seeds=list(hit.get("seeds") or []))
        block["cache"]["hit"] = True
        block["cache"]["age_seconds"] = int(now - float(hit.get("saved_at") or now))
        return _finish(block, dict(hit.get("pages") or {}), dict(hit.get("full") or {}), checkout)
    crawl_fn = crawl_fn or (lambda url, **kw: crawl(url, env=env, **kw))
    extract_fn = extract_fn or (lambda urls: extract(urls, env=env))
    block["docs_domain"] = docs
    pages: dict[str, str] = {}
    any_ok = False
    for seed in seeds(repo, base_sha, docs):
        block["seeds"].append(seed["url"])
        got = crawl_fn(seed["url"], select_domains=seed["select_domains"], select_paths=seed["select_paths"])
        block["calls"] += 1
        got = got if isinstance(got, dict) else {"ok": False, "error": "no response"}
        block["credits"] += _credits(got)
        if got.get("ok") is False or got.get("error"):
            block["errors"].append(f"crawl {seed['url']}: {got.get('error') or 'failed'}")
            continue
        any_ok = True
        for item in got.get("results") or []:
            url = str((item or {}).get("url") or "")
            if in_scope(url, repo, base_sha, docs) and url not in pages:
                pages[url] = str(item.get("raw_content") or "")
    block["pages_crawled"] = list(pages)
    key = [u for u in pages if _KEY_PAGE.search(urlparse(u).path)]
    for u in local_key_urls(repo, base_sha, checkout):
        if u not in key:
            key.append(u)
    key = [u for u in key if in_scope(u, repo, base_sha, docs)][:EXTRACT_MAX]
    full: dict[str, str] = {}
    if key:
        got = extract_fn(key)
        block["calls"] += 1
        got = got if isinstance(got, dict) else {"ok": False, "error": "no response"}
        block["credits"] += _credits(got)
        if got.get("ok") is False or got.get("error"):
            block["errors"].append(f"extract: {got.get('error') or 'failed'}")
        else:
            any_ok = True
            for item in got.get("results") or []:
                url = str((item or {}).get("url") or "")
                if in_scope(url, repo, base_sha, docs):
                    full[url] = str(item.get("raw_content") or "")
    block["pages_extracted"] = list(full)
    if not any_ok:
        why = block["errors"][0] if block["errors"] else "no call succeeded"
        block.update(stop=True, stop_reason=f"{UNAVAILABLE}: {why}")
        return block
    block["cache"]["saved"] = _cache_write(cpath, {"saved_at": now, "repo": repo, "base_sha": base_sha,
                                                   "seeds": block["seeds"], "pages": pages, "full": full})
    return _finish(block, pages, full, checkout)


def _finish(block: dict, pages: dict, full: dict, checkout) -> dict:
    block["pages_crawled"] = list(pages)
    block["pages_extracted"] = list(full)
    steps: list[dict] = []
    for url, text in list(full.items()) + [(u, t) for u, t in pages.items() if u not in full]:
        for step in parse_steps(text, url):
            if not any(s["kind"] == step["kind"] and s["value"] == step["value"] for s in steps):
                steps.append(step)
    rows = merge_steps(steps, checkout)
    block["steps"] = rows
    block["shell"] = steps_shell(rows)
    ctx = []
    for row in rows:
        ctx.append(f"{row['kind']}: {row['value']} ({'used' if row['used'] else 'not used'}; {row['source']})")
    block["context"] = "\n".join(ctx)[:4000]
    block["ok"] = True
    return block
