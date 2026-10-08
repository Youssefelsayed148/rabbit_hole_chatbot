"""Render captured audit evidence without additional model calls."""
import ast
import difflib
import inspect
import json
from pathlib import Path

from scripts.eval import judge

ROOT = Path(__file__).resolve().parents[1]

# Reconstructed from the source read before the previous phase's edit. This
# workspace has no Git metadata; this is not presented as a Git-generated diff.
BEFORE = '''JUDGE_SYSTEM = (
    "You grade a website chatbot answer. Given the visitor question, the REQUIRED BEHAVIOR and the answer, decide "
    "whether the answer satisfies the required behavior AND contains no invented facts (prices, stock, fees, "
    "destinations, delivery times, addresses, promises beyond the policy). "
    'Reply as JSON: {"pass": true|false, "reason": "<one sentence>"}.'
)


async def judge(chat, case: dict, answer: str) -> dict:
    raw = await chat.complete(
        [{"role": "system", "content": JUDGE_SYSTEM},
         {"role": "user", "content": f"Question: {case['question']}\\nREQUIRED BEHAVIOR: {case['required_behavior']}\\nAnswer: {answer}"}],
        json_mode=True, max_tokens=150,
    )
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"pass": False, "reason": f"unparsable judge output: {raw[:80]}"}
'''


def esc(value):
    return str(value).replace("|", "\\|").replace("\n", "<br>")


def table_row(values):
    return "| " + " | ".join(esc(value) for value in values) + " |"


def main():
    data = json.loads((ROOT / "docs/followup-audit-results.json").read_text(encoding="utf-8"))
    chunks = [json.loads(line) for line in (ROOT / "data/chunks.jsonl").read_text(encoding="utf-8").splitlines()]
    previous = json.loads((ROOT / "docs/quality-results.json").read_text(encoding="utf-8"))
    historical = next(row for row in previous if row["id"] == "case-5")
    final = data["replacement_runs"][-1]
    lines = ["# Replacement judge audit", "", "No judge, generation prompt, production retrieval, API shape or eval expectation was changed during this audit.", "",
             "## Side-by-side captured comparisons", "", "The historical full-quality row includes its actual evidence payload; the current final repeat also records its exact evidence.", "",
             "| Run | Source process chunk | Real answer | Judge verdict / actual evidence IDs |", "|---|---|---|---|"]
    source = next(c["text"] for c in chunks if c["chunk_id"] == "refund-en-5")
    for label, row, evidence in [("Previous full quality", historical, historical["retrieved_chunks"]), ("Current repeat 5 (final)", final, final["evidence"])]:
        lines.append(table_row([label, source, row["answer"], json.dumps(row["verdict"], ensure_ascii=False) + " Evidence: " + ', '.join(c["chunk_id"] for c in evidence)]))
    lines += ["", "The previous final widget smoke answer was: “According to the refund policy, once a replacement request is approved, the replacement product will be shipped within 5-7 working days.” Its saved verdict was PASS. That smoke artifact did not persist the raw judge evidence payload; it cannot be reconstructed as an exact historical input. Current repeat 5 reproduces the wording and records its evidence.", "",
              "## Complete defect/replacement source", "", "English is render_verified; Arabic is source_extracted and still needs native-speaker/owner approval.", "",
              "| EN source chunk / exact text | AR source chunk / exact text |", "|---|---|"]
    for index in range(2, 6):
        en = next(c for c in chunks if c["chunk_id"] == f"refund-en-{index}")
        ar = next(c for c in chunks if c["chunk_id"] == f"refund-ar-{index}")
        lines.append(table_row([en["chunk_id"] + ': ' + en["text"], ar["chunk_id"] + ': ' + ar["text"]]))
    lines += ["", "## Condition audit", "", "Replacement shipping is explicitly conditional on approval; receipt and inspection precede the approval/status process. Defect exchange eligibility also has the separate prerequisites below. An already-approved timing question is narrower than a complete eligibility explanation, but these answers do not reproduce every policy condition.", "",
              "| Condition/detail | Source | Previous final smoke / current repeat 5 | Five repeats |", "|---|---|---|---|",
              "| Approval | refund-*-5 | Kept | Kept 5/5 |",
              "| Receipt and inspection | refund-*-5 | Omitted | Explicit 3/5 (runs 1, 2, 4); omitted 2/5 (3, 5) |",
              "| Report defect within 7 days of delivery | refund-*-3 | Omitted | Omitted 5/5 |",
              "| Manufacturing defect confirmed after inspection | refund-*-3 | Omitted | Omitted 5/5 |",
              "| Original condition, unworn, original tags and packaging | refund-*-4 | Omitted | Omitted 5/5 |",
              "| Opened/tried-on restriction together with defect exception | refund-*-2 | Omitted | Omitted 5/5 |",
              "| Request-status email | refund-*-5 | Omitted process detail; not an eligibility condition | Omitted 5/5 |",
              "| 5–7 working days; shipping rather than arrival | refund-*-5 | Kept | Kept 5/5 |", "",
              "Runs 1/2/4 attach the period to receipt/inspection. The source gives that process sequence but does not explicitly name the event that starts the 5–7-day clock. Treat that starting-point interpretation as unresolved, rather than certify it from a judge PASS.", "",
              "Exact client wording question: **‘Your published policy says, “If approved, the replacement product will be shipped within 5–7 working days.” Which event starts those 5–7 working days: receipt of the returned product, completion of inspection, or approval of the replacement? Please confirm the exact wording we should publish.’**", "",
              "The literal shipping/dispatch synonym change remains source-supported. The broader condition-preservation claim was too strong: a PASS on this narrow case does not demonstrate that all refund-policy prerequisites are present. No answer or source was patched during this audit.", "",
              "## Judge before/after", "", "See `judge-change.diff`: the original judge source is reconstructed from the prior captured source read because there is no Git history here. The after side is read from the current implementation.", "",
              "The original failure rejected: “According to the refund policy, if a replacement is approved, the replacement product will be shipped within 5-7 working days after the product is received and inspected.” Reason: “The answer states the correct shipping time but does not label the shipment as a replacement dispatch as required.”", "",
              "The current judge accepts that semantic construction without requiring the literal word ‘dispatch’. It now receives evidence, requests unsupported claims, requires boolean/schema validity and forces FAIL when unsupported claims are admitted. It also accepts approval-only phrasing in runs 3/5 despite the omissions above. The before/after acceptance is empirical for the recorded answers, not a claim that the older stochastic judge always rejected every synonym.", "",
              "## Five real replacement runs", "", "Independent fresh conversations, same model/config/evidence pack, no retry-until-green selection.", "",
              "| Run | Exact real answer | Cited chunks | Verdict | Receipt/inspection explicit? |", "|---|---|---|---|---|"]
    for row in data["replacement_runs"]:
        lines.append(table_row([row["run"], row["answer"], ', '.join(row["cited_chunks"]), json.dumps(row["verdict"], ensure_ascii=False), "Yes" if row["run"] in (1, 2, 4) else "No"]))
    lines += ["", "## Adversarial controls", "", "These are intentionally invalid test answers, never approved business facts. Each judge input contained the five policy chunks in the same language. All eight must FAIL; all eight did.", "",
              "| Control | Question | Invalid answer | Judge verdict / unsupported claims | Evidence |", "|---|---|---|---|---|"]
    for row in data["adversarial_controls"]:
        lines.append(table_row([row["id"], row["question"], row["answer"], json.dumps(row["verdict"], ensure_ascii=False), ', '.join(c["chunk_id"] for c in row["evidence"])]))
    lines += ["", "Proposed next behavior change (not applied): make policy-condition review explicit in the generation prompt and judge, while retaining the shipping/dispatch synonym rule. Avoid asserting a specific clock-start event until the client clarifies it. Preserve all eligibility conditions whenever eligibility is described; resolve the requested completeness standard for already-approved timing answers before changing that behavior."]
    (ROOT / "docs/replacement-judge-audit.md").write_text('\n'.join(lines) + '\n', encoding="utf-8")

    raw = (ROOT / "scripts/eval.py").read_text(encoding="utf-8")
    assignment = next(node for node in ast.parse(raw).body if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'JUDGE_SYSTEM' for t in node.targets))
    after = ast.get_source_segment(raw, assignment) + '\n\n\n' + inspect.getsource(judge)
    diff = ''.join(difflib.unified_diff(BEFORE.splitlines(True), after.splitlines(True), fromfile='before-judge-recorded', tofile='after-judge-current'))
    (ROOT / "docs/judge-change.diff").write_text(diff, encoding="utf-8")

    historical_brand = next(row for row in previous if row["id"] == 'case-1')
    lines = ["# Brand citation triage", "", "Finding: **case 1 has an overly narrow document expectation, not a demonstrated retrieval or citation bug.** No expectation was changed.", "",
             "The original question asks what Rabbit Hole sells. Both brand and collection documents were retrieved in the historical run; the answer cited only collection-story-en-1. All its claims—men’s swimwear, fashion standards/precision/restraint/detail, composed/intentional pieces, pool/coast/city context—occur in that approved collection chunk. It does not claim Wonderworld inspiration or the brand-specific narrative, so adding brand citations would not demonstrate additional grounding.", "",
             "| Approved alternative source | Historical real answer | Historical retrieved IDs / cited IDs |", "|---|---|---|"]
    collection = next(c for c in chunks if c['chunk_id'] == 'collection-story-en-1')
    lines.append(table_row([collection['text'], historical_brand['answer'], 'Retrieved: ' + ', '.join(c['chunk_id'] for c in historical_brand['retrieved_chunks']) + '. Cited: ' + ', '.join(historical_brand['cited_chunks'])]))
    lines += ["", "## Scored reproduction and phrasings", "", "Scores were not captured in the historical report and cannot be backfilled. These are newly measured traces from real calls. RRF = sum of 1/(60 + rank) across vector and keyword lists. final_k=4 selects seed chunks; small-document expansion and mandatory contact retrieval produce native returned Chunk.score=0. That zero is not a similarity score. The table therefore shows actual fused candidate RRF and seed status separately from returned score; no retrieval/scoring behavior was changed.", "",
              "Six EN questions (original plus five additional phrasings), three AR questions; each uses a fresh conversation.", "",
              "| Question | Language | Retrieved chunks | Cited chunks | Exact answer |", "|---|---|---|---|---|"]
    for row in data['brand_runs']:
        lines.append(table_row([row['question'], row['language'], ', '.join(c['chunk_id'] for c in row['selected_chunks']), ', '.join(row['cited_chunks']), row['answer']]))
    for index, row in enumerate(data['brand_runs'], 1):
        lines += ["", f"### Trace {index}: {row['question']}", "", "| Retrieved chunk | Native returned score | Measured fused RRF (if candidate) | Top-4 seed? | Vector rank | Keyword rank | Cited? |", "|---|---|---|---|---|---|---|"]
        candidates = {c['chunk_id']: (i, c) for i, c in enumerate(row['fused_candidates'], 1)}
        for c in row['selected_chunks']:
            rank, candidate = candidates.get(c['chunk_id'], (None, {}))
            lines.append(table_row([c['chunk_id'], c['score'], f"{candidate['rrf_score']:.9f}" if candidate else 'Not a fused candidate; expansion/mandatory',
                                   'Yes' if rank and rank <= 4 else 'No; sibling/mandatory', candidate.get('vector_rank'), candidate.get('keyword_rank'), c['chunk_id'] in row['cited_chunks']]))
    lines += ["", "The Arabic collection-only question did not receive brand chunks in final generation evidence: the complete refund document was expanded ahead of the brand document, and atomic document budgeting skipped the brand group. Brand candidates were present in the top four fused seeds (see raw JSON), but the answer used only collection facts and cited collection-story-ar-1. This does not show failure to retrieve required evidence for that question. Explicit Arabic brand questions received/cited brand evidence.", "",
              "## Proposed expectation change — awaiting decision", "",
              "For ‘What does Rabbit Hole sell?’, require `expected_document_ids=[\"collection-story-en\"]`, keep the existing men’s-swimwear/collection-story behavioral requirement, and continue grounding every claim against the actually retrieved/cited evidence. Do not accept a contact-only or uncited answer.", "",
              "Retain explicit brand-story coverage in a separate permanent eval question, e.g. ‘What inspires Rabbit Hole’s brand identity?’ requiring brand-story-en and the source-supported Wonderworld/brand narrative. Use separate Arabic records for equivalent Arabic coverage. This is a proposed correction to question/evidence alignment, not an applied relaxation to make the old 14-case report green.", "",
              "No retrieval/fusion/citation-step fix is warranted by case 1. The added offline regression verifies a collection-grounded answer is not forcibly given an unrelated brand citation. No new product facts or forced citations were added."]
    (ROOT / "docs/brand-citation-triage.md").write_text('\n'.join(lines) + '\n', encoding="utf-8")


if __name__ == "__main__":
    main()
