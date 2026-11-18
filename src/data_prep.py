"""Turn the raw Google Local files into clean tables for modeling.

Output (in data/processed/):
  places.parquet       one row per place (item_idx, name, categories, lat, lng, hours, ...)
  train.parquet        visits used to build features and train models
  val.parquet          each user's next-to-last visit(s): used to choose model weights
  test.parquet         each user's last visits: used ONLY for the final numbers
"""

import gzip
import json
import re

import pandas as pd

from src import config


def _read_json_lines(path):
    """Yield one dict per line of a .json.gz file (the Google Local format)."""
    with gzip.open(path, "rt", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def is_travel_place(categories):
    if not categories:
        return False
    text = " | ".join(categories).lower()
    return any(
        re.search(r"(?<!\w)" + re.escape(word) + r"(?!\w)", text) for word in config.TRAVEL_KEYWORDS
    )


def load_places(meta_path=config.META_FILE):
    rows = []
    for rec in _read_json_lines(meta_path):
        cats = rec.get("category") or []
        if not is_travel_place(cats):
            continue
        if rec.get("latitude") is None or rec.get("longitude") is None:
            continue
        if "permanently closed" in str(rec.get("state") or "").lower():
            continue
        rows.append(
            {
                "gmap_id": rec["gmap_id"],
                "name": rec.get("name") or "",
                "address": rec.get("address") or "",
                "categories": ", ".join(cats),
                "description": rec.get("description") or "",
                "lat": float(rec["latitude"]),
                "lng": float(rec["longitude"]),
                "price": rec.get("price") or "",
                "hours": json.dumps(rec.get("hours") or []),  # keep the raw list as text
                "avg_rating": rec.get("avg_rating"),
            }
        )
    if not rows:
        raise ValueError("No eligible places in metadata; check categories and coordinates")
    places = pd.DataFrame(rows).drop_duplicates("gmap_id")
    print(f"places kept after category filter: {len(places):,}")
    return places


def load_reviews(review_path, keep_ids):
    keep_ids = set(keep_ids)
    rows = []
    for n, rec in enumerate(_read_json_lines(review_path), start=1):
        if n % 1_000_000 == 0:
            print(f"  read {n:,} review lines ...")  # big files take a few minutes
        if rec.get("gmap_id") in keep_ids and rec.get("rating") is not None:
            rows.append((str(rec["user_id"]), rec["gmap_id"], int(rec["rating"]), int(rec["time"])))
    reviews = pd.DataFrame(rows, columns=["user_id", "gmap_id", "rating", "time"])
    # one review per (user, place): keep the latest one
    reviews = reviews.sort_values("time").drop_duplicates(["user_id", "gmap_id"], keep="last")
    print(f"reviews on kept places: {len(reviews):,}")
    return reviews


def k_core(reviews, min_place, min_user, rounds=None):
    """Repeatedly drop rare places and users until both limits hold."""
    min_user = max(min_user, config.N_TEST + config.N_VAL + 3)
    iteration = 0
    while len(reviews):
        place_counts = reviews["gmap_id"].map(reviews["gmap_id"].value_counts())
        user_counts = reviews["user_id"].map(reviews["user_id"].value_counts())
        keep = (place_counts >= min_place) & (user_counts >= min_user)
        if keep.all():
            break
        reviews = reviews[keep]
        iteration += 1
        if rounds is not None and iteration >= rounds:
            raise ValueError("k-core did not converge within rounds; increase or remove the limit")
    return reviews.copy()


def split_by_time(reviews, n_test=config.N_TEST, n_val=config.N_VAL):
    """For each user: oldest visits -> train, then val, then the newest -> test."""
    reviews = reviews.sort_values(["user_idx", "time"])
    # rank 0 = newest visit of that user
    newest_rank = reviews.groupby("user_idx").cumcount(ascending=False)
    test = reviews[newest_rank < n_test]
    val = reviews[(newest_rank >= n_test) & (newest_rank < n_test + n_val)]
    train = reviews[newest_rank >= n_test + n_val]
    return train.copy(), val.copy(), test.copy()


def prepare(
    meta_path=config.META_FILE,
    review_path=config.REVIEW_FILE,
    out_dir=config.DATA_PROCESSED,
    state=None,
):
    out_dir.mkdir(parents=True, exist_ok=True)
    places = load_places(meta_path)
    reviews = load_reviews(review_path, places["gmap_id"])
    reviews = k_core(reviews, config.MIN_PLACE_REVIEWS, config.MIN_USER_REVIEWS)

    if reviews.empty:
        raise ValueError(
            "No reviews remain after k-core filtering; supply more data or lower thresholds"
        )

    # integer ids 0..N-1 are what the models need
    places = places[places["gmap_id"].isin(reviews["gmap_id"])].reset_index(drop=True)
    places["item_idx"] = range(len(places))
    item_of = dict(zip(places["gmap_id"], places["item_idx"]))
    users = sorted(reviews["user_id"].unique())
    user_of = {u: i for i, u in enumerate(users)}
    reviews["item_idx"] = reviews["gmap_id"].map(item_of)
    reviews["user_idx"] = reviews["user_id"].map(user_of)

    train, val, test = split_by_time(reviews)
    cols = ["user_idx", "item_idx", "rating", "time"]
    places.to_parquet(out_dir / "places.parquet", index=False)
    train[cols].to_parquet(out_dir / "train.parquet", index=False)
    val[cols].to_parquet(out_dir / "val.parquet", index=False)
    test[cols].to_parquet(out_dir / "test.parquet", index=False)

    stats = {
        "places": len(places),
        "users": len(users),
        "reviews": len(reviews),
        "train": len(train),
        "val": len(val),
        "test": len(test),
        "test_positive_share": round(float((test["rating"] >= config.POSITIVE_RATING).mean()), 3),
    }
    stats["state"] = state or config.STATE
    (out_dir / "dataset_info.json").write_text(json.dumps(stats, indent=2))
    print(json.dumps(stats, indent=2))
    return stats
