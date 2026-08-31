#!/usr/bin/env python3
"""Futu / Moomoo CSV parser self-check."""

import sys
from collections import Counter
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tax_agent.models import EventType
from tax_agent.parser.broker_parser import BrokerParser
from tax_agent.parser.futu_parser import parse_futu_csv

TX = ROOT / "tests" / "fixtures" / "broker" / "futu_transaction_history.csv"
XLSX = ROOT / "tests" / "fixtures" / "broker" / "futu_multiyear_tax_statement.xlsx"
TAX2022 = ROOT / "tests" / "fixtures" / "broker" / "futu_tax_2022_annual.xlsx"
TAX2022_INC = ROOT / "tests" / "fixtures" / "broker" / "futu_tax_2022_income_summary.xlsx"
CLASSIFIED_USD = ROOT / "tests" / "fixtures" / "broker" / "futu_classified_income_usd.xlsx"


def main() -> int:
    text = TX.read_text(encoding="utf-8")
    evs, w, err = parse_futu_csv(text, "t.csv")
    assert not err and len(evs) >= 4
    print("PASS futu csv parser (internal):", len(evs), "events")

    import subprocess

    subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "build_futu_multiyear_xlsx.py")],
        check=False,
        cwd=str(ROOT),
    )
    if XLSX.is_file():
        try:
            rx = BrokerParser(template_id="broker_futu_v1").parse_path(XLSX)
            print("PASS futu multiyear xlsx:", len(rx.events), "events")
        except ValueError:
            print("SKIP futu multiyear xlsx: desktop History fixture (tax workbook only)")

    if TAX2022.is_file():
        r22 = BrokerParser().parse_path(TAX2022)
        assert r22.broker_template_id == "broker_futu_v1", r22.broker_template_id
        cg = [e for e in r22.events if e.event_type == EventType.CAPITAL_GAIN]
        assert len(cg) == 14, len(cg)
        assert all(e.classification_status == "confirmed" for e in cg)
        assert all(e.trade_date.startswith("2022") for e in cg)
        pos = sum(max(Decimal("0"), e.gross_amount.amount) for e in cg if e.gross_amount)
        assert pos == Decimal("1365.38"), pos
        assert any("FIFO" in w for w in r22.warnings), r22.warnings
        print("PASS futu tax 2022 annual:", len(cg), "realized gain events (FIFO)")
    if TAX2022_INC.is_file():
        ri = BrokerParser().parse_path(TAX2022_INC)
        assert ri.broker_template_id == "broker_futu_v1"
        print("PASS futu tax 2022 income summary (legacy HKD):", len(ri.events), "events")
    if not CLASSIFIED_USD.is_file():
        subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "build_futu_classified_income_fixture.py")],
            check=False,
            cwd=str(ROOT),
        )
    if CLASSIFIED_USD.is_file():
        rc = BrokerParser().parse_path(CLASSIFIED_USD)
        div = [e for e in rc.events if e.event_type == EventType.DIVIDEND]
        interest = [e for e in rc.events if e.event_type == EventType.INTEREST]
        assert len(div) == 1 and len(interest) == 1, rc.events
        assert div[0].withholding_tax and div[0].withholding_tax.amount > 0
        print("PASS futu classified income USD:", f"div={div[0].gross_amount.amount} wh={div[0].withholding_tax.amount}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
