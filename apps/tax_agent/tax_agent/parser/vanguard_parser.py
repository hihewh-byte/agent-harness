from __future__ import annotations

import csv
import io
import re
from decimal import Decimal
from typing import Any

import yaml

from tax_agent.models import EventType, Money, TaxEvent
from tax_agent.parser.stock_comp_detect import infer_stock_comp_kind, compose_row_blob, tag_event_if_stock_comp
from tax_agent.parser.mapping_loader import mappings_dir


def _load_mapping() -> dict[str, Any]:
    return yaml.safe_load((mappings_dir() / "broker_vanguard_v1.yaml").read_text(encoding="utf-8"))


def _normalize_header(h: str) -> str:
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
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%m/%d/%y"):
        try:
            return datetime.strptime(s[:12], fmt).date().isoformat()
        except ValueError:
            continue
    return None


def find_vanguard_header_row(lines: list[str]) -> tuple[int, list[str]] | None:
    for idx, line in enumerate(lines[:40]):
        if not line.strip():
            continue
        try:
            row = next(csv.reader([line]))
        except csv.Error:
            continue
        hset = {_normalize_header(c) for c in row}
        if "Settlement date" in hset and "Transaction type" in hset and "Amount" in hset:
            return idx, row
        if "Settlement Date" in hset and "Transaction Type" in hset and "Amount" in hset:
            return idx, row
    return None


def is_vanguard_csv(text: str, file_name: str = "") -> bool:
    fn = file_name.lower()
    if "vanguard" in fn:
        return True
    return find_vanguard_header_row(text.splitlines()) is not None


def parse_vanguard_csv(
    text: str,
    file_name: str,
) -> tuple[list[TaxEvent], list[str], list[dict[str, Any]]]:
    lines = text.splitlines()
    found = find_vanguard_header_row(lines)
    if not found:
        return [], ["vanguard: header row not found"], [
            {"code": "VANGUARD_NO_HEADER", "message": "missing Settlement date / Transaction type / Amount"}
        ]

    mapping = _load_mapping()
    type_map = {str(k): str(v) for k, v in (mapping.get("typeMap") or {}).items()}
    header_idx, header_row = found
    data_text = "\n".join(lines[header_idx:])
    reader = csv.DictReader(io.StringIO(data_text))
    headers = list(reader.fieldnames or header_row)
    norm_map = {_normalize_header(h): h for h in headers if h}

    date_col = norm_map.get("Settlement date") or norm_map.get("Settlement Date")
    type_col = norm_map.get("Transaction type") or norm_map.get("Transaction Type")
    amount_col = norm_map.get("Amount")
    symbol_col = norm_map.get("Symbol") or norm_map.get("Investment name")
    if not date_col or not type_col or not amount_col:
        return [], ["vanguard: missing required columns"], [
            {"code": "VANGUARD_COLUMNS", "message": str(norm_map)}
        ]

    warnings: list[str] = []
    errors: list[dict[str, Any]] = []
    events: list[TaxEvent] = []

    for ridx, row in enumerate(reader, start=header_idx + 2):
        norm = {_normalize_header(k): v for k, v in row.items()}
        type_raw = str(norm.get(_normalize_header(type_col), "") or "").strip()
        if not type_raw:
            continue
        symbol = None
        if symbol_col:
            symbol = str(norm.get(_normalize_header(symbol_col), "") or "").strip() or None
        event_type_str = type_map.get(type_raw)
        if not event_type_str:
            if infer_stock_comp_kind(compose_row_blob(type_raw, symbol or "")):
                event_type_str = EventType.STOCK_COMPENSATION.value
            else:
                warnings.append(f"vanguard: unknown type '{type_raw}' row {ridx}")
                continue
        try:
            event_type = EventType(event_type_str)
        except ValueError:
            continue

        trade_date = _parse_date(norm.get(_normalize_header(date_col)))
        amount = _parse_decimal(norm.get(_normalize_header(amount_col)))
        if not trade_date or amount is None or amount == 0:
            continue

        ev = TaxEvent(
            event_type=event_type,
            trade_date=trade_date,
            gross_amount=Money(amount=amount, currency="USD"),
            symbol=symbol,
            source_row_ref=f"{file_name}:{ridx}",
            classification_status="confirmed",
            parse_confidence=0.95,
        )
        ev = tag_event_if_stock_comp(ev, type_raw=type_raw)
        events.append(ev)

    return events, list(dict.fromkeys(warnings)), errors
