"""Step 2: the ranking experiments (the core of the resume bullets).

    python scripts/02_rank_experiments.py            # needs Java for PySpark ALS
    python scripts/02_rank_experiments.py --skip-als # baseline only (if Java is not installed yet)

Variants (each tuned on validation, scored once on test):
  A  popularity only
  B  3-factor baseline: popularity + rating + TF-IDF preference match
  C  B + raw ALS score as an additive factor
  D  B + popularity-residualized ALS score
Writes results/ranking_results.md and the artifacts the website needs.
"""

import argparse
import json
import sys
import time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from scipy import sparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src import config  # noqa: E402
from src.features import bayesian_rating, fit_tfidf, popularity, tfidf_match, user_profiles  # noqa: E402
from src.metrics import catalog_coverage, ndcg_at_k, recall_at_k  # noqa: E402
from src.ranker import blend, top_k, tune_weights, zscore_items, zscore_rows  # noqa: E402
from src.residualize import mean_correlation, residualize_on_popularity  # noqa: E402

parser = argparse.ArgumentParser()
parser.add_argument("--skip-als", action="store_true")
args = parser.parse_args()
t0 = time.time()
P = config.DATA_PROCESSED
places = pd.read_parquet(P / "places.parquet")
train, val, test = (pd.read_parquet(P / f"{n}.parquet") for n in ("train", "val", "test"))
n_items = len(places)
n_users = int(max(train["user_idx"].max(), val["user_idx"].max(), test["user_idx"].max())) + 1
rng = np.random.default_rng(config.SEED)


def eval_split(df, history):
    """Users with >=1 liked held-out place, what they liked, and what to hide (already seen)."""
    pos = df[df["rating"] >= config.POSITIVE_RATING]
    users = np.array(sorted(pos["user_idx"].unique()))
    if len(users) > config.N_EVAL_USERS:
        users = np.sort(rng.choice(users, config.N_EVAL_USERS, replace=False))
    if not len(users):
        raise ValueError("No positive held-out users; ranking evaluation is undefined")
    rel = pos.groupby("user_idx")["item_idx"].apply(set)
    seen = history.groupby("user_idx")["item_idx"].apply(np.array)
    return users, [rel[u] for u in users], [seen.get(u, np.array([], dtype=int)) for u in users]


val_users, val_rel, val_seen = eval_split(val, train)
test_users, test_rel, test_seen = eval_split(test, pd.concat([train, val]))
print(
    f"places={n_items:,} users={n_users:,} | "
    f"eval users: val={len(val_users):,} test={len(test_users):,}"
)

# ---- the three baseline factors (train data only) ----
pop = popularity(train, n_items)
rating = bayesian_rating(train, n_items)
vectorizer, place_matrix = fit_tfidf(places)
profiles = user_profiles(train, place_matrix, n_users)


def factors_for(users, als_parts=None):
    """All factor matrices for some users + how much ALS overlaps with popularity."""
    f = {
        "pop": zscore_items(pop),
        "rating": zscore_items(rating),
        "tfidf": zscore_rows(tfidf_match(profiles, place_matrix, users)),
    }
    overlap = {}
    if als_parts is not None:
        raw = als_parts[0][users] @ als_parts[1].T  # ALS score for every (user, place)
        resid, _ = residualize_on_popularity(raw, pop)  # same scores with popularity removed
        overlap = {
            "corr(raw ALS, log popularity)": round(mean_correlation(raw, pop), 3),
            "corr(residual ALS, log popularity)": round(mean_correlation(resid, pop), 3),
        }
        f["als"], f["als_resid"] = zscore_rows(raw), zscore_rows(resid)
    return f, overlap


als_parts = None
if not args.skip_als:
    from src.als_spark import train_als

    print("training PySpark ALS ...")
    als_parts = train_als(train, n_users, n_items)
F_val, _ = factors_for(val_users, als_parts)
F_test, extra = factors_for(test_users, als_parts)

base_grid = {"pop": [0, 0.25, 0.5, 1.0], "rating": [0, 0.25, 0.5, 1.0], "tfidf": [0.5, 1.0, 2.0]}
variants = [
    ("A. Popularity only", {"pop": [1.0]}),
    ("B. 3-factor baseline (popularity + rating + TF-IDF)", base_grid),
]
if als_parts is not None:
    variants += [
        ("C. B + raw ALS (additive factor)", {**base_grid, "als": [0.5, 1.0, 2.0]}),
        ("D. B + popularity-residualized ALS", {**base_grid, "als_resid": [0.5, 1.0, 2.0]}),
        ("(reference) raw ALS only", {"als": [1.0]}),
    ]

rows = []
for name, grid in variants:
    weights, val_ndcg = tune_weights(F_val, grid, val_seen, val_rel)
    top = top_k(blend(F_test, weights), test_seen)
    rows.append(
        {
            "variant": name,
            "weights": weights,
            "val_ndcg@5": round(val_ndcg, 4),
            "test_ndcg@5": round(ndcg_at_k(top, test_rel), 4),
            "test_recall@5": round(recall_at_k(top, test_rel), 4),
            "catalog_coverage@5": round(catalog_coverage(top, n_items), 4),
        }
    )
    print(
        f"{name:52s} val={rows[-1]['val_ndcg@5']:.4f}  test NDCG@5={rows[-1]['test_ndcg@5']:.4f}  "
        f"coverage={rows[-1]['catalog_coverage@5']:.3f}"
    )

if extra:
    print(extra)

# ---- save results ----
STATE = config.dataset_state()
OUT = config.results_dir()
lines = [
    "# Ranking results",
    "Protocol: per-user temporal split, not a global time cutoff. "
    "Metadata is a static snapshot; historical availability is not verified.",
    "",
    f"Dataset: **{STATE}**"
    + (" (practice data - never report these numbers)" if STATE == "FAKE" else ""),
    "",
    f"Data: {n_items:,} places, {n_users:,} users, {len(train):,} train visits. "
    f"Test = each user's last {config.N_TEST} reviews (proxy for visits); "
    f"relevant = rated >= {config.POSITIVE_RATING}. "
    f"Evaluated on {len(test_users):,} users.",
    "",
    "| Variant | Test NDCG@5 | Test Recall@5 | Catalog coverage@5 | Val NDCG@5 | Weights |",
    "|---|---|---|---|---|---|",
]
for r in rows:
    lines.append(
        f"| {r['variant']} | {r['test_ndcg@5']:.4f} | {r['test_recall@5']:.4f} | "
        f"{r['catalog_coverage@5']:.1%} | {r['val_ndcg@5']:.4f} | {r['weights']} |"
    )
lines += [""] + [f"- {k}: {v}" for k, v in extra.items()]
(OUT / "ranking_results.md").write_text("\n".join(lines) + "\n")
(OUT / "ranking_results.json").write_text(
    json.dumps(
        {
            "dataset": STATE,
            "synthetic": STATE == "FAKE",
            "evaluation": "per-user chronological held-out reviews, not real trips",
            "rows": rows,
            **extra,
        },
        indent=2,
    )
)

# ---- artifacts for the website / agent ----
config.ARTIFACTS.mkdir(exist_ok=True)
joblib.dump(vectorizer, config.ARTIFACTS / "tfidf_vectorizer.joblib")
sparse.save_npz(config.ARTIFACTS / "place_tfidf.npz", place_matrix.tocsr())
np.savez(config.ARTIFACTS / "item_stats.npz", popularity=pop, rating=rating)
if als_parts is not None:
    np.save(config.ARTIFACTS / "als_item_factors.npy", als_parts[1])

# best model on VALIDATION (never pick by test) -> top-50 lists for the re-ranking experiment
best = max([r for r in rows if not r["variant"].startswith("(")], key=lambda r: r["val_ndcg@5"])
top50 = top_k(blend(F_test, best["weights"]), test_seen, k=50)
np.savez(
    config.ARTIFACTS / "test_candidates.npz", users=test_users, top50=top50, variant=best["variant"]
)
print(f"done in {time.time() - t0:.0f}s -> {OUT / 'ranking_results.md'}")
