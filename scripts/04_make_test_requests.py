"""Step 4: build the trip requests used to evaluate the agent -> data/processed/agent_requests.jsonl

    python scripts/04_make_test_requests.py --n 200
    python scripts/04_make_test_requests.py --n 200 --survey survey/requests_from_survey.jsonl

Survey-based requests (real people) come first; the rest are generated with a fixed random seed.
Every request records where it came from ("source"), so you can report it honestly.
"""

import argparse
import json
import random
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src import config  # noqa: E402
from src.constraints import DAYS  # noqa: E402

INTERESTS = {
    "art": "art museums and galleries",
    "history": "historic sites",
    "nature": "parks, gardens and the water",
    "coffee": "coffee shops and bakeries",
    "seafood": "seafood",
    "pizza": "pizza and Italian food",
    "nightlife": "bars and live music",
    "shopping": "book stores and markets",
    "family": "zoos, aquariums and kids' museums",
}
QUERIES = {
    "art": "art museum gallery",
    "history": "historical landmark history museum",
    "nature": "park garden beach trail",
    "coffee": "coffee cafe bakery",
    "seafood": "seafood restaurant oyster",
    "pizza": "pizza italian restaurant",
    "nightlife": "bar brewery live music",
    "shopping": "book store market",
    "family": "zoo aquarium children museum",
}


def request_text(r, region):
    people = "1 person" if r["group_size"] == 1 else f"{r['group_size']} people"
    likes = " and ".join(INTERESTS[i] for i in r["interests"])
    how = "walking" if r["mode"] == "walk" else "car"
    return (
        f"We're {people} spending a day in {region} on {r['day_name']} "
        f"from {r['start']} to {r['end']}. Total budget ${r['budget']}. We like {likes}. "
        f"We'll start at {r['origin']['name']} and get around by {how}; "
        f"keep each leg under {r['max_leg_minutes']} minutes. "
        f"Please plan about {r['n_stops']} stops."
    )


def synthetic(n, places, popular_items, rng, region, start_id=0):
    out = []
    for k in range(n):
        o = places.iloc[rng.choice(popular_items)]
        group = rng.choice([1, 2, 2, 3, 4])
        mode = "walk" if rng.random() < 0.6 else "drive"
        weekday = rng.randrange(7)
        start_h = rng.choice([9, 10, 11])
        r = {
            "id": f"syn_{start_id + k:03d}",
            "source": "synthetic",
            "group_size": group,
            "weekday": weekday,
            "day_name": DAYS[weekday].title(),
            "start": f"{start_h:02d}:00",
            "end": f"{start_h + rng.choice([6, 7, 8]):02d}:00",
            "budget": group * rng.choice([25, 40, 60, 80]),
            "interests": rng.sample(list(INTERESTS), 2),
            "mode": mode,
            "max_leg_minutes": rng.choice([15, 20, 25])
            if mode == "walk"
            else rng.choice([15, 20, 30]),
            "n_stops": rng.choice([3, 4, 4, 5]),
            "origin": {"name": o["name"], "lat": float(o["lat"]), "lng": float(o["lng"])},
        }
        r["query"] = " ".join(QUERIES[i] for i in r["interests"])
        r["text"] = request_text(r, region)
        out.append(r)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=200)
    ap.add_argument(
        "--survey", type=Path, default=None, help="jsonl made by scripts/survey_to_requests.py"
    )
    args = ap.parse_args()
    if args.n <= 0:
        ap.error("--n must be positive")
    if args.survey is not None and not args.survey.is_file():
        ap.error("--survey file does not exist")
    rng = random.Random(config.SEED)
    places = pd.read_parquet(config.DATA_PROCESSED / "places.parquet")
    train = pd.read_parquet(config.DATA_PROCESSED / "train.parquet")
    popular = (
        train["item_idx"].value_counts().index[:100].tolist()
    )  # start points: well-known places
    state = json.loads((config.DATA_PROCESSED / "dataset_info.json").read_text())["state"]
    region = "Providence" if state == "FAKE" else state.replace("_", " ")

    requests = []
    if args.survey and args.survey.exists():
        requests = [
            json.loads(line) for line in args.survey.read_text().splitlines() if line.strip()
        ][: args.n]
        for r in requests:
            r["query"] = " ".join(QUERIES[i] for i in r["interests"])
            r["text"] = request_text(r, region)
    requests += synthetic(args.n - len(requests), places, popular, rng, region)
    out = config.DATA_PROCESSED / "agent_requests.jsonl"
    out.write_text("\n".join(json.dumps(r) for r in requests) + "\n")
    print(
        f"wrote {len(requests)} requests "
        f"({sum(r['source'] == 'survey' for r in requests)} from the survey) -> {out}"
    )
    print("example:", requests[0]["text"])


if __name__ == "__main__":
    main()
