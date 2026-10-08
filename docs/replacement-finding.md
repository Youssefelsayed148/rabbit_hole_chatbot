# Replacement dispatch finding — 2026-10-05

Follow-up qualification: [replacement-judge-audit.md](replacement-judge-audit.md) confirms shipping/dispatch
semantic support but finds that short answers do not preserve every policy condition and the
clock-start event is not explicit. Its client clarification question supersedes the earlier
general statement below that no wording question is needed.

Decision: **(a), source-supported wording rejected by an overly literal judge.**

Reproduced question: “How long does an approved replacement take to ship?”

Reproduced real-model answer:

> According to the refund policy, if a replacement is approved, the replacement product will be shipped within 5-7 working days after the product is received and inspected.

The actual generation evidence includes the complete English refund policy and contact evidence;
the model cited `refund-en-5`. See `replacement-reproduction.json` for the captured evidence and
the original FAIL verdict.

`data/chunks.jsonl`, `refund-en-5`, “4. Exchange Process” says:

> Once we receive and inspect the product, we will send you an email to notify you of the status of your request. If approved, the replacement product will be shipped within 5-7 working days.

This matches the English source document `refund-en` in `data/documents.jsonl`.
An approved replacement being shipped describes dispatch; it does not promise ordinary delivery
or guaranteed arrival. The source itself uses “will be shipped.” The failed judge required a
literal dispatch label despite the answer's conditional replacement wording.

The correction gives the judge actual generation evidence and requires semantic assessment.
It retains checks for unsupported claims, unconditional promises, changed time-window triggers,
normal-delivery/arrival substitutions, and missing material conditions or exceptions.
An unsupported-claims list forces FAIL even if the judge returns `pass=true`.
The generation prompt, approved source content and `/chat` shape are unchanged.

Permanent regressions:

- Offline pipeline: this exact source-supported answer must survive with the refund citation.
- Offline judge harness: evidence is included, semantic instructions retained, invalid verdicts
  and verdicts admitting unsupported claims fail closed.
- Real widget smoke: case 5 is retained and graded using its captured generation evidence;
  the widget must preserve answer text and citation links.

No client wording question is needed for this source-supported finding. This does not confirm
operational fulfilment; the assistant attributes the published policy to its source.
