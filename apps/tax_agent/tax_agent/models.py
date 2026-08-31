from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import uuid4


class EventType(str, Enum):
    DIVIDEND = "DIVIDEND"
    CAPITAL_GAIN = "CAPITAL_GAIN"
    INTEREST = "INTEREST"
    WITHHOLDING_TAX = "WITHHOLDING_TAX"
    FEE = "FEE"
    STOCK_COMPENSATION = "STOCK_COMPENSATION"
    OTHER = "OTHER"


class ResidentStatus(str, Enum):
    CN_TAX_RESIDENT = "cn_tax_resident"
    NON_RESIDENT = "non_resident"
    UNCERTAIN = "uncertain"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass
class Money:
    amount: Decimal
    currency: str = "USD"

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Money:
        return cls(amount=Decimal(str(d["amount"])), currency=d.get("currency", "USD"))


@dataclass
class TaxEvent:
    event_type: EventType
    trade_date: str
    gross_amount: Money | None = None
    withholding_tax: Money | None = None
    fee: Money | None = None
    amount_cny: Decimal | None = None
    fx_rate_used: Decimal | None = None
    fx_rate_source: str | None = None
    event_id: str = field(default_factory=lambda: str(uuid4()))
    classification_status: str = "confirmed"
    symbol: str | None = None
    source_row_ref: str = ""
    parse_confidence: float = 1.0
    metadata: dict[str, Any] | None = None

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> TaxEvent:
        gross = Money.from_dict(d["grossAmount"]) if d.get("grossAmount") else None
        wh = Money.from_dict(d["withholdingTax"]) if d.get("withholdingTax") else None
        amount_cny = Decimal(str(d["amountCny"])) if d.get("amountCny") is not None else None
        fx = Decimal(str(d["fxRateUsed"])) if d.get("fxRateUsed") is not None else None
        fee = Money.from_dict(d["fee"]) if d.get("fee") else None
        return cls(
            event_id=d.get("eventId", str(uuid4())),
            event_type=EventType(d["eventType"]),
            trade_date=d["tradeDate"],
            gross_amount=gross,
            withholding_tax=wh,
            fee=fee,
            amount_cny=amount_cny,
            fx_rate_used=fx,
            classification_status=d.get("classificationStatus", "confirmed"),
            symbol=d.get("symbol"),
            source_row_ref=d.get("sourceRowRef", ""),
            parse_confidence=float(d.get("parseConfidence", 1.0)),
            metadata=_event_metadata(d),
        )

    def resolved_amount_cny(self) -> Decimal:
        if self.amount_cny is not None:
            return self.amount_cny
        if self.gross_amount and self.fx_rate_used:
            return self.gross_amount.amount * self.fx_rate_used
        if self.gross_amount:
            raise ValueError(f"event {self.event_id} missing amountCny or fxRateUsed")
        return Decimal("0")


def _event_metadata(d: dict[str, Any]) -> dict[str, Any] | None:
    meta: dict[str, Any] = {}
    if d.get("stockComp"):
        meta["stockComp"] = d["stockComp"]
    if d.get("metadata") and isinstance(d["metadata"], dict):
        meta.update(d["metadata"])
    return meta or None


@dataclass
class FormulaStep:
    step_index: int
    label: str
    expression: str
    output: Any
    inputs: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        out = self.output
        if isinstance(out, Decimal):
            out = str(out.quantize(Decimal("0.01")))
        return {
            "stepIndex": self.step_index,
            "label": self.label,
            "expression": self.expression,
            "inputs": self.inputs,
            "output": out,
        }


@dataclass
class TaxLineItem:
    tax_category: str
    taxable_income_cny: Decimal
    tax_rate: Decimal
    tax_due_cny: Decimal
    foreign_tax_paid_cny: Decimal
    credit_allowed_cny: Decimal
    net_tax_due_cny: Decimal
    source_event_ids: list[str]
    formula_steps: list[FormulaStep]
    line_id: str = field(default_factory=lambda: str(uuid4()))

    def to_dict(self) -> dict[str, Any]:
        q = Decimal("0.01")
        return {
            "lineId": self.line_id,
            "taxCategory": self.tax_category,
            "taxableIncomeCny": str(self.taxable_income_cny.quantize(q)),
            "taxRate": float(self.tax_rate),
            "taxDueCny": str(self.tax_due_cny.quantize(q)),
            "foreignTaxPaidCny": str(self.foreign_tax_paid_cny.quantize(q)),
            "creditAllowedCny": str(self.credit_allowed_cny.quantize(q)),
            "netTaxDueCny": str(self.net_tax_due_cny.quantize(q)),
            "sourceEventIds": self.source_event_ids,
            "formulaSteps": [s.to_dict() for s in self.formula_steps],
        }
