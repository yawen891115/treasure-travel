"""Prepare Boston city proper from Massachusetts UCSD files and official city boundary.

Point-in-polygon covers() includes points on the boundary and excludes Cambridge/Somerville.
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path

from shapely.geometry import Point, shape
from shapely.ops import unary_union
from shapely.prepared import prep

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src import config  # noqa: E402
from src.data_prep import load_places, load_reviews, k_core, split_by_time  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", type=Path, default=config.DATA_PROCESSED)
    args = parser.parse_args()
    boundary_file = config.DATA_RAW / "boston_boundary.geojson"
    features = json.loads(boundary_file.read_text())["features"]
    boundary = prep(unary_union([shape(f["geometry"]) for f in features]))
    places = load_places(config.DATA_RAW / "meta-Massachusetts.json.gz")
    mask = [boundary.covers(Point(lng, lat)) for lat, lng in zip(places.lat, places.lng)]
    places = places[mask].copy()
    before = len(places)
    print(f"Eligible places inside official Boston city boundary: {before:,}", flush=True)
    reviews = load_reviews(config.DATA_RAW / "review-Massachusetts_10.json.gz", places.gmap_id)
    reviews = k_core(reviews, config.MIN_PLACE_REVIEWS, config.MIN_USER_REVIEWS)
    if reviews.empty:
        raise ValueError("No Boston reviews remain after k-core filtering")
    places = places[places.gmap_id.isin(reviews.gmap_id)].reset_index(drop=True)
    places["item_idx"] = range(len(places))
    items = dict(zip(places.gmap_id, places.item_idx))
    users = {user: i for i, user in enumerate(sorted(reviews.user_id.unique()))}
    reviews["item_idx"] = reviews.gmap_id.map(items)
    reviews["user_idx"] = reviews.user_id.map(users)
    train, val, test = split_by_time(reviews)
    out = args.out_dir
    out.mkdir(parents=True, exist_ok=True)
    places.to_parquet(out / "places.parquet", index=False)
    for name, frame in [("train", train), ("val", val), ("test", test)]:
        frame[["user_idx", "item_idx", "rating", "time"]].to_parquet(
            out / f"{name}.parquet", index=False
        )
    stats = {
        "state": "Boston",
        "source_state": "Massachusetts",
        "places": len(places),
        "users": len(users),
        "reviews": len(reviews),
        "train": len(train),
        "val": len(val),
        "test": len(test),
        "places_before_k_core": before,
        "test_positive_share": float((test.rating >= config.POSITIVE_RATING).mean()),
        "geography": "Boston city proper, official polygon covers(Point(longitude, latitude))",
        "boundary_sha256": hashlib.sha256(boundary_file.read_bytes()).hexdigest(),
        "protocol": "Per-user temporal review split; static historical POI metadata",
    }
    (out / "dataset_info.json").write_text(json.dumps(stats, indent=2))
    print(json.dumps(stats, indent=2), flush=True)


if __name__ == "__main__":
    main()
