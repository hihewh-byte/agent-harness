"""Domestic comprehensive income (综合所得) — progressive tax + merge with foreign lines."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from tax_agent.models import FormulaStep, TaxLineItem

Q = Decimal("0.01")
STANDARD_DEDUCTION_CNY = Decimal("60000")

# (upper_bound_inclusive, rate, quick_deduction)
_PROGRESSIVE_BRACKETS: list[tuple[Decimal, Decimal, Decimal]] = [
    (Decimal("36000"), Decimal("0.03"), Decimal("0")),
    (Decimal("144000"), Decimal("0.10"), Decimal("2520")),
    (Decimal("300000"), Decimal("0.20"), Decimal("16920")),
    (Decimal("420000"), Decimal("0.25"), Decimal("31920")),
    (Decimal("660000"), Decimal("0.30"), Decimal("52920")),
    (Decimal("960000"), Decimal("0.35"), Decimal("85920")),
    (Decimal("999999999"), Decimal("0.45"), Decimal("181920")),
]


@dataclass
class DomesticIncomeInput:
    """User-declared domestic comprehensive income (CNY)."""

    wage_salary_cny: Decimal = Decimal("0")
    labor_service_cny: Decimal = Decimal("0")
    author_remuneration_cny: Decimal = Decimal("0")
    royalty_cny: Decimal = Decimal("0")
    social_insurance_cny: Decimal = Decimal("0")
    special_additional_deduction_cny: Decimal = Decimal("0")
    other_deduction_cny: Decimal = Decimal("0")
    withheld_tax_cny: Decimal = Decimal("0")
    taxable_income_override_cny: Decimal | None = None

    def is_empty(self) -> bool:
        if self.taxable_income_override_cny is not None:
            return self.taxable_income_override_cny <= 0
        parts = (
            self.wage_salary_cny,
            self.labor_service_cny,
            self.author_remuneration_cny,
            self.royalty_cny,
        )
        return all(p <= 0 for p in parts)


def parse_domestic_income(data: dict[str, Any] | None) -> DomesticIncomeInput | None:
    if not data:
        return None

    def _dec(key: str, default: str = "0") -> Decimal:
        v = data.get(key)
        if v is None or v == "":
            return Decimal(default)
        return Decimal(str(v))

    override = data.get("taxableIncomeOverrideCny")
    return DomesticIncomeInput(
        wage_salary_cny=_dec("wageSalaryCny"),
        labor_service_cny=_dec("laborServiceCny"),
        author_remuneration_cny=_dec("authorRemunerationCny"),
        royalty_cny=_dec("royaltyCny"),
        social_insurance_cny=_dec("socialInsuranceCny"),
        special_additional_deduction_cny=_dec("specialAdditionalDeductionCny"),
        other_deduction_cny=_dec("otherDeductionCny"),
        withheld_tax_cny=_dec("withheldTaxCny"),
        taxable_income_override_cny=(
            Decimal(str(override)) if override is not None and override != "" else None
        ),
    )


def comprehensive_gross_cny(inp: DomesticIncomeInput) -> Decimal:
    """四项综合所得收入额（劳务/稿酬/特许权使用费按法定费用扣除后并入）。"""
    labor = (inp.labor_service_cny * Decimal("0.8")).quantize(Q)
    author = (inp.author_remuneration_cny * Decimal("0.56")).quantize(Q)
    royalty = (inp.royalty_cny * Decimal("0.8")).quantize(Q)
    return (inp.wage_salary_cny + labor + author + royalty).quantize(Q)


def comprehensive_taxable_cny(inp: DomesticIncomeInput) -> Decimal:
    if inp.taxable_income_override_cny is not None:
        return max(Decimal("0"), inp.taxable_income_override_cny).quantize(Q)
    gross = comprehensive_gross_cny(inp)
    deductions = (
        STANDARD_DEDUCTION_CNY
        + inp.social_insurance_cny
        + inp.special_additional_deduction_cny
        + inp.other_deduction_cny
    )
    return max(Decimal("0"), gross - deductions).quantize(Q)


def progressive_tax_cny(taxable: Decimal) -> tuple[Decimal, Decimal]:
    """Return (tax_due, effective_rate)."""
    if taxable <= 0:
        return Decimal("0"), Decimal("0")
    for upper, rate, quick in _PROGRESSIVE_BRACKETS:
        if taxable <= upper:
            due = (taxable * rate - quick).quantize(Q)
            eff = (due / taxable).quantize(Decimal("0.0001")) if taxable else Decimal("0")
            return max(Decimal("0"), due), eff
    return Decimal("0"), Decimal("0")


def build_domestic_line_item(inp: DomesticIncomeInput) -> tuple[TaxLineItem, list[str], dict[str, str]]:
    """Build domestic comprehensive tax line + notes + detail dict for audit."""
    notes: list[str] = []
    gross = comprehensive_gross_cny(inp)
    taxable = comprehensive_taxable_cny(inp)
    tax_due, eff_rate = progressive_tax_cny(taxable)
    withheld = min(inp.withheld_tax_cny, tax_due).quantize(Q)
    net = (tax_due - withheld).quantize(Q)

    if inp.taxable_income_override_cny is not None:
        notes.append("境内综合所得：使用用户指定的应纳税所得额覆盖值。")
    else:
        notes.append(
            f"境内综合所得：收入额 {gross} 元，减除费用/专项扣除后应纳税所得额 {taxable} 元"
            f"（基本减除 60000 元已计入）。"
        )
    notes.append("境外分类所得与境内综合所得分别计税，本摘要合计为年度汇算参考。")

    steps = [
        FormulaStep(1, "comprehensive_gross_cny", "sum(income_items)", gross, {"standardDeduction": "60000"}),
        FormulaStep(2, "comprehensive_taxable_cny", "gross - deductions", taxable),
        FormulaStep(3, "progressive_tax", "bracket_table", tax_due, {"effectiveRate": float(eff_rate)}),
        FormulaStep(4, "domestic_withheld", "min(withheld, tax_due)", withheld),
        FormulaStep(5, "domestic_net_due", "tax_due - withheld", net),
    ]
    line = TaxLineItem(
        tax_category="cn_comprehensive_domestic",
        taxable_income_cny=taxable,
        tax_rate=eff_rate,
        tax_due_cny=tax_due,
        foreign_tax_paid_cny=Decimal("0"),
        credit_allowed_cny=withheld,
        net_tax_due_cny=net,
        source_event_ids=[],
        formula_steps=steps,
    )
    detail = {
        "comprehensiveGrossCny": str(gross),
        "comprehensiveTaxableCny": str(taxable),
        "domesticTaxDueCny": str(tax_due),
        "domesticWithheldCny": str(withheld),
        "domesticNetTaxDueCny": str(net),
    }
    return line, notes, detail


def merge_foreign_domestic_summaries(
    foreign: dict[str, str],
    domestic_detail: dict[str, str],
) -> dict[str, str]:
    """Combine foreign classified summary with domestic comprehensive."""
    f_net = Decimal(foreign.get("netTaxDueCny", "0"))
    d_net = Decimal(domestic_detail.get("domesticNetTaxDueCny", "0"))
    f_tax = Decimal(foreign.get("taxDueCny", "0"))
    d_tax = Decimal(domestic_detail.get("domesticTaxDueCny", "0"))
    f_taxable = Decimal(foreign.get("taxableIncomeCny", "0"))
    d_taxable = Decimal(domestic_detail.get("comprehensiveTaxableCny", "0"))

    merged = dict(foreign)
    merged["foreignNetTaxDueCny"] = str(f_net.quantize(Q))
    merged["domesticTaxDueCny"] = domestic_detail.get("domesticTaxDueCny", "0")
    merged["domesticNetTaxDueCny"] = domestic_detail.get("domesticNetTaxDueCny", "0")
    merged["domesticTaxableIncomeCny"] = domestic_detail.get("comprehensiveTaxableCny", "0")
    merged["taxableIncomeCny"] = str((f_taxable + d_taxable).quantize(Q))
    merged["taxDueCny"] = str((f_tax + d_tax).quantize(Q))
    merged["netTaxDueCny"] = str((f_net + d_net).quantize(Q))
    return merged
