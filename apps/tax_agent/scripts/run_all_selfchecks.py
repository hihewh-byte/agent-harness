#!/usr/bin/env python3
"""Run core tax_agent selfchecks in sequence."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = sys.executable
PREFLIGHT = ROOT / "scripts" / "preflight_ci.py"
SCRIPTS = [
    "run_rule_registry_selfcheck.py",
    "run_rule_publish_monitor_selfcheck.py",
    "run_auth_rbac_selfcheck.py",
    "run_rules_webhook_selfcheck.py",
    "run_feed_builder_selfcheck.py",
    "run_tool_executor_selfcheck.py",
    "run_fx_provider_selfcheck.py",
    "run_fx_filing_rules_selfcheck.py",
    "run_fx_comparison_selfcheck.py",
    "run_late_fee_selfcheck.py",
    "run_filing_recommendation_selfcheck.py",
    "run_review_ticket_selfcheck.py",
    "run_review_sla_selfcheck.py",
    "run_template_mapper_selfcheck.py",
    "run_generic_mapped_selfcheck.py",
    "run_domestic_income_selfcheck.py",
    "run_stock_compensation_selfcheck.py",
    "run_stock_comp_parser_selfcheck.py",
    "run_golden_selfcheck.py",
    "run_cost_basis_selfcheck.py",
    "run_cross_year_fifo_selfcheck.py",
    "run_tax_insight_selfcheck.py",
    "run_tax_provenance_selfcheck.py",
    "run_schwab_parser_selfcheck.py",
    "run_fidelity_parser_selfcheck.py",
    "run_tiger_parser_selfcheck.py",
    "run_futu_parser_selfcheck.py",
    "run_vanguard_parser_selfcheck.py",
    "run_sqlite_persistence_selfcheck.py",
    "run_parser_api_selfcheck.py",
    "run_llm_selfcheck.py",
]


def main() -> int:
    print("=== preflight_ci.py ===")
    pre = subprocess.run([PY, str(PREFLIGHT)], cwd=str(ROOT))
    if pre.returncode != 0:
        return pre.returncode

    failed = 0
    for name in SCRIPTS:
        path = ROOT / "scripts" / name
        print(f"\n=== {name} ===")
        r = subprocess.run([PY, str(path)], cwd=str(ROOT))
        if r.returncode != 0:
            failed += 1
    print(f"\nDone: {len(SCRIPTS) - failed}/{len(SCRIPTS)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
