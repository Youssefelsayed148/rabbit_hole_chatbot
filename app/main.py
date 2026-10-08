"""FastAPI service: POST /chat, GET /health, POST /admin/ingest, POST /admin/purge."""
from __future__ import annotations

import logging
from pathlib import Path
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field, field_validator

from .config import Settings, get_settings
from .db import create_pool, init_schema
from .ingest import run_ingest
from .pipeline import ChatService
from .providers import ChatModel, Embedder, OpenAIChat, OpenAIEmbedder
from .security import DailyCap, RateLimiter, check_admin, check_public_access, client_ip

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("rag.api")


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    language: Literal["en", "ar"] | None = None
    conversation_id: str | None = Field(default=None, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")

    @field_validator("message")
    @classmethod
    def _strip(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("message must not be empty")
        return v


class Source(BaseModel):
    title: str
    url: str
    document_id: str


class ChatResponse(BaseModel):
    answer: str
    sources: list[Source]
    products: list[dict]
    needs_human: bool
    conversation_id: str
    language: str


def create_app(
    settings: Settings | None = None,
    embedder: Embedder | None = None,
    llm: ChatModel | None = None,
) -> FastAPI:
    s = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        s.validate_startup()
        emb = embedder or OpenAIEmbedder(s)   # raises a clear error if OPENAI_API_KEY is missing
        chat = llm or OpenAIChat(s)
        log.info("providers embedder=%s chat=%s model=%s", type(emb).__name__, type(chat).__name__, s.chat_model)
        await init_schema(s.database_url, s.embed_dimensions)
        pool = await create_pool(s.database_url)
        try:
            service = ChatService(pool, emb, chat, s)
            app.state.pool, app.state.service, app.state.embedder = pool, service, emb
            app.state.limiter = RateLimiter(s.rate_limit_per_min)
            app.state.daily = DailyCap(s.daily_llm_call_cap)
            if s.auto_ingest:
                log.info("refreshing approved index (hash-diff ingest)")
                await run_ingest(pool, emb, s)
            await service.cache_contact_emails()
            await service.purge_old_messages()
            yield
        finally:
            await pool.close()

    app = FastAPI(title="Rabbit Hole assistant", version="0.1.0", lifespan=lifespan,
                  docs_url=None, redoc_url=None, openapi_url=None)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=s.allowed_origins,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "X-Site-Key"],
        max_age=600,
    )

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception):
        log.exception("unhandled error")
        return JSONResponse({"detail": "Internal error"}, status_code=500)

    @app.get("/health")
    async def health(request: Request):
        n = await request.app.state.pool.fetchval("SELECT count(*) FROM chunks")
        result = {"status": "ok" if n else "empty_index", "chunks": n}
        if s.environment.strip().lower() == "development":
            service = request.app.state.service
            result["providers"] = {
                "embedder": type(service.embedder).__name__,
                "chat": type(service.llm).__name__,
                "model": s.chat_model if isinstance(service.llm, OpenAIChat) else None,
            }
        return result

    assets = Path(__file__).resolve().parent.parent

    @app.get("/widget.js", include_in_schema=False)
    async def widget():
        return FileResponse(assets / "widget.js", media_type="application/javascript",
                            headers={"Cache-Control": "public, max-age=3600, must-revalidate",
                                     "X-Content-Type-Options": "nosniff"})

    if s.environment.strip().lower() == "development":
        @app.get("/demo.html", include_in_schema=False)
        async def demo():
            return FileResponse(assets / "demo.html", media_type="text/html",
                                headers={"Cache-Control": "no-store"})

    @app.post("/chat", response_model=ChatResponse)
    async def chat(req: ChatRequest, request: Request):
        check_public_access(request, s)
        if len(req.message) > s.max_message_chars:
            raise HTTPException(413, f"Message too long (max {s.max_message_chars} characters)")
        if not request.app.state.limiter.check(client_ip(request, s.trust_proxy)):
            raise HTTPException(429, "Too many requests, please slow down")
        if not request.app.state.daily.take():
            raise HTTPException(429, "Daily capacity reached, please try again later")
        result = await request.app.state.service.answer(req.message, req.language, req.conversation_id)
        return ChatResponse(
            answer=result.answer, sources=result.sources, products=result.products,
            needs_human=result.needs_human, conversation_id=result.conversation_id, language=result.language,
        )

    @app.post("/admin/ingest")
    async def admin_ingest(request: Request):
        check_admin(request, s)
        return await run_ingest(request.app.state.pool, request.app.state.embedder, s)

    @app.post("/admin/purge")
    async def admin_purge(request: Request):
        check_admin(request, s)
        return {"conversations_deleted": await request.app.state.service.purge_old_messages()}

    return app


# `uvicorn app.main:app`. create_app only reads env; the OpenAI key is required at startup (lifespan).
app = create_app()
