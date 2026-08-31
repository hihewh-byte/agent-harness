#!/usr/bin/env python3
"""Run golden fixture suite against ComputeEngine."""

from __future__ import annotations

import json
import sys
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tax_agent.compute_engine import ComputeEngine, ComputeRequest
from tax_agent.domestic_income import parse_domestic_income
from tax_agent.models import ResidentStatus, RiskLevel, TaxEvent

GOLDEN = ROOT / "tests" / "fixtures" / "golden"
Q = Decimal("0.01")


def load_cases() -> list[tuple[Path, dict]]:
    cases: list[tuple[Path, dict]] = []
    for sub in (
        "deterministic",
        "missing_data",
        "ambiguous",
        "credit_edge",
        "high_risk",
        "anonymized_broker",
    ):
        d = GOLDEN / sub
        if not d.exists():
            continue
        for p in sorted(d.glob("case_*.json")):
            cases.append((p, json.loads(p.read_text(encoding="utf-8"))))
    return cases


def run_case(engine: ComputeEngine, case: dict) -> tuple[bool, str]:
    params = case.get("parameters") or {}
    events = [TaxEvent.from_dict(e) for e in case["input"]["events"]]
    dq = case.get("dataQuality") or {"coverage": {"withholding": 1.0}}
    req = ComputeRequest(
        events=events,
        tax_year=int(params.get("taxYear", 2024)),
        resident_status=ResidentStatus(params.get("residentStatus", "cn_tax_resident")),
        rule_snapshot_id=params.get("ruleSnapshotId", "latest_stable"),
        fx_policy=params.get("fxPolicy", "safe_harbor_monthly"),
        filing_scope=params.get("filingScope", "foreign_only"),
        domestic_income=parse_domestic_income(params.get("domesticIncome")),
        data_quality=dq,
        broker_template_id=case.get("brokerTemplateId", "broker_ibkr_v1"),
        declared_account_count=case.get("declaredAccountCount"),
        parsed_account_count=case.get("parsedAccountCount", 1),
    )
    result = engine.compute(req)
    exp = case.get("expected") or {}

    if exp.get("riskLevel"):
        if result.risk_level.value != exp["riskLevel"]:
            return False, f"risk {result.risk_level.value} != {exp['riskLevel']}"

    if exp.get("riskLevel") == "high":
        if exp.get("allowDraftCompute"):
            if not result.line_items:
                return False, "draft high risk should emit line items"
            if "summary" in exp:
                for key in ("taxDueCny", "creditAllowedCny", "netTaxDueCny", "taxableIncomeCny"):
                    if key not in exp["summary"]:
                        continue
                    got = Decimal(result.summary.get(key, "0"))
                    want = Decimal(exp["summary"][key])
                    if got != want:
                        return False, f"{key}: got {got} want {want}"
            return True, "ok"
        if result.line_items:
            return False, "high risk should not emit line items"
        return True, "ok"

    if exp.get("allowPartial") and result.risk_level == RiskLevel.MEDIUM:
        return True, "ok"

    if "summary" not in exp:
        if exp.get("computeOk"):
            return (result.status in ("success", "partial"), result.status)
        return True, "ok"

    for key in ("taxDueCny", "creditAllowedCny", "netTaxDueCny"):
        if key not in exp["summary"]:
            continue
        got = Decimal(result.summary.get(key, "0"))
        want = Decimal(exp["summary"][key])
        if abs(got - want) > Q:
            return False, f"{key}: got {got} want {want}"

    if exp.get("confidenceScoreMin") is not None:
        if result.confidence_score < float(exp["confidenceScoreMin"]):
            return False, f"confidence {result.confidence_score} too low"

    return True, "ok"


def main() -> int:
    if not list(GOLDEN.glob("**/case_*.json")):
        print("No cases found; run scripts/generate_golden_cases.py first")
        return 1

    engine = ComputeEngine()
    cases = load_cases()
    failed = 0
    for path, case in cases:
        ok, msg = run_case(engine, case)
        status = "PASS" if ok else "FAIL"
        print(f"{status} {path.name}: {msg}")
        if not ok:
            failed += 1

    print(f"\nTotal {len(cases)} cases, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
