"""Point the real OpenAI SDK clients at a local fake server and inspect the exact requests we send."""
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from app.providers import OpenAIChat, OpenAIEmbedder

SEEN: list[dict] = []


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        SEEN.append({"path": self.path, "body": body, "auth": self.headers.get("Authorization")})
        if self.path.endswith("/embeddings"):
            out = {"object": "list", "model": body["model"], "usage": {"prompt_tokens": 1, "total_tokens": 1},
                   "data": [{"object": "embedding", "index": i, "embedding": [0.1] * body.get("dimensions", 8)}
                            for i in reversed(range(len(body["input"])))]}   # out of order on purpose
        else:
            out = {"id": "x", "object": "chat.completion", "created": 0, "model": body["model"],
                   "choices": [{"index": 0, "finish_reason": "stop",
                                "message": {"role": "assistant", "content": '{"answer":"ok"}'}}],
                   "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}}
        data = json.dumps(out).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


@pytest.fixture(scope="module")
def server():
    srv = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_port}/v1"
    srv.shutdown()


async def test_embedding_request_shape_and_order(server, variant):
    SEEN.clear()
    s = variant(openai_base_url=server, openai_api_key="sk-test")
    vecs = await OpenAIEmbedder(s).embed(["a", "", "c"])
    req = SEEN[0]
    assert req["path"].endswith("/embeddings") and req["auth"] == "Bearer sk-test"
    assert req["body"]["model"] == "text-embedding-3-large" and req["body"]["dimensions"] == 1024
    assert req["body"]["input"] == ["a", " ", "c"]       # empty strings are replaced (API rejects them)
    assert len(vecs) == 3 and len(vecs[0]) == 1024


async def test_embedding_batches_of_96(server, variant):
    SEEN.clear()
    s = variant(openai_base_url=server, openai_api_key="sk-test")
    await OpenAIEmbedder(s).embed([f"t{i}" for i in range(200)])
    assert [len(r["body"]["input"]) for r in SEEN] == [96, 96, 8]


async def test_chat_request_shape(server, variant):
    SEEN.clear()
    s = variant(openai_base_url=server, openai_api_key="sk-test")
    out = await OpenAIChat(s).complete([{"role": "user", "content": "hi"}], json_mode=True, max_tokens=123)
    b = SEEN[0]["body"]
    assert out == '{"answer":"ok"}'
    assert b["model"] == "gpt-4.1-mini" and b["max_tokens"] == 123 and b["temperature"] == 0.2
    assert b["response_format"] == {"type": "json_object"}


async def test_temperature_omitted_for_reasoning_models(server, variant):
    SEEN.clear()
    s = variant(openai_base_url=server, openai_api_key="sk-test", temperature=None, chat_model="some-reasoning-model")
    await OpenAIChat(s).complete([{"role": "user", "content": "hi"}])
    assert "temperature" not in SEEN[0]["body"] and "response_format" not in SEEN[0]["body"]


async def test_separate_chat_provider_without_json_mode(server, variant):
    SEEN.clear()
    s = variant(chat_base_url=server, chat_api_key="sk-chat-only", openai_api_key="sk-embed-only",
                chat_model="google/gemma-test", chat_json_mode=False)
    client = OpenAIChat(s)
    try:
        await client.complete([{"role": "user", "content": "Return JSON"}], json_mode=True, max_tokens=700)
    finally:
        await client.client.close()
    req = SEEN[0]
    assert req["auth"] == "Bearer sk-chat-only"
    assert req["body"]["model"] == "google/gemma-test"
    assert req["body"]["max_tokens"] == 700
    assert "response_format" not in req["body"]

async def test_usage_log_records_tokens_without_payload_or_credentials(server, variant, monkeypatch, tmp_path):
    path = tmp_path / 'usage.jsonl'
    monkeypatch.setenv('OPENAI_USAGE_LOG', str(path))
    client = OpenAIChat(variant(openai_base_url=server, openai_api_key='sk-usage-test'))
    try:
        await client.complete([{'role': 'user', 'content': 'private-message-never-log'}])
    finally:
        await client.client.close()
    raw = path.read_text(encoding='utf-8-sig')
    assert 'private-message-never-log' not in raw and 'sk-usage-test' not in raw
    events = [json.loads(line) for line in raw.splitlines()]
    assert len(events) == 2
    assert events[0]['event'] == 'request' and events[0]['endpoint'] == '/v1/chat/completions'
    assert events[1]['event'] == 'response' and events[1]['status'] == 200
    assert events[0]['call_id'] == events[1]['call_id']
    assert events[1]['prompt_tokens'] == 1 and events[1]['completion_tokens'] == 1


async def test_free_only_fallback_request_preserves_evidence_and_zero_price(server, variant):
    SEEN.clear()
    primary = "google/gemma-4-31b-it:free"
    s = variant(chat_base_url="https://openrouter.ai/api/v1", chat_api_key="sk-chat-only",
                chat_model=primary, chat_free_only=True,
                chat_fallback_models=[primary, "google/gemma-4-26b-a4b-it:free", "google/gemma-4-26b-a4b-it:free"], chat_json_mode=True)
    client = OpenAIChat(s)
    client.client.base_url = server  # only transport changes; configuration validates the real endpoint
    messages = [{"role": "system", "content": "Use only evidence; return JSON"},
                {"role": "user", "content": "<evidence>Approved policy</evidence>"}]
    try:
        await client.complete(messages, json_mode=True, max_tokens=700)
    finally:
        await client.client.close()
    b = SEEN[0]["body"]
    assert b["model"] == primary
    assert b["models"] == [primary, "google/gemma-4-26b-a4b-it:free"]
    assert b["reasoning"] == {"enabled": False}
    assert b["response_format"] == {"type": "json_object"}
    assert b["provider"]["max_price"] == {"prompt": 0, "completion": 0, "request": 0}
    assert b["messages"] == messages and b["max_tokens"] == 700
    assert SEEN[0]["auth"] == "Bearer sk-chat-only"


async def test_default_chat_does_not_send_openrouter_parameters(server, variant):
    SEEN.clear()
    client = OpenAIChat(variant(openai_api_key="test", openai_base_url=server))
    try:
        await client.complete([{"role": "user", "content": "Hello"}])
    finally:
        await client.client.close()
    assert "models" not in SEEN[0]["body"] and "provider" not in SEEN[0]["body"]
