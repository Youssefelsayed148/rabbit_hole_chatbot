# Rabbit Hole assistant — standalone RAG chat service

A separate FastAPI service that answers visitors' questions from Rabbit Hole's approved website content
(English + Arabic). The website calls it over HTTP; OpenAI keys never reach the browser.

```
website widget ──POST /chat──▶ FastAPI ─▶ route ─▶ hybrid retrieval (pgvector + keyword, RRF)
                                              └──▶ live public catalogue (when enabled)
                                         ─▶ OpenAI chat (grounded, JSON, cited) ─▶ answer + sources
```

## Run everything with Docker

Only Docker with Compose and `.env` are needed. Copy `.env.example` to `.env`
using your editor or file manager. Leave `OPENAI_API_KEY` blank for offline use.

```bash
docker compose up
# In another terminal:
docker compose --profile test run --build --rm pytest
docker compose --profile test run --build --rm playwright
```

Open **http://localhost:8000/demo.html?mode=live**. Compose builds the image, waits
for healthy Postgres + pgvector, initializes the schema and hash-diff ingests
approved content on every start. Repeat starts safely refresh changes without
re-embedding unchanged chunks. The default uses fake providers (`stub answer`),
serves `/widget.js`, and keeps the catalogue and unreviewed content disabled.
Use `up -d --build --wait` for a background stack and after changing source/content.

Pytest creates and wipes only the isolated `rh_test` database. Playwright uses
Microsoft's official browser image against the running Compose API. Run tests
sequentially; the browser suite tests actual rate limiting, so allow one minute
before an immediate repeat. Reports persist in named Docker volumes.

For real models, set `OPENAI_API_KEY` in `.env` and use these explicit targets:

```bash
docker compose --profile real up -d --build --wait api-real
# Real demo: http://localhost:8001/demo.html?mode=live
# Paid, opt-in checks with separate smoke/quality databases:
docker compose --profile real run --build --rm real-smoke
docker compose --profile real run --build --rm quality
```

For Gemma through OpenRouter, set `OPENAI_CHAT_MODEL` to the provider's model ID,
`CHAT_BASE_URL=https://openrouter.ai/api/v1`, and `CHAT_API_KEY` to your OpenRouter
key. Keep `OPENAI_API_KEY` for OpenAI embeddings. Set `CHAT_JSON_MODE=false` if the
model does not support JSON response format; answers still require valid JSON and
retrieved citations. Compose passes these settings to all real-profile services.
After changing `.env`, rerun the `api-real` command above and open **port 8001**.
Port 8000 deliberately runs fake providers even with `?mode=live`: that parameter
only enables HTTP requests in the widget. The demo footer and development
`/health` response identify the active backend provider.

For free-only OpenRouter chat, use:

```dotenv
OPENAI_CHAT_MODEL=google/gemma-4-31b-it:free
CHAT_BASE_URL=https://openrouter.ai/api/v1
CHAT_JSON_MODE=true
CHAT_FREE_ONLY=true
CHAT_FALLBACK_MODELS=google/gemma-4-26b-a4b-it:free,nvidia/nemotron-3-super-120b-a12b:free
```

Supply your existing `CHAT_API_KEY`. OpenRouter tries Gemma first and then the
listed free chat models on provider errors. The backend rejects paid model IDs in free-only
mode and sends a zero provider price ceiling. Logs identify the model that served
each response. Use explicit chat models rather than the random free router, which
can select task-specific classifiers. Reasoning is disabled for these short replies
to reserve the output budget for the answer. Free providers still have shared capacity and account quotas;
when all attempts fail, visitors receive the safe support/busy response.
Retrieved evidence, language rules and citation validation apply to every model.
Embeddings continue to use the existing OpenAI key/index and are billed separately.
Apply `.env` changes with the `api-real` command above; use the demo on port 8001.

Real and fake embeddings use separate databases/volumes. Secrets enter containers
only at runtime; `.env*` files are excluded from image builds. For a clean-state
rerun, stop any older Rabbit Hole stack occupying port 8000, run
`docker compose --profile test --profile real down -v` (deletes this stack's data
and reports), then repeat the commands above.

For production, copy `.env.production.example` to `.env.production` and fill all
required values, including access settings and a strong URL-safe database password:

```bash
docker compose --env-file .env.production -p rh-production -f docker-compose.production.yml up -d --build --wait
```

Production supplies no dev credentials or fake providers, hides `/demo.html`,
and has health checks, restart policies and a non-root API user. Put a HTTPS
reverse proxy in front of the localhost API. `/widget.js` and `/chat` remain
available; the public widget key must match `SITE_KEYS` on an allowed origin.

See [Docker details and report export](docs/docker-run.md) and
[current verification status](docs/docker-verification.md).
The approved real run passed the five-case smoke; quality was 13/14 overall and
14/14 grounded. It made 56 OpenAI requests at an estimated cost of $0.0167;
[usage and rate sources](docs/docker-real-results/usage-summary.md).

## API

`POST /chat` — headers: `X-Site-Key` (public key), JSON body:
```json
{"message": "Can I exchange a defective item?", "language": "en", "conversation_id": "optional"}
```
Response:
```json
{"answer": "...", "sources": [{"title": "Refund Policy", "url": ".../refund", "document_id": "refund-en"}],
 "products": [], "needs_human": false, "conversation_id": "server-issued", "language": "en"}
```
Send back the returned `conversation_id` for follow-up questions. IDs are server-issued random values; an unknown ID is replaced.
`GET /health` · `POST /admin/ingest` and `POST /admin/purge` (header `Authorization: Bearer $ADMIN_TOKEN`).
Statuses: 401 bad site key, 403 origin not allowed, 413 too long, 422 invalid body, 429 rate/daily limit.

## How answers are produced

- **Language:** detected from the message (Arabic script vs other); retrieval is a hard filter on that language, so Arabic visitors get Arabic source text (no translation drift).
- **Routing (code, not an LLM):** intent flags come from the original message. With the catalogue disabled, price/stock/size questions get a localized cannot-confirm reply with the cached support email, no model calls, and `needs_human=false` (order/account questions still require a hand-off). Shipping answers use only evidence; greetings get a canned reply; everything else goes to retrieval.
- **Retrieval:** vector (OpenAI `text-embedding-3-large`, 1024 dims) + Postgres full-text, fused with RRF. Small documents (policies) are included whole or skipped as a unit, so a rule is never separated from its conditions/exceptions. Contact evidence has reserved space. The chunk budget is soft when the best expanded document needs more space.
- **Generation:** the model may use only the evidence and the live-data note, returns `{answer, can_answer, sources}`; output is strictly validated (non-empty answer, boolean can_answer, at most eight string citations). Only citations that match retrieved chunks are returned; affirmative knowledge/shipping answers without a valid citation fall back. History contains only unexpired visitor turns; condensed queries are used only for retrieval. `can_answer=false` → `needs_human=true`.
- **Failures:** OpenAI or retrieval errors return a polite fallback with the support email (never a 500 stack trace). The support email is cached at startup, so a database failure during conversation/history/save handling also returns the safe fallback. A catalogue outage is never reported as "sold out".

## Content and the unreviewed draft

`data/` contains 42 original policy/brand chunks and 18 product description chunks (60 total). Product descriptions were extracted from the public website in their original EN/AR versions; they contain no saved prices or inventory. The shipping/payment copy ("expedited shipping", tracking email, Visa/Mastercard/AMEX)
is an **unconfirmed draft**: it is excluded by default. For testing only, set `INCLUDE_UNREVIEWED=true` and re-run ingest;
answers then label that information as unconfirmed. Turn it off (and re-ingest, which deletes those rows) until the owner confirms it.
Arabic text is source text, not reviewed translation — get it signed off before launch.

Refresh content: edit `data/chunks.jsonl`, then `POST /admin/ingest`. Only changed chunks are re-embedded; removed ones are deleted; metadata changes also trigger updates; embedding count/dimensions are validated before the update transaction. A PostgreSQL advisory lock serializes the full ingestion operation.

## Live catalogue

`app/catalogue.py` validates the public website API at `https://rabbitholeapi.theosirislabs.com`: `/v1/products?page=1&limit=20` and `/v1/products/{slug}?locale=en|ar`. Set `CATALOGUE_ENABLED=true`, `CATALOGUE_BASE_URL=https://rabbitholeapi.theosirislabs.com` and `SOURCE_BASE_URL=https://darkturquoise-dunlin-447124.hostingersite.com`. No catalogue API key is required. Prices include VAT and availability comes from fresh responses, including size/colour variants. Outages return a cannot-confirm response.

Run `python -m scripts.sync_products` to refresh descriptive snapshots, then re-ingest. This preserves policy/brand records and writes only original descriptions, care and descriptive specifications, never inventory or prices. The current collection has three designs; separate collection groupings are not present in the verified API. See [widget and catalogue behavior](docs/widget-catalogue-update.md).

## Tests and evaluation

```bash
TEST_DATABASE_URL=postgresql://user:pass@localhost/throwaway pytest      # offline tests, no OpenAI calls (DB is wiped at suite startup)
RUN_REAL_QUALITY=1 python -m scripts.eval --judge                         # 14 questions; records real generation evidence
```
`scripts.eval` needs a real `OPENAI_API_KEY`; its evidence-aware run prints per-case results and saves answers, citations and grounding verdicts in the report.
Read the answers yourself too, especially the Arabic ones. The 14 cases are a smoke test, not production validation.

## Quality and deployment preparation

Follow-up evidence audit: [replacement conditions, source/answer/verdict comparisons and judge diff](docs/replacement-judge-audit.md),
[case-1 triage and scored EN/AR phrasings](docs/brand-citation-triage.md), and
[origin inventory with owner placeholders](docs/origin-prep.md).
The audit leaves the judge, service and eval expectations unchanged. Case 1 appears to need
a question-aligned expectation change; approval-only timing answers omit broader policy conditions,
and the exact event starting the 5–7-day clock needs client clarification. Proposals are in the reports.

Repeat the paid audit (fresh conversations, five replacement calls, eight bilingual negative
controls, original plus five EN brand phrasings and three AR phrasings):

```powershell
$env:DATABASE_URL='postgresql://rh:rh@localhost:55439/rh_quality'
$env:RUN_REAL_QUALITY='1'
python -c "from dotenv import load_dotenv; load_dotenv(); import asyncio; from scripts.audit_followups import audit; raise SystemExit(asyncio.run(audit()))"
python -m scripts.report_followup_audit
```

Permanent paid judge controls alone (use the throwaway test DB, which pytest wipes):

```powershell
$env:TEST_DATABASE_URL='postgresql://rh:rh@localhost:55439/rh_test'
$env:RUN_REAL_JUDGE_CONTROLS='1'
python -c "from dotenv import load_dotenv; load_dotenv(); import pytest; raise SystemExit(pytest.main(['tests/test_judge_adversarial.py', '-k', 'real_adversarial', '-q']))"
```

These controls are intentionally invalid fixture answers; they are not approved business facts
and are not loaded by ingestion. Scores in the audit are measured fused RRF scores; expanded
sibling/mandatory chunks have a native returned score of zero, which is not a similarity score.

Prior phase outcomes and remaining owner tasks: [docs/verification.md](docs/verification.md).

The replacement finding is documented in [docs/replacement-finding.md](docs/replacement-finding.md).
The policy supports conditional replacement shipping; the judge now receives actual evidence
and checks meaning instead of requiring a literal “dispatch” keyword. Unsupported claims,
policy-condition omissions and ordinary-delivery substitutions still fail. No API or source-content changes were made.

The latest full real-provider run is in [docs/quality-results.md](docs/quality-results.md), with
answers, actual retrieved/cited chunk IDs and evidence in [docs/quality-results.json](docs/quality-results.json).
It has **13/14 overall passes**: case 1 omits the expected brand-story citation. All 14 grounding
verdicts passed and identified no unsupported claims; this does not replace human review.

Run paid quality checks only by explicit flag, with a separate real-embedding database:

```powershell
$env:DATABASE_URL='postgresql://rh:rh@localhost:55439/rh_quality'
$env:RUN_REAL_QUALITY='1'
python -c "from dotenv import load_dotenv; load_dotenv(); from scripts.quality import main; raise SystemExit(main())" --out docs/quality-results.json
```

For another database/provider configuration, set backend env values as usual. This command
ingests approved data in `DATABASE_URL` and does not wipe tables; never point it at a fake-embedding
index. Product/stock cases correctly bypass generation with the disabled-catalogue response;
their cached contact provenance is recorded separately from per-question retrieval.
`scripts.eval --judge` uses this evidence-capturing path for in-process evaluation.
Deployed `scripts.eval --url ...` cannot capture generation chunks from the public response,
so use the local quality path for evidence-level audits. All real eval commands require `RUN_REAL_QUALITY=1`.

Deployment is manual and hosting remains undecided:

- [Staging checklist and production settings](docs/staging-deploy.md), with `.env.production.example` and optional `docker-compose.staging.yml`.
- [Live-site integration checklist](docs/live-site-checklist.md): remove the old chat first, test EN/AR/CSS and launcher collisions.
- [iPhone/Android test plan and result sheet](docs/device-results.md).
- [Arabic reviewer pack](docs/arabic-review.csv): UTF-8 spreadsheet CSV with adjacent source/reference and Arabic text, blank corrections and review-status columns.

The Arabic pack contains widget strings/chips, backend canned text, every Arabic chunk
(including excluded drafts clearly labelled), complete Arabic source documents, both Arabic
answers from the full run, and Arabic offline-demo literals. English references are existing
source text or independent EN eval answers, never generated translations. Open in a spreadsheet,
set the Arabic column direction to RTL, fill `corrections`/`review_status`, and return the same file.
Paired chunk indices are review references, not a guarantee of translation equivalence.
Do not silently apply corrections to English records. Regenerate after a new quality run:

```bash
python -m scripts.export_arabic_review --quality docs/quality-results.json --out docs/arabic-review.csv
```

The staging checker uses the existing dev requirements, validates HTTPS certificates, and
does not deploy or change admin data:

```powershell
$env:STAGING_SITE_KEY='PUBLIC_WIDGET_KEY'
python -m scripts.check_staging https://SERVICE_HOST --allowed-origin https://SITE_HOST
```

Browser tests reuse an **already installed Node Playwright or playwright-core package and
its Chromium browser**, so no browser dependency is added to the Python service. Set
`PLAYWRIGHT_MODULE` to the absolute package directory if Node cannot resolve `playwright-core`.
Browser tests skip with an explicit reason when that tooling is absent.
`tests/test_widget_contract.py` always compares the widget's executable field/type
declarations with the Pydantic schemas; browser tests also reject missing or mistyped fields.

After starting the dev stack, create a throwaway test DB once:

```bash
docker compose -p rh-widget-dev -f docker-compose.dev.yml exec -T db createdb -U rh rh_test
TEST_DATABASE_URL=postgresql://rh:rh@localhost:55439/rh_test PLAYWRIGHT_MODULE=/absolute/path/to/playwright-core pytest
# Browser tests alone (start their own HTTP service on an ephemeral port):
TEST_DATABASE_URL=postgresql://rh:rh@localhost:55439/rh_test PLAYWRIGHT_MODULE=/absolute/path/to/playwright-core pytest tests/test_widget_browser.py -k end_to_end
```

PowerShell equivalents:

```powershell
$env:TEST_DATABASE_URL='postgresql://rh:rh@localhost:55439/rh_test'
$env:PLAYWRIGHT_MODULE='C:/path/to/existing/node_modules/playwright-core'
New-Item -ItemType Directory -Force test-results | Out-Null
python -m pytest --basetemp=test-results/pytest
```

These tests wipe the specified test DB. They cover real EN/AR retrieval on desktop/mobile,
conversation continuity and language isolation, dev key, ingestion, real 429, injected
400/401/403/413/422/5xx followed by successful real retries, handoff email, hostile source
titles/URLs, all citations, malformed responses and the default offline demo.

Paid, opt-in smoke (use a **separate throwaway DB**, never a fake-embedding index):

```bash
docker compose -p rh-widget-dev -f docker-compose.dev.yml exec -T db createdb -U rh rh_smoke
RUN_REAL_WIDGET_SMOKE=1 TEST_DATABASE_URL=postgresql://rh:rh@localhost:55439/rh_smoke PLAYWRIGHT_MODULE=/absolute/path/to/playwright-core python -c "from dotenv import load_dotenv; load_dotenv(); import pytest; raise SystemExit(pytest.main(['tests/test_widget_browser.py', '-k', 'real_openai', '-v']))"
```

This uses the real configured OpenAI embedder/LLM, ingests approved content, runs eval cases
2–5 plus an Arabic defect question, checks expected citations and language separation,
compares rendered answers/citations with the HTTP response, and uses the existing grounding
judge. It needs `OPENAI_API_KEY`, consumes API credits, and remains a smoke check requiring
human review. Normal pytest runs skip it. All five judge verdicts and responses are saved as
`grounding-results.json` in pytest's temporary directory before any verdict fails the test.

## Before going live

- Set `ENV=production` to require `ADMIN_TOKEN`, `SITE_KEYS`, `ALLOWED_ORIGINS` at startup; run behind HTTPS (Caddy/Nginx) with `TRUST_PROXY=true` only if that proxy sets `X-Forwarded-For`.
- The site key is public by design; real protection is rate limiting + the daily cap. Rotate the LLM token exposed in the old site chatbot.
- Messages are stored for follow-ups. Startup and `/admin/purge` delete individual messages older than `MESSAGE_RETENTION_DAYS`, then empty conversations; expired messages are excluded from history even before purge; set `STORE_MESSAGES=false` to disable. Message text is not logged.
- Set `SOURCE_BASE_URL` once the final domain is known so citation links point at it.
- Live-site verification still required: final origins, deployment HTTPS/CORS, the site's EN/AR toggle and CSS, mobile keyboards, Arabic owner review and support handoff. Streaming and reranker are not built.



