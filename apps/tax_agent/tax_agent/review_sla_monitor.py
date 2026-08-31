"""Review ticket SLA monitoring and webhook notifications."""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from typing import Any

from tax_agent.review_workflow import DEFAULT_SLA_HOURS

ACTIVE_STATUSES = frozenset({"open", "claimed", "in_review"})


def _repo_root():
    from pathlib import Path

    return Path(__file__).resolve().parent.parent


def _state_path():
    from pathlib import Path

    env = os.environ.get("TAX_AGENT_REVIEW_SLA_STATE")
    if env:
        return Path(env)
    d = _repo_root() / ".data"
    d.mkdir(parents=True, exist_ok=True)
    return d / "review_sla_notify.json"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _parse_iso(value: str) -> datetime:
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def sla_hours_for_ticket(ticket: Any) -> int:
    payload = ticket.payload if hasattr(ticket, "payload") else (ticket.get("payload") or {})
    try:
        return max(1, int(payload.get("slaHours") or DEFAULT_SLA_HOURS))
    except (TypeError, ValueError):
        return DEFAULT_SLA_HOURS


def sla_anchor_iso(ticket: Any) -> str:
    payload = ticket.payload if hasattr(ticket, "payload") else (ticket.get("payload") or {})
    if payload.get("claimedAt"):
        return str(payload["claimedAt"])
    return ticket.created_at if hasattr(ticket, "created_at") else str(ticket.get("createdAt") or "")


def compute_sla_view(ticket: Any, *, now: datetime | None = None) -> dict[str, Any]:
    """Return SLA fields for a ticket."""
    now = now or _utc_now()
    hours = sla_hours_for_ticket(ticket)
    anchor = _parse_iso(sla_anchor_iso(ticket))
    deadline = anchor + timedelta(hours=hours)
    remaining = deadline - now
    remaining_hours = round(remaining.total_seconds() / 3600, 2)
    elapsed_hours = round((now - anchor).total_seconds() / 3600, 2)
    progress = min(1.0, max(0.0, elapsed_hours / hours)) if hours else 1.0

    if remaining.total_seconds() <= 0:
        level = "breached"
    elif progress >= 0.8:
        level = "due_soon"
    else:
        level = "on_track"

    ticket_id = ticket.ticket_id if hasattr(ticket, "ticket_id") else ticket.get("ticketId")
    status = ticket.status if hasattr(ticket, "status") else ticket.get("status")
    return {
        "ticketId": ticket_id,
        "status": status,
        "slaHours": hours,
        "anchorAt": anchor.isoformat(),
        "deadlineAt": deadline.isoformat(),
        "remainingHours": remaining_hours,
        "elapsedHours": elapsed_hours,
        "slaLevel": level,
    }


def load_notify_state() -> dict[str, Any]:
    path = _state_path()
    if not path.exists():
        return {"notified": {}, "log": []}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"notified": {}, "log": []}


def save_notify_state(state: dict[str, Any]) -> None:
    path = _state_path()
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def _append_log(state: dict[str, Any], event: dict[str, Any]) -> None:
    log = state.setdefault("log", [])
    log.append({**event, "loggedAt": _utc_now().isoformat()})
    state["log"] = log[-200:]


def deliver_notification(event: dict[str, Any]) -> bool:
    """POST JSON to webhook URL; always append to local notify log."""
    state = load_notify_state()
    _append_log(state, event)
    save_notify_state(state)

    url = (os.environ.get("TAX_AGENT_REVIEW_SLA_WEBHOOK_URL") or "").strip()
    if not url:
        return True
    try:
        import httpx

        headers: dict[str, str] = {"Content-Type": "application/json"}
        token = (os.environ.get("TAX_AGENT_REVIEW_SLA_WEBHOOK_TOKEN") or "").strip()
        if token:
            headers["Authorization"] = f"Bearer {token}"
        r = httpx.post(url, json=event, headers=headers, timeout=10.0)
        return 200 <= r.status_code < 300
    except Exception:
        return False


def _list_active_tickets(store: Any) -> list[Any]:
    if not hasattr(store, "list_review_tickets"):
        return []
    seen: set[str] = set()
    items: list[Any] = []
    for st in sorted(ACTIVE_STATUSES):
        for t in store.list_review_tickets(status=st, limit=200):
            if t.ticket_id not in seen:
                seen.add(t.ticket_id)
                items.append(t)
    return items


def evaluate_review_sla(store: Any, *, now: datetime | None = None) -> list[dict[str, Any]]:
    """Scan active tickets; emit due_soon / breached notifications (deduped)."""
    now = now or _utc_now()
    state = load_notify_state()
    notified: dict[str, dict[str, str]] = state.setdefault("notified", {})
    actions: list[dict[str, Any]] = []

    for ticket in _list_active_tickets(store):
        view = compute_sla_view(ticket, now=now)
        level = view["slaLevel"]
        if level == "on_track":
            continue

        tid = view["ticketId"]
        already = notified.get(tid, {})
        if already.get(level):
            continue

        event = {
            "event": f"review_sla_{level}",
            "ticketId": tid,
            "ticketStatus": view["status"],
            "riskLevel": ticket.risk_level if hasattr(ticket, "risk_level") else None,
            "reason": ticket.reason if hasattr(ticket, "reason") else None,
            "runId": ticket.run_id if hasattr(ticket, "run_id") else None,
            "slaHours": view["slaHours"],
            "deadlineAt": view["deadlineAt"],
            "remainingHours": view["remainingHours"],
        }
        ok = deliver_notification(event)
        notified.setdefault(tid, {})[level] = now.isoformat()
        actions.append({**event, "delivered": ok})

    # Drop notify keys for tickets no longer active
    active_ids = {t.ticket_id for t in _list_active_tickets(store)}
    for tid in list(notified.keys()):
        if tid not in active_ids:
            del notified[tid]

    state["notified"] = notified
    save_notify_state(state)
    return actions


def get_sla_status(store: Any) -> dict[str, Any]:
    now = _utc_now()
    tickets = [compute_sla_view(t, now=now) for t in _list_active_tickets(store)]
    breached = [t for t in tickets if t["slaLevel"] == "breached"]
    due_soon = [t for t in tickets if t["slaLevel"] == "due_soon"]
    state = load_notify_state()
    return {
        "evaluatedAt": now.isoformat(),
        "defaultSlaHours": DEFAULT_SLA_HOURS,
        "webhookConfigured": bool((os.environ.get("TAX_AGENT_REVIEW_SLA_WEBHOOK_URL") or "").strip()),
        "activeCount": len(tickets),
        "breachedCount": len(breached),
        "dueSoonCount": len(due_soon),
        "tickets": tickets,
        "recentNotifications": (state.get("log") or [])[-20:],
    }


def sla_interval_seconds() -> int:
    return max(60, int(os.environ.get("TAX_AGENT_REVIEW_SLA_INTERVAL_SECONDS", "900") or "900"))
