"""Deterministic tax insight payloads for LLM interpretation (PHA evidence lane)."""

from __future__ import annotations

import json
import os
from decimal import Decimal
from typing import Any

from tax_agent.cost_basis import RealizedGain, fifo_remaining_lots_as_of, lot_cost_for_quantity
from tax_agent.filing_table import asset_type_for_gain, build_filing_report, build_filing_rows_from_packages, is_option_symbol
from tax_agent.futu_session_fifo import collect_merged_legs
from tax_agent.models import EventType
from tax_agent.tax_intent_router import resolve_tax_intent

Q = Decimal("0.01")
TAX_RATE = Decimal("0.20")
DEFAULT_FX = Decimal("7.10")

OPTION_NOTE = (
    "期权：卖出/平仓收入计入「总卖出收入」；FIFO 匹配的开仓权利金计入「原值」；"
    "到期作废（expire）处置收入为 0，已实现损失为已支付权利金（扣除已匹配成本）。"
)


def insight_fast_path_enabled() -> bool:
    v = (os.environ.get("TAX_AGENT_INSIGHT_FAST_PATH") or "1").strip().lower()
    return v not in {"0", "false", "no", "off"}


def _packages(data_quality: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not data_quality:
        return []
    pkgs = data_quality.get("futuTaxPackages") or []
    if not pkgs and data_quality.get("futuTaxPackage"):
        pkgs = [data_quality["futuTaxPackage"]]
    return list(pkgs)


def _package_for_year(packages: list[dict[str, Any]], tax_year: int) -> dict[str, Any] | None:
    for pkg in packages:
        if int(pkg.get("taxYear") or 0) == tax_year:
            return pkg
    return None


def _realized_for_year(events: list[Any], tax_year: int) -> dict[str, Any]:
    prefix = f"{tax_year}-"
    year_events = [
        e
        for e in events
        if e.event_type == EventType.CAPITAL_GAIN
        and (e.trade_date or "").startswith(prefix)
    ]
    total_usd = sum(
        (e.gross_amount.amount for e in year_events if e.gross_amount),
        Decimal("0"),
    ).quantize(Q)
    by_symbol: dict[str, Decimal] = {}
    for e in year_events:
        sym = e.symbol or "UNKNOWN"
        amt = e.gross_amount.amount if e.gross_amount else Decimal("0")
        by_symbol[sym] = by_symbol.get(sym, Decimal("0")) + amt
    top = sorted(by_symbol.items(), key=lambda x: abs(x[1]), reverse=True)[:8]
    return {
        "disposalCount": len(year_events),
        "realizedGainUsd": str(total_usd),
        "topSymbols": [
            {"symbol": sym, "realizedGainUsd": str(amt.quantize(Q))} for sym, amt in top
        ],
    }


def _position_market_value_usd(pos: dict[str, Any]) -> Decimal | None:
    if pos.get("marketValue"):
        return Decimal(str(pos["marketValue"])).quantize(Q)
    qty = Decimal(str(pos.get("quantity") or "0"))
    price = pos.get("marketPrice")
    if price and qty:
        return (qty * Decimal(str(price))).quantize(Q)
    return None


def _option_expire_summary(realized: list[RealizedGain], tax_year: int, fx: Decimal) -> dict[str, Any]:
    prefix = f"{tax_year}-"
    expires = [
        rg
        for rg in realized
        if rg.trade_date.startswith(prefix)
        and asset_type_for_gain(rg) == "option"
        and (rg.metadata or {}).get("disposalType") == "expiration"
    ]
    loss_usd = sum((rg.gain_usd for rg in expires), Decimal("0")).quantize(Q)
    loss_cny = (loss_usd * fx).quantize(Q) if loss_usd < 0 else Decimal("0")
    tax_saved = (-loss_cny * TAX_RATE).quantize(Q) if loss_cny < 0 else Decimal("0")
    return {
        "expireCount": len(expires),
        "realizedLossUsd": str(loss_usd),
        "realizedLossCny": str(loss_cny),
        "estimatedTaxOffsetCny": str(tax_saved),
        "symbols": [rg.symbol for rg in expires[:12]],
        "tier": "T0",
        "note": "期权到期作废：处置收入为 0，上列为当年已实现损失（已参与同年度盈亏相抵）。",
    }


def _deferred_closing_breakdown(
    closings: list[dict[str, Any]],
    remaining: dict[str, list],
    fx: Decimal,
) -> dict[str, Any]:
    buckets: dict[str, dict[str, Any]] = {
        "stock": {"count": 0, "marketValueUsd": Decimal("0"), "unrealizedPnlUsd": Decimal("0"), "unrealizedLossUsd": Decimal("0")},
        "option": {"count": 0, "marketValueUsd": Decimal("0"), "unrealizedPnlUsd": Decimal("0"), "unrealizedLossUsd": Decimal("0")},
    }
    rows: list[dict[str, Any]] = []
    for pos in closings:
        sym = str(pos.get("symbol") or "")
        cat = str(pos.get("category") or "")
        at = "option" if is_option_symbol(sym, cat) else "stock"
        qty = Decimal(str(pos.get("quantity") or "0"))
        mkt = _position_market_value_usd(pos)
        cost, matched = lot_cost_for_quantity(remaining.get(sym, []), qty)
        unrealized = (mkt - cost) if mkt is not None and matched else None
        row = {
            "symbol": sym,
            "assetType": at,
            "quantity": str(qty),
            "asOfDate": pos.get("asOfDate"),
            "marketValueUsd": str(mkt) if mkt is not None else None,
            "costBasisUsd": str(cost) if matched and mkt is not None else None,
            "unrealizedPnlUsd": str(unrealized.quantize(Q)) if unrealized is not None else None,
            "costBasisKnown": matched,
            "tier": "T1",
        }
        rows.append(row)
        b = buckets[at]
        b["count"] += 1
        if mkt is not None:
            b["marketValueUsd"] += mkt
        if unrealized is not None:
            b["unrealizedPnlUsd"] += unrealized
            if unrealized < 0:
                b["unrealizedLossUsd"] += unrealized

    out: dict[str, Any] = {"positions": rows, "byAssetType": {}, "tier": "T1"}
    for at, b in buckets.items():
        loss_cny = (-b["unrealizedLossUsd"] * fx).quantize(Q)
        out["byAssetType"][at] = {
            "positionCount": b["count"],
            "marketValueUsd": str(b["marketValueUsd"].quantize(Q)),
            "unrealizedPnlUsd": str(b["unrealizedPnlUsd"].quantize(Q)),
            "unrealizedLossUsd": str(b["unrealizedLossUsd"].quantize(Q)),
            "unrealizedLossCny": str(loss_cny),
            "tier": "T1",
        }
    return out


def build_tax_insight(
    *,
    focus: str,
    tax_year: int,
    data_quality: dict[str, Any] | None,
    events: list[Any] | None = None,
    last_summary: dict[str, Any] | None = None,
    fx_provider: Any = None,
) -> dict[str, Any]:
    """Build auditable JSON insight for chat / get_tax_insight tool."""
    packages = _packages(data_quality)
    insight: dict[str, Any] = {
        "profile": focus,
        "taxYear": tax_year,
        "optionNote": OPTION_NOTE,
        "disclosure": (
            "T0=申报口径（已实现损益、lastSummary、filingTable）；"
            "T1=辅助对照（期末市值、未实现盈亏、反事实敏感性，不计入申报）。"
        ),
    }

    if last_summary:
        insight["declared"] = {
            "taxableIncomeCny": last_summary.get("taxableIncomeCny"),
            "taxDueCny": last_summary.get("taxDueCny"),
            "netTaxDueCny": last_summary.get("netTaxDueCny"),
            "tier": "T0",
        }

    if events:
        insight["realized"] = _realized_for_year(events, tax_year)
        insight["realized"]["tier"] = "T0"

    pkg = _package_for_year(packages, tax_year)
    if not pkg:
        insight["error"] = f"未找到 {tax_year} 年度税表包；请确认已上传该年 Annual_Statement。"
        return insight

    filing_rows, realized, _ = build_filing_rows_from_packages(
        packages, provider=fx_provider, years=[tax_year]
    )
    filing_row = filing_rows[0] if filing_rows else None
    fx = filing_row.fx_rate if filing_row else DEFAULT_FX
    fx_note = filing_row.fx_note if filing_row else f"默认汇率 {DEFAULT_FX}"
    fx_policy = filing_row.fx_policy if filing_row else "cn_supplemental"

    insight["fx"] = {
        "rate": str(fx),
        "policy": fx_policy,
        "note": fx_note,
        "filingDate": filing_row.filing_date if filing_row else "",
        "tier": "T0",
    }

    if filing_row:
        fd = filing_row.to_dict()
        insight["filingTable"] = {
            "taxYear": tax_year,
            "scope": "property_transfer",
            "netGainUsd": fd.get("netGainUsd"),
            "netGainCny": fd.get("netGainCny"),
            "taxableIncomeCny": fd.get("taxableIncomeCny"),
            "taxDueCny": fd.get("taxDueCny"),
            "stock": fd.get("stock"),
            "option": fd.get("option"),
            "tier": "T0",
        }
        insight["optionExpire"] = _option_expire_summary(realized, tax_year, fx)

    if events:
        full_rep = build_filing_report(
            data_quality or {},
            provider=fx_provider,
            years=[tax_year],
            events=list(events),
        )
        combined = next(
            (r for r in full_rep.get("combinedRows") or [] if int(r.get("taxYear") or 0) == tax_year),
            None,
        )
        if combined:
            gt = combined.get("grandTotal")
            if gt:
                insight["grandTotal"] = {**gt, "tier": "T0"}
            ci = combined.get("classifiedIncome")
            if ci:
                insight["classifiedIncome"] = {**ci, "tier": "T0"}

    closings = list(pkg.get("closingPositions") or [])
    legs = collect_merged_legs(packages)
    as_of = f"{tax_year}-12-31"
    if closings:
        as_of = str(closings[0].get("asOfDate") or as_of)
    remaining = fifo_remaining_lots_as_of(legs, as_of)

    deferred = _deferred_closing_breakdown(closings, remaining, fx)
    insight["deferredUnrealized"] = deferred
    insight["closingPositions"] = deferred["positions"]

    total_unrealized = Decimal("0")
    total_loss = Decimal("0")
    for pos in deferred["positions"]:
        pnl = pos.get("unrealizedPnlUsd")
        if pnl:
            v = Decimal(str(pnl))
            total_unrealized += v
            if v < 0:
                total_loss += v

    insight["unrealizedSummary"] = {
        "asOfDate": as_of,
        "positionCount": len(closings),
        "unrealizedPnlTotalUsd": str(total_unrealized.quantize(Q)),
        "unrealizedLossTotalUsd": str(total_loss.quantize(Q)),
        "unrealizedLossCny": str((-total_loss * fx).quantize(Q)),
        "fxRateUsed": str(fx),
        "tier": "T1",
    }

    if focus in ("realized_vs_deferred", "holdings_year_end") and last_summary:
        taxable = Decimal(str(last_summary.get("taxableIncomeCny") or "0"))
        loss_cny = (-total_loss * fx).quantize(Q)
        tax_saved = (loss_cny * TAX_RATE).quantize(Q)
        insight["sensitivity"] = {
            "note": (
                "若当年末按市价卖出全部浮亏持仓，在同年度盈亏相抵口径下，"
                "应税所得可能减少约下方金额；此为反事实辅助对照，非默认申报口径。"
            ),
            "unrealizedLossOffsetCny": str(loss_cny),
            "estimatedTaxReductionCny": str(tax_saved),
            "counterfactualTaxableIncomeCny": str(max(Decimal("0"), taxable - loss_cny).quantize(Q)),
            "tier": "T1",
        }

    if focus == "realized_vs_deferred":
        insight["interpretationHints"] = [
            "【T0 已实现】境外财产转让所得仅对当年卖出/到期了结的损益计税；期权 expire 损失已计入 FIFO。",
            "【T1 未实现】期末仍持有的浮亏股/期权不计入当年应税所得；未卖出则当年无法抵减已实现盈利。",
            "「盈利偏高」若因未卖出浮亏未抵减 → 见 deferredUnrealized / sensitivity；"
            "若 expire 损失已较大但仍应税高 → 见 optionExpire 与 filingTable 股票段净盈利体量。",
        ]

    return insight


def format_tax_insight_block(insight: dict[str, Any]) -> str:
    """PHA-style evidence lane block (separate from raw user message)."""
    body = json.dumps(insight, ensure_ascii=False, indent=2)
    return (
        "【TAX_INSIGHT】以下为后端确定性洞察 JSON，回答时：\n"
        "- T0 字段可引用为申报口径数字；\n"
        "- T1 字段须标明「辅助对照/未实现/非申报口径」；\n"
        "- 禁止引用 JSON 外的金额。\n\n"
        f"{body}"
    )


def format_insight_reply_zh(insight: dict[str, Any]) -> str:
    """Deterministic narrative (fast path / rules fallback)."""
    if insight.get("error"):
        return str(insight["error"])

    year = insight.get("taxYear")
    lines = [f"## {year} 年度损益与持仓对照", ""]

    fx = insight.get("fx") or {}
    if fx.get("rate"):
        pol = "正常年度汇算" if fx.get("policy") == "cn_annual_filing" else "以前年度补缴"
        lines.append(f"**汇率（T0）**：{fx['rate']} RMB/USD（{pol}；{fx.get('note', '')}）")
        lines.append("")

    declared = insight.get("declared") or {}
    ft = insight.get("filingTable") or {}
    ci = insight.get("classifiedIncome") or {}
    gt = insight.get("grandTotal") or {}
    has_cls = bool(ci.get("dividend") or ci.get("interest"))

    net_due = declared.get("netTaxDueCny") or gt.get("netTaxDueCny")
    taxable_total = declared.get("taxableIncomeCny") or gt.get("taxableIncomeCny")

    if has_cls or gt:
        lines.append("### 一、全税目合计（T0）")
        if taxable_total:
            lines.append(f"- 应纳税所得额（合计）：**{taxable_total}** 元")
        if net_due:
            lines.append(f"- 预计应补税额（合计）：**{net_due}** 元")
        lines.append("- 财产转让与股息/利息分税目计税，不得跨类抵减。")
        lines.append("")

    if has_cls:
        lines.append("### 二、股息 / 利息（T0，分类所得）")
        if ci.get("dividend"):
            d = ci["dividend"]
            lines.append(
                f"- 股息：收入 **{d.get('grossCny')}** 元，应税 **{d.get('taxableIncomeCny')}** 元，"
                f"应补 **{d.get('netTaxDueCny')}** 元"
            )
        if ci.get("interest"):
            it = ci["interest"]
            lines.append(
                f"- 利息：收入 **{it.get('grossCny')}** 元，应税 **{it.get('taxableIncomeCny')}** 元，"
                f"应补 **{it.get('netTaxDueCny')}** 元"
            )
        lines.append("")

    prop_taxable = ft.get("taxableIncomeCny")
    if prop_taxable is not None or ft.get("stock") or ft.get("option"):
        sec = "三" if has_cls else "一"
        lines.append(f"### {sec}、财产转让（T0，申报四列）")
        if prop_taxable is not None:
            lines.append(f"- 应纳税所得额：**{prop_taxable}** 元")
        if ft.get("taxDueCny"):
            lines.append(f"- 应纳税额：**{ft['taxDueCny']}** 元")
        if ft.get("stock"):
            s = ft["stock"]
            lines.append(
                f"- 股票已实现净损益：**{s.get('netGainCny')}** 元（{s.get('disposalCount')} 笔）"
            )
        if ft.get("option"):
            o = ft["option"]
            lines.append(
                f"- 期权已实现净损益：**{o.get('netGainCny')}** 元（{o.get('disposalCount')} 笔）"
            )
        lines.append("")
    elif taxable_total and not has_cls:
        lines.append("### 一、申报口径（T0）")
        lines.append(f"- 应纳税所得额：**{taxable_total}** 元")
        if net_due:
            lines.append(f"- 预计应补税额：**{net_due}** 元")
        lines.append("")

    oe = insight.get("optionExpire") or {}
    if oe.get("expireCount"):
        sec_oe = "四" if has_cls and (prop_taxable is not None or ft.get("stock")) else ("三" if has_cls else "二")
        lines.append(f"### {sec_oe}、期权到期作废（T0，已实现）")
        lines.append(f"- 到期/作废笔数：**{oe['expireCount']}**")
        lines.append(f"- 已实现损失合计：**{oe.get('realizedLossUsd')}** USD（约 **{oe.get('realizedLossCny')}** 元）")
        lines.append(f"- 已参与当年盈亏相抵；约抵税 **{oe.get('estimatedTaxOffsetCny')}** 元（20%×损失）")
        if oe.get("symbols"):
            lines.append(f"- 涉及标的：{', '.join(oe['symbols'][:8])}")
        lines.append(f"- {oe.get('note', OPTION_NOTE)}")
        lines.append("")

    du = insight.get("deferredUnrealized") or {}
    us = insight.get("unrealizedSummary") or {}
    if us.get("positionCount"):
        sec_def = "五" if has_cls and oe.get("expireCount") else ("四" if oe.get("expireCount") else ("三" if has_cls else "二"))
        lines.append(f"### {sec_def}、期末仍持有未卖出（T1，未实现，不计入申报）")
        lines.append(
            f"- 截止 {us.get('asOfDate')}，共 **{us['positionCount']}** 个标的；"
            f"浮亏合计 **{us.get('unrealizedLossTotalUsd')}** USD（约 **{us.get('unrealizedLossCny')}** 元）"
        )
        by_at = du.get("byAssetType") or {}
        for at, label in (("stock", "股票"), ("option", "期权")):
            seg = by_at.get(at) or {}
            if seg.get("positionCount"):
                lines.append(
                    f"  · {label}：{seg['positionCount']} 个，浮亏 **{seg.get('unrealizedLossUsd')}** USD"
                    f"（约 **{seg.get('unrealizedLossCny')}** 元）"
                )
        for pos in (insight.get("closingPositions") or [])[:6]:
            if pos.get("unrealizedPnlUsd") and Decimal(str(pos["unrealizedPnlUsd"])) < 0:
                lines.append(
                    f"  · {pos.get('symbol')}（{pos.get('assetType')}）：未实现 {pos['unrealizedPnlUsd']} USD"
                )
        lines.append("")

    sens = insight.get("sensitivity") or {}
    if sens.get("unrealizedLossOffsetCny") and Decimal(str(sens["unrealizedLossOffsetCny"])) > 0:
        lines.append(f"### 反事实辅助对照（T1，非申报口径）")
        lines.append(
            f"- 若 {year} 年末按市价卖出全部浮亏仓，应税所得或可减少约 **{sens['unrealizedLossOffsetCny']}** 元"
        )
        if sens.get("estimatedTaxReductionCny"):
            lines.append(f"- 约少缴个税 **{sens['estimatedTaxReductionCny']}** 元（按 20%）")
        if sens.get("counterfactualTaxableIncomeCny"):
            lines.append(f"- 反事实应纳税所得额约 **{sens['counterfactualTaxableIncomeCny']}** 元")
        lines.append(f"- {sens.get('note', '')}")
        lines.append("")

    lines.append("### 结论")
    for hint in insight.get("interpretationHints") or []:
        lines.append(f"- {hint}")

    return "\n".join(lines).strip()


def try_insight_fast_turn(message: str, ctx: Any) -> Any | None:
    """Return ChatTurnResult when insight fast path applies."""
    from tax_agent.chat_orchestrator import ChatTurnResult

    if not insight_fast_path_enabled():
        return None
    plan = resolve_tax_intent(
        message,
        default_tax_year=ctx.tax_year,
        has_dataset=bool(ctx.dataset_id),
        has_compute=bool(getattr(ctx, "last_run_id", None) or getattr(ctx, "last_summary", None)),
    )
    if not plan.inject_insight or not ctx.dataset_id or not ctx.data_quality:
        return None
    insight = ctx.tax_insight or build_tax_insight(
        focus=plan.focus,
        tax_year=plan.tax_year,
        data_quality=ctx.data_quality,
        events=ctx.events,
        last_summary=ctx.last_summary,
        fx_provider=getattr(ctx, "fx_provider", None),
    )
    if insight.get("error"):
        return ChatTurnResult(reply=str(insight["error"]), action="none")
    fallback = format_insight_reply_zh(insight)
    from tax_agent.fact_bundle import build_insight_fact_bundle

    bundle = build_insight_fact_bundle(
        insight,
        fallback_markdown=fallback,
        has_dataset=bool(ctx.dataset_id),
    )
    return ChatTurnResult(reply=fallback, action="none", fact_bundle=bundle)
