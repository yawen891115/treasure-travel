# Private, staff-only deployment pilot

This package is deployment-capable scaffolding, **not a claim of production certification**.
It has not been publicly deployed. Docker build/real Redis/real TLS/provider credentials must be
verified on the target host before rollout. The intended initial scope is a small private pilot,
not an anonymous public consumer service.

## Safety boundaries

- Claude or Google mode requires an authenticated, active Django **staff** account for chat and
  feedback. Accounts are operator-created; there is no public signup. Do not grant staff access
  casually: it is also Django's admin-site access flag (model permissions remain separate).
- Browser and native clients use server-side session cookies and CSRF. No API keys or shared
  bearer secret are shipped in the app. Login failures are generic. Session lifetime is 12 hours.
- Shared Redis Lua admission controls enforce per-user (anonymous: direct-peer IP) rolling
  request rate, one in-flight request per identity, and a global in-flight cap. Login has a
  separate rate bucket, including Django admin login. Redis failure returns 503, not unlimited
  access. Rejected requests return 429 with `Retry-After`.
- Production **requires** Redis and enabled limits. The local in-memory limiter is single-process
  development only. Redis is not exposed on a host port. Protect the trusted container network;
  remote Redis requires network access controls and TLS/authentication.
- Lease expiry is 180 seconds; sync Gunicorn worker timeout is 120 seconds. Keep worker timeout
  below lease expiry when changing infrastructure. Leases prevent stale releases freeing another
  request. On worker failure, slots recover by expiry. On Redis restart, rate state resets.
- Admission limits are **not a dollar-spending cap**. Set provider account budgets/alerts and
  restrict credentials. A single request can make several model/tool calls.
- Do not trust arbitrary `X-Forwarded-For`. The app uses direct peer IP for anonymous limits;
  behind Caddy this may group clients together. Add edge rate limits/WAF before broad exposure.
- Google mode does not save replies, itineraries, preferences or conversation history to database
  or sessions. It is stateless across turns: provide complete trip facts each time. Do not enable
  request-body logging or persist provider responses on mobile. Outputs remain transient in the UI.
- Offline mode still stores chat and preference history; operator must define retention/deletion
  and backups before collecting real users' data. Avoid sensitive data during the pilot.
- Budget is a heuristic estimate, not a Google-provided price quote. Google route duration is a
  fetched estimate, not a traffic forecast. Catalog records are historical. Upcoming dated hours
  and manually verified Google Place IDs are required for live checks; see `LIVE_UPGRADE.md`.

## Prepare artifacts first

The code ZIP does not necessarily include trained artifacts or processed datasets. Run the documented
preparation/ranking pipeline using the desired Boston city-proper dataset, and verify that
`artifacts/` and `data/processed/` contain matching versions. The server mounts both **read-only**.
Never load untrusted pickle/joblib artifacts: loading these formats executes Python deserialization.
Back up the SQLite volume separately from these artifacts.

## Local demo (no API key required)

1. Create `.env` from `.env.example`, leave keys empty, set `AGENT_BACKEND=offline`, `MAPS_MODE=offline`.
2. Generate/prepare matching artifacts as in README.
3. `docker compose build`
4. `docker compose run --rm web python web/manage.py migrate --noinput`
5. `docker compose up`
6. Open `http://127.0.0.1:8000`. Local Compose binds only loopback, not a public interface.

## Private HTTPS host

Do not run these steps until a host/domain and any costs have been explicitly approved.

1. Set `APP_DOMAIN` to the DNS name and point DNS at the host. Restrict firewall ingress to intended
   clients or a private access gateway during the pilot. Only Caddy publishes 80/443.
2. Generate a fresh random Django secret (do not use an example), then configure `.env`:
   - `DJANGO_DEBUG=0`
   - `DJANGO_SECRET_KEY=<at least 50 random characters>`
   - `ALLOWED_HOSTS=your.domain,localhost,127.0.0.1` (loopback is needed by container health probe)
   - `CSRF_TRUSTED_ORIGINS=https://your.domain`
   - `APP_DOMAIN=your.domain`
   - Set backend/model/key only after verifying account access and spending limits.
   - Compose supplies the internal `REDIS_URL` and `BEHIND_HTTPS_PROXY=1`.
3. For Google mode, use `AGENT_BACKEND=claude`, an explicit valid `LLM_MODEL`, restricted
   `GOOGLE_MAPS_API_KEY`, and `GOOGLE_PLACE_IDS_FILE=/app/secrets/place_ids.json`.
   Add a read-only mount of your verified mapping file to that path in the HTTPS Compose file.
   Offline planner + Google mode is intentionally rejected because it cannot bind trip dates safely.
4. `docker compose -f docker-compose.https.yml build`
5. `docker compose -f docker-compose.https.yml run --rm web python web/manage.py migrate --noinput`
6. `docker compose -f docker-compose.https.yml run --rm web python web/manage.py createsuperuser`
   Use a strong password. For ordinary pilot accounts create users with staff status but **without**
   superuser status or unnecessary model permissions.
7. `docker compose -f docker-compose.https.yml run --rm web python web/manage.py check --deploy`
8. `docker compose -f docker-compose.https.yml up -d`
9. Verify HTTPS, sign-in, CSRF rejection, anonymous paid denial, authorized planning, 429/503 limits,
   restart recovery, and both health endpoints. Do not infer success merely from a running container.

The app container is non-root, read-only except its named SQLite volume and `/tmp`, has no Linux
capabilities, and cannot elevate privileges. Caddy obtains certificates using its data/config volumes.
The web port is internal only in HTTPS Compose. **Never directly expose web behind an untrusted proxy**
when `BEHIND_HTTPS_PROXY=1`, since that setting trusts the overwritten scheme header.

## Health, operations, and limitations

- `GET /healthz`: process liveness; no model initialization or paid calls.
- `GET /readyz`: database connectivity, cache round-trip and required artifact presence; returns 503
  if unavailable. Checks mapping-file presence in Google mode. It does not authenticate provider keys,
  check file semantic compatibility, or prove live API quotas are available.
- SQLite supports this single-host pilot. Back up `web_data` using SQLite's online backup mechanism
  or stop writers first; test restoration. Do not run multiple hosts against a shared SQLite file.
  Migrate to PostgreSQL with tested migrations/backups before multi-host scaling.
- Run migrations as a separate release step, not simultaneously from every worker. Roll back code
  and artifacts together; take a DB backup before irreversible schema migrations.
- Pin image digests/dependency lockfiles, scan vulnerabilities, configure monitoring, data retention,
  cost alerts and incident response before broader rollout. Current base-image tags are movable.
- HSTS starts at one hour without subdomain/preload to avoid irrevocable domain mistakes. Review it
  with the domain owner before extending it.

## Native/mobile session contract

1. `GET /api/session` with cookie handling → `authenticated`, `paid_access`, `csrf_token`, `data_source`.
2. `POST /api/login` JSON `{username, password}` plus `X-CSRFToken` from step 1 and same cookie jar.
3. On successful login, replace CSRF token with the returned rotated token. Do not store passwords.
4. On HTTPS, native mutations must also send `Origin: <configured HTTPS backend origin>` (or a
   matching HTTPS Referer); a CSRF token alone does not bypass Django’s secure-origin check.
   All mutating endpoints (`/api/chat`, `/api/feedback`, `/api/reset`, `/api/logout`) require CSRF.
5. `POST /api/logout` clears authentication and returns a fresh session/CSRF state.
6. `data_source.maps_mode` describes configuration, not blanket verification of every output.
   Display Google Maps attribution/link when supplied; preserve uncertainty warnings and estimates.
   With `history_persisted=false`, keep provider output transient and include full facts next turn.

Native cookie behavior and release builds still require real-device testing. HTTPS is mandatory for
production; do not disable transport security to bypass a misconfigured server.

## Tests

`pip install -r requirements-security-test.txt` enables actual Lua evaluation with fakeredis, not
merely mocked Redis calls. `cd web && python manage.py test planner` includes session/CSRF, permissions,
rate/concurrency, stale-lease safety, fail-closed cache behavior, retention and readiness regressions.
This emulator is not a replacement for smoke testing a real Redis service and the Docker network.

### Retention operations

Preview: `python web/manage.py purge_planner_logs --days 30` (no deletion).
After operator approval and backup/retention review, add `--apply` to permanently remove old
TripLog and PlaceFeedback rows. Also run Django `clearsessions` for expired sessions. These commands
are not scheduled by the application; configure an approved recurring job before collecting real data.
A user's New trip/Sign out button does not delete historical database logs.

Client timeout/disconnection is not cancellation of an in-flight provider call and may still incur
cost. Inspect request/provider logs before retrying an uncertain result; never promise a client
cancel operation stops billing.
