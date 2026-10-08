"""Offline providers for the dev server and tests; never selected by production startup."""
import hashlib
import json
import math
import re

class FakeEmbedder:
    """Deterministic bag-of-words hashing embedder: gives real lexical similarity, no network."""

    def __init__(self, dimensions=1024):
        self.dimensions = dimensions
        self.calls = 0
        self.texts_embedded = 0

    async def embed(self, texts):
        self.calls += 1
        self.texts_embedded += len(texts)
        out = []
        for t in texts:
            v = [0.0] * self.dimensions
            for tok in re.findall(r"\w+", t.lower()):
                h = int(hashlib.md5(tok.encode()).hexdigest(), 16)
                v[h % self.dimensions] += 1.0
            n = math.sqrt(sum(x * x for x in v)) or 1.0
            out.append([x / n for x in v])
        return out


class FakeChat:
    """Records every call. Default reply cites the first chunk in the evidence block."""

    def __init__(self):
        self.calls: list[dict] = []
        self.next_raw: str | None = None
        self.raise_on_generate = False

    async def complete(self, messages, *, json_mode=False, max_tokens=700):
        self.calls.append({"messages": messages, "json_mode": json_mode})
        if not json_mode:  # condense call
            return "standalone: " + messages[-1]["content"].split("Last visitor message:")[-1].strip()
        if self.raise_on_generate:
            raise RuntimeError("boom")
        if self.next_raw is not None:
            raw, self.next_raw = self.next_raw, None
            return raw
        user = messages[-1]["content"]
        ids = re.findall(r'<chunk id="([^"]+)"', user)
        return json.dumps({"answer": "stub answer", "can_answer": True, "sources": ids[:1]})


