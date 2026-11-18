import math

from src.metrics import catalog_coverage, ndcg_at_k, recall_at_k


def test_ndcg_worked_example():
    # top-5 = A B C D E, the user later liked B, E and F  (the example from the guide)
    top = [["A", "B", "C", "D", "E"]]
    rel = [{"B", "E", "F"}]
    dcg = 1 / math.log2(3) + 1 / math.log2(6)
    idcg = 1 + 1 / math.log2(3) + 1 / math.log2(4)
    assert abs(ndcg_at_k(top, rel, k=5) - dcg / idcg) < 1e-9
    assert abs(ndcg_at_k(top, rel, k=5) - 0.4776) < 1e-3


def test_perfect_and_empty():
    assert ndcg_at_k([[1, 2, 3, 4, 5]], [{1}], k=5) == 1.0
    assert (
        ndcg_at_k([[1, 2, 3, 4, 5]], [set()], k=5) == 0.0
    )  # users with nothing to find are skipped


def test_recall_and_coverage():
    top = [[1, 2, 3, 4, 5], [1, 2, 6, 7, 8]]
    assert recall_at_k(top, [{1, 9}, {8}], k=5) == (0.5 + 1.0) / 2
    assert catalog_coverage(top, n_items=10, k=5) == 0.8


def test_short_lists_and_padding():
    assert ndcg_at_k([[1]], [{1}], k=5) == 1.0
    assert catalog_coverage([[1, -1, -1]], n_items=3) == 1 / 3
    assert catalog_coverage([], n_items=0) == 0.0


def test_top_k_small_catalog_and_seen():
    import numpy as np
    from src.ranker import top_k

    got = top_k([[2.0, 2.0, float("nan")]], [[0]], k=5)
    assert got.tolist() == [[1, -1, -1, -1, -1]]
    assert top_k([1.0, 1.0], [[]], k=2).tolist() == [[0, 1]]
    assert top_k(np.empty((0, 2)), [], k=5).shape == (0, 5)


def test_k_core_holds_both_minima_after_filtering():
    import pandas as pd
    from src.data_prep import k_core

    rows = [(u, f"p{i}") for u in range(8) for i in range(8)]
    rows += [(99, "rare")]
    result = k_core(pd.DataFrame(rows, columns=["user_id", "gmap_id"]), 5, 6)
    assert result.groupby("user_id").size().min() >= 6
    assert result.groupby("gmap_id").size().min() >= 5
    assert "rare" not in set(result.gmap_id)
