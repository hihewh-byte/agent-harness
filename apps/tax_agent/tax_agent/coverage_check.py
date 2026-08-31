"""Material coverage check — 跨年 FIFO 税表缺口（Harness check_coverage）。"""

from __future__ import annotations

import re
from typing import Any

from tax_agent.chat_orchestrator import ChatTurnResult
from tax_agent.cost_basis import match_fifo
from tax_agent.futu_session_fifo import collect_merged_legs
from tax_agent.harness_plan import build_filing_turn_plan
from tax_agent.session_context import SessionContext

_COVERAGE_Q = re.compile(r"(缺|覆盖|齐全|还缺|哪些年|年份.*全|材料.*够|上传.*够)", re.I)


def _packages(data_quality: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not data_quality:
        return []
    pkgs = data_quality.get("futuTaxPackages") or []
    if not pkgs and data_quality.get("futuTaxPackage"):
        pkgs = [data_quality["futuTaxPackage"]]
    return list(pkgs)


def uploaded_tax_years(data_quality: dict[str, Any] | None) -> list[int]:
    years: set[int] = set()
    for p in _packages(data_quality):
        ty = p.get("taxYear")
        if ty is not None:
            years.add(int(ty))
    dq = data_quality or {}
    for y in dq.get("yearsPresent") or dq.get("years") or []:
        years.add(int(y))
    return sorted(years)


def build_coverage_report(
    *,
    data_quality: dict[str, Any] | None,
    events: list[Any] | None = None,
    focus_tax_year: int | None = None,
) -> dict[str, Any]:
    """Deterministic coverage report for a dataset session."""
    packages = _packages(data_quality)
    uploaded = uploaded_tax_years(data_quality)
    if not packages:
        return {
            "hasDataset": False,
            "uploadedYears": uploaded,
            "requiredYears": [],
            "missingYears": [],
            "sellYears": [],
            "complete": False,
            "ambiguousSymbols": [],
            "hints": ["尚未上传富途 Annual_Statement 税表。"],
        }

    legs = collect_merged_legs(packages)
    realized, fifo_warnings = match_fifo(legs)
    sell_years = sorted({int(rg.trade_date[:4]) for rg in realized})

    required: set[int] = set(uploaded)
    if sell_years:
        lo = min(uploaded) if uploaded else min(sell_years)
        hi = max(max(uploaded) if uploaded else lo, max(sell_years))
        required.update(range(lo, hi + 1))

    for pkg in packages:
        ty = pkg.get("taxYear")
        if ty is None:
            continue
        y = int(ty)
        if pkg.get("openingPositions"):
            required.add(y)
            if y - 1 not in uploaded:
                required.add(y - 1)

    if focus_tax_year:
        required.add(int(focus_tax_year))

    required_sorted = sorted(required)
    missing = sorted(y for y in required_sorted if y not in uploaded)

    amb_syms: set[str] = set()
    for rg in realized:
        if rg.classification_status == "ambiguous" and rg.symbol:
            amb_syms.add(rg.symbol)
    if events:
        for ev in events:
            if getattr(ev, "classification_status", None) == "ambiguous":
                sym = getattr(ev, "symbol", None)
                if sym:
                    amb_syms.add(str(sym))

    hints: list[str] = []
    if missing:
        hints.append(
            f"建议补齐纳税年度税表：{', '.join(str(y) for y in missing)}。"
            "跨年卖出须上传买入年至卖出年全部 Annual_Statement。"
        )
    elif sell_years:
        hints.append(f"已覆盖卖出年度 {min(sell_years)}–{max(sell_years)} 所需税表区间。")
    else:
        hints.append("当前流水未识别到卖出实现损益；若仅有买入可暂不补年。")

    for w in fifo_warnings:
        if "期初持仓" in w or "exceeds FIFO" in w or "首笔为卖出" in w:
            hints.append(w)

    if amb_syms:
        hints.append(
            f"存在成本基础不完整标的：{', '.join(sorted(amb_syms)[:12])}（R003，请补买入年税表）。"
        )

    return {
        "hasDataset": True,
        "uploadedYears": uploaded,
        "requiredYears": required_sorted,
        "missingYears": missing,
        "sellYears": sell_years,
        "complete": len(missing) == 0 and not amb_syms,
        "ambiguousSymbols": sorted(amb_syms),
        "hints": hints,
        "fifoWarningCount": len(fifo_warnings),
    }


def format_coverage_reply_zh(report: dict[str, Any]) -> str:
    if not report.get("hasDataset"):
        return (
            "尚未上传税表。\n"
            "请从富途 App「我的税表」导出 Annual_Statement xlsx；"
            "跨年卖出需上传买入年至卖出年全部税表。"
        )

    lines = [
        "【材料覆盖检查】",
        f"- 已上传年度：{', '.join(str(y) for y in report.get('uploadedYears') or []) or '（未识别）'}",
    ]
    sell = report.get("sellYears") or []
    if sell:
        lines.append(f"- 已实现卖出归属年度：{', '.join(str(y) for y in sell)}")
    missing = report.get("missingYears") or []
    if missing:
        lines.append(f"- **缺口年度**：{', '.join(str(y) for y in missing)}")
    else:
        lines.append("- 按当前 FIFO 区间，年度税表已齐。")

    amb = report.get("ambiguousSymbols") or []
    if amb:
        lines.append(f"- 待复核标的：{', '.join(amb[:10])}")

    for h in (report.get("hints") or [])[:4]:
        if h not in lines:
            lines.append(f"- {h}")

    if report.get("complete"):
        lines.append("\n材料覆盖完整，可进行测算或生成申报数据表。")
    return "\n".join(lines)


def try_coverage_fast_turn(message: str, ctx: SessionContext) -> ChatTurnResult | None:
    plan = build_filing_turn_plan(
        message,
        default_tax_year=ctx.tax_year,
        has_dataset=bool(ctx.dataset_id),
        has_compute=bool(ctx.last_run_id or ctx.last_summary),
    )
    if plan.profile != "coverage_check" and not _COVERAGE_Q.search(message or ""):
        return None
    if plan.profile != "coverage_check" and not ctx.dataset_id:
        return None

    report = build_coverage_report(
        data_quality=ctx.data_quality,
        events=ctx.events,
        focus_tax_year=plan.tax_year,
    )
    reply = format_coverage_reply_zh(report)
    from tax_agent.fact_bundle import build_coverage_fact_bundle

    bundle = build_coverage_fact_bundle(
        report,
        fallback_markdown=reply,
        tax_year=plan.tax_year,
        journey_phase=plan.journey_phase,
    )
    return ChatTurnResult(reply=reply, action="none", fact_bundle=bundle)
