"""Read-only service behavior audit; real calls require RUN_REAL_QUALITY=1."""
import asyncio
from dataclasses import asdict, replace
import json
import os
from pathlib import Path
from unittest.mock import patch

from app.config import Settings
from app.db import create_pool, init_schema
from app.ingest import run_ingest
from app.pipeline import ChatService, parse_model_json
from app.providers import OpenAIChat, OpenAIEmbedder
from app import retrieval
from scripts.eval import judge, load_cases
from scripts.quality import RecordingChat

ROOT = Path(__file__).resolve().parents[1]
BRAND_QUESTIONS = [
    ("en", "What does Rabbit Hole sell?"),
    ("en", "Tell me the story behind the Rabbit Hole brand."),
    ("en", "What inspires Rabbit Hole's brand identity?"),
    ("en", "How would you describe Rabbit Hole's style and its swimwear collection?"),
    ("en", "What is the idea behind Rabbit Hole's swimwear collection?"),
    ("en", "What makes Rabbit Hole's brand story distinctive?"),
    ("ar", "ما قصة علامة رابت هول؟"),
    ("ar", "ما مصدر إلهام رابت هول وما طابع العلامة؟"),
    ("ar", "ما فكرة تشكيلة ملابس السباحة من رابت هول؟"),
]


def audit_case():
    return next(c for c in load_cases(ROOT / "data/evaluation.jsonl") if c["id"] == "case-5")


async def audit():
    if os.environ.get("RUN_REAL_QUALITY") != "1":
        raise RuntimeError("RUN_REAL_QUALITY=1 required for paid audit")
    s = replace(Settings.from_env(), catalogue_enabled=False, include_unreviewed=False, store_messages=False)
    await init_schema(s.database_url, s.embed_dimensions)
    pool = await create_pool(s.database_url)
    embedder, generator, grader = OpenAIEmbedder(s), OpenAIChat(s), OpenAIChat(s)
    recorder = RecordingChat(generator)
    output = {"models": {"chat": s.chat_model, "embedding": s.embed_model, "dimensions": s.embed_dimensions},
              "replacement_runs": [], "adversarial_controls": [], "brand_runs": []}
    out = ROOT / "docs/followup-audit-results.json"
    def save():
        out.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        await run_ingest(pool, embedder, s)
        service = ChatService(pool, embedder, recorder, s)
        await service.cache_contact_emails()
        original_retrieve, original_fuse = retrieval.retrieve, retrieval.rrf_fuse
        trace = {}
        def traced_fuse(*rankings):
            fused = original_fuse(*rankings)
            trace["fused_candidates"] = [{"chunk_id": row["chunk_id"], "document_id": row["document_id"], "rrf_score": score,
                "vector_rank": next((i for i, r in enumerate(rankings[0], 1) if r["chunk_id"] == row["chunk_id"]), None),
                "keyword_rank": next((i for i, r in enumerate(rankings[1], 1) if r["chunk_id"] == row["chunk_id"]), None)}
                for row, score in fused]
            return fused
        async def traced_retrieve(*args, **kwargs):
            with patch("app.retrieval.rrf_fuse", traced_fuse):
                chunks = await original_retrieve(*args, **kwargs)
            trace["selected_chunks"] = [asdict(c) for c in chunks]
            return chunks
        async def answer(question, lang):
            trace.clear()
            recorder.evidence, recorder.raw = [], None
            with patch("app.pipeline.retrieve", traced_retrieve):
                result = await service.answer(question, lang)
            parsed = parse_model_json(recorder.raw) if recorder.raw else None
            return {"question": question, "language": result.language, "answer": result.answer,
                    "sources": result.sources, "needs_human": result.needs_human,
                    "cited_chunks": parsed["sources"] if parsed else [],
                    "evidence": recorder.evidence, **trace}
        case = audit_case()
        for index in range(5):
            row = await answer(case["question"], "en")
            row["run"] = index + 1
            row["verdict"] = await judge(grader, case, row["answer"], evidence=row["evidence"])
            output["replacement_runs"].append(row)
            save()
            print("replacement", index + 1, row["verdict"]["pass"], flush=True)
        chunks = load_cases(ROOT / "data/chunks.jsonl")
        for control in load_cases(ROOT / "data/judge_adversarial.jsonl"):
            evidence = [{"chunk_id": c["chunk_id"], "document_id": c["id"], "text": c["text"]}
                        for c in chunks if c["id"] == "refund-" + control["language"]]
            verdict = await judge(grader, control, control["answer"], evidence=evidence)
            output["adversarial_controls"].append({**control, "evidence": evidence, "verdict": verdict,
                "control_pass": verdict.get("pass") is False})
            save()
            print("adversarial", control["id"], verdict["pass"], flush=True)
        for lang, question in BRAND_QUESTIONS:
            row = await answer(question, lang)
            output["brand_runs"].append(row)
            save()
            print("brand", lang, row["cited_chunks"], flush=True)
        return 0 if all(row["control_pass"] for row in output["adversarial_controls"]) else 1
    finally:
        await pool.close()
        for provider in (embedder, generator, grader):
            await provider.client.close()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(audit()))
