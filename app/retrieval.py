"""Hybrid retrieval: vector search + keyword search, fused with Reciprocal Rank Fusion (RRF).

Language is a hard filter so an Arabic visitor gets Arabic source text (no translation drift).
Small documents (policies) are pulled in whole around the top hit so a rule is never separated
from its conditions or exceptions.
"""
from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass

import asyncpg
import numpy as np

from .config import Settings
from .providers import Embedder

RRF_K = 60

_STOP = {
    # English
    "the", "a", "an", "is", "are", "was", "were", "do", "does", "did", "can", "i", "you", "your", "my", "me", "we",
    "to", "of", "in", "on", "for", "and", "or", "it", "this", "that", "what", "when", "how", "where", "which",
    "with", "have", "has", "be", "if", "any", "about", "at", "by", "from", "will",
    # Arabic
    "في", "من", "على", "هل", "ما", "ماذا", "هو", "هي", "إلى", "عن", "أن", "ان", "كم", "كيف", "متى", "أين", "مع", "هذا", "هذه",
    "لي", "لا", "أو", "و", "يمكن", "يمكنني",
}


@dataclass
class Chunk:
    chunk_id: str
    document_id: str
    language: str
    title: str
    heading: str
    source_url: str
    text: str
    verification_status: str
    score: float = 0.0


def _row_to_chunk(r: asyncpg.Record, score: float = 0.0) -> Chunk:
    return Chunk(
        chunk_id=r["chunk_id"], document_id=r["document_id"], language=r["language"], title=r["title"],
        heading=r["heading"], source_url=r["source_url"], text=r["text"],
        verification_status=r["verification_status"], score=score,
    )


def _natural(s: str) -> list:
    return [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", s)]


def keyword_tsquery(text: str) -> str:
    """OR-query of meaningful tokens ('simple' config: no stemming, works for Arabic script too)."""
    toks = [t.lower() for t in re.findall(r"\w+", text, flags=re.UNICODE)]
    toks = [t for t in toks if len(t) > 1 and t not in _STOP]
    return " | ".join(dict.fromkeys(toks))  # de-dup, keep order; \w+ tokens are tsquery-safe


COLS = "chunk_id, document_id, language, title, heading, source_url, text, verification_status"


async def _vector_search(conn, qvec, lang, statuses, k) -> list[asyncpg.Record]:
    return await conn.fetch(
        f"SELECT {COLS} FROM chunks WHERE language=$1 AND verification_status = ANY($2::text[]) "
        f"ORDER BY embedding <=> $3 LIMIT $4",
        lang, statuses, qvec, k,
    )


async def _keyword_search(conn, tsq, lang, statuses, k) -> list[asyncpg.Record]:
    if not tsq:
        return []
    return await conn.fetch(
        f"SELECT {COLS} FROM chunks WHERE language=$1 AND verification_status = ANY($2::text[]) "
        f"AND fts @@ to_tsquery('simple', $3) ORDER BY ts_rank_cd(fts, to_tsquery('simple', $3)) DESC LIMIT $4",
        lang, statuses, tsq, k,
    )


def rrf_fuse(*ranked: list[asyncpg.Record]) -> list[tuple[asyncpg.Record, float]]:
    scores: dict[str, float] = {}
    rows: dict[str, asyncpg.Record] = {}
    for lst in ranked:
        for rank, r in enumerate(lst, 1):
            scores[r["chunk_id"]] = scores.get(r["chunk_id"], 0.0) + 1.0 / (RRF_K + rank)
            rows[r["chunk_id"]] = r
    return sorted(((rows[c], sc) for c, sc in scores.items()), key=lambda x: x[1], reverse=True)


async def fetch_documents(pool: asyncpg.Pool, doc_ids: list[str], statuses: list[str]) -> list[Chunk]:
    if not doc_ids:
        return []
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"SELECT {COLS} FROM chunks WHERE document_id = ANY($1::text[]) AND verification_status = ANY($2::text[]) "
            f"ORDER BY document_id",
            doc_ids, statuses,
        )
    return sorted((_row_to_chunk(r) for r in rows), key=lambda c: (c.document_id, _natural(c.chunk_id)))


async def retrieve(
    pool: asyncpg.Pool,
    embedder: Embedder,
    s: Settings,
    query: str,
    language: str,
    always_documents: list[str] | None = None,
) -> list[Chunk]:
    statuses = s.allowed_statuses
    qvec = np.array((await embedder.embed([query]))[0], dtype=np.float32)
    tsq = keyword_tsquery(query)

    async def run(fn, *a):
        async with pool.acquire() as conn:
            return await fn(conn, *a)

    vec_rows, kw_rows = await asyncio.gather(
        run(_vector_search, qvec, language, statuses, s.top_k),
        run(_keyword_search, tsq, language, statuses, s.top_k),
    )
    fused = rrf_fuse(vec_rows, kw_rows)[: s.final_k]
    chunks = [_row_to_chunk(r, sc) for r, sc in fused]

    # Reserve mandatory documents before allocating the evidence budget.
    mandatory = await fetch_documents(
        pool, [f"{d}-{language}" for d in (always_documents or [])], statuses,
    )
    mandatory_ids = {c.chunk_id for c in mandatory}
    groups: dict[str, list[Chunk]] = {}
    for c in chunks:
        if c.chunk_id not in mandatory_ids:
            groups.setdefault(c.document_id, []).append(c)

    selected: list[Chunk] = []
    budget = max(0, s.max_evidence_chunks - len(mandatory))
    for doc_id, hits in groups.items():
        siblings = await fetch_documents(pool, [doc_id], statuses)
        expanded = sum(len(c.text) for c in siblings) <= s.expand_doc_max_chars
        group = siblings if expanded else sorted(hits, key=lambda c: _natural(c.chunk_id))
        # An expanded document is indivisible. The best document may exceed
        # the soft chunk budget; lower-ranked documents must fit in full.
        if expanded:
            if not selected or len(selected) + len(group) <= budget:
                selected.extend(group)
        else:
            selected.extend(group[:max(0, budget - len(selected))])
    return selected + mandatory
