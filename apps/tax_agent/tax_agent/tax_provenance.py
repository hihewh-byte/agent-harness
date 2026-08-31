"""Deterministic policy / FX provenance for chat (PHA policy_explain lane)."""

from __future__ import annotations

from typing import Any

from tax_agent.fx_filing_rules import (
    SUPPLEMENTAL_FX_LEGAL_REF,
    default_filing_date,
    filing_date_for_request,
    resolve_filing_month_key,
    supplemental_month_key_for_tax_year,
    supplemental_reference_date,
)
from tax_agent.fx_rates import FxRateProvider


def build_fx_provenance(
    *,
    tax_year: int,
    fx_policy: str,
    filing_date: str | None,
    provider: FxRateProvider | None,
) -> dict[str, Any]:
    """Auditable FX resolution for supplemental / annual filing."""
    resolved_fd = filing_date_for_request(
        policy=fx_policy,
        tax_year=tax_year,
        filing_date=filing_date,
    ) or default_filing_date(tax_year, fx_policy)

    month_key, rule_label = resolve_filing_month_key(
        fx_policy,
        resolved_fd,
        tax_year=tax_year if fx_policy == "cn_supplemental" else None,
    )

    rate = None
    source_note = "无汇率数据集"
    data_source = None
    if provider and provider.available:
        res = provider.resolve_filing(
            fx_policy,
            resolved_fd,
            tax_year=tax_year if fx_policy == "cn_supplemental" else None,
        )
        rate = str(res.rate)
        source_note = res.note
        data_source = provider.source_label or provider.source

    out: dict[str, Any] = {
        "topic": "fx_provenance",
        "taxYear": tax_year,
        "fxPolicy": fx_policy,
        "filingDate": resolved_fd,
        "monthKey": month_key,
        "rate": rate,
        "ruleLabel": rule_label,
        "dataSource": data_source,
        "sourceNote": source_note,
        "legalRef": SUPPLEMENTAL_FX_LEGAL_REF,
        "tier": "T0",
    }

    if fx_policy == "cn_supplemental":
        out["anchorExplanation"] = (
            f"补缴 {tax_year} 年度所得：「上一纳税年度」= {tax_year - 1} 年，"
            f"取 {supplemental_reference_date(tax_year)} 对应月末中间价（{month_key}）。"
            "与办理申报公历年无关。"
        )
        out["notApplicable"] = (
            "非所得所属年末（如 2021-12-31）汇率；"
            "非办理申报公历年的上一自然年末（如 2026 年办理时取 2025-12）汇率。"
        )
    else:
        out["anchorExplanation"] = (
            f"正常年度汇算 {tax_year} 年度所得：按办理申报日 {resolved_fd} 的上一月末中间价（{month_key}）。"
        )

    return out


def format_multi_fx_provenance_reply_zh(
    rows: list[dict[str, Any]],
    *,
    fx_policy: str = "cn_supplemental",
) -> str:
    if not rows:
        return "未指定纳税年度。"
    if len(rows) == 1:
        return format_fx_provenance_reply_zh(rows[0])

    years = [r.get("taxYear") for r in rows]
    y_lo, y_hi = min(years), max(years)
    lines = [
        f"## {y_lo}–{y_hi} 年度汇率依据（申报口径 T0）",
        "",
        f"**政策**：{fx_policy}（以前年度补缴：各年取**上一纳税年度**末日中间价）",
        "",
        "| 所得年度 | 适用月键 | 汇率 (RMB/USD) | 锚定末日 |",
        "|---------|---------|----------------|----------|",
    ]
    for prov in rows:
        y = prov.get("taxYear")
        ref = f"{int(y) - 1}-12-31" if fx_policy == "cn_supplemental" else prov.get("monthKey", "")
        lines.append(
            f"| **{y}** | {prov.get('monthKey')} | **{prov.get('rate') or '—'}** | {ref} |"
        )
    lines.extend(
        [
            "",
            f"**法条依据**：{SUPPLEMENTAL_FX_LEGAL_REF}",
            f"**数据来源**：{rows[0].get('dataSource') or '—'}（PBOC 月末中间价人工校对数据集）",
            "",
            "**不适用**：所得所属年末汇率（如补缴 2023 取 2023-12）；办理申报公历年的上一自然年末汇率。",
        ]
    )
    return "\n".join(lines)


def format_fx_provenance_reply_zh(prov: dict[str, Any]) -> str:
    year = prov.get("taxYear")
    lines = [
        f"## {year} 年度汇率依据（申报口径 T0）",
        "",
        f"**政策**：{prov.get('fxPolicy')}",
        f"**办理申报日**：{prov.get('filingDate')}",
        f"**适用月份键**：{prov.get('monthKey')}",
        f"**汇率**：{prov.get('rate') or '—'} RMB/USD",
        f"**规则说明**：{prov.get('ruleLabel')}",
        "",
        f"**锚定解释**：{prov.get('anchorExplanation')}",
    ]
    if prov.get("notApplicable"):
        lines.append(f"**不适用**：{prov['notApplicable']}")
    lines.extend(
        [
            "",
            f"**数据来源**：{prov.get('dataSource') or '—'}；{prov.get('sourceNote')}",
            "",
            f"**法条依据**：{prov.get('legalRef')}",
        ]
    )
    return "\n".join(lines)


def infer_provenance_years(
    message: str,
    default: int,
    *,
    data_quality: dict | None = None,
    fx_provider: Any | None = None,
    episodic: Any | None = None,
    available_years: list[int] | None = None,
) -> list[int]:
    """解析汇率问法中的所得年度（委托 TaxTurnResolver，禁止硬编码年份区间）。"""
    from tax_agent.tax_turn_resolver import resolve_turn_scope

    dq = data_quality
    if dq is None and available_years:
        dq = {"yearsPresent": list(available_years)}
    scope = resolve_turn_scope(
        message,
        default,
        data_quality=dq,
        fx_provider=fx_provider,
        episodic=episodic,
        profile_hint="policy_explain",
    )
    return scope.tax_years


def try_provenance_fast_turn(
    message: str,
    ctx: Any,
) -> Any | None:
    from tax_agent.chat_orchestrator import ChatTurnResult
    from tax_agent.coverage_check import uploaded_tax_years
    from tax_agent.harness_plan import build_filing_turn_plan
    from tax_agent.session_turn_focus import revive_tax_session_focus

    sid = getattr(ctx, "session_id", None) or ""
    focus = revive_tax_session_focus(sid, message) if sid else None

    from tax_agent.tax_turn_resolver import (
        resolve_turn_scope,
        scope_primary_year,
        try_clarify_turn,
    )

    scope = resolve_turn_scope(
        message,
        ctx.tax_year,
        data_quality=getattr(ctx, "data_quality", None),
        fx_provider=getattr(ctx, "fx_provider", None),
        episodic=focus,
        profile_hint="policy_explain",
    )
    clarify = try_clarify_turn(scope)
    if clarify:
        return clarify

    plan = build_filing_turn_plan(
        message,
        default_tax_year=ctx.tax_year,
        has_dataset=bool(getattr(ctx, "dataset_id", None)),
        has_compute=bool(getattr(ctx, "last_run_id", None) or getattr(ctx, "last_summary", None)),
        resolved_tax_year=scope_primary_year(scope, ctx.tax_year),
        episodic_profile=focus.focus_profile if focus else None,
    )
    if plan.profile != "policy_explain":
        return None

    fx_policy = getattr(ctx, "fx_policy", None) or "cn_supplemental"
    provider = getattr(ctx, "fx_provider", None)
    filing_date = getattr(ctx, "filing_date", None)
    years = scope.tax_years
    rows = [
        build_fx_provenance(
            tax_year=y,
            fx_policy=fx_policy,
            filing_date=filing_date,
            provider=provider,
        )
        for y in years
    ]
    ctx.tax_provenance = rows[0] if len(rows) == 1 else {"multi": rows}
    reply = format_multi_fx_provenance_reply_zh(rows, fx_policy=fx_policy)
    from tax_agent.fact_bundle import build_provenance_fact_bundle

    bundle = build_provenance_fact_bundle(
        rows,
        fx_policy=fx_policy,
        fallback_markdown=reply,
        tax_year=scope_primary_year(scope, ctx.tax_year),
        has_dataset=bool(getattr(ctx, "dataset_id", None)),
        journey_phase=plan.journey_phase,
    )
    return ChatTurnResult(reply=reply, action="none", fact_bundle=bundle)
