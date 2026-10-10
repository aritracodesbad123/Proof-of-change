"""Probe for rasbt/mlxtend#1229: feature_importance_permutation with feature_groups.

Runs on both sides (main and PR) in the side's own environment and prints one JSON object
{"observations": {name: value}}. Deterministic: fixed data, a fixed linear model, metric r2, seed 123.
No assertions: plain code compares the two sides (poc/probes.py).
"""
import json

import numpy as np
from mlxtend.evaluate import feature_importance_permutation as fip

PROBE = {
    "id": "feature-groups-permutation",
    "target": "rasbt/mlxtend#1229",
    "about": "Which columns each feature group permutes, importances for a fixed seed, and the caller's X after the call.",
    "claims": [
        {"id": "C1", "source": "PR description",
         "text": "A group given as a list or range now permutes its own columns, not the first columns of X.",
         "covers": ["list_groups.columns_permuted"], "expect": "differs"},
        {"id": "C2", "source": "PR description",
         "text": "For integer groups the results do not change for a given seed.",
         "covers": ["int_groups_only.importances"], "expect": "same"},
    ],
    "timeout_s": 120,
}

SEED = 123
rs = np.random.RandomState(0)
N, P = 40, 5
X0 = rs.normal(size=(N, P))
COEF = np.array([3.0, -2.0, 1.5, 1.0, 0.5])
Y = X0 @ COEF + 0.1 * rs.normal(size=N)


def predict(X):
    return X @ COEF


def label(g):
    return str(g) if isinstance(g, int) else str(list(g))


def importances(groups, rounds):
    X = X0.copy()
    mean, allv = fip(X, Y, predict, metric="r2", num_rounds=rounds, seed=SEED, feature_groups=groups)
    names = [str(i) for i in range(P)] if groups is None else [label(g) for g in groups]
    return {name: [float(v) for v in row] for name, row in zip(names, allv)}


def columns_permuted(groups):
    """Columns that differ from the caller's original X in each predict call after the baseline call, per group."""
    X = X0.copy()
    seen = []

    def pm(Z):
        seen.append([int(c) for c in range(P) if not np.array_equal(Z[:, c], X0[:, c])])
        return predict(Z)
    fip(X, Y, pm, metric="r2", num_rounds=1, seed=SEED, feature_groups=groups)
    return {label(g): cols for g, cols in zip(groups, seen[1:])}


def caller_x_changed_columns(groups):
    X = X0.copy()
    fip(X, Y, predict, metric="r2", num_rounds=1, seed=SEED, feature_groups=groups)
    return [int(c) for c in range(P) if not np.array_equal(X[:, c], X0[:, c])]


obs = {
    # C2: integer groups only, 3 rounds
    "int_groups_only.importances": importances([0, 1, 2, 3, 4], 3),
    # no groups at all
    "no_groups.importances": importances(None, 3),
    # C1: single-element list groups, each should permute its own column
    "list_groups.columns_permuted": columns_permuted([[2], [3], [4]]),
    # integer groups after a multi-column group on the first columns (the old wrong-column bug cannot apply here)
    "int_groups_after_multi_group.importances": importances([range(0, 2), 2, 3, 4], 1),
    # the caller's X after a call with a multi-column group that is not on the first columns
    "caller_x_after_call.changed_columns": caller_x_changed_columns([0, 1, range(2, 4), 4]),
}
print(json.dumps({"observations": obs}, sort_keys=True))
