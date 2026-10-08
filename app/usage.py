"""Opt-in local OpenAI request/usage accounting; never records prompts or credentials."""
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from openai import DefaultAsyncHttpxClient


def usage_http_client(path: str) -> DefaultAsyncHttpxClient:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)

    def write(event):
        event['time_utc'] = datetime.now(timezone.utc).isoformat()
        fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        try:
            os.write(fd, (json.dumps(event, ensure_ascii=True) + '\n').encode())
        finally:
            os.close(fd)

    async def request_hook(request):
        call_id = uuid4().hex
        request.extensions['usage_call_id'] = call_id
        # Only the model name is retained from the body, never input/messages.
        body = json.loads(request.content)
        write({'event': 'request', 'call_id': call_id,
               'endpoint': request.url.path, 'model': body.get('model')})

    async def response_hook(response):
        await response.aread()
        try:
            body = response.json()
        except ValueError:
            body = {}
        # Whitelist numeric usage counters, excluding response text and headers.
        usage = body.get('usage') or {}
        details = usage.get('prompt_tokens_details') or {}
        write({'event': 'response', 'call_id': response.request.extensions['usage_call_id'],
               'status': response.status_code, 'model': body.get('model'),
               'prompt_tokens': usage.get('prompt_tokens', 0),
               'completion_tokens': usage.get('completion_tokens', 0),
               'cached_tokens': details.get('cached_tokens', 0),
               'total_tokens': usage.get('total_tokens', 0)})

    return DefaultAsyncHttpxClient(event_hooks={'request': [request_hook], 'response': [response_hook]})

