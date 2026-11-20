# Treasure Travel

Treasure Travel turns a description of a day in Boston into an editable walking itinerary. The browser demo searches a catalog of 38 places, builds a schedule, and checks it against opening hours, visit lengths, walking limits, budget, and finish time. The repository also contains a Python recommendation benchmark, a Django planner, and an Expo client prototype.

**[Open the Boston demo](https://treasure-travel-boston-demo.brainyraisin5.chatgpt.site)**

Try *“Two people, art and coffee, under $40, back by 4 pm.”* You can pin, remove, or add stops and see the changes on the map. The demo uses approximate coordinates and estimated hours, costs, and walking times.

## Run the browser demo

Use Node.js 18 or later. From the repository root:

```bash
cd demo
npm ci
npm test
npm run build
python -m http.server 8080 --bind 127.0.0.1
```

Open [http://127.0.0.1:8080](http://127.0.0.1:8080). The generated `demo/index.html` embeds the browser code, Leaflet, and fonts. It can be served directly from static hosting. Map tiles load from the network. The default build uses a deterministic browser planner and requires no API keys. An optional [Cloudflare Worker](demo/README.md) connects the demo to Claude tool calling and validates proposed routes before returning them.

## Run the Django planner with sample data

Use Python 3.12. These commands generate a synthetic Providence catalog and the search artifacts Django needs. `--skip-als` lets you run the planner without Java.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt -r requirements-security-test.txt
python scripts/00_make_fake_data.py
python scripts/01_prepare_data.py --state FAKE
python scripts/02_rank_experiments.py --skip-als
AGENT_BACKEND=offline MAPS_MODE=offline python web/manage.py migrate
AGENT_BACKEND=offline MAPS_MODE=offline python web/manage.py runserver
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000) and enter:

```text
Saturday 10:00-18:00, 2 people, budget $100, walk, max 20 minutes,
origin (41.83, -71.41), interests: art and coffee
```

The Django planner ranks places for the current text query and applies the trip constraints. Personalized PySpark ALS is used in the offline ranking experiments. See [DEPLOYMENT.md](DEPLOYMENT.md) for the private-pilot backend configuration and [mobile/README.md](mobile/README.md) for the Expo client.

## Boston recommendation benchmark

The historical benchmark used the UCSD Google Local reviews and Boston's city boundary. After filtering, the dataset contained **2,210 places**, **22,287 reviewers**, and **352,408 interactions**. The experiment trained on **285,547 interactions**, used a per-reviewer chronological split, selected model weights on validation, and evaluated full-catalog ranking on **2,000 held-out reviewers**. Ratings of 4 or 5 counted as relevant, and previously seen places were excluded from ranking.

| Model | Test NDCG@5 | Catalog coverage@5 |
|---|---:|---:|
| Popularity + rating + TF-IDF baseline | 0.0334 | 14.43% |
| Baseline + popularity-residualized ALS, selected on validation | 0.0436 | 23.85% |
| Baseline + raw ALS, ablation | 0.0441 | 24.66% |

On 200 synthetic Boston trip requests, the Python rule planner generated **188 nonempty plans** that satisfied estimated constraints. **66** also met the requested stop count. These measures describe offline feasibility on historical hours and estimated costs. The benchmark uses per-user time splits and a catalog selected from the full observation window, which limits how well these estimates generalize to future traffic.

See the [ranking results](results/ranking_results.md) and [itinerary results](results/offline_rules_results.md). To reproduce the historical runs, install Java 17 or later and review the [UCSD data source](https://mcauleylab.ucsd.edu/public_datasets/gdrive/googlelocal/) and [Boston GIS source](https://gisportal.boston.gov/arcgis/rest/services/Planning/OpenData/MapServer/9) before downloading. The repo includes aggregate results and synthetic examples. Historical datasets, reviewer-level outputs, and trained artifacts are generated locally.

```bash
export TRAVEL_DATASET_ROOT="$PWD/audit/boston"
python scripts/download_public_data.py --state Massachusetts
python scripts/01_prepare_boston.py
SPARK_LOCAL_IP=127.0.0.1 python scripts/02_rank_experiments.py
python scripts/03_rerank_eval.py
python scripts/04_make_test_requests.py --n 200
python scripts/06_eval_offline.py --n 200
```

## Tests

Generate the catalog and search artifacts with either setup above before running the Python and Django suites. The HTTP smoke test launches Django locally and checks itinerary creation, feedback, and session reset over HTTP.

```bash
python -m pytest -q
python web/manage.py test planner
ruff check .
python scripts/smoke_http.py
(cd demo && npm ci && npm test && npm run build)
(cd mobile && npm ci && npm test && npm run typecheck)
```

The optional Claude and Google integrations require provider credentials and separate live validation. The Expo client is a development prototype and needs native-device testing. For data attribution and third-party license details, see [NOTICE.md](NOTICE.md).
