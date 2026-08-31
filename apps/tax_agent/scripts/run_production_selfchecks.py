#!/usr/bin/env python3
"""Production gate selfchecks (Futu CN resident v1). All must pass before release."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = sys.executable

# Curated for current product: Futu + core tax path. See docs/agent-consensus-v1.md §6.
PRODUCTION_SCRIPTS = [
    "run_filing_ssot_selfcheck.py",
    "run_fx_filing_rules_selfcheck.py",
    "run_fx_provider_selfcheck.py",
    "run_cost_basis_selfcheck.py",
    "run_cross_year_fifo_selfcheck.py",
    "run_futu_parser_selfcheck.py",
    "run_futu_income_summary_selfcheck.py",
    "run_filing_report_contract_selfcheck.py",
    "run_numerics_classified_selfcheck.py",
    "run_tax_provenance_selfcheck.py",
    "run_tax_turn_resolver_selfcheck.py",
    "run_tax_intent_catalog_selfcheck.py",
    "run_harness_tier0_selfcheck.py",
    "run_tax_chat_turn_fsm_selfcheck.py",
    "run_tax_harness_profile_registry_selfcheck.py",
    "run_tax_harness_core_adapter_selfcheck.py",
    "run_tax_harness_golden_run.py",
    "run_chat_experience_selfcheck.py",
    "run_policy_kb_selfcheck.py",
    "run_chat_stream_selfcheck.py",
    "run_filing_journey_coach_selfcheck.py",
    "run_tax_user_profile_selfcheck.py",
    "run_narration_budget_selfcheck.py",
    "run_chat_quality_selfcheck.py",
    "run_phase_b_selfcheck.py",
    "run_phase_c2_selfcheck.py",
    "run_policy_narration_selfcheck.py",
    "run_manual_rubric_selfcheck.py",
    "run_browser_e2e_verify.py",
    "run_tax_insight_selfcheck.py",
    "run_golden_selfcheck.py",
    "run_tool_executor_selfcheck.py",
    "run_harness_p2_selfcheck.py",
    "run_harness_p3_selfcheck.py",
    "run_filing_recommendation_selfcheck.py",
    "run_review_ticket_selfcheck.py",
    "run_auth_rbac_selfcheck.py",
]


def main() -> int:
    print("=== tax_agent production selfchecks ===\n")
    failed = 0
    for name in PRODUCTION_SCRIPTS:
        path = ROOT / "scripts" / name
        print(f"--- {name} ---")
        r = subprocess.run([PY, str(path)], cwd=str(ROOT))
        if r.returncode != 0:
            failed += 1
        print()
    print(f"Production: {len(PRODUCTION_SCRIPTS) - failed}/{len(PRODUCTION_SCRIPTS)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
