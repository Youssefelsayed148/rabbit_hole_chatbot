"""OpenAI-backed embedder and chat model, behind small interfaces so tests can swap fakes in."""
from __future__ import annotations

import os
import logging
from typing import Protocol
from urllib.parse import urlsplit

from openai import APIError, AsyncOpenAI, BadRequestError, UnprocessableEntityError

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
        if s.chat_reasoning_effort and s.chat_reasoning_effort not in {"minimal", "low", "medium", "high"}:
            raise ValueError("CHAT_REASONING_EFFORT must be one of minimal, low, medium, high (or empty)")
        self.client = _client(s, chat=True)
        self.paid_client = None
        if s.chat_paid_fallback_model:
            if not s.chat_base_url:
                raise ValueError("CHAT_PAID_FALLBACK_MODEL needs a separate primary chat endpoint (CHAT_BASE_URL)")
            if not s.openai_api_key:
                raise RuntimeError("CHAT_PAID_FALLBACK_MODEL needs OPENAI_API_KEY (used directly against OpenAI)")
            self.paid_client = _client(s)  # OpenAI key and base URL, never the chat endpoint's key

    async def complete(self, messages: list[dict], *, json_mode: bool = False, max_tokens: int = 700) -> str:
        try:
            return await self._complete_primary(messages, json_mode=json_mode, max_tokens=max_tokens)
        except (BadRequestError, UnprocessableEntityError):
            raise  # the request itself is wrong; another model would reject it too
        except APIError as exc:
            if self.paid_client is None:
                raise
            log.warning("primary chat failed (%s); retrying on OpenAI model %s", type(exc).__name__, self.s.chat_paid_fallback_model)
            return await self._complete_paid(messages, json_mode=json_mode, max_tokens=max_tokens)

    async def _complete_paid(self, messages: list[dict], *, json_mode: bool, max_tokens: int) -> str:
        kwargs: dict = {"model": self.s.chat_paid_fallback_model, "messages": messages, "max_completion_tokens": max_tokens}
        if self.s.temperature is not None:
            kwargs["temperature"] = self.s.temperature
        if json_mode and self.s.chat_json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        resp = await self.paid_client.chat.completions.create(**kwargs)
        log.info("chat completion requested=%s served=%s via=openai-direct", kwargs["model"], resp.model)
        return resp.choices[0].message.content or ""

    async def _complete_primary(self, messages: list[dict], *, json_mode: bool = False, max_tokens: int = 700) -> str:
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
        elif self.s.chat_reasoning_effort:
            # Paid reasoning fallbacks (e.g. gpt-5-nano) can spend the whole token budget thinking; cap it.
            extra["reasoning"] = {"effort": self.s.chat_reasoning_effort}
        if extra:
            kwargs["extra_body"] = extra
        resp = await self.client.chat.completions.create(**kwargs)
        log.info("chat completion requested=%s served=%s", self.s.chat_model, resp.model)
        return resp.choices[0].message.content or ""

