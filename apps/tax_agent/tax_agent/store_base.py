from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from tax_agent.compute_engine import ComputeResult
from tax_agent.models import TaxEvent
from tax_agent.parser.broker_parser import ParseResult


@dataclass
class StoredDataset:
    dataset_id: str
    session_id: str
    broker_template_id: str
    events: list[TaxEvent]
    data_quality: dict[str, Any]
    file_hashes: list[str] = field(default_factory=list)
    file_names: list[str] = field(default_factory=list)
    detected_headers: list[str] = field(default_factory=list)
    mapping_hints: dict[str, Any] | None = None


@dataclass
class StoredReport:
    run_id: str
    dataset_id: str
    markdown: str
    result_json: dict[str, Any]


@dataclass
class ReviewTicket:
    ticket_id: str
    run_id: str | None
    dataset_id: str | None
    session_id: str | None
    risk_level: str
    reason: str
    status: str
    payload: dict[str, Any]
    created_at: str
    updated_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "ticketId": self.ticket_id,
            "runId": self.run_id,
            "datasetId": self.dataset_id,
            "sessionId": self.session_id,
            "riskLevel": self.risk_level,
            "reason": self.reason,
            "status": self.status,
            "payload": self.payload,
            "createdAt": self.created_at,
            "updatedAt": self.updated_at,
        }


class InMemoryDatasetStore:
    def __init__(self) -> None:
        self._datasets: dict[str, StoredDataset] = {}
        self._reports: dict[str, StoredReport] = {}
        self._tickets: dict[str, ReviewTicket] = {}

    def _post_parse_finalize(self, stored: StoredDataset, parse: ParseResult) -> StoredDataset:
        from tax_agent.futu_session_fifo import append_futu_tax_package, finalize_futu_session_dataset

        append_futu_tax_package(
            stored.data_quality, parse.data_quality, file_hash=parse.file_hash
        )
        if stored.data_quality.get("futuTaxPackages"):
            events, warnings = finalize_futu_session_dataset(stored.events, stored.data_quality)
            stored.events = events
            if warnings:
                stored.data_quality["_futuRematchWarnings"] = warnings
                parse.warnings.extend(warnings)
        return stored

    def save_parse(self, parse: ParseResult) -> StoredDataset:
        stored = StoredDataset(
            dataset_id=parse.dataset_id,
            session_id=parse.session_id,
            broker_template_id=parse.broker_template_id,
            events=list(parse.events),
            data_quality=dict(parse.data_quality),
            file_hashes=[parse.file_hash],
            file_names=[parse.file_name],
            detected_headers=list(parse.detected_headers),
            mapping_hints=parse.mapping_hints,
        )
        stored = self._post_parse_finalize(stored, parse)
        self._datasets[parse.dataset_id] = stored
        return stored

    def merge_into_session(self, session_id: str, parse: ParseResult) -> StoredDataset:
        for ds in self._datasets.values():
            if ds.session_id == session_id:
                ds.events.extend(parse.events)
                ds.file_hashes.append(parse.file_hash)
                ds.file_names.append(parse.file_name)
                parse.dataset_id = ds.dataset_id
                return self._post_parse_finalize(ds, parse)
        return self.save_parse(parse)

    def get(self, dataset_id: str) -> StoredDataset | None:
        return self._datasets.get(dataset_id)

    def apply_column_mapping(
        self,
        dataset_id: str,
        column_mapping: dict[str, str],
    ) -> StoredDataset | None:
        from datetime import datetime, timezone

        from tax_agent.parser.generic_mapped_parser import parse_mapped_rows, quality_report

        ds = self._datasets.get(dataset_id)
        if not ds:
            return None
        raw_rows = (ds.data_quality or {}).get("_rawRows")
        if not raw_rows:
            return None

        file_name = ds.file_names[0] if ds.file_names else "upload.csv"
        events, warnings, errors = parse_mapped_rows(
            raw_rows, column_mapping, file_name=file_name
        )
        if not events:
            return None

        dq = quality_report(events)
        dq["_rawRows"] = raw_rows
        dq["_confirmedMapping"] = column_mapping
        dq["_mappingAppliedAt"] = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        if warnings:
            dq["_mappingWarnings"] = warnings

        ds.events = events
        ds.broker_template_id = "broker_generic_mapped_v1"
        ds.data_quality = dq
        ds.mapping_hints = {
            "suggestedMapping": {
                k: {"header": v, "confidence": 1.0} for k, v in column_mapping.items()
            },
            "confirmed": True,
            "nextSteps": ["列映射已确认，可进行测算。"],
        }
        return ds

    def save_report(
        self,
        run_id: str,
        dataset_id: str,
        markdown: str,
        result: ComputeResult,
    ) -> StoredReport:
        result_json = {
            "runId": result.run_id,
            "ruleSnapshotId": result.rule_snapshot_id,
            "status": result.status,
            "riskLevel": result.risk_level.value,
            "confidenceScore": result.confidence_score,
            "summary": result.summary,
            "lineItems": [ln.to_dict() for ln in result.line_items],
            "auditBundle": result.audit_bundle,
            "triggeredRiskRules": result.triggered_risk_rules,
            "netTaxDueRangeCny": result.net_tax_due_range_cny,
            "notes": result.notes,
            "fxRateSources": result.audit_bundle.get("fxRateSources", []),
            "fxComparison": result.fx_comparison,
            "lateFee": result.late_fee,
            "filingRecommendation": result.filing_recommendation,
        }
        rep = StoredReport(
            run_id=run_id,
            dataset_id=dataset_id,
            markdown=markdown,
            result_json=result_json,
        )
        self._reports[run_id] = rep
        return rep

    def get_report(self, run_id: str) -> StoredReport | None:
        return self._reports.get(run_id)

    def create_review_ticket(
        self,
        *,
        run_id: str | None,
        dataset_id: str | None,
        session_id: str | None,
        risk_level: str = "high",
        reason: str = "",
        payload: dict[str, Any] | None = None,
    ) -> ReviewTicket:
        from datetime import datetime, timezone
        from uuid import uuid4

        from tax_agent.review_workflow import DEFAULT_SLA_HOURS

        now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        pl = dict(payload or {})
        pl.setdefault("slaHours", DEFAULT_SLA_HOURS)
        ticket = ReviewTicket(
            ticket_id=str(uuid4()),
            run_id=run_id,
            dataset_id=dataset_id,
            session_id=session_id,
            risk_level=risk_level,
            reason=reason,
            status="open",
            payload=pl,
            created_at=now,
            updated_at=now,
        )
        self._tickets[ticket.ticket_id] = ticket
        return ticket

    def list_review_tickets(self, status: str | None = None, limit: int = 100) -> list[ReviewTicket]:
        items = sorted(self._tickets.values(), key=lambda t: t.created_at, reverse=True)
        if status:
            items = [t for t in items if t.status == status]
        return items[:limit]

    def get_review_ticket(self, ticket_id: str) -> ReviewTicket | None:
        return self._tickets.get(ticket_id)

    def update_review_ticket_status(self, ticket_id: str, status: str) -> ReviewTicket | None:
        from datetime import datetime, timezone

        ticket = self._tickets.get(ticket_id)
        if not ticket:
            return None
        ticket.status = status
        ticket.updated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        return ticket

    def claim_review_ticket(self, ticket_id: str, reviewer_id: str) -> ReviewTicket | None:
        from tax_agent.review_workflow import claim_ticket

        ticket = self._tickets.get(ticket_id)
        if not ticket:
            return None
        try:
            claim_ticket(ticket, reviewer_id)
        except ValueError:
            return None
        return ticket

    def submit_review_decision(
        self,
        ticket_id: str,
        *,
        decision_type: str,
        notes: str = "",
        reviewer_id: str = "",
        revised_summary: dict[str, Any] | None = None,
        revised_line_items: list[dict[str, Any]] | None = None,
    ) -> ReviewTicket | None:
        from tax_agent.review_workflow import build_expert_review_overlay, submit_decision

        ticket = self._tickets.get(ticket_id)
        if not ticket:
            return None
        try:
            decision = submit_decision(
                ticket,
                decision_type=decision_type,
                notes=notes,
                reviewer_id=reviewer_id,
                revised_summary=revised_summary,
                revised_line_items=revised_line_items,
            )
        except ValueError:
            return None
        if ticket.run_id and decision_type in ("confirm_agent", "revise_amount"):
            rep = self._reports.get(ticket.run_id)
            if rep:
                overlay = build_expert_review_overlay(decision, rep.result_json)
                rep.result_json["expertReview"] = overlay
                if overlay.get("displaySummary"):
                    rep.result_json["summary"] = overlay["displaySummary"]
                if decision.get("revisedLineItems"):
                    rep.result_json["lineItems"] = decision["revisedLineItems"]
        return ticket

    def patch_report_expert_review(self, run_id: str, expert_review: dict[str, Any]) -> bool:
        rep = self._reports.get(run_id)
        if not rep:
            return False
        rep.result_json["expertReview"] = expert_review
        if expert_review.get("displaySummary"):
            rep.result_json["summary"] = expert_review["displaySummary"]
        return True
