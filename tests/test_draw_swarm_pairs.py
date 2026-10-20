"""The swarm-on draw is fixed: the same list, N, and seed always give the same pairs."""
import json
import subprocess
import sys
from pathlib import Path

from evals.draw_swarm_pairs import SEED, choose_swarm_pairs, draw, swarm_count, write_draw

ROOT = Path(__file__).resolve().parent.parent


def _pairs(k=120):
    return [f"pair-{i:03d}" for i in range(k)]


def test_reserve_shrinks_so_the_main_study_stays_at_80():
    assert swarm_count(100) == 10
    assert swarm_count(90) == 10
    assert swarm_count(85) == 5
    assert swarm_count(80) == 0
    assert swarm_count(70) == 0
    assert len(choose_swarm_pairs(_pairs(), 100)) == 10
    assert len(choose_swarm_pairs(_pairs(), 85)) == 5
    assert choose_swarm_pairs(_pairs(), 80) == []


def test_only_the_pairs_the_main_study_will_run_are_drawn():
    pool = _pairs()
    chosen = choose_swarm_pairs(pool, 90)
    assert set(chosen) <= set(pool[:90])
    assert not (set(chosen) & set(pool[90:]))
    assert chosen != pool[:10]


def test_running_twice_gives_the_same_result(tmp_path):
    pool = _pairs()
    assert draw(pool, 100, "abc") == draw(pool, 100, "abc")
    assert choose_swarm_pairs(pool, 100) == choose_swarm_pairs(pool, 100)
    src = tmp_path / "pairs.txt"
    src.write_text("\n".join(pool) + "\n")
    first = write_draw(pool, 100, tmp_path / "a.json", "abc")
    second = write_draw(pool, 100, tmp_path / "b.json", "abc")
    assert first == second
    assert (tmp_path / "a.json").read_text() == (tmp_path / "b.json").read_text()
    body = json.loads((tmp_path / "a.json").read_text())
    assert body["seed"] == SEED == 20261020
    assert body["commit"] == "abc"
    assert body["pairs"] == first["pairs"]

    out1, out2 = tmp_path / "run1.json", tmp_path / "run2.json"
    cmd = [sys.executable, "-m", "evals.draw_swarm_pairs", "--pairs", str(src), "--n", "100",
           "--commit", "abc"]
    subprocess.run([*cmd, "--out", str(out1)], cwd=ROOT, check=True)
    subprocess.run([*cmd, "--out", str(out2)], cwd=ROOT, check=True)
    assert out1.read_bytes() == out2.read_bytes()
