# Replacement judge audit

No judge, generation prompt, production retrieval, API shape or eval expectation was changed during this audit.

## Side-by-side captured comparisons

The historical full-quality row includes its actual evidence payload; the current final repeat also records its exact evidence.

| Run | Source process chunk | Real answer | Judge verdict / actual evidence IDs |
|---|---|---|---|
| Previous full quality | 4. Exchange Process<br>Once we receive and inspect the product, we will send you an email to notify you of the status of your request. If approved, the replacement product will be shipped within 5-7 working days. | According to the refund policy, if a replacement is approved, it will be shipped within 5-7 working days after the product is received and inspected. | {"pass": true, "reason": "The answer correctly states that an approved replacement will be shipped within 5-7 working days after inspection, matching the policy's replacement dispatch timeframe.", "unsupported_claims": []} Evidence: refund-en-1, refund-en-2, refund-en-3, refund-en-4, refund-en-5, contact-en-1 |
| Current repeat 5 (final) | 4. Exchange Process<br>Once we receive and inspect the product, we will send you an email to notify you of the status of your request. If approved, the replacement product will be shipped within 5-7 working days. | According to the refund policy, once a replacement request is approved, the replacement product will be shipped within 5-7 working days. | {"pass": true, "reason": "The answer correctly states that an approved replacement will be shipped within 5-7 working days, matching the retrieved evidence, and uses the term 'shipped' consistent with replacement dispatch rather than normal delivery.", "unsupported_claims": []} Evidence: refund-en-1, refund-en-2, refund-en-3, refund-en-4, refund-en-5, contact-en-1 |

The previous final widget smoke answer was: “According to the refund policy, once a replacement request is approved, the replacement product will be shipped within 5-7 working days.” Its saved verdict was PASS. That smoke artifact did not persist the raw judge evidence payload; it cannot be reconstructed as an exact historical input. Current repeat 5 reproduces the wording and records its evidence.

## Complete defect/replacement source

English is render_verified; Arabic is source_extracted and still needs native-speaker/owner approval.

| EN source chunk / exact text | AR source chunk / exact text |
|---|---|
| refund-en-2: 1. Hygiene Policy (Crucial)<br>Due to the nature of our products (swimwear), and for reasons of public health and hygiene, we do not accept returns or exchanges for any item that has been opened or tried on, except in the case of a manufacturing defect. | refund-ar-2: 1. سياسة الوقاية (مهم جداً)<br>نظراً لطبيعة منتجاتنا (ملابس السباحة)، ولأسباب تتعلق بالصحة العامة والوقاية، فإننا لا نقبل استرجاع أو استبدال أي قطعة تم فتحها أو تجربتها، إلا في حالة وجود عيب مصنعي. |
| refund-en-3: 2. Manufacturing Defects<br>In the event of receiving a product with a manufacturing defect, please contact us within 7 days of the delivery date. We will inspect the product and replace it with a new item if the defect is confirmed. | refund-ar-3: 2. العيوب المصنعية<br>في حالة استلام منتج به عيب مصنعي، يرجى التواصل معنا خلال 7 أيام من تاريخ الاستلام. سنقوم بفحص المنتج واستبداله بقطعة جديدة في حالة التأكد من وجود العيب. |
| refund-en-4: 3. Product Condition<br>To be eligible for an exchange, the product must be in its original condition, unworn, with all original tags attached and in its original packaging. | refund-ar-4: 3. حالة المنتج<br>ليتم النظر في طلب الاستبدال، يجب أن يكون المنتج في حالته الأصلية، غير مستخدم، مع جميع الملصقات الأصلية وفي غلافه الأصلي. |
| refund-en-5: 4. Exchange Process<br>Once we receive and inspect the product, we will send you an email to notify you of the status of your request. If approved, the replacement product will be shipped within 5-7 working days. | refund-ar-5: 4. عملية الاستبدال<br>بمجرد استلامنا للمنتج وفحصه، سنرسل لك بريداً إلكترونياً لإخطارك بحالة الطلب. في حالة الموافقة، سيتم شحن المنتج البديل خلال 5-7 أيام عمل. |

## Condition audit

Replacement shipping is explicitly conditional on approval; receipt and inspection precede the approval/status process. Defect exchange eligibility also has the separate prerequisites below. An already-approved timing question is narrower than a complete eligibility explanation, but these answers do not reproduce every policy condition.

| Condition/detail | Source | Previous final smoke / current repeat 5 | Five repeats |
|---|---|---|---|
| Approval | refund-*-5 | Kept | Kept 5/5 |
| Receipt and inspection | refund-*-5 | Omitted | Explicit 3/5 (runs 1, 2, 4); omitted 2/5 (3, 5) |
| Report defect within 7 days of delivery | refund-*-3 | Omitted | Omitted 5/5 |
| Manufacturing defect confirmed after inspection | refund-*-3 | Omitted | Omitted 5/5 |
| Original condition, unworn, original tags and packaging | refund-*-4 | Omitted | Omitted 5/5 |
| Opened/tried-on restriction together with defect exception | refund-*-2 | Omitted | Omitted 5/5 |
| Request-status email | refund-*-5 | Omitted process detail; not an eligibility condition | Omitted 5/5 |
| 5–7 working days; shipping rather than arrival | refund-*-5 | Kept | Kept 5/5 |

Runs 1/2/4 attach the period to receipt/inspection. The source gives that process sequence but does not explicitly name the event that starts the 5–7-day clock. Treat that starting-point interpretation as unresolved, rather than certify it from a judge PASS.

Exact client wording question: **‘Your published policy says, “If approved, the replacement product will be shipped within 5–7 working days.” Which event starts those 5–7 working days: receipt of the returned product, completion of inspection, or approval of the replacement? Please confirm the exact wording we should publish.’**

The literal shipping/dispatch synonym change remains source-supported. The broader condition-preservation claim was too strong: a PASS on this narrow case does not demonstrate that all refund-policy prerequisites are present. No answer or source was patched during this audit.

## Judge before/after

See `judge-change.diff`: the original judge source is reconstructed from the prior captured source read because there is no Git history here. The after side is read from the current implementation.

The original failure rejected: “According to the refund policy, if a replacement is approved, the replacement product will be shipped within 5-7 working days after the product is received and inspected.” Reason: “The answer states the correct shipping time but does not label the shipment as a replacement dispatch as required.”

The current judge accepts that semantic construction without requiring the literal word ‘dispatch’. It now receives evidence, requests unsupported claims, requires boolean/schema validity and forces FAIL when unsupported claims are admitted. It also accepts approval-only phrasing in runs 3/5 despite the omissions above. The before/after acceptance is empirical for the recorded answers, not a claim that the older stochastic judge always rejected every synonym.

## Five real replacement runs

Independent fresh conversations, same model/config/evidence pack, no retry-until-green selection.

| Run | Exact real answer | Cited chunks | Verdict | Receipt/inspection explicit? |
|---|---|---|---|---|
| 1 | According to the refund policy, if a replacement is approved, it will be shipped within 5-7 working days after the product is received and inspected. | refund-en-5 | {"pass": true, "reason": "The answer correctly states that an approved replacement will be shipped within 5-7 working days after inspection, matching the policy's 'replacement dispatch' timeframe.", "unsupported_claims": []} | Yes |
| 2 | According to the refund policy, if your replacement request is approved, the replacement product will be shipped within 5-7 working days after the product is received and inspected. | refund-en-5 | {"pass": true, "reason": "The answer correctly states that an approved replacement will be shipped within 5-7 working days after inspection, matching the policy and labeling it as replacement dispatch, not normal delivery.", "unsupported_claims": []} | Yes |
| 3 | According to the refund policy, once a replacement request is approved, the replacement product will be shipped within 5-7 working days. | refund-en-5 | {"pass": true, "reason": "The answer correctly states that an approved replacement will be shipped within 5-7 working days, matching the policy's specified replacement dispatch timeframe.", "unsupported_claims": []} | No |
| 4 | According to the refund policy, if a replacement is approved, the replacement product will be shipped within 5-7 working days after the product is received and inspected. | refund-en-5 | {"pass": true, "reason": "The answer correctly states that an approved replacement will be shipped within 5-7 working days after inspection, matching the required behavior and evidence without adding unsupported claims.", "unsupported_claims": []} | Yes |
| 5 | According to the refund policy, once a replacement request is approved, the replacement product will be shipped within 5-7 working days. | refund-en-5 | {"pass": true, "reason": "The answer correctly states that an approved replacement will be shipped within 5-7 working days, matching the retrieved evidence, and uses the term 'shipped' consistent with replacement dispatch rather than normal delivery.", "unsupported_claims": []} | No |

## Adversarial controls

These are intentionally invalid test answers, never approved business facts. Each judge input contained the five policy chunks in the same language. All eight must FAIL; all eight did.

| Control | Question | Invalid answer | Judge verdict / unsupported claims | Evidence |
|---|---|---|---|---|
| unconditional-en | Will you replace my defective swimwear? | We will replace your swimwear unconditionally, even if no manufacturing defect is confirmed and the exchange is not approved. | {"pass": false, "reason": "The answer promises an unconditional replacement even if no manufacturing defect is confirmed and the exchange is not approved, which contradicts the published conditions.", "unsupported_claims": ["We will replace your swimwear unconditionally, even if no manufacturing defect is confirmed and the exchange is not approved."]} | refund-en-1, refund-en-2, refund-en-3, refund-en-4, refund-en-5 |
| unconditional-ar | هل ستستبدلون قطعة السباحة المعيبة؟ | سنستبدل القطعة دون أي شروط، حتى إذا لم يتم التأكد من وجود عيب مصنعي ولم تتم الموافقة على الاستبدال. | {"pass": false, "reason": "The answer promises an unconditional replacement without verifying the defect or approval, which contradicts the policy conditions.", "unsupported_claims": ["سنستبدل القطعة دون أي شروط، حتى إذا لم يتم التأكد من وجود عيب مصنعي ولم تتم الموافقة على الاستبدال."]} | refund-ar-1, refund-ar-2, refund-ar-3, refund-ar-4, refund-ar-5 |
| timeline-en | When does an approved replacement ship? | According to the policy, an approved replacement is dispatched within 24 hours of your first email. | {"pass": false, "reason": "The answer states a 24-hour dispatch timeline which is not supported by the policy; the policy specifies replacement shipping within 5-7 working days after inspection and approval.", "unsupported_claims": ["an approved replacement is dispatched within 24 hours of your first email"]} | refund-en-1, refund-en-2, refund-en-3, refund-en-4, refund-en-5 |
| timeline-ar | متى يتم شحن البديل الموافق عليه؟ | وفق السياسة، يتم شحن البديل الموافق عليه خلال 24 ساعة من إرسال أول بريد إلكتروني. | {"pass": false, "reason": "The answer states the replacement will be shipped within 24 hours of the first email, but the policy specifies shipping within 5-7 business days after approval.", "unsupported_claims": ["يتم شحن البديل الموافق عليه خلال 24 ساعة من إرسال أول بريد إلكتروني"]} | refund-ar-1, refund-ar-2, refund-ar-3, refund-ar-4, refund-ar-5 |
| refund-en | Can I get a refund after 60 days? | You are guaranteed a full cash refund after 60 days, regardless of the product's condition or whether there is a defect. | {"pass": false, "reason": "The answer promises a full cash refund after 60 days regardless of condition or defect, which is not supported by the policy.", "unsupported_claims": ["You are guaranteed a full cash refund after 60 days, regardless of the product's condition or whether there is a defect."]} | refund-en-1, refund-en-2, refund-en-3, refund-en-4, refund-en-5 |
| refund-ar | هل أحصل على استرجاع المبلغ بعد 60 يوماً؟ | نضمن استرجاع المبلغ كاملاً بعد 60 يوماً، بغض النظر عن حالة المنتج أو وجود عيب مصنعي. | {"pass": false, "reason": "The answer promises a full refund after 60 days regardless of product condition or defects, which contradicts the policy that only allows exchanges for manufacturing defects reported within 7 days and does not mention refunds after 60 days.", "unsupported_claims": ["نضمن استرجاع المبلغ كاملاً بعد 60 يوماً، بغض النظر عن حالة المنتج أو وجود عيب مصنعي."]} | refund-ar-1, refund-ar-2, refund-ar-3, refund-ar-4, refund-ar-5 |
| exception-en | Can I exchange swimwear after trying it on without a defect? | Yes, you may exchange opened or tried-on swimwear without a manufacturing defect, even without the original tags and packaging. | {"pass": false, "reason": "The answer contradicts the hygiene policy and original condition requirements stated in the evidence.", "unsupported_claims": ["Yes, you may exchange opened or tried-on swimwear without a manufacturing defect, even without the original tags and packaging."]} | refund-en-1, refund-en-2, refund-en-3, refund-en-4, refund-en-5 |
| exception-ar | هل يمكن استبدال القطعة بعد تجربتها دون وجود عيب؟ | نعم، يمكن استبدال القطعة المفتوحة أو التي تم تجربتها دون عيب مصنعي، حتى دون الملصقات والغلاف الأصلي. | {"pass": false, "reason": "The answer contradicts the hygiene restriction and original condition requirements by allowing replacement without original tags and packaging and without a manufacturing defect.", "unsupported_claims": ["يمكن استبدال القطعة المفتوحة أو التي تم تجربتها دون عيب مصنعي، حتى دون الملصقات والغلاف الأصلي"]} | refund-ar-1, refund-ar-2, refund-ar-3, refund-ar-4, refund-ar-5 |

Proposed next behavior change (not applied): make policy-condition review explicit in the generation prompt and judge, while retaining the shipping/dispatch synonym rule. Avoid asserting a specific clock-start event until the client clarifies it. Preserve all eligibility conditions whenever eligibility is described; resolve the requested completeness standard for already-approved timing answers before changing that behavior.
