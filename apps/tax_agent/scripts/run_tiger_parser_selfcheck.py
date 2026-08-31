#!/usr/bin/env python3
"""Tiger Brokers CSV parser self-check."""

import sys
from collections import Counter
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tax_agent.models import EventType
from tax_agent.parser.broker_parser import BrokerParser
from tax_agent.parser.tiger_parser import parse_tiger_csv

TRADES = ROOT / "tests" / "fixtures" / "broker" / "tiger_trades.csv"
DIVS = ROOT / "tests" / "fixtures" / "broker" / "tiger_dividends.csv"


def main() -> int:
    assert TRADES.exists() and DIVS.exists()
    p = BrokerParser()

    r1 = p.parse_path(TRADES)
    assert r1.broker_template_id == "broker_tiger_v1", r1.broker_template_id
    c1 = Counter(e.event_type for e in r1.events)
    assert c1[EventType.CAPITAL_GAIN] == 2, c1
    assert sum(e.gross_amount.amount for e in r1.events) == Decimal("3100")
    print("PASS tiger trades:", dict(c1))

    r2 = p.parse_path(DIVS)
    assert r2.broker_template_id == "broker_tiger_v1"
    c2 = Counter(e.event_type for e in r2.events)
    assert c2[EventType.DIVIDEND] == 2, c2
    div = [e for e in r2.events if e.withholding_tax]
    assert len(div) == 2
    print("PASS tiger dividends:", dict(c2))

    text = TRADES.read_text(encoding="utf-8")
    evs, w, err = parse_tiger_csv(text, "t.csv")
    assert not err and len(evs) == 2
    print("PASS tiger direct parser")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
