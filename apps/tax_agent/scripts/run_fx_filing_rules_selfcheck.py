#!/usr/bin/env python3
"""Compliance FX filing rules self-check."""

from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tax_agent.fx import apply_fx_to_events
from tax_agent.fx_filing_rules import (
    prior_month_key,
    resolve_filing_month_key,
    supplemental_month_key_for_tax_year,
)
from tax_agent.fx_rates import FxRateProvider
from tax_agent.models import EventType, Money, TaxEvent

SNAP = ROOT / "rules" / "cn_resident_us_equity" / "snapshots" / "2026.06.01"


def main() -> int:
    failures: list[str] = []
    provider = FxRateProvider.from_snapshot_dir(SNAP)
    assert provider

    if prior_month_key(__import__("datetime").date(2026, 4, 15)) != "2026-03":
        failures.append("prior_month_key April")

    # 补缴 2021 年度 → 上一纳税年度 2020-12（与办理年 2026 无关）
    if supplemental_month_key_for_tax_year(2021) != "2020-12":
        failures.append("supplemental month for tax_year 2021")

    mk, label = resolve_filing_month_key("cn_supplemental", "2026-04-15", tax_year=2021)
    if mk != "2020-12":
        failures.append(f"2021 supplemental month key {mk}")
    if "2020-12-31" not in label:
        failures.append(f"label missing 2020-12-31: {label}")

    res = provider.resolve_filing("cn_supplemental", "2026-04-15", tax_year=2021)
    if res.rate != Decimal("6.5249"):
        failures.append(f"2021 supplemental expected 6.5249 got {res.rate}")

    # 补缴 2023 → 2022-12
    res23 = provider.resolve_filing("cn_supplemental", "2026-04-15", tax_year=2023)
    if res23.rate != Decimal("6.9646"):
        failures.append(f"2023 supplemental expected 6.9646 got {res23.rate}")

    ev = TaxEvent(
        event_type=EventType.CAPITAL_GAIN,
        trade_date="2021-07-01",
        gross_amount=Money(amount=Decimal("1000"), currency="USD"),
    )
    out = apply_fx_to_events(
        [ev],
        provider=provider,
        policy="cn_supplemental",
        filing_date="2026-04-15",
        tax_year=2021,
    )
    if out[0].amount_cny != Decimal("6524.90"):
        failures.append(f"2021 FX cny expected 6524.90 got {out[0].amount_cny}")

    annual = provider.resolve_filing("cn_annual_filing", "2026-04-15")
    if "2026-03" not in annual.note:
        failures.append(f"annual filing note missing 2026-03: {annual.note}")

    if failures:
        for f in failures:
            print(f"FAIL: {f}")
        return 1
    print("PASS: fx filing rules selfcheck ok")
    print(f"  supplemental tax_year=2021 → rate {res.rate} (2020-12)")
    print(f"  supplemental tax_year=2023 → rate {res23.rate} (2022-12)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
