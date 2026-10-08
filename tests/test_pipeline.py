import json

import pytest

from app.ingest import run_ingest
from app.pipeline import ChatService, parse_model_json


@pytest.fixture
async def svc(pool, embedder, chat_model, settings):
    await pool.execute("DELETE FROM chunks")
    await run_ingest(pool, embedder, settings)
    service = ChatService(pool, embedder, chat_model, settings)
    await service.cache_contact_emails()
    return service


def last_user_turn(chat_model):
    gen = [c for c in chat_model.calls if c["json_mode"]]
    return gen[-1]["messages"][-1]["content"]


async def test_conditional_replacement_shipping_is_supported(svc, chat_model):
    answer = "According to the refund policy, if a replacement is approved, the replacement product will be shipped within 5-7 working days after the product is received and inspected."
    chat_model.next_raw = json.dumps({"answer": answer, "can_answer": True, "sources": ["refund-en-5"]})
    result = await svc.answer("How long does an approved replacement take to ship?")
    assert result.answer == answer and not result.needs_human
    assert result.sources[0]["document_id"] == "refund-en"
    assert 'id="refund-en-5"' in last_user_turn(chat_model)
    assert "If approved, the replacement product will be shipped within 5-7 working days." in last_user_turn(chat_model)


async def test_collection_facts_cite_collection_without_unrelated_brand_citation(svc, chat_model, monkeypatch):
    # Historical case-1 evidence contains both docs. Sources must reflect the
    # chunks the answer actually uses, rather than adding a citation for an eval gate.
    from app.retrieval import fetch_documents
    async def evidence(*args, **kwargs):
        return await fetch_documents(svc.pool, ["brand-story-en", "collection-story-en", "contact-en"], svc.s.allowed_statuses)
    monkeypatch.setattr("app.pipeline.retrieve", evidence)
    answer = "Rabbit Hole sells swimwear designed for men, focusing on high-end fashion standards such as precision, restraint, and detail."
    chat_model.next_raw = json.dumps({"answer": answer, "can_answer": True, "sources": ["collection-story-en-1"]})
    result = await svc.answer("What does Rabbit Hole sell?")
    assert result.answer == answer
    assert [s["document_id"] for s in result.sources] == ["collection-story-en"]
    assert 'id="brand-story-en-1"' in last_user_turn(chat_model)
    assert 'id="collection-story-en-1"' in last_user_turn(chat_model)


async def test_knowledge_question_cites_only_retrieved_sources(svc, chat_model):
    r = await svc.answer("When should I report a manufacturing defect?")
    assert r.intent == "knowledge" and r.language == "en"
    assert r.sources and r.sources[0]["document_id"] == "refund-en"
    assert r.sources[0]["url"].endswith("/refund")
    assert not r.needs_human
    turn = last_user_turn(chat_model)
    assert "<evidence>" in turn and 'document="refund-en"' in turn and "contact-en" in turn


async def test_bogus_citations_are_dropped(svc, chat_model):
    chat_model.next_raw = json.dumps({"answer": "x", "can_answer": True, "sources": ["made-up-1", "refund-en-3"]})
    r = await svc.answer("When should I report a manufacturing defect?")
    assert [s["document_id"] for s in r.sources] == ["refund-en"]


async def test_smalltalk_makes_no_model_call(svc, chat_model):
    r = await svc.answer("hello")
    assert r.intent == "smalltalk" and chat_model.calls == []
    r = await svc.answer("مرحبا")
    assert r.language == "ar" and "رابت هول" in r.answer


async def test_product_question_is_deterministic(svc, chat_model, embedder):
    before = embedder.calls
    chat_model.next_raw = json.dumps({"answer": "The price is AED 99 and all sizes are in stock.", "can_answer": True, "sources": []})
    r = await svc.answer("Is size M in stock?")
    assert r.intent == "product" and r.products == []
    assert "can't confirm" in r.answer and "info@rabbithole.ae" in r.answer
    assert "AED 99" not in r.answer and not r.needs_human and not r.sources
    assert chat_model.calls == [] and embedder.calls == before


async def test_outage_is_not_sold_out(svc, chat_model):
    r = await svc.answer("The product API is unavailable. Is everything sold out?")
    assert "sold out" not in r.answer.lower() and "can't confirm" in r.answer
    assert chat_model.calls == []


async def test_order_question_needs_human(svc, chat_model):
    chat_model.next_raw = json.dumps({"answer": "Please email support.", "can_answer": True, "sources": []})
    r = await svc.answer("Where is my order?")
    assert r.intent == "order" and r.needs_human is True


async def test_can_answer_false_sets_needs_human(svc, chat_model):
    chat_model.next_raw = json.dumps({"answer": "I can't confirm that.", "can_answer": False, "sources": []})
    r = await svc.answer("How much is shipping to Egypt?")
    assert r.needs_human is True and r.sources == []


async def test_unparsable_model_output_falls_back_with_contact_email(svc, chat_model):
    chat_model.next_raw = "not json at all"
    r = await svc.answer("What does Rabbit Hole sell?")
    assert r.degraded and r.needs_human and "info@rabbithole.ae" in r.answer


async def test_model_exception_falls_back_arabic(svc, chat_model):
    chat_model.raise_on_generate = True
    r = await svc.answer("ما هي مهلة الإبلاغ عن عيب تصنيع؟")
    assert r.degraded and r.language == "ar" and "info@rabbithole.ae" in r.answer


async def test_conversation_id_is_server_issued_and_history_is_used(svc, chat_model, pool):
    r1 = await svc.answer("When should I report a manufacturing defect?", conversation_id="attacker-guess")
    assert r1.conversation_id != "attacker-guess"           # unknown client IDs are never adopted
    r2 = await svc.answer("and then how long until the replacement?", conversation_id=r1.conversation_id)
    assert r2.conversation_id == r1.conversation_id
    condense = [c for c in chat_model.calls if not c["json_mode"]]
    assert condense, "follow-up should be condensed into a standalone query"
    gen_msgs = [c for c in chat_model.calls if c["json_mode"]][-1]["messages"]
    assert not any(m["role"] == "assistant" for m in gen_msgs)
    assert any(m["role"] == "user" and m["content"] == "When should I report a manufacturing defect?" for m in gen_msgs)
    assert await pool.fetchval("SELECT count(*) FROM messages WHERE conversation_id=$1", r1.conversation_id) == 4


async def test_conversations_are_isolated(svc, chat_model):
    a = await svc.answer("When should I report a manufacturing defect?")
    b = await svc.answer("What does Rabbit Hole sell?")
    assert a.conversation_id != b.conversation_id
    gen_msgs = [c for c in chat_model.calls if c["json_mode"]][-1]["messages"]
    assert [m["role"] for m in gen_msgs] == ["system", "user"]   # b sees none of a's history


async def test_citation_urls_can_be_rewritten_to_final_domain(pool, embedder, chat_model, variant):
    s = variant(source_base_url="https://www.rabbithole.ae")
    svc = ChatService(pool, embedder, chat_model, s)
    await pool.execute("DELETE FROM chunks")
    await run_ingest(pool, embedder, s)
    r = await svc.answer("When should I report a manufacturing defect?")
    assert r.sources[0]["url"] == "https://www.rabbithole.ae/refund"


async def test_purge_removes_only_expired(svc, pool):
    r = await svc.answer("What does Rabbit Hole sell?")
    await pool.execute("UPDATE conversations SET created_at = now() - interval '40 days'")
    await pool.execute("UPDATE messages SET created_at = now() - interval '40 days'")
    assert await svc.purge_old_messages() >= 1
    assert await pool.fetchval("SELECT count(*) FROM conversations WHERE conversation_id=$1", r.conversation_id) == 0


def test_parse_model_json_variants():
    assert parse_model_json('{"answer":"a","can_answer":true,"sources":[]}')["answer"] == "a"
    assert parse_model_json('```json\n{"answer":"a"}\n```') is None
    assert parse_model_json("junk {\"answer\": \"a\"} trailing") is None
    assert parse_model_json("no braces") is None
    assert parse_model_json('{"answer": 5}') is None


@pytest.mark.parametrize("message,language", [
    ("What is the price?", "en"), ("I need XL", "en"), ("Is medium left?", "en"),
    ("كم سعر المقاس M؟", "ar"), ("هل المقاس متوفر؟", "ar"),
    ("Is size M available and do you ship to Egypt?", "en"),
])
async def test_disabled_catalogue_localized_without_models(svc, chat_model, embedder, message, language):
    first = await svc.answer("hello")
    before = embedder.calls
    r = await svc.answer(message, conversation_id=first.conversation_id)
    assert r.language == language and "info@rabbithole.ae" in r.answer
    assert ("can't confirm" if language == "en" else "لا أستطيع تأكيد") in r.answer
    assert not r.needs_human and not r.products and not r.sources
    assert chat_model.calls == [] and embedder.calls == before


async def test_condensed_query_cannot_change_original_order_route(svc, chat_model, monkeypatch):
    first = await svc.answer("hello")
    async def rewrite(*args):
        return "What does Rabbit Hole sell?"
    monkeypatch.setattr(svc, "_condense", rewrite)
    r = await svc.answer("Where is my order?", conversation_id=first.conversation_id)
    assert r.intent == "order" and r.needs_human
    assert "cannot see orders" in last_user_turn(chat_model)


@pytest.mark.parametrize("changes", [
    {"answer": "  "}, {"answer": 1}, {"can_answer": "false"}, {"can_answer": 0},
    {"sources": None}, {"sources": "refund-en-3"}, {"sources": [1]},
    {"sources": ["refund-en-3"] * 9}, {"can_answer": None},
])
async def test_invalid_model_schema_falls_back(svc, chat_model, changes):
    obj = {"answer": "x", "can_answer": True, "sources": ["refund-en-3"]}
    obj.update(changes)
    chat_model.next_raw = json.dumps(obj)
    r = await svc.answer("When should I report a manufacturing defect?")
    assert r.degraded and r.needs_human and "info@rabbithole.ae" in r.answer


@pytest.mark.parametrize("missing", ["answer", "can_answer", "sources"])
def test_model_schema_requires_all_fields(missing):
    obj = {"answer": "x", "can_answer": True, "sources": []}
    del obj[missing]
    assert parse_model_json(json.dumps(obj)) is None


async def test_retention_deletes_old_messages_in_active_conversation(svc, pool):
    r = await svc.answer("hello")
    await pool.execute("UPDATE messages SET created_at=now()-interval '40 days' WHERE conversation_id=$1", r.conversation_id)
    await svc._save(r.conversation_id, "recent user", "recent assistant")
    await svc.purge_old_messages()
    rows = await pool.fetch("SELECT content FROM messages WHERE conversation_id=$1 ORDER BY id", r.conversation_id)
    assert [row["content"] for row in rows] == ["recent user", "recent assistant"]
    assert await pool.fetchval("SELECT 1 FROM conversations WHERE conversation_id=$1", r.conversation_id)


async def test_history_ignores_expired_messages_before_purge(svc, pool):
    r = await svc.answer("hello")
    await pool.execute("UPDATE messages SET created_at=now()-interval '40 days' WHERE conversation_id=$1", r.conversation_id)
    await svc._save(r.conversation_id, "recent user", "recent assistant")
    history = await svc._history(r.conversation_id)
    assert [m["content"] for m in history] == ["recent user"]


async def test_purge_removes_empty_conversations(svc, pool):
    cid = await svc._resolve_conversation(None)
    await svc.purge_old_messages()
    assert not await pool.fetchval("SELECT 1 FROM conversations WHERE conversation_id=$1", cid)


@pytest.mark.parametrize("operation", ["_resolve_conversation", "_history", "_save"])
@pytest.mark.parametrize("message,language", [("What does Rabbit Hole sell?", "en"), ("ما هي مهلة الإبلاغ عن عيب تصنيع؟", "ar")])
async def test_storage_failures_use_cached_contact_fallback(svc, monkeypatch, operation, message, language):
    async def fail(*args, **kwargs):
        raise ConnectionError("database unavailable")
    monkeypatch.setattr(svc, operation, fail)
    r = await svc.answer(message)
    assert r.degraded and r.needs_human and r.language == language
    assert "info@rabbithole.ae" in r.answer and r.conversation_id


@pytest.mark.parametrize("message", ["hello", "Is size M in stock?"])
async def test_canned_reply_storage_failures_also_fall_back(svc, monkeypatch, message):
    async def fail(*args, **kwargs):
        raise ConnectionError("database unavailable")
    monkeypatch.setattr(svc, "_save", fail)
    r = await svc.answer(message)
    assert r.degraded and r.needs_human and "info@rabbithole.ae" in r.answer


async def test_retrieval_db_failure_does_not_query_db_for_fallback(svc):
    class BrokenPool:
        def acquire(self):
            raise ConnectionError("database unavailable")
    svc.pool = BrokenPool()
    from app.router import Intent
    direct = await svc._fallback("server-issued", "en", Intent.KNOWLEDGE)
    assert direct.degraded and "info@rabbithole.ae" in direct.answer
    r = await svc.answer("What does Rabbit Hole sell?")
    assert r.degraded and r.needs_human and "info@rabbithole.ae" in r.answer


async def test_stale_assistant_claims_never_reach_generation_or_condense(svc, chat_model):
    cid = await svc._resolve_conversation(None)
    stale = "The price is AED 99, Visa is accepted, and delivery is guaranteed tomorrow."
    await svc._save(cid, "When should I report a manufacturing defect?", stale)
    await svc.answer("What about the replacement?", conversation_id=cid)
    condense = [call for call in chat_model.calls if not call["json_mode"]]
    generation = [call for call in chat_model.calls if call["json_mode"]]
    assert condense and generation
    for call in chat_model.calls:
        assert stale not in "\n".join(m["content"] for m in call["messages"])
        assert not any(m["role"] == "assistant" for m in call["messages"])
    assert any(m["content"] == "When should I report a manufacturing defect?" for m in generation[-1]["messages"])


async def test_history_budget_counts_previous_visitor_turns(pool, embedder, chat_model, variant):
    svc = ChatService(pool, embedder, chat_model, variant(history_turns=2))
    cid = await svc._resolve_conversation(None)
    for index in range(4):
        await svc._save(cid, f"user {index}", f"assistant {index}")
    assert await svc._history(cid) == [
        {"role": "user", "content": "user 2"}, {"role": "user", "content": "user 3"},
    ]


async def test_enabled_catalogue_uses_original_message(svc, monkeypatch):
    from dataclasses import replace
    from app import catalogue
    svc.s = replace(svc.s, catalogue_enabled=True)
    first = await svc.answer("hello")
    calls = []
    async def rewrite(*args):
        return "unrelated condensed retrieval query"
    async def lookup(query, language, *, enabled, **kwargs):
        calls.append((query, language, enabled))
        return catalogue.CatalogueResult(catalogue.CatalogueStatus.UNAVAILABLE)
    monkeypatch.setattr(svc, "_condense", rewrite)
    monkeypatch.setattr(catalogue, "lookup", lookup)
    r = await svc.answer("Is size M in stock?", conversation_id=first.conversation_id)
    assert r.intent == "product" and calls == [("Is size M in stock?", "en", True)]


async def test_condensed_product_query_cannot_reroute_knowledge(svc, chat_model, monkeypatch):
    first = await svc.answer("hello")
    async def rewrite(*args):
        return "Is size M in stock?"
    monkeypatch.setattr(svc, "_condense", rewrite)
    r = await svc.answer("Tell me about the brand story.", conversation_id=first.conversation_id)
    assert r.intent == "knowledge"
    assert any(call["json_mode"] for call in chat_model.calls)


@pytest.mark.parametrize("message", ["Where is your physical shop?", "How long does delivery take?", "Can I have a refund?"])
@pytest.mark.parametrize("sources", [[], ["made-up-1"]])
async def test_factual_answer_without_valid_citation_falls_back(svc, chat_model, message, sources):
    chat_model.next_raw = json.dumps({"answer": "Unsupported promise.", "can_answer": True, "sources": sources})
    r = await svc.answer(message)
    assert r.degraded and r.needs_human and "Unsupported promise" not in r.answer


@pytest.mark.parametrize("message,language,expected", [
    ("What is your refund policy?", "en", "temporarily busy"),
    ("ما هي سياسة الاستبدال؟", "ar", "مشغولة مؤقتًا"),
])
async def test_provider_rate_limit_returns_temporary_busy_message(svc, monkeypatch, message, language, expected):
    import httpx
    from openai import RateLimitError
    async def limited(*args, **kwargs):
        response = httpx.Response(429, request=httpx.Request("POST", "https://example.com/v1/chat/completions"))
        raise RateLimitError("shared pool busy", response=response, body=None)
    monkeypatch.setattr(svc.llm, "complete", limited)
    result = await svc.answer(message, language)
    assert expected in result.answer
    assert "info@rabbithole.ae" in result.answer
    assert result.needs_human and result.degraded
    assert result.sources == []


async def test_catalogue_outage_never_uses_model_or_claims_stock(svc, chat_model, monkeypatch):
    from dataclasses import replace
    from app import catalogue
    svc.s = replace(svc.s, catalogue_enabled=True)
    async def down(*args, **kwargs):
        return catalogue.CatalogueResult(catalogue.CatalogueStatus.UNAVAILABLE)
    monkeypatch.setattr(catalogue, "lookup", down)
    result = await svc.answer("Show me your products")
    assert "can't confirm" in result.answer
    assert "sold out" not in result.answer.lower()
    assert not chat_model.calls and not result.products


async def test_live_products_are_returned_with_catalogue_citation(svc, chat_model, monkeypatch):
    from dataclasses import replace
    from app import catalogue
    svc.s = replace(svc.s, catalogue_enabled=True)
    products = [{"id": "41", "name": "Dubai Above Mars", "url": catalogue.STORE_BASE + "/collection", "price": 1365}]
    async def live(*args, **kwargs):
        return catalogue.CatalogueResult(catalogue.CatalogueStatus.OK, products)
    monkeypatch.setattr(catalogue, "lookup", live)
    chat_model.next_raw = json.dumps({"answer": "Here is the current design.", "can_answer": True, "sources": []})
    result = await svc.answer("Show me your products")
    assert result.products == products
    assert result.sources[-1]["document_id"] == "catalogue-en"
    assert not result.needs_human
    assert '1365' in last_user_turn(chat_model)


@pytest.mark.parametrize('followup,slug', [
    ('What sizes are available for the second product?', 'wonders-of-the-world'),
    ('ما المقاسات المتاحة للمنتج الثاني؟', 'wonders-of-the-world'),
    ('What about the third product?', 'glitched'),
])
async def test_product_followup_uses_saved_order_and_fresh_lookup(svc, chat_model, monkeypatch, pool, followup, slug):
    from dataclasses import replace
    from app import catalogue
    svc.s = replace(svc.s, catalogue_enabled=True)
    products = [{'slug': slug, 'name': name, 'url': catalogue.STORE_BASE + '/collection', 'price': 99, 'variants': [{'size': 'M', 'available': True}]} for slug, name in
                [('dubai-above-mars', 'Dubai Above Mars'), ('wonders-of-the-world', 'Wonders of the World'), ('glitched', 'Glitched')]]
    calls = []
    async def live(query, language, **kwargs):
        calls.append(query)
        if len(calls) == 1:
            return catalogue.CatalogueResult(catalogue.CatalogueStatus.OK, products)
        selected = next(p for p in products if p['slug'] == slug)
        return catalogue.CatalogueResult(catalogue.CatalogueStatus.OK, [{**selected, 'price': 210, 'variants': [{'size': 'M', 'available': False}]}])
    monkeypatch.setattr(catalogue, 'lookup', live)
    chat_model.next_raw = json.dumps({'answer': 'Current products.', 'can_answer': True, 'sources': []})
    first = await svc.answer('Show me your products')
    references = await svc._product_context(first.conversation_id)
    assert set(references[0][1]) == {'name', 'slug'}
    assert 'price' not in json.dumps(references) and 'stock' not in json.dumps(references)
    # A fresh service instance must keep the same context; no process-local memory.
    resumed = ChatService(pool, svc.embedder, svc.llm, svc.s)
    result = await resumed.answer(followup, conversation_id=first.conversation_id)
    assert calls[-1] == followup + '\nProduct: ' + slug
    assert len(result.products) == 1 and result.products[0]['slug'] == slug
    assert result.products[0]['variants'][0]['available'] is False
    assert '"stock":' not in last_user_turn(chat_model)
    assert '"available": false' in last_user_turn(chat_model)
    assert not result.degraded


async def test_product_reference_context_is_isolated_and_expires(svc, pool):
    first = await svc._resolve_conversation(None)
    second = await svc._resolve_conversation(None)
    await svc._save(first, 'browse', 'products', products=[{'slug': 'glitched', 'name': 'Glitched', 'price': 100}])
    assert await svc._product_context(second) == []
    await pool.execute("UPDATE messages SET created_at=now()-interval '40 days' WHERE conversation_id=$1", first)
    assert await svc._product_context(first) == []


async def test_ambiguous_followup_asks_instead_of_guessing(svc, chat_model, monkeypatch):
    from dataclasses import replace
    from app import catalogue
    svc.s = replace(svc.s, catalogue_enabled=True)
    cid = await svc._resolve_conversation(None)
    await svc._save(cid, 'browse', 'products', products=[{'slug': 'a', 'name': 'A'}, {'slug': 'b', 'name': 'B'}])
    async def unexpected(*args, **kwargs):
        pytest.fail('Ambiguous reference must not fetch or guess a product')
    monkeypatch.setattr(catalogue, 'lookup', unexpected)
    result = await svc.answer('What sizes are available?', conversation_id=cid)
    assert 'Which product' in result.answer and not result.products and not chat_model.calls


async def test_size_followup_answers_from_live_variants_without_model_confusion(svc, chat_model, monkeypatch):
    from dataclasses import replace
    from app import catalogue
    svc.s = replace(svc.s, catalogue_enabled=True, retrieval_mode='keyword')
    cid=await svc._resolve_conversation(None)
    await svc._save(cid,'browse','products',products=[{'slug':'dubai','name':'Dubai'},{'slug':'wonders','name':'Wonders'}])
    async def live(query, language, **kwargs):
        assert query.endswith('Product: wonders')
        return catalogue.CatalogueResult(catalogue.CatalogueStatus.OK,[{'slug':'wonders','name':'Wonders','url':catalogue.STORE_BASE+'/collection','colors':[{'id':'blue','label':'Blue'}],'variants':[{'colorId':'blue','size':'M','available':False}]}])
    monkeypatch.setattr(catalogue,'lookup',live)
    result=await svc.answer('What sizes are available for the second product?',conversation_id=cid)
    assert 'Wonders' in result.answer and 'No sizes are currently available' in result.answer
    assert not result.needs_human and result.sources[0]['document_id']=='catalogue-en'
    assert not [c for c in chat_model.calls if c['json_mode']]
