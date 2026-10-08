## Run everything with Docker

Only Docker (with Compose) and a `.env` file are needed. Copy `.env.example` to
`.env` using your editor or file manager. Leave `OPENAI_API_KEY` blank for offline
use. Do not copy production credentials into the development example.

```bash
docker compose up
```

The first run builds the service, waits for healthy Postgres + pgvector, applies
idempotent schema initialization, refreshes approved content with hash-diff ingestion,
and serves **http://localhost:8000/demo.html?mode=live** and `/widget.js`.
Repeat starts refresh changed/removed content without re-embedding unchanged chunks.
`/health` reports readiness and chunk count. Use `docker compose up -d --build --wait`
for a background stack; use `--build` after changing application code or content.

The default service uses fake providers and never receives `OPENAI_API_KEY`.
Its answers say `stub answer`: this validates integration, not answer quality.
The local demo's public `pk_demo` key and local browser origins are always included
in development, alongside the keys/origins in `.env`. Development uses a limit of
100 requests/minute; production reads its explicit configured limit.
The catalogue and unreviewed content remain disabled in every supplied stack.
Postgres stays internal; the API binds to localhost. The demo without `?mode=live`
uses an offline browser mock. `/chat` request/response fields are unchanged.

Run checks from a second terminal (each command builds its own test image):

```bash
# Python suite against an isolated rh_test database in Compose Postgres.
docker compose --profile test run --build --rm pytest
# Playwright desktop/mobile suite against the running Compose API.
docker compose --profile test run --build --rm playwright
```

The Playwright runner derives from Microsoft's official Playwright image, with the
matching Node package installed inside it. Python browser tests skip in the small
pytest image; the separate Playwright command runs the browser checks without skips.
Tests create their own databases, and pytest wipes only `rh_test`; the demo index
is preserved. The browser suite includes real API ingestion, retrieval, EN/AR,
conversation isolation, hostile responses, retry/error handling and actual 429s.
Run checks sequentially. The browser test exhausts its own client IP's rate limit;
allow one minute before an immediate repeat if Docker reuses that IP.
Results persist in named `pytest-results` and `browser-results` volumes.

Real models and paid checks require `OPENAI_API_KEY` in `.env` and the real profile:

```bash
# Explicit target avoids starting paid test jobs along with the service.
docker compose --profile real up -d --build --wait api-real
# Real demo: http://localhost:8001/demo.html?mode=live
# Paid five-case browser grounding smoke, isolated rh_smoke DB.
docker compose --profile real run --build --rm real-smoke
# Paid 14-case evidence-aware quality evaluation, isolated rh_quality DB.
docker compose --profile real run --build --rm quality
```

Real providers use a separate Postgres volume/database from fake embeddings.
Smoke and quality flags are set only in the real-profile jobs; ordinary pytest
explicitly disables all paid checks. The quality command exits nonzero on failed
citations or grounding verdicts; it does not relax expectations. Reports persist
in `smoke-results` and `quality-results` volumes. To export them without host Python:

```bash
docker compose --profile test run --rm --no-deps --entrypoint tar pytest -C /results -cf - . > pytest-results.tar
docker compose --profile test run --rm --no-deps --entrypoint tar playwright -C /results -cf - . > browser-results.tar
docker compose --profile real run --rm --no-deps --entrypoint tar real-smoke -C /results -cf - . > smoke-results.tar
docker compose --profile real run --rm --no-deps --entrypoint tar quality -C /results -cf - . > quality-results.tar
```

Use a binary-safe shell for archive redirection (PowerShell 7.4+ or Bash).
For clean-state verification, stop any older Rabbit Hole stack occupying port 8000,
then run `docker compose --profile test --profile real down -v` (deletes this stack's
DBs and reports), followed by the start and test commands above. Do not use `down -v`
on production data. Current verification status: [Docker verification](docker-verification.md).

## Production with Docker

Copy `.env.production.example` to `.env.production`, fill all required settings,
and keep it private. Use a URL-safe strong `POSTGRES_PASSWORD` because Compose
uses it in the database URL. No development key, origin, password or fake provider
is supplied by this standalone file:

```bash
docker compose --env-file .env.production -p rh-production -f docker-compose.production.yml up -d --build --wait
```

Startup requires `OPENAI_API_KEY`, `POSTGRES_PASSWORD`, `ADMIN_TOKEN`, `SITE_KEYS`
and `ALLOWED_ORIGINS`. The API runs as the non-root `rag` user, has an HTTP health
check, uses one worker, and both services restart unless stopped. `/demo.html`
is unavailable with `ENV=production`; `/widget.js` remains available.
Put a HTTPS reverse proxy in front of the localhost API. Set `TRUST_PROXY=true`
only when your own proxy overwrites forwarded headers. Secrets are runtime
variables; `.env*` files are excluded from image build context and secret files
are git-ignored. No secrets are supplied as build arguments or copied into layers.

Embed the widget on an allowed origin:

```html
<script src="https://YOUR-SERVICE/widget.js?v=1" data-api="https://YOUR-SERVICE"
        data-site-key="YOUR_PUBLIC_PRODUCTION_SITE_KEY" defer></script>
```

The widget sends the public site key, message, language and last server-issued
conversation ID. EN and AR have separate transcripts and conversation IDs.
The older `docker-compose.dev.yml` remains an isolated offline compatibility stack;
`docker-compose.staging.yml` is a legacy staging template. Use the production file
above for the hardened production configuration.



## Measuring a scoped real-provider verification

Use `--env-file .env -f docker-compose.yml -f docker-compose.verify.yml` with the
real commands above to select the official OpenAI endpoint, disable api-real visitor
ports/history, and capture local metadata-only usage logs. `api-real` is checked
inside its container in this mode; localhost:8001 is intentionally unavailable.
Stop api-real after checking startup. Smoke and quality reports/usage logs remain
in their named result volumes. `OPENAI_USAGE_LOG` is opt-in and never records
request bodies, answers or credentials.

The completed run is in [Docker verification](docker-verification.md): 56 OpenAI
requests, about $0.0167 at standard public rates, five-case smoke passed, and quality
13/14 overall with 14/14 grounding. The outstanding case-1 citation requirement was
not changed. Cost sources and token counts are in
[usage-summary.md](docker-real-results/usage-summary.md).
