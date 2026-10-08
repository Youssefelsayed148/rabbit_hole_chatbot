"""Runtime configuration, read from environment variables (see .env.example)."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path


def _bool(name: str, default: bool) -> bool:
    v = os.environ.get(name)
    return default if v is None else v.strip().lower() in {"1", "true", "yes", "on"}


def _list(name: str) -> list[str]:
    return [x.strip() for x in os.environ.get(name, "").split(",") if x.strip()]


def _float_or_none(name: str) -> float | None:
    v = os.environ.get(name, "").strip()
    return float(v) if v else None


@dataclass(frozen=True)
class Settings:
    environment: str = "development"
    database_url: str = "postgresql://rh:rh@localhost:5432/rh"
    openai_api_key: str = ""
    chat_model: str = "gpt-4.1-mini"
    # Reasoning models reject a custom temperature; leave unset (None) for those.
    temperature: float | None = 0.2
    embed_model: str = "text-embedding-3-large"
    # Fixed at schema-creation time. 1024 keeps us under pgvector's index limits.
    embed_dimensions: int = 1024
    openai_timeout: float = 25.0
    openai_base_url: str = ""   # optional: proxy / compatible endpoint
    openai_max_retries: int = 2
    # Optional separate chat endpoint (e.g. OpenRouter). Blank falls back to the OpenAI key/base URL.
    # Embeddings always use the OpenAI settings above so vectors do not change.
    chat_api_key: str = ""
    chat_base_url: str = ""
    chat_json_mode: bool = True   # set false if the chat model rejects response_format
    chat_free_only: bool = False  # OpenRouter: reject paid models and cap provider prices at zero
    chat_fallback_models: list[str] = field(default_factory=list)

    data_dir: Path = Path(__file__).resolve().parent.parent / "data"
    # Test mode: also index the needs_review draft copy (shipping/payments wording).
    # Keep OFF in production until the owner confirms those facts.
    include_unreviewed: bool = False
    auto_ingest: bool = True

    top_k: int = 8            # candidates per retriever
    final_k: int = 4          # chunks kept after fusion
    expand_doc_max_chars: int = 1500   # small docs are pulled in whole (policy sections stay together)
    max_evidence_chunks: int = 8      # soft budget: an expanded document is never cut
    history_turns: int = 6            # previous visitor messages sent to the model

    # Security / abuse controls
    allowed_origins: list[str] = field(default_factory=list)
    site_keys: list[str] = field(default_factory=list)
    admin_token: str = ""
    rate_limit_per_min: int = 20
    daily_llm_call_cap: int = 5000
    trust_proxy: bool = False
    max_message_chars: int = 1000
    # Optional: re-point citation URLs at the final production domain (scheme+host only).
    source_base_url: str = ""

    # Data handling
    store_messages: bool = True
    message_retention_days: int = 30
    log_messages: bool = False

    # Live catalogue (not connected yet)
    catalogue_enabled: bool = False
    catalogue_base_url: str = ""
    catalogue_token: str = ""

    @property
    def allowed_statuses(self) -> list[str]:
        s = ["render_verified", "source_extracted"]
        if self.include_unreviewed:
            s.append("needs_review")
        return s

    def validate_startup(self) -> None:
        if self.environment.strip().lower() != "production":
            return
        required = {
            "SITE_KEYS": self.site_keys and all(key.strip() for key in self.site_keys),
            "ALLOWED_ORIGINS": self.allowed_origins and all(origin.strip() and origin != "*" for origin in self.allowed_origins),
            "ADMIN_TOKEN": self.admin_token.strip(),
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise ValueError("Production requires configured " + ", ".join(missing))

    @classmethod
    def from_env(cls) -> "Settings":
        e = os.environ
        d = cls()
        return cls(
            environment=e.get("ENV", d.environment),
            database_url=e.get("DATABASE_URL", d.database_url),
            openai_api_key=e.get("OPENAI_API_KEY", ""),
            chat_model=e.get("OPENAI_CHAT_MODEL", d.chat_model),
            temperature=_float_or_none("OPENAI_TEMPERATURE") if "OPENAI_TEMPERATURE" in e else d.temperature,
            embed_model=e.get("OPENAI_EMBED_MODEL", d.embed_model),
            embed_dimensions=int(e.get("EMBED_DIMENSIONS", d.embed_dimensions)),
            openai_timeout=float(e.get("OPENAI_TIMEOUT", d.openai_timeout)),
            openai_base_url=e.get("OPENAI_BASE_URL", ""),
            chat_api_key=e.get("CHAT_API_KEY", ""),
            chat_base_url=e.get("CHAT_BASE_URL", ""),
            chat_json_mode=_bool("CHAT_JSON_MODE", True),
            chat_free_only=_bool("CHAT_FREE_ONLY", False),
            chat_fallback_models=_list("CHAT_FALLBACK_MODELS"),
            data_dir=Path(e.get("DATA_DIR", str(d.data_dir))),
            include_unreviewed=_bool("INCLUDE_UNREVIEWED", False),
            auto_ingest=_bool("AUTO_INGEST", True),
            top_k=int(e.get("TOP_K", d.top_k)),
            final_k=int(e.get("FINAL_K", d.final_k)),
            allowed_origins=_list("ALLOWED_ORIGINS"),
            site_keys=_list("SITE_KEYS"),
            admin_token=e.get("ADMIN_TOKEN", ""),
            rate_limit_per_min=int(e.get("RATE_LIMIT_PER_MIN", d.rate_limit_per_min)),
            daily_llm_call_cap=int(e.get("DAILY_LLM_CALL_CAP", d.daily_llm_call_cap)),
            trust_proxy=_bool("TRUST_PROXY", False),
            source_base_url=e.get("SOURCE_BASE_URL", ""),
            store_messages=_bool("STORE_MESSAGES", True),
            message_retention_days=int(e.get("MESSAGE_RETENTION_DAYS", d.message_retention_days)),
            log_messages=_bool("LOG_MESSAGES", False),
            catalogue_enabled=_bool("CATALOGUE_ENABLED", False),
            catalogue_base_url=e.get("CATALOGUE_BASE_URL", ""),
            catalogue_token=e.get("CATALOGUE_TOKEN", ""),
        )


@lru_cache
def get_settings() -> Settings:
    return Settings.from_env()
