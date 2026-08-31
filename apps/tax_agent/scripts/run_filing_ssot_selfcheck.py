#!/usr/bin/env python3
"""Compute engine vs filing_table SSOT — property transfer + classified income per §2.4."""

import os
import sys
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tax_agent.compute_engine import ComputeEngine, ComputeRequest
from tax_agent.filing_table import build_filing_report
from tax_agent.fx import apply_fx_to_events
from tax_agent.fx_rates import FxRateProvider
from tax_agent.futu_session_fifo import finalize_futu_session_dataset
from tax_agent.models import ResidentStatus
from tax_agent.parser.broker_parser import BrokerParser

DOCS = ROOT / "docs"
FIXTURE_ANNUAL = ROOT / "tests" / "fixtures" / "broker" / "futu_tax_2022_annual.xlsx"
FIXTURE_INCOME = ROOT / "tests" / "fixtures" / "broker" / "futu_classified_income_usd.xlsx"
SNAP = ROOT / "rules" / "cn_resident_us_equity" / "snapshots" / "2026.06.01"
Q = Decimal("0.01")


def _line_item(res, cat_id: str):
    for ln in res.line_items:
        if ln.tax_category == cat_id:
            return ln
    return None


def _load_datasets() -> tuple[list, list, dict]:
    paths: list[Path] = []
    if FIXTURE_ANNUAL.is_file():
        paths = [FIXTURE_ANNUAL]
        if not FIXTURE_INCOME.is_file():
            import subprocess

            subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "build_futu_classified_income_fixture.py")],
                check=True,
            )
        if FIXTURE_INCOME.is_file():
            paths.append(FIXTURE_INCOME)
    elif (os.environ.get("TAX_FIXTURE_USE_LOCAL_DOCS") or "").strip() == "1":
        annual = sorted(DOCS.glob("*_Annual_Statement_*.xlsx"))
        paths = list(annual)
    if not paths:
        return [], [], {}

    pkgs: list = []
    events_all = []
    for p in paths:
        pr = BrokerParser(template_id="broker_futu_v1").parse_path(p)
        pkg = (pr.data_quality or {}).get("futuTaxPackage")
        if pkg:
            pkgs.append(pkg)
        events_all.extend(pr.events)

    dq = {"futuTaxPackages": pkgs}
    events, _ = finalize_futu_session_dataset(events_all, dq)
    return events, pkgs, dq


def main() -> int:
    events, pkgs, dq = _load_datasets()
    if not pkgs:
        print("SKIP: need futu_tax_2022 fixtures (or TAX_FIXTURE_USE_LOCAL_DOCS=1)")
        return 0

    provider = FxRateProvider.from_snapshot_dir(SNAP)
    filing = build_filing_report(dq, provider=provider, events=events)
    engine = ComputeEngine()

    failures: list[str] = []
    combined_by_year = {int(r["taxYear"]): r for r in filing.get("combinedRows") or []}

    for row in filing.get("rows") or []:
        year = int(row["taxYear"])
        year_raw = [e for e in events if e.trade_date.startswith(str(year))]
        if not year_raw:
            continue
        year_events = apply_fx_to_events(
            year_raw,
            provider=provider,
            policy="cn_supplemental",
            filing_date=row.get("filingDate"),
            tax_year=year,
        )
        res = engine.compute(
            ComputeRequest(
                events=year_events,
                tax_year=year,
                resident_status=ResidentStatus.CN_TAX_RESIDENT,
                fx_policy="cn_supplemental",
                filing_date=row.get("filingDate"),
                broker_template_id="broker_futu_v1",
                data_quality=dq,
            )
        )
        ft_taxable = Decimal(row["taxableIncomeCny"])
        ce_prop = _line_item(res, "cn_property_transfer")
        ce_taxable = ce_prop.taxable_income_cny if ce_prop else Decimal("0")
        ce_tax = ce_prop.tax_due_cny if ce_prop else Decimal("0")
        ft_tax = Decimal(row["taxDueCny"])
        if abs(ft_taxable - ce_taxable) > Q:
            failures.append(f"{year} property taxable: filing={ft_taxable} compute={ce_taxable}")
        if abs(ft_tax - ce_tax) > Q:
            failures.append(f"{year} property taxDue: filing={ft_tax} compute={ce_tax}")

        combined = combined_by_year.get(year) or {}
        cls = combined.get("classifiedIncome") or {}
        for cat_id, key in (("cn_interest_dividend", "dividend"), ("cn_interest", "interest")):
            seg = cls.get(key)
            ln = _line_item(res, cat_id)
            if not seg and not ln:
                continue
            if bool(seg) != bool(ln):
                failures.append(f"{year} {cat_id}: presence mismatch filing={bool(seg)} compute={bool(ln)}")
                continue
            if not seg or not ln:
                continue
            if abs(Decimal(seg["taxableIncomeCny"]) - ln.taxable_income_cny) > Q:
                failures.append(
                    f"{year} {cat_id} taxable: filing={seg['taxableIncomeCny']} compute={ln.taxable_income_cny}"
                )
            if abs(Decimal(seg["taxDueCny"]) - ln.tax_due_cny) > Q:
                failures.append(
                    f"{year} {cat_id} taxDue: filing={seg['taxDueCny']} compute={ln.tax_due_cny}"
                )

        grand = combined.get("grandTotal") or {}
        if grand:
            ce_net = Decimal(res.summary.get("netTaxDueCny", "0"))
            ft_net = Decimal(grand.get("netTaxDueCny", "0"))
            if abs(ft_net - ce_net) > Q:
                failures.append(f"{year} grand netDue: filing={ft_net} compute={ce_net}")

    if failures:
        for f in failures:
            print("FAIL", f)
        return 1

    n_prop = len(filing.get("rows") or [])
    n_cls = len((filing.get("classifiedIncome") or {}).get("rows") or [])
    print(
        f"PASS filing SSOT: {n_prop} property year(s), {n_cls} classified year(s) "
        "(filing_table + income_summary ≡ compute)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
