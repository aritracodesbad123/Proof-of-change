"""Draw the swarm-on share of the pairs a main study will run.

The ordered list is the candidate pool. N is how many pairs the main study will
run, taken from the front of that list. Those pairs are shuffled with seed
20261020, and the first share is the swarm-on group.

Ten pairs are reserved for the swarm. If reserving ten would leave the main
study with fewer than 80 pairs, the swarm group shrinks so the main study stays
at 80. When there are not 80 pairs to begin with, the swarm group is empty.

The written file records the chosen pairs, the seed, and the commit.
"""
from __future__ import annotations

import argparse
import json
import random
import subprocess
import sys
from pathlib import Path

SEED = 20261020
SWARM_RESERVE = 10
MAIN_STUDY_FLOOR = 80


def study_pairs(pairs: list, n: int) -> list:
    """The pairs the main study will run: the first n of the ordered list."""
    if n < 0:
        raise ValueError("n must be zero or more")
    return list(pairs[:n])


def swarm_count(study_n: int) -> int:
    """How many pairs to reserve. Never enough to push the main study below 80."""
    return min(SWARM_RESERVE, max(0, study_n - MAIN_STUDY_FLOOR))


def choose_swarm_pairs(pairs: list, n: int, seed: int = SEED) -> list:
    """Shuffle the main-study pairs and take the swarm-on share."""
    chosen = study_pairs(pairs, n)
    random.Random(seed).shuffle(chosen)
    return chosen[:swarm_count(len(chosen))]


def head_commit() -> str:
    cp = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True)
    return cp.stdout.strip()


def draw(pairs: list, n: int, commit: str, seed: int = SEED) -> dict:
    """The record that is written: chosen pairs, seed, and commit."""
    return {"commit": commit, "pairs": choose_swarm_pairs(pairs, n, seed), "seed": seed}


def load_pairs(path: Path) -> list:
    """A JSON list, or one pair per line. Blank lines and lines starting with # are skipped."""
    text = Path(path).read_text()
    stripped = text.strip()
    if stripped.startswith("["):
        data = json.loads(stripped)
        if not isinstance(data, list):
            raise ValueError("pair list must be a JSON list")
        return data
    return [ln.strip() for ln in text.splitlines() if ln.strip() and not ln.strip().startswith("#")]


def write_draw(pairs: list, n: int, dest: Path, commit: str, seed: int = SEED) -> dict:
    payload = draw(pairs, n, commit, seed)
    Path(dest).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return payload


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Draw the swarm-on pairs for a main study.")
    ap.add_argument("--pairs", required=True, type=Path,
                    help="ordered pair list: a JSON list, or one pair per line")
    ap.add_argument("--n", required=True, type=int,
                    help="how many pairs the main study will run, from the front of the list")
    ap.add_argument("--out", required=True, type=Path,
                    help="where to write the chosen pairs, the seed, and the commit")
    ap.add_argument("--commit", default=None, help="commit to record (default: current HEAD)")
    a = ap.parse_args(argv)
    payload = write_draw(load_pairs(a.pairs), a.n, a.out, a.commit or head_commit())
    print(f"wrote {len(payload['pairs'])} swarm pair(s) to {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
