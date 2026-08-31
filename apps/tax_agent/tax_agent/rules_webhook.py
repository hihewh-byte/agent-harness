from __future__ import annotations

import hashlib
import hmac
import json
import os
from typing import Any


def webhook_secret() -> str | None:
    s = (os.environ.get("TAX_AGENT_RULES_WEBHOOK_SECRET") or "").strip()
    return s or None


def verify_github_signature(body: bytes, signature_header: str | None) -> bool:
    secret = webhook_secret()
    if not secret or not signature_header:
        return False
    if not signature_header.startswith("sha256="):
        return False
    expected = signature_header.split("=", 1)[1]
    digest = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(digest, expected)


def verify_shared_secret(header_value: str | None) -> bool:
    secret = webhook_secret()
    if not secret:
        return False
    return hmac.compare_digest((header_value or "").strip(), secret)


def should_trigger_sync(payload: dict[str, Any]) -> bool:
    """GitHub push to default branch or generic {action: sync_rules}."""
    if payload.get("action") in ("sync_rules", "publish_rules"):
        return True
    ref = str(payload.get("ref") or "")
    if ref.startswith("refs/heads/"):
        branch = ref.split("/", 2)[-1]
        expected = (os.environ.get("TAX_AGENT_RULES_WEBHOOK_BRANCH") or "main").strip()
        return branch == expected
    return bool(payload.get("sync") is True)


def parse_webhook_body(body: bytes) -> dict[str, Any]:
    if not body:
        return {"sync": True}
    try:
        data = json.loads(body.decode("utf-8"))
        return data if isinstance(data, dict) else {"sync": True}
    except json.JSONDecodeError:
        return {"sync": True}
