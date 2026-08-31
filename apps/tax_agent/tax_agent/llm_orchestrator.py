from __future__ import annotations

import json
import os
import re
from typing import Any

from tax_agent.chat_orchestrator import ChatTurnResult, orchestrate_user_message
from tax_agent.llm_model_resolver import TaxModelResolution, resolve_tax_agent_model, recommended_model_doc_zh
from tax_agent.ollama_memory import prepare_ollama_for_tax
from tax_agent.pha_llm import (
    chat_completion_messages,
    chat_with_tools_messages,
    import_ollama_provider,
    ollama_base_url,
)
from tax_agent.session_context import SessionContext
from tax_agent.tax_insight import (
    build_tax_insight,
    format_tax_insight_block,
    format_insight_reply_zh,
    try_insight_fast_turn,
)
from tax_agent.chat_context import build_chat_recall_block
from tax_agent.coverage_check import try_coverage_fast_turn
from tax_agent.filing_narrative import should_polish_narrative, try_narrative_fast_turn
from tax_agent.session_turn_focus import (
    episodic_bridge_block,
    focus_tier0_block,
    revive_tax_session_focus,
)
from tax_agent.tax_turn_resolver import (
    resolve_turn_scope,
    scope_primary_year,
    try_clarify_turn,
)
from tax_agent.tax_provenance import try_provenance_fast_turn
from tax_agent.policy_kb import try_policy_qa_fast_turn
from tax_agent.answer_composer import finalize_turn_with_composer
from tax_agent.chat_message_stack import (
    build_session_snapshot_dict,
    build_tax_chat_message_stack,
)
from tax_agent.filing_session_state import (
    FilingSessionState,
    build_filing_ledger_slice,
)
from tax_agent.harness_plan import build_filing_turn_plan
from tax_agent.numerics_audit import (
    audit_turn_reply,
    build_numerics_manifest,
    format_numerics_manifest_block,
)
from tax_agent.tool_executor import apply_tool_calls, ollama_tool_calls_from_message
from tax_agent.tools_schema import TAX_AGENT_TOOLS, TOOL_SYSTEM_APPENDIX, model_supports_ollama_tools


def llm_enabled() -> bool:
    v = (os.environ.get("TAX_AGENT_LLM_ENABLED") or "1").strip().lower()
    return v not in {"0", "false", "no", "off"}


SYSTEM_PROMPT = """你是富途境外所得报税助手，仅服务中国大陆税务居民，使用富途 App「我的税表」Annual_Statement xlsx（非 CSV）。

你的任务：
1. 用简洁中文回答用户。
2. 通过工具决定下一步：compute_tax、request_upload、show_report、reply_only。
3. 从用户话术中提取 tax_year（默认 {tax_year}）。

规则：
- 未上传 dataset 时不可 compute_tax；用 request_upload 引导上传富途 Annual_Statement xlsx。
- 跨年卖出须同会话上传买入年至卖出年全部 Annual_Statement（如 2022+2023）。
- 已上传且 session 含 lastSummary 时：用户问税额/结果用 reply_only 解读摘要，勿再 request_upload。
- 若上下文含【TAX_INSIGHT】JSON：用 reply_only 解读；T0=申报口径，T1=辅助对照（未实现/敏感性），须区分口径。
- 不要编造税额；数字仅来自 lastSummary 或 TAX_INSIGHT 块。
- 不要提及 Schwab、Fidelity、IBKR、CSV 等其他券商或格式。
{tool_appendix}
"""

SYSTEM_PROMPT_JSON = """你是富途境外所得报税助手，仅服务中国大陆税务居民，使用富途 Annual_Statement xlsx。

任务：判断 action（need_upload|compute|show_report|none），提取 taxYear（默认 {tax_year}）。

规则：
- 未上传 dataset → need_upload，引导富途税表 xlsx；跨年需多年度税表。
- 已上传且有 lastSummary → 解读结果用 none，勿 need_upload。
- 勿提其他券商或 CSV。
- 勿编造税额；输出单行 JSON。

字段：reply, action, taxYear, followUpQuestions
"""


def _normalize_follow_up(raw: Any) -> list[str]:
    if isinstance(raw, list):
        return [str(q).strip() for q in raw if str(q).strip()][:3]
    if isinstance(raw, str) and raw.strip():
        return [raw.strip()]
    return []


def _filing_plan(
    message: str,
    ctx: SessionContext,
    *,
    focus_tax_year: int | None = None,
    resolved_tax_year: int | None = None,
    episodic_profile: str | None = None,
):
    return build_filing_turn_plan(
        message,
        default_tax_year=ctx.tax_year,
        has_dataset=bool(ctx.dataset_id),
        has_compute=bool(ctx.last_run_id or ctx.last_summary),
        focus_tax_year=focus_tax_year,
        resolved_tax_year=resolved_tax_year,
        episodic_profile=episodic_profile,
    )


def _prepare_tax_insight(ctx: SessionContext, plan) -> None:
    ctx.tax_insight_plan = plan.profile
    if not plan.inject_insight or not ctx.dataset_id or not ctx.data_quality:
        return
    ctx.tax_insight = build_tax_insight(
        focus=plan.focus,
        tax_year=plan.tax_year,
        data_quality=ctx.data_quality,
        events=ctx.events,
        last_summary=ctx.last_summary,
        fx_provider=ctx.fx_provider,
    )


def _insight_rules_turn(ctx: SessionContext, plan) -> ChatTurnResult | None:
    if not plan.inject_insight or not ctx.dataset_id or not ctx.data_quality:
        return None
    insight = build_tax_insight(
        focus=plan.focus,
        tax_year=plan.tax_year,
        data_quality=ctx.data_quality,
        events=ctx.events,
        last_summary=ctx.last_summary,
        fx_provider=ctx.fx_provider,
    )
    return ChatTurnResult(reply=format_insight_reply_zh(insight), action="none")


def _build_user_payload(message: str, ctx: SessionContext) -> str:
    return json.dumps(
        {
            "userMessage": message,
            "session": {
                "hasDataset": bool(ctx.dataset_id),
                "datasetId": ctx.dataset_id,
                "lastRunId": ctx.last_run_id,
                "brokerTemplateId": ctx.broker_template_id,
                "mappingHints": ctx.mapping_hints,
                "eventCount": ctx.event_count,
                "eventCounts": ctx.event_counts or {},
                "lastSummary": ctx.last_summary,
                "taxInsightPlan": ctx.tax_insight_plan,
                "hasTaxInsight": bool(ctx.tax_insight),
                "riskLevel": ctx.risk_level,
                "defaultTaxYear": ctx.tax_year,
                "residentStatus": ctx.resident_status,
                "filingScope": ctx.filing_scope,
                "domesticIncomeProvided": ctx.domestic_income_provided,
            },
        },
        ensure_ascii=False,
    )


def _parse_llm_json(raw: str) -> dict[str, Any] | None:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{[\s\S]*\}", text)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                return None
    return None


def _turn_from_json(parsed: dict[str, Any], ctx: SessionContext) -> ChatTurnResult:
    action = str(parsed.get("action") or "none")
    if action == "clarify":
        action = "none"
    reply = str(parsed.get("reply") or "").strip() or "已收到。"
    params: dict[str, Any] = {}
    if parsed.get("taxYear"):
        params["taxYear"] = int(parsed["taxYear"])
    if parsed.get("residentStatus"):
        params["residentStatus"] = str(parsed["residentStatus"])
    filing = parsed.get("filingScope") or parsed.get("filing_scope")
    if filing:
        params["filingScope"] = str(filing)
    elif ctx.filing_scope:
        params["filingScope"] = ctx.filing_scope
    if action == "compute" and not ctx.dataset_id:
        action = "need_upload"
        reply += "\n\n请先上传券商对账单后再测算。"
    follow = _normalize_follow_up(parsed.get("followUpQuestions"))
    if follow:
        reply += "\n\n" + "\n".join(f"- {q}" for q in follow)
    return ChatTurnResult(reply=reply, action=action, compute_params=params or None)


def _build_llm_messages(
    message: str,
    ctx: SessionContext,
    *,
    use_tools: bool = False,
    plan: Any = None,
    filing_state: FilingSessionState | None = None,
    numerics_block: str = "",
    recall_block: str = "",
) -> list[dict[str, str]]:
    if use_tools:
        soul = SYSTEM_PROMPT.format(
            tax_year=ctx.tax_year,
            tool_appendix=TOOL_SYSTEM_APPENDIX,
        )
    else:
        soul = SYSTEM_PROMPT_JSON.format(tax_year=ctx.tax_year)

    state = filing_state or FilingSessionState.from_session_context(ctx)
    ledger = ""
    task_text = ""
    if plan is not None:
        task_text = plan.task_text
        ledger = build_filing_ledger_slice(state, plan, numerics_block=numerics_block)

    insight_block = format_tax_insight_block(ctx.tax_insight) if ctx.tax_insight else ""

    return build_tax_chat_message_stack(
        system_soul=soul,
        task_text=task_text,
        history_messages=list((ctx.chat_history or [])[-8:]),
        filing_ledger=ledger,
        episodic_block=recall_block,
        tax_insight_block=insight_block,
        session_snapshot=build_session_snapshot_dict(ctx, user_message=message),
        raw_user_message=message,
    )


def _apply_numerics_audit(
    turn: ChatTurnResult,
    ctx: SessionContext,
    plan,
    meta: dict[str, Any],
) -> ChatTurnResult:
    state = FilingSessionState.from_session_context(ctx)
    audited_reply, audit = audit_turn_reply(turn.reply, state, plan)
    if not audit.ok and audit.unknown:
        meta["numericsAudit"] = audit.to_dict()
        turn = ChatTurnResult(
            reply=audited_reply,
            action=turn.action,
            compute_params=turn.compute_params,
        )
    return turn


def _finish_turn(
    turn: ChatTurnResult,
    meta: dict[str, Any],
    ctx: SessionContext,
    plan,
    message: str,
    *,
    turn_scope: Any | None = None,
    llm_on: bool = True,
    model_override: str | None = None,
    episodic_block: str = "",
) -> tuple[ChatTurnResult, dict[str, Any]]:
    if turn_scope is not None:
        meta["turnScope"] = {
            "taxYears": list(turn_scope.tax_years),
            "yearSource": turn_scope.year_source,
            "episodicRevived": bool(turn_scope.episodic_revived),
        }
    if turn.fact_bundle is not None:
        turn, composer_meta = finalize_turn_with_composer(
            turn,
            user_message=message,
            episodic_block=episodic_block,
            llm_on=llm_on,
            model_override=model_override,
            reply_verbosity=getattr(ctx, "reply_verbosity", None) or "normal",
        )
        meta.setdefault("runtime", {})
        meta["runtime"].update(composer_meta)
        if turn.follow_ups:
            meta["followUps"] = list(turn.follow_ups)
    return turn, meta


def orchestrate_with_llm(
    message: str,
    ctx: SessionContext,
    *,
    model_override: str | None = None,
    session_id: str | None = None,
    narrative_polish: bool | None = None,
    reply_verbosity: str | None = None,
) -> tuple[ChatTurnResult, dict[str, Any]]:
    """
    Returns (turn, meta) where meta includes model, mode, fallback reason.
    """
    if session_id and not ctx.session_id:
        ctx.session_id = session_id
    ctx.reply_verbosity = reply_verbosity or "normal"

    meta: dict[str, Any] = {"mode": "rules", "model": None, "reason": ""}
    sid = (ctx.session_id or session_id or "").strip()
    active_focus = revive_tax_session_focus(sid, message) if sid else None
    focus_year = active_focus.focus_tax_year if active_focus and active_focus.active else None

    turn_scope = resolve_turn_scope(
        message,
        ctx.tax_year,
        data_quality=ctx.data_quality,
        fx_provider=ctx.fx_provider,
        episodic=active_focus,
    )
    clarify_turn = try_clarify_turn(turn_scope)
    if clarify_turn:
        meta.update(
            {
                "mode": "clarify",
                "turnScope": {
                    "taxYears": turn_scope.tax_years,
                    "yearSource": turn_scope.year_source,
                },
            }
        )
        return _finish_turn(clarify_turn, meta, ctx, _filing_plan(message, ctx), message, turn_scope=turn_scope)

    resolved_year = scope_primary_year(turn_scope, ctx.tax_year)
    plan = _filing_plan(
        message,
        ctx,
        focus_tax_year=focus_year,
        resolved_tax_year=resolved_year,
        episodic_profile=active_focus.focus_profile if active_focus else None,
    )
    ctx.tax_year = plan.tax_year
    _prepare_tax_insight(ctx, plan)
    meta["harnessProfile"] = plan.profile
    meta["journeyPhase"] = plan.journey_phase
    if active_focus and active_focus.active:
        meta["turnFocusYear"] = active_focus.focus_tax_year
        meta["turnFocusTtl"] = active_focus.turns_remaining

    filing_state = FilingSessionState.from_session_context(ctx)
    manifest = build_numerics_manifest(filing_state, plan)
    numerics_block = format_numerics_manifest_block(
        manifest, tax_year=filing_state.effective_tax_year(plan)
    )
    epi_block = episodic_bridge_block(active_focus)
    recall_block = build_chat_recall_block(
        message,
        session_id=sid,
        chat_history=ctx.chat_history,
        focus_block=focus_tier0_block(active_focus),
        episodic_block=epi_block,
    )
    meta["intentScore"] = plan.intent_score
    meta["messageStack"] = "pha_v1"
    llm_on = llm_enabled()

    polish_narrative = (
        narrative_polish
        if narrative_polish is not None
        else should_polish_narrative(message, llm_on=llm_on)
    )
    fast = (
        try_provenance_fast_turn(message, ctx)
        or try_policy_qa_fast_turn(message, ctx)
        or try_coverage_fast_turn(message, ctx)
        or try_narrative_fast_turn(
            message,
            ctx,
            plan,
            polish=polish_narrative and llm_on,
            model_override=model_override,
        )
        or try_insight_fast_turn(message, ctx)
    )
    if fast:
        if ctx.tax_provenance:
            mode = "provenance_fast"
        elif plan.profile == "policy_qa":
            mode = "policy_qa_fast"
        elif plan.profile == "coverage_check":
            mode = "coverage_fast"
        elif plan.profile == "filing_narrative":
            mode = "narrative_fast"
            meta["narrativePolished"] = bool(getattr(ctx, "last_narrative_polished", False))
        else:
            mode = "insight_fast"
        meta.update({"mode": mode, "insightProfile": ctx.tax_insight_plan})
        return _finish_turn(
            fast,
            meta,
            ctx,
            plan,
            message,
            turn_scope=turn_scope,
            llm_on=llm_on,
            model_override=model_override,
            episodic_block=epi_block,
        )

    if not llm_enabled():
        meta["reason"] = "llm_disabled"
        insight_turn = _insight_rules_turn(ctx, plan)
        if insight_turn:
            meta["insightProfile"] = ctx.tax_insight_plan
            return _finish_turn(insight_turn, meta, ctx, plan, message, turn_scope=turn_scope)
        turn = orchestrate_user_message(
            message,
            dataset_id=ctx.dataset_id,
            last_run_id=ctx.last_run_id,
            default_tax_year=ctx.tax_year,
            broker_template_id=ctx.broker_template_id,
            mapping_hints=ctx.mapping_hints,
            filing_scope=ctx.filing_scope,
            domestic_income_provided=ctx.domestic_income_provided,
        )
        return _finish_turn(turn, meta, ctx, plan, message, turn_scope=turn_scope)

    resolution: TaxModelResolution = resolve_tax_agent_model(override=model_override)
    if not resolution.model:
        meta["reason"] = resolution.reason
        turn = orchestrate_user_message(
            message,
            dataset_id=ctx.dataset_id,
            last_run_id=ctx.last_run_id,
            default_tax_year=ctx.tax_year,
            broker_template_id=ctx.broker_template_id,
            mapping_hints=ctx.mapping_hints,
            filing_scope=ctx.filing_scope,
            domestic_income_provided=ctx.domestic_income_provided,
        )
        turn.reply += f"\n\n（本地模型不可用：{resolution.reason}，已使用规则引擎。）"
        return _finish_turn(turn, meta, ctx, plan, message, turn_scope=turn_scope)

    try:
        unloaded = prepare_ollama_for_tax(keep_model=resolution.model)
        OllamaProvider = import_ollama_provider()
        provider = OllamaProvider(
            base_url=ollama_base_url(),
            model=resolution.model,
            timeout_seconds=float(os.environ.get("TAX_AGENT_LLM_TIMEOUT_SECONDS", "120")),
        )
        use_tools = model_supports_ollama_tools(resolution.model)
        messages = _build_llm_messages(
            message,
            ctx,
            use_tools=use_tools,
            plan=plan,
            filing_state=filing_state,
            numerics_block=numerics_block,
            recall_block=recall_block,
        )

        if use_tools:
            try:
                payload = chat_with_tools_messages(
                    provider, messages=messages, tools=TAX_AGENT_TOOLS
                )
                ollama_msg = payload.get("message") or {}
                tool_calls = ollama_tool_calls_from_message(ollama_msg)
                if tool_calls:
                    turn, executed = apply_tool_calls(tool_calls, ctx)
                    if turn:
                        turn = _apply_numerics_audit(turn, ctx, plan, meta)
                        meta.update(
                            {
                                "mode": "llm_tools",
                                "model": resolution.model,
                                "reason": resolution.reason,
                                "unloadedModels": unloaded,
                                "toolsExecuted": executed,
                            }
                        )
                        return _finish_turn(turn, meta, ctx, plan, message, turn_scope=turn_scope)
                content = (ollama_msg.get("content") or "").strip()
                if content:
                    parsed = _parse_llm_json(content)
                    if parsed:
                        turn = _apply_numerics_audit(
                            _turn_from_json(parsed, ctx), ctx, plan, meta
                        )
                        meta.update(
                            {
                                "mode": "llm",
                                "model": resolution.model,
                                "reason": "tools_empty_json_fallback",
                                "unloadedModels": unloaded,
                            }
                        )
                        return _finish_turn(turn, meta, ctx, plan, message, turn_scope=turn_scope)
            except Exception as tool_exc:
                meta["toolError"] = str(tool_exc)[:200]

        raw = chat_completion_messages(
            provider,
            messages=_build_llm_messages(
                message,
                ctx,
                use_tools=False,
                plan=plan,
                filing_state=filing_state,
                numerics_block=numerics_block,
                recall_block=recall_block,
            ),
            json_mode=True,
        )
        parsed = _parse_llm_json(raw)
        if not parsed:
            meta["reason"] = "invalid_json"
            meta["raw"] = raw[:500]
            insight_turn = _insight_rules_turn(ctx, plan)
            if insight_turn:
                meta["insightProfile"] = ctx.tax_insight_plan
                return _finish_turn(insight_turn, meta, ctx, plan, message, turn_scope=turn_scope)
            turn = orchestrate_user_message(
                message,
                dataset_id=ctx.dataset_id,
                last_run_id=ctx.last_run_id,
                default_tax_year=ctx.tax_year,
                broker_template_id=ctx.broker_template_id,
                mapping_hints=ctx.mapping_hints,
                filing_scope=ctx.filing_scope,
                domestic_income_provided=ctx.domestic_income_provided,
            )
            return _finish_turn(turn, meta, ctx, plan, message, turn_scope=turn_scope)

        turn = _apply_numerics_audit(_turn_from_json(parsed, ctx), ctx, plan, meta)
        meta.update(
            {
                "mode": "llm",
                "model": resolution.model,
                "reason": resolution.reason,
                "unloadedModels": unloaded,
            }
        )
        return _finish_turn(turn, meta, ctx, plan, message, turn_scope=turn_scope)

    except Exception as exc:
        meta["reason"] = f"llm_error:{exc}"
        insight_turn = _insight_rules_turn(ctx, plan)
        if insight_turn:
            meta["insightProfile"] = ctx.tax_insight_plan
            insight_turn.reply += f"\n\n（模型调用失败，已使用规则洞察：{exc}）"
            return _finish_turn(insight_turn, meta, ctx, plan, message, turn_scope=turn_scope)
        turn = orchestrate_user_message(
            message,
            dataset_id=ctx.dataset_id,
            last_run_id=ctx.last_run_id,
            default_tax_year=ctx.tax_year,
            broker_template_id=ctx.broker_template_id,
            mapping_hints=ctx.mapping_hints,
            filing_scope=ctx.filing_scope,
            domestic_income_provided=ctx.domestic_income_provided,
        )
        turn.reply += f"\n\n（模型调用失败，已回退规则引擎：{exc}）"
        return _finish_turn(turn, meta, ctx, plan, message, turn_scope=turn_scope)


def get_llm_status(*, model_override: str | None = None) -> dict[str, Any]:
    from tax_agent.llm_model_resolver import _low_ram_mode, list_tax_model_choices

    resolution = resolve_tax_agent_model(override=model_override)
    model = resolution.model or ""
    return {
        "enabled": llm_enabled(),
        "lowRamMode": _low_ram_mode(),
        "baseUrl": ollama_base_url(),
        "resolvedModel": resolution.model,
        "resolutionReason": resolution.reason,
        "installedModels": resolution.installed,
        "modelChoices": list_tax_model_choices(resolution.installed),
        "recommendedModel": resolution.recommended,
        "recommendationZh": recommended_model_doc_zh(),
        "toolsSupported": model_supports_ollama_tools(model) if model else False,
        "tools": [t["function"]["name"] for t in TAX_AGENT_TOOLS],
        "fastPaths": ["provenance_fast", "coverage_fast", "narrative_fast", "insight_fast"],
    }
