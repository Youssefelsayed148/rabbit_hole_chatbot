import contextlib

import pytest
from starlette.testclient import TestClient

from app.main import create_app
from app.config import Settings

ORIGIN = "https://shop.example"


def test_staging_checker_against_production_app(make_client):
    from scripts.check_staging import check
    c = make_client(environment="production", site_keys=["public"], allowed_origins=[ORIGIN], admin_token="secret")
    check(c, ORIGIN, "https://denied.example", "public")


@pytest.fixture
def make_client(variant, embedder, chat_model):
    stack = contextlib.ExitStack()

    def make(**overrides):
        s = variant(auto_ingest=True, **overrides)
        return stack.enter_context(TestClient(create_app(s, embedder, chat_model)))

    yield make
    stack.close()


def test_health_and_chat_shape(make_client):
    c = make_client()
    h = c.get("/health").json()
    assert h["status"] == "ok" and h["chunks"] >= 42
    r = c.post("/chat", json={"message": "When should I report a manufacturing defect?"})
    assert r.status_code == 200
    body = r.json()
    assert set(body) == {"answer", "sources", "products", "needs_human", "conversation_id", "language"}
    assert body["sources"][0]["document_id"] == "refund-en"
    assert body["language"] == "en" and body["products"] == [] and body["needs_human"] is False


def test_arabic_language_detected(make_client):
    r = make_client().post("/chat", json={"message": "ما هي مهلة الإبلاغ عن عيب تصنيع؟"}).json()
    assert r["language"] == "ar" and r["sources"][0]["document_id"] == "refund-ar"


def test_development_health_identifies_injected_providers(make_client):
    health = make_client().get("/health").json()
    assert health["providers"] == {"embedder": "FakeEmbedder", "chat": "FakeChat", "model": None}


def test_production_health_omits_provider_details(make_client):
    c = make_client(environment="production", site_keys=["public"], allowed_origins=[ORIGIN], admin_token="secret")
    assert "providers" not in c.get("/health").json()


@pytest.mark.parametrize("payload", [{}, {"message": ""}, {"message": "   "}, {"message": "hi", "language": "fr"},
                                      {"message": "hi", "conversation_id": "bad id!"}])
def test_validation_errors(make_client, payload):
    assert make_client().post("/chat", json=payload).status_code == 422


def test_message_too_long(make_client):
    c = make_client(max_message_chars=50)
    assert c.post("/chat", json={"message": "x" * 51}).status_code == 413


def test_site_key_enforced(make_client):
    c = make_client(site_keys=["pk_live_abc"])
    body = {"message": "What does Rabbit Hole sell?"}
    assert c.post("/chat", json=body).status_code == 401
    assert c.post("/chat", json=body, headers={"X-Site-Key": "wrong"}).status_code == 401
    assert c.post("/chat", json=body, headers={"X-Site-Key": "pk_live_abc"}).status_code == 200


def test_origin_allowlist_and_cors(make_client):
    c = make_client(allowed_origins=[ORIGIN])
    body = {"message": "What does Rabbit Hole sell?"}
    assert c.post("/chat", json=body, headers={"Origin": "https://evil.example"}).status_code == 403
    ok = c.post("/chat", json=body, headers={"Origin": ORIGIN})
    assert ok.status_code == 200 and ok.headers["access-control-allow-origin"] == ORIGIN
    pre = c.options("/chat", headers={"Origin": ORIGIN, "Access-Control-Request-Method": "POST",
                                      "Access-Control-Request-Headers": "content-type,x-site-key"})
    assert pre.status_code == 200 and pre.headers["access-control-allow-origin"] == ORIGIN
    evil = c.options("/chat", headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "POST"})
    assert "access-control-allow-origin" not in evil.headers


def test_empty_allowlist_denies_browser_origins(make_client):
    c = make_client()
    assert c.post("/chat", json={"message": "hello"}, headers={"Origin": ORIGIN}).status_code == 403


@pytest.mark.parametrize("origin", [
    "https://example.com.evil.com", "https://evil-example.com", "https://sub.example.com",
    "https://www.example.com", "http://example.com", "https://example.com:443",
    "https://example.com/", "https://EXAMPLE.com", "https://example.com@evil.com", "null",
])
def test_production_origin_matching_is_exact(make_client, origin):
    allowed = "https://example.com"
    c = make_client(environment="production", allowed_origins=[allowed], site_keys=["public"], admin_token="secret")
    headers = {"Origin": origin, "X-Site-Key": "public"}
    denied = c.post("/chat", json={"message": "hello"}, headers=headers)
    assert denied.status_code == 403 and "access-control-allow-origin" not in denied.headers
    preflight = c.options("/chat", headers={"Origin": origin, "Access-Control-Request-Method": "POST",
                                           "Access-Control-Request-Headers": "content-type,x-site-key"})
    assert preflight.status_code == 400 and "access-control-allow-origin" not in preflight.headers
    assert c.post("/chat", json={"message": "hello"}, headers={"Origin": allowed, "X-Site-Key": "public"}).status_code == 200


def test_wildcard_origin_config_is_rejected_in_production(make_client):
    with pytest.raises(ValueError, match="ALLOWED_ORIGINS"):
        make_client(environment="production", allowed_origins=["*"], site_keys=["public"], admin_token="secret")


def test_domain_wildcard_is_literal_not_suffix_matching(make_client):
    c = make_client(environment="production", allowed_origins=["https://*.example.com"], site_keys=["public"], admin_token="secret")
    origin = "https://sub.example.com"
    assert c.post("/chat", json={"message": "hello"}, headers={"Origin": origin, "X-Site-Key": "public"}).status_code == 403
    preflight = c.options("/chat", headers={"Origin": origin, "Access-Control-Request-Method": "POST"})
    assert preflight.status_code == 400


def test_widget_static_and_dev_demo(make_client):
    c = make_client()
    js = c.get("/widget.js")
    assert js.status_code == 200 and "validResponse" in js.text
    assert js.headers["content-type"].startswith("application/javascript")
    assert js.headers["cache-control"] == "public, max-age=3600, must-revalidate"
    assert js.headers["x-content-type-options"] == "nosniff"
    demo = c.get("/demo.html")
    assert demo.status_code == 200 and demo.headers["cache-control"] == "no-store"
    c = make_client(environment="production", site_keys=["public"], allowed_origins=[ORIGIN], admin_token="secret")
    assert c.get("/demo.html").status_code == 404
    assert c.get("/widget.js").status_code == 200


def test_rate_limit(make_client):
    c = make_client(rate_limit_per_min=3)
    codes = [c.post("/chat", json={"message": "hello"}).status_code for _ in range(5)]
    assert codes == [200, 200, 200, 429, 429]


def test_daily_cap(make_client):
    c = make_client(daily_llm_call_cap=2)
    codes = [c.post("/chat", json={"message": "hello"}).status_code for _ in range(3)]
    assert codes == [200, 200, 429]


def test_admin_requires_token(make_client):
    assert make_client().post("/admin/ingest").status_code == 503          # no ADMIN_TOKEN configured
    c = make_client(admin_token="s3cret")
    assert c.post("/admin/ingest").status_code == 401
    assert c.post("/admin/ingest", headers={"Authorization": "Bearer nope"}).status_code == 401
    r = c.post("/admin/ingest", headers={"Authorization": "Bearer s3cret"})
    assert r.status_code == 200 and r.json()["unchanged"] >= 42
    assert c.post("/admin/purge", headers={"Authorization": "Bearer s3cret"}).status_code == 200


def test_openapi_and_docs_not_exposed(make_client):
    c = make_client()
    assert c.get("/openapi.json").status_code == 404 and c.get("/docs").status_code == 404


@pytest.mark.parametrize("field,missing", [
    ("site_keys", "SITE_KEYS"), ("allowed_origins", "ALLOWED_ORIGINS"), ("admin_token", "ADMIN_TOKEN"),
])
def test_production_startup_requires_access_settings(make_client, field, missing):
    values = dict(environment="production", site_keys=["public"], allowed_origins=[ORIGIN], admin_token="secret")
    values[field] = "" if field == "admin_token" else []
    with pytest.raises(ValueError, match=missing):
        make_client(**values)


def test_production_startup_with_required_settings(make_client):
    c = make_client(environment="production", site_keys=["public"], allowed_origins=[ORIGIN], admin_token="secret")
    assert c.get("/health").status_code == 200


def test_env_production_is_read_and_validated(monkeypatch):
    monkeypatch.setenv("ENV", "production")
    for name in ("SITE_KEYS", "ALLOWED_ORIGINS", "ADMIN_TOKEN"):
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(ValueError, match="SITE_KEYS, ALLOWED_ORIGINS, ADMIN_TOKEN"):
        Settings.from_env().validate_startup()


def test_startup_caches_contact_and_db_outage_returns_200(make_client, monkeypatch):
    c = make_client()
    service = c.app.state.service
    assert service.contact_emails == {"en": "info@rabbithole.ae", "ar": "info@rabbithole.ae"}
    async def fail(*args, **kwargs):
        raise ConnectionError("database unavailable")
    monkeypatch.setattr(service, "_resolve_conversation", fail)
    r = c.post("/chat", json={"message": "What does Rabbit Hole sell?", "conversation_id": "unknown-client-id"})
    assert r.status_code == 200
    body = r.json()
    assert body["needs_human"] and "info@rabbithole.ae" in body["answer"]
    assert body["conversation_id"] != "unknown-client-id"

async def test_startup_refreshes_nonempty_index_without_reembedding(pool, settings, embedder, chat_model):
    from dataclasses import replace
    from app.ingest import run_ingest

    await run_ingest(pool, embedder, settings)
    # Simulate an approved source record removed since the last deployment.
    await pool.execute("""
        INSERT INTO chunks (chunk_id, document_id, language, text, content_hash,
                            verification_status, embedding)
        SELECT 'obsolete-startup-chunk', document_id, language, text, content_hash,
               verification_status, embedding FROM chunks LIMIT 1
    """)
    calls = embedder.calls
    s = replace(settings, auto_ingest=True)
    for _ in range(2):
        with TestClient(create_app(s, embedder, chat_model)) as client:
            assert client.get('/health').json()['status'] == 'ok'
        assert not await pool.fetchval("SELECT 1 FROM chunks WHERE chunk_id='obsolete-startup-chunk'")
        assert embedder.calls == calls
