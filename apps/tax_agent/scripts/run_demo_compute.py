#!/usr/bin/env python3
"""Demo: compute det_001 and print markdown report."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tax_agent.compute_engine import ComputeEngine, ComputeRequest
from tax_agent.models import ResidentStatus, TaxEvent
from tax_agent.report_composer import compose_markdown_report

case_path = ROOT / "tests" / "fixtures" / "golden" / "deterministic" / "case_det_001.json"
case = json.loads(case_path.read_text(encoding="utf-8"))
events = [TaxEvent.from_dict(e) for e in case["input"]["events"]]
params = case["parameters"]
req = ComputeRequest(
    events=events,
    tax_year=params["taxYear"],
    resident_status=ResidentStatus(params["residentStatus"]),
    rule_snapshot_id=params["ruleSnapshotId"],
)
result = ComputeEngine().compute(req)
print(compose_markdown_report(result))
print("\n--- audit ---")
print(json.dumps(result.audit_bundle, ensure_ascii=False, indent=2))
