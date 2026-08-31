"""FIFO cost-basis matching for capital gains (财产转让所得)."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

Q = Decimal("0.01")
QTY = Decimal("0.00000001")


@dataclass
class TradeLeg:
    trade_date: str
    symbol: str
    side: str  # buy | sell | expire
    quantity: Decimal
    net_cash: Decimal
    fee: Decimal = Decimal("0")
    source_row_ref: str = ""
    category: str = ""
    sort_key: tuple[str, int] = field(default_factory=lambda: ("", 0))


@dataclass
class Lot:
    quantity: Decimal
    unit_cost: Decimal
    acquired_date: str
    source_row_ref: str = ""


@dataclass
class RealizedGain:
    trade_date: str
    symbol: str
    quantity: Decimal
    proceeds_usd: Decimal
    cost_basis_usd: Decimal
    fee_usd: Decimal
    gain_usd: Decimal
    source_row_ref: str
    classification_status: str = "confirmed"
    metadata: dict[str, Any] = field(default_factory=dict)


def _quantize_usd(val: Decimal) -> Decimal:
    return val.quantize(Q)


def _quantize_qty(val: Decimal) -> Decimal:
    return val.quantize(QTY)


def match_fifo(legs: list[TradeLeg]) -> tuple[list[RealizedGain], list[str]]:
    """Match buy/sell/expire legs per symbol using FIFO."""
    warnings: list[str] = []
    gains: list[RealizedGain] = []
    lots: dict[str, deque[Lot]] = {}

    ordered = sorted(legs, key=lambda leg: (leg.trade_date, leg.sort_key[1]))

    for leg in ordered:
        sym = leg.symbol
        if not sym:
            warnings.append(f"cost_basis: skip leg without symbol ({leg.source_row_ref})")
            continue

        if leg.side == "buy":
            qty = _quantize_qty(abs(leg.quantity))
            if qty <= 0:
                continue
            total_cost = _quantize_usd(abs(leg.net_cash))
            unit_cost = (total_cost / qty).quantize(QTY)
            lots.setdefault(sym, deque()).append(
                Lot(
                    quantity=qty,
                    unit_cost=unit_cost,
                    acquired_date=leg.trade_date,
                    source_row_ref=leg.source_row_ref,
                )
            )
            continue

        if leg.side not in ("sell", "expire"):
            warnings.append(f"cost_basis: unknown side '{leg.side}' ({leg.source_row_ref})")
            continue

        sell_qty = _quantize_qty(abs(leg.quantity))
        if sell_qty <= 0:
            continue

        proceeds = _quantize_usd(leg.net_cash if leg.side == "sell" else Decimal("0"))
        sell_fee = _quantize_usd(abs(leg.fee))
        queue = lots.setdefault(sym, deque())

        remaining = sell_qty
        cost_basis = Decimal("0")
        consumed_refs: list[str] = []

        while remaining > 0 and queue:
            lot = queue[0]
            take = min(remaining, lot.quantity)
            cost_basis += (take * lot.unit_cost).quantize(Q)
            consumed_refs.append(lot.source_row_ref)
            lot.quantity -= take
            remaining -= take
            if lot.quantity <= 0:
                queue.popleft()

        status = "confirmed"
        if remaining > 0:
            status = "ambiguous"
            warnings.append(
                f"cost_basis: {sym} sell qty {sell_qty} exceeds FIFO lots "
                f"(short {remaining}, {leg.source_row_ref})"
            )

        gain = _quantize_usd(proceeds - cost_basis)
        gains.append(
            RealizedGain(
                trade_date=leg.trade_date,
                symbol=sym,
                quantity=sell_qty,
                proceeds_usd=proceeds,
                cost_basis_usd=_quantize_usd(cost_basis),
                fee_usd=sell_fee,
                gain_usd=gain,
                source_row_ref=leg.source_row_ref,
                classification_status=status,
                metadata={
                    "costBasisMethod": "fifo",
                    "lotSourceRefs": consumed_refs,
                    "disposalType": "expiration" if leg.side == "expire" else "sell",
                    "category": leg.category,
                    "assetSide": leg.side,
                },
            )
        )

    return gains, warnings


def fifo_remaining_lots_as_of(
    legs: list[TradeLeg],
    as_of_date: str,
) -> dict[str, list[Lot]]:
    """FIFO lots still open after processing legs with trade_date <= as_of_date."""
    lots: dict[str, deque[Lot]] = {}
    ordered = sorted(
        (leg for leg in legs if leg.trade_date <= as_of_date),
        key=lambda leg: (leg.trade_date, leg.sort_key[1]),
    )
    for leg in ordered:
        sym = leg.symbol
        if not sym:
            continue
        if leg.side == "buy":
            qty = _quantize_qty(abs(leg.quantity))
            if qty <= 0:
                continue
            total_cost = _quantize_usd(abs(leg.net_cash))
            unit_cost = (total_cost / qty).quantize(QTY)
            lots.setdefault(sym, deque()).append(
                Lot(
                    quantity=qty,
                    unit_cost=unit_cost,
                    acquired_date=leg.trade_date,
                    source_row_ref=leg.source_row_ref,
                )
            )
            continue
        if leg.side not in ("sell", "expire"):
            continue
        sell_qty = _quantize_qty(abs(leg.quantity))
        if sell_qty <= 0:
            continue
        queue = lots.setdefault(sym, deque())
        remaining = sell_qty
        while remaining > 0 and queue:
            lot = queue[0]
            take = min(remaining, lot.quantity)
            lot.quantity -= take
            remaining -= take
            if lot.quantity <= 0:
                queue.popleft()
    return {sym: [lot for lot in queue if lot.quantity > 0] for sym, queue in lots.items()}


def lot_cost_for_quantity(lots: list[Lot], quantity: Decimal) -> tuple[Decimal, bool]:
    """Consume lots FIFO-style; return (cost_basis_usd, fully_matched)."""
    need = _quantize_qty(abs(quantity))
    if need <= 0:
        return Decimal("0"), True
    cost = Decimal("0")
    for lot in lots:
        if need <= 0:
            break
        take = min(need, lot.quantity)
        cost += (take * lot.unit_cost).quantize(Q)
        need -= take
    return _quantize_usd(cost), need <= 0


def sum_realized_gain_cny(events: list[Any]) -> Decimal:
    """Sum all disposal realized gains/losses in CNY for the tax year."""
    return sum((ev.resolved_amount_cny() for ev in events), Decimal("0")).quantize(Q)


def taxable_gain_cny(events: list[Any]) -> Decimal:
    """境外财产转让所得：同纳税年度内盈亏相抵后，按净额计税（净亏损按 0）。

    征管实操：国家税务总局专家解读（2024）明确境外股票交易允许按纳税年度
    盈亏互抵，不得跨年结转。参见 docs/cn-overseas-property-transfer-netting-v1.md
    """
    net = sum_realized_gain_cny(events)
    return net if net > 0 else Decimal("0")


def per_disposal_positive_gain_cny(events: list[Any]) -> Decimal:
    """辅助对照：按次 max(损益,0) 汇总（非默认申报口径）。"""
    total = Decimal("0")
    for ev in events:
        amt = ev.resolved_amount_cny()
        if amt > 0:
            total += amt.quantize(Q)
    return total.quantize(Q)
