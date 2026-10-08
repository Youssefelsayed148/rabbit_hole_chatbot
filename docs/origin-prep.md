# Exact origin inventory — fill before deployment

Only one website host is evidenced in the repository: `darkturquoise-dunlin-447124.hostingersite.com`.
It appears in `data/manifest.json`, `data/PACK_README.md`, `.env.example` and README.
These are repository references, not verification of current live DNS, redirects or certificates.
Do not put every candidate into `ALLOWED_ORIGINS`; include only confirmed origins that actually host the widget page.

| Website origin candidate | Repository status | Served page / redirect-only / unused — fill in |
|---|---|---|
| `https://darkturquoise-dunlin-447124.hostingersite.com` | Confirmed source/preview origin in repo | __________ |
| `http://darkturquoise-dunlin-447124.hostingersite.com` | Scheme variant only; serving unknown | __________ |
| `https://www.darkturquoise-dunlin-447124.hostingersite.com` | www variant only; serving unknown | __________ |
| `http://www.darkturquoise-dunlin-447124.hostingersite.com` | www + HTTP variant only; serving unknown | __________ |
| `https://<PRODUCTION_APEX>` | Final domain undecided; fill actual hostname | __________ |
| `https://www.<PRODUCTION_APEX>` | Fill only if served independently | __________ |
| `http://<PRODUCTION_APEX>` | Fill; preferably redirect-only, not allowlisted | __________ |
| `http://www.<PRODUCTION_APEX>` | Fill; preferably redirect-only, not allowlisted | __________ |
| `https://<OTHER_STAGING_HOST>` | No additional staging host named | __________ |
| `https://www.<OTHER_STAGING_HOST>` | Candidate only; mark unused if inapplicable | __________ |
| `http://<OTHER_STAGING_HOST>` | Candidate only; usually redirect-only | __________ |
| `http://www.<OTHER_STAGING_HOST>` | Candidate only; usually redirect-only | __________ |
| `https://<PREVIEW_HOST>` | No additional preview host named; one exact row per served preview | __________ |
| `https://www.<PREVIEW_HOST>` | Candidate only; mark unused if inapplicable | __________ |
| `http://<PREVIEW_HOST>` | Candidate only; usually redirect-only | __________ |
| `http://www.<PREVIEW_HOST>` | Candidate only; usually redirect-only | __________ |
| `<SCHEME>://<ACTUAL_HOST>:<NONDEFAULT_PORT>` | Include a port only if the site really uses it | __________ |

Other origins and their roles:

- `http://localhost:8000` and `http://127.0.0.1:8000`: dev demo origins, explicitly configured by `docker-compose.dev.yml`; exclude from production.
- `https://rabbitholeapi.theosirislabs.com`: documented legacy catalogue API origin in `data/PACK_README.md`; it is not evidence of a website-page origin and should not automatically be allowlisted. Catalogue stays disabled.
- README's `YOUR-SERVICE` / `SERVICE_HOST` and `.env.example`'s `www.final-domain.com` are placeholders, not discovered domains.
- The email domain `rabbithole.ae` does not establish the website's served origin; no production website is inferred from it.

## Matching behavior and regression coverage

The request gate uses literal membership: `origin not in s.allowed_origins`.
The CORS middleware uses the explicit `allow_origins` list, with no `allow_origin_regex`.
There is no suffix test, subdomain expansion or wildcard-domain matching. Missing Origin is
permitted for non-browser clients; configured site-key auth still applies.

With only `https://example.com` configured, tests cover allowed POST/preflight and rejected
POST/preflight for `https://example.com.evil.com`, `https://evil-example.com`, subdomain/www,
HTTP, a port suffix, trailing slash, raw uppercase spelling, userinfo-style input and `null`.
Denied calls return 403; denied preflights return 400 without an allow-origin header.
Some deliberately malformed/raw variants would normally be canonicalized by browsers; the tests
prove the service does not silently broaden a received Origin string.

Production rejects the literal `*` at startup. A configured `https://*.example.com` is a literal
string, not a wildcard; a real subdomain fails both checks. It should not be used as configuration.
In development, manually configuring literal `*` makes Starlette's preflight permissive,
but the request gate still denies real origins that do not literally appear in the list.
Do not use `*` in any environment. This existing development behavior has not been changed.

Final confirmed allowlist (exact scheme/host/optional port; no path or trailing slash):

```dotenv
ALLOWED_ORIGINS=<FILL_CONFIRMED_HTTPS_SITE_ORIGINS_COMMA_SEPARATED>
```

Owner/date/DNS+redirect verification notes: ______________________________
