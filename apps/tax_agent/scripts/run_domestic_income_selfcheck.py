#!/usr/bin/env python3
"""Self-check for domestic comprehensive income merge."""

from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tax_agent.compute_engine import ComputeEngine, ComputeRequest
from tax_agent.domestic_income import (
    DomesticIncomeInput,
    comprehensive_gross_cny,
    comprehensive_taxable_cny,
    progressive_tax_cny,
)
from tax_agent.models import ResidentStatus, TaxEvent

CASE = ROOT / "tests" / "fixtures" / "golden" / "deterministic" / "case_det_domestic_merge_001.json"


def main() -> int:
    failures: list[str] = []

    inp = DomesticIncomeInput(wage_salary_cny=Decimal("200000"), withheld_tax_cny=Decimal("10000"))
    taxable = comprehensive_taxable_cny(inp)
    if taxable != Decimal("140000.00"):
        failures.append(f"taxable expected 140000, got {taxable}")
    tax_due, _ = progressive_tax_cny(taxable)
    if tax_due != Decimal("11480.00"):
        failures.append(f"progressive tax expected 11480, got {tax_due}")

    mixed = DomesticIncomeInput(
        author_remuneration_cny=Decimal("10000"),
        royalty_cny=Decimal("5000"),
    )
    gross = comprehensive_gross_cny(mixed)
    if gross != Decimal("9600.00"):
        failures.append(f"author/royalty gross expected 9600, got {gross}")

    import json

    case = json.loads(CASE.read_text(encoding="utf-8"))
    events = [TaxEvent.from_dict(e) for e in case["input"]["events"]]
    params = case["parameters"]
    from tax_agent.domestic_income import parse_domestic_income

    req = ComputeRequest(
        events=events,
        tax_year=2024,
        resident_status=ResidentStatus.CN_TAX_RESIDENT,
        rule_snapshot_id=params["ruleSnapshotId"],
        filing_scope="includes_domestic",
        domestic_income=parse_domestic_income(params["domesticIncome"]),
        data_quality={"coverage": {"withholding": 1.0}},
    )
    result = ComputeEngine().compute(req)
    exp = case["expected"]["summary"]
    for key, val in exp.items():
        got = Decimal(result.summary.get(key, "0"))
        if got != Decimal(val):
            failures.append(f"{key}: got {got} want {val}")

    if "R008" in result.triggered_risk_rules:
        failures.append("R008 should not trigger when domestic income provided")

    cats = [ln.tax_category for ln in result.line_items]
    if "cn_comprehensive_domestic" not in cats:
        failures.append(f"missing domestic line item: {cats}")

    if failures:
        for f in failures:
            print(f"FAIL: {f}")
        return 1
    print("PASS: domestic income merge selfcheck ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
