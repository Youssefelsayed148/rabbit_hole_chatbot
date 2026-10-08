"""PostgreSQL search works without keys, model downloads or embedding calls."""
import json
from dataclasses import replace
from pathlib import Path

import pytest
import pytest_asyncio
from starlette.testclient import TestClient

from app.config import Settings
from app.ingest import run_ingest
from app.main import create_app
from app.providers import KeywordOnlyEmbedder, build_embedder
from app.retrieval import retrieve


@pytest_asyncio.fixture
async def keyword_settings(pool, settings):
    s = replace(settings, retrieval_mode="keyword", openai_api_key="")
    await run_ingest(pool, KeywordOnlyEmbedder(), s)
    return s


def test_keyword_provider_needs_no_embedding_key_or_model():
    assert isinstance(build_embedder(Settings(retrieval_mode="keyword")), KeywordOnlyEmbedder)
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        build_embedder(Settings(retrieval_mode="hybrid"))
    with pytest.raises(ValueError, match="RETRIEVAL_MODE"):
        Settings(retrieval_mode="invalid").validate_startup()


async def test_keyword_ingest_uses_null_vectors_and_hybrid_can_restore(pool, settings, embedder):
    await pool.execute("DELETE FROM chunks")
    keyword = replace(settings, retrieval_mode="keyword", openai_api_key="")
    first = await run_ingest(pool, KeywordOnlyEmbedder(), keyword)
    assert first["indexed"] == 60 and first["embedded"] == 0
    assert await pool.fetchval("SELECT count(*) FROM chunks WHERE embedding IS NULL") == 60
    again = await run_ingest(pool, KeywordOnlyEmbedder(), keyword)
    assert again["indexed"] == 0 and again["unchanged"] == 60
    restored = await run_ingest(pool, embedder, settings)
    assert restored["embedded"] == 60
    preserved = await run_ingest(pool, KeywordOnlyEmbedder(), keyword)
    assert preserved["indexed"] == 0
    assert await pool.fetchval("SELECT count(*) FROM chunks WHERE embedding IS NOT NULL") == 60


CASES = [json.loads(line) for line in (Path(__file__).resolve().parents[1] / "data/evaluation.jsonl").read_text(encoding="utf-8").splitlines()]


@pytest.mark.parametrize('case', [c for c in CASES if c['expected_document_ids']], ids=lambda c:c['id'])
async def test_keyword_baseline_retrieval(pool, keyword_settings, case):
    from app.router import detect_language
    lang = detect_language(case['question'])
    chunks = await retrieve(pool, KeywordOnlyEmbedder(), keyword_settings, case['question'], lang, ['contact'])
    ids = {c.document_id for c in chunks}
    assert set(case['expected_document_ids']) <= ids
    assert all(c.language == lang and c.verification_status != 'needs_review' for c in chunks)
    if 'refund-' + lang in case['expected_document_ids']:
        assert {f'refund-{lang}-{i}' for i in range(1,6)} <= {c.chunk_id for c in chunks}


async def test_keyword_no_match_returns_only_contact(pool, keyword_settings):
    chunks = await retrieve(pool, KeywordOnlyEmbedder(), keyword_settings, 'zzzzzzqwerty', 'en', ['contact'])
    assert {c.document_id for c in chunks} == {'contact-en'}


@pytest.mark.parametrize('query,lang,expected', [
    ('What fabric is Dubai Above Mars made of?', 'en', 'product-dubai-above-mars-en'),
    ('What is your refund policy?', 'en', 'refund-en'),
    ('مَا هِي سِيَاسَة الاسْتِرْجَاع؟', 'ar', 'refund-ar'),
    ('What about personal data deletion?', 'en', 'privacy-en'),
])
async def test_keyword_common_queries(pool, keyword_settings, query, lang, expected):
    chunks = await retrieve(pool, KeywordOnlyEmbedder(), keyword_settings, query, lang, ['contact'])
    assert expected in {c.document_id for c in chunks}


@pytest.mark.parametrize("environment", ["development", "production"])
def test_app_starts_and_answers_without_openai_key(variant, chat_model, environment):
    s = variant(retrieval_mode="keyword", openai_api_key="", auto_ingest=True, environment=environment, site_keys=["test-public"], allowed_origins=["https://shop.example"], admin_token="test-admin")
    with TestClient(create_app(settings=s, llm=chat_model)) as client:
        health = client.get('/health').json()
        assert health['status'] == 'ok' and health['retrieval_mode'] == 'keyword'
        if environment == 'development':
            assert health['providers']['embedder'] == 'KeywordOnlyEmbedder'
        response = client.post('/chat', headers={'X-Site-Key': 'test-public'}, json={'message':'When should I report a manufacturing defect?'}).json()
        assert response['sources'][0]['document_id'] == 'refund-en'
        assert not response['needs_human']


async def test_keyword_changes_invalidate_only_changed_vectors(pool, settings, embedder, monkeypatch):
    from app import ingest
    await pool.execute("DELETE FROM chunks")
    await run_ingest(pool, embedder, settings)
    source = ingest.load_source_chunks(settings)
    source[0] = replace(source[0], text=source[0].text + " Updated description.")
    monkeypatch.setattr(ingest, 'load_source_chunks', lambda _: source)
    result = await run_ingest(pool, KeywordOnlyEmbedder(), replace(settings, retrieval_mode='keyword'))
    assert result['indexed'] == 1 and result['embedded'] == 0
    assert await pool.fetchval('SELECT count(*) FROM chunks WHERE embedding IS NULL') == 1
    restored = await run_ingest(pool, embedder, settings)
    assert restored['embedded'] == 1


async def test_keyword_filters_existing_drafts(pool, settings):
    enabled = replace(settings, retrieval_mode='keyword', include_unreviewed=True)
    await run_ingest(pool, KeywordOnlyEmbedder(), enabled)
    chunks = await retrieve(pool, KeywordOnlyEmbedder(), replace(enabled, include_unreviewed=False), 'Visa Mastercard expedited shipping', 'en', ['contact'])
    assert all(c.verification_status != 'needs_review' for c in chunks)
