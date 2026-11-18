# Treasure Travel

**An explainable Boston trip-planning demo, recommendation benchmark, and deployment candidate.**

### [Try the public Boston demo →](https://treasure-travel-boston-demo.brainyraisin5.chatgpt.site)

No login, API key or installation is required. Set your time window, group budget, interests and walking limit, then change your preferences and watch the itinerary recalculate.

> **What is live?** The static demo is publicly accessible. Its six authored sample records and operating assumptions are illustrative, not current business data. It runs a real rule-based planner in your browser, not an LLM. The Django/Google/Claude backend and iOS app are separate development candidates, not publicly deployed or App Store published.

## Features

- **Interactive browser demo:** haversine walking estimates, opening-window/time/budget constraints, interest-first greedy selection, partial-plan reporting and follow-up recalculation.
- **Offline recommendation pipeline:** popularity, rating and TF-IDF baseline; PySpark implicit ALS; popularity-residualized ALS; validation-based weight selection and held-out evaluation.
- **Trip-planning backends:** deterministic no-key fallback and optional Claude tool calling with explicit constraint validation.
- **Optional Google verification:** explicit trip dates, current/special opening hours, route estimates, verified Place-ID mappings, bounded calls and fail-closed errors. Provider credentials and live acceptance testing are still required.
- **Django private-pilot API:** session authentication/CSRF, staff-only paid access, Redis rate/concurrency controls, liveness/readiness and retention tooling.
- **iPhone client prototype:** Expo/React Native source using the backend session API. JavaScript export tested; native build and real-device testing remain pending.

## Architecture

```text
Public static demo (independent authored fixtures)
  form + follow-up controls → browser greedy planner → recalculated itinerary

Offline research pipeline (download separately)
  reviews + metadata → Boston boundary / category filters → temporal per-user split
  → TF-IDF + popularity/rating + ALS → validation selection → held-out metrics

Backend candidate
  Django / iPhone client → authenticated session API → planner
  ├─ deterministic offline rules → historical catalog + estimated constraints
  └─ Claude tools → catalog search / Google checks / budget estimate → validator
```

The anonymous serving ranker is a cold-start text-query model. It does **not** silently serve the personalized ALS benchmark model. Google mode verifies a mapped historical catalog; it is not a complete current-business discovery service. Costs are estimates, not merchant quotes.

## Run the public demo locally

Requires Python 3 only; Node.js is optional for demo tests.

```bash
python -m http.server 8080 --directory demo
# Open http://localhost:8080
node demo/test.cjs
```

The single file `demo/index.html` can be deployed unchanged to static hosting. It makes no API calls and needs no data download.

## Run the Python project without API keys

Use Python 3.12 and Java 17+ for Spark. Commands below use a POSIX shell.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -r requirements-security-test.txt
cp .env.example .env

# Generate synthetic practice data; do not confuse these results with the Boston benchmark.
python scripts/00_make_fake_data.py
python scripts/01_prepare_data.py --state FAKE
SPARK_LOCAL_IP=127.0.0.1 python scripts/02_rank_experiments.py
python scripts/04_make_test_requests.py --n 20
python scripts/06_eval_offline.py --n 20

# Launch the no-key Django planner against the generated artifacts.
python web/manage.py migrate
AGENT_BACKEND=offline MAPS_MODE=offline python web/manage.py runserver
# Open http://127.0.0.1:8000
```

No raw data, processed reviewer records, model artifacts, databases or credentials are included. Generate artifacts locally before running the Python planner. `requirements-audit-lock.txt` records the tested audit dependency snapshot; it is not a guarantee that those versions remain free of vulnerabilities.

## Tests

```bash
python -m pytest -q
python web/manage.py test planner
ruff check .
python scripts/smoke_http.py
node demo/test.cjs

# Mobile checks
cd mobile
npm ci
npm test
npx tsc --noEmit
```

Verification at the release snapshot: **75 Python tests and 25 Django/security tests passed**, plus lint, compilation and an actual local HTTP itinerary/feedback/reset flow. Redis Lua was exercised with fakeredis, not a production Redis deployment. Mobile checks and an iOS-target JavaScript export passed; no native iPhone binary, TestFlight or App Store test occurred. CI is configured but a local pass does not establish a hosted CI pass.

## Measured Boston evaluation

Historical UCSD Google Local data were downloaded separately and filtered using the official Boston city boundary. The release includes **aggregate metrics only**, not third-party data.

- 2,210 places, 22,287 reviewers and 352,408 interactions.
- 285,547 training interactions; one validation and two test interactions per reviewer.
- Relevant ratings: 4–5 stars. Final ranking evaluation: 2,000 held-out reviewers, full-catalog candidates with seen items excluded.
- Weights selected on validation, not on test performance.

| Model | Test NDCG@5 | Catalog coverage@5 |
|---|---:|---:|
| Three-factor baseline | 0.0334 | 14.43% |
| Baseline + residual ALS, selected on validation | 0.0436 | 23.85% |
| Baseline + raw ALS, ablation | 0.0441 | 24.66% |

On **200 synthetic requests**, the deterministic Python planner produced 188 nonempty plans satisfying its estimated constraints; **66/200 fulfilled all requested stops**. These are historical-data integration results, not real traveler success rates, live Google accuracy, or LLM performance. Planning and checking share constraints, so feasibility is not an independent recommendation-quality assessment.

Limitations: per-user time splits are not a global chronological split; static metadata and full-corpus catalog/k-core selection limit prospective interpretation. Reviews proxy interactions, not verified trips. See [audit report](AUDIT_REPORT.md) and [aggregate results](results/).

To reproduce the Boston benchmark, first review the source's terms and citation requirements:

```bash
python scripts/download_public_data.py --state Massachusetts
python scripts/01_prepare_boston.py
SPARK_LOCAL_IP=127.0.0.1 python scripts/02_rank_experiments.py
python scripts/03_rerank_eval.py
python scripts/04_make_test_requests.py --n 200
python scripts/06_eval_offline.py --n 200
```

Sources: [UCSD Google Local](https://mcauleylab.ucsd.edu/public_datasets/gdrive/googlelocal/), [official Boston boundary service](https://gisportal.boston.gov/arcgis/rest/services/Planning/OpenData/MapServer/9). Dataset citations: *UCTopic* (Li, Shang, McAuley, ACL 2022) and *Personalized Showcases* (Yan et al., SIGIR 2023). No commercial redistribution rights are asserted.

## Repository map

| Directory / file | Purpose |
|---|---|
| `demo/` | Standalone publicly deployed browser demo and fixture tests |
| `src/` | Data prep, rankers, metrics, constraints and serving |
| `agent/` | Rule planner, LLM tools, map adapters and validation |
| `web/` | Django application, auth, limits and security tests |
| `mobile/` | Expo iPhone client prototype and release checklist |
| `scripts/` | Reproducible preparation, experiments and HTTP smoke test |
| `tests/` | Python regression tests |
| `results/` | Aggregate benchmark results only |
| `DEPLOYMENT.md` | Private-pilot deployment configuration and acceptance gates |
| `LIVE_UPGRADE.md` | Live integration scope, costs and remaining blockers |

## Deployment and safety

The **static demo** needs no backend or credentials. For the full service, follow [DEPLOYMENT.md](DEPLOYMENT.md). Do not expose paid endpoints anonymously. Keep keys server-side, configure quotas and approved spending limits, and complete Google attribution/Privacy/Terms requirements. Alerts and per-turn limits are not hard monetary caps.

Docker/Caddy/TLS/real Redis acceptance tests, live provider tests, vulnerability scanning, backup restoration, public-consumer account/data-deletion flows and native-device testing remain launch gates. The supplied configuration targets a private single-host pilot, not a production-scale consumer service.

## Data and licensing

The demo fixtures are authored illustrative examples and do not contain UCSD review data. Third-party datasets and provider outputs remain subject to their own terms. See [NOTICE.md](NOTICE.md). Public source access does not by itself grant a project-wide open-source license; third-party dependency licenses remain applicable.
