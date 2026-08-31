"""Futu tax workbook xlsx parser only."""

from __future__ import annotations

import csv
import hashlib
import io
import re
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from tax_agent.models import EventType, TaxEvent
from tax_agent.parser.mapping_loader import load_mapping
from tax_agent.parser.xlsx_utils import (
    find_header_in_sheet_rows,
    is_futu_tax_workbook,
    load_workbook_sheet_data,
)


@dataclass
class ParseResult:
    dataset_id: str
    session_id: str
    broker_template_id: str
    events: list[TaxEvent]
    data_quality: dict[str, Any]
    file_hash: str
    file_name: str
    warnings: list[str] = field(default_factory=list)
    errors: list[dict[str, Any]] = field(default_factory=list)
    detected_headers: list[str] = field(default_factory=list)
    mapping_hints: dict[str, Any] | None = None


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _normalize_header(h: str) -> str:
    return re.sub(r"\s+", " ", (h or "").strip())


class BrokerParser:
    """Parse Futu Annual_Statement xlsx only."""

    FUTU_TEMPLATE = "broker_futu_v1"

    def __init__(self, template_id: str | None = None) -> None:
        self.template_id = template_id or self.FUTU_TEMPLATE

    def parse_bytes(
        self,
        data: bytes,
        file_name: str,
        session_id: str | None = None,
    ) -> ParseResult:
        sid = session_id or str(uuid4())
        file_hash = _sha256(data)
        lower = file_name.lower()
        if not lower.endswith((".xlsx", ".xls")):
            raise ValueError("仅支持富途税表 xlsx（Annual_Statement）")
        return self._parse_xlsx(data, file_name, sid, file_hash)

    def parse_path(self, path, session_id: str | None = None) -> ParseResult:
        from pathlib import Path

        p = Path(path)
        return self.parse_bytes(p.read_bytes(), p.name, session_id)

    def _parse_xlsx(self, data: bytes, file_name: str, session_id: str, file_hash: str) -> ParseResult:
        try:
            import openpyxl  # noqa: F401
        except ImportError as e:
            raise ImportError("install openpyxl: pip install -e .") from e

        sheet_names, raw_by_sheet = load_workbook_sheet_data(data)
        if not is_futu_tax_workbook(sheet_names):
            raise ValueError(
                "不是富途税表 xlsx。请从富途 App「我的税表」导出 Annual_Statement（含证券-交易流水）。"
            )

        rows_by_sheet: dict[str, list[dict[str, Any]]] = {}
        for name in sheet_names:
            all_rows = raw_by_sheet.get(name) or []
            if not all_rows:
                continue
            found = find_header_in_sheet_rows(all_rows)
            if found:
                header_idx, header_cells = found
            else:
                header_idx = 0
                header_cells = [str(c) if c is not None else "" for c in all_rows[0]]
            headers = [_normalize_header(str(c) if c else "") for c in header_cells if c != ""]
            col_index = {h: i for i, h in enumerate(headers) if h}
            body: list[dict[str, Any]] = []
            for ridx, row in enumerate(all_rows[header_idx + 1 :], start=header_idx + 2):
                if not row or all(c is None or str(c).strip() == "" for c in row):
                    continue
                record = {}
                for h, i in col_index.items():
                    if i < len(row):
                        record[h] = row[i]
                record["__row__"] = ridx
                body.append(record)
            rows_by_sheet[name] = body

        return self._build_futu_from_sheets(
            rows_by_sheet, file_name, session_id, file_hash, [], []
        )

    def _build_futu_from_sheets(
        self,
        rows_by_sheet: dict[str, list[dict[str, Any]]],
        file_name: str,
        session_id: str,
        file_hash: str,
        warnings: list[str],
        errors: list[dict[str, Any]],
    ) -> ParseResult:
        from tax_agent.parser.futu_parser import (
            is_futu_tax_trade_sheet,
            parse_futu_income_summary_rows,
            parse_futu_tax_trades_rows,
        )

        mapping = load_mapping(self.FUTU_TEMPLATE)
        sheet_cfgs = {str(s.get("namePattern")): s for s in (mapping.get("sheets") or [])}
        asset_rows = rows_by_sheet.get("证券-资产进出") or []
        position_rows = rows_by_sheet.get("证券-持仓总览") or []
        account_rows = rows_by_sheet.get("账户信息") or []
        futu_tax_package: dict[str, Any] | None = None
        all_events: list[TaxEvent] = []
        used_tax_fifo = False

        for sheet_name, rows in rows_by_sheet.items():
            if not rows:
                continue
            cfg = sheet_cfgs.get(sheet_name) or {}
            if cfg.get("rowType") == "income_summary" or sheet_name == "股息、利息及其他收入":
                evs, w, e = parse_futu_income_summary_rows(rows, file_name=f"{file_name}:{sheet_name}")
                warnings.extend(w)
                errors.extend(e)
                all_events.extend(evs)
                continue
            if is_futu_tax_trade_sheet(sheet_name, rows):
                evs, w, e, pkg = parse_futu_tax_trades_rows(
                    rows,
                    file_name=f"{file_name}:{sheet_name}",
                    asset_rows=asset_rows,
                    position_rows=position_rows,
                    account_rows=account_rows,
                    file_hash=file_hash,
                )
                if evs or pkg or "交易流水" in sheet_name:
                    warnings.extend(w)
                    errors.extend(e)
                    all_events.extend(evs)
                    if pkg:
                        futu_tax_package = pkg
                    used_tax_fifo = True
                continue
            if sheet_name in ("证券-资产进出", "账户信息", "证券-持仓总览", "证券-资金总览", "证券-资金进出"):
                continue

        if not used_tax_fifo and not all_events:
            warnings.append("futu: 未找到有效交易流水，请确认税表含「证券-交易流水」工作表")

        if used_tax_fifo:
            warnings.append("futu: 已按 FIFO 解析富途税表")
            warnings.append("futu: 跨年卖出请同会话上传买入年至卖出年全部 Annual_Statement")

        quality = self._quality_report(all_events)
        if futu_tax_package:
            quality["futuTaxPackage"] = futu_tax_package

        return ParseResult(
            dataset_id=str(uuid4()),
            session_id=session_id,
            broker_template_id=self.FUTU_TEMPLATE,
            events=all_events,
            data_quality=quality,
            file_hash=file_hash,
            file_name=file_name,
            warnings=warnings,
            errors=errors,
        )

    def _quality_report(self, events: list[TaxEvent]) -> dict[str, Any]:
        counts = {t.value: 0 for t in EventType}
        for e in events:
            counts[e.event_type.value] = counts.get(e.event_type.value, 0) + 1
        total = len(events) or 1
        div = counts.get("DIVIDEND", 0)
        cg = counts.get("CAPITAL_GAIN", 0)
        wh = counts.get("WITHHOLDING_TAX", 0) + sum(
            1 for e in events if e.withholding_tax is not None
        )
        return {
            "totalRows": total,
            "parsedEvents": len(events),
            "coverage": {
                "dividend": min(1.0, div / max(1, div)),
                "capital_gain": min(1.0, cg / max(1, cg)) if cg else 1.0,
                "withholding": min(1.0, wh / max(1, div + counts.get("INTEREST", 0))) if div else 1.0,
            },
            "eventCounts": counts,
        }
