"""境外股息/利息分类所得申报汇总（与财产转让四列分税目，共识 §2.4）。"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from tax_agent.filing_table import TAX_RATE, _fx_for_tax_year
from tax_agent.fx_rates import DEFAULT_FX, FxRateProvider
from tax_agent.models import EventType, TaxEvent

Q = Decimal("0.01")

_CATEGORY_BY_EVENT: dict[EventType, tuple[str, str]] = {
    EventType.DIVIDEND: ("cn_interest_dividend", "利息、股息、红利所得"),
    EventType.INTEREST: ("cn_interest", "利息所得"),
}


@dataclass
class IncomeCategoryLine:
    category_id: str
    label_zh: str
    event_count: int = 0
    gross_usd: Decimal = Decimal("0")
    gross_cny: Decimal = Decimal("0")
    taxable_cny: Decimal = Decimal("0")
    tax_due_cny: Decimal = Decimal("0")
    foreign_tax_cny: Decimal = Decimal("0")
    credit_allowed_cny: Decimal = Decimal("0")
    net_tax_due_cny: Decimal = Decimal("0")

    def quantize(self) -> None:
        self.gross_usd = self.gross_usd.quantize(Q)
        self.gross_cny = self.gross_cny.quantize(Q)
        self.taxable_cny = self.taxable_cny.quantize(Q)
        self.tax_due_cny = self.tax_due_cny.quantize(Q)
        self.foreign_tax_cny = self.foreign_tax_cny.quantize(Q)
        self.credit_allowed_cny = self.credit_allowed_cny.quantize(Q)
        self.net_tax_due_cny = self.net_tax_due_cny.quantize(Q)

    def to_dict(self) -> dict[str, Any]:
        self.quantize()
        return {
            "categoryId": self.category_id,
            "labelZh": self.label_zh,
            "eventCount": self.event_count,
            "grossUsd": str(self.gross_usd),
            "grossCny": str(self.gross_cny),
            "taxableIncomeCny": str(self.taxable_cny),
            "taxDueCny": str(self.tax_due_cny),
            "foreignTaxPaidCny": str(self.foreign_tax_cny),
            "creditAllowedCny": str(self.credit_allowed_cny),
            "netTaxDueCny": str(self.net_tax_due_cny),
        }


@dataclass
class YearClassifiedIncomeRow:
    tax_year: int
    fx_rate: Decimal = DEFAULT_FX
    fx_policy: str = "cn_supplemental"
    fx_note: str = ""
    filing_date: str = ""
    dividend: IncomeCategoryLine | None = None
    interest: IncomeCategoryLine | None = None
    warnings: list[str] = field(default_factory=list)

    def categories(self) -> list[IncomeCategoryLine]:
        out: list[IncomeCategoryLine] = []
        if self.dividend and self.dividend.event_count:
            out.append(self.dividend)
        if self.interest and self.interest.event_count:
            out.append(self.interest)
        return out

    def taxable_cny(self) -> Decimal:
        return sum((c.taxable_cny for c in self.categories()), Decimal("0")).quantize(Q)

    def tax_due_cny(self) -> Decimal:
        return sum((c.tax_due_cny for c in self.categories()), Decimal("0")).quantize(Q)

    def net_tax_due_cny(self) -> Decimal:
        return sum((c.net_tax_due_cny for c in self.categories()), Decimal("0")).quantize(Q)

    def to_dict(self) -> dict[str, Any]:
        return {
            "taxYear": self.tax_year,
            "fxRate": str(self.fx_rate),
            "fxPolicy": self.fx_policy,
            "fxNote": self.fx_note,
            "filingDate": self.filing_date,
            "dividend": self.dividend.to_dict() if self.dividend and self.dividend.event_count else None,
            "interest": self.interest.to_dict() if self.interest and self.interest.event_count else None,
            "taxableIncomeCny": str(self.taxable_cny()),
            "taxDueCny": str(self.tax_due_cny()),
            "netTaxDueCny": str(self.net_tax_due_cny()),
            "warnings": self.warnings[:10],
        }


def _event_amount_cny(ev: TaxEvent, fx_rate: Decimal) -> Decimal:
    if ev.amount_cny is not None:
        return ev.amount_cny.quantize(Q)
    if ev.gross_amount:
        return (ev.gross_amount.amount * fx_rate).quantize(Q)
    return Decimal("0")


def _foreign_tax_cny(ev: TaxEvent, fx_rate: Decimal) -> Decimal:
    if not ev.withholding_tax:
        return Decimal("0")
    if ev.fx_rate_used:
        return (ev.withholding_tax.amount * ev.fx_rate_used).quantize(Q)
    return (ev.withholding_tax.amount * fx_rate).quantize(Q)


def _build_category_line(
    cat_id: str,
    label_zh: str,
    cat_events: list[TaxEvent],
    fx_rate: Decimal,
) -> IncomeCategoryLine:
    gross_usd = sum(
        (e.gross_amount.amount for e in cat_events if e.gross_amount),
        Decimal("0"),
    ).quantize(Q)
    raw_cny = sum((_event_amount_cny(e, fx_rate) for e in cat_events), Decimal("0")).quantize(Q)
    taxable = raw_cny if raw_cny > 0 else Decimal("0")
    tax_due = (taxable * TAX_RATE).quantize(Q)
    foreign = sum((_foreign_tax_cny(e, fx_rate) for e in cat_events), Decimal("0")).quantize(Q)
    credit = min(foreign, tax_due)
    net = (tax_due - credit).quantize(Q)
    return IncomeCategoryLine(
        category_id=cat_id,
        label_zh=label_zh,
        event_count=len(cat_events),
        gross_usd=gross_usd,
        gross_cny=raw_cny,
        taxable_cny=taxable,
        tax_due_cny=tax_due,
        foreign_tax_cny=foreign,
        credit_allowed_cny=credit,
        net_tax_due_cny=net,
    )


def allocate_standalone_withholding(
    lines: list[IncomeCategoryLine],
    standalone_wh_cny: Decimal,
) -> Decimal:
    """按应纳税额比例分摊独立 WITHHOLDING_TAX 事件（对齐 compute_engine）。"""
    if standalone_wh_cny <= 0 or not lines:
        return standalone_wh_cny
    total_due = sum((ln.tax_due_cny for ln in lines), Decimal("0"))
    if total_due <= 0:
        return standalone_wh_cny
    allocated = Decimal("0")
    for ln in lines:
        share = (ln.tax_due_cny / total_due).quantize(Decimal("0.0001"))
        headroom = ln.tax_due_cny - ln.foreign_tax_cny
        add = min((standalone_wh_cny * share).quantize(Q), headroom)
        if add > 0:
            ln.foreign_tax_cny += add
            ln.credit_allowed_cny = min(ln.foreign_tax_cny, ln.tax_due_cny)
            ln.net_tax_due_cny = (ln.tax_due_cny - ln.credit_allowed_cny).quantize(Q)
            allocated += add
    return (standalone_wh_cny - allocated).quantize(Q)


def build_classified_income_rows(
    events: list[TaxEvent],
    *,
    provider: FxRateProvider | None = None,
    years: list[int] | None = None,
) -> tuple[list[YearClassifiedIncomeRow], list[str]]:
    """从 DIVIDEND / INTEREST 事件构建分类所得申报行。"""
    warnings: list[str] = []
    by_year: dict[int, dict[EventType, list[TaxEvent]]] = {}
    standalone_wh_by_year: dict[int, Decimal] = {}

    for ev in events:
        if ev.event_type == EventType.WITHHOLDING_TAX:
            year = int(ev.trade_date[:4])
            if years and year not in years:
                continue
            standalone_wh_by_year.setdefault(year, Decimal("0"))
            # 金额在年度循环中按同年汇率折算
            standalone_wh_by_year[year] += ev.gross_amount.amount if ev.gross_amount else Decimal("0")
            continue
        if ev.event_type not in _CATEGORY_BY_EVENT:
            continue
        year = int(ev.trade_date[:4])
        if years and year not in years:
            continue
        by_year.setdefault(year, {}).setdefault(ev.event_type, []).append(ev)

    out_years = sorted(by_year.keys())
    if years:
        out_years = [y for y in sorted(years) if y in by_year]

    rows: list[YearClassifiedIncomeRow] = []
    for y in out_years:
        policy, fd, _, rate, note = _fx_for_tax_year(y, provider=provider)
        row = YearClassifiedIncomeRow(
            tax_year=y,
            fx_rate=rate,
            fx_policy=policy,
            fx_note=note,
            filing_date=fd,
        )
        year_map = by_year.get(y, {})
        if EventType.DIVIDEND in year_map:
            cat_id, label = _CATEGORY_BY_EVENT[EventType.DIVIDEND]
            row.dividend = _build_category_line(cat_id, label, year_map[EventType.DIVIDEND], rate)
        if EventType.INTEREST in year_map:
            cat_id, label = _CATEGORY_BY_EVENT[EventType.INTEREST]
            row.interest = _build_category_line(cat_id, label, year_map[EventType.INTEREST], rate)

        unused = allocate_standalone_withholding(
            row.categories(),
            (standalone_wh_by_year.get(y, Decimal("0")) * rate).quantize(Q),
        )
        if unused > 0:
            row.warnings.append(
                f"独立预扣税 {unused} 元超过分类所得抵免限额，需人工核对或结转至以后年度"
            )
        if row.categories():
            row.warnings.append("futu: 分类所得来自年度收入汇总表（年末单日口径）")
        rows.append(row)

    if not rows and any(e.event_type in _CATEGORY_BY_EVENT for e in events):
        warnings.append("分类所得事件存在但未匹配到指定年度")

    return rows, warnings


def compose_classified_income_markdown(rows: list[YearClassifiedIncomeRow]) -> str:
    if not rows:
        return ""
    lines = [
        "## 境外股息/利息分类所得申报表",
        "",
        "与个税 App 分栏填列：**股息** →「利息、股息、红利所得」；**利息** →「利息所得」。"
        "不得并入财产转让四列；不得用炒股亏损抵减股息/利息。",
        "",
        "| 年份 | 类别 | 收入(USD) | 收入(RMB) | 应纳税所得额(RMB) | 20%税(RMB) | 境外已扣(RMB) | 应补(RMB) |",
        "|------|------|----------|----------|------------------|-----------|--------------|----------|",
    ]
    for row in rows:
        d = row.to_dict()
        for key, label in (("dividend", "股息"), ("interest", "利息")):
            seg = d.get(key)
            if not seg:
                continue
            lines.append(
                f"| **{d['taxYear']}** | {label} | {seg['grossUsd']} | {seg['grossCny']} | "
                f"**{seg['taxableIncomeCny']}** | {seg['taxDueCny']} | {seg['foreignTaxPaidCny']} | "
                f"**{seg['netTaxDueCny']}** |"
            )
    lines.append("")
    return "\n".join(lines)


def build_grand_total(
  *,
    property_taxable_cny: Decimal,
    property_tax_due_cny: Decimal,
    property_net_due_cny: Decimal,
    classified_rows: list[YearClassifiedIncomeRow],
) -> dict[str, str]:
    cls_taxable = sum((r.taxable_cny() for r in classified_rows), Decimal("0")).quantize(Q)
    cls_tax_due = sum((r.tax_due_cny() for r in classified_rows), Decimal("0")).quantize(Q)
    cls_net = sum((r.net_tax_due_cny() for r in classified_rows), Decimal("0")).quantize(Q)
    return {
        "taxableIncomeCny": str((property_taxable_cny + cls_taxable).quantize(Q)),
        "taxDueCny": str((property_tax_due_cny + cls_tax_due).quantize(Q)),
        "netTaxDueCny": str((property_net_due_cny + cls_net).quantize(Q)),
    }
