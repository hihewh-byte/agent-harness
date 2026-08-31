from __future__ import annotations

import csv
import io
import re
from decimal import Decimal
from typing import Any

import yaml

from tax_agent.models import EventType, Money, TaxEvent
from tax_agent.parser.mapping_loader import mappings_dir
from tax_agent.parser.stock_comp_detect import compose_row_blob, infer_stock_comp_kind, tag_event_if_stock_comp


def _load_schwab_mapping() -> dict[str, Any]:
    path = mappings_dir() / "broker_schwab_v1.yaml"
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _normalize_header(h: str) -> str:
    return re.sub(r"\s+", " ", (h or "").strip())


def _parse_decimal(val: Any) -> Decimal | None:
    if val is None or val == "":
        return None
    s = str(val).strip().replace(",", "").replace("$", "")
    if not s or s in ("-", "N/A", "n/a"):
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
    for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%m/%d/%y", "%d-%b-%Y"):
        try:
            return datetime.strptime(s[:12], fmt).date().isoformat()
        except ValueError:
            continue
    m = re.search(r"(\d{4}-\d{2}-\d{2})", s)
    return m.group(1) if m else None


def _resolve_alias(row_headers: list[str], aliases: dict[str, list[str]]) -> dict[str, str]:
    normalized = {_normalize_header(h): h for h in row_headers if h}
    out: dict[str, str] = {}
    for canonical, candidates in aliases.items():
        for c in candidates:
            key = _normalize_header(c)
            if key in normalized:
                out[canonical] = normalized[key]
                break
    return out


def find_schwab_header_row(lines: list[str]) -> tuple[int, list[str]] | None:
    """Locate transaction or realized G/L header after Schwab preamble rows."""
    mapping = _load_schwab_mapping()
    sigs = list(mapping.get("detection", {}).get("headerSignatures") or [])
    sigs.append(["Closed Date", "Gain/Loss ($)"])
    sigs.append(["Closed Date", "Gain/Loss"])
    gl_aliases = (mapping.get("csvProfiles") or {}).get("realized_gain_loss", {}).get(
        "headerAliases", {}
    )
    gain_headers = gl_aliases.get("GainLoss") or []
    date_headers = gl_aliases.get("Date") or ["Closed Date"]

    for idx, line in enumerate(lines[:80]):
        if not line.strip():
            continue
        try:
            row = next(csv.reader([line]))
        except csv.Error:
            continue
        headers = [_normalize_header(c) for c in row]
        hset = set(headers)
        for sig in sigs:
            if all(_normalize_header(s) in hset for s in sig):
                return idx, row
        has_date = any(_normalize_header(d) in hset for d in date_headers)
        has_gain = any(_normalize_header(g) in hset for g in gain_headers)
        if has_date and has_gain:
            return idx, row
    return None


def is_schwab_csv(text: str, file_name: str = "") -> bool:
    lower = text[:4000].lower()
    fn = file_name.lower()
    if "schwab" in fn:
        return True
    mapping = _load_schwab_mapping()
    for marker in mapping.get("detection", {}).get("preambleMarkers") or []:
        if marker.lower() in lower:
            return True
    lines = text.splitlines()
    return find_schwab_header_row(lines) is not None


def _detect_csv_profile(headers: list[str]) -> str:
    hset = {_normalize_header(h) for h in headers}
    mapping = _load_schwab_mapping()
    for profile_name, profile in (mapping.get("csvProfiles") or {}).items():
        aliases = profile.get("headerAliases") or {}
        if profile_name == "realized_gain_loss":
            gain_keys = aliases.get("GainLoss") or []
            if any(_normalize_header(k) in hset for k in gain_keys):
                return profile_name
        if profile_name == "transaction_history":
            if "Date" in {_normalize_header(k) for k in (aliases.get("Date") or [])} or "Date" in hset:
                if any(_normalize_header(k) in hset for k in (aliases.get("Action") or ["Action"])):
                    return profile_name
    if any("gain/loss" in h.lower() for h in headers):
        return "realized_gain_loss"
    return "transaction_history"


def parse_schwab_csv(
    text: str,
    file_name: str,
    start_row_offset: int = 0,
) -> tuple[list[TaxEvent], list[str], list[dict[str, Any]]]:
    """
    Parse Schwab transaction history or realized gain/loss CSV.
    Returns (events, warnings, errors).
    """
    mapping = _load_schwab_mapping()
    lines = text.splitlines()
    found = find_schwab_header_row(lines)
    if not found:
        return [], ["schwab: header row not found"], [
            {"code": "SCHWAB_NO_HEADER", "message": "missing Date/Action/Amount header"}
        ]

    header_idx, header_row = found
    data_text = "\n".join(lines[header_idx:])
    reader = csv.DictReader(io.StringIO(data_text))
    headers = list(reader.fieldnames or header_row)
    profile_name = _detect_csv_profile(headers)
    profile = (mapping.get("csvProfiles") or {}).get(profile_name) or {}
    col = _resolve_alias(headers, profile.get("headerAliases") or {})

    warnings: list[str] = []
    errors: list[dict[str, Any]] = []
    events: list[TaxEvent] = []

    if profile_name == "realized_gain_loss":
        events, warnings, errors = _parse_realized_gl(
            reader, col, profile, file_name, header_idx + 1 + start_row_offset
        )
    else:
        events, warnings, errors = _parse_transaction_history(
            reader, col, profile, file_name, header_idx + 1 + start_row_offset
        )

    return events, warnings, errors


def _parse_transaction_history(
    reader: csv.DictReader,
    col: dict[str, str],
    profile: dict[str, Any],
    file_name: str,
    row_base: int,
) -> tuple[list[TaxEvent], list[str], list[dict[str, Any]]]:
    action_map = profile.get("actionMap") or {}
    skip_actions = {s.lower() for s in (profile.get("skipActions") or [])}
    warnings: list[str] = []
    errors: list[dict[str, Any]] = []
    events: list[TaxEvent] = []

    date_col = col.get("Date")
    action_col = col.get("Action")
    amount_col = col.get("Amount")
    if not date_col or not action_col or not amount_col:
        return [], ["schwab: missing required columns"], [
            {"code": "SCHWAB_COLUMNS", "message": f"resolved columns: {col}"}
        ]

    for ridx, row in enumerate(reader, start=row_base + 1):
        norm = {_normalize_header(k): v for k, v in row.items()}
        action_raw = str(norm.get(_normalize_header(action_col), "") or "").strip()
        if not action_raw:
            continue
        action_key = action_raw
        if action_key.lower() in skip_actions:
            continue

        event_type_str = action_map.get(action_key)
        if not event_type_str:
            # fuzzy: Longest prefix / contains
            for k, v in action_map.items():
                if k.lower() in action_raw.lower() or action_raw.lower() in k.lower():
                    event_type_str = v
                    break
        if not event_type_str:
            desc_preview = ""
            if col.get("Description"):
                desc_preview = str(norm.get(_normalize_header(col["Description"]), "") or "")
            symbol_preview = None
            if col.get("Symbol"):
                symbol_preview = str(norm.get(_normalize_header(col["Symbol"]), "") or "").strip() or None
            if not infer_stock_comp_kind(compose_row_blob(action_raw, desc_preview, symbol_preview)):
                continue
            event_type_str = EventType.STOCK_COMPENSATION.value

        trade_date = _parse_date(norm.get(_normalize_header(date_col)))
        if not trade_date:
            continue

        amount = _parse_decimal(norm.get(_normalize_header(amount_col)))
        if amount is None or amount == 0:
            continue

        event_type = EventType(event_type_str)
        classification = "confirmed"
        confidence = 0.96

        if event_type == EventType.CAPITAL_GAIN and "sell" in action_raw.lower():
            warnings.append(
                "schwab: Sell 行 Amount 为成交回款非已实现损益；建议同时上传 Realized Gain/Loss 报告"
            )
            classification = "inferred"
            confidence = 0.75

        gross = abs(amount)
        withholding = None
        fee = None

        if col.get("Fees"):
            fee_val = _parse_decimal(norm.get(_normalize_header(col["Fees"])))
            if fee_val is not None and fee_val != 0:
                fee = Money(amount=abs(fee_val), currency="USD")

        if event_type == EventType.WITHHOLDING_TAX:
            gross = abs(amount)

        symbol = None
        if col.get("Symbol"):
            symbol = str(norm.get(_normalize_header(col["Symbol"]), "") or "").strip() or None

        desc_col = col.get("Description")
        description = ""
        if desc_col:
            description = str(norm.get(_normalize_header(desc_col), "") or "")

        ev = TaxEvent(
            event_type=event_type,
            trade_date=trade_date,
            gross_amount=Money(amount=gross, currency="USD"),
            withholding_tax=withholding,
            fee=fee,
            symbol=symbol,
            source_row_ref=f"{file_name}:tx:{ridx}",
            parse_confidence=confidence,
            classification_status=classification,
        )
        ev = tag_event_if_stock_comp(ev, action=action_raw, description=description)
        if ev.event_type == EventType.STOCK_COMPENSATION:
            warnings.append("schwab: detected RSU/ESPP row — draft stock compensation (R007)")
        events.append(ev)

    return events, warnings, errors


def _parse_realized_gl(
    reader: csv.DictReader,
    col: dict[str, str],
    profile: dict[str, Any],
    file_name: str,
    row_base: int,
) -> tuple[list[TaxEvent], list[str], list[dict[str, Any]]]:
    warnings: list[str] = []
    errors: list[dict[str, Any]] = []
    events: list[TaxEvent] = []

    date_col = col.get("Date")
    gain_col = col.get("GainLoss")
    if not date_col or not gain_col:
        return [], ["schwab G/L: missing Date or Gain/Loss column"], []

    for ridx, row in enumerate(reader, start=row_base + 1):
        norm = {_normalize_header(k): v for k, v in row.items()}
        trade_date = _parse_date(norm.get(_normalize_header(date_col)))
        gain = _parse_decimal(norm.get(_normalize_header(gain_col)))
        if not trade_date or gain is None or gain == 0:
            continue
        symbol = None
        if col.get("Symbol"):
            symbol = str(norm.get(_normalize_header(col["Symbol"]), "") or "").strip() or None

        proceeds = None
        cost_basis = None
        if col.get("Proceeds"):
            proceeds = _parse_decimal(norm.get(_normalize_header(col["Proceeds"])))
        if col.get("CostBasis"):
            cost_basis = _parse_decimal(norm.get(_normalize_header(col["CostBasis"])))

        ev = TaxEvent(
            event_type=EventType.CAPITAL_GAIN,
            trade_date=trade_date,
            gross_amount=Money(amount=gain, currency="USD"),
            symbol=symbol,
            source_row_ref=f"{file_name}:gl:{ridx}",
            parse_confidence=0.98,
            classification_status="confirmed",
        )
        ev = tag_event_if_stock_comp(
            ev,
            type_raw="realized gain loss",
            description=symbol or "",
            cost_basis_usd=cost_basis,
            proceeds_usd=proceeds,
        )
        if ev.event_type == EventType.STOCK_COMPENSATION:
            warnings.append("schwab: G/L row tagged as RSU/ESPP sale (R007)")
        events.append(ev)

    warnings.append("schwab: parsed realized gain/loss report (preferred for capital gains)")
    return events, warnings, errors


def merge_schwab_events(event_lists: list[list[TaxEvent]]) -> list[TaxEvent]:
    """Merge transaction + G/L exports; prefer G/L capital gains over Sell rows."""
    combined: list[TaxEvent] = []
    has_gl_gain = False
    for batch in event_lists:
        for e in batch:
            if e.event_type == EventType.CAPITAL_GAIN and ":gl:" in e.source_row_ref:
                has_gl_gain = True
    for batch in event_lists:
        for e in batch:
            if (
                has_gl_gain
                and e.event_type == EventType.CAPITAL_GAIN
                and ":tx:" in e.source_row_ref
                and e.classification_status == "inferred"
            ):
                continue
            combined.append(e)
    return combined
