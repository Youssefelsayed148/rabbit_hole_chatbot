from app.ingest import load_source_chunks, run_ingest
from app.retrieval import retrieve
import pytest


async def count(pool, where="true"):
    return await pool.fetchval(f"SELECT count(*) FROM chunks WHERE {where}")


async def test_ingest_idempotent_and_diff(pool, embedder, settings):
    await pool.execute("DELETE FROM chunks")
    r1 = await run_ingest(pool, embedder, settings)
    assert r1["total_source_chunks"] == 60 and r1["embedded"] == 60 and r1["deleted"] == 0
    assert await count(pool) == 60
    # drafts are excluded by default
    assert await count(pool, "verification_status='needs_review'") == 0

    n_before = embedder.texts_embedded
    r2 = await run_ingest(pool, embedder, settings)
    assert r2["embedded"] == 0 and r2["unchanged"] == 60
    assert embedder.texts_embedded == n_before, "unchanged content must not be re-embedded"


async def test_unreviewed_toggle_adds_and_removes_drafts(pool, embedder, variant):
    on, off = variant(include_unreviewed=True), variant(include_unreviewed=False)
    await pool.execute("DELETE FROM chunks")
    await run_ingest(pool, embedder, off)
    r = await run_ingest(pool, embedder, on)
    assert r["embedded"] == 22 and await count(pool, "verification_status='needs_review'") == 22
    r = await run_ingest(pool, embedder, off)
    assert r["deleted"] == 22 and await count(pool) == 60


async def test_changed_text_is_reembedded(pool, embedder, settings):
    await pool.execute("DELETE FROM chunks")
    await run_ingest(pool, embedder, settings)
    await pool.execute("UPDATE chunks SET content_hash='stale' WHERE chunk_id='refund-en-3'")
    r = await run_ingest(pool, embedder, settings)
    assert r["embedded"] == 1


def test_source_data_is_clean(settings):
    chunks = load_source_chunks(settings)
    assert {c.language for c in chunks} == {"en", "ar"}
    blob = " ".join(c.text for c in chunks).lower()
    for forbidden in ("bearer", "sk-", "authorization"):
        assert forbidden not in blob


async def test_retrieval_finds_refund_doc_whole(pool, embedder, settings):
    await pool.execute("DELETE FROM chunks")
    await run_ingest(pool, embedder, settings)
    chunks = await retrieve(pool, embedder, settings, "manufacturing defect report within days", "en", ["contact"])
    ids = [c.chunk_id for c in chunks]
    assert chunks[0].document_id == "refund-en"
    # parent expansion: the whole (small) refund policy comes along, so the rule keeps its conditions
    assert {f"refund-en-{i}" for i in range(1, 6)} <= set(ids)
    assert "contact-en-1" in ids
    assert all(c.language == "en" for c in chunks)


async def test_arabic_query_gets_only_arabic_sources(pool, embedder, settings):
    await pool.execute("DELETE FROM chunks")
    await run_ingest(pool, embedder, settings)
    chunks = await retrieve(pool, embedder, settings, "مهلة الإبلاغ عن عيب تصنيع", "ar", ["contact"])
    assert chunks and all(c.language == "ar" for c in chunks)
    assert chunks[0].document_id == "refund-ar"


async def test_keyword_side_contributes(pool, embedder, settings):
    """An exact token ('Wonderworld') should surface the brand story via lexical match."""
    await pool.execute("DELETE FROM chunks")
    await run_ingest(pool, embedder, settings)
    chunks = await retrieve(pool, embedder, settings, "Wonderworld", "en")
    assert chunks[0].document_id == "brand-story-en"


async def test_status_filter_applies_at_query_time(pool, embedder, variant):
    on, off = variant(include_unreviewed=True), variant(include_unreviewed=False)
    await pool.execute("DELETE FROM chunks")
    await run_ingest(pool, embedder, on)
    q = "do you accept Visa Mastercard credit cards payment"
    with_drafts = await retrieve(pool, embedder, on, q, "en")
    without = await retrieve(pool, embedder, off, q, "en")  # rows still in DB, but filtered out
    assert any(c.verification_status == "needs_review" for c in with_drafts)
    assert all(c.verification_status != "needs_review" for c in without)


async def test_language_filter_is_a_hard_filter(pool, embedder, settings):
    """English wording asked in 'ar' mode must still return only Arabic records (no cross-language leakage)."""
    await pool.execute("DELETE FROM chunks")
    await run_ingest(pool, embedder, settings)
    chunks = await retrieve(pool, embedder, settings, "manufacturing defect refund policy report within days", "ar", ["contact"])
    assert chunks and all(c.language == "ar" for c in chunks)
    chunks = await retrieve(pool, embedder, settings, "مهلة الإبلاغ عن عيب تصنيع سياسة الاستحقاق", "en", ["contact"])
    assert chunks and all(c.language == "en" for c in chunks)


@pytest.mark.parametrize("query", ["refund hygiene tags packaging privacy", "manufacturing defect intellectual property personal data", "refund privacy policy"])
async def test_contact_reserved_and_expanded_policies_whole(pool, embedder, settings, query):
    await pool.execute("DELETE FROM chunks")
    await run_ingest(pool, embedder, settings)
    chunks = await retrieve(pool, embedder, settings, query, "en", ["contact"])
    assert "contact-en-1" in {c.chunk_id for c in chunks}
    for doc in {c.document_id for c in chunks} - {"contact-en"}:
        expected = await pool.fetchval("SELECT count(*) FROM chunks WHERE document_id=$1", doc)
        assert sum(c.document_id == doc for c in chunks) == expected


async def test_expanded_document_is_not_cut_by_small_budget(pool, embedder, variant):
    s = variant(max_evidence_chunks=3)
    await pool.execute("DELETE FROM chunks")
    await run_ingest(pool, embedder, s)
    chunks = await retrieve(pool, embedder, s, "manufacturing defect report within days", "en", ["contact"])
    ids = {c.chunk_id for c in chunks}
    assert {f"refund-en-{i}" for i in range(1, 6)} <= ids
    assert "contact-en-1" in ids
