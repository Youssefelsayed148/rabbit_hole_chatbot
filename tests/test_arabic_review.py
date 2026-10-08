import json
from pathlib import Path

from scripts.export_arabic_review import build_rows


def test_review_pack_preserves_every_arabic_chunk_and_answer():
    root = Path(__file__).resolve().parents[1]
    chunks = [json.loads(line) for line in (root / "data/chunks.jsonl").read_text(encoding="utf-8").splitlines()]
    quality = [{"id": "case-10", "question": "ما هي المهلة؟", "answer": "إجابة مصدرية", "language": "ar", "cited_chunks": ["refund-ar-3"], "pass": True}]
    rows = build_rows({"en": {"send": "Send"}, "ar": {"send": "إرسال"}}, quality)
    for chunk in chunks:
        if chunk["language"] == "ar":
            row = next(row for row in rows if row["source_reference"] == chunk["chunk_id"] + ".text")
            assert row["Arabic_text"] == chunk["text"]
            assert row["corrections"] == "" and "UNREVIEWED" in row["review_status"]
    answer = next(row for row in rows if row["kind"] == "real evaluation answer")
    assert answer["Arabic_text"] == quality[0]["answer"]
    assert any(row["Arabic_text"] == "إرسال" and row["source_string_or_English_reference"] == "Send" for row in rows)
