#!/usr/bin/env python3
"""Self-check: IBKR parser + FastAPI upload/compute flow."""

from __future__ import annotations

import json
import subprocess
import sys
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tax_agent.parser.broker_parser import BrokerParser

FIXTURE = ROOT / "tests" / "fixtures" / "broker"
XLSX = FIXTURE / "ibkr_mini.xlsx"
SCHWAB_TX = FIXTURE / "schwab_transactions_realistic.csv"
SCHWAB_GL = FIXTURE / "schwab_realized_gl.csv"


def ensure_xlsx() -> None:
    if XLSX.exists():
        return
    subprocess.run([sys.executable, str(ROOT / "scripts" / "build_ibkr_sample_xlsx.py")], check=True)


def test_parser() -> None:
    ensure_xlsx()
    p = BrokerParser(template_id="broker_ibkr_v1")
    r = p.parse_path(XLSX)
    assert r.broker_template_id == "broker_ibkr_v1", r.broker_template_id
    assert len(r.events) >= 2, f"expected >=2 events, got {len(r.events)}"
    types = {e.event_type.value for e in r.events}
    assert "DIVIDEND" in types
    assert "CAPITAL_GAIN" in types
    print(f"PASS parser: {len(r.events)} events, types={types}")


def test_api() -> None:
    try:
        from fastapi.testclient import TestClient
    except ImportError:
        print("SKIP api: install fastapi")
        return

    from tax_agent.api.app import create_app

    ensure_xlsx()
    client = TestClient(create_app())
    assert client.get("/health").json()["status"] == "ok"

    with XLSX.open("rb") as f:
        up = client.post(
            "/tax/upload",
            files={"file": ("ibkr_mini.xlsx", f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )
    assert up.status_code == 200, up.text
    dataset_id = up.json()["datasetId"]
    assert up.json()["eventCount"] >= 2

    comp = client.post(
        "/tax/compute",
        json={
            "datasetId": dataset_id,
            "taxYear": 2024,
            "residentStatus": "cn_tax_resident",
            "defaultFxRate": 7.10,
        },
    )
    assert comp.status_code == 200, comp.text
    body = comp.json()
    assert body["riskLevel"] in ("low", "medium")
    net = Decimal(body["summary"]["netTaxDueCny"])
    assert net > 0
    run_id = body["runId"]

    rep = client.get(f"/tax/report/{run_id}")
    assert rep.status_code == 200
    assert "结论摘要" in rep.json()["markdown"]

    chat = client.post(
        "/tax/chat",
        json={
            "sessionId": up.json()["sessionId"],
            "message": "按 2024 年测算税额",
            "datasetId": dataset_id,
            "taxYear": 2024,
        },
    )
    assert chat.status_code == 200, chat.text
    chat_body = chat.json()
    assert chat_body.get("runId")
    assert chat_body.get("summary", {}).get("netTaxDueCny")
    assert chat_body.get("riskLevel")

    assert client.get("/health").json().get("store") == "sqlite"
    print(f"PASS api: netTaxDueCny={net}, runId={run_id}, chat ok")


def test_schwab_upload_flow(client) -> None:
    sid = client.post("/tax/session/new").json()["sessionId"]
    for path in (SCHWAB_TX, SCHWAB_GL):
        with path.open("rb") as f:
            r = client.post(
                "/tax/upload",
                data={"sessionId": sid, "brokerTemplateId": "broker_schwab_v1"},
                files={"file": (path.name, f, "text/csv")},
            )
        assert r.status_code == 200, r.text
    last = r.json()
    assert last["brokerTemplateId"] == "broker_schwab_v1"
    assert last["eventCount"] >= 5
    comp = client.post(
        "/tax/compute",
        json={
            "datasetId": last["datasetId"],
            "sessionId": sid,
            "taxYear": 2024,
            "residentStatus": "cn_tax_resident",
        },
    )
    assert comp.status_code == 200
    cg_inferred = any(
        li.get("taxCategory") == "cn_property_transfer" for li in comp.json().get("lineItems", [])
    )
    assert cg_inferred
    print(f"PASS schwab api flow: events={last['eventCount']}, net={comp.json()['summary'].get('netTaxDueCny')}")


def main() -> int:
    test_parser()
    test_api()
    try:
        from fastapi.testclient import TestClient
        from tax_agent.api.app import create_app

        test_schwab_upload_flow(TestClient(create_app()))
    except ImportError:
        pass
    print("\nAll parser+api checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
