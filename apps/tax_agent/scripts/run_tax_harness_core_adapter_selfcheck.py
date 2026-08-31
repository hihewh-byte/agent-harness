#!/usr/bin/env python3
"""Selfcheck: tax ↔ harness_core thin adapter (local sibling required)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def main() -> int:
    from tax_agent.harness_core_adapter import (
        harness_core_available,
        plan_vs_actual_via_core,
        smoke_adapter_roundtrip,
        to_core_plan,
    )
    from tax_agent.harness_plan import build_filing_turn_plan

    if not harness_core_available():
        print("FAIL: harness_core sibling required for tax adapter selfcheck")
        return 1

    plan = build_filing_turn_plan(
        "第一次报税需要什么材料？怎么开始？",
        default_tax_year=2023,
        has_dataset=False,
        has_compute=False,
    )
    core = to_core_plan(plan)
    assert core.profile == plan.profile
    assert "tax_year" in core.domain_meta or "journey_phase" in core.domain_meta

    smoke = smoke_adapter_roundtrip(plan)
    assert smoke["core_phases"][0] == "init"
    assert "plan" in smoke["core_phases"]
    assert "compose" in smoke["core_phases"]  # fast_lane → compose

    diffs = plan_vs_actual_via_core(plan, tools_executed=["invent_fx"])
    assert "tool_not_allowed:invent_fx" in diffs, diffs

    print("PASS run_tax_harness_core_adapter_selfcheck")
    print(f"  profile={core.profile} phases={smoke['core_phases']} meta={core.domain_meta}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
