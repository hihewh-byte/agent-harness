"""Detect RSU / ESPP rows in broker statements and tag TaxEvent metadata."""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
from typing import Any

from tax_agent.models import EventType, Money, TaxEvent

_KEYWORDS = (
    "rsu",
    "espp",
    "vest",
    "grant",
    "stock plan",
    "equity award",
    "restricted stock",
    "share award",
    "lapse release",
    "employee stock purchase",
)

_SALE_HINTS = ("sell", "sold", "sale", "you sold", "disposal")
_VEST_HINTS = ("vest", "grant", "award", "release", "lapse", "shares vested", "share award")
_ESPP_HINTS = ("espp", "employee stock purchase", "purchase plan")


def compose_row_blob(*parts: str | None) -> str:
    return " ".join(str(p).strip().lower() for p in parts if p and str(p).strip())


def matches_stock_comp_text(blob: str) -> bool:
    text = (blob or "").lower()
    return any(k in text for k in _KEYWORDS)


def infer_stock_comp_kind(blob: str) -> str | None:
    text = (blob or "").lower()
    if not matches_stock_comp_text(text):
        return None
    if any(h in text for h in _ESPP_HINTS):
        return "espp_discount"
    if any(h in text for h in _SALE_HINTS):
        return "rsu_sale"
    if any(h in text for h in _VEST_HINTS):
        return "rsu_vest"
    return "rsu_vest"


def apply_stock_comp_detection(
    ev: TaxEvent,
    *,
    row_blob: str = "",
    cost_basis_usd: Decimal | None = None,
    proceeds_usd: Decimal | None = None,
) -> tuple[TaxEvent, bool]:
    """Reclassify event as STOCK_COMPENSATION when row text matches RSU/ESPP patterns."""
    if ev.event_type in (EventType.WITHHOLDING_TAX, EventType.FEE):
        return ev, False

    blob = row_blob or compose_row_blob(ev.symbol, ev.source_row_ref)
    kind = infer_stock_comp_kind(blob)
    if not kind and ev.event_type != EventType.STOCK_COMPENSATION:
        return ev, False
    if not kind:
        kind = "rsu_vest"

    meta: dict[str, Any] = dict(ev.metadata or {})
    sc: dict[str, Any] = dict(meta.get("stockComp") or {})
    sc["kind"] = kind
    sc["detectedFrom"] = "broker_parser"
    if cost_basis_usd is not None:
        sc["costBasisUsd"] = str(cost_basis_usd)
    if proceeds_usd is not None:
        sc["proceedsUsd"] = str(proceeds_usd)
    meta["stockComp"] = sc

    gross = ev.gross_amount
    if kind == "rsu_sale" and proceeds_usd is not None and cost_basis_usd is not None:
        gain = (proceeds_usd - cost_basis_usd).quantize(Decimal("0.01"))
        gross = Money(amount=gain, currency="USD")

    updated = replace(
        ev,
        event_type=EventType.STOCK_COMPENSATION,
        gross_amount=gross,
        metadata=meta,
        classification_status="inferred",
        parse_confidence=min(ev.parse_confidence, 0.82),
    )
    return updated, True


def tag_event_if_stock_comp(
    ev: TaxEvent,
    *,
    action: str = "",
    description: str = "",
    type_raw: str = "",
    cost_basis_usd: Decimal | None = None,
    proceeds_usd: Decimal | None = None,
) -> TaxEvent:
    blob = compose_row_blob(action, description, type_raw, ev.symbol)
    tagged, _ = apply_stock_comp_detection(
        ev,
        row_blob=blob,
        cost_basis_usd=cost_basis_usd,
        proceeds_usd=proceeds_usd,
    )
    return tagged
