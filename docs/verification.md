# Phase verification — 2026-10-05

Follow-up: [the replacement audit](replacement-judge-audit.md) identifies omitted conditions and
an unspecified clock-start event; [the case-1 triage](brand-citation-triage.md) proposes a
question-aligned expectation change instead of a service fix. These supersede the earlier broad
condition-preservation and case-1 service-bug interpretations below. Historical results are retained.

No deployment was performed. No `/chat` API shape, generation prompt or approved source
content was changed. No dependencies were added. Catalogue and unreviewed-draft flags stayed off.

## Replacement blocker

Decision **(a)**: the conditional replacement-shipping wording is supported by the retrieved
`refund-en-5` and the complete source policy. The old judge failed on a literal dispatch label.
The evidence comparison and exact reproduction are in [replacement-finding.md](replacement-finding.md)
and [replacement-reproduction.json](replacement-reproduction.json).
The judge now receives actual evidence and checks meaning, conditions and unsupported claims.
Permanent offline and paid smoke regressions were added; the real judge accepts the exact
source-supported wording and rejects a deliberate normal-delivery/guaranteed-arrival substitution.
No client policy wording answer is needed for this finding.

## Quality outcome

All 14 cases were run with real OpenAI providers (`gpt-4.1-mini`, `text-embedding-3-large`, 1024 dimensions),
with explicit `RUN_REAL_QUALITY=1`. EN/AR evidence remained separate. The catalogue-disabled
price/stock/outage cases followed their deterministic branch; their cached contact provenance is recorded.

- **13/14 overall PASS**, requiring both expected document citations and a passing judge verdict.
- **14/14 grounding verdicts PASS**, with no unsupported claims identified by the judge.
- **Case 1 FAIL**: “What does Rabbit Hole sell?” cites `collection-story-en-1`, omitting expected
  `brand-story-en`. That citation-coverage failure is retained; the requirement was not weakened.
- Both Arabic cases PASS; their original answers are in the reviewer pack.

Every question, result, accepted cited chunk, unsupported-claim finding and judge reason is
in [quality-results.md](quality-results.md). [quality-results.json](quality-results.json) contains
the exact answers and generation evidence for independent review. Judge passes are not a substitute
for human review or evidence that the catalogue is available.

## Verification performed

- Windows full suite: **151 passed, 1 skipped** (paid smoke flag off). It included **105 Chromium checks**.
- The two subsequently added export-completeness/paid-flag tests passed in focused verification.
- Final complete container offline suite: **152 passed, 2 skipped** (no Node browser installation
  in the Python image; paid flag off). Chromium was already verified on the host.
- Gated real widget smoke: **PASS**, five actual questions plus the judge's positive/negative controls.
- Final `docker build --no-cache --pull`: **PASS**, local image only, not pushed or deployed.
- Actual HTTP checks inside that image under production settings with injected fake providers:
  `/widget.js` 200, JavaScript MIME, `public, max-age=3600, must-revalidate`, `nosniff`; `/demo.html` 404.
- Staging checker: tested against the actual production-configured FastAPI app, including allowed/denied
  preflight, chat/site-key enforcement and static routes. Its HTTPS input validation also passed.
  **Not run against staging**: no service URL or deployed TLS/proxy exists yet.
- Arabic export: **104 rows**, including 24 widget rows, 4 backend strings, 63 chunk fields (all
  21 Arabic chunks), 7 full source documents, 2 actual Arabic eval answers and 4 offline-demo literals.
  Source text is preserved; correction cells are blank. No translation or production correction was applied.

## Exactly what remains

| Item | Required next action |
|---|---|
| Client policy answer | None needed for the replacement finding; the published source is clear. |
| Citation-coverage failure | Case 1 remains an open service-quality issue. Resolve it before treating the full eval as green; no client fact is needed. |
| Staging | You choose hosting/service host/site origins, provision secrets/database/HTTPS, deploy, and run [the staging checklist](staging-deploy.md) and `scripts.check_staging`. |
| Live site | You remove the old chat, install one new script, and complete [the integration checklist](live-site-checklist.md). |
| Real devices | You run iPhone Safari and Android checks and fill [device-results.md](device-results.md), including controlled faults. |
| Arabic reviewer | A native speaker completes corrections/sign-off in [arabic-review.csv](arabic-review.csv), including UI and actual generated answers. Arabic remains unreviewed until owner approval. |

Production templates are `.env.production.example` and optional `docker-compose.staging.yml`.
Hosting has not been selected, and placeholder settings are intentionally unfilled.
