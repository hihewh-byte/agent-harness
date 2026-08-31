#!/usr/bin/env python3
import hashlib
import hmac
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient

from tax_agent.api.app import create_app
from tax_agent.rules_webhook import should_trigger_sync, verify_github_signature


def main() -> int:
    assert should_trigger_sync({"ref": "refs/heads/main"}) is True
    assert should_trigger_sync({"ref": "refs/heads/dev"}) is False
    assert should_trigger_sync({"action": "sync_rules"}) is True
    print("PASS should_trigger_sync")

    secret = "test-webhook-secret"
    os.environ["TAX_AGENT_RULES_WEBHOOK_SECRET"] = secret
    body = b'{"ref":"refs/heads/main"}'
    sig = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    assert verify_github_signature(body, sig)
    assert not verify_github_signature(body, "sha256=bad")
    print("PASS github signature")

    client = TestClient(create_app())
    bad = client.post("/rules/webhook", data=body, headers={"X-Hub-Signature-256": "sha256=bad"})
    assert bad.status_code == 401
    ok = client.post("/rules/webhook", data=body, headers={"X-Hub-Signature-256": sig})
    assert ok.status_code == 200, ok.text
    assert ok.json().get("triggered") is True
    print("PASS webhook endpoint")

    status = client.get("/rules/status")
    assert status.status_code == 200
    assert status.json().get("latestStable")
    print("PASS rules status")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
