"""The chat pipeline: route -> (condense) -> retrieve -> live-data note -> grounded generation -> cited result."""
from __future__ import annotations

import logging
import json
import re
import secrets
import time
from dataclasses import dataclass, field
from urllib.parse import urlsplit, urlunsplit

import asyncpg
from openai import RateLimitError
from pydantic import BaseModel, Field, StrictBool, StrictStr, ValidationError, field_validator

from . import catalogue
from .config import Settings
from .prompts import CONDENSE_PROMPT, SYSTEM_PROMPT, build_user_turn
from .providers import ChatModel, Embedder
from .retrieval import fetch_documents, retrieve
from .router import SMALLTALK_REPLY, Intent, detect_language, route

log = logging.getLogger("rag.chat")

INTENT_NOTES = {
    Intent.KNOWLEDGE: "",
    Intent.PRODUCT_LIVE: "The visitor is asking about price, stock, sizes, colours or product availability. "
                         "These come only from <live_data>. Evidence documents never answer them.",
    Intent.SHIPPING: "The visitor is asking about shipping or delivery. State only shipping facts that appear in the "
                     "evidence. Fees, destinations and delivery times are NOT confirmed unless the evidence states them. "
                     "Do not confuse replacement dispatch time with delivery time.",
    Intent.ORDER_ACCOUNT: "The visitor asks about a specific order or their account. You cannot see orders or accounts. "
                          "Do not answer from policy text as if it described their order. Set can_answer to false and "
                          "tell them to email support with their order details.",
}

FALLBACK_TEXT = {
    "en": "I can't answer that right now. Please contact our team{email} and they will help you.",
    "ar": "لا أستطيع الإجابة الآن. يرجى التواصل مع فريقنا{email} وسيساعدونك.",
}

MODEL_BUSY_TEXT = {
    "en": "Our chat service is temporarily busy. Please try again shortly, or contact our team{email}.",
    "ar": "خدمة المحادثة مشغولة مؤقتًا. يرجى المحاولة مرة أخرى بعد قليل، أو التواصل مع فريقنا{email}.",
}

CATALOGUE_UNCONFIRMED = {
    "en": "I can't confirm product prices, stock, sizes or availability here. Please check the website or contact our team{email}.",
    "ar": "لا أستطيع تأكيد أسعار المنتجات أو المخزون أو المقاسات أو التوفر هنا. يرجى مراجعة الموقع أو التواصل مع فريقنا{email}.",
}


class ModelReply(BaseModel):
    answer: StrictStr
    can_answer: StrictBool
    sources: list[StrictStr] = Field(max_length=8)

    @field_validator("answer")
    @classmethod
    def nonempty_answer(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("empty answer")
        return value.strip()


@dataclass
class ChatResult:
    answer: str
    conversation_id: str
    language: str
    intent: str
    sources: list[dict] = field(default_factory=list)
    products: list[dict] = field(default_factory=list)
    needs_human: bool = False
    degraded: bool = False


def parse_model_json(raw: str) -> dict | None:
    try:
        return ModelReply.model_validate_json(raw, strict=True).model_dump()
    except ValidationError:
        return None


def _public_url(url: str, base: str) -> str:
    """Optionally re-point citation URLs at the final production domain."""
    if not base or not url:
        return url
    b, u = urlsplit(base), urlsplit(url)
    return urlunsplit((b.scheme or u.scheme, b.netloc or u.netloc, u.path, u.query, u.fragment))


class ChatService:
    def __init__(self, pool: asyncpg.Pool, embedder: Embedder, llm: ChatModel, settings: Settings):
        self.pool, self.embedder, self.llm, self.s = pool, embedder, llm, settings
        self.contact_emails: dict[str, str] = {}

    # ---- conversation storage -------------------------------------------------
    async def _resolve_conversation(self, cid: str | None) -> str:
        """Server-issued random IDs only: an unknown client-supplied ID is replaced, never adopted."""
        async with self.pool.acquire() as conn:
            if cid and await conn.fetchval("SELECT 1 FROM conversations WHERE conversation_id=$1", cid):
                return cid
            new = secrets.token_urlsafe(16)
            await conn.execute("INSERT INTO conversations (conversation_id) VALUES ($1)", new)
            return new

    async def _history(self, cid: str) -> list[dict]:
        if not self.s.store_messages:
            return []
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT role, content FROM messages WHERE conversation_id=$1 AND role='user' "
                "AND created_at >= now() - ($3::int * interval '1 day') ORDER BY id DESC LIMIT $2",
                cid, self.s.history_turns, self.s.message_retention_days,
            )
        return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]

    async def _save(self, cid: str, user: str, assistant: str, *, products: list[dict] | None = None) -> None:
        if not self.s.store_messages:
            return
        async with self.pool.acquire() as conn:
            await conn.executemany(
                "INSERT INTO messages (conversation_id, role, content, product_references) VALUES ($1,$2,$3,$4::jsonb)",
                [(cid, "user", user, "[]"), (cid, "assistant", assistant, json.dumps([
                    {"slug": p["slug"], "name": p["name"]} for p in (products or []) if p.get("slug") and p.get("name")
                ]))],
            )

    async def _product_context(self, cid: str) -> list[list[dict]]:
        if not self.s.store_messages:
            return []
        rows = await self.pool.fetch(
            "SELECT product_references FROM messages WHERE conversation_id=$1 AND role='assistant' "
            "AND product_references <> '[]'::jsonb AND created_at >= now() - ($2::int * interval '1 day') "
            "ORDER BY id DESC LIMIT $3", cid, self.s.message_retention_days, self.s.history_turns,
        )
        return [json.loads(row['product_references']) for row in rows]

    async def purge_old_messages(self) -> int:
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    "DELETE FROM messages WHERE created_at < now() - ($1::int * interval '1 day')",
                    self.s.message_retention_days,
                )
                res = await conn.execute(
                    "DELETE FROM conversations WHERE NOT EXISTS "
                    "(SELECT 1 FROM messages m WHERE m.conversation_id = conversations.conversation_id)",
                )
        return int(res.split()[-1])

    # ---- helpers ----------------------------------------------------------------
    async def _condense(self, message: str, history: list[dict]) -> str:
        if not history:
            return message
        convo = "\n".join(f"{m['role']}: {m['content']}" for m in history)
        try:
            out = await self.llm.complete(
                [{"role": "system", "content": CONDENSE_PROMPT},
                 {"role": "user", "content": f"Conversation:\n{convo}\n\nLast visitor message: {message}"}],
                max_tokens=80,
            )
            return out.strip().strip('"') or message
        except Exception:
            log.exception("condense failed; using raw message")
            return message

    async def cache_contact_emails(self) -> None:
        emails = {}
        for language in ("en", "ar"):
            chunks = await fetch_documents(self.pool, [f"contact-{language}"], self.s.allowed_statuses)
            for c in chunks:
                match = re.search(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+", c.text)
                if match:
                    emails[language] = match.group(0)
                    break
        self.contact_emails = emails

    def _email_suffix(self, language: str) -> str:
        email = self.contact_emails.get(language)
        return {"en": f" at {email}", "ar": f" عبر {email}"}[language] if email else ""

    async def _fallback(self, cid: str, language: str, intent: Intent, *, busy: bool = False) -> ChatResult:
        return ChatResult(
            answer=(MODEL_BUSY_TEXT if busy else FALLBACK_TEXT)[language].format(email=self._email_suffix(language)), conversation_id=cid, language=language,
            intent=intent.label, needs_human=True, degraded=True,
        )

    # ---- main entry --------------------------------------------------------------
    async def answer(self, message: str, language_hint: str | None = None, conversation_id: str | None = None) -> ChatResult:
        language = detect_language(message, language_hint)
        intent = route(message)
        cid = secrets.token_urlsafe(16)
        try:
            cid = await self._resolve_conversation(conversation_id)
            return await self._answer(message, language, cid, intent)
        except Exception:
            log.exception("chat operation failed; returning cached-contact fallback")
            return await self._fallback(cid, language, intent)

    async def _answer(self, message: str, language: str, cid: str, intent: Intent) -> ChatResult:
        t0 = time.perf_counter()

        if intent & Intent.SMALLTALK:
            reply = SMALLTALK_REPLY[language]
            await self._save(cid, message, reply)
            return ChatResult(reply, cid, language, intent.label)

        if intent & Intent.PRODUCT_LIVE and not self.s.catalogue_enabled:
            reply = CATALOGUE_UNCONFIRMED[language].format(email=self._email_suffix(language))
            await self._save(cid, message, reply)
            return ChatResult(reply, cid, language, intent.label,
                              needs_human=bool(intent & Intent.ORDER_ACCOUNT))

        product_query = message
        if intent & Intent.PRODUCT_LIVE or catalogue.is_product_reference(message):
            contexts = await self._product_context(cid)
            product_query, ambiguous = catalogue.resolve_reference(message, contexts)
            if ambiguous:
                reply = {"en": "Which product do you mean? Please give its name or its number from the products shown.",
                         "ar": "أي منتج تقصد؟ اذكر اسمه أو رقمه من المنتجات المعروضة."}[language]
                await self._save(cid, message, reply)
                return ChatResult(reply, cid, language, Intent.PRODUCT_LIVE.label)
            if product_query != message:
                intent |= Intent.PRODUCT_LIVE
                if intent == (Intent.PRODUCT_LIVE | Intent.KNOWLEDGE):
                    intent = Intent.PRODUCT_LIVE

        history = await self._history(cid)
        query = product_query if product_query != message else await self._condense(message, history)

        try:
            chunks = await retrieve(self.pool, self.embedder, self.s, query, language, always_documents=["contact"])
        except Exception:
            log.exception("retrieval failed")
            return await self._fallback(cid, language, intent)

        cat = None
        if intent & Intent.PRODUCT_LIVE:
            cat = await catalogue.lookup(product_query, language, enabled=self.s.catalogue_enabled,
                                         base_url=self.s.catalogue_base_url or catalogue.API_BASE,
                                         website=self.s.source_base_url or catalogue.STORE_BASE)

        if intent & Intent.PRODUCT_LIVE and (cat is None or cat.status is not catalogue.CatalogueStatus.OK or not cat.products):
            reply = CATALOGUE_UNCONFIRMED[language].format(email=self._email_suffix(language))
            await self._save(cid, message, reply)
            return ChatResult(reply, cid, language, intent.label, needs_human=bool(intent & Intent.ORDER_ACCOUNT))

        if intent == Intent.PRODUCT_LIVE and cat and cat.products:
            size_answer = catalogue.available_sizes_answer(message, cat.products, language)
            if size_answer:
                sources = [{"title": "Product collection" if language == "en" else "تشكيلة المنتجات",
                            "url": cat.products[0]["url"], "document_id": "catalogue-" + language}]
                await self._save(cid, message, size_answer, products=cat.products)
                return ChatResult(size_answer, cid, language, intent.label, sources=sources, products=cat.products)

        messages = [{"role": "system", "content": SYSTEM_PROMPT}, *history,
                    {"role": "user", "content": build_user_turn(
                        message, language, chunks, catalogue.live_data_note(cat),
                        " ".join(note for flag, note in INTENT_NOTES.items() if intent & flag) +
                        (" The visitor product reference is already resolved from the earlier displayed list. Any ordinal refers to that earlier list, not the number or position of products in this fresh lookup. Answer about the selected product directly; do not treat having one selected result as missing data. Resolved identity only: " + product_query if product_query != message else ""))}]
        try:
            raw = await self.llm.complete(messages, json_mode=True, max_tokens=700)
        except RateLimitError:
            log.warning("generation temporarily rate-limited by provider")
            return await self._fallback(cid, language, intent, busy=True)
        except Exception:
            log.exception("generation failed")
            return await self._fallback(cid, language, intent)

        parsed = parse_model_json(raw)
        if parsed is None:
            log.warning("model returned unparsable output")
            return await self._fallback(cid, language, intent)

        can_answer = parsed["can_answer"]
        by_id = {c.chunk_id: c for c in chunks}
        cited = [by_id[i] for i in parsed["sources"] if i in by_id]
        if can_answer and intent & (Intent.KNOWLEDGE | Intent.SHIPPING) and not cited:
            return await self._fallback(cid, language, intent)
        sources, seen = [], set()
        for c in cited:
            if c.document_id not in seen:
                seen.add(c.document_id)
                sources.append({"title": c.title, "url": _public_url(c.source_url, self.s.source_base_url),
                                "document_id": c.document_id})

        if cat and cat.status is catalogue.CatalogueStatus.OK and cat.products:
            sources.append({"title": "Product collection" if language == "en" else "تشكيلة المنتجات",
                            "url": cat.products[0]["url"], "document_id": "catalogue-" + language})
        answer = parsed["answer"].strip()
        await self._save(cid, message, answer, products=cat.products if cat else None)
        log.info("chat intent=%s lang=%s retrieved=%s cited=%s can_answer=%s ms=%d",
                 intent.label, language, [c.chunk_id for c in chunks], [c.chunk_id for c in cited],
                 can_answer, (time.perf_counter() - t0) * 1000)
        return ChatResult(
            answer=answer, conversation_id=cid, language=language, intent=intent.label, sources=sources,
            products=(cat.products if cat else []),
            needs_human=(not can_answer) or bool(intent & Intent.ORDER_ACCOUNT),
        )
