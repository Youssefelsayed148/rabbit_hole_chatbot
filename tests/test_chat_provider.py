"""Chat can use a separate OpenAI-compatible provider while embeddings stay on OpenAI."""
import pytest

from app.config import Settings
from app.providers import OpenAIChat, OpenAIEmbedder


def test_default_uses_openai_for_chat_and_embeddings():
    s = Settings(openai_api_key="sk-oa")
    assert str(OpenAIChat(s).client.base_url).startswith("https://api.openai.com")
    assert OpenAIChat(s).client.api_key == "sk-oa"


def test_chat_override_leaves_embeddings_on_openai():
    s = Settings(openai_api_key="sk-oa", chat_api_key="sk-or", chat_base_url="https://openrouter.ai/api/v1")
    chat, emb = OpenAIChat(s), OpenAIEmbedder(s)
    assert str(chat.client.base_url).startswith("https://openrouter.ai") and chat.client.api_key == "sk-or"
    assert str(emb.client.base_url).startswith("https://api.openai.com") and emb.client.api_key == "sk-oa"


def test_chat_base_url_without_chat_key_fails_clearly():
    with pytest.raises(RuntimeError, match="CHAT_API_KEY"):
        OpenAIChat(Settings(openai_api_key="", chat_base_url="https://example.com/v1"))


def test_separate_chat_endpoint_never_receives_embedding_credential():
    with pytest.raises(RuntimeError, match="CHAT_API_KEY"):
        OpenAIChat(Settings(openai_api_key="sk-embedding-only", chat_base_url="https://openrouter.ai/api/v1"))


def test_chat_settings_are_loaded_from_environment(monkeypatch):
    monkeypatch.setenv("CHAT_API_KEY", "sk-chat")
    monkeypatch.setenv("CHAT_BASE_URL", "https://openrouter.ai/api/v1")
    monkeypatch.setenv("CHAT_JSON_MODE", "false")
    monkeypatch.setenv("OPENAI_CHAT_MODEL", "google/gemma-test")
    s = Settings.from_env()
    assert s.chat_api_key == "sk-chat"
    assert s.chat_base_url == "https://openrouter.ai/api/v1"
    assert s.chat_json_mode is False
    assert s.chat_model == "google/gemma-test"


def test_compose_forwards_separate_chat_settings_only_to_real_services():
    from pathlib import Path
    import yaml
    config = yaml.safe_load(Path("docker-compose.yml").read_text())
    for name in ("api-real", "real-smoke", "quality"):
        env = config["services"][name]["environment"]
        assert env["CHAT_API_KEY"] == "${CHAT_API_KEY:-}"
        assert env["CHAT_BASE_URL"] == "${CHAT_BASE_URL:-}"
        assert env["CHAT_JSON_MODE"] == "${CHAT_JSON_MODE:-true}"
        assert env["CHAT_FREE_ONLY"] == "${CHAT_FREE_ONLY:-false}"
        assert env["CHAT_FALLBACK_MODELS"] == "${CHAT_FALLBACK_MODELS:-}"
    assert "CHAT_API_KEY" not in config["services"]["api"]["environment"]


def test_blank_base_url_environment_uses_openai_default(monkeypatch):
    monkeypatch.setenv("OPENAI_BASE_URL", "")
    s = Settings(openai_api_key="sk-oa")
    assert str(OpenAIEmbedder(s).client.base_url) == "https://api.openai.com/v1/"
    assert str(OpenAIChat(s).client.base_url) == "https://api.openai.com/v1/"


@pytest.mark.parametrize("primary,fallbacks", [
    ("google/gemma-4-31b-it", ["openrouter/free"]),
    ("google/gemma-4-31b-it:free", ["openai/gpt-4.1-mini"]),
    ("openrouter/auto", []),
])
def test_free_only_rejects_paid_models(primary, fallbacks):
    with pytest.raises(ValueError, match="free model IDs"):
        OpenAIChat(Settings(chat_base_url="https://openrouter.ai/api/v1", chat_api_key="test",
                            chat_model=primary, chat_fallback_models=fallbacks, chat_free_only=True))


@pytest.mark.parametrize("endpoint", ["https://example.com/v1", "https://openrouter.ai.evil.com/v1", "http://openrouter.ai/api/v1"])
def test_free_routing_requires_openrouter(endpoint):
    with pytest.raises(ValueError, match="HTTPS OpenRouter"):
        OpenAIChat(Settings(chat_base_url=endpoint, chat_api_key="test",
                            chat_model="openrouter/free", chat_free_only=True))


def test_free_routing_environment(monkeypatch):
    monkeypatch.setenv("CHAT_FREE_ONLY", "true")
    monkeypatch.setenv("CHAT_FALLBACK_MODELS", " openrouter/free, ,google/other:free ")
    s = Settings.from_env()
    assert s.chat_free_only is True
    assert s.chat_fallback_models == ["openrouter/free", "google/other:free"]
