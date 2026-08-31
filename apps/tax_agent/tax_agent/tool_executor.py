"""Map Ollama tool_calls to ChatTurnResult (deterministic, auditable)."""

from __future__ import annotations

import json
from typing import Any

from tax_agent.chat_orchestrator import ChatTurnResult
from tax_agent.coverage_check import build_coverage_report, format_coverage_reply_zh
from tax_agent.filing_narrative import build_filing_narrative
from tax_agent.filing_table import build_filing_report
from tax_agent.risk_engine import RiskContext, assess_risk
from tax_agent.session_context import SessionContext
from tax_agent.tax_insight import build_tax_insight, format_insight_reply_zh

_FUTU_UPLOAD_HINT = (
    "请从富途 App「我的税表」导出 Annual_Statement xlsx（含证券-交易流水）。\n"
    "跨年卖出请同会话上传买入年至卖出年全部税表（如 2022+2023）。"
)


def _tool_args(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and raw.strip():
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def _normalize_follow_up(raw: Any) -> list[str]:
    if isinstance(raw, list):
        return [str(q).strip() for q in raw if str(q).strip()][:3]
    if isinstance(raw, str) and raw.strip():
        return [raw.strip()]
    return []


def _summary_reply(ctx: SessionContext) -> str | None:
    s = ctx.last_summary or {}
    if not s:
        return None
    net = s.get("netTaxDueCny")
    taxable = s.get("taxableIncomeCny")
    tax_due = s.get("taxDueCny")
    if net is None and taxable is None:
        return None
    return (
        f"最近一次测算：应纳税所得额 {taxable or '—'} 元，"
        f"应纳税额 {tax_due or '—'} 元，预计应补 {net or '—'} 元。"
        "如需其他年度，请说明年份或点侧栏「批量测算各年度」。"
    )


def apply_tool_call(
    name: str,
    arguments: Any,
    ctx: SessionContext,
) -> ChatTurnResult:
    args = _tool_args(arguments)
    n = (name or "").strip()

    if n == "compute_tax":
        year = int(args.get("tax_year") or ctx.tax_year)
        resident = str(args.get("resident_status") or ctx.resident_status or "cn_tax_resident")
        if not ctx.dataset_id:
            return ChatTurnResult(reply=_FUTU_UPLOAD_HINT, action="need_upload")
        reply = (args.get("reply") or "").strip() or (
            f"好的，将按 **{year}** 年度测算富途境外所得（结果由规则引擎生成）。"
        )
        scope = str(args.get("filing_scope") or ctx.filing_scope or "foreign_only")
        hint = ""
        if scope == "includes_domestic" and not ctx.domestic_income_provided:
            hint = "（R008：已选含境内综合所得但未提供境内收入，结果仅含境外部分。）"
        return ChatTurnResult(
            reply=reply + hint,
            action="compute",
            compute_params={
                "taxYear": year,
                "residentStatus": resident,
                "filingScope": scope,
                "fxPolicy": "cn_supplemental",
            },
        )

    if n == "request_upload":
        if ctx.dataset_id and (ctx.event_count or 0) > 0:
            existing = _summary_reply(ctx)
            if existing:
                return ChatTurnResult(
                    reply=(args.get("reply") or "").strip() or existing,
                    action="none",
                )
            return ChatTurnResult(
                reply=(
                    "税表已上传并解析完成。请点侧栏「测算税额」或说「测算 2023 年税额」。"
                    "若涉及跨年持仓，请确认已上传全部相关年度 Annual_Statement。"
                ),
                action="none",
            )
        reply = (args.get("reply") or "").strip() or "为测算境外所得个税，请先上传富途税表。"
        return ChatTurnResult(reply=reply + "\n\n" + _FUTU_UPLOAD_HINT, action="need_upload")

    if n == "get_tax_insight":
        year = int(args.get("tax_year") or ctx.tax_year)
        focus = str(args.get("focus") or ctx.tax_insight_plan or "holdings_year_end")
        if not ctx.dataset_id:
            return ChatTurnResult(reply=_FUTU_UPLOAD_HINT, action="need_upload")
        insight = ctx.tax_insight or build_tax_insight(
            focus=focus,
            tax_year=year,
            data_quality=ctx.data_quality,
            events=ctx.events,
            last_summary=ctx.last_summary,
            fx_provider=ctx.fx_provider,
        )
        reply = (args.get("reply") or "").strip() or format_insight_reply_zh(insight)
        return ChatTurnResult(reply=reply, action="none")

    if n == "check_coverage":
        year = int(args.get("tax_year") or ctx.tax_year)
        if not ctx.dataset_id:
            return ChatTurnResult(reply=_FUTU_UPLOAD_HINT, action="need_upload")
        report = build_coverage_report(
            data_quality=ctx.data_quality,
            events=ctx.events,
            focus_tax_year=year,
        )
        reply = (args.get("reply") or "").strip() or format_coverage_reply_zh(report)
        return ChatTurnResult(reply=reply, action="none")

    if n == "get_filing_table":
        if not ctx.dataset_id:
            return ChatTurnResult(reply=_FUTU_UPLOAD_HINT, action="need_upload")
        years = None
        if args.get("tax_year"):
            years = [int(args["tax_year"])]
        report = build_filing_report(
            ctx.data_quality or {},
            provider=ctx.fx_provider,
            years=years,
            events=list(ctx.events or []),
        )
        if report.get("error"):
            return ChatTurnResult(
                reply=f"无法生成申报表：{report['error']}",
                action="none",
            )
        intro = (args.get("reply") or "").strip() or "申报数据表（四列权威口径）如下："
        md = report.get("markdown") or ""
        return ChatTurnResult(
            reply=intro + "\n\n" + md,
            action="show_filing_table",
            compute_params={"filingTable": report},
        )

    if n == "compose_filing_narrative":
        year = int(args.get("tax_year") or ctx.tax_year)
        if not ctx.dataset_id:
            return ChatTurnResult(reply=_FUTU_UPLOAD_HINT, action="need_upload")
        result = build_filing_narrative(
            data_quality=ctx.data_quality,
            tax_year=year,
            fx_provider=ctx.fx_provider,
            events=list(ctx.events or []),
        )
        if result.get("error"):
            return ChatTurnResult(
                reply=f"无法生成申报说明：{result['error']}",
                action="none",
            )
        intro = (args.get("reply") or "").strip() or f"{year} 年度申报说明如下："
        return ChatTurnResult(
            reply=intro + "\n\n" + result["narrative"],
            action="none",
        )

    if n == "get_risk_brief":
        if not ctx.dataset_id:
            return ChatTurnResult(reply=_FUTU_UPLOAD_HINT, action="need_upload")
        assessment = assess_risk(
            RiskContext(
                resident_status=ctx.resident_status or "cn_tax_resident",
                data_quality=ctx.data_quality or {},
                broker_template_id=ctx.broker_template_id or "futu_tax_v1",
                filing_scope=ctx.filing_scope or "foreign_only",
                events=list(ctx.events or []),
                confidence_base=0.9,
                domestic_income_provided=ctx.domestic_income_provided,
            )
        )
        lines = [
            "【风险简报】",
            f"- 等级：{assessment.level.value}",
            f"- 触发规则：{', '.join(assessment.triggered_rules) or '无'}",
        ]
        for msg in assessment.messages[:8]:
            lines.append(f"- {msg}")
        reply = (args.get("reply") or "").strip() or "\n".join(lines)
        return ChatTurnResult(reply=reply, action="none")

    if n == "show_report":
        rid = (args.get("run_id") or ctx.last_run_id or "").strip()
        reply = (args.get("reply") or "").strip() or "正在加载测算报告。"
        if not rid:
            return ChatTurnResult(
                reply=reply + "\n\n尚无测算记录，请先上传税表并测算。",
                action="none",
            )
        return ChatTurnResult(
            reply=reply,
            action="show_report",
            compute_params={"runId": rid},
        )

    if n == "reply_only":
        reply = (args.get("reply") or "").strip()
        if not reply and ctx.last_summary:
            reply = _summary_reply(ctx) or "已收到。"
        if not reply:
            reply = "已收到。"
        follow = _normalize_follow_up(args.get("follow_up_questions"))
        if follow:
            reply += "\n\n" + "\n".join(f"- {q}" for q in follow)
        return ChatTurnResult(reply=reply, action="none")

    return ChatTurnResult(reply=f"未知工具：{n}", action="none")


def apply_tool_calls(
    tool_calls: list[dict[str, Any]],
    ctx: SessionContext,
) -> tuple[ChatTurnResult | None, list[str]]:
    """
    Pick the highest-priority tool result when the model emits multiple calls.
    Priority: compute_tax > show_report > reply_only > request_upload
    """
    priority = {
        "compute_tax": 4,
        "show_report": 3,
        "get_filing_table": 3,
        "get_tax_insight": 3,
        "check_coverage": 3,
        "compose_filing_narrative": 3,
        "get_risk_brief": 3,
        "reply_only": 2,
        "request_upload": 1,
    }
    executed: list[str] = []
    best: ChatTurnResult | None = None
    best_rank = 0

    for tc in tool_calls:
        fn = tc.get("function") or {}
        name = str(fn.get("name") or "")
        if not name:
            continue
        executed.append(name)
        turn = apply_tool_call(name, fn.get("arguments"), ctx)
        rank = priority.get(name, 0)
        if rank >= best_rank:
            best_rank = rank
            best = turn

    return best, executed


def ollama_tool_calls_from_message(message: dict[str, Any]) -> list[dict[str, Any]]:
    raw = message.get("tool_calls")
    if not isinstance(raw, list):
        return []
    out: list[dict[str, Any]] = []
    for item in raw:
        if isinstance(item, dict) and item.get("function"):
            out.append(item)
    return out
