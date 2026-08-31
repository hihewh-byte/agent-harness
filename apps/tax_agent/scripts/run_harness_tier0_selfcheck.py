#!/usr/bin/env python3
"""P5: harness_tier0_assembly protected SLA."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tax_agent.harness_plan import FilingTurnPlan
from tax_agent.harness_tier0_assembly import assemble_filing_ledger


def main() -> int:
    plan = FilingTurnPlan(
        profile="filing_narrative",
        focus="narrative",
        tax_year=2023,
        journey_phase="reviewing",
        slots_tier0=("FILING_TABLE_AUTHORITY", "NUMERICS_MANIFEST", "RISK_BRIEF", "TASK"),
        slots_tier1=(),
        forbidden=(),
        tools_allowed=(),
        task_text="润色",
    )
    big_risk = "【风险】" + ("x" * 5000)
    table = "【FILING_TABLE_AUTHORITY】" + ("9" * 800)
    manifest = "【NUMERICS_MANIFEST】" + ("1" * 400)
    ledger, asm, integrity = assemble_filing_ledger(
        [
            ("FILING_TABLE_AUTHORITY", table),
            ("NUMERICS_MANIFEST", manifest),
            ("RISK_BRIEF", big_risk),
        ],
        plan,
        budget=1200,
    )
    assert "FILING_TABLE_AUTHORITY" in ledger or "9" in ledger
    assert "NUMERICS" in ledger or "1" in ledger
    assert len(ledger) <= 1300
    assert integrity.get("assertions")
    assert "assert:filing_table_authority_required" in integrity["assertions"]
    assert not any(e.startswith("protected_slot_dropped:") for e in integrity.get("errors") or [])
    print("PASS protected SLA keeps filing + numerics under budget")
    print(f"PASS tier0_integrity assertions={integrity.get('assertions')}")

    plan2 = FilingTurnPlan(
        profile="general",
        focus="general",
        tax_year=2022,
        journey_phase="ready",
        slots_tier0=("MASTER_ANCHOR", "FILING_SNAPSHOT", "TASK"),
        slots_tier1=(),
        forbidden=(),
        tools_allowed=(),
        task_text="",
    )
    out, _, integrity2 = assemble_filing_ledger(
        [("MASTER_ANCHOR", "锚点"), ("FILING_SNAPSHOT", "快照" * 200)],
        plan2,
        budget=200,
    )
    assert len(out) <= 250
    assert "budget_limit" in integrity2
    print("PASS general profile degrades under budget")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
