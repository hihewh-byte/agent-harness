from __future__ import annotations

import csv
import io

from tax_agent.event_codec import event_to_dict
from tax_agent.models import TaxEvent


def events_to_csv(events: list[TaxEvent]) -> str:
    buf = io.StringIO()
    fields = [
        "eventId",
        "eventType",
        "tradeDate",
        "symbol",
        "grossAmount",
        "currency",
        "withholdingTax",
        "amountCny",
        "fxRateUsed",
        "classificationStatus",
        "sourceRowRef",
    ]
    writer = csv.DictWriter(buf, fieldnames=fields)
    writer.writeheader()
    for ev in events:
        d = event_to_dict(ev)
        gross = d.get("grossAmount") or {}
        wh = d.get("withholdingTax") or {}
        writer.writerow(
            {
                "eventId": d.get("eventId"),
                "eventType": d.get("eventType"),
                "tradeDate": d.get("tradeDate"),
                "symbol": d.get("symbol", ""),
                "grossAmount": gross.get("amount", ""),
                "currency": gross.get("currency", ""),
                "withholdingTax": wh.get("amount", ""),
                "amountCny": d.get("amountCny", ""),
                "fxRateUsed": d.get("fxRateUsed", ""),
                "classificationStatus": d.get("classificationStatus"),
                "sourceRowRef": d.get("sourceRowRef"),
            }
        )
    return buf.getvalue()
