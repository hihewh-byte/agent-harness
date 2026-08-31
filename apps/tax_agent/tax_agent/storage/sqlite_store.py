from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from typing import Any
from uuid import uuid4

from tax_agent.compute_engine import ComputeResult
from tax_agent.store_base import InMemoryDatasetStore, ReviewTicket, StoredDataset, StoredReport
from tax_agent.event_codec import decode_event, encode_event
from tax_agent.models import TaxEvent
from tax_agent.parser.broker_parser import ParseResult
def _default_db_path() -> Path:
    env = os.environ.get("TAX_AGENT_DB")
    if env:
        return Path(env)
    data_dir = Path(__file__).resolve().parent.parent.parent / ".data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / "tax_agent.db"


class SqliteDatasetStore(InMemoryDatasetStore):
    def __init__(self, db_path: Path | None = None) -> None:
        InMemoryDatasetStore.__init__(self)
        self.db_path = db_path or _default_db_path()
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _init_schema(self) -> None:
        schema = (Path(__file__).parent / "schema_v1.sql").read_text(encoding="utf-8")
        with self._connect() as conn:
            conn.executescript(schema)
            conn.commit()

    def save_parse(self, parse: ParseResult) -> StoredDataset:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT dataset_id FROM tax_dataset WHERE dataset_id = ?",
                (parse.dataset_id,),
            ).fetchone()
            if row:
                return self._load_dataset(conn, parse.dataset_id, extend_parse=parse)

            conn.execute(
                """
                INSERT INTO tax_dataset (dataset_id, session_id, broker_template_id, data_quality_json)
                VALUES (?, ?, ?, ?)
                """,
                (
                    parse.dataset_id,
                    parse.session_id,
                    parse.broker_template_id,
                    json.dumps(self._quality_bundle(parse), ensure_ascii=False),
                ),
            )
            self._insert_parse_rows(conn, parse)
            stored = self._load_dataset(conn, parse.dataset_id)
            stored = self._post_parse_finalize(stored, parse)
            self._persist_dataset(conn, stored)
            conn.commit()
        return self.get(parse.dataset_id)  # type: ignore[return-value]

    def merge_into_session(self, session_id: str, parse: ParseResult) -> StoredDataset:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT dataset_id FROM tax_dataset WHERE session_id = ? ORDER BY created_at LIMIT 1",
                (session_id,),
            ).fetchone()
            if row:
                parse.dataset_id = row["dataset_id"]
                self._insert_parse_rows(conn, parse)
                conn.execute(
                    "UPDATE tax_dataset SET updated_at = datetime('now'), broker_template_id = ? WHERE dataset_id = ?",
                    (parse.broker_template_id, parse.dataset_id),
                )
                stored = self._load_dataset(conn, parse.dataset_id)
                stored = self._post_parse_finalize(stored, parse)
                self._persist_dataset(conn, stored)
                conn.commit()
                return self.get(parse.dataset_id)  # type: ignore[return-value]
        return self.save_parse(parse)

    @staticmethod
    def _quality_bundle(parse: ParseResult) -> dict[str, Any]:
        dq = dict(parse.data_quality)
        if parse.mapping_hints:
            dq["_mappingHints"] = parse.mapping_hints
        if parse.detected_headers:
            dq["_detectedHeaders"] = parse.detected_headers
        return dq

    @staticmethod
    def _split_quality_bundle(dq: dict[str, Any]) -> tuple[dict[str, Any], list[str], dict[str, Any] | None]:
        hints = dq.pop("_mappingHints", None)
        headers = dq.pop("_detectedHeaders", None) or []
        return dq, headers, hints

    def _persist_dataset(self, conn: sqlite3.Connection, stored: StoredDataset) -> None:
        conn.execute("DELETE FROM tax_event_row WHERE dataset_id = ?", (stored.dataset_id,))
        for ev in stored.events:
            conn.execute(
                "INSERT OR REPLACE INTO tax_event_row (event_id, dataset_id, event_json) VALUES (?, ?, ?)",
                (ev.event_id, stored.dataset_id, encode_event(ev)),
            )
        bundle = dict(stored.data_quality)
        if stored.mapping_hints:
            bundle["_mappingHints"] = stored.mapping_hints
        if stored.detected_headers:
            bundle["_detectedHeaders"] = stored.detected_headers
        conn.execute(
            "UPDATE tax_dataset SET data_quality_json = ?, updated_at = datetime('now') WHERE dataset_id = ?",
            (json.dumps(bundle, ensure_ascii=False), stored.dataset_id),
        )

    def _insert_parse_rows(self, conn: sqlite3.Connection, parse: ParseResult) -> None:
        for ev in parse.events:
            conn.execute(
                "INSERT OR REPLACE INTO tax_event_row (event_id, dataset_id, event_json) VALUES (?, ?, ?)",
                (ev.event_id, parse.dataset_id, encode_event(ev)),
            )
        doc_id = str(uuid4())
        conn.execute(
            """
            INSERT INTO tax_document (document_id, dataset_id, file_name, file_hash)
            VALUES (?, ?, ?, ?)
            """,
            (doc_id, parse.dataset_id, parse.file_name, parse.file_hash),
        )

    def _load_dataset(
        self,
        conn: sqlite3.Connection,
        dataset_id: str,
        extend_parse: ParseResult | None = None,
    ) -> StoredDataset:
        if extend_parse:
            self._insert_parse_rows(conn, extend_parse)
        meta = conn.execute(
            "SELECT * FROM tax_dataset WHERE dataset_id = ?", (dataset_id,)
        ).fetchone()
        events = self._load_events(conn, dataset_id)
        docs = conn.execute(
            "SELECT file_name, file_hash FROM tax_document WHERE dataset_id = ?",
            (dataset_id,),
        ).fetchall()
        raw_dq = json.loads(meta["data_quality_json"] or "{}")
        dq, headers, hints = self._split_quality_bundle(raw_dq)
        return StoredDataset(
            dataset_id=dataset_id,
            session_id=meta["session_id"],
            broker_template_id=meta["broker_template_id"],
            events=events,
            data_quality=dq,
            file_hashes=[r["file_hash"] for r in docs],
            file_names=[r["file_name"] for r in docs],
            detected_headers=headers,
            mapping_hints=hints,
        )

    def _load_events(self, conn: sqlite3.Connection, dataset_id: str) -> list[TaxEvent]:
        rows = conn.execute(
            "SELECT event_json FROM tax_event_row WHERE dataset_id = ?",
            (dataset_id,),
        ).fetchall()
        # trade_date inside json — load all then sort
        events = [decode_event(r["event_json"]) for r in rows]
        events.sort(key=lambda e: e.trade_date)
        return events

    def get(self, dataset_id: str) -> StoredDataset | None:
        with self._connect() as conn:
            meta = conn.execute(
                "SELECT dataset_id FROM tax_dataset WHERE dataset_id = ?", (dataset_id,)
            ).fetchone()
            if not meta:
                return None
            return self._load_dataset(conn, dataset_id)

    def apply_column_mapping(
        self,
        dataset_id: str,
        column_mapping: dict[str, str],
    ) -> StoredDataset | None:
        from datetime import datetime, timezone

        from tax_agent.parser.generic_mapped_parser import parse_mapped_rows, quality_report

        ds = self.get(dataset_id)
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
        dq["_mappingHints"] = {
            "suggestedMapping": {
                k: {"header": v, "confidence": 1.0} for k, v in column_mapping.items()
            },
            "confirmed": True,
            "nextSteps": ["列映射已确认，可进行测算。"],
        }

        with self._connect() as conn:
            conn.execute("DELETE FROM tax_event_row WHERE dataset_id = ?", (dataset_id,))
            for ev in events:
                conn.execute(
                    "INSERT OR REPLACE INTO tax_event_row (event_id, dataset_id, event_json) VALUES (?, ?, ?)",
                    (ev.event_id, dataset_id, encode_event(ev)),
                )
            conn.execute(
                """
                UPDATE tax_dataset
                SET broker_template_id = ?, data_quality_json = ?, updated_at = datetime('now')
                WHERE dataset_id = ?
                """,
                (
                    "broker_generic_mapped_v1",
                    json.dumps(dq, ensure_ascii=False),
                    dataset_id,
                ),
            )
            conn.commit()
        return self.get(dataset_id)

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
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO tax_report (run_id, dataset_id, markdown, result_json)
                VALUES (?, ?, ?, ?)
                """,
                (run_id, dataset_id, markdown, json.dumps(result_json, ensure_ascii=False)),
            )
            conn.commit()
        return StoredReport(run_id=run_id, dataset_id=dataset_id, markdown=markdown, result_json=result_json)

    def get_report(self, run_id: str) -> StoredReport | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT run_id, dataset_id, markdown, result_json FROM tax_report WHERE run_id = ?",
                (run_id,),
            ).fetchone()
            if not row:
                return None
            return StoredReport(
                run_id=row["run_id"],
                dataset_id=row["dataset_id"],
                markdown=row["markdown"],
                result_json=json.loads(row["result_json"]),
            )

    def append_chat(self, session_id: str, role: str, content: str, meta: dict | None = None) -> str:
        mid = str(uuid4())
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO chat_message (message_id, session_id, role, content, meta_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (mid, session_id, role, content, json.dumps(meta or {}, ensure_ascii=False)),
            )
            conn.commit()
        return mid

    def _row_to_ticket(self, r: sqlite3.Row) -> ReviewTicket:
        return ReviewTicket(
            ticket_id=r["ticket_id"],
            run_id=r["run_id"],
            dataset_id=r["dataset_id"],
            session_id=r["session_id"],
            risk_level=r["risk_level"],
            reason=r["reason"],
            status=r["status"],
            payload=json.loads(r["payload_json"] or "{}"),
            created_at=r["created_at"],
            updated_at=r["updated_at"],
        )

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
        from tax_agent.review_workflow import DEFAULT_SLA_HOURS

        tid = str(uuid4())
        pl = dict(payload or {})
        pl.setdefault("slaHours", DEFAULT_SLA_HOURS)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO review_ticket
                    (ticket_id, run_id, dataset_id, session_id, risk_level, reason, status, payload_json)
                VALUES (?, ?, ?, ?, ?, ?, 'open', ?)
                """,
                (
                    tid,
                    run_id,
                    dataset_id,
                    session_id,
                    risk_level,
                    reason,
                    json.dumps(pl, ensure_ascii=False),
                ),
            )
            conn.commit()
            row = conn.execute("SELECT * FROM review_ticket WHERE ticket_id = ?", (tid,)).fetchone()
        return self._row_to_ticket(row)

    def list_review_tickets(self, status: str | None = None, limit: int = 100) -> list[ReviewTicket]:
        with self._connect() as conn:
            if status:
                rows = conn.execute(
                    "SELECT * FROM review_ticket WHERE status = ? ORDER BY created_at DESC LIMIT ?",
                    (status, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM review_ticket ORDER BY created_at DESC LIMIT ?",
                    (limit,),
                ).fetchall()
        return [self._row_to_ticket(r) for r in rows]

    def get_review_ticket(self, ticket_id: str) -> ReviewTicket | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM review_ticket WHERE ticket_id = ?", (ticket_id,)
            ).fetchone()
        return self._row_to_ticket(row) if row else None

    def update_review_ticket_status(self, ticket_id: str, status: str) -> ReviewTicket | None:
        with self._connect() as conn:
            cur = conn.execute(
                "UPDATE review_ticket SET status = ?, updated_at = datetime('now') WHERE ticket_id = ?",
                (status, ticket_id),
            )
            conn.commit()
            if cur.rowcount == 0:
                return None
            row = conn.execute(
                "SELECT * FROM review_ticket WHERE ticket_id = ?", (ticket_id,)
            ).fetchone()
        return self._row_to_ticket(row) if row else None

    def claim_review_ticket(self, ticket_id: str, reviewer_id: str) -> ReviewTicket | None:
        from tax_agent.review_workflow import claim_ticket

        ticket = self.get_review_ticket(ticket_id)
        if not ticket:
            return None
        try:
            claim_ticket(ticket, reviewer_id)
        except ValueError:
            return None
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE review_ticket
                SET status = ?, payload_json = ?, updated_at = datetime('now')
                WHERE ticket_id = ?
                """,
                (ticket.status, json.dumps(ticket.payload, ensure_ascii=False), ticket_id),
            )
            conn.commit()
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

        ticket = self.get_review_ticket(ticket_id)
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
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE review_ticket
                SET status = ?, payload_json = ?, updated_at = datetime('now')
                WHERE ticket_id = ?
                """,
                (ticket.status, json.dumps(ticket.payload, ensure_ascii=False), ticket_id),
            )
            if ticket.run_id and decision_type in ("confirm_agent", "revise_amount"):
                row = conn.execute(
                    "SELECT result_json FROM tax_report WHERE run_id = ?", (ticket.run_id,)
                ).fetchone()
                if row:
                    result_json = json.loads(row["result_json"])
                    overlay = build_expert_review_overlay(decision, result_json)
                    result_json["expertReview"] = overlay
                    if overlay.get("displaySummary"):
                        result_json["summary"] = overlay["displaySummary"]
                    if decision.get("revisedLineItems"):
                        result_json["lineItems"] = decision["revisedLineItems"]
                    conn.execute(
                        "UPDATE tax_report SET result_json = ? WHERE run_id = ?",
                        (json.dumps(result_json, ensure_ascii=False), ticket.run_id),
                    )
            conn.commit()
        return ticket

    def list_chat(self, session_id: str, limit: int = 50) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT role, content, meta_json, created_at FROM chat_message
                WHERE session_id = ? ORDER BY created_at DESC LIMIT ?
                """,
                (session_id, limit),
            ).fetchall()
        out = []
        for r in reversed(rows):
            out.append(
                {
                    "role": r["role"],
                    "content": r["content"],
                    "meta": json.loads(r["meta_json"] or "{}"),
                    "createdAt": r["created_at"],
                }
            )
        return out


def get_store() -> SqliteDatasetStore | InMemoryDatasetStore:
    from tax_agent.store_singleton import get_app_store

    return get_app_store()
