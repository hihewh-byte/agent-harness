#!/usr/bin/env python3
"""PR-C: filing report JSON contract for frontend (combinedRows / classifiedIncome)."""

import sys
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tax_agent.filing_table import build_filing_report
from tax_agent.futu_session_fifo import finalize_futu_session_dataset
from tax_agent.models import EventType
from tax_agent.parser.broker_parser import BrokerParser

ANNUAL = ROOT / "tests" / "fixtures" / "broker" / "futu_tax_2022_annual.xlsx"
INCOME = ROOT / "tests" / "fixtures" / "broker" / "futu_classified_income_usd.xlsx"


def main() -> int:
    if not ANNUAL.is_file() or not INCOME.is_file():
        import subprocess

        subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "build_futu_classified_income_fixture.py")],
            check=False,
        )
    if not ANNUAL.is_file() or not INCOME.is_file():
        print("SKIP: need futu annual + classified income fixtures")
        return 0

    events_all: list = []
    pkgs: list = []
    for p in (ANNUAL, INCOME):
        pr = BrokerParser(template_id="broker_futu_v1").parse_path(p)
        pkg = (pr.data_quality or {}).get("futuTaxPackage")
        if pkg:
            pkgs.append(pkg)
        events_all.extend(pr.events)

    dq = {"futuTaxPackages": pkgs}
    events, _ = finalize_futu_session_dataset(events_all, dq)
    rep = build_filing_report(dq, events=events)

    failures: list[str] = []
    if rep.get("error"):
        failures.append(rep["error"])
    for key in ("rows", "classifiedIncome", "combinedRows", "markdown", "classifiedIncomeNote"):
        if key not in rep:
            failures.append(f"missing key: {key}")

    cls_rows = (rep.get("classifiedIncome") or {}).get("rows") or []
    if not cls_rows:
        failures.append("expected classifiedIncome.rows")
    else:
        row = cls_rows[0]
        if not row.get("dividend") or not row.get("interest"):
            failures.append("classified row missing dividend/interest")
        div = row["dividend"]
        for field in ("grossUsd", "taxableIncomeCny", "netTaxDueCny"):
            if field not in div:
                failures.append(f"dividend missing {field}")

    combined = rep.get("combinedRows") or []
    cr2022 = next((r for r in combined if int(r.get("taxYear", 0)) == 2022), None)
    if not cr2022:
        failures.append("missing combinedRows 2022")
    else:
        gt = cr2022.get("grandTotal") or {}
        if Decimal(gt.get("netTaxDueCny", "0")) <= 0:
            failures.append("grandTotal.netTaxDueCny should be > 0 for fixture")
        if not cr2022.get("propertyTransfer"):
            failures.append("combined row missing propertyTransfer")
        if not cr2022.get("classifiedIncome"):
            failures.append("combined row missing classifiedIncome")

    md = rep.get("markdown") or ""
    if "股息" not in md or "财产转让" not in md:
        failures.append("markdown missing dividend or property section")

    n_div = sum(1 for e in events if e.event_type == EventType.DIVIDEND)
    if n_div < 1:
        failures.append("fixture events missing DIVIDEND")

    if failures:
        for f in failures:
            print("FAIL", f)
        return 1

    print("PASS filing report UI contract (combinedRows + classifiedIncome + markdown)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
