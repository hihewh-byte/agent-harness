"""一键最优申报日推荐：在合规候选日内最小化应补税 + 滞纳金。"""

from __future__ import annotations

import copy
from datetime import date
from decimal import Decimal
from typing import Any

from tax_agent.fx import apply_fx_to_events
from tax_agent.fx_filing_rules import filing_date_for_request, parse_iso_date
from tax_agent.fx_rates import FxRateProvider
from tax_agent.late_fee import compute_late_fee, overdue_days, penalty_start_date, statutory_deadline
from tax_agent.models import TaxEvent
from tax_agent.rules_loader import RuleSnapshot

Q = Decimal("0.01")

TIER_NO_PENALTY = "no_penalty"
TIER_MINIMUM_TOTAL = "minimum_total"


def _clone_events(events: list[TaxEvent]) -> list[TaxEvent]:
    return copy.deepcopy(events)


def _summarize_from_engine(engine: Any, events: list[TaxEvent], snapshot: RuleSnapshot, tax_year: int) -> dict[str, str]:
    year_events = [e for e in events if e.trade_date.startswith(str(tax_year))]
    lines, _ = engine._build_line_items(year_events, snapshot)
    return engine._summarize(lines)


def _add_months(d: date, months: int) -> date:
    y = d.year + (d.month - 1 + months) // 12
    m = (d.month - 1 + months) % 12 + 1
    day = min(d.day, 28)
    return date(y, m, day)


def _month_starts(start: date, end: date) -> list[date]:
    out: list[date] = []
    cur = date(start.year, start.month, 1)
    limit = date(end.year, end.month, 1)
    while cur <= limit:
        out.append(cur)
        cur = _add_months(cur, 1)
    return out


def _candidate_filing_dates(
    *,
    tax_year: int,
    policy: str,
    primary_filing_date: str | None,
    today: date,
) -> list[date]:
    """生成可扫描的合规/现实申报日候选（每月首日 + 关键截止日）。"""
    y1 = tax_year + 1
    candidates: set[date] = set()

    if policy == "cn_annual_filing":
        for m in (3, 4, 5, 6):
            candidates.add(date(y1, m, 1))
        candidates.add(statutory_deadline(tax_year))
        scan_end = date(y1, 12, 1)
        if primary_filing_date:
            fd = parse_iso_date(primary_filing_date)
            if fd and fd > statutory_deadline(tax_year):
                scan_end = max(scan_end, fd)
        scan_end = max(scan_end, today)
        for d in _month_starts(penalty_start_date(tax_year), scan_end):
            candidates.add(d)
    elif policy == "cn_supplemental":
        start = penalty_start_date(tax_year)
        horizon = _add_months(today, 24)
        if primary_filing_date:
            fd = parse_iso_date(primary_filing_date)
            if fd:
                horizon = max(horizon, _add_months(fd, 12))
        for d in _month_starts(start, horizon):
            candidates.add(d)
        if primary_filing_date:
            fd = parse_iso_date(primary_filing_date)
            if fd:
                candidates.add(fd)
    else:
        return []

    return sorted(candidates)


def _evaluate_date(
    raw_events: list[TaxEvent],
    *,
    engine: Any,
    snapshot: RuleSnapshot,
    provider: FxRateProvider | None,
    tax_year: int,
    policy: str,
    filing_date: date,
    fallback_rate: Decimal | None,
) -> dict[str, Any] | None:
    fd = filing_date.isoformat()
    resolved = filing_date_for_request(policy=policy, tax_year=tax_year, filing_date=fd)
    evs = apply_fx_to_events(
        _clone_events(raw_events),
        provider=provider,
        policy=policy,
        fallback_rate=fallback_rate,
        filing_date=resolved,
        tax_year=tax_year if policy == "cn_supplemental" else None,
    )
    summary = _summarize_from_engine(engine, evs, snapshot, tax_year)
    net = Decimal(summary.get("netTaxDueCny", "0")).quantize(Q)
    tax_due = Decimal(summary.get("taxDueCny", "0")).quantize(Q)
    if tax_due <= 0 and net <= 0:
        return None

    lf = compute_late_fee(tax_due, tax_year=tax_year, filing_date=fd, policy=policy)
    late = Decimal("0")
    overdue = 0
    if lf:
        late = Decimal(lf.get("lateFeeCny", "0")).quantize(Q)
        overdue = int(lf.get("overdueDays", 0))
    total_cash = (net + late).quantize(Q)

    fx_note = ""
    if provider and provider.available and policy in ("cn_annual_filing", "cn_supplemental"):
        fx_note = provider.resolve_filing(
            policy, resolved, tax_year=tax_year if policy == "cn_supplemental" else None
        ).note

    return {
        "filingDate": fd,
        "fxPolicy": policy,
        "netTaxDueCny": str(net),
        "taxDueCny": str(tax_due),
        "lateFeeCny": str(late),
        "totalCashCny": str(total_cash),
        "overdueDays": overdue,
        "fxNote": fx_note,
        "noPenalty": overdue == 0,
    }


def _pick_best(rows: list[dict[str, Any]], *, no_penalty_only: bool = False) -> dict[str, Any] | None:
    pool = [r for r in rows if r.get("noPenalty")] if no_penalty_only else rows
    if not pool:
        return None
    return min(pool, key=lambda r: Decimal(r["totalCashCny"]))


def _format_savings(amount: Decimal) -> str:
    return str(amount.quantize(Q))


def build_filing_recommendation(
    raw_events: list[TaxEvent],
    *,
    engine: Any,
    snapshot: RuleSnapshot,
    provider: FxRateProvider | None,
    tax_year: int,
    primary_policy: str,
    primary_filing_date: str | None,
    fallback_rate: Decimal | None = None,
    today: date | None = None,
) -> dict[str, Any]:
    """
    扫描候选申报日，推荐 totalCash = 应补税 + 滞纳金 最低的方案。
    """
    if primary_policy not in ("cn_annual_filing", "cn_supplemental"):
        return {"status": "not_applicable", "reason": f"policy {primary_policy} 不支持申报日优化"}

    ref_day = today or date.today()
    resolved_primary = filing_date_for_request(
        policy=primary_policy, tax_year=tax_year, filing_date=primary_filing_date
    )
    primary_fd = parse_iso_date(resolved_primary) or ref_day

    candidates = _candidate_filing_dates(
        tax_year=tax_year,
        policy=primary_policy,
        primary_filing_date=resolved_primary,
        today=ref_day,
    )
    if not candidates:
        return {"status": "no_candidates", "reason": "无可用候选申报日"}

    evaluated: list[dict[str, Any]] = []
    for fd in candidates:
        row = _evaluate_date(
            raw_events,
            engine=engine,
            snapshot=snapshot,
            provider=provider,
            tax_year=tax_year,
            policy=primary_policy,
            filing_date=fd,
            fallback_rate=fallback_rate,
        )
        if row:
            evaluated.append(row)

    if not evaluated:
        return {"status": "no_tax", "reason": "本年无需缴税，无需优化申报日", "scanCount": len(candidates)}

    primary_row = _evaluate_date(
        raw_events,
        engine=engine,
        snapshot=snapshot,
        provider=provider,
        tax_year=tax_year,
        policy=primary_policy,
        filing_date=primary_fd,
        fallback_rate=fallback_rate,
    )
    primary_cash = Decimal(primary_row["totalCashCny"]) if primary_row else Decimal("0")

    best_any = _pick_best(evaluated)
    best_clean = _pick_best(evaluated, no_penalty_only=True)

    recommended = best_clean or best_any
    tier = TIER_NO_PENALTY if recommended and recommended.get("noPenalty") else TIER_MINIMUM_TOTAL
    if recommended and not recommended.get("noPenalty") and best_any:
        recommended = {**best_any, "tier": tier}
    elif recommended:
        recommended = {**recommended, "tier": tier}

    savings = primary_cash - Decimal(recommended["totalCashCny"]) if recommended else Decimal("0")
    recommended["savingsVsPrimaryCny"] = _format_savings(savings)

    ranked = sorted(evaluated, key=lambda r: Decimal(r["totalCashCny"]))[:8]

    if savings <= 0:
        status = "already_optimal"
        rationale = (
            f"当前申报日 {resolved_primary} 已在扫描的 {len(evaluated)} 个候选日中总支出最低"
            f"（应补 {primary_row['netTaxDueCny'] if primary_row else '0'} + "
            f"滞纳金 {primary_row['lateFeeCny'] if primary_row else '0'} = {primary_cash} 元）。"
        )
        recommended = primary_row or recommended
        if recommended:
            recommended = {**recommended, "tier": tier, "savingsVsPrimaryCny": "0.00"}
    else:
        status = "ok"
        if recommended.get("noPenalty"):
            rationale = (
                f"建议在 **{recommended['filingDate']}** 办理申报（{primary_policy}）："
                f"应补 {recommended['netTaxDueCny']} 元，无滞纳金，"
                f"较当前方案少支出 **{recommended['savingsVsPrimaryCny']}** 元。"
            )
        else:
            rationale = (
                f"若尽快申报，推荐 **{recommended['filingDate']}**："
                f"应补 {recommended['netTaxDueCny']} 元 + 滞纳金 {recommended['lateFeeCny']} 元 "
                f"= 合计 **{recommended['totalCashCny']}** 元，"
                f"较当前 {resolved_primary} 少 **{recommended['savingsVsPrimaryCny']}** 元。"
                "（已逾期，无法避免滞纳金；推迟换更低汇率通常不划算。）"
            )

    out: dict[str, Any] = {
        "status": status,
        "primaryFilingDate": resolved_primary,
        "primaryFxPolicy": primary_policy,
        "primaryTotalCashCny": str(primary_cash),
        "recommended": recommended,
        "bestNoPenalty": best_clean,
        "topCandidates": ranked,
        "rationale": rationale,
        "scanCount": len(evaluated),
        "statutoryDeadline": statutory_deadline(tax_year).isoformat(),
        "penaltyStartDate": penalty_start_date(tax_year).isoformat(),
    }
    if best_clean and best_any and best_clean["filingDate"] != best_any["filingDate"]:
        extra = Decimal(best_any["totalCashCny"]) - Decimal(best_clean["totalCashCny"])
        if extra < 0:
            out["note"] = (
                f"无滞纳金最优日为 {best_clean['filingDate']}（{best_clean['totalCashCny']} 元）；"
                f"全局最低为 {best_any['filingDate']}（{best_any['totalCashCny']} 元），"
                "但需承担滞纳金，一般不建议为省税故意逾期。"
            )
    return out
