"""境外财产转让所得申报数据表（FIFO 收入/原值/净损益，含股票与期权分列）。"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any

from tax_agent.cost_basis import RealizedGain, TradeLeg, match_fifo
from tax_agent.futu_session_fifo import collect_merged_legs
from tax_agent.fx_filing_rules import default_filing_date, filing_date_for_request
from tax_agent.fx_rates import DEFAULT_FX, FxRateProvider

Q = Decimal("0.01")
TAX_RATE = Decimal("0.20")

_OPTION_SYM = re.compile(r"\d{6}[CP]\d", re.I)


def is_option_symbol(symbol: str, category: str = "") -> bool:
    cat = (category or "").strip()
    if "期权" in cat:
        return True
    sym = (symbol or "").strip()
    if _OPTION_SYM.search(sym):
        return True
    if sym.endswith((" C", " P")) or " CALL" in sym.upper() or " PUT" in sym.upper():
        return True
    return False


def asset_type_for_gain(rg: RealizedGain) -> str:
    cat = str((rg.metadata or {}).get("category") or "")
    return "option" if is_option_symbol(rg.symbol, cat) else "stock"


@dataclass
class SegmentTotals:
    """申报四列：总收入(毛) / 资产原值 / 合理费用 / 净损益。"""

    asset_type: str
    disposal_count: int = 0
    gross_proceeds_usd: Decimal = Decimal("0")
    cost_basis_usd: Decimal = Decimal("0")
    reasonable_fee_usd: Decimal = Decimal("0")
    net_usd: Decimal = Decimal("0")

    def add(self, rg: RealizedGain) -> None:
        self.disposal_count += 1
        # proceeds_usd 来自变动金额(扣费后)；总收入=成交金额≈proceeds+卖出佣金
        self.gross_proceeds_usd += rg.proceeds_usd + rg.fee_usd
        self.cost_basis_usd += rg.cost_basis_usd
        self.reasonable_fee_usd += rg.fee_usd
        # 应税净额 = 总收入 − 原值 − 合理费用 = (proc+fee) − cost − fee = proc − cost
        self.net_usd += rg.proceeds_usd - rg.cost_basis_usd

    def quantize(self) -> None:
        self.gross_proceeds_usd = self.gross_proceeds_usd.quantize(Q)
        self.cost_basis_usd = self.cost_basis_usd.quantize(Q)
        self.reasonable_fee_usd = self.reasonable_fee_usd.quantize(Q)
        self.net_usd = self.net_usd.quantize(Q)

    def to_dict(self, *, fx_rate: Decimal) -> dict[str, Any]:
        self.quantize()
        r = fx_rate
        return {
            "assetType": self.asset_type,
            "assetTypeLabel": "期权" if self.asset_type == "option" else "股票",
            "disposalCount": self.disposal_count,
            "grossProceedsUsd": str(self.gross_proceeds_usd),
            "grossProceedsCny": str((self.gross_proceeds_usd * r).quantize(Q)),
            "costBasisUsd": str(self.cost_basis_usd),
            "costBasisCny": str((self.cost_basis_usd * r).quantize(Q)),
            "reasonableFeeUsd": str(self.reasonable_fee_usd),
            "reasonableFeeCny": str((self.reasonable_fee_usd * r).quantize(Q)),
            "netGainUsd": str(self.net_usd),
            "netGainCny": str((self.net_usd * r).quantize(Q)),
            # 兼容旧字段名
            "proceedsUsd": str(self.gross_proceeds_usd),
            "proceedsCny": str((self.gross_proceeds_usd * r).quantize(Q)),
            "costAndFeeUsd": str((self.cost_basis_usd + self.reasonable_fee_usd).quantize(Q)),
            "costAndFeeCny": str(((self.cost_basis_usd + self.reasonable_fee_usd) * r).quantize(Q)),
        }


@dataclass
class YearFilingRow:
    tax_year: int
    segments: dict[str, SegmentTotals] = field(default_factory=dict)
    fx_rate: Decimal = DEFAULT_FX
    fx_policy: str = "cn_supplemental"
    fx_note: str = ""
    filing_date: str = ""

    def segment(self, asset_type: str) -> SegmentTotals:
        if asset_type not in self.segments:
            self.segments[asset_type] = SegmentTotals(asset_type=asset_type)
        return self.segments[asset_type]

    @property
    def total(self) -> SegmentTotals:
        t = SegmentTotals(asset_type="total")
        for seg in self.segments.values():
            t.disposal_count += seg.disposal_count
            t.gross_proceeds_usd += seg.gross_proceeds_usd
            t.cost_basis_usd += seg.cost_basis_usd
            t.reasonable_fee_usd += seg.reasonable_fee_usd
            t.net_usd += seg.net_usd
        return t

    def taxable_cny(self) -> Decimal:
        net = (self.total.net_usd * self.fx_rate).quantize(Q)
        return net if net > 0 else Decimal("0")

    def tax_due_cny(self) -> Decimal:
        return (self.taxable_cny() * TAX_RATE).quantize(Q)

    def filing_advice(self) -> str:
        if self.tax_due_cny() > 0:
            return "需补缴"
        if self.total.net_usd < 0:
            return "亏损，无需缴税"
        return "无需缴税"

    def to_dict(self) -> dict[str, Any]:
        tot = self.total
        tot.quantize()
        r = self.fx_rate
        return {
            "taxYear": self.tax_year,
            "grossProceedsUsd": str(tot.gross_proceeds_usd),
            "grossProceedsCny": str((tot.gross_proceeds_usd * r).quantize(Q)),
            "costBasisUsd": str(tot.cost_basis_usd),
            "costBasisCny": str((tot.cost_basis_usd * r).quantize(Q)),
            "reasonableFeeUsd": str(tot.reasonable_fee_usd),
            "reasonableFeeCny": str((tot.reasonable_fee_usd * r).quantize(Q)),
            "proceedsUsd": str(tot.gross_proceeds_usd),
            "proceedsCny": str((tot.gross_proceeds_usd * r).quantize(Q)),
            "costAndFeeUsd": str((tot.cost_basis_usd + tot.reasonable_fee_usd).quantize(Q)),
            "costAndFeeCny": str(((tot.cost_basis_usd + tot.reasonable_fee_usd) * r).quantize(Q)),
            "netGainUsd": str(tot.net_usd),
            "netGainCny": str((tot.net_usd * r).quantize(Q)),
            "taxableIncomeCny": str(self.taxable_cny()),
            "taxDueCny": str(self.tax_due_cny()),
            "fxRate": str(r),
            "fxPolicy": self.fx_policy,
            "fxNote": self.fx_note,
            "filingDate": self.filing_date,
            "filingAdvice": self.filing_advice(),
            "stock": self.segments.get("stock", SegmentTotals("stock")).to_dict(fx_rate=r)
            if "stock" in self.segments
            else None,
            "option": self.segments.get("option", SegmentTotals("option")).to_dict(fx_rate=r)
            if "option" in self.segments
            else None,
        }


def _fx_for_tax_year(
    tax_year: int,
    *,
    provider: FxRateProvider | None,
    as_of: date | None = None,
) -> tuple[str, str, str, Decimal, str]:
    """Return policy, filing_date, month_key label, rate, note."""
    today = as_of or date.today()
    # 上一自然年 → 正常年度汇算；更早年度 → 以前年度补缴
    if tax_year == today.year - 1:
        policy = "cn_annual_filing"
        fd = default_filing_date(tax_year, policy)
    else:
        policy = "cn_supplemental"
        fd = filing_date_for_request(policy=policy, tax_year=tax_year, filing_date=None) or today.isoformat()

    if provider and provider.available:
        res = provider.resolve_filing(policy, fd, tax_year=tax_year)
        return policy, fd, res.note, res.rate, res.note
    return policy, fd, "默认汇率", DEFAULT_FX, f"默认汇率 {DEFAULT_FX}"


def build_filing_rows_from_packages(
    packages: list[dict[str, Any]],
    *,
    provider: FxRateProvider | None = None,
    years: list[int] | None = None,
) -> tuple[list[YearFilingRow], list[RealizedGain], list[str]]:
    legs = collect_merged_legs(packages)
    realized, warnings = match_fifo(legs)

    by_year: dict[int, YearFilingRow] = {}
    for rg in realized:
        year = int(rg.trade_date[:4])
        if years and year not in years:
            continue
        row = by_year.setdefault(year, YearFilingRow(tax_year=year))
        at = asset_type_for_gain(rg)
        row.segment(at).add(rg)

    out_years = sorted(by_year.keys())
    if years:
        out_years = [y for y in sorted(years) if y in by_year]

    rows: list[YearFilingRow] = []
    for y in out_years:
        row = by_year[y]
        policy, fd, _, rate, note = _fx_for_tax_year(y, provider=provider)
        row.fx_policy = policy
        row.filing_date = fd
        row.fx_rate = rate
        row.fx_note = note
        rows.append(row)

    return rows, realized, warnings


def compose_filing_table_markdown(
    rows: list[YearFilingRow],
    *,
    title: str = "境外财产转让所得申报数据表",
) -> str:
    lines = [
        f"## {title}",
        "",
        "申报四列（与个税 App「财产转让所得」一致）：**总收入** = 卖出成交金额(毛)；**资产原值** = FIFO 匹配买入成本；"
        "**合理费用** = 卖出佣金/平台费；**应纳税所得额** = max(0, 总收入 − 原值 − 合理费用) × 汇率。",
        "买入侧佣金已含在 FIFO 原值；融资利息等不得在此扣减（应单独申报利息所得）。",
        "",
        "| 年份 | 总收入(USD) | 总收入(RMB) | 资产原值(USD) | 资产原值(RMB) | 合理费用(USD) | 合理费用(RMB) | 净损益(USD) | 净损益(RMB) | 20%税(RMB) | 建议 |",
        "|------|------------|------------|--------------|--------------|--------------|--------------|------------|------------|-----------|------|",
    ]
    for row in rows:
        d = row.to_dict()
        lines.append(
            f"| **{d['taxYear']}** | {d['grossProceedsUsd']} | {d['grossProceedsCny']} | "
            f"{d['costBasisUsd']} | {d['costBasisCny']} | {d['reasonableFeeUsd']} | {d['reasonableFeeCny']} | "
            f"**{d['netGainUsd']}** | **{d['netGainCny']}** | **{d['taxDueCny']}** | {d['filingAdvice']} |"
        )

    lines.append("")
    lines.append("### 股票 / 期权分列（人民币计价）")
    lines.append("")
    lines.append(
        "| 年份 | 类别 | 总收入(USD) | 原值(USD) | 合理费用(USD) | 净损益(RMB) | 笔数 |"
    )
    lines.append("|------|------|------------|----------|--------------|------------|------|")
    for row in rows:
        d = row.to_dict()
        for key, label in (("stock", "股票"), ("option", "期权")):
            seg = d.get(key)
            if not seg:
                continue
            lines.append(
                f"| {d['taxYear']} | {label} | {seg['grossProceedsUsd']} | {seg['costBasisUsd']} | "
                f"{seg['reasonableFeeUsd']} | **{seg['netGainCny']}** | {seg['disposalCount']} |"
            )

    lines.append("")
    lines.append("### 汇率说明")
    for row in rows:
        d = row.to_dict()
        pol = "正常年度汇算" if d["fxPolicy"] == "cn_annual_filing" else "以前年度补缴"
        lines.append(
            f"- **{d['taxYear']}年**（{pol}）：汇率 **{d['fxRate']}** RMB/USD；{d['fxNote']}"
        )
    lines.append("")
    return "\n".join(lines)


def build_filing_report(
    data_quality: dict[str, Any],
    *,
    provider: FxRateProvider | None = None,
    years: list[int] | None = None,
    events: list[Any] | None = None,
) -> dict[str, Any]:
    from tax_agent.income_summary import (
        build_classified_income_rows,
        build_grand_total,
        compose_classified_income_markdown,
    )

    packages = data_quality.get("futuTaxPackages") or []
    if not packages:
        pkg = data_quality.get("futuTaxPackage")
        if pkg:
            packages = [pkg]
    if not packages:
        return {"error": "无富途税表流水，请先上传 Annual_Statement"}

    rows, realized, warnings = build_filing_rows_from_packages(
        packages, provider=provider, years=years
    )

    classified_rows: list[Any] = []
    classified_warnings: list[str] = []
    if events:
        classified_rows, classified_warnings = build_classified_income_rows(
            list(events), provider=provider, years=years
        )

    property_by_year = {r.tax_year: r for r in rows}
    classified_by_year = {r.tax_year: r for r in classified_rows}
    all_years = sorted(set(property_by_year) | set(classified_by_year))
    if years:
        all_years = [y for y in sorted(years) if y in set(all_years)]

    combined_rows: list[dict[str, Any]] = []
    for y in all_years:
        prop = property_by_year.get(y)
        cls = classified_by_year.get(y)
        prop_dict = prop.to_dict() if prop else None
        cls_dict = cls.to_dict() if cls else None
        prop_taxable = Decimal(prop_dict["taxableIncomeCny"]) if prop_dict else Decimal("0")
        prop_tax = Decimal(prop_dict["taxDueCny"]) if prop_dict else Decimal("0")
        prop_net = prop_tax  # 财产转让申报表暂不建模境外预扣抵免
        grand = build_grand_total(
            property_taxable_cny=prop_taxable,
            property_tax_due_cny=prop_tax,
            property_net_due_cny=prop_net,
            classified_rows=[cls] if cls else [],
        )
        combined_rows.append(
            {
                "taxYear": y,
                "propertyTransfer": prop_dict,
                "classifiedIncome": cls_dict,
                "grandTotal": grand,
            }
        )

    markdown = compose_filing_table_markdown(rows)
    cls_md = compose_classified_income_markdown(classified_rows)
    if cls_md:
        markdown = markdown + "\n\n---\n\n" + cls_md
    if combined_rows:
        markdown += "\n\n### 全税目合计（财产转让 + 股息/利息）\n\n"
        markdown += (
            "| 年份 | 应纳税所得额合计(RMB) | 应纳税额合计(RMB) | 应补税额合计(RMB) |\n"
            "|------|---------------------|-----------------|---------------|\n"
        )
        for cr in combined_rows:
            g = cr["grandTotal"]
            markdown += (
                f"| **{cr['taxYear']}** | {g['taxableIncomeCny']} | {g['taxDueCny']} | "
                f"**{g['netTaxDueCny']}** |\n"
            )
        markdown += "\n"

    return {
        "title": "境外所得申报数据表（财产转让四列 + 股息/利息分类所得）",
        "rows": [r.to_dict() for r in rows],
        "classifiedIncome": {
            "rows": [r.to_dict() for r in classified_rows],
            "warnings": classified_warnings[:20],
        },
        "combinedRows": combined_rows,
        "markdown": markdown,
        "realizedCount": len(realized),
        "warnings": (warnings + classified_warnings)[:30],
        "optionNote": (
            "期权：卖出/平仓成交金额计入「总收入」；FIFO 匹配开仓权利金计入「资产原值」；"
            "卖出佣金计入「合理费用」；到期作废处置收入为 0 时净损失为已付权利金（扣除已匹配原值）。"
        ),
        "filingColumnsNote": (
            "总收入=证券-交易流水卖出成交金额合计；合理费用=同表卖出总费用；"
            "资产原值=FIFO 匹配买入成本（买入佣金已含在买入金额）。"
        ),
        "classifiedIncomeNote": (
            "股息/利息来自「股息、利息及其他收入」年度汇总；与财产转让分税目申报；"
            "「全年其他收入」不自动计税。"
        ),
    }
