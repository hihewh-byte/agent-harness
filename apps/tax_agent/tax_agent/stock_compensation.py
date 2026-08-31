"""RSU / ESPP stock compensation — v1 taxable amount + cost basis helpers."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from tax_agent.models import EventType, FormulaStep, TaxEvent, TaxLineItem

Q = Decimal("0.01")

_KEYWORDS = ("rsu", "espp", "vest", "grant", "stock plan", "equity award", "restricted stock")


def _keyword_blob(ev: TaxEvent) -> str:
    return " ".join(str(x).lower() for x in (ev.symbol, ev.source_row_ref) if x)


def matches_stock_compensation_keywords(ev: TaxEvent) -> bool:
    blob = _keyword_blob(ev)
    return any(k in blob for k in _KEYWORDS)


def is_stock_compensation_event(ev: TaxEvent) -> bool:
    if ev.event_type == EventType.STOCK_COMPENSATION:
        return True
    if ev.event_type in (EventType.WITHHOLDING_TAX, EventType.FEE):
        return False
    return matches_stock_compensation_keywords(ev)


def stock_comp_metadata(ev: TaxEvent) -> dict[str, Any]:
    meta = ev.metadata or {}
    sc = meta.get("stockComp")
    return sc if isinstance(sc, dict) else {}


def stock_comp_kind(ev: TaxEvent) -> str:
    sc = stock_comp_metadata(ev)
    kind = str(sc.get("kind") or "").strip().lower()
    if kind in ("rsu_vest", "espp_discount", "rsu_sale"):
        return kind
    blob = _keyword_blob(ev)
    if "espp" in blob:
        return "espp_discount"
    if "sale" in blob or "sell" in blob:
        return "rsu_sale"
    return "rsu_vest"


def _meta_amount_cny(sc: dict[str, Any], cny_key: str, usd_key: str, fx: Decimal | None) -> Decimal | None:
    raw_cny = sc.get(cny_key)
    if raw_cny is not None and str(raw_cny).strip() != "":
        return Decimal(str(raw_cny)).quantize(Q)
    raw_usd = sc.get(usd_key)
    if raw_usd is not None and str(raw_usd).strip() != "" and fx:
        return (Decimal(str(raw_usd)) * fx).quantize(Q)
    return None


def taxable_income_cny(ev: TaxEvent) -> Decimal:
    """Compute taxable CNY for a stock compensation event."""
    kind = stock_comp_kind(ev)
    sc = stock_comp_metadata(ev)
    fx = ev.fx_rate_used
    if kind == "rsu_sale":
        proceeds = _meta_amount_cny(sc, "proceedsCny", "proceedsUsd", fx)
        basis = _meta_amount_cny(sc, "costBasisCny", "costBasisUsd", fx)
        if proceeds is not None and basis is not None:
            return max(Decimal("0"), (proceeds - basis).quantize(Q))
        return max(Decimal("0"), ev.resolved_amount_cny().quantize(Q))
    if kind == "espp_discount":
        discount = sc.get("discountCny")
        if discount is not None and str(discount).strip() != "":
            return max(Decimal("0"), Decimal(str(discount)).quantize(Q))
        return max(Decimal("0"), ev.resolved_amount_cny().quantize(Q))
    return max(Decimal("0"), ev.resolved_amount_cny().quantize(Q))


def partition_events(events: list[TaxEvent]) -> tuple[list[TaxEvent], list[TaxEvent]]:
    stock: list[TaxEvent] = []
    regular: list[TaxEvent] = []
    for ev in events:
        if is_stock_compensation_event(ev):
            stock.append(ev)
        else:
            regular.append(ev)
    return stock, regular


def build_stock_compensation_line(
    events: list[TaxEvent],
    *,
    tax_rate: Decimal,
    category_id: str = "cn_stock_compensation",
) -> tuple[TaxLineItem | None, list[str]]:
    if not events:
        return None, []

    notes: list[str] = []
    taxable_parts: list[Decimal] = []
    foreign = Decimal("0")
    for ev in events:
        kind = stock_comp_kind(ev)
        part = taxable_income_cny(ev)
        taxable_parts.append(part)
        if ev.withholding_tax and ev.fx_rate_used:
            foreign += (ev.withholding_tax.amount * ev.fx_rate_used).quantize(Q)
        notes.append(
            f"股权激励 {ev.symbol or '—'} ({kind})：应税 {part} 元"
            f"（来源：{ev.source_row_ref or ev.event_id[:8]}）"
        )

    taxable = sum(taxable_parts, Decimal("0")).quantize(Q)
    if taxable <= 0:
        notes.append("股权激励事件未形成正应税收入，请专家核对归属日与成本基础。")
        return None, notes

    tax_due = (taxable * tax_rate).quantize(Q)
    credit = min(foreign, tax_due)
    net = (tax_due - credit).quantize(Q)
    steps = [
        FormulaStep(
            1,
            "stock_comp_taxable",
            "sum(vest_fmv|espp_discount|sale_gain)",
            taxable,
            {"eventCount": len(events)},
        ),
        FormulaStep(2, "apply_tax_rate", "taxable * rate", tax_due, {"rate": float(tax_rate)}),
        FormulaStep(3, "allocate_foreign_tax", "sum(withholding)", foreign),
        FormulaStep(4, "apply_credit_limit", "min(foreign, tax_due)", credit),
        FormulaStep(5, "net_tax_due", "tax_due - credit", net),
    ]
    line = TaxLineItem(
        tax_category=category_id,
        taxable_income_cny=taxable,
        tax_rate=tax_rate,
        tax_due_cny=tax_due,
        foreign_tax_paid_cny=foreign,
        credit_allowed_cny=credit,
        net_tax_due_cny=net,
        source_event_ids=[e.event_id for e in events],
        formula_steps=steps,
    )
    notes.append(
        "股权激励税额为 v1 草稿（归属日 FMV / ESPP 折扣 / 出售增益），"
        "已触发 R007，正式申报前须专家复核成本基础与境内合并口径。"
    )
    return line, notes
