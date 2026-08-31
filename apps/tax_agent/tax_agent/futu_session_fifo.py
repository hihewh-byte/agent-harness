"""Cross-year FIFO rematch for Futu tax workbook uploads in one session."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from tax_agent.cost_basis import RealizedGain, TradeLeg, match_fifo
from tax_agent.models import EventType, Money, TaxEvent


def leg_to_dict(leg: TradeLeg) -> dict[str, Any]:
    return {
        "tradeDate": leg.trade_date,
        "symbol": leg.symbol,
        "side": leg.side,
        "quantity": str(leg.quantity),
        "netCash": str(leg.net_cash),
        "fee": str(leg.fee),
        "sourceRowRef": leg.source_row_ref,
        "category": leg.category,
        "sortKey": leg.sort_key[1],
    }


def leg_from_dict(d: dict[str, Any]) -> TradeLeg:
    return TradeLeg(
        trade_date=str(d["tradeDate"]),
        symbol=str(d.get("symbol") or ""),
        side=str(d["side"]),
        quantity=Decimal(str(d["quantity"])),
        net_cash=Decimal(str(d["netCash"])),
        fee=Decimal(str(d.get("fee") or "0")),
        source_row_ref=str(d.get("sourceRowRef") or ""),
        category=str(d.get("category") or ""),
        sort_key=(str(d["tradeDate"]), int(d.get("sortKey") or 0)),
    )


def realized_gains_to_events(realized: list[RealizedGain]) -> list[TaxEvent]:
    """Map FIFO disposals to CAPITAL_GAIN events.

    SSOT: ``gross_amount`` = ``gain_usd`` (proceeds − cost_basis). Sell commission is on
    ``fee`` for filing-table「合理费用」; do not subtract again in ``gross_amount``.
    See docs/agent-consensus-v1.md §2.
    """
    events: list[TaxEvent] = []
    for rg in realized:
        if rg.gain_usd == 0:
            continue
        meta = dict(rg.metadata)
        meta.update(
            {
                "proceedsUsd": str(rg.proceeds_usd),
                "grossProceedsUsd": str(rg.proceeds_usd + rg.fee_usd),
                "costBasisUsd": str(rg.cost_basis_usd),
                "feeUsd": str(rg.fee_usd),
                "realizedGainUsd": str(rg.gain_usd),
                "quantity": str(rg.quantity),
            }
        )
        events.append(
            TaxEvent(
                event_type=EventType.CAPITAL_GAIN,
                trade_date=rg.trade_date,
                gross_amount=Money(amount=rg.gain_usd, currency="USD"),
                fee=Money(amount=rg.fee_usd, currency="USD") if rg.fee_usd else None,
                symbol=rg.symbol,
                source_row_ref=rg.source_row_ref,
                classification_status=rg.classification_status,
                parse_confidence=0.95 if rg.classification_status == "confirmed" else 0.75,
                metadata=meta,
            )
        )
    return events


def _opening_gap_warnings(
    legs: list[TradeLeg],
    openings: list[dict[str, Any]],
) -> list[str]:
    warnings: list[str] = []
    if not openings:
        return warnings

    first_by_sym: dict[str, TradeLeg] = {}
    for leg in sorted(legs, key=lambda x: (x.trade_date, x.sort_key[1])):
        if leg.symbol and leg.symbol not in first_by_sym:
            first_by_sym[leg.symbol] = leg

    for op in openings:
        sym = str(op.get("symbol") or "")
        if not sym:
            continue
        qty = Decimal(str(op.get("quantity") or "0"))
        if qty <= 0:
            continue
        first = first_by_sym.get(sym)
        if first and first.side in ("sell", "expire"):
            warnings.append(
                f"futu: {sym} 在流水首笔为卖出，但税表含期初持仓 {qty} 股；"
                f"未上传买入年度账单则成本可能不完整（持仓总览价格为期市值，非买入成本）"
            )
    return warnings


def collect_merged_legs(packages: list[dict[str, Any]]) -> list[TradeLeg]:
    legs: list[TradeLeg] = []
    seen: set[str] = set()
    for pkg in sorted(packages, key=lambda p: int(p.get("taxYear") or 0)):
        for raw in pkg.get("legs") or []:
            ref = str(raw.get("sourceRowRef") or "")
            if ref and ref in seen:
                continue
            if ref:
                seen.add(ref)
            legs.append(leg_from_dict(raw))
    return legs


def rematch_futu_capital_gains(
    packages: list[dict[str, Any]],
    other_events: list[TaxEvent],
) -> tuple[list[TaxEvent], list[str]]:
    """Run unified FIFO across all uploaded Futu tax packages; keep non-CG events."""
    if not packages:
        return list(other_events), []

    legs = collect_merged_legs(packages)
    if not legs:
        return list(other_events), ["futu: 无交易流水可供 FIFO 匹配"]

    openings: list[dict[str, Any]] = []
    for pkg in packages:
        openings.extend(pkg.get("openingPositions") or [])

    realized, fifo_warnings = match_fifo(legs)
    warnings = list(fifo_warnings)
    warnings.extend(_opening_gap_warnings(legs, openings))

    years = sorted({int(p.get("taxYear") or 0) for p in packages if p.get("taxYear")})
    if len(years) > 1:
        warnings.append(
            f"futu: 已合并 {years[0]}–{years[-1]} 年共 {len(packages)} 份税表、"
            f"{len(legs)} 条流水做跨年度 FIFO（处置损益按卖出日归属纳税年度）"
        )

    cg_events = realized_gains_to_events(realized)
    if cg_events:
        total = sum(e.gross_amount.amount for e in cg_events if e.gross_amount)
        warnings.append(
            f"futu: 跨年度 FIFO 完成，{len(cg_events)} 笔已实现损益，合计 {total} USD"
        )
    return list(other_events) + cg_events, warnings


def append_futu_tax_package(
    stored_quality: dict[str, Any],
    parse_quality: dict[str, Any],
    *,
    file_hash: str,
) -> bool:
    pkg = parse_quality.get("futuTaxPackage")
    if not pkg:
        return False
    pkg = dict(pkg)
    pkg["fileHash"] = file_hash
    packages: list[dict[str, Any]] = stored_quality.setdefault("futuTaxPackages", [])
    if any(p.get("fileHash") == file_hash for p in packages):
        return False
    packages.append(pkg)
    return True


def finalize_futu_session_dataset(
    stored_events: list[TaxEvent],
    data_quality: dict[str, Any],
) -> tuple[list[TaxEvent], list[str]]:
    packages = data_quality.get("futuTaxPackages") or []
    inferred_cg = [
        e
        for e in stored_events
        if e.event_type == EventType.CAPITAL_GAIN and e.classification_status == "inferred"
    ]
    if not packages:
        if inferred_cg:
            return stored_events, [
                "futu: 检测到按卖出金额近似资本利得（未走 FIFO）；"
                "请确认上传的是富途税表 xlsx（含证券-交易流水），并在侧栏选择富途模板后重新上传"
            ]
        return stored_events, []
    other = [e for e in stored_events if e.event_type != EventType.CAPITAL_GAIN]
    events, warnings = rematch_futu_capital_gains(packages, other)
    if inferred_cg and not any("跨年度 FIFO" in w or "FIFO 完成" in w for w in warnings):
        warnings.append(
            f"futu: 已丢弃 {len(inferred_cg)} 条近似资本利得，改用 {len(packages)} 份税表流水做 FIFO"
        )
    return events, warnings
