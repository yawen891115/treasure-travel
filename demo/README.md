# Treasure Travel demo

A one-page Boston trip planner with an optional Claude agent behind it.

| Path | What it is |
|---|---|
| `index.html` | The built page. Deploy this single file to any static host. |
| `src/core.js` | 38 Boston places, walking estimate, schedule validator, TF-IDF text matching, beam-search planner and rule-based request parser. Shared by the page and the agent. |
| `src/app.js`, `src/charts.js`, `src/styles.css`, `src/template.html` | Page source: chat, map, itinerary, plan checks and the "How it works" charts. |
| `agent/` | Cloudflare Worker. `agent.js` runs the tool-calling loop, `anthropic.js` calls the Messages API, `maps.js` adds optional Google Routes walking times, `index.js` handles HTTP, CORS and request limits. |
| `test/` | Node tests. They use a scripted model, so no API key is needed. |
| `build.mjs` | Inlines Leaflet, the Overpass font, CSS and JS into `index.html`. |

## Develop

```bash
npm install
npm test
npm run build                                   # rule planner only
npm run build -- --api=https://<agent-url>      # page sends typed requests to the agent
```

## How the agent plans

Claude gets the catalog, the traveler's constraints, the current itinerary and the conversation so far, plus five tools:

| Tool | What it does |
|---|---|
| `search_places` | Ranks places for a free-text wish, interests, price and walking distance. |
| `walk_time` | Walking minutes between two places, from Google Routes when configured, otherwise the estimate. |
| `update_constraints` | Applies changes the traveler asks for (time, budget, group, walk limit, stops, interests, start point). |
| `check_itinerary` | Simulates an ordered plan and lists every violation: closed on arrival, past the finish time, over budget, leg too long, removed or missing kept stops. |
| `submit_itinerary` | Re-checks the plan. Violations go back to the model as an error result to fix; an accepted plan ends the turn. |

If no plan is accepted within `MAX_ROUNDS` model calls, the rule planner answers and the response says so (`fallback: true`). The response includes the tool trace, token usage and the validated schedule, and the page shows them under "How the agent built this plan".

## Deploy the agent

```bash
npx wrangler secret put ANTHROPIC_API_KEY
npx wrangler secret put GOOGLE_MAPS_API_KEY     # optional; each Routes call is billed by Google
npx wrangler deploy
```

Then rebuild the page with the Worker URL and upload `index.html` to the static host. Set `ALLOWED_ORIGINS` in `wrangler.toml` to the page's origin.

| Setting | Default | Purpose |
|---|---|---|
| `MODEL` | `claude-haiku-5-5` | Model ID |
| `ANTHROPIC_VERSION` | `2026-10-21` | API version header |
| `MAX_ROUNDS` | `8` | Model calls per request |
| `MAX_TOKENS` | `1024` | Output tokens per model call |
| `ALLOWED_ORIGINS` | demo site | Comma-separated origins allowed to call the agent |
| `PER_IP_PER_HOUR` / `DAILY_LIMIT` | `20` / `300` | Request caps; bind the `RATE_KV` namespace so they hold across Worker instances |

Request caps limit traffic, not money. Set a monthly spend limit in the Anthropic Console as the hard cap.

## Data notes

The places are real Boston landmarks at approximate coordinates. Opening hours, prices and visit lengths are estimates written for the demo. Walking time is the straight-line distance at 4.5 km/h with a 1.3 street factor, unless Google Routes times are configured. The benchmark numbers in "How it works" come from `../results/`.
