#!/usr/bin/env python3
"""Self-check for human-review ticket lifecycle (in-memory + sqlite)."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tax_agent.compute_engine import ComputeResult
from tax_agent.models import RiskLevel
from tax_agent.parser.broker_parser import ParseResult
from tax_agent.store_base import InMemoryDatasetStore
from tax_agent.storage.sqlite_store import SqliteDatasetStore


def _seed_dataset(store, dataset_id: str = "ds-1") -> None:
    if isinstance(store, SqliteDatasetStore) and store.get(dataset_id) is None:
        store.save_parse(
            ParseResult(
                dataset_id=dataset_id,
                session_id="sess-1",
                broker_template_id="broker_ibkr_v1",
                events=[],
                data_quality={},
                file_hash="seed",
                file_name="seed.csv",
            )
        )


def _seed_report(store, run_id: str = "run-1", dataset_id: str = "ds-1") -> None:
    _seed_dataset(store, dataset_id)
    result = ComputeResult(
        run_id=run_id,
        rule_snapshot_id="test_snapshot",
        status="ok",
        risk_level=RiskLevel.HIGH,
        confidence_score=0.6,
        summary={
            "taxableIncomeCny": "10000.00",
            "taxDueCny": "1200.00",
            "netTaxDueCny": "1000.00",
            "foreignTaxPaidCny": "200.00",
            "creditAllowedCny": "200.00",
        },
        line_items=[],
        audit_bundle={},
        disclaimers=[],
        triggered_risk_rules=["R007"],
    )
    store.save_report(run_id, dataset_id, "# test report", result)


def _exercise(store) -> list[str]:
    failures: list[str] = []
    _seed_report(store)

    t = store.create_review_ticket(
        run_id="run-1",
        dataset_id="ds-1",
        session_id="sess-1",
        risk_level="high",
        reason="R007；R009",
        payload={"summary": {"netTaxDueCny": "1000.00"}},
    )
    if not t.ticket_id or t.status != "open":
        failures.append("ticket not created open")

    listed = store.list_review_tickets(status="open")
    if not any(x.ticket_id == t.ticket_id for x in listed):
        failures.append("ticket not listed under open")

    got = store.get_review_ticket(t.ticket_id)
    if got is None or got.reason != "R007；R009":
        failures.append("ticket fetch/reason mismatch")

    claimed = store.claim_review_ticket(t.ticket_id, "expert-01")
    if claimed is None or claimed.status != "claimed":
        failures.append("claim failed or wrong status")
    elif (claimed.payload or {}).get("claimedBy") != "expert-01":
        failures.append("claimedBy not recorded")

    if store.claim_review_ticket(t.ticket_id, "expert-02") is not None:
        failures.append("double claim should fail")

    revised = {
        "taxableIncomeCny": "10000.00",
        "taxDueCny": "1100.00",
        "netTaxDueCny": "900.00",
        "foreignTaxPaidCny": "200.00",
        "creditAllowedCny": "200.00",
    }
    decided = store.submit_review_decision(
        t.ticket_id,
        decision_type="revise_amount",
        notes="调整抵免口径",
        reviewer_id="expert-01",
        revised_summary=revised,
    )
    if decided is None or decided.status != "resolved":
        failures.append("revise_amount decision failed")
    elif (decided.payload or {}).get("decision", {}).get("type") != "revise_amount":
        failures.append("decision payload missing")

    rep = store.get_report("run-1")
    if not rep:
        failures.append("report missing after decision")
    else:
        er = rep.result_json.get("expertReview")
        if not er or er.get("decisionType") != "revise_amount":
            failures.append("expertReview overlay missing")
        if rep.result_json.get("summary", {}).get("netTaxDueCny") != "900.00":
            failures.append("summary not updated from revisedSummary")

    # confirm_agent on a fresh ticket
    t2 = store.create_review_ticket(
        run_id="run-1",
        dataset_id="ds-1",
        session_id="sess-1",
        risk_level="high",
        reason="R009",
    )
    store.claim_review_ticket(t2.ticket_id, "expert-02")
    confirmed = store.submit_review_decision(
        t2.ticket_id,
        decision_type="confirm_agent",
        notes="同意 Agent 结论",
        reviewer_id="expert-02",
    )
    if confirmed is None or confirmed.status != "resolved":
        failures.append("confirm_agent decision failed")

    updated = store.update_review_ticket_status(t.ticket_id, "resolved")
    if updated is None or updated.status != "resolved":
        failures.append("ticket status update failed")

    still_open = store.list_review_tickets(status="open")
    if any(x.ticket_id == t.ticket_id for x in still_open):
        failures.append("resolved ticket still shows as open")

    if store.update_review_ticket_status("nonexistent", "resolved") is not None:
        failures.append("updating missing ticket should return None")
    return failures


def main() -> int:
    failures = _exercise(InMemoryDatasetStore())
    failures = [f"memory: {f}" for f in failures]

    with tempfile.TemporaryDirectory() as d:
        sq = SqliteDatasetStore(db_path=Path(d) / "t.db")
        failures += [f"sqlite: {f}" for f in _exercise(sq)]

    if failures:
        for f in failures:
            print(f"FAIL: {f}")
        return 1
    print("PASS: review ticket selfcheck ok (claim + decision + expertReview)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
