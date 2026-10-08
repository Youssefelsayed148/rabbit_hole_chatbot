"""Ingestion: load approved chunks, diff by content hash, embed only what changed, swap atomically.

Source of truth for v1 is the owner-reviewed data pack in data/. Arabic and English stay separate
records (no silent translation). Unreviewed drafts are only indexed when INCLUDE_UNREVIEWED=true.
"""
from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from pathlib import Path

import asyncpg
import numpy as np

from .config import Settings
from .providers import Embedder

log = logging.getLogger("rag.ingest")
INGEST_LOCK_KEY = 0x5248524147494E47


@dataclass
class SourceChunk:
    chunk_id: str
    document_id: str
    language: str
    title: str
    heading: str
    content_type: str
    source_url: str
    text: str
    verification_status: str
    source_updated_at: str | None

    def embed_input(self) -> str:
        # Parent title + heading travel with the text so short sections stay findable.
        parts = [self.title, self.heading if self.heading != self.title else "", self.text]
        return "\n".join(p for p in parts if p)


def _read_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def load_source_chunks(s: Settings) -> list[SourceChunk]:
    allowed = set(s.allowed_statuses)
    chunks: list[SourceChunk] = []

    # 1) Pre-chunked, heading-preserving approved content.
    for r in _read_jsonl(s.data_dir / "chunks.jsonl"):
        if r["verification_status"] not in allowed:
            continue
        chunks.append(
            SourceChunk(
                chunk_id=r["chunk_id"],
                document_id=r["parent_document_id"],
                language=r["language"],
                title=r["title"],
                heading=r["heading"],
                content_type=r["content_type"],
                source_url=r["source_url"],
                text=r["text"],
                verification_status=r["verification_status"],
                source_updated_at=r.get("source_updated_at"),
            )
        )

    # 2) Draft documents (needs_review) are chunked per paragraph, only in test mode.
    if s.include_unreviewed:
        for d in _read_jsonl(s.data_dir / "documents.jsonl"):
            if d["verification_status"] != "needs_review":
                continue
            paras = [p.strip() for p in d["text"].split("\n\n") if p.strip()]
            for i, p in enumerate(paras, 1):
                chunks.append(
                    SourceChunk(
                        chunk_id=f"{d['id']}-p{i}",
                        document_id=d["id"],
                        language=d["language"],
                        title=d["title"],
                        heading=d["title"],
                        content_type=d["content_type"],
                        source_url=d["source_url"],
                        text=p,
                        verification_status="needs_review",
                        source_updated_at=d.get("source_updated_at"),
                    )
                )

    ids = [c.chunk_id for c in chunks]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate chunk_id in source data")
    return chunks


def chunk_hash(c: SourceChunk, embed_model: str, dims: int) -> str:
    # Model + dims are part of the hash so switching embedding model re-embeds everything.
    payload = json.dumps(
        [c.embed_input(), c.document_id, c.content_type, c.source_updated_at,
         c.language, c.verification_status, c.source_url, embed_model, dims],
        ensure_ascii=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


async def run_ingest(pool: asyncpg.Pool, embedder: Embedder, s: Settings) -> dict:
    # Session lock spans embedding without keeping a DB transaction open.
    # Every stage uses this connection; release even if embedding/validation fails.
    async with pool.acquire() as conn:
        await conn.execute("SELECT pg_advisory_lock($1)", INGEST_LOCK_KEY)
        try:
            return await _run_ingest_locked(conn, embedder, s)
        finally:
            await conn.execute("SELECT pg_advisory_unlock($1)", INGEST_LOCK_KEY)


async def _run_ingest_locked(conn: asyncpg.Connection, embedder: Embedder, s: Settings) -> dict:
    source = load_source_chunks(s)
    hashes = {c.chunk_id: chunk_hash(c, s.embed_model, s.embed_dimensions) for c in source}

    rows = await conn.fetch("SELECT chunk_id, content_hash, embedding IS NOT NULL AS has_embedding FROM chunks")
    existing = {r["chunk_id"]: r["content_hash"] for r in rows}
    missing_vectors = {r["chunk_id"] for r in rows if not r["has_embedding"]}

    to_embed = [c for c in source if existing.get(c.chunk_id) != hashes[c.chunk_id] or (s.retrieval_mode == "hybrid" and c.chunk_id in missing_vectors)]
    removed = [cid for cid in existing if cid not in hashes]

    # Embed first (network), then apply all DB changes in one transaction so the index never half-updates.
    if s.retrieval_mode == "keyword":
        # NULL is honest: no fake/zero vectors. Unchanged existing vectors are preserved.
        vectors = [None] * len(to_embed)
    else:
        vectors = await embedder.embed([c.embed_input() for c in to_embed]) if to_embed else []
        if len(vectors) != len(to_embed):
            raise ValueError("embedding count does not match source chunk count")
        vectors = [np.asarray(vec, dtype=np.float32) for vec in vectors]
        if any(vec.shape != (s.embed_dimensions,) or not np.isfinite(vec).all() for vec in vectors):
            raise ValueError("embedding dimensions or values are invalid")
    async with conn.transaction():
        for c, vec in zip(to_embed, vectors):
            await conn.execute(
                """
                INSERT INTO chunks (chunk_id, document_id, language, title, heading, content_type, source_url,
                                    text, content_hash, verification_status, source_updated_at, embedding, updated_at)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12, now())
                ON CONFLICT (chunk_id) DO UPDATE SET
                    document_id=EXCLUDED.document_id, language=EXCLUDED.language, title=EXCLUDED.title,
                    heading=EXCLUDED.heading, content_type=EXCLUDED.content_type, source_url=EXCLUDED.source_url,
                    text=EXCLUDED.text, content_hash=EXCLUDED.content_hash,
                    verification_status=EXCLUDED.verification_status,
                    source_updated_at=EXCLUDED.source_updated_at, embedding=EXCLUDED.embedding, updated_at=now()
                """,
                c.chunk_id, c.document_id, c.language, c.title, c.heading, c.content_type, c.source_url,
                c.text, hashes[c.chunk_id], c.verification_status, c.source_updated_at,
                vec,
            )
        if removed:
            await conn.execute("DELETE FROM chunks WHERE chunk_id = ANY($1::text[])", removed)

    summary = {
        "total_source_chunks": len(source),
        "embedded": len(to_embed) if s.retrieval_mode == "hybrid" else 0,
        "indexed": len(to_embed),
        "unchanged": len(source) - len(to_embed),
        "deleted": len(removed),
        "include_unreviewed": s.include_unreviewed,
    }
    log.info("ingest done: %s", summary)
    return summary
