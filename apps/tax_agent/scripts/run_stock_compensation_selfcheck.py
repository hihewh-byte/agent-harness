#!/usr/bin/env python3
"""Self-check for RSU/ESPP stock compensation modeling."""

from __future__ import annotations

import json
import sys
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tax_agent.compute_engine import ComputeEngine, ComputeRequest
from tax_agent.models import EventType, ResidentStatus, TaxEvent
from tax_agent.stock_compensation import (
    is_stock_compensation_event,
    partition_events,
    taxable_income_cny,
)

CASES = [
    ROOT / "tests" / "fixtures" / "golden" / "deterministic" / "case_det_rsu_vest_001.json",
    ROOT / "tests" / "fixtures" / "golden" / "deterministic" / "case_det_rsu_sale_001.json",
    ROOT / "tests" / "fixtures" / "golden" / "high_risk" / "case_stock_compensation.json",
]


def main() -> int:
    failures: list[str] = []

    vest = TaxEvent.from_dict(
        {
            "eventType": "STOCK_COMPENSATION",
            "tradeDate": "2024-01-01",
            "amountCny": "5000.00",
            "stockComp": {"kind": "rsu_vest"},
        }
    )
    sale = TaxEvent.from_dict(
        {
            "eventType": "STOCK_COMPENSATION",
            "tradeDate": "2024-02-01",
            "amountCny": "9000.00",
            "stockComp": {
                "kind": "rsu_sale",
                "proceedsCny": "9000.00",
                "costBasisCny": "6000.00",
            },
        }
    )
    div_mis = TaxEvent.from_dict(
        {
            "eventType": "DIVIDEND",
            "tradeDate": "2024-03-01",
            "amountCny": "100.00",
            "sourceRowRef": "RSU vest Q1",
        }
    )
    if taxable_income_cny(vest) != Decimal("5000.00"):
        failures.append("rsu_vest taxable mismatch")
    if taxable_income_cny(sale) != Decimal("3000.00"):
        failures.append("rsu_sale gain taxable mismatch")
    if not is_stock_compensation_event(div_mis):
        failures.append("keyword RSU should match stock comp")
    stock, regular = partition_events([vest, sale, div_mis])
    if len(stock) != 3 or len(regular) != 0:
        failures.append(f"partition expected 3 stock events, got {len(stock)}/{len(regular)}")

    engine = ComputeEngine()
    for path in CASES:
        case = json.loads(path.read_text(encoding="utf-8"))
        events = [TaxEvent.from_dict(e) for e in case["input"]["events"]]
        params = case["parameters"]
        result = engine.compute(
            ComputeRequest(
                events=events,
                tax_year=int(params["taxYear"]),
                resident_status=ResidentStatus(params["residentStatus"]),
                rule_snapshot_id=params["ruleSnapshotId"],
                data_quality={"coverage": {"withholding": 1.0}},
            )
        )
        exp = case["expected"]
        if result.risk_level.value != exp["riskLevel"]:
            failures.append(f"{path.name}: risk {result.risk_level.value}")
        if "R007" not in result.triggered_risk_rules:
            failures.append(f"{path.name}: missing R007")
        cats = [ln.tax_category for ln in result.line_items]
        if "cn_stock_compensation" not in cats:
            failures.append(f"{path.name}: missing cn_stock_compensation line")
        for key, val in (exp.get("summary") or {}).items():
            got = Decimal(result.summary.get(key, "0"))
            if got != Decimal(val):
                failures.append(f"{path.name}: {key} got {got} want {val}")

    blocking = TaxEvent.from_dict(
        {
            "eventType": "OTHER",
            "tradeDate": "2024-08-15",
            "amountCny": "21300.00",
            "classificationStatus": "ambiguous",
        }
    )
    block_result = engine.compute(
        ComputeRequest(
            events=[blocking],
            tax_year=2024,
            resident_status=ResidentStatus.CN_TAX_RESIDENT,
            data_quality={"coverage": {"withholding": 1.0}},
        )
    )
    if block_result.line_items:
        failures.append("R003 blocking high should not emit line items")

    if failures:
        for f in failures:
            print(f"FAIL: {f}")
        return 1
    print("PASS: stock compensation selfcheck ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
