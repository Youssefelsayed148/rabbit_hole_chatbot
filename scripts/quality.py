"""Opt-in real-provider evaluation with the actual generation evidence recorded."""
import argparse
import asyncio
from dataclasses import replace
import json
import os
from pathlib import Path
import re

from app.config import Settings
from app.db import create_pool, init_schema
from app.ingest import run_ingest
from app.pipeline import ChatService, parse_model_json
from app.providers import OpenAIChat, OpenAIEmbedder
from scripts.eval import judge, load_cases


class RecordingChat:
    def __init__(self, delegate):
        self.delegate = delegate
        self.evidence = []
        self.raw = None
        self.records = []

    async def complete(self, messages, *, json_mode=False, max_tokens=700):
        if json_mode:
            turn = messages[-1]["content"]
            self.evidence = [{"chunk_id": cid, "document_id": doc, "text": text}
                             for cid, doc, text in re.findall(
                                 r'<chunk id="([^"]+)" document="([^"]+)"[^>]*>\n(.*?)\n</chunk>', turn, re.S)]
        result = await self.delegate.complete(messages, json_mode=json_mode, max_tokens=max_tokens)
        if json_mode:
            self.raw = result
            self.records.append({"evidence": self.evidence, "raw": result})
        return result


async def run(args):
    if os.environ.get("RUN_REAL_QUALITY") != "1":
        raise RuntimeError("Set RUN_REAL_QUALITY=1 to authorize paid real-provider evaluation")
    s = replace(Settings.from_env(), catalogue_enabled=False, include_unreviewed=False, store_messages=False)
    await init_schema(s.database_url, s.embed_dimensions)
    pool = await create_pool(s.database_url)
    embedder, generator, grader = OpenAIEmbedder(s), OpenAIChat(s), OpenAIChat(s)
    recorder = RecordingChat(generator)
    rows = []
    try:
        await run_ingest(pool, embedder, s)
        service = ChatService(pool, embedder, recorder, s)
        await service.cache_contact_emails()
        cases = load_cases(s.data_dir / "evaluation.jsonl")
        if args.only:
            cases = [c for c in cases if c["id"] == args.only]
        for case in cases:
            recorder.evidence, recorder.raw = [], None
            result = await service.answer(case["question"])
            parsed = parse_model_json(recorder.raw) if recorder.raw else None
            evidence = recorder.evidence
            model_cited = parsed["sources"] if parsed else []
            returned_docs = {source["document_id"] for source in result.sources}
            accepted_ids = {chunk["chunk_id"] for chunk in evidence if chunk["document_id"] in returned_docs}
            cited = [cid for cid in model_cited if cid in accepted_ids]
            # Deterministic catalogue-disabled replies use the approved contact cache,
            # not per-question retrieval. Record that provenance separately.
            cached = []
            if not recorder.raw:
                cached = [dict(r) for r in await pool.fetch(
                    "SELECT chunk_id, document_id, text FROM chunks WHERE document_id=$1",
                    "contact-" + result.language)]
            verdict = await judge(grader, case, result.answer, evidence=evidence + cached)
            cite_ok = set(case["expected_document_ids"]) <= {s["document_id"] for s in result.sources}
            row = {**case, "answer": result.answer, "language": result.language,
                   "chat_model": s.chat_model, "embed_model": s.embed_model, "embed_dimensions": s.embed_dimensions,
                   "generation_called": bool(recorder.raw), "model_cited_chunks": model_cited,
                   "needs_human": result.needs_human, "sources": result.sources,
                   "retrieved_chunks": evidence, "cited_chunks": cited, "verdict": verdict,
                   "cached_support_evidence": cached,
                   "pass": cite_ok and verdict.get("pass") is True, "cite_ok": cite_ok}
            rows.append(row)
            print(case["id"], "PASS" if row["pass"] else "FAIL", cited, flush=True)
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        write_report(rows, out)
        return 0 if all(r["pass"] for r in rows) else 1
    finally:
        await pool.close()
        for provider in (embedder, generator, grader):
            await provider.client.close()


def write_report(rows, out):
    out.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    grounded = sum(row['verdict'].get('pass') is True for row in rows)
    overall = sum(row['pass'] for row in rows)
    lines = ["# Real-provider quality results", "", "Each row records actual generation evidence in the adjacent JSON report.",
             f"Overall: {overall}/{len(rows)} pass; grounding judge: {grounded}/{len(rows)} pass. Overall pass requires BOTH expected document citations and a passing grounding verdict.", "",
             "| Case / question | Result | Cited chunks | Unsupported claims | Judge reason |", "|---|---|---|---|---|"]
    esc = lambda value: str(value).replace("|", "\\|").replace("\n", "<br>")
    for row in rows:
        citation_text = ', '.join(row['cited_chunks']) or ('None (deterministic path)' if not row['retrieved_chunks'] else 'None')
        missing = set(row['expected_document_ids']) - {s['document_id'] for s in row['sources']}
        reason = row['verdict']['reason'] + (" CITATION FAILURE: missing " + ', '.join(sorted(missing)) if missing else '')
        lines.append("| " + " | ".join(map(esc, [row['id'] + ': ' + row['question'],
            'PASS' if row['pass'] else 'FAIL', citation_text,
            '; '.join(row['verdict'].get('unsupported_claims', [])) or 'None identified by judge', reason])) + " |")
    out.with_suffix(".md").write_text("\n".join(lines) + "\n", encoding="utf-8")

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only")
    parser.add_argument("--out", default="docs/quality-results.json")
    return asyncio.run(run(parser.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
