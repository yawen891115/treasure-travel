"""Step 3: does constraint-aware re-ranking remove closed / too-far places from the top-5?

    python scripts/03_rerank_eval.py

For every test user we invent a realistic trip moment (a weekday, a start time, the user's last
known location, max 20 min walk) and compare the model's top-5 before and after re-ranking.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src import config  # noqa: E402
from src.metrics import ndcg_at_k  # noqa: E402
from src.rerank import PlaceConstraints, rerank  # noqa: E402

MODE, MAX_MIN, VISIT_MIN = "drive", 25, 60  # state-wide data: driving is realistic
P = config.DATA_PROCESSED
STATE = config.dataset_state()
places = pd.read_parquet(P / "places.parquet")
train, test = pd.read_parquet(P / "train.parquet"), pd.read_parquet(P / "test.parquet")
cand = np.load(config.ARTIFACTS / "test_candidates.npz", allow_pickle=True)
users, top50 = cand["users"], cand["top50"]
cons = PlaceConstraints(places)
rng = np.random.default_rng(config.SEED)

last_place = train.sort_values("time").groupby("user_idx")["item_idx"].last()
pos = test[test["rating"] >= config.POSITIVE_RATING].groupby("user_idx")["item_idx"].apply(set)

before_bad, after_bad, n_before, users_bad_before, users_bad_after = 0, 0, 0, 0, 0
before_lists, after_lists, rel, lengths = [], [], [], []
unknown_hours = sum(1 for h in cons.hours if not h) / len(cons.hours)
for u, ranked in zip(users, top50):
    ranked = ranked[ranked >= 0]
    weekday = int(rng.integers(0, 7))
    start = int(rng.choice(np.arange(9 * 60, 20 * 60 + 1, 30)))
    item = last_place[u]
    origin = (cons.lat[item], cons.lng[item])
    top5 = list(ranked[:5])
    bad = [cons.violation(i, weekday, start, VISIT_MIN, origin, MAX_MIN, MODE) for i in top5]
    n_bad = sum(b is not None for b in bad)
    before_bad += n_bad
    users_bad_before += n_bad > 0
    n_before += len(top5)
    new5 = rerank(ranked, cons, weekday, start, VISIT_MIN, origin, MAX_MIN, k=5, mode=MODE)
    new_bad = sum(
        cons.violation(i, weekday, start, VISIT_MIN, origin, MAX_MIN, MODE) is not None
        for i in new5
    )
    after_bad += new_bad
    users_bad_after += new_bad > 0
    lengths.append(len(new5))
    before_lists.append(top5)
    after_lists.append(new5 + [-1] * (5 - len(new5)))  # pad short lists so shapes match
    rel.append(pos.get(u, set()))

lines = [
    "# Constraint-aware re-ranking",
    "",
    f"Dataset: **{STATE}**"
    + (" (practice data - never report these numbers)" if STATE == "FAKE" else ""),
    "",
    f"Model: {cand['variant']}. Trip moment per user: random weekday, start 09:00-20:00, "
    f"{VISIT_MIN}-min visit, last known location, max {MAX_MIN} min by {MODE}.",
    "",
    "| | Before re-ranking | After re-ranking |",
    "|---|---|---|",
    "| Top-5 places that are closed, too far or unverified hours | "
    f"{before_bad / max(n_before, 1):.1%} "
    f"| {after_bad / max(sum(lengths), 1):.1%} |",
    "| Users whose top-5 has at least one such place | "
    f"{users_bad_before / max(len(users), 1):.1%} "
    f"| {users_bad_after / max(len(users), 1):.1%} |",
    f"| NDCG@5 against held-out visits | {ndcg_at_k(before_lists, rel):.4f} "
    f"| {ndcg_at_k(after_lists, rel):.4f} |",
    f"| Average list length | {n_before / max(len(users), 1):.2f} | "
    f"{np.mean(lengths) if lengths else 0:.2f} |",
    "",
    "Places with unknown opening hours (excluded unless a known interval covers the visit): "
    f"{unknown_hours:.1%}",
]
(config.results_dir() / "rerank_results.md").write_text("\n".join(lines) + "\n")
print("\n".join(lines))
