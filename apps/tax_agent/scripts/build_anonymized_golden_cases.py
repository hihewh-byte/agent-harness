#!/usr/bin/env python3
"""
Build golden compute cases from anonymized broker statement fixtures.

Reads tests/fixtures/broker/*.csv, parses via BrokerParser, applies monthly FX,
runs ComputeEngine, writes tests/fixtures/golden/anonymized_broker/case_*.json
"""

from __future__ import annotations

import json
import sys
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tax_agent.compute_engine import ComputeEngine, ComputeRequest
from tax_agent.event_codec import event_to_dict
from tax_agent.fx import apply_fx_to_events
from tax_agent.fx_rates import FxRateProvider
from tax_agent.models import ResidentStatus
from tax_agent.parser.broker_parser import BrokerParser
from tax_agent.parser.fidelity_parser import merge_fidelity_events
from tax_agent.parser.schwab_parser import merge_schwab_events

BROKER_DIR = ROOT / "tests" / "fixtures" / "broker"
OUT_DIR = ROOT / "tests" / "fixtures" / "golden" / "anonymized_broker"
SNAP = ROOT / "rules" / "cn_resident_us_equity" / "snapshots" / "2026.06.01"
TAX_YEAR = 2024

# (case_id, description, file paths relative to broker dir)
CASES: list[tuple[str, str, list[str]]] = [
    ("broker_schwab", "Schwab transaction history + realized G/L (anonymized)", [
        "schwab_transactions_realistic.csv",
        "schwab_realized_gl.csv",
    ]),
    ("broker_ibkr", "IBKR dividends + trades (anonymized)", [
        "ibkr_dividends.csv",
        "ibkr_trades.csv",
    ]),
    ("broker_fidelity", "Fidelity activity + gains/losses (anonymized)", [
        "fidelity_activity_realistic.csv",
        "fidelity_gains_losses.csv",
    ]),
    ("broker_tiger_trades", "Tiger trades export (anonymized)", ["tiger_trades.csv"]),
    ("broker_tiger_dividends", "Tiger dividends export (anonymized)", ["tiger_dividends.csv"]),
    ("broker_futu", "Futu transaction history (anonymized)", ["futu_transaction_history.csv"]),
    ("broker_vanguard", "Vanguard transaction history (anonymized)", ["vanguard_transaction_history.csv"]),
]


def _merge_events(template_id: str, batches: list[list]) -> list:
    if template_id == "broker_schwab_v1":
        return merge_schwab_events(batches)
    if template_id == "broker_fidelity_v1":
        return merge_fidelity_events(batches)
    out = []
    for b in batches:
        out.extend(b)
    return out


def _build_case(case_id: str, description: str, files: list[str]) -> dict | None:
    parser = BrokerParser()
    batches = []
    template_id = ""
    for fname in files:
        path = BROKER_DIR / fname
        if not path.is_file():
            print(f"skip {case_id}: missing {path}")
            return None
        pr = parser.parse_path(path)
        template_id = pr.broker_template_id
        batches.append(list(pr.events))
    events = _merge_events(template_id, batches)
    if not events:
        print(f"skip {case_id}: no events")
        return None

    provider = FxRateProvider.from_snapshot_dir(SNAP)
    events = apply_fx_to_events(events, provider=provider, policy="safe_harbor_monthly")
    year_events = [e for e in events if e.trade_date.startswith(str(TAX_YEAR))]
    if not year_events:
        print(f"skip {case_id}: no {TAX_YEAR} events")
        return None

    engine = ComputeEngine()
    req = ComputeRequest(
        events=year_events,
        tax_year=TAX_YEAR,
        resident_status=ResidentStatus.CN_TAX_RESIDENT,
        broker_template_id=template_id,
        data_quality={"coverage": {"withholding": 0.9}},
    )
    result = engine.compute(req)

    expected: dict = {
        "riskLevel": result.risk_level.value,
        "confidenceScoreMin": max(0.0, result.confidence_score - 0.05),
    }
    if result.risk_level.value == "high":
        expected["computeOk"] = True
    else:
        expected["summary"] = {
            k: result.summary[k]
            for k in ("taxDueCny", "creditAllowedCny", "netTaxDueCny")
            if k in result.summary
        }
        if result.risk_level.value == "medium":
            expected["allowPartial"] = True

    return {
        "caseId": case_id,
        "description": description,
        "sourceFiles": files,
        "brokerTemplateId": template_id,
        "input": {"events": [event_to_dict(e) for e in year_events]},
        "parameters": {
            "taxYear": TAX_YEAR,
            "residentStatus": "cn_tax_resident",
            "fxPolicy": "safe_harbor_monthly",
            "ruleSnapshotId": "cn_resident_us_equity@2026.06.01",
        },
        "brokerTemplateId": template_id,
        "expected": expected,
    }


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    written = 0
    for case_id, desc, files in CASES:
        case = _build_case(case_id, desc, files)
        if not case:
            continue
        out = OUT_DIR / f"case_{case_id}.json"
        out.write_text(json.dumps(case, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        written += 1
        print(f"wrote {out.name} risk={case['expected']['riskLevel']}")
    print(f"done: {written} anonymized golden cases")
    return 0 if written >= 5 else 1


if __name__ == "__main__":
    raise SystemExit(main())
