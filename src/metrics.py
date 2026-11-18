"""Offline evaluation metrics for top-K recommendation lists."""

import numpy as np


def ndcg_at_k(top_items, relevant, k=5):
    """Mean NDCG@k with binary relevance.

    top_items: array (n_users, >=k) of recommended item ids, best first
    relevant:  list of sets; relevant[u] = items user u liked in the held-out period
    """
    discounts = 1.0 / np.log2(np.arange(2, k + 2))  # 1/log2(2), 1/log2(3), ...
    scores = []
    for items, rel in zip(top_items, relevant):
        if not rel:
            continue  # nothing to find for this user
        gains = np.array([1.0 if i in rel else 0.0 for i in items[:k]])
        dcg = float((gains * discounts[: len(gains)]).sum())
        idcg = float(discounts[: min(len(rel), k)].sum())  # best possible order
        scores.append(dcg / idcg)
    return float(np.mean(scores)) if scores else 0.0


def recall_at_k(top_items, relevant, k=5):
    vals = [len(set(items[:k]) & rel) / len(rel) for items, rel in zip(top_items, relevant) if rel]
    return float(np.mean(vals)) if vals else 0.0


def catalog_coverage(top_items, n_items, k=5):
    """Share of all places that appear in at least one user's top-k list."""
    if n_items <= 0 or len(top_items) == 0:
        return 0.0
    items = np.asarray(top_items)[:, :k]
    valid = items[(items >= 0) & (items < n_items)]
    return len(np.unique(valid)) / n_items
