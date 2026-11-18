# Live-data deployment candidate

This upgrade is implemented and locally tested with provider mocks. It is **not publicly deployed**, not App Store published, and not live-provider certified. Previous Boston benchmark results remain offline historical results, not results of this upgrade.

## Maps changes

`agent/maps.py` no longer writes indefinite Google hours/routes caches. Live checks require a verified catalog-ID→Google Place-ID JSON file (`GOOGLE_PLACE_IDS_FILE`), a server-side `GOOGLE_MAPS_API_KEY`, and an explicit `date` (YYYY-MM-DD) within today through six days ahead in America/New_York. Unknown identities are not guessed from fuzzy search. Place Details requests `currentOpeningHours,businessStatus`; dated intervals incorporate special hours and clip overnight carry-over. Missing data, closed businesses, failed routes, timeouts and API errors are not replaced with offline guesses. Routes are freshly fetched estimates, **not live traffic forecasts or guaranteed travel times for the trip date**. There is no content persistence in this adapter.

Each LLM turn gets an isolated adapter and a 40-request ceiling. This is a request bound, not a monetary/monthly budget. Google Cloud quotas and a separately approved spending limit are still required. Provider errors are redacted, redirects disabled, HTTP connect/read timeouts bounded. `agent/tools.py` requires successful constraint validation before accepting a live itinerary. Tool preferences now accept an explicit ISO date.

Catalog candidates still come from historical Boston public data; this is **live verification of an existing catalog**, not a complete current-business discovery engine. Costs remain historical-category heuristics, not merchant quotes. Manually verified mappings are deliberately required to avoid silently checking the wrong location. No raw provider keys belong in mobile code, browser bundles, logs or Git.

## Activation checklist (not performed)

1. Choose hosting and domain and approve any recurring charges. Use backend worker's deployment guide, Redis, HTTPS, production secret and authenticated access. No public deployment has been authorized/performed here.
2. Create/choose a Google Cloud project with billing; enable Places API (New) and Routes API. Restrict the server key to required APIs and, where supported, the server's fixed outbound IP. Set quotas, alerts and operational monitoring. Alerts alone do not cap spend.
3. Put secrets in host secret storage. Set `MAPS_MODE=google` and `AGENT_BACKEND=claude`, configure an explicitly chosen `LLM_MODEL` and `ANTHROPIC_API_KEY`. Do not send API keys in chat.
4. Prepare a small verified mapping file, e.g. `{ "historical_catalog_id": "verified_Google_place_id" }`. Place IDs, unlike other Google content, are exempt from normal caching restrictions. Verify each business/location before enabling it.
5. Publish operator-specific Privacy Policy and Terms; implement required Google attribution. If Places data is drawn on a map it must be a Google Map, not an Apple Map. Review provider requirements before distribution.
6. Run a capped live smoke test with an approved budget, then validate production HTTPS, login/logout, Redis controls, schema/errors, backups and restoration, observed API charges, current holidays/closed businesses and operational monitoring. These stages remain unverified without credentials/deployment access.

## Cost/source notes

Official documentation checked during upgrade:
- [Places data fields](https://developers.google.com/maps/documentation/places/web-service/data-fields): currentOpeningHours triggers Place Details Enterprise.
- [Pricing](https://developers.google.com/maps/billing-and-pricing/pricing): listed Enterprise Details pricing is $20 per 1,000 requests after 1,000 monthly free usage; quotas/region/account terms may affect the actual bill. Routes and LLM calls are additional.
- [Places policies](https://developers.google.com/maps/documentation/places/web-service/policies): caching and attribution restrictions, public privacy/terms requirements.
- [Places reference](https://developers.google.com/maps/documentation/places/web-service/reference/rest/v1/places): current hours cover next seven days including today and special hours.

Do not multiply old 200-request offline benchmarks by these prices as a claim of observed cost: no live calls were made. Do not label this production-ready until the activation and deployment acceptance checks pass.

## Additional integrity fixes

The agent ignores all further tool actions in a response batch once a validated itinerary is accepted, preventing a later preference update from invalidating the already-approved budget/date. Fractional group sizes are rejected rather than rounded inconsistently. Tests include provider failures, date-window enforcement, verified-ID absence, closed businesses, dated special/overnight hours, route parsing, call ceilings, request isolation, live submission rejection, and the actual mocked HTTP path through ToolBox.

Manual mapping is trusted operator configuration, not automatic identity verification. Review addresses/coordinates before adding a mapping; the code does not independently prove two records represent the same business.

## Final local verification and rollout order

- Python suite: 75 passing tests; Django/security suite: 25 passing tests, including Redis Lua exercised with fakeredis. Lint and Python compilation pass.
- Actual localhost HTTP workflow: session/CSRF, offline Boston itinerary generation, feedback and reset pass after upgrade. This is a no-key fallback demonstration, not live Google/Claude verification.
- iOS sources in `mobile/`: worker verified six tests, TypeScript check, Expo dependency check and iOS-target JavaScript bundle export. No native iPhone binary, physical-device test, TestFlight upload or App Store review occurred.
- Container/Caddy/TLS/real Redis not run here because Docker is unavailable. See `DEPLOYMENT.md` for acceptance gates, session API, backups and operator retention.

Recommended sequence: (1) agree private staff pilot host/domain and budget; (2) provision credentials in secret storage and verify a small Boston Place-ID mapping; (3) deploy backend to private staging, test real Redis/TLS/login and a capped live trip; (4) connect iPhone build to staging and test native cookies/CSRF/foreground-background/logout; (5) finish operator privacy/terms, screenshots, icons, support and account/data-deletion behavior; (6) enroll/configure Apple account, signing and bundle ID, then build/TestFlight/submit only after release approval. An Expo JS export is not step6.
