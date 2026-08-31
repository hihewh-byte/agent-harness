#!/usr/bin/env python3
"""D1-D2 API E2E verification (companion to browser UI checks)."""

import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE = "http://127.0.0.1:8790"


def _post(path: str, body: dict) -> dict:
    req = urllib.request.Request(
        f"{BASE}{path}",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.loads(r.read().decode("utf-8"))


def _get(path: str) -> dict:
    with urllib.request.urlopen(f"{BASE}{path}", timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def main() -> int:
    try:
        _get("/tax/llm/status")
    except (urllib.error.URLError, TimeoutError) as exc:
        print(f"SKIP: API not running at {BASE} ({exc})")
        return 0

    sid = _post("/tax/session/new", {})["sessionId"]
    user_key = "d-e2e-browser-user"

    # D2 followUps
    prov = _post(
        "/tax/chat",
        {
            "sessionId": sid,
            "userKey": user_key,
            "message": "22年的补申报的汇率是如何确定的",
            "taxYear": 2022,
            "llmModel": "auto",
        },
    )
    fu = prov.get("followUps") or (prov.get("llm") or {}).get("followUps") or []
    assert len(fu) == 3, fu
    comp = ((prov.get("llm") or {}).get("runtime") or {}).get("composer") or {}
    print(f"PASS D2 provenance followUps×3 narrated={comp.get('narrated')} fb={comp.get('fallbackReason')}")

    # D1 policy + citation
    pol = _post(
        "/tax/chat",
        {
            "sessionId": sid,
            "userKey": user_key,
            "message": "境外股票赚的钱要交税吗",
            "taxYear": 2024,
            "llmModel": "auto",
        },
    )
    reply = pol.get("reply") or ""
    assert "申报" in reply or "财产转让" in reply
    pcomp = ((pol.get("llm") or {}).get("runtime") or {}).get("composer") or {}
    cite = pcomp.get("citationAudit") or {}
    print(
        f"PASS D1 policy narrated={pcomp.get('narrated')} "
        f"cite_ok={cite.get('ok')} len={len(reply)}"
    )

    # D2 profile readback
    prof = _get(f"/tax/user/profile?userKey={user_key}")
    assert prof.get("hasProfile")
    print(f"PASS D2 profile llm={prof.get('llmPreference')} verb={prof.get('replyVerbosity')}")

    # D2 SSE follow_ups event order
    q = urllib.parse.urlencode(
        {
            "sessionId": sid,
            "userKey": user_key,
            "message": "汇算清缴什么时候办",
            "taxYear": 2024,
            "llmModel": "__off__",
        }
    )
    with urllib.request.urlopen(f"{BASE}/tax/chat/stream?{q}", timeout=60) as r:
        raw = r.read().decode("utf-8")
    assert "event: follow_ups" in raw, "missing follow_ups SSE event"
    assert "event: done" in raw
    print("PASS D2 SSE follow_ups event present")

    print("PASS D1-D2 API E2E verify")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
