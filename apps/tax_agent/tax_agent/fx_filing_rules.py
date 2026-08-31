"""CN resident overseas income — compliant FX filing date rules."""

from __future__ import annotations

from datetime import date

COMPLIANCE_FX_POLICIES = frozenset({"cn_annual_filing", "cn_supplemental"})

# 财税务总局公告2020年第3号第十二条 → 实施条例第三十二条
SUPPLEMENTAL_FX_LEGAL_REF = (
    "《个人所得税法实施条例》第三十二条：年度终了后办理汇算清缴的，"
    "对应当补缴税款的所得部分，按照上一纳税年度最后一日人民币汇率中间价折算。"
)


def parse_iso_date(value: str | None) -> date | None:
    if not value or not str(value).strip():
        return None
    s = str(value).strip()[:10]
    try:
        return date.fromisoformat(s)
    except ValueError:
        return None


def default_filing_date(tax_year: int, policy: str) -> str:
    """Heuristic defaults when user omits filingDate."""
    if policy == "cn_annual_filing":
        return f"{tax_year + 1}-04-01"
    return date.today().isoformat()


def prior_month_key(filing: date) -> str:
    """申报当月上一月（YYYY-MM），对应条例「上一月最后一日」中间价。"""
    if filing.month == 1:
        return f"{filing.year - 1}-12"
    return f"{filing.year}-{filing.month - 1:02d}"


def supplemental_month_key_for_tax_year(tax_year: int) -> str:
    """
    以前年度补缴：汇率锚定**所得所属纳税年度**的「上一纳税年度」末日。

    例：补缴 2021 年度境外所得 → 上一纳税年度为 2020 → 取 2020-12 月末中间价。
    与办理申报公历年（如 2026）无关。
    """
    return f"{tax_year - 1}-12"


def supplemental_reference_date(tax_year: int) -> str:
    """上一纳税年度末日（ISO）。"""
    return f"{tax_year - 1}-12-31"


def resolve_filing_month_key(
    policy: str,
    filing_date: str,
    *,
    tax_year: int | None = None,
) -> tuple[str, str]:
    """
    Return (month_key for rate lookup, human-readable rule label).
    """
    fd = parse_iso_date(filing_date)
    if not fd:
        raise ValueError(f"invalid filingDate: {filing_date}")

    if policy == "cn_annual_filing":
        mk = prior_month_key(fd)
        return mk, f"正常年度汇算·申报日{filing_date}→上一月末({mk})"
    if policy == "cn_supplemental":
        if tax_year is None:
            raise ValueError("cn_supplemental requires tax_year (所得所属纳税年度)")
        mk = supplemental_month_key_for_tax_year(tax_year)
        ref = supplemental_reference_date(tax_year)
        return (
            mk,
            f"以前年度补缴·所得所属纳税年度{tax_year}·上一纳税年度末日({ref})→{mk}中间价",
        )
    raise ValueError(f"not a compliance filing policy: {policy}")


def filing_date_for_request(
    *,
    policy: str,
    tax_year: int,
    filing_date: str | None,
) -> str | None:
    if policy not in COMPLIANCE_FX_POLICIES:
        return filing_date
    if filing_date:
        return filing_date
    return default_filing_date(tax_year, policy)
