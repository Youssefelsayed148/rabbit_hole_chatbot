# Staging deployment checklist

The owner will deploy on a VPS. The server and HTTPS domain still need to be configured.
Confirm that the selected hosting plan supports a persistent Python/container service, outbound
OpenAI requests, and Postgres with pgvector. An ordinary static/PHP hosting plan is insufficient
unless the RAG service and database are hosted separately.

## Before deployment

- [ ] Choose hosting, the service HTTPS origin, and the exact website origins (EN/AR may share one origin).
- [ ] Review `quality-results.md`: case 1 currently fails expected citation coverage; resolve or explicitly review before launch. Do not lower the eval requirement to hide it.
- [ ] Approve Arabic content/UI with the review pack. Keep the shipping/payments draft excluded.
- [ ] Rotate the previously exposed LLM token; keep the new OpenAI key and admin token in backend secrets only.
- [ ] Copy `.env.production.example` into the hosting secret store or ignored `.env.production`.
- [ ] Set `ENV=production`, `OPENAI_API_KEY`, a random `ADMIN_TOKEN`, `SITE_KEYS`, `ALLOWED_ORIGINS`, and `DATABASE_URL`.
- [ ] For the optional container template, set a strong `POSTGRES_PASSWORD`. Use a random hex/alphanumeric password to avoid DSN URL-encoding issues. It overrides `DATABASE_URL` with its private `db` service address.
- [ ] Use `CATALOGUE_ENABLED=true` for the verified public shop adapter; keep `INCLUDE_UNREVIEWED=false`, `LOG_MESSAGES=false`.
- [ ] Set `CHAT_API_KEY` to the OpenRouter key. The production template uses the tested free Gemma setup with explicit free fallbacks. `OPENAI_API_KEY` is still required for embeddings. Confirm model IDs/account access, token budget, timeout and embedding dimensions. A different dimension needs a fresh database; never reuse a fake-embedding index for real embeddings.
- [ ] Decide message retention and whether to set `STORE_MESSAGES=false`; configure backups for the persistent database.

`SITE_KEYS` is a comma-separated list of public widget keys. The script's `data-site-key`
must exactly match one entry. It is not the OpenAI key or admin token. Keys can overlap during rotation.
`ALLOWED_ORIGINS` is a comma-separated list of exact HTTPS origins, with no path, wildcard or
trailing slash. Include `www`/non-`www` separately only if both serve the site; do not guess them.
An empty list denies browser origins, and production startup requires a nonempty list.
`SOURCE_BASE_URL` is optional; set it to the owner-confirmed citation origin once known.

The template lists all deployment-relevant settings: models, dimensions, timeouts, API access,
content flags, limits, retention and logging. `DATA_DIR`, `TOP_K` and `FINAL_K` are optional tuning
settings; defaults use the bundled content and current retrieval settings. No tuning is needed to deploy.

## HTTPS and proxy

- [ ] Terminate valid, publicly trusted HTTPS at the chosen reverse proxy; redirect public HTTP to HTTPS.
- [ ] Serve the widget and `/chat` under the same service HTTPS origin. Avoid mixed content and API redirects.
- [ ] Expose only the proxy publicly; keep port 8000 and the database private. The optional Compose template binds 8000 to host loopback.
- [ ] Forward `Host`, `Origin`, `Content-Type`, `X-Site-Key` and OPTIONS requests unchanged. Do not synthesize wildcard CORS headers or cache POST responses.
- [ ] Preserve `/widget.js` cache headers and JavaScript content type. Do not make `/demo.html` public from another static server: FastAPI hides it outside development, but the file is present in the image.
- [ ] Set proxy read timeout above the backend's OpenAI timeout/retry budget. Verify the widget's 45-second timeout remains suitable; slow responses may need a later timeout adjustment.
- [ ] Use a single uvicorn worker. Current rate/daily counters are process-local and reset on restart.
- [ ] Set `TRUST_PROXY=true` only after the proxy overwrites incoming `X-Forwarded-For` with a trusted client address. For a single direct proxy, forward its actual client IP, not an untrusted caller-supplied chain. Configure trusted upstream/CDN IPs explicitly if there is more than one hop.
- [ ] Configure uvicorn's `FORWARDED_ALLOW_IPS` to only trusted proxy addresses; never use `*` on a directly reachable backend.
- [ ] Keep admin endpoints accessible only to the operator through a trusted route and bearer token.

For a host that supports Docker Compose, the optional standalone template is:

```bash
docker compose --env-file .env.production -f docker-compose.staging.yml config --quiet
docker compose --env-file .env.production -f docker-compose.staging.yml up -d --build
```

These are operator commands, not a recommendation for a hosting provider. On another platform,
use the same Dockerfile/env settings and that platform's private database/network/HTTPS facilities.
Do not print or commit resolved Compose configuration containing secrets.

## Verify after the operator deploys

- [ ] `/health` returns `ok` and approved content is ingested; refresh via authenticated `/admin/ingest` if necessary.
- [ ] Run the checker below from a machine with `requirements-dev.txt` installed.
- [ ] Confirm valid and invalid site keys, allowed and denied origins, cache policy, production demo hiding and real EN/AR retrieval.
- [ ] Test the live site's script integration using `live-site-checklist.md`, then run `device-results.md`.
- [ ] Record the deployed revision, date, service URL, site origins and check output below.

```powershell
$env:STAGING_SITE_KEY='PUBLIC_WIDGET_KEY'
python -m scripts.check_staging https://SERVICE_HOST --allowed-origin https://SITE_HOST
```

```bash
STAGING_SITE_KEY=PUBLIC_WIDGET_KEY python -m scripts.check_staging https://SERVICE_HOST --allowed-origin https://SITE_HOST
```

The checker verifies TLS (certificate validation stays enabled), widget/cache headers, demo 404,
allowed/denied CORS preflight, site-key enforcement, and EN/AR chat schema. It sends greetings,
which exercise the HTTP/security contract without model calls; verify real retrieved answers separately.
It makes no deployment or admin changes. No redirects are followed.

| Deployment / verification field | Result |
|---|---|
| Hosting / revision / date | |
| Service HTTPS URL | |
| Exact website origins | |
| Checker exit code / output location | |
| Approved-content health / real retrieved answer | |
| Remaining issue / owner | |
