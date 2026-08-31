#!/usr/bin/env python3
"""Filing date recommendation self-check."""

from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tax_agent.compute_engine import ComputeEngine
from tax_agent.filing_recommendation import build_filing_recommendation
from tax_agent.fx_rates import FxRateProvider
from tax_agent.models import EventType, Money, TaxEvent
from tax_agent.rules_loader import RuleRepository

SNAP = ROOT / "rules" / "cn_resident_us_equity" / "snapshots" / "2026.06.01"


def main() -> int:
    failures: list[str] = []
    provider = FxRateProvider.from_snapshot_dir(SNAP)
    repo = RuleRepository()
    engine = ComputeEngine(repo)
    snapshot = repo.load_snapshot("cn_resident_us_equity@2026.06.01")

    ev = TaxEvent(
        event_type=EventType.CAPITAL_GAIN,
        trade_date="2023-07-15",
        gross_amount=Money(amount=Decimal("153358"), currency="USD"),
    )
    rec = build_filing_recommendation(
        [ev],
        engine=engine,
        snapshot=snapshot,
        provider=provider,
        tax_year=2023,
        primary_policy="cn_supplemental",
        primary_filing_date="2026-04-15",
    )

    if rec.get("status") != "ok":
        failures.append(f"expected status ok got {rec.get('status')}")

    recommended = rec.get("recommended") or {}
    if not recommended.get("filingDate"):
        failures.append("missing recommended filingDate")

    primary_cash = Decimal(rec.get("primaryTotalCashCny", "0"))
    rec_cash = Decimal(recommended.get("totalCashCny", "0"))
    if rec_cash >= primary_cash:
        failures.append(f"recommended {rec_cash} should be less than primary {primary_cash}")

    savings = Decimal(recommended.get("savingsVsPrimaryCny", "0"))
    if savings <= 0:
        failures.append("expected positive savings vs primary")

    if recommended.get("noPenalty") is not True:
        failures.append("earliest supplemental date should have no penalty")

    if (rec.get("scanCount") or 0) < 5:
        failures.append(f"scan count too low: {rec.get('scanCount')}")

    top = rec.get("topCandidates") or []
    if not top or top[0]["filingDate"] != recommended["filingDate"]:
        failures.append("top candidate should match recommended")

    if failures:
        for f in failures:
            print(f"FAIL: {f}")
        return 1
    print("PASS: filing recommendation selfcheck ok")
    print(f"  primary cash={primary_cash} → recommend {recommended['filingDate']} cash={rec_cash} save={savings}")
    print(f"  scan={rec.get('scanCount')} rationale={rec.get('rationale', '')[:80]}…")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
