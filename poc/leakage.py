"""Answer-key firewall: refuse a prompt bundle that could leak the benchmark's ground truth or the PR head.

A prompt bundle is everything a probe or claim generator is about to see:

    bundle = {
        "pr": "owner/repo#123",                 # optional: the PR the bundle is for (its own URL/number are allowed)
        "text": {"title": "...", "body": "...", "instructions": "..."},   # free text, any keys (PR text,
                                                                         # release notes, ...)
        "files": {"pkg/mod.py": "<content>"},  # source files, relative paths
    }

Nothing here assumes a PR merge commit or a particular benchmark: "base" means the OLD side (merge first parent,
base branch, or an old release) and "PR side" the NEW side (merge commit, PR head, or a new release); `answers` is
any answer-key CSV.

`check_bundle(bundle, answers, base_files=..., pr_files=..., base_root=...)` raises `LeakageError` when:

* any text or file contains a URL from the answer key (normalised: scheme, `www.`, case and trailing `/` ignored);
* any text or file contains an issue or PR reference from the answer key (`owner/repo#N`, `repo#N`, `issues/N`,
  `pull/N`, and `#N` / `GH-N` when the bundle's PR is in the same repository);
* any text or file contains a phrase from the answer key: any run of 5 words from its free-text columns that has at
  least 3 non-trivial words, or any quoted string of 3+ words (case and punctuation ignored). A file whose content
  is byte-identical to the base tree (base_root given) is exempt from the PHRASE rule only: it existed before the
  PR, so a match there is the library's own text, not a leak. URLs and references are still checked;
* the bundle has any key other than "pr", "text" and "files" (an unknown key could carry text past the checks);
  nested values under "text" are scanned string by string;
* a file in the bundle exists only on the new side (in pr_files but not in base_files), or is missing from the old
  (base) tree when base_root is given.

Limit: matching is EXACT (after normalising case, punctuation and spacing). A paraphrase of the answer ("the adapter
no longer calls the overridable method" for "stopped calling the public, overridable get_connection()") is not
caught. The firewall is a backstop; the real protection is that generator inputs are built only from PR text (or
release notes trimmed to their own version) and old-side code, never from anything written after the change.

The answer key is read only to build `Fingerprints`: SHA-256 hashes of the normalised terms. The plain text is not
kept, not returned and never printed; a refusal names the rule, the bundle part and a short hash, not the term.
`python -m poc.leakage fingerprint <answers.csv> --out fp.json` writes the hashes so a generator host can check
bundles without ever holding the answer key.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

SHINGLE = 5
MIN_CONTENT_WORDS = 3
SKIP_COLUMNS = ("id", "label")   # a case ID such as B01 and a label such as 'regression' are not secrets
STOP = frozenset("""a an and are as at be been but by can could did do does for from had has have if in into is it its
of on or so such than that the their then there these this those to was were will with would not no""".split())
URL_RE = re.compile(r"https?://[^\s<>\"'`;,)\]]+", re.I)
GH_REF_RE = re.compile(r"github\.com/([\w.-]+)/([\w.-]+)/(?:issues|pull|pulls)/(\d+)", re.I)
REF_FORMS_RE = re.compile(r"(?<![\w/.-])(?:([\w.-]+)/)?([\w.-]+)#(\d+)\b|\b(issues|pulls?)/(\d+)\b|(?<![\w#])(?:#|gh-)(\d+)\b",
                          re.I)
QUOTE_RE = re.compile(r"'([^']{8,})'|\"([^\"]{8,})\"|`([^`]{8,})`")
WORD_RE = re.compile(r"[a-z0-9_]+")


class LeakageError(ValueError):
    """The bundle may leak the answer key or the PR head; it must not be sent to a generator."""


def _h(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


def norm_url(u: str) -> str:
    u = re.sub(r"^https?://", "", u.strip().lower())
    u = re.sub(r"^www\.", "", u)
    return u.rstrip("/.#")


def words(text: str) -> list[str]:
    return WORD_RE.findall((text or "").lower())


def shingles(ws: list[str], n: int = SHINGLE) -> set[str]:
    return {" ".join(ws[i:i + n]) for i in range(len(ws) - n + 1)
            if sum(w not in STOP for w in ws[i:i + n]) >= MIN_CONTENT_WORDS}


@dataclass
class Fingerprints:
    urls: set[str] = field(default_factory=set)
    refs: set[str] = field(default_factory=set)      # "owner/repo#n", "repo#n", "issues/n@owner/repo", ...
    phrases: set[str] = field(default_factory=set)   # 5-word shingles and whole quoted strings
    quote_lengths: set[int] = field(default_factory=set)
    source: str = ""

    def to_json(self) -> dict:
        return {"kind": "answer-key fingerprints (sha256 of normalised terms)", "shingle": SHINGLE,
                "source": self.source, "urls": sorted(self.urls), "refs": sorted(self.refs),
                "phrases": sorted(self.phrases), "quote_lengths": sorted(self.quote_lengths)}

    @classmethod
    def from_json(cls, d: dict) -> Fingerprints:
        return cls(set(d["urls"]), set(d["refs"]), set(d["phrases"]), set(d.get("quote_lengths", [])),
                   d.get("source", ""))


def _ref_keys(owner: str, repo: str, n: str) -> list[str]:
    o, r = owner.lower(), repo.lower()
    return [f"{o}/{r}#{n}", f"{r}#{n}", f"issues/{n}@{o}/{r}", f"pull/{n}@{o}/{r}", f"#{n}@{o}/{r}"]


def fingerprints(answers_csv: str | Path, skip_columns: tuple[str, ...] = SKIP_COLUMNS) -> Fingerprints:
    """Hash every URL, issue/PR reference and phrase of any answer-key CSV (benchmark, release pairs, ...). Every
    column is read except skip_columns (by default the case ID and label columns)."""
    fp = Fingerprints(source=Path(answers_csv).name)
    with open(answers_csv, newline="") as fh:
        for row in csv.DictReader(fh):
            for col, val in row.items():
                if col is None or col in skip_columns or not val:
                    continue
                for u in URL_RE.findall(val):
                    fp.urls.add(_h(norm_url(u)))
                    m = GH_REF_RE.search(u)
                    if m:
                        fp.refs.update(_h(k) for k in _ref_keys(*m.groups()))
                fp.phrases.update(_h(s) for s in shingles(words(URL_RE.sub(" ", val))))
                for q in QUOTE_RE.findall(val):
                    qw = words(next(x for x in q if x))
                    if len(qw) >= 3:
                        fp.phrases.add(_h(" ".join(qw)))
                        fp.quote_lengths.add(len(qw))
    return fp


def _own(pr: str | None) -> tuple[str, str, str] | None:
    m = re.match(r"^([\w.-]+)/([\w.-]+)#(\d+)$", pr or "")
    return (m.group(1).lower(), m.group(2).lower(), m.group(3)) if m else None


def _ref_candidates(text: str, own: tuple | None) -> list[str]:
    out = []
    for m in REF_FORMS_RE.finditer(text):
        owner, repo, n, kind, kn, bare = m.groups()
        if n:
            out.append(f"{owner.lower()}/{repo.lower()}#{n}" if owner else f"{repo.lower()}#{n}")
        elif kn and own:
            out.append(f"{'issues' if kind.lower() == 'issues' else 'pull'}/{kn}@{own[0]}/{own[1]}")
        elif bare and own:
            out.append(f"#{bare}@{own[0]}/{own[1]}")
    for m in GH_REF_RE.finditer(text):
        out += _ref_keys(*m.groups())[:1]
    return out


def _own_keys(own: tuple | None) -> set[str]:
    if not own:
        return set()
    o, r, n = own
    return {_h(k) for k in _ref_keys(o, r, n)} | {_h(f"github.com/{o}/{r}/pull/{n}")}


def scan_text(part: str, text: str, fp: Fingerprints, own: tuple | None, phrases: bool = True) -> list[str]:
    """Problems found in one bundle part (no answer text in the messages)."""
    allowed = _own_keys(own)
    out = []
    for u in URL_RE.findall(text):
        h = _h(norm_url(u))
        if h in fp.urls and h not in allowed:
            out.append(f"{part}: contains a URL from the answer key (sha {h[:10]})")
    for k in _ref_candidates(text, own):
        h = _h(k)
        if h in fp.refs and h not in allowed:
            out.append(f"{part}: contains an issue/PR reference from the answer key (sha {h[:10]})")
    if phrases:
        ws = words(text)
        hit = {_h(s) for s in shingles(ws)} & fp.phrases
        for n in fp.quote_lengths:
            hit |= {_h(" ".join(ws[i:i + n])) for i in range(len(ws) - n + 1)} & fp.phrases
        if hit:
            out.append(f"{part}: contains {len(hit)} phrase(s) from the answer key (sha {sorted(hit)[0][:10]})")
    return sorted(set(out))


BUNDLE_KEYS = ("pr", "text", "files")


def strings_in(value, where: str):
    """Every string inside value (str, numbers, or nested lists/tuples/dicts, keys included), with its location."""
    if isinstance(value, str):
        yield where, value
    elif isinstance(value, dict):
        for k, v in value.items():
            yield f"{where}.key", str(k)
            yield from strings_in(v, f"{where}[{k}]")
    elif isinstance(value, (list, tuple, set)):
        for i, v in enumerate(value):
            yield from strings_in(v, f"{where}[{i}]")
    elif value is not None:
        yield where, str(value)


def check_bundle(bundle: dict, answers: str | Path | Fingerprints, base_files: set[str] | list[str] | None = None,
                 pr_files: set[str] | list[str] | None = None, base_root: str | Path | None = None) -> dict:
    """Raise LeakageError listing every problem; return {"ok": True, "checked": {...}} for a clean bundle.
    answers: the answer-key CSV path or precomputed Fingerprints. base_files / pr_files: repo-relative paths on each
    side (a bundle file only on the PR side is refused). base_root: the base checkout; bundle files must exist there,
    and those identical to it are exempt from the phrase rule."""
    fp = answers if isinstance(answers, Fingerprints) else fingerprints(answers)
    if not isinstance(bundle, dict):
        raise LeakageError("prompt bundle refused (answer-key firewall): a bundle must be a dict")
    problems: list[str] = [f"{k!r}: unexpected key (allowed: {', '.join(BUNDLE_KEYS)}); nothing may reach a "
                           "generator unchecked" for k in sorted(map(str, set(bundle) - set(BUNDLE_KEYS)))]
    pr = bundle.get("pr")
    if pr is not None and not isinstance(pr, str):
        problems.append("'pr': must be a string such as owner/repo#123")
    own = _own(pr if isinstance(pr, str) else None)
    text = bundle.get("text") or {}
    if not isinstance(text, dict):
        problems.append("'text': must be a dict of named text parts")
        text = {}
    for k, v in sorted(text.items(), key=lambda kv: str(kv[0])):
        for where, piece in strings_in(v, f"text[{k}]"):    # nested lists/dicts: every string is scanned
            problems += scan_text(where, piece, fp, own)
    if not isinstance(bundle.get("files") or {}, dict):
        problems.append("'files': must be a dict of relative path -> content")
        bundle = dict(bundle, files={})
    base_set = set(base_files) if base_files is not None else None
    pr_set = set(pr_files) if pr_files is not None else None
    exempt = []
    for rel, content in sorted((bundle.get("files") or {}).items()):
        if not isinstance(rel, str) or not isinstance(content, str):
            problems.append(f"files[{rel!r}]: path and content must be strings")
            continue
        if ".." in Path(rel).parts or Path(rel).is_absolute():
            problems.append(f"files[{rel}]: path must be repo-relative")
            continue
        if pr_set is not None and rel in pr_set and (base_set is None or rel not in base_set):
            problems.append(f"files[{rel}]: exists only on the PR side")
        same_as_base = False
        if base_root is not None:
            bp = Path(base_root) / rel
            if not bp.is_file():
                problems.append(f"files[{rel}]: not in the base tree")
            else:
                same_as_base = bp.read_text(errors="replace") == content
                if same_as_base:
                    exempt.append(rel)
        problems += scan_text(f"files[{rel}]", content, fp, own, phrases=not same_as_base)
    if problems:
        raise LeakageError("prompt bundle refused (answer-key firewall):\n  " + "\n  ".join(problems))
    return {"ok": True, "checked": {"text_parts": len(bundle.get("text") or {}), "files": len(bundle.get("files") or {}),
                                    "phrase_exempt_base_identical": exempt, "answer_key": fp.source}}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Answer-key firewall")
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("fingerprint", help="hash the answer key's terms into a JSON file")
    f.add_argument("answers")
    f.add_argument("--out", required=True)
    c = sub.add_parser("check", help="check a bundle JSON file against an answer key or fingerprint file")
    c.add_argument("bundle")
    c.add_argument("--answers", help="answer-key CSV")
    c.add_argument("--fingerprints", help="fingerprint JSON from 'fingerprint'")
    a = ap.parse_args(argv)
    if a.cmd == "fingerprint":
        Path(a.out).write_text(json.dumps(fingerprints(a.answers).to_json(), indent=1))
        return 0
    fp = (Fingerprints.from_json(json.loads(Path(a.fingerprints).read_text())) if a.fingerprints else a.answers)
    if fp is None:
        ap.error("give --answers or --fingerprints")
    try:
        print(json.dumps(check_bundle(json.loads(Path(a.bundle).read_text()), fp)))
    except LeakageError as e:
        print(e)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
