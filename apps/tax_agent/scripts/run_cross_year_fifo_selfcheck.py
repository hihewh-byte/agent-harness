#!/usr/bin/env python3
"""Cross-year Futu tax FIFO rematch self-check."""

from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tax_agent.cost_basis import TradeLeg
from tax_agent.futu_session_fifo import (
    collect_merged_legs,
    finalize_futu_session_dataset,
    leg_to_dict,
    rematch_futu_capital_gains,
)
from tax_agent.models import EventType
from tax_agent.store_base import InMemoryDatasetStore
from tax_agent.parser.broker_parser import ParseResult
from tax_agent.models import TaxEvent, ResidentStatus
from tax_agent.compute_engine import ComputeEngine, ComputeRequest
from tax_agent.fx import apply_fx_to_events

FIXTURE_2022 = ROOT / "tests" / "fixtures" / "broker" / "futu_tax_2022_annual.xlsx"


def test_synthetic_cross_year() -> None:
    pkg_2022 = {
        "fileHash": "y2022",
        "taxYear": 2022,
        "legs": [
            leg_to_dict(
                TradeLeg(
                    "2022-03-01",
                    "TEST",
                    "buy",
                    Decimal("10"),
                    Decimal("1000"),
                    Decimal("0"),
                    "2022:1",
                    "证券",
                    ("2022-03-01", 1),
                )
            )
        ],
        "openingPositions": [],
    }
    pkg_2023 = {
        "fileHash": "y2023",
        "taxYear": 2023,
        "legs": [
            leg_to_dict(
                TradeLeg(
                    "2023-06-15",
                    "TEST",
                    "sell",
                    Decimal("-10"),
                    Decimal("800"),
                    Decimal("2"),
                    "2023:1",
                    "证券",
                    ("2023-06-15", 1),
                )
            )
        ],
        "openingPositions": [],
    }
    events, warnings = rematch_futu_capital_gains([pkg_2022, pkg_2023], [])
    cg = [e for e in events if e.event_type == EventType.CAPITAL_GAIN]
    assert len(cg) == 1, cg
    assert cg[0].gross_amount.amount == Decimal("-200.00"), cg[0].gross_amount.amount
    assert cg[0].trade_date.startswith("2023")
    assert cg[0].classification_status == "confirmed"
    assert any("跨年度" in w for w in warnings), warnings
    print("PASS synthetic 2022 buy / 2023 sell loss -200")


def test_2023_only_ambiguous() -> None:
    pkg_2023 = {
        "fileHash": "y2023solo",
        "taxYear": 2023,
        "legs": [
            leg_to_dict(
                TradeLeg(
                    "2023-06-15",
                    "TEST",
                    "sell",
                    Decimal("-10"),
                    Decimal("800"),
                    Decimal("0"),
                    "2023:1",
                    "证券",
                    ("2023-06-15", 1),
                )
            )
        ],
        "openingPositions": [
            {
                "symbol": "TEST",
                "quantity": "10",
                "asOfDate": "2023-01-01",
                "costBasisKnown": False,
            }
        ],
    }
    events, warnings = rematch_futu_capital_gains([pkg_2023], [])
    cg = events[0]
    assert cg.classification_status == "ambiguous"
    assert any("期初持仓" in w for w in warnings), warnings
    print("PASS 2023-only sell warns opening position without cost")


def test_store_merge_with_fixture_2022() -> None:
    if not FIXTURE_2022.is_file():
        print("SKIP fixture 2022 merge: futu_tax_2022_annual.xlsx missing")
        return
    from tax_agent.parser.broker_parser import BrokerParser

    store = InMemoryDatasetStore()
    parser = BrokerParser()
    p1 = parser.parse_path(FIXTURE_2022)
    s1 = store.save_parse(p1)
    assert s1.data_quality.get("futuTaxPackages"), "missing package"
    assert any(e.event_type == EventType.CAPITAL_GAIN for e in s1.events)
    print("PASS fixture 2022 package stored, events", len(s1.events))


def test_compute_year_filter() -> None:
    pkg_2022 = {
        "fileHash": "a",
        "taxYear": 2022,
        "legs": [
            leg_to_dict(
                TradeLeg("2022-01-01", "X", "buy", Decimal("1"), Decimal("100"), Decimal("0"), "a:1", "", ("2022-01-01", 1))
            )
        ],
        "openingPositions": [],
    }
    pkg_2023 = {
        "fileHash": "b",
        "taxYear": 2023,
        "legs": [
            leg_to_dict(
                TradeLeg("2023-01-01", "X", "sell", Decimal("-1"), Decimal("80"), Decimal("0"), "b:1", "", ("2023-01-01", 1))
            )
        ],
        "openingPositions": [],
    }
    events, _ = rematch_futu_capital_gains([pkg_2022, pkg_2023], [])
    fx = apply_fx_to_events(events, fx_rate=Decimal("7.10"))
    res = ComputeEngine().compute(
        ComputeRequest(
            events=fx,
            tax_year=2023,
            resident_status=__import__("tax_agent.models", fromlist=["ResidentStatus"]).ResidentStatus.CN_TAX_RESIDENT,
        )
    )
    assert res.summary["taxableIncomeCny"] == "0.00"
    print("PASS 2023 tax year attributes loss to 2023, taxable 0")


def main() -> int:
    test_synthetic_cross_year()
    test_2023_only_ambiguous()
    test_store_merge_with_fixture_2022()
    test_compute_year_filter()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
