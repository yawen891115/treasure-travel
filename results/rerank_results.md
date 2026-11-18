# Constraint-aware re-ranking

Dataset: **Boston**

Model: D. B + popularity-residualized ALS. Trip moment per user: random weekday, start 09:00-20:00, 60-min visit, last known location, max 25 min by drive.

| | Before re-ranking | After re-ranking |
|---|---|---|
| Top-5 places that are closed, too far or unverified hours | 34.9% | 0.0% |
| Users whose top-5 has at least one such place | 77.8% | 0.0% |
| NDCG@5 against held-out visits | 0.0436 | 0.0394 |
| Average list length | 5.00 | 4.98 |

Places with unknown opening hours (excluded unless a known interval covers the visit): 7.0%
