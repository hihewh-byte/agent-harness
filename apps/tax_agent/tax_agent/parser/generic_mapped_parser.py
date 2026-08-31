"""Parse CSV rows using user-confirmed column mapping (template_unknown fallback)."""

from __future__ import annotations

import re
from decimal import Decimal
from typing import Any

from tax_agent.models import EventType, Money, TaxEvent
from tax_agent.parser.stock_comp_detect import compose_row_blob, infer_stock_comp_kind, tag_event_if_stock_comp

# Raw type cell -> EventType
_TYPE_MAP: dict[str, EventType] = {
    "sell": EventType.CAPITAL_GAIN,
    "sale": EventType.CAPITAL_GAIN,
    "trade": EventType.CAPITAL_GAIN,
    "buy": EventType.CAPITAL_GAIN,
    "capital gain": EventType.CAPITAL_GAIN,
    "realized": EventType.CAPITAL_GAIN,
    "dividend": EventType.DIVIDEND,
    "dividends": EventType.DIVIDEND,
    "interest": EventType.INTEREST,
    "tax": EventType.WITHHOLDING_TAX,
    "withholding": EventType.WITHHOLDING_TAX,
    "nra tax": EventType.WITHHOLDING_TAX,
    "fee": EventType.FEE,
    "commission": EventType.FEE,
    "comm": EventType.FEE,
}


def _norm(h: str) -> str:
    return re.sub(r"\s+", " ", (h or "").strip())


def _parse_decimal(val: Any) -> Decimal | None:
    if val is None or val == "":
        return None
    s = str(val).strip().replace(",", "").replace("$", "")
    if not s or s in ("-", "N/A"):
        return None
    if s.startswith("(") and s.endswith(")"):
        s = "-" + s[1:-1]
    try:
        return Decimal(s)
    except Exception:
        return None


def _parse_date(val: Any) -> str | None:
    if not val:
        return None
    from datetime import datetime

    s = str(val).strip()
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%Y/%m/%d", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(s[:19], fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _resolve_event_type(type_raw: str | None, amount: Decimal | None) -> EventType:
    if type_raw:
        key = _norm(type_raw).lower()
        if key in _TYPE_MAP:
            return _TYPE_MAP[key]
        for token, et in _TYPE_MAP.items():
            if token in key:
                return et
    if amount is not None and amount < 0:
        return EventType.FEE
    return EventType.CAPITAL_GAIN


def _row_value(row: dict[str, Any], header: str | None) -> Any:
    if not header:
        return None
    nh = _norm(header)
    for k, v in row.items():
        if k == "__row__":
            continue
        if _norm(str(k)) == nh:
            return v
    return None


def parse_mapped_rows(
    rows: list[dict[str, Any]],
    column_mapping: dict[str, str],
    *,
    file_name: str = "upload.csv",
) -> tuple[list[TaxEvent], list[str], list[dict[str, Any]]]:
    """column_mapping: canonical field name -> source header label."""
    date_h = column_mapping.get("tradeDate")
    amount_h = column_mapping.get("grossAmount")
    if not date_h or not amount_h:
        return [], ["mapping: tradeDate and grossAmount are required"], [
            {"code": "MAPPING_REQUIRED", "message": "missing tradeDate or grossAmount"}
        ]

    type_h = column_mapping.get("eventType")
    symbol_h = column_mapping.get("symbol")
    wh_h = column_mapping.get("withholdingTax")
    fee_h = column_mapping.get("fee")

    warnings: list[str] = []
    errors: list[dict[str, Any]] = []
    events: list[TaxEvent] = []
    saw_inferred = False

    for row in rows:
        ridx = row.get("__row__", "?")
        trade_date = _parse_date(_row_value(row, date_h))
        if not trade_date:
            continue

        type_raw = str(_row_value(row, type_h) or "").strip() if type_h else ""
        amount = _parse_decimal(_row_value(row, amount_h))
        if amount is None or amount == 0:
            if type_raw and _resolve_event_type(type_raw, amount) == EventType.WITHHOLDING_TAX:
                wh_only = _parse_decimal(_row_value(row, wh_h)) if wh_h else None
                if wh_only and wh_only != 0:
                    amount = abs(wh_only)
                else:
                    continue
            else:
                continue

        row_blob = compose_row_blob(
            type_raw,
            symbol_h and str(_row_value(row, symbol_h) or ""),
            *(str(v) for v in row.values() if v and str(v).strip()),
        )
        if infer_stock_comp_kind(row_blob):
            event_type = EventType.STOCK_COMPENSATION
        else:
            event_type = _resolve_event_type(type_raw or None, amount)
        symbol = None
        if symbol_h:
            symbol = str(_row_value(row, symbol_h) or "").strip() or None

        wh = None
        if wh_h:
            wh_val = _parse_decimal(_row_value(row, wh_h))
            if wh_val and wh_val != 0:
                wh = Money(amount=abs(wh_val), currency="USD")

        fee = None
        if fee_h:
            fee_val = _parse_decimal(_row_value(row, fee_h))
            if fee_val and fee_val != 0:
                fee = Money(amount=abs(fee_val), currency="USD")

        status = "confirmed"
        confidence = 0.85
        if event_type == EventType.CAPITAL_GAIN:
            status = "inferred"
            confidence = 0.75
            saw_inferred = True

        if event_type == EventType.WITHHOLDING_TAX:
            events.append(
                TaxEvent(
                    event_type=EventType.WITHHOLDING_TAX,
                    trade_date=trade_date,
                    gross_amount=Money(amount=abs(amount), currency="USD"),
                    symbol=symbol,
                    source_row_ref=f"{file_name}:{ridx}",
                    classification_status="confirmed",
                    parse_confidence=0.85,
                )
            )
            continue

        ev = TaxEvent(
            event_type=event_type,
            trade_date=trade_date,
            gross_amount=Money(amount=amount, currency="USD"),
            withholding_tax=wh,
            fee=fee,
            symbol=symbol,
            source_row_ref=f"{file_name}:{ridx}",
            classification_status=status,
            parse_confidence=confidence,
        )
        ev = tag_event_if_stock_comp(ev, type_raw=type_raw, description=row_blob)
        if ev.event_type == EventType.STOCK_COMPENSATION:
            warnings.append("generic_mapped: detected RSU/ESPP row (R007)")
        events.append(ev)

    if saw_inferred:
        warnings.append("generic_mapped: 交易类金额按资本利得近似，建议核对已实现盈亏")
    if not events:
        warnings.append("generic_mapped: no events parsed from confirmed mapping")
    return events, warnings, errors


def quality_report(events: list[TaxEvent]) -> dict[str, Any]:
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
