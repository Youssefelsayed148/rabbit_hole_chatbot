"""OpenAI-backed embedder and chat model, behind small interfaces so tests can swap fakes in."""
from __future__ import annotations

import os
import logging
from typing import Protocol
from urllib.parse import urlsplit

from openai import AsyncOpenAI

from .config import Settings

log = logging.getLogger("rag.providers")


class Embedder(Protocol):
    async def embed(self, texts: list[str]) -> list[list[float]]: ...


class ChatModel(Protocol):
    async def complete(self, messages: list[dict], *, json_mode: bool = False, max_tokens: int = 700) -> str: ...


def _client(s: Settings, *, chat: bool = False) -> AsyncOpenAI:
    if chat and s.chat_base_url and not s.chat_api_key:
        raise RuntimeError("CHAT_API_KEY is required when CHAT_BASE_URL is set")
    api_key = (s.chat_api_key if chat else "") or s.openai_api_key
    base_url = (s.chat_base_url if chat else "") or s.openai_base_url
    if not api_key:
        raise RuntimeError("CHAT_API_KEY is not set" if chat and s.chat_base_url else "OPENAI_API_KEY is not set")
    options = {}
    if path := os.environ.get('OPENAI_USAGE_LOG'):
        from .usage import usage_http_client
        options['http_client'] = usage_http_client(path)
    return AsyncOpenAI(**options, api_key=api_key, timeout=s.openai_timeout, max_retries=s.openai_max_retries,
                       base_url=base_url or "https://api.openai.com/v1")


class KeywordOnlyEmbedder:
    """No model is loaded; any accidental embedding request must fail loudly."""
    async def embed(self, texts: list[str]) -> list[list[float]]:
        raise RuntimeError("Embedding calls are disabled in keyword retrieval mode")


def build_embedder(s: Settings) -> Embedder:
    return KeywordOnlyEmbedder() if s.retrieval_mode == "keyword" else OpenAIEmbedder(s)


class OpenAIEmbedder:
    BATCH = 96

    def __init__(self, s: Settings):
        self.s = s
        self.client = _client(s)

    async def embed(self, texts: list[str]) -> list[list[float]]:
        out: list[list[float]] = []
        for i in range(0, len(texts), self.BATCH):
            batch = [t if t.strip() else " " for t in texts[i : i + self.BATCH]]
            kwargs: dict = {"model": self.s.embed_model, "input": batch}
            if self.s.embed_model.startswith("text-embedding-3"):
                kwargs["dimensions"] = self.s.embed_dimensions
            resp = await self.client.embeddings.create(**kwargs)
            out.extend(d.embedding for d in sorted(resp.data, key=lambda d: d.index))
        return out


def s_base(s: Settings) -> str:
    return s.chat_base_url or s.openai_base_url


class OpenAIChat:
    def __init__(self, s: Settings):
        self.s = s
        self.models = list(dict.fromkeys([s.chat_model, *s.chat_fallback_models]))
        if s.chat_free_only or s.chat_fallback_models:
            endpoint = urlsplit(s_base(s))
            if endpoint.scheme != "https" or endpoint.hostname != "openrouter.ai":
                raise ValueError("CHAT_FREE_ONLY and CHAT_FALLBACK_MODELS require the HTTPS OpenRouter endpoint")
        if s.chat_free_only:
            if any(m != "openrouter/free" and not m.endswith(":free") for m in self.models):
                raise ValueError("CHAT_FREE_ONLY requires free model IDs (:free or openrouter/free)")
        self.client = _client(s, chat=True)

    async def complete(self, messages: list[dict], *, json_mode: bool = False, max_tokens: int = 700) -> str:
        kwargs: dict = {
            "model": self.s.chat_model,
            "messages": messages,
        }
        # Non-OpenAI compatible endpoints universally accept max_tokens; OpenAI proper uses max_completion_tokens.
        kwargs["max_tokens" if s_base(self.s) else "max_completion_tokens"] = max_tokens
        if self.s.temperature is not None:
            kwargs["temperature"] = self.s.temperature
        if json_mode and self.s.chat_json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        extra = {}
        if self.s.chat_fallback_models:
            extra["models"] = self.models
        if self.s.chat_free_only:
            extra["provider"] = {"max_price": {"prompt": 0, "completion": 0, "request": 0}}
            # Short evidence-grounded replies should reserve their token budget for the answer.
            extra["reasoning"] = {"enabled": False}
        if extra:
            kwargs["extra_body"] = extra
        resp = await self.client.chat.completions.create(**kwargs)
        log.info("chat completion requested=%s served=%s", self.s.chat_model, resp.model)
        return resp.choices[0].message.content or ""

