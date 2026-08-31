#!/usr/bin/env python3
"""Self-check for date-aware FX rate provider and engine integration."""

from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tax_agent.compute_engine import ComputeEngine, ComputeRequest
from tax_agent.fx import apply_fx_to_events
from tax_agent.fx_rates import FxRateProvider
from tax_agent.models import EventType, Money, ResidentStatus, TaxEvent

SNAP = ROOT / "rules" / "cn_resident_us_equity" / "snapshots" / "2026.06.01"


def _event(date: str, amount: str) -> TaxEvent:
    return TaxEvent(
        event_type=EventType.DIVIDEND,
        trade_date=date,
        gross_amount=Money(Decimal(amount), "USD"),
    )


def main() -> int:
    failures: list[str] = []

    provider = FxRateProvider.from_snapshot_dir(SNAP)
    if provider is None or not provider.available:
        print("FAIL: provider not loaded from snapshot")
        return 1

    # exact monthly
    res = provider.resolve("2024-03-15", "safe_harbor_monthly")
    if res.rate != Decimal("7.0950"):
        failures.append(f"monthly exact wrong: {res.rate}")

    # fallback to prior month
    res2 = provider.resolve("2024-04-30", "safe_harbor_monthly")
    if res2.rate != Decimal("7.1063"):
        failures.append(f"monthly 2024-04 wrong: {res2.rate}")

    # missing month falls back to nearest prior
    res3 = provider.resolve("2024-05-15", "safe_harbor_monthly")
    if res3.rate != Decimal("7.1088"):
        failures.append(f"monthly 2024-05 wrong: {res3.rate}")

    # yearly average (derived from monthly table)
    res4 = provider.resolve("2024-07-01", "safe_harbor_yearly")
    expected_yearly = provider.yearly_average.get("2024")
    if expected_yearly is None or res4.rate != expected_yearly:
        failures.append(f"yearly wrong: {res4.rate} expected {expected_yearly}")

    # apply per-date: two different months -> different rates
    evs = apply_fx_to_events(
        [_event("2024-01-10", "100"), _event("2024-12-20", "100")],
        provider=provider,
        policy="safe_harbor_monthly",
    )
    if evs[0].fx_rate_used == evs[1].fx_rate_used:
        failures.append("per-date rates should differ across months")
    if not evs[0].fx_rate_source:
        failures.append("fx_rate_source not recorded")

    # override beats provider
    ov = apply_fx_to_events(
        [_event("2024-01-10", "100")],
        provider=provider,
        policy="user_override",
        override_rate=Decimal("6.50"),
    )
    if ov[0].fx_rate_used != Decimal("6.50"):
        failures.append("override_rate not applied")

    engine = ComputeEngine()
    events = apply_fx_to_events(
        [TaxEvent(event_type=EventType.DIVIDEND, trade_date="2024-03-01",
                  gross_amount=Money(Decimal("1000"), "USD"))],
        provider=provider,
        policy="safe_harbor_monthly",
    )
    req = ComputeRequest(events=events, tax_year=2024, resident_status=ResidentStatus.CN_TAX_RESIDENT)
    result = engine.compute(req)
    if provider.source == "sample_placeholder":
        if not any("样例" in n for n in result.notes):
            failures.append("sample FX warning note missing")
    elif provider.source.startswith("pboc"):
        if any("样例" in n for n in result.notes):
            failures.append("pboc source should not trigger sample warning")
    if not result.audit_bundle.get("fxRateSources"):
        failures.append("fxRateSources missing from audit bundle")

    if failures:
        for f in failures:
            print(f"FAIL: {f}")
        return 1
    print("PASS: fx provider selfcheck ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
