from __future__ import annotations

import csv
import io
import re
from decimal import Decimal
from typing import Any

import yaml

from tax_agent.cost_basis import TradeLeg, match_fifo
from tax_agent.futu_session_fifo import leg_to_dict, realized_gains_to_events
from tax_agent.models import EventType, Money, TaxEvent
from tax_agent.parser.stock_comp_detect import infer_stock_comp_kind, compose_row_blob, tag_event_if_stock_comp
from tax_agent.parser.mapping_loader import mappings_dir


def _load_mapping() -> dict[str, Any]:
    return yaml.safe_load((mappings_dir() / "broker_futu_v1.yaml").read_text(encoding="utf-8"))


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
    for fmt in (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
        "%Y%m%d",
        "%m/%d/%Y",
        "%d/%m/%Y",
        "%Y/%m/%d",
    ):
        try:
            return datetime.strptime(s[:19], fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _header_aliases() -> dict[str, list[str]]:
    mapping = _load_mapping()
    return mapping.get("headerAliases") or {}


def _resolve_col(norm_map: dict[str, str], canonical: str) -> str | None:
    aliases = _header_aliases().get(canonical) or [canonical]
    for alias in aliases:
        key = _normalize_header(alias)
        if key in norm_map:
            return norm_map[key]
    return None


def find_futu_header_row(lines: list[str]) -> tuple[int, list[str]] | None:
    date_keys = {_normalize_header(a) for a in (_header_aliases().get("Date") or ["Date"])}
    type_keys = {_normalize_header(a) for a in (_header_aliases().get("Type") or ["Type"])}
    amount_keys = {_normalize_header(a) for a in (_header_aliases().get("Amount") or ["Amount"])}
    # 富途税表「证券-交易流水」：成交时间 + 方向 + 成交金额

    for idx, line in enumerate(lines[:40]):
        if not line.strip():
            continue
        try:
            row = next(csv.reader([line]))
        except csv.Error:
            continue
        hset = {_normalize_header(c) for c in row}
        if hset & date_keys and hset & type_keys and hset & amount_keys:
            if "Action" not in hset:
                return idx, row
    return None


def is_futu_csv(text: str, file_name: str = "") -> bool:
    fn = file_name.lower()
    if "futu" in fn or "moomoo" in fn or "富途" in file_name:
        return True
    if "annual_statement" in fn or "interest" in fn and "dividend" in fn:
        # 文件名可能为 Schwab 风格，但由 xlsx 工作表名识别
        pass
    return find_futu_header_row(text.splitlines()) is not None


def _futu_trade_side(direction: str) -> str | None:
    d = (direction or "").strip()
    if not d:
        return None
    if "卖出" in d or d.lower() in ("sell", "sell close"):
        return "sell"
    if "买入" in d or d.lower() in ("buy", "buy open"):
        return "buy"
    return None


def _futu_net_cash(
    amount: Decimal | None,
    change_amount: Decimal | None,
    fee: Decimal | None,
    *,
    side: str,
) -> Decimal | None:
    """Return positive cash: buy cost or sell proceeds (after fees when possible)."""
    fee_val = abs(fee or Decimal("0"))
    if change_amount is not None and change_amount != 0:
        return abs(change_amount) if side == "buy" else change_amount
    if amount is None:
        return None
    if side == "buy":
        return abs(amount) + fee_val
    return amount - fee_val


def infer_futu_tax_year_from_filename(file_name: str) -> int | None:
    m = re.search(r"(20\d{2})", file_name or "")
    if m:
        return int(m.group(1))
    return None


def is_futu_tax_trade_rows(rows: list[dict[str, Any]]) -> bool:
    """True for 富途税表「证券-交易流水」— needs qty column, not desktop History CSV."""
    if not rows:
        return False
    keys = {_normalize_header(k) for k in rows[0].keys() if k != "__row__"}
    if {"成交时间", "方向", "成交金额"}.issubset(keys):
        return True
    qty_keys = {"数量/面值", "Quantity", "数量"}
    has_qty = bool(keys & qty_keys) or any("数量" in k for k in keys)
    if not has_qty:
        return False
    date_keys = {_normalize_header(a) for a in (_header_aliases().get("Date") or ["Date"])}
    type_keys = {_normalize_header(a) for a in (_header_aliases().get("Type") or ["Type"])}
    amount_keys = {_normalize_header(a) for a in (_header_aliases().get("Amount") or ["Amount"])}
    return bool(keys & date_keys) and bool(keys & type_keys) and bool(keys & amount_keys)


def is_futu_tax_trade_sheet(sheet_name: str, rows: list[dict[str, Any]]) -> bool:
    if "交易流水" in (sheet_name or ""):
        return is_futu_tax_trade_rows(rows)
    return is_futu_tax_trade_rows(rows)


def parse_futu_tax_year(account_rows: list[dict[str, Any]] | None) -> int | None:
    for row in account_rows or []:
        year_raw = row.get("年份") or row.get("year")
        if not year_raw:
            continue
        year = str(year_raw).strip()[:4]
        if year.isdigit():
            return int(year)
    return None


def _parse_futu_position_rows(
    position_rows: list[dict[str, Any]] | None,
    *,
    file_name: str,
    tax_year: int | None,
    period_match: str,
) -> list[dict[str, Any]]:
    """持仓总览行：期初/期末数量与市值价（不等于买入成本）。"""
    out: list[dict[str, Any]] = []
    for row in position_rows or []:
        period = str(row.get("时期类型") or row.get("periodType") or "")
        if period_match == "opening":
            if "期初" not in period and "opening" not in period.lower():
                continue
        elif period_match == "closing":
            if "期末" not in period and "closing" not in period.lower():
                continue
        else:
            continue
        symbol = str(row.get("代码名称") or row.get("Symbol") or "").strip()
        qty = _parse_decimal(row.get("数量/面值") or row.get("Quantity"))
        price = _parse_decimal(row.get("价格") or row.get("Price"))
        market_value = _parse_decimal(row.get("市值") or row.get("Market Value"))
        as_of = _parse_date(row.get("日期") or row.get("Date"))
        category = str(row.get("品类") or row.get("Category") or "").strip()
        ridx = int(row.get("__row__", 0) or 0)
        if not symbol or qty is None or qty == 0:
            continue
        default_date = (
            f"{tax_year}-12-31"
            if period_match == "closing" and tax_year
            else (f"{tax_year}-01-01" if tax_year else "")
        )
        out.append(
            {
                "symbol": symbol,
                "quantity": str(abs(qty)),
                "asOfDate": as_of or default_date,
                "marketPrice": str(price) if price is not None else None,
                "marketValue": str(market_value) if market_value is not None else None,
                "category": category,
                "costBasisKnown": False,
                "sourceRowRef": f"{file_name}:pos:{ridx}",
            }
        )
    return out


def parse_futu_opening_positions(
    position_rows: list[dict[str, Any]] | None,
    *,
    file_name: str,
    tax_year: int | None,
) -> list[dict[str, Any]]:
    """期初持仓（仅数量+市值价；价格不等于买入成本）。"""
    return _parse_futu_position_rows(
        position_rows, file_name=file_name, tax_year=tax_year, period_match="opening"
    )


def parse_futu_closing_positions(
    position_rows: list[dict[str, Any]] | None,
    *,
    file_name: str,
    tax_year: int | None,
) -> list[dict[str, Any]]:
    """期末持仓（税表持仓总览；市值价不等于买入成本，未实现盈亏不计入申报）。"""
    return _parse_futu_position_rows(
        position_rows, file_name=file_name, tax_year=tax_year, period_match="closing"
    )


def extract_futu_trade_legs(
    trade_rows: list[dict[str, Any]],
    *,
    file_name: str,
    asset_rows: list[dict[str, Any]] | None = None,
) -> list[TradeLeg]:
    legs: list[TradeLeg] = []
    for row in trade_rows:
        ridx = int(row.get("__row__", 0) or 0)
        direction = str(row.get("方向") or row.get("Type") or "").strip()
        side = _futu_trade_side(direction)
        if not side:
            continue

        trade_date = _parse_date(row.get("成交时间") or row.get("Date"))
        if not trade_date:
            continue

        symbol = str(row.get("代码名称") or row.get("Symbol") or "").strip() or None
        qty = _parse_decimal(row.get("数量/面值") or row.get("Quantity"))
        amount = _parse_decimal(row.get("成交金额") or row.get("Amount"))
        fee = _parse_decimal(row.get("总费用") or row.get("Fee"))
        change_amount = _parse_decimal(row.get("变动金额"))
        category = str(row.get("品类") or "").strip()

        if qty is None or qty == 0:
            continue
        net = _futu_net_cash(amount, change_amount, fee, side=side)
        if net is None:
            continue

        legs.append(
            TradeLeg(
                trade_date=trade_date,
                symbol=symbol or "",
                side=side,
                quantity=qty,
                net_cash=net,
                fee=abs(fee or Decimal("0")),
                source_row_ref=f"{file_name}:{ridx}",
                category=category,
                sort_key=(trade_date, ridx),
            )
        )

    for row in asset_rows or []:
        ridx = int(row.get("__row__", 0) or 0)
        note = str(row.get("备注") or row.get("Description") or "")
        if "expiration" not in note.lower() and "到期" not in note:
            continue
        trade_date = _parse_date(row.get("日期") or row.get("Date"))
        symbol = str(row.get("代码名称") or row.get("Symbol") or "").strip() or None
        qty = _parse_decimal(row.get("数量") or row.get("Quantity"))
        if not trade_date or not symbol or qty is None or qty == 0:
            continue
        legs.append(
            TradeLeg(
                trade_date=trade_date,
                symbol=symbol,
                side="expire",
                quantity=qty,
                net_cash=Decimal("0"),
                fee=Decimal("0"),
                source_row_ref=f"{file_name}:asset:{ridx}",
                category=str(row.get("品类") or ""),
                sort_key=(trade_date, 100000 + ridx),
            )
        )
    return legs


def build_futu_tax_package(
    *,
    trade_rows: list[dict[str, Any]],
    file_name: str,
    file_hash: str,
    asset_rows: list[dict[str, Any]] | None = None,
    position_rows: list[dict[str, Any]] | None = None,
    account_rows: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    tax_year = parse_futu_tax_year(account_rows) or infer_futu_tax_year_from_filename(file_name)
    legs = extract_futu_trade_legs(trade_rows, file_name=file_name, asset_rows=asset_rows)
    return {
        "fileName": file_name,
        "fileHash": file_hash,
        "taxYear": tax_year,
        "legs": [leg_to_dict(leg) for leg in legs],
        "openingPositions": parse_futu_opening_positions(
            position_rows, file_name=file_name, tax_year=tax_year
        ),
        "closingPositions": parse_futu_closing_positions(
            position_rows, file_name=file_name, tax_year=tax_year
        ),
    }


def parse_futu_tax_trades_rows(
    trade_rows: list[dict[str, Any]],
    *,
    file_name: str,
    asset_rows: list[dict[str, Any]] | None = None,
    position_rows: list[dict[str, Any]] | None = None,
    account_rows: list[dict[str, Any]] | None = None,
    file_hash: str = "",
) -> tuple[list[TaxEvent], list[str], list[dict[str, Any]], dict[str, Any] | None]:
    """Parse 证券-交易流水; single-file FIFO (session merge may rematch cross-year)."""
    warnings: list[str] = []
    errors: list[dict[str, Any]] = []

    legs = extract_futu_trade_legs(trade_rows, file_name=file_name, asset_rows=asset_rows)
    if not legs:
        return [], ["futu: 交易流水无有效买卖记录"], [], None

    pkg = build_futu_tax_package(
        trade_rows=trade_rows,
        file_name=file_name,
        file_hash=file_hash or file_name,
        asset_rows=asset_rows,
        position_rows=position_rows,
        account_rows=account_rows,
    )

    realized, fifo_warnings = match_fifo(legs)
    warnings.extend(fifo_warnings)
    events = realized_gains_to_events(realized)

    if events:
        total_gain = sum(e.gross_amount.amount for e in events if e.gross_amount)
        warnings.append(
            f"futu: 已按 FIFO 计算已实现损益（{len(events)} 笔，合计 {total_gain} USD）"
        )
    else:
        warnings.append("futu: FIFO 匹配完成，本年无已实现资本利得（可能全部为净亏损）")

    return events, warnings, errors, pkg


def parse_futu_tax_trades_rows_legacy(
    trade_rows: list[dict[str, Any]],
    *,
    file_name: str,
    asset_rows: list[dict[str, Any]] | None = None,
) -> tuple[list[TaxEvent], list[str], list[dict[str, Any]]]:
    events, warnings, errors, _ = parse_futu_tax_trades_rows(
        trade_rows, file_name=file_name, asset_rows=asset_rows
    )
    return events, warnings, errors


def parse_futu_income_summary_rows(
    rows: list[dict[str, Any]],
    *,
    file_name: str,
) -> tuple[list[TaxEvent], list[str], list[dict[str, Any]]]:
    """解析「股息、利息及其他收入」年度汇总行（仅 USD 正金额）。"""
    if not rows:
        return [], [], []
    headers = [k for k in rows[0].keys() if k != "__row__"]
    norm_map = {_normalize_header(h): h for h in headers}
    year_col = norm_map.get("年份") or norm_map.get("year")
    ccy_col = norm_map.get("币种") or norm_map.get("currency")
    div_col = norm_map.get("全年股息")
    int_col = norm_map.get("全年利息")
    div_tax_col = norm_map.get("全年股息税") or norm_map.get("股息税") or norm_map.get("美国税费")
    int_tax_col = norm_map.get("全年利息税") or norm_map.get("利息税")
    other_col = norm_map.get("全年其他收入")
    if not year_col:
        return [], [], []

    events: list[TaxEvent] = []
    warnings: list[str] = []
    for row in rows:
        year_raw = row.get(year_col)
        if not year_raw:
            continue
        year = str(year_raw).strip()[:4]
        if not year.isdigit():
            continue
        ccy = str(row.get(ccy_col, "USD") if ccy_col else "USD").strip().upper() or "USD"
        if ccy != "USD":
            continue
        trade_date = f"{year}-12-31"
        ridx = row.get("__row__", 0)
        for col, etype, tax_col in (
            (div_col, EventType.DIVIDEND, div_tax_col),
            (int_col, EventType.INTEREST, int_tax_col),
        ):
            if not col:
                continue
            amt = _parse_decimal(row.get(col))
            if amt is None or amt <= 0:
                continue
            wh_amt = _parse_decimal(row.get(tax_col)) if tax_col else None
            if wh_amt is not None and wh_amt < 0:
                wh_amt = abs(wh_amt)
            events.append(
                TaxEvent(
                    event_type=etype,
                    trade_date=trade_date,
                    gross_amount=Money(amount=amt, currency="USD"),
                    withholding_tax=Money(amount=wh_amt, currency="USD")
                    if wh_amt and wh_amt > 0
                    else None,
                    source_row_ref=f"{file_name}:income:{ridx}:{etype.value}",
                    classification_status="confirmed",
                    parse_confidence=0.85,
                )
            )
        if other_col:
            amt = _parse_decimal(row.get(other_col))
            if amt and amt > 0:
                events.append(
                    TaxEvent(
                        event_type=EventType.OTHER,
                        trade_date=trade_date,
                        gross_amount=Money(amount=amt, currency="USD"),
                        source_row_ref=f"{file_name}:income:{ridx}:other",
                        classification_status="ambiguous",
                        parse_confidence=0.7,
                    )
                )
    if events:
        warnings.append("futu: 已从年度收入汇总表解析（年末单日口径，建议与交易流水交叉核对）")
    return events, warnings, []


def parse_futu_csv(
    text: str,
    file_name: str,
) -> tuple[list[TaxEvent], list[str], list[dict[str, Any]]]:
    lines = text.splitlines()
    found = find_futu_header_row(lines)
    if not found:
        return [], ["futu: header row not found"], [
            {"code": "FUTU_NO_HEADER", "message": "missing Date/Type/Amount header"}
        ]

    mapping = _load_mapping()
    type_map = {str(k): str(v) for k, v in (mapping.get("typeMap") or {}).items()}
    skip_types = {str(s).lower() for s in (mapping.get("skipTypes") or [])}
    header_idx, header_row = found
    data_text = "\n".join(lines[header_idx:])
    reader = csv.DictReader(io.StringIO(data_text))
    headers = list(reader.fieldnames or header_row)
    norm_map = {_normalize_header(h): h for h in headers if h}

    date_col = _resolve_col(norm_map, "Date")
    type_col = _resolve_col(norm_map, "Type")
    amount_col = _resolve_col(norm_map, "Amount")
    symbol_col = _resolve_col(norm_map, "Symbol")
    tax_col = _resolve_col(norm_map, "Tax")
    desc_col = _resolve_col(norm_map, "Description")
    fee_col = _resolve_col(norm_map, "Fee")
    if not date_col or not type_col or not amount_col:
        return [], ["futu: missing required columns"], [
            {"code": "FUTU_COLUMNS", "message": str(norm_map)}
        ]

    warnings: list[str] = []
    errors: list[dict[str, Any]] = []
    events: list[TaxEvent] = []
    saw_trade = False

    for ridx, row in enumerate(reader, start=header_idx + 2):
        norm = {_normalize_header(k): v for k, v in row.items()}
        type_raw = str(norm.get(_normalize_header(type_col), "") or "").strip()
        if not type_raw:
            continue
        if type_raw.lower() in skip_types:
            continue
        symbol = None
        if symbol_col:
            symbol = str(norm.get(_normalize_header(symbol_col), "") or "").strip() or None
        event_type_str = type_map.get(type_raw)
        if not event_type_str:
            if infer_stock_comp_kind(compose_row_blob(type_raw, symbol or "")):
                event_type_str = EventType.STOCK_COMPENSATION.value
            else:
                warnings.append(f"futu: unknown type '{type_raw}' row {ridx}")
                continue
        try:
            event_type = EventType(event_type_str)
        except ValueError:
            continue

        trade_date = _parse_date(norm.get(_normalize_header(date_col)))
        amount = _parse_decimal(norm.get(_normalize_header(amount_col)))
        if not trade_date:
            continue

        if event_type == EventType.WITHHOLDING_TAX:
            wh_val = amount
            if tax_col and (wh_val is None or wh_val == 0):
                wh_val = _parse_decimal(norm.get(_normalize_header(tax_col)))
            if wh_val is None or wh_val == 0:
                continue
            events.append(
                TaxEvent(
                    event_type=EventType.WITHHOLDING_TAX,
                    trade_date=trade_date,
                    gross_amount=Money(amount=abs(wh_val), currency="USD"),
                    symbol=symbol,
                    source_row_ref=f"{file_name}:{ridx}",
                    classification_status="confirmed",
                    parse_confidence=0.95,
                )
            )
            continue

        if amount is None or amount == 0:
            continue

        wh = None
        if tax_col:
            wh_val = _parse_decimal(norm.get(_normalize_header(tax_col)))
            if wh_val and wh_val != 0:
                wh = Money(amount=abs(wh_val), currency="USD")

        fee = None
        if fee_col:
            fee_val = _parse_decimal(norm.get(_normalize_header(fee_col)))
            if fee_val and fee_val != 0:
                fee = Money(amount=abs(fee_val), currency="USD")

        status = "confirmed"
        if event_type == EventType.CAPITAL_GAIN:
            status = "inferred"
            saw_trade = True

        ev = TaxEvent(
            event_type=event_type,
            trade_date=trade_date,
            gross_amount=Money(amount=abs(amount), currency="USD"),
            withholding_tax=wh,
            fee=fee,
            symbol=symbol,
            source_row_ref=f"{file_name}:{ridx}",
            classification_status=status,
            parse_confidence=0.9 if status == "inferred" else 0.95,
        )
        desc = ""
        if desc_col:
            desc = str(norm.get(_normalize_header(desc_col), "") or "")
        ev = tag_event_if_stock_comp(ev, type_raw=type_raw, description=desc)
        events.append(ev)

    if saw_trade:
        warnings.append("futu: Trade 金额作为资本利得近似，建议核对已实现盈亏")
    return events, warnings, errors
