"""Remove the popularity effect from ALS scores (the 'residual taste' factor).

Same idea as building a momentum factor from CAPM residuals: regress the raw
signal on the known factor and keep only what the known factor cannot explain.

For each user u we fit   score[u, i] = a_u + b_u * log_pop[i] + residual[u, i]
and keep residual[u, i] as the new factor.
"""

import numpy as np


def residualize_on_popularity(scores, log_pop):
    x = log_pop - log_pop.mean()  # centered popularity
    s = scores - scores.mean(axis=1, keepdims=True)  # centered scores, per user
    denom = float(x @ x)
    slope = (s @ x) / denom if denom > 1e-12 else np.zeros(len(s))
    residual = s - np.outer(slope, x)
    return residual.astype(np.float32), slope


def mean_correlation(scores, log_pop):
    """Average (over users) Pearson correlation between a user's scores and log-popularity."""
    x = (log_pop - log_pop.mean()) / (log_pop.std() + 1e-9)
    s = scores - scores.mean(axis=1, keepdims=True)
    s = s / (s.std(axis=1, keepdims=True) + 1e-9)
    return float((s @ x / len(x)).mean())
