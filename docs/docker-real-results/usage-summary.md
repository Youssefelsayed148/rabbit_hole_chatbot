# Real Docker verification usage

Measured HTTP attempts and response token usage; no prompts or credentials logged.

| Phase | API calls | Embeddings | Chat / judge | Approx. USD |
|---|---:|---:|---:|---:|
| api-real startup | 1 | 1 | 0 | $0.000518 |
| real-smoke | 18 | 6 | 12 | $0.005484 |
| quality | 37 | 12 | 25 | $0.010673 |
| Total | 56 | 19 | 37 | $0.016675 |

Token totals: {"embedding_input": 12146, "chat_input": 30311, "chat_cached_input": 0, "chat_output": 1857}

Unsuccessful/unanswered HTTP attempts: 0.

Estimate uses standard public rates and reported cached tokens; account credits, taxes and billing adjustments are excluded.

Rates verified 2026-10-06: [GPT-4.1 mini](https://developers.openai.com/api/docs/models/gpt-4.1-mini), [text-embedding-3-large](https://developers.openai.com/api/docs/models/text-embedding-3-large).
