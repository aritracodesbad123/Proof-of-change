"""Reproducible draw of 3 PRs from pool.json. Pool is sorted by (repo lowercase, number).

Usage: python3 draw.py [pool.json]
"""
import json
import random
import sys

SEED = 20261021
pool = json.load(open(sys.argv[1] if len(sys.argv) > 1 else "pool.json"))["pool"]
rng = random.Random(SEED)
order = rng.sample(range(len(pool)), len(pool))  # full permutation; take first 3 eligible, later ones are redraws
drawn = [pool[k] for k in order[:3]]
for p in drawn:
    print(p["repo"], p["number"], p["url"], p["title"])
json.dump({"seed": SEED, "pool_size": len(pool), "draw_order_indices": order[:10], "drawn": drawn},
          open("draw_result.json", "w"), indent=1)
