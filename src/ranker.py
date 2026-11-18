"""Combine factors into one score, pick the top-K places, and tune the factor weights."""

import itertools

import numpy as np

from src import config
from src.metrics import ndcg_at_k


def zscore_items(values):
    """Standardize an item-level factor (one value per place) to mean 0, std 1."""
    return ((values - values.mean()) / (values.std() + 1e-9)).astype(np.float32)


def zscore_rows(matrix):
    """Standardize a user x place matrix row by row (each user separately)."""
    mean = matrix.mean(axis=1, keepdims=True)
    std = matrix.std(axis=1, keepdims=True) + 1e-9
    return ((matrix - mean) / std).astype(np.float32)


def blend(factors, weights):
    """score[u, i] = sum over factors of weight * factor[u, i].

    factors: dict name -> array of shape (places,) or (users, places)
    weights: dict name -> float (factors missing from weights get weight 0)
    """
    score = None
    for name, w in weights.items():
        if w == 0:
            continue
        part = w * factors[name]
        score = part if score is None else score + part
    return score


def top_k(scores, seen, k=config.K):
    """Best k items per user, skipping items the user already visited.

    scores: (users, places) array; seen: list of arrays of item ids to exclude
    """
    if k < 0:
        raise ValueError("k must be nonnegative")
    scores = np.array(scores, dtype=np.float32, copy=True)
    if scores.ndim == 1:
        scores = np.tile(scores, (len(seen), 1))
    if scores.ndim != 2 or len(scores) != len(seen):
        raise ValueError("scores and seen must have matching user rows")
    result = np.full((len(seen), k), -1, dtype=int)
    for row, items in enumerate(seen):
        items = np.asarray(items, dtype=int)
        items = items[(items >= 0) & (items < scores.shape[1])]
        scores[row, items] = -np.inf
        valid = np.flatnonzero(np.isfinite(scores[row]))
        # Partition to avoid sorting the whole catalog for every grid-search trial.
        # Keep all boundary ties, then stable-sort their IDs for identical exact top-k.
        if 0 < k < len(valid):
            threshold = np.partition(scores[row, valid], len(valid) - k)[len(valid) - k]
            valid = valid[scores[row, valid] >= threshold]
        ordered = valid[np.argsort(-scores[row, valid], kind="stable")][:k]
        result[row, : len(ordered)] = ordered
    return result


def tune_weights(factors, grid, seen, relevant, k=config.K):
    """Try every weight combination in `grid` and keep the best one by NDCG@k.

    grid: dict name -> list of candidate weights, e.g. {"pop": [0, 0.5, 1], ...}
    """
    names = list(grid)
    best = (-1.0, None)
    for combo in itertools.product(*(grid[n] for n in names)):
        weights = dict(zip(names, combo))
        if all(w == 0 for w in combo):
            continue
        score = ndcg_at_k(top_k(blend(factors, weights), seen, k), relevant, k)
        if score > best[0]:
            best = (score, weights)
    return best[1], best[0]
