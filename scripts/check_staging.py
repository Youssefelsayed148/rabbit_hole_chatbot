"""Verify staging over HTTPS; never deploys or calls the admin endpoints."""
import argparse
import json
import os
from urllib.parse import urlsplit

import httpx

from app.main import ChatResponse


def check_url(value):
    parsed = urlsplit(value)
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password
            or parsed.query or parsed.fragment or parsed.path not in ("", "/")):
        raise ValueError("Service URL must be an HTTPS origin with no credentials, query or path")
    return value.rstrip("/")


def check(client, allowed, disallowed, key):
    if allowed == disallowed:
        raise ValueError("Allowed and disallowed origins must differ")
    def require(condition, message):
        if not condition:
            raise RuntimeError(message)
        print("PASS:", message)

    asset = client.get("/widget.js")
    require(asset.status_code == 200 and "RabbitHoleChat" in asset.text, "widget reachable over HTTPS")
    require(asset.headers.get("content-type", "").startswith("application/javascript"), "widget JavaScript content type")
    require(asset.headers.get("cache-control") == "public, max-age=3600, must-revalidate", "widget cache policy")
    require(asset.headers.get("x-content-type-options") == "nosniff", "widget nosniff header")
    require(client.get("/demo.html").status_code == 404, "demo hidden outside development")
    headers = {"Origin": allowed, "Access-Control-Request-Method": "POST",
               "Access-Control-Request-Headers": "content-type,x-site-key"}
    preflight = client.options("/chat", headers=headers)
    require(preflight.status_code == 200 and preflight.headers.get("access-control-allow-origin") == allowed,
            "allowed-origin preflight")
    allowed_headers = preflight.headers.get("access-control-allow-headers", "").lower()
    require("x-site-key" in allowed_headers and "content-type" in allowed_headers, "site-key/JSON headers allowed")
    require("POST" in preflight.headers.get("access-control-allow-methods", ""), "POST allowed")
    denied = client.options("/chat", headers={**headers, "Origin": disallowed})
    require(denied.status_code == 400 and "access-control-allow-origin" not in denied.headers, "disallowed-origin preflight denied")
    request_headers = {"Origin": allowed, "X-Site-Key": key}
    response = client.post("/chat", headers=request_headers, json={"message": "hello", "language": "en"})
    require(response.status_code == 200 and response.headers.get("access-control-allow-origin") == allowed,
            "allowed-origin chat with site key")
    body = ChatResponse.model_validate(response.json())
    require(bool(body.answer) and body.language == "en" and not body.products, "chat response contract")
    follow = client.post("/chat", headers=request_headers,
                         json={"message": "مرحبا", "language": "ar"})
    require(follow.status_code == 200 and ChatResponse.model_validate(follow.json()).language == "ar", "Arabic round trip")
    denied_chat = client.post("/chat", headers={"Origin": disallowed, "X-Site-Key": key}, json={"message": "hello"})
    require(denied_chat.status_code == 403, "disallowed-origin chat denied")
    no_key = client.post("/chat", headers={"Origin": allowed}, json={"message": "hello"})
    require(no_key.status_code == 401, "missing site key denied")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url")
    parser.add_argument("--allowed-origin", required=True)
    parser.add_argument("--disallowed-origin", default="https://disallowed.invalid")
    args = parser.parse_args()
    key = os.environ.get("STAGING_SITE_KEY", "")
    if not key:
        parser.error("Set STAGING_SITE_KEY to the public widget site key")
    try:
        with httpx.Client(base_url=check_url(args.url), timeout=60, follow_redirects=False) as client:
            check(client, args.allowed_origin, args.disallowed_origin, key)
    except (ValueError, RuntimeError, httpx.HTTPError) as error:
        print("FAIL:", type(error).__name__, str(error))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
