"""Label each main-study pair by the revised library rule.

The rule is evals/study_pairs/library_label_rule_v2.md. This program only
reads public GitHub and https://pypi.org/pypi/<name>/json. It does not
change the ordered pair list. The first labels file is left as it is.
"""
from __future__ import annotations

import argparse
import configparser
import json
import os
import re
import time
import tomllib
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from evals.label_study_pairs import link_matches, split_repo

TIMEOUT = 20
UNREACHABLE = {429} | set(range(500, 600))
SETUP_NAME = re.compile(r"""(?<![A-Za-z0-9_.])name\s*=\s*(['"])([^'"]+)\1""")
PACKAGING = ("pyproject.toml", "setup.cfg", "setup.py")


class LookupFailed(Exception):
    """A request failed. The caller retries once, then the label is unknown."""


def retry_call(fn, sleep=time.sleep):
    """Run fn. On LookupFailed, try once more, then let that failure through."""
    try:
        return fn()
    except LookupFailed:
        sleep(1)
        return fn()


def names_from_pyproject(text: str) -> list[str]:
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError:
        return []
    project = data.get("project") if isinstance(data, dict) else None
    if isinstance(project, dict) and isinstance(project.get("name"), str) and project["name"].strip():
        return [project["name"].strip()]
    return []


def names_from_setup_cfg(text: str) -> list[str]:
    parser = configparser.RawConfigParser()
    try:
        parser.read_string(text)
    except configparser.Error:
        return []
    section = next((s for s in parser.sections() if s.lower() == "metadata"), None)
    if section is None:
        return []
    for key, value in parser.items(section):
        if key.lower() == "name" and value.strip():
            return [value.strip()]
    return []


def names_from_setup_py(text: str) -> list[str]:
    return [m.group(2).strip() for m in SETUP_NAME.finditer(text) if m.group(2).strip()]


def packaging_paths(paths: list[str]) -> dict[str, list[str]]:
    grouped = {name: [] for name in PACKAGING}
    for path in paths:
        base = path.rsplit("/", 1)[-1]
        if base in grouped:
            grouped[base].append(path)
    for name in PACKAGING:
        grouped[name].sort()
    return grouped


def _info_links(info: dict) -> list[str]:
    found = []
    home = info.get("home_page")
    if isinstance(home, str):
        found.append(home)
    urls = info.get("project_urls")
    if isinstance(urls, dict):
        found.extend(value for value in urls.values() if isinstance(value, str))
    return found


def links_back(info: dict, owner: str, repo: str) -> bool:
    return any(link_matches(value, owner, repo) for value in _info_links(info))


def _request(url: str, token: str | None, accept: str) -> tuple[int, bytes]:
    headers = {"User-Agent": "proof-of-change-study-labels", "Accept": accept}
    if token and "api.github.com" in url:
        headers["Authorization"] = "Bearer " + token
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()
    except (urllib.error.URLError, OSError) as exc:
        raise LookupFailed(str(exc)) from exc


def _json_body(status: int, body: bytes):
    if status in UNREACHABLE or status == 403:
        raise LookupFailed(f"status {status}")
    if status != 200:
        return None
    try:
        return json.loads(body)
    except json.JSONDecodeError as exc:
        raise LookupFailed("not json") from exc


class Index:
    """Public reads. Each method retries once on a network or API error."""

    def __init__(self, token: str | None = None, sleep=time.sleep):
        self.token = token if token is not None else (os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN"))
        self.sleep = sleep

    def repo(self, owner: str, repo: str):
        url = "https://api.github.com/repos/" + urllib.parse.quote(owner) + "/" + urllib.parse.quote(repo)

        def once():
            status, body = _request(url, self.token, "application/vnd.github+json")
            if status == 404:
                return None
            data = _json_body(status, body)
            if not isinstance(data, dict) or not isinstance(data.get("default_branch"), str):
                raise LookupFailed("no default branch")
            return data

        return retry_call(once, self.sleep)

    def tree(self, owner: str, repo: str, branch: str) -> list[str]:
        url = ("https://api.github.com/repos/" + urllib.parse.quote(owner) + "/" + urllib.parse.quote(repo)
               + "/git/trees/" + urllib.parse.quote(branch, safe="") + "?recursive=1")

        def once():
            status, body = _request(url, self.token, "application/vnd.github+json")
            data = _json_body(status, body)
            if not isinstance(data, dict) or not isinstance(data.get("tree"), list) or data.get("truncated"):
                raise LookupFailed("tree")
            return [item["path"] for item in data["tree"] if isinstance(item, dict) and isinstance(item.get("path"), str)]

        return retry_call(once, self.sleep)

    def file(self, owner: str, repo: str, branch: str, path: str) -> str:
        segments = "/".join(urllib.parse.quote(part, safe="") for part in path.split("/"))
        url = ("https://raw.githubusercontent.com/" + urllib.parse.quote(owner) + "/" + urllib.parse.quote(repo)
               + "/" + urllib.parse.quote(branch, safe="") + "/" + segments)

        def once():
            status, body = _request(url, None, "text/plain")
            if status != 200:
                raise LookupFailed(f"file {status}")
            return body.decode("utf-8", "replace")

        return retry_call(once, self.sleep)

    def pypi(self, name: str):
        url = "https://pypi.org/pypi/" + urllib.parse.quote(name, safe="") + "/json"

        def once():
            status, body = _request(url, None, "application/json")
            if status == 404:
                return None
            data = _json_body(status, body)
            if not isinstance(data, dict):
                return None
            info = data.get("info")
            return info if isinstance(info, dict) else {}

        return retry_call(once, self.sleep)


def candidates_from(owner: str, repo: str, index: Index) -> list[tuple[str, str]]:
    """Declared distribution names, then the repository name. Each name once."""
    found: list[tuple[str, str]] = []
    seen: set[str] = set()

    def add(name: str, how: str) -> None:
        name = name.strip()
        if not name or name in seen:
            return
        seen.add(name)
        found.append((name, how))

    meta = index.repo(owner, repo)
    if meta is not None:
        branch = meta["default_branch"]
        grouped = packaging_paths(index.tree(owner, repo, branch))
        readers = (("pyproject.toml", names_from_pyproject), ("setup.cfg", names_from_setup_cfg),
                   ("setup.py", names_from_setup_py))
        for filename, reader in readers:
            for path in grouped[filename]:
                for name in reader(index.file(owner, repo, branch, path)):
                    add(name, filename)
    add(repo, "repo_name")
    return found


def label_repo(owner: str, repo: str, index: Index) -> dict:
    try:
        candidates = candidates_from(owner, repo, index)
        for name, how in candidates:
            info = index.pypi(name)
            if info is not None and links_back(info, owner, repo):
                return {"label": "library", "pypi_project": name, "found_by": how}
    except LookupFailed:
        return {"label": "unknown", "pypi_project": None, "found_by": None}
    return {"label": "non_library", "pypi_project": None, "found_by": None}


def label_pairs(pairs: list[dict], index: Index, only: set[str] | None = None) -> list[dict]:
    cache: dict[str, dict] = {}
    labelled = []
    for pair in pairs:
        if only is not None and pair["repo"] not in only:
            continue
        repo = pair["repo"]
        if repo not in cache:
            parts = split_repo(repo)
            if parts is None:
                cache[repo] = {"label": "non_library", "pypi_project": None, "found_by": None}
            else:
                cache[repo] = label_repo(parts[0], parts[1], index)
            print(f"{repo}: {cache[repo]['label']} {cache[repo]['pypi_project'] or ''} {cache[repo]['found_by'] or ''}",
                  flush=True)
        hit = cache[repo]
        labelled.append({"repo": repo, "agent_pr": pair["agent_pr"], "human_pr": pair["human_pr"],
                         "label": hit["label"], "pypi_project": hit["pypi_project"], "found_by": hit["found_by"]})
    return labelled


def counts(labelled: list[dict]) -> dict[str, int]:
    tally = {"library": 0, "non_library": 0, "unknown": 0}
    for item in labelled:
        tally[item["label"]] = tally.get(item["label"], 0) + 1
    return tally


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Label main-study pairs from the revised library rule.")
    ap.add_argument("--pairs", required=True, type=Path, help="ordered pair list JSON (read only)")
    ap.add_argument("--rule", required=True, type=Path, help="the revised rule; it must already exist")
    ap.add_argument("--out", required=True, type=Path, help="where to write the revised labels")
    ap.add_argument("--only", action="append", default=None, help="label only this owner/name (repeatable)")
    a = ap.parse_args(argv)
    if not a.rule.is_file():
        print(f"missing rule file: {a.rule}", flush=True)
        return 2
    pairs = json.loads(a.pairs.read_text())
    labelled = label_pairs(pairs, Index(), set(a.only) if a.only else None)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(labelled, indent=2) + "\n")
    tally = counts(labelled)
    unknowns = [item["repo"] for item in labelled if item["label"] == "unknown"]
    print(f"labelled {len(labelled)}: library {tally.get('library', 0)}, "
          f"non_library {tally.get('non_library', 0)}, unknown {tally.get('unknown', 0)}")
    for repo in unknowns:
        print(f"unknown: {repo}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
