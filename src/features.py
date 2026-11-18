"""The three baseline factors: popularity, rating and TF-IDF preference match.

All factors are computed from TRAIN visits only, so nothing from the future leaks in.
"""

import numpy as np
from scipy import sparse
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import normalize

from src import config


def popularity(train, n_items):
    """log(1 + number of train visits) for every place."""
    counts = np.bincount(train["item_idx"], minlength=n_items)
    return np.log1p(counts).astype(np.float32)


def bayesian_rating(train, n_items, m=10.0):
    """Average rating, pulled toward the global mean when a place has few reviews.

    score = (sum of ratings + m * global_mean) / (number of ratings + m)
    """
    global_mean = train["rating"].mean()
    sums = np.bincount(train["item_idx"], weights=train["rating"], minlength=n_items)
    counts = np.bincount(train["item_idx"], minlength=n_items)
    return ((sums + m * global_mean) / (counts + m)).astype(np.float32)


def place_documents(places):
    """Text that describes each place: its categories (twice, they matter most) + description."""
    return (
        places["categories"] + ". " + places["categories"] + ". " + places["description"]
    ).tolist()


def fit_tfidf(places):
    vectorizer = TfidfVectorizer(
        stop_words="english", ngram_range=(1, 2), min_df=2, sublinear_tf=True
    )
    place_matrix = vectorizer.fit_transform(place_documents(places))  # shape: places x words
    return vectorizer, normalize(place_matrix)


def user_profiles(train, place_matrix, n_users):
    """A user's taste = average TF-IDF vector of the places they liked (rating >= 4).

    Users who liked nothing fall back to all the places they visited.
    """
    liked = train[train["rating"] >= config.POSITIVE_RATING]
    rows, cols = liked["user_idx"].to_numpy(), liked["item_idx"].to_numpy()
    missing = np.setdiff1d(np.arange(n_users), np.unique(rows))
    if len(missing):
        extra = train[train["user_idx"].isin(missing)]
        rows = np.concatenate([rows, extra["user_idx"].to_numpy()])
        cols = np.concatenate([cols, extra["item_idx"].to_numpy()])
    user_item = sparse.csr_matrix(
        (np.ones(len(rows)), (rows, cols)), shape=(n_users, place_matrix.shape[0])
    )
    profiles = user_item @ place_matrix  # sum of liked place vectors
    return normalize(profiles)  # length 1, so dot product = cosine similarity


def tfidf_match(profiles, place_matrix, users):
    """Cosine similarity between each user's taste and every place: matrix users x places."""
    return (profiles[users] @ place_matrix.T).toarray().astype(np.float32)
