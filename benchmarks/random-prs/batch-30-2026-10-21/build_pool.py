"""Build pool of merged Python-library PRs with tests. Read-only GitHub API."""
# ruff: noqa: E402, E501

import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

TOK = os.environ["GITHUB_TOKEN"]
import subprocess


def get(url):
    auth = [] if "/search/" in url else ["-H", "Authorization: Bearer " + TOK]
    for a in range(12):
        p = subprocess.run(
            ["curl", "-s", "-m", "40", "-w", "\n%{http_code}"] + auth + ["-H", "Accept: application/vnd.github+json", url],
            capture_output=True,
            text=True,
        )
        body, _, code = p.stdout.rpartition("\n")
        if code == "200":
            return json.loads(body)
        if code in ("404", "451", "409"):
            return None
        print("http", code, url[:90], file=sys.stderr, flush=True)
        time.sleep(65)
    return None


Q = "is:pr is:merged draft:false language:python merged:{day} -author:app/dependabot -author:app/renovate -author:app/pre-commit-ci  (four date ranges 07-10, 11-13, 14-16, 17-20 Oct 2026, first 1000 each, sorted by updated desc)"
items = []
seen = set()
for day in ("2026-10-07..2026-10-10", "2026-10-11..2026-10-13", "2026-10-14..2026-10-16", "2026-10-17..2026-10-20"):
    print("range", day, len(items), file=sys.stderr, flush=True)
    q = Q.split("  (")[0].replace("{day}", day)
    for page in range(1, 11):
        d = get(
            "https://api.github.com/search/issues?"
            + urllib.parse.urlencode({"q": q, "sort": "updated", "order": "desc", "per_page": 100, "page": page})
        )
        time.sleep(7)
        if not d or not d.get("items"):
            break
        for it in d["items"]:
            if it["html_url"] not in seen:
                seen.add(it["html_url"])
                items.append(it)
print("search", len(items), file=sys.stderr)
repos = {}
pool = []
AUTOMATED = re.compile(r"\[b[o]t\]$|^(dependabot|renovate|pre-commit-ci|github-actions)", re.I)
TEST = re.compile(r"(^|/)(tests?|testing)/|(^|/)test_[^/]*\.py$|_test\.py$|(^|/)conftest\.py$")
for it in items:
    full = it["repository_url"].split("/repos/")[1]
    if AUTOMATED.search(it["user"]["login"]):
        continue
    if full not in repos:
        r = get("https://api.github.com/repos/" + full)
        ok = False
        if (
            r
            and r.get("language") == "Python"
            and r["stargazers_count"] >= 200
            and r["pushed_at"] >= "2026-09-21"
            and not r.get("archived")
        ):
            ok = any(
                get(f"https://api.github.com/repos/{full}/contents/{f}?ref={r['default_branch']}")
                for f in ("pyproject.toml", "setup.py", "setup.cfg")
            )
        repos[full] = (ok, r["stargazers_count"] if r else None)
    if not repos[full][0]:
        continue
    n = it["number"]
    pr = get(f"https://api.github.com/repos/{full}/pulls/{n}")  # br-allow-external: read-only GET of a PR
    if not pr or not pr.get("merged_at") or pr["additions"] + pr["deletions"] > 300:
        continue
    files = get(f"https://api.github.com/repos/{full}/pulls/{n}/files?per_page=100") or []  # br-allow-external: read-only GET of PR files
    names = [f["filename"] for f in files]
    py = [x for x in names if x.endswith(".py")]
    tests = [x for x in py if TEST.search(x)]
    src = [x for x in py if not TEST.search(x)]
    if not tests or not src:
        continue
    pool.append(
        {
            "repo": full,
            "number": n,
            "url": pr["html_url"],
            "title": pr["title"],
            "author": pr["user"]["login"],
            "merged_at": pr["merged_at"],
            "base_sha": pr["base"]["sha"],
            "head_sha": pr["head"]["sha"],
            "merge_commit_sha": pr["merge_commit_sha"],
            "additions": pr["additions"],
            "deletions": pr["deletions"],
            "py_source_files": len(src),
            "py_test_files": len(tests),
            "stars": repos[full][1],
        }
    )
pool.sort(key=lambda p: (p["repo"].lower(), p["number"]))
json.dump(
    {
        "collected": time.strftime("%Y-%m-%d %H:%M IST"),
        "search": Q,
        "search_results": len(items),
        "filters": {
            "repo": "primary language Python, 200+ stars, pushed on/after 2026-09-21, not archived, pyproject.toml/setup.py/setup.cfg on default branch",
            "pr": "merged, author not an automated account, <=300 changed lines, changes >=1 non-test .py file AND >=1 test .py file (tests/, test_*.py, *_test.py, conftest.py)",
        },
        "pool": pool,
    },
    open("pool.json", "w"),
    indent=1,
)
print("pool", len(pool), "repos", len(repos), file=sys.stderr)
