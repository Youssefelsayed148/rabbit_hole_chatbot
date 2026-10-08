# Brand citation triage

Finding: **case 1 has an overly narrow document expectation, not a demonstrated retrieval or citation bug.** No expectation was changed.

The original question asks what Rabbit Hole sells. Both brand and collection documents were retrieved in the historical run; the answer cited only collection-story-en-1. All its claims—men’s swimwear, fashion standards/precision/restraint/detail, composed/intentional pieces, pool/coast/city context—occur in that approved collection chunk. It does not claim Wonderworld inspiration or the brand-specific narrative, so adding brand citations would not demonstrate additional grounding.

| Approved alternative source | Historical real answer | Historical retrieved IDs / cited IDs |
|---|---|---|
| A Swimwear Collection for Season 27<br>Rabbit Hole exists for gentle men who don’t treat swimwear as an afterthought. It was created to bring the same standards found in High end fashion—precision, restraint, and detail—into what you wear when the heat rises and the water calls. Pieces that feel composed, look intentional, and hold their presence whether you’re poolside, on a coastline, or stepping into the city after. | Rabbit Hole sells swimwear designed for men, focusing on high-end fashion standards such as precision, restraint, and detail. Their pieces are intended to feel composed and look intentional, suitable for poolside, coastline, or city wear. | Retrieved: collection-story-en-1, brand-story-en-1, brand-story-en-2, brand-story-en-3, brand-story-en-4, contact-en-1. Cited: collection-story-en-1 |

## Scored reproduction and phrasings

Scores were not captured in the historical report and cannot be backfilled. These are newly measured traces from real calls. RRF = sum of 1/(60 + rank) across vector and keyword lists. final_k=4 selects seed chunks; small-document expansion and mandatory contact retrieval produce native returned Chunk.score=0. That zero is not a similarity score. The table therefore shows actual fused candidate RRF and seed status separately from returned score; no retrieval/scoring behavior was changed.

Six EN questions (original plus five additional phrasings), three AR questions; each uses a fresh conversation.

| Question | Language | Retrieved chunks | Cited chunks | Exact answer |
|---|---|---|---|---|
| What does Rabbit Hole sell? | en | collection-story-en-1, brand-story-en-1, brand-story-en-2, brand-story-en-3, brand-story-en-4, contact-en-1 | collection-story-en-1 | Rabbit Hole sells swimwear designed for gentlemen who appreciate high-end fashion standards, focusing on precision, restraint, and detail for occasions by the pool, coastline, or city. |
| Tell me the story behind the Rabbit Hole brand. | en | brand-story-en-1, brand-story-en-2, brand-story-en-3, brand-story-en-4, contact-en-1 | brand-story-en-1, brand-story-en-2, brand-story-en-3, brand-story-en-4 | Rabbit Hole is inspired by the concept of Wonderworld, capturing the feeling of crossing into something different without anyone noticing the moment it happens—a familiar scene with one impossible detail or a quiet distortion. The brand lives in the tension between real and unreal, always cinematic, elegant, and never loud. It communicates through silhouette, texture, light, and mood rather than logos or noise, expressing confidence without needing approval. Each collection is like a chapter with its own atmosphere and visual language, maintaining a polished, mysterious, and composed signature. Rabbit Hole is designed for gentle men who notice details most people miss and prefer their luxury to be felt rather than announced. |
| What inspires Rabbit Hole's brand identity? | en | brand-story-en-1, brand-story-en-2, brand-story-en-3, brand-story-en-4, contact-en-1 | brand-story-en-1 | Rabbit Hole's brand identity is inspired by the concept of Wonderworld, focusing on the feeling of crossing into something different without it being overtly noticed. It embodies a tension between the real and unreal, creating a cinematic, elegant, and subtle presence rather than loud or obvious branding. |
| How would you describe Rabbit Hole's style and its swimwear collection? | en | collection-story-en-1, brand-story-en-1, brand-story-en-2, brand-story-en-3, brand-story-en-4, contact-en-1 | collection-story-en-1, brand-story-en-2, brand-story-en-4 | Rabbit Hole's style is elegant, polished, and composed, focusing on subtlety rather than loud logos or noise. It communicates through silhouette, texture, light, and mood, appealing to gentle men who appreciate detail and luxury that is felt rather than announced. The swimwear collection for Season 27 embodies these values, offering pieces that feel composed, look intentional, and maintain presence whether poolside, on a coastline, or in the city. |
| What is the idea behind Rabbit Hole's swimwear collection? | en | collection-story-en-1, brand-story-en-1, brand-story-en-2, brand-story-en-3, brand-story-en-4, contact-en-1 | collection-story-en-1 | Rabbit Hole's swimwear collection is designed for gentle men who treat swimwear with the same precision, restraint, and detail as high-end fashion. The pieces are meant to feel composed, look intentional, and maintain their presence whether poolside, on a coastline, or in the city, reflecting a polished and thoughtful approach to swimwear. |
| What makes Rabbit Hole's brand story distinctive? | en | brand-story-en-1, brand-story-en-2, brand-story-en-3, brand-story-en-4, contact-en-1 | brand-story-en-1, brand-story-en-2, brand-story-en-3, brand-story-en-4 | Rabbit Hole's brand story is distinctive because it is inspired by the concept of Wonderworld, focusing on the subtle feeling of crossing into something different without obvious signs. The brand emphasizes elegance, subtlety, and a cinematic quality, communicating through silhouette, texture, light, and mood rather than logos or noise. Each collection tells its own unique story while maintaining a polished, mysterious, and composed signature, appealing to those who appreciate understated luxury and attention to detail. |
| ما قصة علامة رابت هول؟ | ar | brand-story-ar-1, brand-story-ar-2, brand-story-ar-3, brand-story-ar-4, collection-story-ar-1, contact-ar-1 | brand-story-ar-1, brand-story-ar-2, brand-story-ar-3, brand-story-ar-4 | رابت هول مستوحاة من عالم العجائب بلا تنكّر، حيث تمزج بين الواقع والخيال بخفة، وتقدم تجربة أنيقة وهادئة. العلامة لا تعتمد على الضجيج أو الشعارات، بل تتحدث عبر القصة والملمس والضوء، مع حضور واثق لا يحتاج إلى تفسير. كل إصدار من رابت هول هو فصل جديد يحمل لغته البصرية الخاصة، مع توقيع مصقول وغامض ومتزن. صممت العلامة للجنتلمان الذين يلاحظون التفاصيل الدقيقة ويفضلون أن تُحس فخامتهُم. |
| ما مصدر إلهام رابت هول وما طابع العلامة؟ | ar | brand-story-ar-1, brand-story-ar-2, brand-story-ar-3, brand-story-ar-4, collection-story-ar-1, contact-ar-1 | brand-story-ar-1 | رابت هول مستوحاة من عالم العجائب بلا تنكّر، حيث تعيش في التوتر الدقيق بين الحقيقي وغير الحقيقي، بطابع سينمائي، أنيق، وهادئ. |
| ما فكرة تشكيلة ملابس السباحة من رابت هول؟ | ar | collection-story-ar-1, refund-ar-1, refund-ar-2, refund-ar-3, refund-ar-4, refund-ar-5, contact-ar-1 | collection-story-ar-1 | تشكيلة ملابس السباحة من رابت هول موجهة للجنتلمان الذين يرون ملابس السباحة امتدادًا لأسلوبهم وليست مجرد تفصيلة ثانوية. تم تصميمها لنقل معايير الأزياء الراقية مثل الدقة والاتزان والاهتمام بالتفاصيل إلى الملابس التي ترتديها عند السباحة أو التواجد بجانب المسبح أو على الساحل أو حتى في المدينة بعد ذلك. |

### Trace 1: What does Rabbit Hole sell?

| Retrieved chunk | Native returned score | Measured fused RRF (if candidate) | Top-4 seed? | Vector rank | Keyword rank | Cited? |
|---|---|---|---|---|---|---|
| collection-story-en-1 | 0.0 | 0.032522475 | Yes | 1 | 2 | True |
| brand-story-en-1 | 0.0 | 0.031754032 | Yes | 2 | 4 | False |
| brand-story-en-2 | 0.0 | 0.030536131 | No; sibling/mandatory | 6 | 5 | False |
| brand-story-en-3 | 0.0 | 0.032266458 | Yes | 3 | 1 | False |
| brand-story-en-4 | 0.0 | 0.031498016 | Yes | 4 | 3 | False |
| contact-en-1 | 0.0 | 0.030536131 | No; sibling/mandatory | 5 | 6 | False |

### Trace 2: Tell me the story behind the Rabbit Hole brand.

| Retrieved chunk | Native returned score | Measured fused RRF (if candidate) | Top-4 seed? | Vector rank | Keyword rank | Cited? |
|---|---|---|---|---|---|---|
| brand-story-en-1 | 0.0 | 0.032522475 | Yes | 1 | 2 | True |
| brand-story-en-2 | 0.0 | 0.032002048 | Yes | 2 | 3 | True |
| brand-story-en-3 | 0.0 | 0.032266458 | Yes | 3 | 1 | True |
| brand-story-en-4 | 0.0 | 0.031250000 | Yes | 4 | 4 | True |
| contact-en-1 | 0.0 | 0.030076888 | No; sibling/mandatory | 6 | 7 | False |

### Trace 3: What inspires Rabbit Hole's brand identity?

| Retrieved chunk | Native returned score | Measured fused RRF (if candidate) | Top-4 seed? | Vector rank | Keyword rank | Cited? |
|---|---|---|---|---|---|---|
| brand-story-en-1 | 0.0 | 0.032786885 | Yes | 1 | 1 | True |
| brand-story-en-2 | 0.0 | 0.032258065 | Yes | 2 | 2 | False |
| brand-story-en-3 | 0.0 | 0.031498016 | Yes | 4 | 3 | False |
| brand-story-en-4 | 0.0 | 0.031498016 | Yes | 3 | 4 | False |
| contact-en-1 | 0.0 | 0.029850746 | No; sibling/mandatory | 7 | 7 | False |

### Trace 4: How would you describe Rabbit Hole's style and its swimwear collection?

| Retrieved chunk | Native returned score | Measured fused RRF (if candidate) | Top-4 seed? | Vector rank | Keyword rank | Cited? |
|---|---|---|---|---|---|---|
| collection-story-en-1 | 0.0 | 0.032786885 | Yes | 1 | 1 | True |
| brand-story-en-1 | 0.0 | 0.031754032 | Yes | 2 | 4 | False |
| brand-story-en-2 | 0.0 | 0.031257631 | Yes | 3 | 5 | True |
| brand-story-en-3 | 0.0 | 0.031754032 | Yes | 4 | 2 | False |
| brand-story-en-4 | 0.0 | 0.031257631 | No; sibling/mandatory | 5 | 3 | True |
| contact-en-1 | 0.0 | 0.030303030 | No; sibling/mandatory | 6 | 6 | False |

### Trace 5: What is the idea behind Rabbit Hole's swimwear collection?

| Retrieved chunk | Native returned score | Measured fused RRF (if candidate) | Top-4 seed? | Vector rank | Keyword rank | Cited? |
|---|---|---|---|---|---|---|
| collection-story-en-1 | 0.0 | 0.032786885 | Yes | 1 | 1 | True |
| brand-story-en-1 | 0.0 | 0.031754032 | Yes | 2 | 4 | False |
| brand-story-en-2 | 0.0 | 0.031009615 | No; sibling/mandatory | 4 | 5 | False |
| brand-story-en-3 | 0.0 | 0.032002048 | Yes | 3 | 2 | False |
| brand-story-en-4 | 0.0 | 0.031257631 | Yes | 5 | 3 | False |
| contact-en-1 | 0.0 | 0.030076888 | No; sibling/mandatory | 7 | 6 | False |

### Trace 6: What makes Rabbit Hole's brand story distinctive?

| Retrieved chunk | Native returned score | Measured fused RRF (if candidate) | Top-4 seed? | Vector rank | Keyword rank | Cited? |
|---|---|---|---|---|---|---|
| brand-story-en-1 | 0.0 | 0.032002048 | Yes | 3 | 2 | True |
| brand-story-en-2 | 0.0 | 0.032002048 | Yes | 2 | 3 | True |
| brand-story-en-3 | 0.0 | 0.032018443 | Yes | 4 | 1 | True |
| brand-story-en-4 | 0.0 | 0.032018443 | Yes | 1 | 4 | True |
| contact-en-1 | 0.0 | 0.030076888 | No; sibling/mandatory | 6 | 7 | False |

### Trace 7: ما قصة علامة رابت هول؟

| Retrieved chunk | Native returned score | Measured fused RRF (if candidate) | Top-4 seed? | Vector rank | Keyword rank | Cited? |
|---|---|---|---|---|---|---|
| brand-story-ar-1 | 0.0 | 0.032018443 | Yes | 4 | 1 | True |
| brand-story-ar-2 | 0.0 | 0.032522475 | Yes | 1 | 2 | True |
| brand-story-ar-3 | 0.0 | 0.015151515 | No; sibling/mandatory | 6 | None | True |
| brand-story-ar-4 | 0.0 | 0.032002048 | Yes | 2 | 3 | True |
| collection-story-ar-1 | 0.0 | 0.031498016 | Yes | 3 | 4 | False |
| contact-ar-1 | 0.0 | 0.014925373 | No; sibling/mandatory | 7 | None | False |

### Trace 8: ما مصدر إلهام رابت هول وما طابع العلامة؟

| Retrieved chunk | Native returned score | Measured fused RRF (if candidate) | Top-4 seed? | Vector rank | Keyword rank | Cited? |
|---|---|---|---|---|---|---|
| brand-story-ar-1 | 0.0 | 0.032266458 | Yes | 3 | 1 | True |
| brand-story-ar-2 | 0.0 | 0.032258065 | Yes | 2 | 2 | False |
| brand-story-ar-3 | 0.0 | 0.015625000 | No; sibling/mandatory | 4 | None | False |
| brand-story-ar-4 | 0.0 | 0.032266458 | Yes | 1 | 3 | False |
| collection-story-ar-1 | 0.0 | 0.031009615 | Yes | 5 | 4 | False |
| contact-ar-1 | 0.0 | 0.014925373 | No; sibling/mandatory | 7 | None | False |

### Trace 9: ما فكرة تشكيلة ملابس السباحة من رابت هول؟

| Retrieved chunk | Native returned score | Measured fused RRF (if candidate) | Top-4 seed? | Vector rank | Keyword rank | Cited? |
|---|---|---|---|---|---|---|
| collection-story-ar-1 | 0.0 | 0.032786885 | Yes | 1 | 1 | True |
| refund-ar-1 | 0.0 | Not a fused candidate; expansion/mandatory | No; sibling/mandatory | None | None | False |
| refund-ar-2 | 0.0 | 0.032002048 | Yes | 3 | 2 | False |
| refund-ar-3 | 0.0 | Not a fused candidate; expansion/mandatory | No; sibling/mandatory | None | None | False |
| refund-ar-4 | 0.0 | Not a fused candidate; expansion/mandatory | No; sibling/mandatory | None | None | False |
| refund-ar-5 | 0.0 | Not a fused candidate; expansion/mandatory | No; sibling/mandatory | None | None | False |
| contact-ar-1 | 0.0 | 0.014705882 | No; sibling/mandatory | 8 | None | False |

The Arabic collection-only question did not receive brand chunks in final generation evidence: the complete refund document was expanded ahead of the brand document, and atomic document budgeting skipped the brand group. Brand candidates were present in the top four fused seeds (see raw JSON), but the answer used only collection facts and cited collection-story-ar-1. This does not show failure to retrieve required evidence for that question. Explicit Arabic brand questions received/cited brand evidence.

## Proposed expectation change — awaiting decision

For ‘What does Rabbit Hole sell?’, require `expected_document_ids=["collection-story-en"]`, keep the existing men’s-swimwear/collection-story behavioral requirement, and continue grounding every claim against the actually retrieved/cited evidence. Do not accept a contact-only or uncited answer.

Retain explicit brand-story coverage in a separate permanent eval question, e.g. ‘What inspires Rabbit Hole’s brand identity?’ requiring brand-story-en and the source-supported Wonderworld/brand narrative. Use separate Arabic records for equivalent Arabic coverage. This is a proposed correction to question/evidence alignment, not an applied relaxation to make the old 14-case report green.

No retrieval/fusion/citation-step fix is warranted by case 1. The added offline regression verifies a collection-grounded answer is not forcibly given an unrelated brand citation. No new product facts or forced citations were added.
