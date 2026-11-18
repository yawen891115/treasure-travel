# Ranking results
Protocol: per-user temporal split, not a global time cutoff. Metadata is a static snapshot; historical availability is not verified.

Dataset: **Boston**

Data: 2,210 places, 22,287 users, 285,547 train visits. Test = each user's last 2 reviews (proxy for visits); relevant = rated >= 4. Evaluated on 2,000 users.

| Variant | Test NDCG@5 | Test Recall@5 | Catalog coverage@5 | Val NDCG@5 | Weights |
|---|---|---|---|---|---|
| A. Popularity only | 0.0311 | 0.0367 | 0.6% | 0.0216 | {'pop': 1.0} |
| B. 3-factor baseline (popularity + rating + TF-IDF) | 0.0334 | 0.0418 | 14.4% | 0.0282 | {'pop': 1.0, 'rating': 0.5, 'tfidf': 0.5} |
| C. B + raw ALS (additive factor) | 0.0441 | 0.0575 | 24.7% | 0.0477 | {'pop': 0.5, 'rating': 0, 'tfidf': 0.5, 'als': 2.0} |
| D. B + popularity-residualized ALS | 0.0436 | 0.0568 | 23.8% | 0.0480 | {'pop': 1.0, 'rating': 0, 'tfidf': 0.5, 'als_resid': 2.0} |
| (reference) raw ALS only | 0.0440 | 0.0578 | 25.3% | 0.0465 | {'als': 1.0} |

- corr(raw ALS, log popularity): 0.213
- corr(residual ALS, log popularity): -0.0
