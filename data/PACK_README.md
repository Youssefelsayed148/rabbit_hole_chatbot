# Rabbit Hole — RAG data starter pack

Original inspection date: 4 October 2026 (UTC).

Catalogue update: the public API is now verified. `products.jsonl` contains six original EN/AR description records for three designs; `chunks.jsonl` has 60 chunks (42 original plus 18 product descriptions). Prices and inventory are fetched live. The inspection notes below describe the original extraction. See [the current behavior](../docs/widget-catalogue-update.md).
Website: https://darkturquoise-dunlin-447124.hostingersite.com/

## What is delivered

- `documents.jsonl`: 14 bilingual source documents, including 2 supplementary drafts.
- `chunks.jsonl`: 42 heading-preserving chunks, excluding supplementary drafts. No embeddings have been generated.
- `knowledge_base.md`: readable extraction, with provenance and verification status.
- `manifest.json`: extraction metadata and missing data.
- `evaluation.jsonl`: 14 baseline questions and required answer behavior.
- `extract_snapshot.py`: standard-library extraction script for this observed frontend build; not a general crawler.
- `implementation_plan.md`: ingestion, retrieval, live data and service integration design.

English brand/story/policy text was cross-checked against rendered pages. Arabic text was extracted from the published application source, not translated; Arabic rendering and translations still need owner review. Contact data came from the rendered footer. The same proper nouns/email are used in both language records.

## Verified site structure and data boundaries

The homepage is an HTML shell with a client-rendered React application and `/assets/index-CCGx41Sk.js`. A simple HTML scraper would miss the business content. `/sitemap.xml` currently returns that HTML shell, not XML. `robots.txt` disallows Googlebot and allows other user agents.

Observed rendered routes: `/`, `/brand-story`, `/collection`, `/terms`, `/refund`, `/privacy`, `/artwork`.

- `/brand-story` has separate story and collection-story modals; both were opened.
- `/collection` exposed navigation/footer but no visible catalogue during inspection.
- `/artwork` exposed only chatbot UI during inspection; no artwork facts were extracted.
- Published application code defines `/product/:slug` and `/artwork/:slug`; individual records and slugs were not verified.
- Contact link: `mailto:info@rabbithole.ae`. Footer location: Dubai, UAE. This is not a street/store address.
- Social links were observed in the footer; no social content was ingested.
- Videos appear in the frontend; video/audio facts were not transcribed or inferred.
- Login, account, checkout, orders, and admin data were excluded.

The published frontend uses the API origin `https://rabbitholeapi.theosirislabs.com` and public GET functions for `/v1/products` and `/v1/products/{id-or-slug}`. One read-only request to `/v1/products?page=1&limit=50` returned HTTP 403 in this execution environment. Its response schema, pagination, authentication requirements and catalogue contents remain unverified. This does not prove the endpoint is private or the site is broken.

## Useful facts supported by the extracted content

- Brand: Rabbit Hole; luxury-oriented men's swimwear; collection story refers to Season 27.
- The refund policy says opened/tried-on swimwear cannot be returned/exchanged except for manufacturing defects.
- Manufacturing defects must be reported within 7 days of delivery.
- Exchange eligibility requires original condition, unworn, original tags and packaging.
- Approved replacement products are shipped within 5–7 working days following receipt/inspection and approval. This is not a delivery estimate for a normal purchase.
- Terms, refund and privacy pages display “Last Updated: April 26, 2026”. This is the page's own label, not independently verified change history.
- Privacy policy statements must be attributed to the published policy. This inspection did not audit the actual security implementation.

Supplementary source-only copy claims expedited shipping, shipment tracking by email and major payment cards including Visa/Mastercard/AMEX. Do not promise these until the business confirms actual checkout/shipping behavior. Shipping destinations, prices, times and free-shipping thresholds are unknown.

## Immediate information to request from the website developer/owner

1. Repository/source export, particularly product content and Arabic/English policy files. Hostinger access is not required for the already extracted static content.
2. A public product JSON/CSV export or authorized server-to-server catalogue API, with pagination documented and the service's IP/origin permitted as appropriate.
3. Per product: ID, slug, names/descriptions in both languages, collection, material, fit, care instructions, size chart, variants, colour, images, currency, current price and availability. Verify each field; none is assumed present.
4. Shipping destinations, fees, expected delivery ranges and support escalation process; distinguish normal shipping from replacement shipping.
5. Confirm that this temporary Hostinger domain and policies are production-approved; obtain the final domain for citations and website CORS configuration.
6. Have the owner confirm refund wording where product modal summaries are stricter than the full policy, plus handling of a tried-on defective item versus the unworn-condition clause.

## Existing chatbot finding

The published frontend contains a direct LLM-provider request and a literal bearer authorization token near that request. Its validity was not tested, and it is deliberately absent from this pack. If active, the owner should rotate it and keep the replacement in the separate backend's environment variables. Do not embed API secrets or this JavaScript bundle into the knowledge base.

## Reproducing this snapshot

Download the exact public app build separately, then run:

```bash
python extract_snapshot.py path/to/index-CCGx41Sk.js output-directory
```

The script parses specific component names and text patterns observed in this build. Assertions fail if the expected policy/story shape changes. After any rebuild, replace the parser with a rendered-page extractor or, preferably, an owner-approved content export. Do not treat this as an unattended future-proof ingestion system.

## Completion status

Static bilingual seed corpus: extracted. Baseline heading chunks: generated. Product catalogue/live price/stock: blocked/unavailable. Shipping operational facts: need owner confirmation. Embeddings, retrieval, chatbot backend and website integration: not implemented or deployed in this data-extraction task.
