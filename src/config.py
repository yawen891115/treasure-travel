"""Project-wide settings. Change values here, not inside the other files."""

import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_RAW = ROOT / "data" / "raw"
DATASET_ROOT = Path(os.environ.get("TRAVEL_DATASET_ROOT", ROOT))
DATA_PROCESSED = DATASET_ROOT / "data" / "processed"
ARTIFACTS = DATASET_ROOT / "artifacts"
RESULTS = DATASET_ROOT / "results"

# Which Google Local file to use. Override with:  STATE=Vermont python scripts/01_prepare_data.py
STATE = os.environ.get("STATE", "Rhode_Island")
META_FILE = DATA_RAW / f"meta-{STATE}.json.gz"
REVIEW_FILE = DATA_RAW / f"review-{STATE}_10.json.gz"

# Keep only places a traveler might visit (matched against Google categories, lower-case).
TRAVEL_KEYWORDS = [
    "museum",
    "art gallery",
    "park",
    "garden",
    "beach",
    "tourist attraction",
    "historical",
    "landmark",
    "monument",
    "zoo",
    "aquarium",
    "theater",
    "theatre",
    "cafe",
    "coffee",
    "bakery",
    "restaurant",
    "pizza",
    "seafood",
    "brewery",
    "winery",
    "bar",
    "ice cream",
    "dessert",
    "book store",
    "market",
    "hiking",
    "scenic",
    "lighthouse",
    "mansion",
    "observation deck",
    "botanical",
    "library",
    "music venue",
    "farm",
]

MIN_PLACE_REVIEWS = 20  # drop places with fewer reviews (too little signal)
MIN_USER_REVIEWS = 8  # drop users with fewer reviews
N_TEST = 2  # each user's last 2 visits -> test set
N_VAL = 1  # the visit before those -> validation set
POSITIVE_RATING = 4  # a held-out visit counts as "relevant" if rated >= 4
K = 5  # we evaluate the top-5 list (NDCG@5)
N_EVAL_USERS = 2000  # evaluate on at most this many users (keeps it laptop-friendly)
SEED = 42


def dataset_state():
    """Which dataset is in data/processed right now (written by scripts/01_prepare_data.py)."""
    return json.loads((DATA_PROCESSED / "dataset_info.json").read_text())["state"]


def results_dir():
    """Practice (FAKE) results go to results/practice/, which Git ignores; real ones to results/."""
    path = RESULTS / "practice" if dataset_state() == "FAKE" else RESULTS
    path.mkdir(parents=True, exist_ok=True)
    return path
