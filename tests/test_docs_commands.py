"""Every command in the README and docs must match the real code: make targets exist, and every
`python -m <module> ...` / `ops/daily_run.py ...` line parses with that module's own argument parser.
(This is what caught `reports.generate ... -o`; `-o` is now an alias of `--out`.)"""
import argparse
import importlib
import importlib.util
import re
import shlex
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
DOCS = [ROOT / "README.md", ROOT / "reports" / "README.md", ROOT / "harness" / "README.md"] + sorted((ROOT / "docs").glob("*.md"))
MODULES = {"reports.generate", "reports.pr_report", "evals.run_evals"}  # harness.run passes unknown flags to br_run.py


def _code_blocks(text: str):
    """Bodies of fenced code blocks tagged bash, sh or untagged (mermaid and others are skipped)."""
    body, lang = None, None
    for line in text.splitlines():
        if line.startswith("```"):
            if body is None:
                body, lang = [], line[3:].strip()
            else:
                if lang in ("", "bash", "sh"):
                    yield "\n".join(body) + "\n"
                body = None
        elif body is not None:
            body.append(line)


def _commands():
    for doc in DOCS:
        if not doc.exists():
            continue
        text = doc.read_text()
        for block in _code_blocks(text):
            for line in block.replace("\\\n", " ").splitlines():
                line = line.strip()
                if line.startswith("$ "):
                    line = line[2:]
                if not line or line.startswith("#"):
                    continue
                if not re.match(r"^(?:[A-Z_]+=\S+\s+)*(?:make\b|\S*python\S*\s)", line):
                    continue  # example output, file trees and other non-commands
                line = re.sub(r"<[^>]*>", "X", line)  # synopsis placeholders such as <record.json | ...>
                toks = [t.strip("[]") for t in shlex.split(line, comments=True) if t not in ("[", "]", "...", "|")]
                toks = [t for t in toks if t]
                while toks and re.match(r"^[A-Z_]+=", toks[0]):  # env assignments
                    toks = toks[1:]
                if toks and (toks[0] == "make" or "python" in toks[0]):
                    yield pytest.param(toks, id=f"{doc.name}: {line[:70]}")
        # inline `make ...` commands in prose and tables too
        for m in re.findall(r"`(make [^`]+)`", text):
            yield pytest.param(shlex.split(m), id=f"{doc.name}: {m[:70]}")


class _Parsed(Exception):
    pass


def _check_args(main, argv, monkeypatch):
    orig = argparse.ArgumentParser.parse_args

    def parse(self, args=None, namespace=None):
        orig(self, args, namespace)  # a bad flag raises SystemExit(2) here
        raise _Parsed

    monkeypatch.setattr(argparse.ArgumentParser, "parse_args", parse)
    with pytest.raises(_Parsed):
        main(argv)


MAKE_TARGETS = set(re.findall(r"^([a-z][\w-]*):", (ROOT / "Makefile").read_text(), re.M))


@pytest.mark.parametrize("toks", list(_commands()))
def test_documented_command_matches_code(toks, monkeypatch):
    if toks[0] == "make":
        # allow chained shells: `make a && make b`
        targets = [t for t in toks[1:] if "=" not in t and not t.startswith("-")
                   and t not in ("&&", "||", ";", "make")]
        assert all(t in MAKE_TARGETS for t in targets), f"unknown make target in {toks}"
        if "check" in targets:
            assert any(t.startswith("PR=") for t in toks) or "<" in " ".join(toks) or len(toks) == 2
        return
    args = toks[1:]
    if args[:1] == ["-m"]:
        mod = args[1]
        if mod not in MODULES:
            pytest.skip(f"{mod}: no argument parser to check")
        _check_args(importlib.import_module(mod).main, args[2:], monkeypatch)
    elif args and args[0].endswith("ops/daily_run.py"):
        spec = importlib.util.spec_from_file_location("daily_run_docs", ROOT / "ops" / "daily_run.py")
        dr = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(dr)
        _check_args(dr.main, args[1:], monkeypatch)
    else:
        pytest.skip("not a project command")


def test_found_commands():
    found = [p.values[0] for p in _commands()]
    assert any(t[:2] == ["make", "check"] for t in found)
    assert any("reports.generate" in t for t in found)


def test_checker_rejects_unknown_flags(monkeypatch):
    from reports import generate
    with pytest.raises(SystemExit):
        _check_args(generate.main, ["x.json", "--output", "d"], monkeypatch)
    _check_args(generate.main, ["x.json", "-o", "d"], monkeypatch)  # -o is an alias of --out
