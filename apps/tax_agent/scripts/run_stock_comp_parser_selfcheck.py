#!/usr/bin/env python3
"""Broker parser RSU/ESPP auto-detection self-check."""

from __future__ import annotations

import sys
from collections import Counter
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tax_agent.compute_engine import ComputeEngine, ComputeRequest
from tax_agent.fx import apply_fx_to_events
from tax_agent.models import EventType, ResidentStatus
from tax_agent.parser.broker_parser import BrokerParser
from tax_agent.parser.stock_comp_detect import infer_stock_comp_kind, compose_row_blob
from tax_agent.stock_compensation import stock_comp_kind

SCHWAB = ROOT / "tests" / "fixtures" / "broker" / "schwab_rsu_activity.csv"
FIDELITY = ROOT / "tests" / "fixtures" / "broker" / "fidelity_rsu_activity.csv"


def main() -> int:
    failures: list[str] = []

    assert infer_stock_comp_kind(compose_row_blob("Lapse Release", "RSU VEST")) == "rsu_vest"
    assert infer_stock_comp_kind(compose_row_blob("Sell", "SOLD RSU")) == "rsu_sale"
    assert infer_stock_comp_kind(compose_row_blob("ESPP Purchase", "employee stock purchase")) == "espp_discount"

    p = BrokerParser()
    rs = p.parse_path(SCHWAB)
    assert rs.broker_template_id == "broker_schwab_v1", rs.broker_template_id
    sc = [e for e in rs.events if e.event_type == EventType.STOCK_COMPENSATION]
    if len(sc) < 3:
        failures.append(f"schwab: expected >=3 STOCK_COMPENSATION, got {len(sc)}")
    kinds = {stock_comp_kind(e) for e in sc}
    for want in ("rsu_vest", "rsu_sale", "espp_discount"):
        if want not in kinds:
            failures.append(f"schwab: missing kind {want} in {kinds}")
    div = [e for e in rs.events if e.event_type == EventType.DIVIDEND]
    if len(div) != 1:
        failures.append(f"schwab: expected 1 dividend, got {len(div)}")

    rf = p.parse_path(FIDELITY)
    assert rf.broker_template_id == "broker_fidelity_v1"
    fsc = [e for e in rf.events if e.event_type == EventType.STOCK_COMPENSATION]
    if len(fsc) < 2:
        failures.append(f"fidelity: expected >=2 STOCK_COMPENSATION, got {len(fsc)}")
    if not any(stock_comp_kind(e) == "rsu_vest" for e in fsc):
        failures.append("fidelity: missing rsu_vest")
    if not any(stock_comp_kind(e) == "rsu_sale" for e in fsc):
        failures.append("fidelity: missing rsu_sale")

    # End-to-end compute: Schwab RSU vest only + FX
    vest_only = [e for e in sc if stock_comp_kind(e) == "rsu_vest"]
    if vest_only:
        fx_events = apply_fx_to_events(vest_only, fx_rate=Decimal("7.10"))
        result = ComputeEngine().compute(
            ComputeRequest(
                events=fx_events,
                tax_year=2024,
                resident_status=ResidentStatus.CN_TAX_RESIDENT,
                data_quality={"coverage": {"withholding": 1.0}},
            )
        )
        if "R007" not in result.triggered_risk_rules:
            failures.append("compute: missing R007")
        if not result.line_items:
            failures.append("compute: expected draft line items")
        net = Decimal(result.summary.get("netTaxDueCny", "0"))
        # 12000 USD * 7.1 * 20% = 17040
        if net != Decimal("17040.00"):
            failures.append(f"compute: net {net} expected 17040.00")

    if failures:
        for f in failures:
            print(f"FAIL: {f}")
        print("schwab counts:", Counter(e.event_type for e in rs.events))
        return 1
    print("PASS: stock comp parser selfcheck ok")
    print("schwab:", Counter(e.event_type for e in rs.events))
    print("fidelity:", Counter(e.event_type for e in rf.events))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
