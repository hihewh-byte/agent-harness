#!/usr/bin/env python3
"""Classified income (dividend/interest) SSOT — income_summary ≡ compute_engine line items."""

import sys
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tax_agent.compute_engine import ComputeEngine, ComputeRequest
from tax_agent.fx import apply_fx_to_events
from tax_agent.fx_rates import FxRateProvider
from tax_agent.income_summary import build_classified_income_rows
from tax_agent.models import EventType, ResidentStatus
from tax_agent.parser.broker_parser import BrokerParser

FIXTURE = ROOT / "tests" / "fixtures" / "broker" / "futu_classified_income_usd.xlsx"
LEGACY_FIXTURE = ROOT / "tests" / "fixtures" / "broker" / "futu_tax_2022_income_summary.xlsx"
SNAP = ROOT / "rules" / "cn_resident_us_equity" / "snapshots" / "2026.06.01"
Q = Decimal("0.01")


def _line_item(res, cat_id: str):
    for ln in res.line_items:
        if ln.tax_category == cat_id:
            return ln
    return None


def main() -> int:
    fixture = FIXTURE
    if not fixture.is_file():
        import subprocess

        subprocess.run([sys.executable, str(ROOT / "scripts" / "build_futu_classified_income_fixture.py")], check=True)
    if not fixture.is_file():
        print(f"SKIP: missing {fixture}")
        return 0

    pr = BrokerParser(template_id="broker_futu_v1").parse_path(fixture)
    events = [e for e in pr.events if e.event_type in (EventType.DIVIDEND, EventType.INTEREST, EventType.WITHHOLDING_TAX)]
    if not events:
        print("SKIP: no dividend/interest events in fixture")
        return 0

    provider = FxRateProvider.from_snapshot_dir(SNAP)
    years = sorted({int(e.trade_date[:4]) for e in events})
    failures: list[str] = []

    for year in years:
        year_raw = [e for e in pr.events if e.trade_date.startswith(str(year))]
        year_events = apply_fx_to_events(
            year_raw,
            provider=provider,
            policy="cn_supplemental",
            tax_year=year,
        )
        rows, _ = build_classified_income_rows(year_events, provider=provider, years=[year])
        if not rows:
            failures.append(f"{year}: no classified income rows")
            continue
        row = rows[0]
        res = ComputeEngine().compute(
            ComputeRequest(
                events=year_events,
                tax_year=year,
                resident_status=ResidentStatus.CN_TAX_RESIDENT,
                fx_policy="cn_supplemental",
                broker_template_id="broker_futu_v1",
            )
        )
        for cat_id, seg in (
            ("cn_interest_dividend", row.dividend),
            ("cn_interest", row.interest),
        ):
            if not seg or not seg.event_count:
                continue
            ln = _line_item(res, cat_id)
            if not ln:
                failures.append(f"{year} {cat_id}: missing compute line")
                continue
            if abs(seg.taxable_cny - ln.taxable_income_cny) > Q:
                failures.append(
                    f"{year} {cat_id} taxable: summary={seg.taxable_cny} compute={ln.taxable_income_cny}"
                )
            if abs(seg.tax_due_cny - ln.tax_due_cny) > Q:
                failures.append(
                    f"{year} {cat_id} taxDue: summary={seg.tax_due_cny} compute={ln.tax_due_cny}"
                )
            if abs(seg.net_tax_due_cny - ln.net_tax_due_cny) > Q:
                failures.append(
                    f"{year} {cat_id} netDue: summary={seg.net_tax_due_cny} compute={ln.net_tax_due_cny}"
                )

    if failures:
        for f in failures:
            print("FAIL", f)
        return 1

    print(f"PASS classified income SSOT: {len(years)} year(s) aligned (income_summary ≡ compute)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
