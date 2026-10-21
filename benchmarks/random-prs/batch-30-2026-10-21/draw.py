"""Reproducible draw of 30 PRs from pool.json (sorted by repo lowercase, then number).

Usage: python3 draw.py [pool.json]
At most 3 PRs per repository, so one busy repo can't fill the batch; a skipped index is
logged under `skipped_same_repo_cap`.
"""
import json, random, sys
SEED = 20261022
N, PER_REPO = 30, 3
pool = json.load(open(sys.argv[1] if len(sys.argv) > 1 else "pool.json"))["pool"]
order = random.Random(SEED).sample(range(len(pool)), len(pool))
drawn, skipped, per = [], [], {}
for k in order:
    p = pool[k]
    if per.get(p["repo"], 0) >= PER_REPO:
        skipped.append(k); continue
    per[p["repo"]] = per.get(p["repo"], 0) + 1
    drawn.append(dict(p, pool_index=k))
    if len(drawn) == N: break
for i, p in enumerate(drawn, 1):
    print(i, p["repo"], p["number"], p["url"])
json.dump({"seed": SEED, "pool_size": len(pool), "per_repo_cap": PER_REPO, "draw_order_indices": order[:len(drawn)+len(skipped)],
           "skipped_same_repo_cap": skipped, "drawn": drawn}, open("drawn.json", "w"), indent=1)
