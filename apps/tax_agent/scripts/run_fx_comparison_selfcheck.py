#!/usr/bin/env python3
"""FX multi-scenario comparison self-check."""

from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tax_agent.compute_engine import ComputeEngine
from tax_agent.fx_comparison import TIER_PRIMARY, build_fx_comparison
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
    cmp_ = build_fx_comparison(
        [ev],
        engine=engine,
        snapshot=snapshot,
        provider=provider,
        tax_year=2023,
        primary_policy="cn_supplemental",
        primary_filing_date="2026-04-15",
    )

    scenarios = cmp_.get("scenarios") or []
    if not scenarios:
        failures.append("no scenarios")
    primary = scenarios[0]
    if primary.get("tier") != TIER_PRIMARY:
        failures.append("first scenario not primary")
    if Decimal(primary["netTaxDueCny"]) <= 0:
        failures.append("primary net tax should be positive")

    policies = {s["fxPolicy"] for s in scenarios}
    if "safe_harbor_monthly" not in policies:
        failures.append("missing monthly auxiliary")
    if "cn_supplemental" not in policies:
        failures.append("missing supplemental")

    monthly = cmp_.get("monthlyBreakdown") or []
    if not monthly or monthly[0].get("month") != "2023-07":
        failures.append(f"monthly breakdown unexpected: {monthly}")

    if not primary.get("lateFee", {}).get("applicable"):
        failures.append("primary should have applicable late fee")

    if failures:
        for f in failures:
            print(f"FAIL: {f}")
        return 1
    print("PASS: fx comparison selfcheck ok")
    print(f"  scenarios={len(scenarios)} primary net={primary['netTaxDueCny']}")
    print(f"  monthly rows={len(monthly)} tips={len(cmp_.get('optimizationTips') or [])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
