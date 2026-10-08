"""Abuse controls. CORS alone does not authenticate callers: these checks add a public site key,
origin allow-list, per-IP rate limit and a daily request cap to protect the OpenAI bill."""
from __future__ import annotations

import hmac
import time
from collections import defaultdict, deque
from datetime import date

from fastapi import HTTPException, Request

from .config import Settings


class RateLimiter:
    def __init__(self, per_minute: int):
        self.per_minute = per_minute
        self.hits: dict[str, deque[float]] = defaultdict(deque)

    def check(self, key: str) -> bool:
        now = time.monotonic()
        q = self.hits[key]
        while q and now - q[0] > 60:
            q.popleft()
        if len(q) >= self.per_minute:
            return False
        q.append(now)
        if len(self.hits) > 10_000:  # opportunistic cleanup of idle keys
            for k in [k for k, v in self.hits.items() if not v or now - v[-1] > 60]:
                self.hits.pop(k, None)
        return True


class DailyCap:
    def __init__(self, cap: int):
        self.cap, self.day, self.count = cap, date.today(), 0

    def take(self) -> bool:
        today = date.today()
        if today != self.day:
            self.day, self.count = today, 0
        if self.count >= self.cap:
            return False
        self.count += 1
        return True


def client_ip(request: Request, trust_proxy: bool) -> str:
    if trust_proxy:
        fwd = request.headers.get("x-forwarded-for")
        if fwd:
            return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def check_public_access(request: Request, s: Settings) -> None:
    origin = request.headers.get("origin")
    if origin and origin not in s.allowed_origins:
        raise HTTPException(403, "Origin not allowed")
    if s.site_keys:
        supplied = request.headers.get("x-site-key", "")
        if not any(hmac.compare_digest(supplied, k) for k in s.site_keys):
            raise HTTPException(401, "Invalid site key")


def check_admin(request: Request, s: Settings) -> None:
    if not s.admin_token:
        raise HTTPException(503, "Admin API disabled (ADMIN_TOKEN not set)")
    supplied = request.headers.get("authorization", "").removeprefix("Bearer ").strip()
    if not hmac.compare_digest(supplied, s.admin_token):
        raise HTTPException(401, "Unauthorized")
