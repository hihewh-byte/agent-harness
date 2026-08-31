#!/usr/bin/env python3
"""Vanguard transaction history CSV parser self-check."""

import sys
from collections import Counter
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tax_agent.models import EventType
from tax_agent.parser.broker_parser import BrokerParser
from tax_agent.parser.vanguard_parser import parse_vanguard_csv

TX = ROOT / "tests" / "fixtures" / "broker" / "vanguard_transaction_history.csv"


def main() -> int:
    assert TX.exists()
    p = BrokerParser()
    r = p.parse_path(TX)
    assert r.broker_template_id == "broker_vanguard_v1", r.broker_template_id
    c = Counter(e.event_type for e in r.events)
    assert c[EventType.DIVIDEND] == 2, c
    assert c[EventType.CAPITAL_GAIN] == 2, c
    assert c[EventType.INTEREST] == 1, c
    assert sum(e.gross_amount.amount for e in r.events) == Decimal("500.00")
    print("PASS vanguard broker parser:", dict(c))

    text = TX.read_text(encoding="utf-8")
    evs, w, err = parse_vanguard_csv(text, "t.csv")
    assert not err and len(evs) == 5
    print("PASS vanguard direct parser:", len(evs), "events")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
