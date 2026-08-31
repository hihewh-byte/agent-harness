#!/usr/bin/env python3
"""FIFO cost-basis matching self-check."""

from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tax_agent.compute_engine import ComputeEngine, ComputeRequest
from tax_agent.cost_basis import (
    TradeLeg,
    match_fifo,
    per_disposal_positive_gain_cny,
    taxable_gain_cny,
)
from tax_agent.fx import apply_fx_to_events
from tax_agent.models import EventType, Money, ResidentStatus, TaxEvent
from tax_agent.parser.broker_parser import BrokerParser

TAX2022 = ROOT / "tests" / "fixtures" / "broker" / "futu_tax_2022_annual.xlsx"
FX = Decimal("7.10")


def test_fifo_simple() -> None:
    legs = [
        TradeLeg("2024-01-01", "AAA", "buy", Decimal("10"), Decimal("1000"), sort_key=("2024-01-01", 1)),
        TradeLeg("2024-06-01", "AAA", "sell", Decimal("-4"), Decimal("600"), sort_key=("2024-06-01", 2)),
    ]
    gains, warnings = match_fifo(legs)
    assert not warnings, warnings
    assert len(gains) == 1
    assert gains[0].gain_usd == Decimal("200.00")
    assert gains[0].cost_basis_usd == Decimal("400.00")
    print("PASS fifo simple match")


def test_property_transfer_formula() -> None:
    events = [
        TaxEvent(
            event_type=EventType.CAPITAL_GAIN,
            trade_date="2024-07-01",
            gross_amount=Money(amount=Decimal("100"), currency="USD"),
            amount_cny=Decimal("710.00"),
            fx_rate_used=FX,
        ),
        TaxEvent(
            event_type=EventType.CAPITAL_GAIN,
            trade_date="2024-08-01",
            gross_amount=Money(amount=Decimal("-50"), currency="USD"),
            amount_cny=Decimal("-355.00"),
            fx_rate_used=FX,
        ),
    ]
    assert per_disposal_positive_gain_cny(events) == Decimal("710.00")
    assert taxable_gain_cny(events) == Decimal("355.00")
    res = ComputeEngine().compute(
        ComputeRequest(
            events=events,
            tax_year=2024,
            resident_status=ResidentStatus.CN_TAX_RESIDENT,
            fx_policy="safe_harbor_monthly",
        )
    )
    cg = next(li for li in res.line_items if li.tax_category == "cn_property_transfer")
    assert cg.taxable_income_cny == Decimal("355.00")
    assert cg.tax_due_cny == Decimal("71.00")
    print("PASS property transfer annual net gain")


def test_futu_2022_fixture() -> None:
    assert TAX2022.is_file(), "missing futu 2022 fixture"
    parsed = BrokerParser().parse_path(TAX2022)
    cg = [e for e in parsed.events if e.event_type == EventType.CAPITAL_GAIN]
    assert len(cg) == 14, len(cg)
    assert all(e.classification_status == "confirmed" for e in cg), [
        e.classification_status for e in cg
    ]
    pos_usd = sum(max(Decimal("0"), e.gross_amount.amount) for e in cg if e.gross_amount)
    assert pos_usd == Decimal("1365.38"), pos_usd
    for e in cg:
        e.amount_cny = e.fx_rate_used = e.fx_rate_source = None
    fx_events = apply_fx_to_events(
        cg,
        fx_rate=Decimal("7.0288"),
        policy="cn_supplemental",
        filing_date="2026-04-15",
    )
    res = ComputeEngine().compute(
        ComputeRequest(
            events=fx_events,
            tax_year=2022,
            resident_status=ResidentStatus.CN_TAX_RESIDENT,
            fx_policy="cn_supplemental",
            filing_date="2026-04-15",
        )
    )
    assert res.summary["taxableIncomeCny"] == "0.00"
    assert res.summary["taxDueCny"] == "0.00"
    print("PASS futu 2022 FIFO fixture: annual net loss, tax due 0")


def main() -> int:
    test_fifo_simple()
    test_property_transfer_formula()
    test_futu_2022_fixture()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
