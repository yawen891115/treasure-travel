"""Create a small FAKE dataset in the exact Google Local format, for practice runs only.

    python scripts/00_make_fake_data.py

It writes data/raw/meta-FAKE.json.gz and data/raw/review-FAKE_10.json.gz.
Use it to check that every script runs. Never put numbers from fake data on a resume.
"""

import gzip
import json
import random
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src import config  # noqa: E402

THEMES = {
    "art": [
        ["Art museum", "Museum", "Tourist attraction"],
        ["Art gallery"],
        ["Museum", "Art center"],
    ],
    "history": [
        ["Historical landmark", "Tourist attraction"],
        ["History museum", "Museum"],
        ["Mansion", "Historical place museum"],
    ],
    "nature": [
        ["Park"],
        ["Beach"],
        ["Botanical garden", "Garden"],
        ["Hiking area", "Park"],
        ["Lighthouse", "Scenic spot"],
    ],
    "coffee": [["Coffee shop", "Cafe"], ["Cafe", "Bakery"], ["Espresso bar", "Coffee shop"]],
    "seafood": [
        ["Seafood restaurant", "Restaurant"],
        ["Oyster bar restaurant", "Seafood restaurant"],
    ],
    "pizza": [
        ["Pizza restaurant", "Italian restaurant", "Restaurant"],
        ["Italian restaurant", "Restaurant"],
    ],
    "night": [["Bar", "Cocktail bar"], ["Brewery", "Bar"], ["Live music venue", "Bar"]],
    "shopping": [
        ["Book store"],
        ["Farmers' market", "Market"],
        ["Vintage clothing store", "Market"],
    ],
    "family": [
        ["Zoo", "Tourist attraction"],
        ["Aquarium", "Tourist attraction"],
        ["Children's museum", "Museum"],
    ],
}
DESCRIPTIONS = {
    "art": "Rotating exhibitions of contemporary and classic art, sculpture and photography.",
    "history": "Colonial-era history, guided tours and preserved architecture.",
    "nature": "Walking trails, water views and green space for picnics.",
    "coffee": "Specialty coffee, espresso drinks and fresh pastries.",
    "seafood": "Fresh local seafood, oysters and chowder.",
    "pizza": "Wood-fired pizza and Italian classics.",
    "night": "Craft beer, cocktails and live music in the evening.",
    "shopping": "Local makers, used books and weekend vendors.",
    "family": "Animals, interactive exhibits and activities for kids.",
}
DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def hours_for(theme, rng):
    if rng.random() < 0.1:
        return None  # some places have no hours
    if theme in ("art", "history", "family"):
        return [[d, "Closed" if d == "Monday" else "10AM–5PM"] for d in DAYS]
    if theme == "nature":
        return [[d, "Open 24 hours" if rng.random() < 0.5 else "6AM–9PM"] for d in DAYS]
    if theme == "coffee":
        return [[d, "7AM–6PM"] for d in DAYS]
    if theme in ("seafood", "pizza"):
        return [[d, "Closed" if d == "Monday" else "11:30AM–2:30PM, 5–10PM"] for d in DAYS]
    if theme == "night":
        return [[d, "4PM–1AM"] for d in DAYS]
    return [[d, "9AM–7PM"] for d in DAYS]


def main(n_places=800, n_users=4000, seed=config.SEED):
    rng = random.Random(seed)
    np_rng = np.random.default_rng(seed)
    theme_names = list(THEMES)
    places = []
    for i in range(n_places):
        theme = rng.choice(theme_names)
        cats = rng.choice(THEMES[theme])
        food = theme in ("coffee", "seafood", "pizza", "night")
        places.append(
            {
                "name": f"{theme.title()} Place {i}",
                "address": f"{i} Example St, Providence, RI 02903",
                "gmap_id": f"0x{rng.getrandbits(64):016x}:0x{rng.getrandbits(64):016x}",
                "description": DESCRIPTIONS[theme] if rng.random() < 0.5 else None,
                "latitude": 41.80 + rng.random() * 0.06,
                "longitude": -71.44 + rng.random() * 0.06,
                "category": cats,
                "avg_rating": round(rng.uniform(3.5, 4.9), 1),
                "num_of_reviews": 0,
                "price": rng.choice(["$", "$$", "$$", "$$$"]) if food else None,
                "hours": hours_for(theme, rng),
                "MISC": None,
                "state": "Open ⋅ Closes 5PM",
                "relative_results": [],
                "url": "https://www.google.com/maps/place/fake",
                "_theme": theme,
            }
        )
    popularity = np_rng.lognormal(0.0, 1.0, n_places)
    theme_idx = np.array([theme_names.index(p["_theme"]) for p in places])

    reviews = []
    for u in range(n_users):
        taste = np_rng.dirichlet(np.full(len(theme_names), 0.3))
        weight = popularity**0.8 * (taste[theme_idx] + 0.02) ** 1.5
        n = int(np_rng.integers(10, 40))
        chosen = np_rng.choice(n_places, size=n, replace=False, p=weight / weight.sum())
        times = np.sort(np_rng.integers(1_450_000_000_000, 1_630_000_000_000, size=n))
        for item, t in zip(chosen, times):
            match = taste[theme_idx[item]]
            rating = int(np.clip(round(3.6 + 2.5 * match + np_rng.normal(0, 0.7)), 1, 5))
            reviews.append(
                {
                    "user_id": str(10**20 + u),
                    "name": f"User {u}",
                    "time": int(t),
                    "rating": rating,
                    "text": "Great visit." if rating >= 4 else "It was okay.",
                    "pics": None,
                    "resp": None,
                    "gmap_id": places[item]["gmap_id"],
                }
            )
    config.DATA_RAW.mkdir(parents=True, exist_ok=True)
    with gzip.open(config.DATA_RAW / "meta-FAKE.json.gz", "wt", encoding="utf-8") as f:
        for p in places:
            p = {k: v for k, v in p.items() if not k.startswith("_")}
            f.write(json.dumps(p) + "\n")
    with gzip.open(config.DATA_RAW / "review-FAKE_10.json.gz", "wt", encoding="utf-8") as f:
        for r in reviews:
            f.write(json.dumps(r) + "\n")
    print(f"wrote {len(places)} fake places and {len(reviews)} fake reviews to {config.DATA_RAW}")


if __name__ == "__main__":
    main()
