from __future__ import annotations

import json
from decimal import Decimal
from typing import Any

from tax_agent.models import EventType, Money, TaxEvent


class _DecimalEncoder(json.JSONEncoder):
    def default(self, o: Any) -> Any:
        if isinstance(o, Decimal):
            return str(o)
        return super().default(o)


def event_to_dict(ev: TaxEvent) -> dict[str, Any]:
    d: dict[str, Any] = {
        "eventId": ev.event_id,
        "eventType": ev.event_type.value,
        "tradeDate": ev.trade_date,
        "classificationStatus": ev.classification_status,
        "sourceRowRef": ev.source_row_ref,
        "parseConfidence": ev.parse_confidence,
    }
    if ev.symbol:
        d["symbol"] = ev.symbol
    if ev.gross_amount:
        d["grossAmount"] = {"amount": str(ev.gross_amount.amount), "currency": ev.gross_amount.currency}
    if ev.withholding_tax:
        d["withholdingTax"] = {
            "amount": str(ev.withholding_tax.amount),
            "currency": ev.withholding_tax.currency,
        }
    if ev.fee:
        d["fee"] = {"amount": str(ev.fee.amount), "currency": ev.fee.currency}
    if ev.amount_cny is not None:
        d["amountCny"] = str(ev.amount_cny)
    if ev.fx_rate_used is not None:
        d["fxRateUsed"] = float(ev.fx_rate_used)
    if ev.metadata and ev.metadata.get("stockComp"):
        d["stockComp"] = ev.metadata["stockComp"]
    return d


def event_from_dict(d: dict[str, Any]) -> TaxEvent:
    fee = None
    if d.get("fee"):
        fee = Money.from_dict(d["fee"])
    ev = TaxEvent.from_dict(d)
    ev.fee = fee
    ev.source_row_ref = d.get("sourceRowRef", "")
    ev.parse_confidence = float(d.get("parseConfidence", 1.0))
    return ev


def encode_event(ev: TaxEvent) -> str:
    return json.dumps(event_to_dict(ev), ensure_ascii=False, cls=_DecimalEncoder)


def decode_event(raw: str) -> TaxEvent:
    return event_from_dict(json.loads(raw))
