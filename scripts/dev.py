"""Explicit offline entry point: python -m scripts.dev (never uses OpenAI)."""
from dataclasses import replace

import uvicorn

from app.config import Settings
from app.main import create_app
from scripts.fakes import FakeChat, FakeEmbedder


def build_app():
    s = Settings.from_env()
    if s.environment.strip().lower() != "development":
        raise RuntimeError("Fake providers are development-only")
    s = replace(s, catalogue_enabled=False)
    return create_app(s, FakeEmbedder(s.embed_dimensions), FakeChat())


if __name__ == "__main__":
    uvicorn.run(build_app(), host="0.0.0.0", port=8000)
