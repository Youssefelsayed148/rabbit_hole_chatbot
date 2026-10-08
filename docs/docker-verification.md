# Docker verification

Verified after `docker compose --profile test --profile real down -v`:

| Command / check | Result |
|---|---|
| `docker compose up -d --wait` | Both services healthy; fresh schema and 42 approved chunks |
| `/health`, `/widget.js`, `/demo.html?mode=live` | Health status ok; both assets HTTP 200 |
| Live `/chat` with pk_demo + localhost origin | HTTP 200, fake stub answer, refund-en citation; API fields unchanged |
| `docker compose --profile test run --build --rm pytest` | 174 passed, 3 skipped in 6.08s |
| `docker compose restart api` | Restart succeeded; embedded 0, unchanged 42, deleted 0 |
| In-container asset / identity / ingest checks | Passed: non-root user, no OpenAI key, both assets, repeat ingest embedded 0 |
| `docker compose --profile test run --build --rm playwright` | 105 Playwright checks passed, exit 0; official image v1.63.0-noble |
| Default, test, real, legacy dev Compose configuration | Parse and invariant checks passed |
| Production Compose configuration | Parses with dummy required values; rejects blank credentials/access settings |
| Production app route/schema inspection | Demo absent; widget present; chat response fields unchanged |

The three pytest skips are the offline browser check (runs in the separate official
Playwright image), paid widget smoke, and paid adversarial judge controls.
The startup regression test passed: a removed chunk is deleted from a nonempty index,
and two starts embed no unchanged chunks.

The older Rabbit Hole dev containers occupying port 8000 were removed without deleting
their database volumes. Unrelated ERP containers were left untouched. Initial approval
review timeouts were resolved by subsequent accepted operations.

Real-provider verification completed after the user's explicit approval to send the
42 approved EN/AR chunks and eval/smoke queries to OpenAI, using only the project key
from `.env`. There was no host key override and no secret file was edited.

The runs used `--env-file .env -f docker-compose.yml -f docker-compose.verify.yml`.
The verification override forces the official OpenAI endpoint, disables stored history
and published visitor ports on api-real, and logs only request IDs, endpoints, model
names, status codes and numeric token counters. Protocol prompts and generated answers
were sent as part of generation/grading; repository files, secrets other than the auth
key, and stored visitor conversations were not sent.

| Real check | Result | OpenAI API calls |
|---|---|---:|
| api-real startup | Healthy, non-root, 42 chunks; widget/demo served internally | 1 |
| real-smoke | 1 pytest passed; five EN/AR cases and grounding controls passed | 18 |
| quality | 13/14 overall, 14/14 grounding; exit 1 on case-1 citation failure | 37 |
| Total | All 56 requests returned HTTP 200; no failed/unanswered attempts | 56 |

Case 1 cites `collection-story-en` but expects `brand-story-en`, matching the previous
known quality finding. Expectations, prompts, approved content and `/chat` fields
were left unchanged. See the [new quality evidence](docker-real-results/quality.json),
[readable results](docker-real-results/quality.md), and
[smoke grounding report](docker-real-results/smoke/pytest/test_real_openai_grounding_sur0/grounding-results.json).

Measured usage: 19 embedding requests (12,146 input tokens), 37 chat/generation/judge
requests (30,311 input, 1,857 output, 0 reported cached tokens). Estimated total cost:
**$0.01667458 USD**, excluding account credits, taxes and billing adjustments.
See the [cost breakdown and official rate sources](docker-real-results/usage-summary.md)
and [machine-readable counters](docker-real-results/usage-summary.json).
The API startup, smoke and quality databases each ingested the same approved 42 chunks;
no unreviewed draft was included. All results were exported from Docker volumes. The cost summary was also reproduced inside the offline pytest image without an API key.

The first instrumented startup failed before any HTTP request because the logger
imported a test-only HTTP package. It was corrected to use the SDK's built-in client
without adding dependencies, and the five request/usage regression tests passed.
The earlier full offline run with instrumentation passed 175 tests with 3 expected
skips. The final logger correction was then verified by those five targeted tests
and all real-provider runs. Usage logging remains opt-in via `OPENAI_USAGE_LOG`.

The real API was stopped immediately after startup/asset checks to prevent extra
traffic or charges. Real Postgres and results volumes remain available. Production
runtime was not started: production configuration and route restrictions remain
verified as described above, but no production credential file/deployment was supplied.

Static Python compile and discovery checks used the existing host virtual environment;
application startup, pytest and Playwright ran in Docker without host Python or Node.
No secret file was changed, no key was printed, and no key was copied into an image.


The offline API remains running at http://localhost:8000/demo.html?mode=live.



