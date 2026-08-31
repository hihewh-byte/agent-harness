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
    return yaml.safe_load((mappings_dir() / "broker_fidelity_v1.yaml").read_text(encoding="utf-8"))


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
    for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%m/%d/%y"):
        try:
            return datetime.strptime(s[:12], fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _resolve_alias(headers: list[str], aliases: dict[str, list[str]]) -> dict[str, str]:
    normalized = {_normalize_header(h): h for h in headers if h}
    out: dict[str, str] = {}
    for canonical, candidates in aliases.items():
        for c in candidates:
            key = _normalize_header(c)
            if key in normalized:
                out[canonical] = normalized[key]
                break
    return out


def find_fidelity_header_row(lines: list[str]) -> tuple[int, list[str]] | None:
    mapping = _load_mapping()
    sigs = list(mapping.get("detection", {}).get("headerSignatures") or [])
    gl_aliases = (mapping.get("csvProfiles") or {}).get("gains_losses", {}).get(
        "headerAliases", {}
    )
    gain_headers = gl_aliases.get("GainLoss") or []
    date_headers = gl_aliases.get("Date") or ["Date Sold", "Closed Date"]

    for idx, line in enumerate(lines[:80]):
        if not line.strip():
            continue
        try:
            row = next(csv.reader([line]))
        except csv.Error:
            continue
        hset = {_normalize_header(c) for c in row}
        for sig in sigs:
            if all(_normalize_header(s) in hset for s in sig):
                return idx, row
        if "Run Date" in hset and "Action" in hset:
            return idx, row
        has_date = any(_normalize_header(d) in hset for d in date_headers)
        has_gain = any(_normalize_header(g) in hset for g in gain_headers)
        if has_date and has_gain:
            return idx, row
        if any("gain/loss" in h.lower() for h in hset) and has_date:
            return idx, row
    return None


def _detect_fidelity_profile(headers: list[str]) -> str:
    hset = {_normalize_header(h) for h in headers}
    mapping = _load_mapping()
    profiles = mapping.get("csvProfiles") or {}
    gl = profiles.get("gains_losses") or {}
    gl_aliases = gl.get("headerAliases") or {}
    gain_keys = gl_aliases.get("GainLoss") or []
    if any(_normalize_header(k) in hset for k in gain_keys):
        return "gains_losses"
    st_lt = (gl_aliases.get("ShortTerm") or []) + (gl_aliases.get("LongTerm") or [])
    if any(_normalize_header(k) in hset for k in st_lt):
        return "gains_losses"
    hist = profiles.get("account_history") or {}
    hist_aliases = hist.get("headerAliases") or {}
    if any(_normalize_header(k) in hset for k in (hist_aliases.get("Action") or ["Action"])):
        if any(_normalize_header(k) in hset for k in (hist_aliases.get("Date") or ["Run Date"])):
            return "account_history"
    if any("gain/loss" in h.lower() for h in headers) and "Action" not in hset:
        return "gains_losses"
    return "account_history"


def is_fidelity_csv(text: str, file_name: str = "") -> bool:
    if "fidelity" in file_name.lower():
        return True
    lower = text[:3000].lower()
    for m in _load_mapping().get("detection", {}).get("preambleMarkers") or []:
        if m.lower() in lower:
            return True
    return find_fidelity_header_row(text.splitlines()) is not None


def _match_action(action_raw: str, action_map: dict[str, str]) -> str | None:
    key = action_raw.strip()
    if key in action_map:
        return action_map[key]
    upper = key.upper()
    for k, v in action_map.items():
        if k.upper() == upper:
            return v
    for k, v in action_map.items():
        if k.upper() in upper or upper in k.upper():
            return v
    return None


def _parse_fidelity_gains_losses(
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
    st_col = col.get("ShortTerm")
    lt_col = col.get("LongTerm")
    if not date_col:
        return [], ["fidelity G/L: missing date column"], [{"code": "FIDELITY_GL_COLUMNS"}]
    if not gain_col and not (st_col or lt_col):
        return [], ["fidelity G/L: missing gain/loss column"], [{"code": "FIDELITY_GL_COLUMNS"}]

    for ridx, row in enumerate(reader, start=row_base + 1):
        norm = {_normalize_header(k): v for k, v in row.items()}
        trade_date = _parse_date(norm.get(_normalize_header(date_col)))
        if not trade_date:
            continue

        gain: Decimal | None = None
        if gain_col:
            gain = _parse_decimal(norm.get(_normalize_header(gain_col)))
        if gain is None and (st_col or lt_col):
            st = _parse_decimal(norm.get(_normalize_header(st_col))) if st_col else None
            lt = _parse_decimal(norm.get(_normalize_header(lt_col))) if lt_col else None
            parts = [p for p in (st, lt) if p is not None]
            gain = sum(parts, Decimal(0)) if parts else None
        if gain is None or gain == 0:
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
            source_row_ref=f"{file_name}:fgl:{ridx}",
            parse_confidence=0.98,
            classification_status="confirmed",
        )
        ev = tag_event_if_stock_comp(
            ev,
            type_raw="gains losses",
            description=symbol or "",
            cost_basis_usd=cost_basis,
            proceeds_usd=proceeds,
        )
        if ev.event_type == EventType.STOCK_COMPENSATION:
            warnings.append("fidelity: G/L row tagged as RSU/ESPP sale (R007)")
        events.append(ev)

    warnings.append("fidelity: parsed gains & losses report (preferred for capital gains)")
    return events, warnings, errors


def _parse_fidelity_account_history(
    reader: csv.DictReader,
    col: dict[str, str],
    profile: dict[str, Any],
    file_name: str,
    row_base: int,
) -> tuple[list[TaxEvent], list[str], list[dict[str, Any]]]:
    date_col = col.get("Date")
    action_col = col.get("Action")
    amount_col = col.get("Amount")
    if not date_col or not action_col or not amount_col:
        return [], [f"fidelity: columns {col}"], [{"code": "FIDELITY_COLUMNS"}]

    action_map = profile.get("actionMap") or {}
    skip = {s.upper() for s in (profile.get("skipActions") or [])}
    sell_inferred = profile.get("sellUsesAmountAsInferredGain", True)
    warnings: list[str] = []
    errors: list[dict[str, Any]] = []
    events: list[TaxEvent] = []

    for ridx, row in enumerate(reader, start=row_base + 1):
        norm = {_normalize_header(k): v for k, v in row.items()}
        action_raw = str(norm.get(_normalize_header(action_col), "") or "").strip()
        if not action_raw or action_raw.upper() in skip:
            continue

        description = ""
        if col.get("Description"):
            description = str(norm.get(_normalize_header(col["Description"]), "") or "")
        symbol_preview = None
        if col.get("Symbol"):
            symbol_preview = str(norm.get(_normalize_header(col["Symbol"]), "") or "").strip() or None

        event_type_str = _match_action(action_raw, action_map)
        if not event_type_str:
            if infer_stock_comp_kind(compose_row_blob(action_raw, description, symbol_preview)):
                event_type_str = EventType.STOCK_COMPENSATION.value
            else:
                continue

        trade_date = _parse_date(norm.get(_normalize_header(date_col)))
        if not trade_date:
            continue

        amount = _parse_decimal(norm.get(_normalize_header(amount_col)))
        if (amount is None or amount == 0) and col.get("Fees"):
            amount = _parse_decimal(norm.get(_normalize_header(col["Fees"])))
        if amount is None or amount == 0:
            continue

        event_type = EventType(event_type_str)
        classification = "confirmed"
        confidence = 0.96

        if event_type == EventType.CAPITAL_GAIN and sell_inferred:
            warnings.append(
                "fidelity: YOU SOLD 的 Amount 为回款；如有 Gains & Losses 报告请一并上传"
            )
            classification = "inferred"
            confidence = 0.75

        gross = abs(amount)
        fee = None
        if col.get("Fees"):
            fv = _parse_decimal(norm.get(_normalize_header(col["Fees"])))
            if fv and fv != 0:
                fee = Money(amount=abs(fv), currency="USD")

        symbol = None
        if col.get("Symbol"):
            symbol = str(norm.get(_normalize_header(col["Symbol"]), "") or "").strip() or None

        ev = TaxEvent(
            event_type=event_type,
            trade_date=trade_date,
            gross_amount=Money(amount=gross, currency="USD"),
            fee=fee,
            symbol=symbol,
            source_row_ref=f"{file_name}:fd:{ridx}",
            parse_confidence=confidence,
            classification_status=classification,
        )
        ev = tag_event_if_stock_comp(ev, action=action_raw, description=description)
        if ev.event_type == EventType.STOCK_COMPENSATION:
            warnings.append("fidelity: detected RSU/ESPP row — draft stock compensation (R007)")
        events.append(ev)

    return events, warnings, errors


def parse_fidelity_csv(text: str, file_name: str) -> tuple[list[TaxEvent], list[str], list[dict[str, Any]]]:
    lines = text.splitlines()
    found = find_fidelity_header_row(lines)
    if not found:
        return [], ["fidelity: header not found"], [{"code": "FIDELITY_NO_HEADER", "message": "missing Run Date/Action"}]

    header_idx, header_row = found
    mapping = _load_mapping()
    reader = csv.DictReader(io.StringIO("\n".join(lines[header_idx:])))
    headers = list(reader.fieldnames or header_row)
    profile_name = _detect_fidelity_profile(headers)
    profile = (mapping.get("csvProfiles") or {}).get(profile_name) or {}
    col = _resolve_alias(headers, profile.get("headerAliases") or {})

    if profile_name == "gains_losses":
        return _parse_fidelity_gains_losses(
            reader, col, profile, file_name, header_idx + 1
        )
    return _parse_fidelity_account_history(
        reader, col, profile, file_name, header_idx + 1
    )


def merge_fidelity_events(event_lists: list[list[TaxEvent]]) -> list[TaxEvent]:
    """Merge History + Gains/Losses; prefer confirmed G/L over inferred YOU SOLD rows."""
    combined: list[TaxEvent] = []
    has_gl_gain = False
    for batch in event_lists:
        for e in batch:
            if e.event_type == EventType.CAPITAL_GAIN and ":fgl:" in e.source_row_ref:
                has_gl_gain = True
    for batch in event_lists:
        for e in batch:
            if (
                has_gl_gain
                and e.event_type == EventType.CAPITAL_GAIN
                and ":fd:" in e.source_row_ref
                and e.classification_status == "inferred"
            ):
                continue
            combined.append(e)
    return combined
