"""Filing narrative (F8) — 申报说明叙述；数字仅来自 filing_table。"""

from __future__ import annotations

import os
from typing import Any

from tax_agent.chat_orchestrator import ChatTurnResult
from tax_agent.filing_table import build_filing_report
from tax_agent.harness_plan import FilingTurnPlan, build_filing_turn_plan
from tax_agent.session_context import SessionContext

_POLISH_SYSTEM = """你是报税申报说明润色助手。
任务：在保持全部 {{NUM_n}} 占位符不变的前提下，将草稿改写为更通顺的正式中文说明信。
硬性规则：
- 不得删除、修改、重排任何 {{NUM_n}} 占位符（一个字符都不能改）。
- 不得新增任何数字、金额、税率或汇率。
- 不得编造税务事实；仅润色表述与段落衔接。
- 保留「仅供参考，不构成税务意见」类免责声明。
输出：仅正文，不要 JSON。"""


def narrative_polish_enabled() -> bool:
    return os.environ.get("TAX_NARRATIVE_LLM_POLISH", "1").strip() not in (
        "0",
        "false",
        "no",
        "off",
    )


def should_polish_narrative(message: str, *, llm_on: bool) -> bool:
    if not llm_on or not narrative_polish_enabled():
        return False
    msg = (message or "").strip()
    if "不润色" in msg or "不要润色" in msg:
        return False
    if any(k in msg for k in ("润色", "正式一点", "说明信", "叙述")):
        return True
    return narrative_polish_enabled()


def _row_for_year(rows: list[dict[str, Any]], tax_year: int) -> dict[str, Any] | None:
    for r in rows:
        if int(r.get("taxYear") or 0) == tax_year:
            return r
    return None


def compose_filing_narrative_text(
    row: dict[str, Any],
    *,
    tax_year: int,
    warnings: list[str] | None = None,
    classified_income: dict[str, Any] | None = None,
    grand_total: dict[str, Any] | None = None,
) -> str:
    """确定性申报说明（财产转让四列 + 可选股息/利息，数字均来自申报数据表）。"""
    fx = row.get("fxRate") or "—"
    fx_note = row.get("fxNote") or ""
    pol = "正常年度汇算" if row.get("fxPolicy") == "cn_annual_filing" else "以前年度补缴"

    lines = [f"【{tax_year} 年度境外所得申报说明（草稿）】", ""]
    if grand_total:
        lines.extend(
            [
                "零、全税目合计",
                f"- 应纳税所得额合计：{grand_total.get('taxableIncomeCny')} 元",
                f"- 应纳税额合计：{grand_total.get('taxDueCny')} 元",
                f"- 应补税额合计：{grand_total.get('netTaxDueCny')} 元",
                "（财产转让与股息/利息分税目，不得跨类抵减。）",
                "",
            ]
        )

    lines.extend(
        [
            f"本人为居民纳税人，{tax_year} 年度通过富途证券取得境外所得，分税目申报。",
            "",
            "一、财产转让所得（四列）",
            f"- 总收入（折合人民币）：{row.get('grossProceedsCny')} 元"
            f"（美元 {row.get('grossProceedsUsd')}）",
            f"- 资产原值（折合人民币）：{row.get('costBasisCny')} 元"
            f"（美元 {row.get('costBasisUsd')}）",
            f"- 合理费用（卖出佣金等）：{row.get('reasonableFeeCny')} 元"
            f"（美元 {row.get('reasonableFeeUsd')}）",
            f"- 应纳税所得额：{row.get('taxableIncomeCny')} 元"
            f"（净损益折合人民币 {row.get('netGainCny')} 元，亏损按 0 计）",
            "",
            "二、财产转让税额",
            f"- 适用税率 20%，应纳税额 {row.get('taxDueCny')} 元。",
        ]
    )

    next_sec = 3
    if classified_income and (classified_income.get("dividend") or classified_income.get("interest")):
        lines.append("")
        lines.append("三、股息 / 利息（分类所得）")
        if classified_income.get("dividend"):
            d = classified_income["dividend"]
            lines.append(
                f"- 股息：收入 {d.get('grossCny')} 元，应税 {d.get('taxableIncomeCny')} 元，"
                f"应补 {d.get('netTaxDueCny')} 元（境外已扣 {d.get('foreignTaxPaidCny')} 元）。"
            )
        if classified_income.get("interest"):
            it = classified_income["interest"]
            lines.append(
                f"- 利息：收入 {it.get('grossCny')} 元，应税 {it.get('taxableIncomeCny')} 元，"
                f"应补 {it.get('netTaxDueCny')} 元。"
            )
        next_sec = 4

    lines.extend(
        [
            "",
            f"{next_sec}、汇率",
            f"- {pol}，汇率 {fx} RMB/USD。{fx_note}".strip(),
            "",
            f"{next_sec + 1}、说明",
            "- 买入成本按先进先出（FIFO）匹配；卖出佣金计入合理费用，不重复扣减。",
            "- 股息/利息不得并入财产转让四列；数字均来自系统申报数据表。",
        ]
    )

    stock = row.get("stock")
    option = row.get("option")
    if stock or option:
        lines.append("")
        lines.append(f"{next_sec + 2}、财产转让分项")
        if stock:
            lines.append(
                f"- 股票：净损益 {stock.get('netGainCny')} 元，"
                f"处置 {stock.get('disposalCount')} 笔。"
            )
        if option:
            lines.append(
                f"- 期权：净损益 {option.get('netGainCny')} 元，"
                f"处置 {option.get('disposalCount')} 笔。"
            )

    if warnings:
        lines.append("")
        lines.append("复核提示")
        for w in warnings[:5]:
            lines.append(f"- {w}")

    lines.append("")
    lines.append("（仅供参考，不构成税务意见。）")
    return "\n".join(lines)


def build_filing_narrative(
    *,
    data_quality: dict[str, Any] | None,
    tax_year: int,
    fx_provider: Any = None,
    events: list[Any] | None = None,
) -> dict[str, Any]:
    report = build_filing_report(
        data_quality or {},
        provider=fx_provider,
        years=[tax_year],
        events=events,
    )
    if report.get("error"):
        return {"error": report["error"]}
    row = _row_for_year(report.get("rows") or [], tax_year)
    if not row:
        years = [r.get("taxYear") for r in report.get("rows") or []]
        cls_years = [r.get("taxYear") for r in (report.get("classifiedIncome") or {}).get("rows") or []]
        avail = sorted({*(years or []), *(cls_years or [])})
        return {
            "error": f"申报表无 {tax_year} 年数据",
            "availableYears": avail,
        }
    combined = next(
        (r for r in report.get("combinedRows") or [] if int(r.get("taxYear") or 0) == tax_year),
        None,
    )
    classified = (combined or {}).get("classifiedIncome")
    grand = (combined or {}).get("grandTotal")
    text = compose_filing_narrative_text(
        row,
        tax_year=tax_year,
        warnings=(report.get("warnings") or [])[:8],
        classified_income=classified,
        grand_total=grand,
    )
    return {
        "taxYear": tax_year,
        "narrative": text,
        "row": row,
        "classifiedIncome": classified,
        "grandTotal": grand,
        "filingTable": report,
        "baseNarrative": text,
        "polished": False,
    }


def polish_filing_narrative(
    base_narrative: str,
    *,
    row: dict[str, Any],
    tax_year: int,
    data_quality: dict[str, Any] | None = None,
    fx_provider: Any = None,
    model_override: str | None = None,
    events: list[Any] | None = None,
) -> tuple[str, dict[str, Any]]:
    """Layer-1：占位符冻结 → LLM 润色 → 还原 → numerics strict。"""
    meta: dict[str, Any] = {"polished": False}
    from tax_agent.filing_session_state import FilingSessionState
    from tax_agent.llm_model_resolver import resolve_tax_agent_model
    from tax_agent.numerics_audit import (
        audit_response_numerics,
        build_numerics_manifest,
        freeze_numerics_placeholders,
        placeholders_intact,
        restore_numerics_placeholders,
    )
    from tax_agent.pha_llm import chat_completion_messages, import_ollama_provider, ollama_base_url

    state = FilingSessionState(
        focus_tax_year=tax_year,
        data_quality=data_quality,
        fx_provider=fx_provider,
        events=list(events) if events else None,
        last_filing_snapshot={"rows": [row]},
    )
    plan = FilingTurnPlan(
        profile="filing_narrative",
        focus="narrative",
        tax_year=tax_year,
        journey_phase="reviewing",
        slots_tier0=(),
        slots_tier1=(),
        forbidden=(),
        tools_allowed=(),
        task_text="",
    )
    manifest = build_numerics_manifest(state, plan)

    frozen, mapping = freeze_numerics_placeholders(base_narrative, manifest)
    if not mapping:
        meta["reason"] = "no_placeholders"
        return base_narrative, meta

    resolution = resolve_tax_agent_model(override=model_override)
    if not resolution.model:
        meta["reason"] = resolution.reason or "no_model"
        return base_narrative, meta

    try:
        Provider = import_ollama_provider()
        provider = Provider(
            base_url=ollama_base_url(),
            model=resolution.model,
            timeout_seconds=float(os.environ.get("TAX_AGENT_LLM_TIMEOUT_SECONDS", "120")),
        )
        raw = chat_completion_messages(
            provider,
            messages=[
                {"role": "system", "content": _POLISH_SYSTEM},
                {
                    "role": "user",
                    "content": f"纳税年度 {tax_year}。请润色以下草稿：\n\n{frozen}",
                },
            ],
            json_mode=False,
        )
        polished = (raw or "").strip()
        if not polished or not placeholders_intact(polished, mapping):
            meta["reason"] = "placeholder_damaged"
            return base_narrative, meta
        restored = restore_numerics_placeholders(polished, mapping)
        audit = audit_response_numerics(restored, manifest, strict=True)
        if not audit.ok:
            meta["reason"] = "numerics_audit_failed"
            meta["numericsAudit"] = audit.to_dict()
            return base_narrative, meta
        meta.update(
            {
                "polished": True,
                "model": resolution.model,
                "numericsAudit": audit.to_dict(),
            }
        )
        return restored, meta
    except Exception as exc:
        meta["reason"] = f"polish_error:{exc}"
        return base_narrative, meta


def deliver_filing_narrative(
    ctx: SessionContext,
    tax_year: int,
    *,
    polish: bool = False,
    model_override: str | None = None,
) -> dict[str, Any]:
    result = build_filing_narrative(
        data_quality=ctx.data_quality,
        tax_year=tax_year,
        fx_provider=ctx.fx_provider,
        events=ctx.events,
    )
    if result.get("error"):
        return result
    if polish:
        polished, pmeta = polish_filing_narrative(
            result["narrative"],
            row=result["row"],
            tax_year=tax_year,
            data_quality=ctx.data_quality,
            fx_provider=ctx.fx_provider,
            model_override=model_override,
            events=ctx.events,
        )
        result["narrative"] = polished
        result["polishMeta"] = pmeta
        result["polished"] = bool(pmeta.get("polished"))
    return result


def try_narrative_fast_turn(
    message: str,
    ctx: SessionContext,
    plan=None,
    *,
    polish: bool = False,
    model_override: str | None = None,
) -> ChatTurnResult | None:
    plan = plan or build_filing_turn_plan(
        message,
        default_tax_year=ctx.tax_year,
        has_dataset=bool(ctx.dataset_id),
        has_compute=bool(ctx.last_run_id or ctx.last_summary),
    )
    if plan.profile != "filing_narrative":
        return None
    if not ctx.dataset_id:
        return ChatTurnResult(
            reply="请先上传富途 Annual_Statement 税表后再生成申报说明。",
            action="need_upload",
        )
    result = deliver_filing_narrative(
        ctx,
        plan.tax_year,
        polish=polish,
        model_override=model_override,
    )
    if result.get("error"):
        avail = result.get("availableYears") or []
        hint = f"可用年度：{', '.join(str(y) for y in avail)}" if avail else ""
        return ChatTurnResult(
            reply=f"无法生成申报说明：{result['error']}。{hint}",
            action="none",
        )
    ctx.last_narrative_polished = bool(result.get("polished"))
    if result.get("polishMeta"):
        ctx.tax_insight_plan = ctx.tax_insight_plan or "filing_narrative"
    reply = result["narrative"]
    if result.get("polished"):
        reply += "\n\n（已由本地模型润色表述；金额未改，以申报数据表为准。）"
    from tax_agent.fact_bundle import build_filing_narrative_fact_bundle

    bundle = build_filing_narrative_fact_bundle(
        result["row"],
        tax_year=plan.tax_year,
        fallback_markdown=reply,
        has_dataset=bool(ctx.dataset_id),
        classified_income=result.get("classifiedIncome"),
        grand_total=result.get("grandTotal"),
    )
    return ChatTurnResult(reply=reply, action="none", fact_bundle=bundle)
