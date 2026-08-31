"""多口径汇率测算对照：合规主结果 + 辅助/申报期优化场景。"""

from __future__ import annotations

import copy
from decimal import Decimal
from typing import Any

from tax_agent.fx import apply_fx_to_events
from tax_agent.fx_filing_rules import filing_date_for_request
from tax_agent.fx_rates import FxRateProvider
from tax_agent.late_fee import compute_late_fee
from tax_agent.models import TaxEvent
from tax_agent.rules_loader import RuleSnapshot

Q = Decimal("0.01")

POLICY_LABELS: dict[str, str] = {
    "cn_annual_filing": "正常年度汇算（申报上一月末中间价）",
    "cn_supplemental": "以前年度补缴（上一纳税年度末日中间价）",
    "safe_harbor_monthly": "辅助·按交易发生月折算",
    "safe_harbor_yearly": "辅助·纳税年度平均汇率",
}

TIER_PRIMARY = "primary"
TIER_COMPLIANT_ALT = "compliant_alternative"
TIER_AUXILIARY = "auxiliary"


def _clone_events(events: list[TaxEvent]) -> list[TaxEvent]:
    return copy.deepcopy(events)


def _month_key(trade_date: str) -> str:
    return trade_date[:7] if len(trade_date) >= 7 else "unknown"


def _summarize_from_engine(engine: Any, events: list[TaxEvent], snapshot: RuleSnapshot, tax_year: int) -> dict[str, str]:
    year_events = [e for e in events if e.trade_date.startswith(str(tax_year))]
    lines, _ = engine._build_line_items(year_events, snapshot)
    return engine._summarize(lines)


def _scenario_row(
    *,
    policy: str,
    label: str,
    tier: str,
    filing_date: str | None,
    provider: FxRateProvider | None,
    summary: dict[str, str],
    fx_note: str = "",
    is_lowest: bool = False,
) -> dict[str, Any]:
    net = Decimal(summary.get("netTaxDueCny", "0"))
    return {
        "fxPolicy": policy,
        "label": label,
        "tier": tier,
        "filingDate": filing_date,
        "fxNote": fx_note,
        "taxableIncomeCny": summary.get("taxableIncomeCny", "0.00"),
        "taxDueCny": summary.get("taxDueCny", "0.00"),
        "netTaxDueCny": summary.get("netTaxDueCny", "0.00"),
        "creditAllowedCny": summary.get("creditAllowedCny", "0.00"),
        "isLowestNetTax": is_lowest,
        "deltaVsPrimaryCny": None,
    }


def _fx_note(
    provider: FxRateProvider | None,
    policy: str,
    filing_date: str | None,
    *,
    tax_year: int | None = None,
) -> str:
    if not provider or not provider.available:
        return "无汇率数据集"
    if policy in ("cn_annual_filing", "cn_supplemental") and filing_date:
        return provider.resolve_filing(policy, filing_date, tax_year=tax_year).note
    if policy == "safe_harbor_yearly":
        return "按各交易年度平均汇率"
    return "按交易发生月中间价逐笔折算"


def build_monthly_breakdown(
    events: list[TaxEvent],
    *,
    provider: FxRateProvider | None,
    tax_year: int,
    fallback_rate: Decimal | None = None,
) -> list[dict[str, Any]]:
    """分月折算明细（safe_harbor_monthly）。"""
    fx_events = apply_fx_to_events(
        _clone_events(events),
        provider=provider,
        policy="safe_harbor_monthly",
        fallback_rate=fallback_rate,
    )
    buckets: dict[str, dict[str, Decimal]] = {}
    for ev in fx_events:
        if not ev.gross_amount:
            continue
        if not ev.trade_date.startswith(str(tax_year)):
            continue
        mk = _month_key(ev.trade_date)
        b = buckets.setdefault(
            mk,
            {"usd": Decimal("0"), "cny": Decimal("0"), "count": Decimal("0")},
        )
        b["usd"] += ev.gross_amount.amount
        b["cny"] += ev.amount_cny or Decimal("0")
        b["count"] += Decimal("1")

    rows: list[dict[str, Any]] = []
    for mk in sorted(buckets):
        b = buckets[mk]
        rate = None
        if provider and provider.available:
            rate = provider.resolve_month(mk).rate
        rows.append(
            {
                "month": mk,
                "eventCount": int(b["count"]),
                "grossUsd": str(b["usd"].quantize(Q)),
                "grossCny": str(b["cny"].quantize(Q)),
                "fxRate": str(rate) if rate is not None else None,
            }
        )
    return rows


def _annual_filing_alternatives(tax_year: int) -> list[str]:
    y = tax_year + 1
    return [f"{y}-04-01", f"{y}-05-01", f"{y}-06-01", f"{y}-06-30"]


def _supplemental_alternatives(filing_date: str) -> list[str]:
    """不同办理年 → 汇率不变（锚定所得年度），仅滞纳金不同。"""
    parts = filing_date.split("-")
    if len(parts) < 3:
        return []
    y, m, d = int(parts[0]), parts[1], parts[2]
    return [f"{y}-{m}-{d}", f"{y + 1}-{m}-{d}"]


def build_fx_comparison(
    raw_events: list[TaxEvent],
    *,
    engine: Any,
    snapshot: RuleSnapshot,
    provider: FxRateProvider | None,
    tax_year: int,
    primary_policy: str,
    primary_filing_date: str | None,
    fallback_rate: Decimal | None = None,
) -> dict[str, Any]:
    """
    一次测算输出多口径对照表 + 分月明细 + 合规优化提示。
    """
    scenarios: list[dict[str, Any]] = []

    def add_scenario(policy: str, filing_date: str | None, tier: str, label: str | None = None) -> None:
        resolved = filing_date_for_request(
            policy=policy, tax_year=tax_year, filing_date=filing_date
        )
        evs = apply_fx_to_events(
            _clone_events(raw_events),
            provider=provider,
            policy=policy,
            fallback_rate=fallback_rate,
            filing_date=resolved if policy in ("cn_annual_filing", "cn_supplemental") else None,
            tax_year=tax_year,
        )
        summary = _summarize_from_engine(engine, evs, snapshot, tax_year)
        scenarios.append(
            _scenario_row(
                policy=policy,
                label=label or POLICY_LABELS.get(policy, policy),
                tier=tier,
                filing_date=resolved,
                provider=provider,
                summary=summary,
                fx_note=_fx_note(provider, policy, resolved, tax_year=tax_year),
            )
        )

    add_scenario(primary_policy, primary_filing_date, TIER_PRIMARY)

    if primary_policy == "cn_annual_filing":
        for fd in _annual_filing_alternatives(tax_year):
            if fd == primary_filing_date:
                continue
            add_scenario(
                "cn_annual_filing",
                fd,
                TIER_COMPLIANT_ALT,
                f"若改在 {fd[:7]} 月申报（上一月末汇率）",
            )
    elif primary_policy == "cn_supplemental" and primary_filing_date:
        for fd in _supplemental_alternatives(primary_filing_date):
            if fd == primary_filing_date:
                continue
            add_scenario(
                "cn_supplemental",
                fd,
                TIER_COMPLIANT_ALT,
                f"若推迟至 {fd[:4]} 年办理补缴（汇率同主场景，滞纳金不同）",
            )
        add_scenario("cn_annual_filing", primary_filing_date, TIER_COMPLIANT_ALT, "对照·正常汇算口径（同申报日）")

    for aux in ("safe_harbor_monthly", "safe_harbor_yearly"):
        if aux == primary_policy:
            continue
        add_scenario(aux, None, TIER_AUXILIARY)

    primary_net = Decimal(scenarios[0]["netTaxDueCny"])
    compliant = [s for s in scenarios if s["tier"] in (TIER_PRIMARY, TIER_COMPLIANT_ALT)]
    if compliant:
        lowest = min(compliant, key=lambda s: Decimal(s["netTaxDueCny"]))
        for s in scenarios:
            s["deltaVsPrimaryCny"] = str(
                (Decimal(s["netTaxDueCny"]) - primary_net).quantize(Q)
            )
            if s is lowest and Decimal(s["netTaxDueCny"]) <= primary_net:
                s["isLowestNetTax"] = True

    monthly = build_monthly_breakdown(
        raw_events, provider=provider, tax_year=tax_year, fallback_rate=fallback_rate
    )
    monthly_summary = (
        _summarize_from_engine(
            engine,
            apply_fx_to_events(
                _clone_events(raw_events),
                provider=provider,
                policy="safe_harbor_monthly",
                fallback_rate=fallback_rate,
            ),
            snapshot,
            tax_year,
        )
        if monthly
        else {}
    )

    for s in scenarios:
        if s["tier"] not in (TIER_PRIMARY, TIER_COMPLIANT_ALT):
            continue
        lf = compute_late_fee(
            s["taxDueCny"],
            tax_year=tax_year,
            filing_date=s.get("filingDate"),
            policy=s.get("fxPolicy", ""),
        )
        if lf:
            s["lateFee"] = lf
            s["totalPayableCny"] = lf.get("totalPayableCny", s["netTaxDueCny"])

    tips: list[str] = []
    payable_rank = [
        s for s in compliant if s.get("totalPayableCny")
    ]
    if len(payable_rank) >= 2:
        best = min(payable_rank, key=lambda s: Decimal(s["totalPayableCny"]))
        if Decimal(best["totalPayableCny"]) < Decimal(scenarios[0].get("totalPayableCny") or scenarios[0]["netTaxDueCny"]):
            tips.append(
                f"含滞纳金后最低总支出约 {best['totalPayableCny']} 元（{best['label']}），"
                f"低于主场景合计；请确认该申报时点仍属合规。"
            )

    lowest_compliant = [s for s in compliant if s.get("isLowestNetTax")]
    if lowest_compliant and lowest_compliant[0].get("fxPolicy") != primary_policy:
        lc = lowest_compliant[0]
        tips.append(
            f"合规口径中最低应补税为 {lc['netTaxDueCny']} 元（{lc['label']}），"
            f"较主场景 {'少' if Decimal(lc['deltaVsPrimaryCny'] or '0') < 0 else '多'} "
            f"{abs(Decimal(lc['deltaVsPrimaryCny'] or '0'))} 元；须结合滞纳金综合判断。"
        )
    elif primary_policy == "cn_supplemental" and monthly_summary:
        m_net = Decimal(monthly_summary.get("netTaxDueCny", "0"))
        if m_net != primary_net:
            tips.append(
                f"分月折算辅助口径应补税 {m_net} 元（与补缴统一汇率 {primary_net} 元不同），"
                "分月结果仅用于台账核对，补缴仍以统一汇率为准。"
            )

    return {
        "primaryPolicy": primary_policy,
        "primaryFilingDate": primary_filing_date,
        "scenarios": scenarios,
        "monthlyBreakdown": monthly,
        "monthlyPolicySummary": monthly_summary,
        "optimizationTips": tips,
    }
