#!/usr/bin/env python3
"""Self-check for review ticket SLA monitor + notifications."""

from __future__ import annotations

import os
import sys
import tempfile
from datetime import timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tax_agent import review_sla_monitor as sla
from tax_agent.store_base import InMemoryDatasetStore
from tax_agent.storage.sqlite_store import SqliteDatasetStore


def _backdate_created(store, ticket_id: str, hours_ago: float, now) -> None:
    iso = (now - timedelta(hours=hours_ago)).strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(store, SqliteDatasetStore):
        with store._connect() as conn:
            conn.execute(
                "UPDATE review_ticket SET created_at = ? WHERE ticket_id = ?",
                (iso, ticket_id),
            )
            conn.commit()
        return
    if isinstance(store, InMemoryDatasetStore):
        t = store.get_review_ticket(ticket_id)
        if t:
            t.created_at = iso
        return
    with store._connect() as conn:
        conn.execute(
            "UPDATE review_ticket SET created_at = ? WHERE ticket_id = ?",
            (iso, ticket_id),
        )
        conn.commit()


def _exercise(store, label: str) -> list[str]:
    failures: list[str] = []
    now = sla._utc_now()

    t_due = store.create_review_ticket(
        run_id="run-due",
        dataset_id="ds-1",
        session_id="sess-1",
        reason="R007",
        payload={"slaHours": 48},
    )
    _backdate_created(store, t_due.ticket_id, 40, now)
    t_due = store.get_review_ticket(t_due.ticket_id)

    t_breach = store.create_review_ticket(
        run_id="run-breach",
        dataset_id="ds-2",
        session_id="sess-2",
        reason="R009",
        payload={"slaHours": 48},
    )
    _backdate_created(store, t_breach.ticket_id, 50, now)
    t_breach = store.get_review_ticket(t_breach.ticket_id)

    view_due = sla.compute_sla_view(t_due, now=now)
    view_breach = sla.compute_sla_view(t_breach, now=now)
    if view_due["slaLevel"] != "due_soon":
        failures.append(f"{label}: expected due_soon, got {view_due['slaLevel']}")
    if view_breach["slaLevel"] != "breached":
        failures.append(f"{label}: expected breached, got {view_breach['slaLevel']}")

    actions = sla.evaluate_review_sla(store, now=now)
    events = {a["event"] for a in actions}
    if "review_sla_due_soon" not in events:
        failures.append(f"{label}: missing due_soon notification")
    if "review_sla_breached" not in events:
        failures.append(f"{label}: missing breached notification")

    actions2 = sla.evaluate_review_sla(store, now=now)
    if actions2:
        failures.append(f"{label}: duplicate notifications on second evaluate: {actions2}")

    st = sla.get_sla_status(store)
    if st.get("breachedCount", 0) < 1 or st.get("dueSoonCount", 0) < 1:
        failures.append(f"{label}: sla status counts wrong: {st}")

    store.submit_review_decision(
        t_breach.ticket_id,
        decision_type="confirm_agent",
        notes="done",
        reviewer_id="expert",
    )
    sla.evaluate_review_sla(store, now=now)
    state = sla.load_notify_state()
    if t_breach.ticket_id in state.get("notified", {}):
        failures.append(f"{label}: resolved ticket still in notified map")

    return failures


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["TAX_AGENT_REVIEW_SLA_STATE"] = str(Path(tmp) / "sla.json")
        os.environ.pop("TAX_AGENT_REVIEW_SLA_WEBHOOK_URL", None)

        failures = _exercise(InMemoryDatasetStore(), "memory")
        with tempfile.TemporaryDirectory() as d:
            failures += _exercise(SqliteDatasetStore(Path(d) / "t.db"), "sqlite")

    if failures:
        for f in failures:
            print(f"FAIL: {f}")
        return 1
    print("PASS: review SLA selfcheck ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
