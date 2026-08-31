from __future__ import annotations

import csv
import io
import re
from decimal import Decimal
from typing import Any

import yaml

from tax_agent.models import EventType, Money, TaxEvent
from tax_agent.parser.stock_comp_detect import compose_row_blob, infer_stock_comp_kind, tag_event_if_stock_comp
from tax_agent.parser.mapping_loader import mappings_dir


def _load_mapping() -> dict[str, Any]:
    return yaml.safe_load((mappings_dir() / "broker_tiger_v1.yaml").read_text(encoding="utf-8"))


def _normalize_header(h: str) -> str:
    return re.sub(r"\s+", " ", (h or "").strip())


def _parse_decimal(val: Any) -> Decimal | None:
    if val is None or val == "":
        return None
    s = str(val).strip().replace(",", "").replace("$", "").replace("¥", "")
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
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(s[:19], fmt).date().isoformat()
        except ValueError:
            continue
    m = re.search(r"(\d{4}-\d{2}-\d{2})", s)
    return m.group(1) if m else None


def find_tiger_header_row(lines: list[str]) -> tuple[int, list[str], str] | None:
    """Return (row_index, headers, profile) where profile is trades|dividends."""
    for idx, line in enumerate(lines[:40]):
        if not line.strip():
            continue
        try:
            row = next(csv.reader([line]))
        except csv.Error:
            continue
        hset = {_normalize_header(c) for c in row}
        if "成交时间" in hset and "成交金额" in hset:
            return idx, row, "trades"
        if "日期" in hset and "金额" in hset and ("预扣税" in hset or "代码" in hset):
            return idx, row, "dividends"
    return None


def is_tiger_csv(text: str, file_name: str = "") -> bool:
    fn = file_name.lower()
    if "tiger" in fn or "老虎" in file_name:
        return True
    return find_tiger_header_row(text.splitlines()) is not None


def parse_tiger_csv(
    text: str,
    file_name: str,
) -> tuple[list[TaxEvent], list[str], list[dict[str, Any]]]:
    lines = text.splitlines()
    found = find_tiger_header_row(lines)
    if not found:
        return [], ["tiger: header row not found"], [
            {"code": "TIGER_NO_HEADER", "message": "missing 成交/分红 headers"}
        ]

    header_idx, header_row, profile = found
    data_text = "\n".join(lines[header_idx:])
    reader = csv.DictReader(io.StringIO(data_text))
    headers = list(reader.fieldnames or header_row)
    norm_map = {_normalize_header(h): h for h in headers if h}

    warnings: list[str] = []
    errors: list[dict[str, Any]] = []
    events: list[TaxEvent] = []

    if profile == "trades":
        date_col = norm_map.get("成交时间")
        amount_col = norm_map.get("成交金额")
        symbol_col = norm_map.get("代码")
        fee_col = norm_map.get("佣金")
        if not date_col or not amount_col:
            return [], ["tiger: missing trade columns"], [
                {"code": "TIGER_COLUMNS", "message": str(norm_map)}
            ]
        for ridx, row in enumerate(reader, start=header_idx + 2):
            norm = {_normalize_header(k): v for k, v in row.items()}
            trade_date = _parse_date(norm.get(_normalize_header(date_col)))
            gross = _parse_decimal(norm.get(_normalize_header(amount_col)))
            if not trade_date or gross is None or gross == 0:
                continue
            fee = None
            if fee_col:
                fee_val = _parse_decimal(norm.get(_normalize_header(fee_col)))
                if fee_val and fee_val != 0:
                    fee = Money(amount=abs(fee_val), currency="USD")
            symbol = str(norm.get(_normalize_header(symbol_col), "") or "").strip() or None
            note_col = norm_map.get("备注") or norm_map.get("说明")
            note = str(norm.get(_normalize_header(note_col), "") or "") if note_col else ""
            ev = TaxEvent(
                event_type=EventType.CAPITAL_GAIN,
                trade_date=trade_date,
                gross_amount=Money(amount=gross, currency="USD"),
                fee=fee,
                symbol=symbol,
                source_row_ref=f"{file_name}:trades:{ridx}",
                classification_status="inferred",
                parse_confidence=0.9,
            )
            if infer_stock_comp_kind(compose_row_blob(note, symbol, "trade")):
                ev = tag_event_if_stock_comp(ev, type_raw="trade", description=note)
            events.append(ev)
    else:
        date_col = norm_map.get("日期")
        amount_col = norm_map.get("金额")
        wh_col = norm_map.get("预扣税")
        symbol_col = norm_map.get("代码")
        if not date_col or not amount_col:
            return [], ["tiger: missing dividend columns"], [
                {"code": "TIGER_COLUMNS", "message": str(norm_map)}
            ]
        for ridx, row in enumerate(reader, start=header_idx + 2):
            norm = {_normalize_header(k): v for k, v in row.items()}
            trade_date = _parse_date(norm.get(_normalize_header(date_col)))
            gross = _parse_decimal(norm.get(_normalize_header(amount_col)))
            if not trade_date or gross is None or gross == 0:
                continue
            wh = None
            if wh_col:
                wh_val = _parse_decimal(norm.get(_normalize_header(wh_col)))
                if wh_val and wh_val != 0:
                    wh = Money(amount=abs(wh_val), currency="USD")
            symbol = str(norm.get(_normalize_header(symbol_col), "") or "").strip() or None
            events.append(
                TaxEvent(
                    event_type=EventType.DIVIDEND,
                    trade_date=trade_date,
                    gross_amount=Money(amount=gross, currency="USD"),
                    withholding_tax=wh,
                    symbol=symbol,
                    source_row_ref=f"{file_name}:dividends:{ridx}",
                    classification_status="confirmed",
                    parse_confidence=0.95,
                )
            )

    if profile == "trades":
        warnings.append("tiger: 成交金额作为资本利得近似，建议核对已实现盈亏报表")
    return events, warnings, errors
