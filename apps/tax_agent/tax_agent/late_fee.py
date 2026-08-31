"""滞纳金估算（境外所得逾期申报）。

依据：税收征收管理法第三十二条 — 每日万分之五，自法定申报期限次日起算。
境外分类所得年度汇算法定申报期限：纳税年度终了后六个月（次年 6 月 30 日），
次日起算日为次年 7 月 1 日。
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from tax_agent.fx_filing_rules import parse_iso_date

Q = Decimal("0.01")
DAILY_RATE = Decimal("0.0005")  # 万分之五


def statutory_deadline(tax_year: int) -> date:
    """纳税年度 Y 的法定申报截止日（次年 6 月 30 日）。"""
    return date(tax_year + 1, 6, 30)


def penalty_start_date(tax_year: int) -> date:
    """滞纳金起算日（法定截止日次日）。"""
    return date(tax_year + 1, 7, 1)


def overdue_days(tax_year: int, filing: date) -> int:
    start = penalty_start_date(tax_year)
    if filing <= start:
        return 0
    return (filing - start).days


def compute_late_fee(
    tax_due_cny: Decimal | str,
    *,
    tax_year: int,
    filing_date: str | date | None,
    policy: str = "",
) -> dict[str, Any] | None:
    """
    估算滞纳金。仅当应纳税额 > 0 且申报日晚于起算日时返回明细。
    """
    due = Decimal(str(tax_due_cny)).quantize(Q)
    if due <= 0:
        return None

    fd = filing_date if isinstance(filing_date, date) else parse_iso_date(
        str(filing_date) if filing_date else None
    )
    if not fd:
        return None

    days = overdue_days(tax_year, fd)
    if days <= 0:
        return {
            "applicable": False,
            "taxDueCny": str(due),
            "overdueDays": 0,
            "dailyRate": str(DAILY_RATE),
            "lateFeeCny": "0.00",
            "totalPayableCny": str(due),
            "statutoryDeadline": statutory_deadline(tax_year).isoformat(),
            "penaltyStartDate": penalty_start_date(tax_year).isoformat(),
            "filingDate": fd.isoformat(),
            "policy": policy,
            "note": "在法定申报期限内办理，不产生滞纳金。",
        }

    fee = (due * DAILY_RATE * days).quantize(Q)
    total = (due + fee).quantize(Q)
    return {
        "applicable": True,
        "taxDueCny": str(due),
        "overdueDays": days,
        "dailyRate": str(DAILY_RATE),
        "lateFeeCny": str(fee),
        "totalPayableCny": str(total),
        "statutoryDeadline": statutory_deadline(tax_year).isoformat(),
        "penaltyStartDate": penalty_start_date(tax_year).isoformat(),
        "filingDate": fd.isoformat(),
        "policy": policy,
        "note": (
            f"逾期 {days} 天（自 {penalty_start_date(tax_year)} 起），"
            f"滞纳金 = 应纳税额 × 0.05% × 天数；本估算不含罚款。"
        ),
    }
