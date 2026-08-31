#!/usr/bin/env python3
"""Schwab realistic CSV + G/L merge self-check."""

import sys
from collections import Counter
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tax_agent.parser.broker_parser import BrokerParser
from tax_agent.parser.schwab_parser import merge_schwab_events, parse_schwab_csv
from tax_agent.models import EventType

TX = ROOT / "tests" / "fixtures" / "broker" / "schwab_transactions_realistic.csv"
GL = ROOT / "tests" / "fixtures" / "broker" / "schwab_realized_gl.csv"


def main() -> int:
    assert TX.exists() and GL.exists()

    p = BrokerParser()
    r1 = p.parse_path(TX)
    assert r1.broker_template_id == "broker_schwab_v1", r1.broker_template_id
    c1 = Counter(e.event_type for e in r1.events)
    assert c1[EventType.DIVIDEND] >= 1, c1
    assert c1[EventType.INTEREST] >= 1, c1
    assert c1[EventType.WITHHOLDING_TAX] >= 1, c1
    assert c1[EventType.CAPITAL_GAIN] >= 1, "Sell row should parse as inferred capital gain"
    sell = [e for e in r1.events if e.event_type == EventType.CAPITAL_GAIN][0]
    assert sell.classification_status == "inferred"
    print("PASS schwab transaction history:", dict(c1), "warnings=", len(r1.warnings))

    r2 = p.parse_path(GL)
    assert r2.broker_template_id == "broker_schwab_v1"
    assert len(r2.events) == 2
    assert all(e.classification_status == "confirmed" for e in r2.events)
    assert sum(e.gross_amount.amount for e in r2.events) == Decimal("1700")
    print("PASS schwab realized G/L: total gain USD", sum(e.gross_amount.amount for e in r2.events))

    merged = merge_schwab_events([r1.events, r2.events])
    cg = [e for e in merged if e.event_type == EventType.CAPITAL_GAIN]
    assert len(cg) == 2, f"expected 2 G/L rows after merge, got {len(cg)}"
    assert all(":gl:" in e.source_row_ref for e in cg)
    print("PASS merge drops inferred Sell when G/L present:", len(merged), "events")

    # Session-style dual upload
    sid = "test-session"
    a = p.parse_path(TX, session_id=sid)
    b = p.parse_path(GL, session_id=sid)
    merged2 = merge_schwab_events([a.events, b.events])
    assert len([e for e in merged2 if e.event_type == EventType.DIVIDEND]) >= 1
    print("PASS dual-file merge")

    # Preamble detection
    text = TX.read_text(encoding="utf-8")
    evs, w, err = parse_schwab_csv(text, "t.csv")
    assert not err
    assert len(evs) >= 4
    print("PASS preamble skip, events=", len(evs))

    print("\nAll Schwab parser checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
