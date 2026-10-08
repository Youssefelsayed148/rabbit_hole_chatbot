"""Offline test harness: real PostgreSQL + pgvector, fake embedder and fake chat model (no OpenAI calls).

Set TEST_DATABASE_URL to a database where the `vector` extension can be created. The tests DROP and
recreate the chunks/messages tables in that database, so point it at a throwaway DB.
"""
from __future__ import annotations

import os
from dataclasses import replace

import asyncpg
import pytest
import pytest_asyncio

from app.config import Settings
from app.db import create_pool, init_schema
from scripts.fakes import FakeChat, FakeEmbedder

TEST_DSN = os.environ.get("TEST_DATABASE_URL", "postgresql://rh:rh@localhost:5432/rh_test")
DIMS = 1024


@pytest.fixture(scope="session")
def settings() -> Settings:
    return Settings(database_url=TEST_DSN, openai_api_key="test", embed_dimensions=DIMS, auto_ingest=False)


@pytest_asyncio.fixture(scope="session", autouse=True)
async def pool(settings):
    conn = await asyncpg.connect(TEST_DSN)
    await conn.execute("DROP TABLE IF EXISTS messages, conversations, chunks CASCADE")
    await conn.close()
    await init_schema(TEST_DSN, DIMS)
    p = await create_pool(TEST_DSN)
    yield p
    await p.close()


@pytest.fixture
def embedder() -> FakeEmbedder:
    return FakeEmbedder()


@pytest.fixture
def chat_model() -> FakeChat:
    return FakeChat()


@pytest.fixture
def variant(settings):
    """Helper: settings with overrides."""
    return lambda **kw: replace(settings, **kw)
