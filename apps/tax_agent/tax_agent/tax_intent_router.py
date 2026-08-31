"""Deterministic intent routing — facade over harness_plan.FilingTurnPlan."""

from __future__ import annotations

from tax_agent.harness_plan import FilingTurnPlan, build_filing_turn_plan
from tax_agent.chat_orchestrator import infer_tax_year

# 向后兼容
TaxInsightPlan = FilingTurnPlan


def resolve_tax_intent(
    message: str,
    *,
    default_tax_year: int,
    has_dataset: bool = False,
    has_compute: bool = False,
) -> FilingTurnPlan:
    return build_filing_turn_plan(
        message,
        default_tax_year=default_tax_year,
        has_dataset=has_dataset,
        has_compute=has_compute,
    )


__all__ = [
    "TaxInsightPlan",
    "FilingTurnPlan",
    "resolve_tax_intent",
    "infer_tax_year",
]
