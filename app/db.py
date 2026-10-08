"""PostgreSQL + pgvector access: schema, pool, and small query helpers."""
from __future__ import annotations

import asyncpg
from pgvector.asyncpg import register_vector


def schema_sql(dims: int) -> str:
    # No ANN index on purpose: the corpus is tiny, so exact scan is fast and exact.
    # Add an HNSW index (vector_cosine_ops) if the catalogue grows past ~10k rows.
    return f"""
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS chunks (
    chunk_id            text PRIMARY KEY,
    document_id         text NOT NULL,
    language            text NOT NULL,
    title               text NOT NULL DEFAULT '',
    heading             text NOT NULL DEFAULT '',
    content_type        text NOT NULL DEFAULT '',
    source_url          text NOT NULL DEFAULT '',
    text                text NOT NULL,
    content_hash        text NOT NULL,
    verification_status text NOT NULL,
    source_updated_at   text,
    embedding           vector({dims}),
    fts                 tsvector GENERATED ALWAYS AS (
        to_tsvector('simple', coalesce(title,'') || ' ' || coalesce(heading,'') || ' ' || text)
    ) STORED,
    updated_at          timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE chunks ALTER COLUMN embedding DROP NOT NULL;
CREATE INDEX IF NOT EXISTS chunks_lang_idx ON chunks (language);
CREATE INDEX IF NOT EXISTS chunks_doc_idx  ON chunks (document_id);
CREATE INDEX IF NOT EXISTS chunks_fts_idx  ON chunks USING gin (fts);

CREATE TABLE IF NOT EXISTS conversations (
    conversation_id text PRIMARY KEY,
    created_at      timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS messages (
    id              bigserial PRIMARY KEY,
    conversation_id text NOT NULL REFERENCES conversations(conversation_id) ON DELETE CASCADE,
    role            text NOT NULL CHECK (role IN ('user','assistant')),
    content         text NOT NULL,
    created_at      timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE messages ADD COLUMN IF NOT EXISTS product_references jsonb NOT NULL DEFAULT '[]'::jsonb;
CREATE INDEX IF NOT EXISTS messages_conv_idx ON messages (conversation_id, id);
"""


async def init_schema(dsn: str, dims: int) -> None:
    """Create extension/tables. Runs on a plain connection (the vector codec needs the extension first)."""
    conn = await asyncpg.connect(dsn)
    try:
        await conn.execute(schema_sql(dims))
        # Guard against a silent dimension mismatch after changing EMBED_DIMENSIONS.
        row = await conn.fetchrow(
            "SELECT atttypmod FROM pg_attribute WHERE attrelid = 'chunks'::regclass AND attname = 'embedding'"
        )
        if row and row["atttypmod"] != dims:
            raise RuntimeError(
                f"chunks.embedding is vector({row['atttypmod']}) but EMBED_DIMENSIONS={dims}. "
                "Drop the chunks table (or use a fresh database) and re-ingest."
            )
    finally:
        await conn.close()


async def create_pool(dsn: str) -> asyncpg.Pool:
    return await asyncpg.create_pool(dsn, min_size=1, max_size=10, init=register_vector)
