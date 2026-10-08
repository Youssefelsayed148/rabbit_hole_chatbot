# Widget and catalogue update

Question shortcuts stay in one horizontally scrollable row directly above the message box, in English and Arabic. The row stays available while reading the conversation and disables during requests. Replies render paragraphs, lists and bold labels with safe DOM nodes; HTML from models or products is never executed. Live products appear as cards with VAT-inclusive prices, availability and a link to the verified collection page.

History uses sessionStorage by default: reloads keep the chat, new browser sessions start fresh. New chat clears history. Optional script attributes `data-storage="local"` and `data-history-days="30"` enable longer browser-local retention only when explicitly configured; `data-storage="none"` disables saving. Browser session restoration can restore sessionStorage together with reopened tabs.

The public collection API was verified against the website's own requests. There are three current designs and original English/Arabic product details. Descriptive snapshots are in `data/products.jsonl`; 18 product chunks join the 42 policy/brand chunks. Arabic remains original source text awaiting owner review. Prices, sizes, colours and stock are fetched live, never embedded. Collection stories use the existing source content; no extra collection grouping is inferred.

Refresh snapshots with `python -m scripts.sync_products`, then run the authenticated ingest endpoint (or restart the real development service, which auto-ingests). This calls the public catalogue only; embedding changed chunks uses the configured embedding provider. Offline tests use fakes and a separate test database.

Local live demo: http://localhost:8001/demo.html?mode=live . Port 8000 is the fake development service and intentionally returns stub answers.


Product follow-ups remember the order of the cards shown. For example, after browsing three products, “What sizes are available for the second product?” checks the identity of the second card against the live API. First/second/third and Arabic equivalents work; “it” or a plain size question follows the most recent single selected product. Ordinals use the most recent multi-product list within the configured conversation-history window. Ambiguous or out-of-range references ask which product rather than guess.

Only product names and slugs are saved alongside assistant messages in `messages.product_references`; no historical price or stock is reused. References follow the same message retention setting and are disabled with `STORE_MESSAGES=false`. Startup adds the JSONB column to existing databases without deleting conversations. A new browser chat uses a new conversation and does not inherit another chat’s products.

Exact stock quantities stay inside the catalogue adapter. Model context and chat response variants expose only `available` booleans, alongside size/colour identities. Replies must never provide or estimate inventory counts.
