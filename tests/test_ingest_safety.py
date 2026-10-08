import asyncio
from dataclasses import replace

import pytest

from app import ingest


@pytest.mark.parametrize("field,value", [
    ("document_id", "new-parent"), ("content_type", "new-type"),
    ("source_updated_at", "2026-10-05"),
])
async def test_metadata_changes_update_index(pool, embedder, settings, monkeypatch, field, value):
    await pool.execute("DELETE FROM chunks")
    await ingest.run_ingest(pool, embedder, settings)
    source = ingest.load_source_chunks(settings)
    old_hash = ingest.chunk_hash(source[0], settings.embed_model, settings.embed_dimensions)
    source[0] = replace(source[0], **{field: value})
    assert ingest.chunk_hash(source[0], settings.embed_model, settings.embed_dimensions) != old_hash
    monkeypatch.setattr(ingest, "load_source_chunks", lambda s: source)
    summary = await ingest.run_ingest(pool, embedder, settings)
    assert summary["embedded"] == 1
    row = await pool.fetchrow("SELECT document_id, content_type, source_updated_at FROM chunks WHERE chunk_id=$1", source[0].chunk_id)
    assert row[field] == value


@pytest.mark.parametrize("invalid", ["missing", "extra", "dimensions", "nan"])
async def test_invalid_embeddings_leave_index_unchanged_and_release_lock(pool, embedder, settings, monkeypatch, invalid):
    await pool.execute("DELETE FROM chunks")
    await ingest.run_ingest(pool, embedder, settings)
    before = await pool.fetch("SELECT chunk_id, content_hash FROM chunks ORDER BY chunk_id")
    source = [replace(ingest.load_source_chunks(settings)[0], text="changed source")]
    monkeypatch.setattr(ingest, "load_source_chunks", lambda s: source)

    class InvalidEmbedder:
        async def embed(self, texts):
            vector = [0.0] * settings.embed_dimensions
            if invalid == "missing": return []
            if invalid == "extra": return [vector, vector]
            if invalid == "dimensions": return [[0.0]]
            return [[float("nan")] * settings.embed_dimensions]

    with pytest.raises(ValueError, match="embedding"):
        await ingest.run_ingest(pool, InvalidEmbedder(), settings)
    assert await pool.fetch("SELECT chunk_id, content_hash FROM chunks ORDER BY chunk_id") == before
    # A separate session must be able to acquire the lock after validation fails.
    async with pool.acquire() as first, pool.acquire() as second:
        assert await second.fetchval("SELECT pg_try_advisory_lock($1)", ingest.INGEST_LOCK_KEY)
        await second.execute("SELECT pg_advisory_unlock($1)", ingest.INGEST_LOCK_KEY)
    summary = await asyncio.wait_for(ingest.run_ingest(pool, embedder, settings), timeout=5)
    assert summary["embedded"] == 1 and summary["deleted"] == len(before) - 1


async def test_concurrent_ingest_rechecks_diff_after_lock(pool, embedder, settings):
    await pool.execute("DELETE FROM chunks")
    entered, release = asyncio.Event(), asyncio.Event()

    class BlockingEmbedder:
        async def embed(self, texts):
            entered.set()
            await release.wait()
            return await embedder.embed(texts)

    first = asyncio.create_task(ingest.run_ingest(pool, BlockingEmbedder(), settings))
    await asyncio.wait_for(entered.wait(), timeout=5)
    second = asyncio.create_task(ingest.run_ingest(pool, embedder, settings))
    try:
        async def wait_for_lock():
            while not await pool.fetchval("SELECT EXISTS (SELECT 1 FROM pg_locks WHERE locktype='advisory' AND NOT granted)"):
                await asyncio.sleep(0.01)
        await asyncio.wait_for(wait_for_lock(), timeout=5)
        assert embedder.calls == 0 and not second.done()
    finally:
        release.set()
        results = await asyncio.wait_for(asyncio.gather(first, second), timeout=5)
    assert [r["embedded"] for r in results] == [60, 0]
    assert embedder.calls == 1
