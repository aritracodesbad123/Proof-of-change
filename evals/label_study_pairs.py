"""Label each main-study pair by the written library rule.

The rule is evals/study_pairs/library_label_rule.md. This program only reads
https://pypi.org/pypi/<name>/json. It does not change the ordered pair list.
"""
from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ATTEMPTS = 4  # the first request, plus 3 retries
TIMEOUT = 20
UNREACHABLE = {429} | set(range(500, 600))


def split_repo(repo: str) -> tuple[str, str] | None:
    """owner/name with exactly one slash. Anything else is not looked up."""
    owner, slash, name = repo.partition("/")
    if not slash or not owner or not name or "/" in name or " " in repo:
        return None
    return owner, name


def link_matches(value: str, owner: str, name: str) -> bool:
    """True when value contains github.com/owner/name, ignoring case and a trailing .git or slash."""
    text = value.lower()
    needle = f"github.com/{owner.lower()}/{name.lower()}"
    start = 0
    while True:
        found = text.find(needle, start)
        if found < 0:
            return False
        rest = text[found + len(needle):]
        if rest.startswith(".git"):
            rest = rest[4:]
        if rest == "" or rest[0] in "/?#":
            return True
        start = found + 1


def _links(info: dict) -> list[str]:
    found = []
    home = info.get("home_page")
    if isinstance(home, str):
        found.append(home)
    urls = info.get("project_urls")
    if isinstance(urls, dict):
        found.extend(value for value in urls.values() if isinstance(value, str))
    return found


def judge(status: int, body: bytes, owner: str, name: str) -> str | None:
    """A label, or None when this attempt could not reach the index."""
    if status in UNREACHABLE:
        return None
    if status != 200:
        return "non_library"
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return None
    info = data.get("info") if isinstance(data, dict) else None
    if not isinstance(info, dict):
        return "non_library"
    if any(link_matches(value, owner, name) for value in _links(info)):
        return "library"
    return "non_library"


def default_fetch(name: str) -> tuple[int, bytes]:
    """One public read of the package index. Raises if the connection fails."""
    url = "https://pypi.org/pypi/" + urllib.parse.quote(name) + "/json"
    req = urllib.request.Request(url, headers={"Accept": "application/json",
                                               "User-Agent": "proof-of-change-study-labels"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()


def label_name(owner: str, name: str, fetch=default_fetch, sleep=time.sleep) -> str:
    """library, non_library, or unknown after the first request and 3 retries."""
    for attempt in range(ATTEMPTS):
        try:
            status, body = fetch(name)
            verdict = judge(status, body, owner, name)
        except (urllib.error.URLError, OSError):
            verdict = None
        if verdict is not None:
            return verdict
        if attempt + 1 < ATTEMPTS:
            sleep(min(8, 2 ** attempt))
    return "unknown"


def label_pairs(pairs: list[dict], fetch=default_fetch, sleep=time.sleep) -> list[dict]:
    """One entry per pair, in the same order. Each repository is looked up once."""
    cache: dict[str, str] = {}
    labelled = []
    for pair in pairs:
        repo = pair["repo"]
        if repo not in cache:
            parts = split_repo(repo)
            cache[repo] = "non_library" if parts is None else label_name(parts[0], parts[1], fetch, sleep)
        labelled.append({"repo": repo, "agent_pr": pair["agent_pr"], "human_pr": pair["human_pr"],
                         "label": cache[repo]})
    return labelled


def counts(labelled: list[dict]) -> dict[str, int]:
    tally = {"library": 0, "non_library": 0, "unknown": 0}
    for item in labelled:
        tally[item["label"]] = tally.get(item["label"], 0) + 1
    return tally


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Label main-study pairs from the written library rule.")
    ap.add_argument("--pairs", required=True, type=Path, help="ordered pair list JSON (read only)")
    ap.add_argument("--rule", required=True, type=Path, help="the written rule; it must already exist")
    ap.add_argument("--out", required=True, type=Path, help="where to write repo, agent_pr, human_pr, and label")
    a = ap.parse_args(argv)
    if not a.rule.is_file():
        print(f"missing rule file: {a.rule}", flush=True)
        return 2
    pairs = json.loads(a.pairs.read_text())
    labelled = label_pairs(pairs, default_fetch)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(labelled, indent=2) + "\n")
    tally = counts(labelled)
    print(f"labelled {len(labelled)}: library {tally.get('library', 0)}, "
          f"non_library {tally.get('non_library', 0)}, unknown {tally.get('unknown', 0)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
