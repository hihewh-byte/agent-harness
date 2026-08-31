"""Expert review ticket workflow — claim, decision, report overlay."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

VALID_DECISION_TYPES = frozenset(
    {"confirm_agent", "revise_amount", "reject_compute", "refer_to_authority"}
)
VALID_STATUSES = frozenset(
    {"open", "claimed", "in_review", "resolved", "escalated", "cancelled"}
)
DEFAULT_SLA_HOURS = 48


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def claim_ticket(ticket: Any, reviewer_id: str) -> None:
    if ticket.status not in ("open",):
        raise ValueError(f"cannot claim ticket in status {ticket.status}")
    ticket.status = "claimed"
    ticket.payload = dict(ticket.payload or {})
    ticket.payload["claimedBy"] = reviewer_id
    ticket.payload["claimedAt"] = _utc_now()
    ticket.payload.setdefault("slaHours", DEFAULT_SLA_HOURS)
    ticket.updated_at = _utc_now()


def submit_decision(
    ticket: Any,
    *,
    decision_type: str,
    notes: str = "",
    reviewer_id: str = "",
    revised_summary: dict[str, Any] | None = None,
    revised_line_items: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if decision_type not in VALID_DECISION_TYPES:
        raise ValueError(f"invalid decisionType: {decision_type}")
    if ticket.status not in ("claimed", "in_review", "open"):
        raise ValueError(f"cannot decide ticket in status {ticket.status}")

    decision: dict[str, Any] = {
        "type": decision_type,
        "notes": notes,
        "reviewerId": reviewer_id,
        "decidedAt": _utc_now(),
    }
    if revised_summary:
        decision["revisedSummary"] = revised_summary
    if revised_line_items:
        decision["revisedLineItems"] = revised_line_items

    ticket.payload = dict(ticket.payload or {})
    ticket.payload["decision"] = decision
    ticket.status = "resolved" if decision_type != "refer_to_authority" else "escalated"
    ticket.updated_at = _utc_now()
    return decision


def build_expert_review_overlay(
    decision: dict[str, Any],
    original_result: dict[str, Any],
) -> dict[str, Any]:
    """Build expertReview block stored on report result_json."""
    overlay: dict[str, Any] = {
        "decisionType": decision.get("type"),
        "notes": decision.get("notes"),
        "reviewerId": decision.get("reviewerId"),
        "decidedAt": decision.get("decidedAt"),
        "originalSummary": original_result.get("summary"),
    }
    if decision.get("type") == "revise_amount" and decision.get("revisedSummary"):
        overlay["revisedSummary"] = decision["revisedSummary"]
        overlay["displaySummary"] = decision["revisedSummary"]
    elif decision.get("type") == "confirm_agent":
        overlay["displaySummary"] = original_result.get("summary")
    if decision.get("revisedLineItems"):
        overlay["revisedLineItems"] = decision["revisedLineItems"]
    return overlay
