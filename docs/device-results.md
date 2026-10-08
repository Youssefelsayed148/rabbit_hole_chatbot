# Real-device test record

Use the deployed HTTPS site, not just desktop emulation. Fill one result per platform.
Run each scenario in EN and AR. Screenshot/video links and exact reproduction steps belong in notes.

| Test setup | iPhone Safari | Android browser |
|---|---|---|
| Device / OS / browser version | | |
| Date / tester / deployed revision | | |
| Site URL / service URL | | |
| Portrait / landscape / text-size setting | | |
| Network / keyboard / Arabic keyboard version | | |

Record **PASS / FAIL / NOT TESTED**, language and notes for each row.

| Scenario and expected behaviour | iPhone result | Android result | Notes / evidence / owner |
|---|---|---|---|
| Launcher visible and clear of fixed elements in EN and AR; tapping opens once | | | |
| Full-screen sheet fits visible viewport; no clipped header/close/send control | | | |
| Notch/home-indicator safe areas, browser toolbar expansion/collapse and rotation | | | |
| Focus input; keyboard opens without hiding composer/send; messages remain scrollable | | | |
| Dismiss and reopen keyboard; close/reopen chat; sheet height restores correctly | | | |
| Arabic IME: type and edit Arabic, accept suggestions/composition, mix numbers/email; no premature submission or lost text | | | |
| Send Arabic message; RTL labels/bubbles/citations align; EN history stays separate | | | |
| Long input and multiline/Shift+Enter where supported; composer grows and send stays reachable | | | |
| Submit once during slow network; typing indicator and disabled send prevent duplicate submission | | | |
| Temporarily disable network; readable localized error; restore network and Retry succeeds without duplicate user message | | | |
| 429 from a controlled staging limiter: localized wait/retry message; retry after window expires | | | |
| Controlled staging 5xx: readable error, Retry succeeds after recovery | | | |
| needs_human: support email button opens the mail composer with the correct recipient | | | |
| Source titles render as text; tap valid HTTPS links, return to site, chat/session still usable | | | |
| HTTP-only citation targets may be blocked/upgraded by browser policy; record actual destination behaviour | | | |
| Source schemes such as javascript/data/mailto are absent from citation buttons (use local security fixture, not invented live facts) | | | |
| New chat clears only current-language history; language toggle then back restores the other language | | | |
| Reload preserves session transcript; new tab/session behaviour is acceptable | | | |

Fault tests require a controlled staging setup: do not modify production or repeatedly exhaust
its shared limiter. The offline demo offers `429`, `error`, and `offline` messages for UI-only
checks; real staging fault recovery should also be tested. Never infer that a successful UI
check proves model grounding. Record any inability to inject a fault as NOT TESTED.

Launch approval: __________  Open defects: __________  Retest date: __________
