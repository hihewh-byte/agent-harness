from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class SessionContext:
    session_id: str | None = None
    user_key: str | None = None
    dataset_id: str | None = None
    last_run_id: str | None = None
    tax_year: int = 2024
    resident_status: str = "cn_tax_resident"
    broker_template_id: str | None = None
    event_count: int = 0
    event_counts: dict[str, int] | None = None
    last_summary: dict[str, Any] | None = None
    risk_level: str | None = None
    chat_history: list[dict[str, str]] | None = None
    mapping_hints: dict[str, Any] | None = None
    filing_scope: str = "foreign_only"
    domestic_income_provided: bool = False
    data_quality: dict[str, Any] | None = None
    events: list[Any] | None = None
    tax_insight: dict[str, Any] | None = None
    tax_insight_plan: str | None = None
    fx_provider: Any = None
    fx_policy: str = "cn_supplemental"
    filing_date: str | None = None
    tax_provenance: dict[str, Any] | None = None
    policy_kb_cards: list[dict[str, Any]] | None = None
    last_narrative_polished: bool = False
