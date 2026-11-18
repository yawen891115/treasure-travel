"""Text-query cold-start serving, distinct from the offline personalized ALS experiment.

These hand-set query weights are not the validation-tuned personalized ranking model.
No user identity/history is supplied by the chat interface, so no ALS benefit is claimed here.
"""

import difflib

import joblib
import numpy as np
import pandas as pd
from scipy import sparse
from sklearn.preprocessing import normalize

from src import config
from src.constraints import estimate_cost, estimate_travel_minutes, is_open, parse_hours
from src.ranker import zscore_items

QUERY_WEIGHTS = {"match": 1.0, "pop": 0.15, "rating": 0.10}


class PlaceIndex:
    def __init__(self, artifacts_dir=config.ARTIFACTS, processed_dir=config.DATA_PROCESSED):
        self.places = pd.read_parquet(processed_dir / "places.parquet")
        self.vectorizer = joblib.load(artifacts_dir / "tfidf_vectorizer.joblib")
        self.place_matrix = sparse.load_npz(artifacts_dir / "place_tfidf.npz")
        stats = np.load(artifacts_dir / "item_stats.npz")
        self.pop_z = zscore_items(stats["popularity"])
        self.rating_z = zscore_items(stats["rating"])
        self.hours = [parse_hours(h) for h in self.places["hours"]]
        self.by_id = {gid: i for i, gid in enumerate(self.places["gmap_id"])}

    def find_by_name(self, name):
        """Look a place up by (part of) its name, e.g. 'RISD Museum'. Returns describe() or None."""
        names = self.places["name"]
        exact = names[names.str.lower() == str(name).strip().lower()]
        if len(exact):
            return self.describe(int(exact.index[0]))
        hits = names[names.str.contains(str(name).strip(), case=False, regex=False)]
        if len(hits):
            return self.describe(int(hits.index[0]))
        close = difflib.get_close_matches(str(name), names.tolist(), n=1, cutoff=0.6)
        return self.describe(int(names[names == close[0]].index[0])) if close else None

    def describe(self, item):
        row = self.places.iloc[item]
        return {
            "place_id": row["gmap_id"],
            "name": row["name"],
            "categories": row["categories"],
            "price_level": row["price"] or "unknown",
            "est_cost_per_person": estimate_cost(row["price"], row["categories"]),
            "lat": round(float(row["lat"]), 5),
            "lng": round(float(row["lng"]), 5),
        }

    def search(
        self,
        query,
        near=None,
        max_minutes=None,
        mode="walk",
        k=8,
        exclude=(),
        weekday=None,
        start_min=None,
        visit_min=60,
    ):
        """Rank places for a text query; optionally only places near a point / open at a time."""
        if k <= 0:
            return []
        q = normalize(self.vectorizer.transform([query]))
        match = (self.place_matrix @ q.T).toarray().ravel()  # cosine similarity, 0..1
        # Relevance first; popularity and rating only break near-ties. These weights are set by
        # hand: we have no labelled query->place data to tune them on (the survey/likes can help).
        w = QUERY_WEIGHTS
        score = (
            w["match"] * match / (match.max() + 1e-9)
            + w["pop"] * np.clip(self.pop_z, -2, 2)
            + w["rating"] * np.clip(self.rating_z, -2, 2)
        )
        excluded = {self.by_id[p] for p in exclude if p in self.by_id}
        results = []
        for item in np.argsort(-score):
            if item in excluded or match[item] <= 0:
                continue
            if near is not None and max_minutes is not None:
                minutes = estimate_travel_minutes(
                    near[0],
                    near[1],
                    self.places["lat"].iat[item],
                    self.places["lng"].iat[item],
                    mode,
                )
                if minutes > max_minutes:
                    continue
            if weekday is not None and start_min is not None:
                if is_open(self.hours[item], weekday, start_min, start_min + visit_min) is False:
                    continue
            results.append(self.describe(item))
            if len(results) == k:
                break
        return results
