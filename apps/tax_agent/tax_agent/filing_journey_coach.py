"""Proactive coach (NBA) + guided_filing wizard (Tax Chat Experience v2 · C4)."""

from __future__ import annotations

from typing import Any

from tax_agent.chat_orchestrator import ChatTurnResult
from tax_agent.coverage_check import build_coverage_report
from tax_agent.fact_bundle import FactBundle
from tax_agent.filing_session_state import FilingSessionState
from tax_agent.harness_plan import JourneyPhase, build_filing_turn_plan
from tax_agent.tax_guided_session import (
    get_tax_guided_session,
    max_guided_step,
    save_tax_guided_session,
)

_GUIDED_ORDER: tuple[JourneyPhase, ...] = (
    "collecting",
    "ready",
    "computed",
    "reviewing",
    "export",
)

_GUIDED_RESUME_TOKENS = ("继续申报", "下一步", "向导", "申报流程")


def infer_guided_step_from_state(state: FilingSessionState) -> JourneyPhase:
    if not state.dataset_id:
        return "collecting"
    coverage = build_coverage_report(
        data_quality=state.data_quality,
        events=getattr(state, "events", None),
        focus_tax_year=state.focus_tax_year,
    )
    if coverage.get("missingYears"):
        return "collecting"
    if not state.has_compute:
        return "ready"
    snap = state.last_filing_snapshot or {}
    has_table = bool(snap.get("rows") or state.data_quality and state.data_quality.get("filingTable"))
    if not has_table:
        return "computed"
    if state.journey_phase in ("export",):
        return "export"
    return "reviewing"


def effective_guided_step(session_id: str, state: FilingSessionState) -> JourneyPhase:
    inferred = infer_guided_step_from_state(state)
    stored = get_tax_guided_session(session_id)
    if stored and stored.wizard_active:
        return max_guided_step(stored.guided_step, inferred)
    return inferred


def build_next_best_action(
    state: FilingSessionState,
    *,
    coverage: dict[str, Any] | None = None,
) -> str | None:
    """Deterministic NBA from journey + coverage + risk (template pool)."""
    if not state.dataset_id:
        return None

    cov = coverage or build_coverage_report(
        data_quality=state.data_quality,
        events=getattr(state, "events", None),
        focus_tax_year=state.focus_tax_year,
    )
    missing = cov.get("missingYears") or []
    year = state.focus_tax_year or (missing[0] if missing else 0)

    if missing:
        yrs = "、".join(str(y) for y in missing[:5])
        return (
            f"检测到材料缺口：建议补传 {yrs} 年度富途税表，"
            "否则 FIFO 成本可能不完整、税额偏高。"
        )

    if cov.get("complete") and not state.has_compute:
        y = year or (cov.get("uploadedYears") or [2024])[0]
        return f"材料覆盖完整，可以直接说「测算 {y} 年税额」。"

    amb = state.short_symbols or cov.get("ambiguousSymbols") or []
    if state.has_compute and amb:
        n = len(amb)
        return f"有 {n} 笔成本不确定（ambiguous），建议先说「风险清单」再填表。"

    if state.has_compute and not amb:
        return "下一步：说「生成申报数据表」，对照个税 App 四列填写。"

    if state.journey_phase in ("reviewing", "export", "computed") and state.has_compute:
        return "需要我写一份申报情况说明吗？可以说「帮我写申报说明」。"

    return None


def format_nba_footer(nba: str) -> str:
    return f"\n\n---\n💡 **下一步建议**：{nba.strip()}"


def append_nba_to_reply(reply: str, nba: str | None) -> str:
    if not nba or nba.strip() in (reply or ""):
        return reply or ""
    return (reply or "").rstrip() + format_nba_footer(nba)


def _guided_step_message(
    step: JourneyPhase,
    *,
    state: FilingSessionState,
    tax_year: int,
    coverage: dict[str, Any],
) -> str:
    idx = _GUIDED_ORDER.index(step) + 1 if step in _GUIDED_ORDER else 1
    prefix = f"**申报向导 · 第 {idx}/5 步（{step}）**\n\n"
    missing = coverage.get("missingYears") or []
    y = tax_year or state.focus_tax_year or 2024

    if step == "collecting":
        if not state.dataset_id:
            return (
                prefix
                + "请先上传富途 App「我的税表」Annual_Statement xlsx。\n"
                "跨年卖出需上传买入年至卖出年全部税表。"
            )
        if missing:
            yrs = "、".join(str(x) for x in missing)
            return (
                prefix
                + f"已检测到缺口年度：**{yrs}**。\n"
                f"请补传上述年度税表后再测算 {y} 年，否则成本可能偏高。"
            )
        return prefix + "材料检查中，请稍候或询问「材料覆盖完整吗」。"
    if step == "ready":
        return (
            prefix
            + f"材料已齐。请直接说：**测算 {y} 年税额**（或点击侧栏测算）。\n"
            "测算完成后我会带你进入填表步骤。"
        )
    if step == "computed":
        return (
            prefix
            + f"{y} 年度已测算。请说：**生成申报数据表**，获取个税 App 四列对照。\n"
            "也可问「风险清单」确认 ambiguous 项。"
        )
    if step == "reviewing":
        return (
            prefix
            + "对照侧栏「申报数据表」四列填写个税 App：总收入、资产原值、合理费用、应纳税所得额。\n"
            "需要文字说明可说「帮我写申报说明」。"
        )
    return (
        prefix
        + "申报数据已就绪。可导出报告，或让我润色申报情况说明。\n"
        "如需重算其他年度，直接说纳税年度即可。"
    )


def build_guided_fact_bundle(
    *,
    step: JourneyPhase,
    message: str,
    fallback_markdown: str,
    tax_year: int,
    has_dataset: bool,
) -> FactBundle:
    return FactBundle(
        profile="guided_filing",
        facts={"guidedStep": step, "userMessage": message},
        numerics={str(tax_year)} if tax_year else set(),
        citations=[],
        fallback_markdown=fallback_markdown,
        tier="T0",
        journey_phase=step,
        tax_year=tax_year,
        has_dataset=has_dataset,
    )


def try_guided_filing_fast_turn(message: str, ctx: Any) -> ChatTurnResult | None:
    from tax_agent.session_turn_focus import revive_tax_session_focus

    sid = getattr(ctx, "session_id", None) or ""
    focus = revive_tax_session_focus(sid, message) if sid else None
    episodic = focus.focus_profile if focus else None

    plan = build_filing_turn_plan(
        message,
        default_tax_year=ctx.tax_year,
        has_dataset=bool(getattr(ctx, "dataset_id", None)),
        has_compute=bool(getattr(ctx, "last_run_id", None) or getattr(ctx, "last_summary", None)),
        episodic_profile=episodic,
    )

    resume = any(t in (message or "") for t in _GUIDED_RESUME_TOKENS)
    stored = get_tax_guided_session(sid) if sid else None
    if plan.profile != "guided_filing" and not (stored and stored.wizard_active and resume):
        return None

    state = FilingSessionState.from_session_context(ctx)
    step = effective_guided_step(sid, state)
    coverage = build_coverage_report(
        data_quality=state.data_quality,
        events=getattr(state, "events", None),
        focus_tax_year=plan.tax_year,
    )
    reply = _guided_step_message(step, state=state, tax_year=plan.tax_year, coverage=coverage)
    if sid:
        save_tax_guided_session(
            sid,
            guided_step=step,
            wizard_active=True,
            tax_year=plan.tax_year,
        )

    bundle = build_guided_fact_bundle(
        step=step,
        message=message,
        fallback_markdown=reply,
        tax_year=plan.tax_year,
        has_dataset=bool(getattr(ctx, "dataset_id", None)),
    )
    follow = [
        f"测算 {plan.tax_year} 年税额" if step in ("ready", "collecting") else "生成申报数据表",
        "材料覆盖完整吗",
        "风险清单",
    ]
    return ChatTurnResult(
        reply=reply,
        action="none",
        fact_bundle=bundle,
        follow_ups=follow[:3],
    )


def resolve_turn_nba(
    state: FilingSessionState,
    profile: str | None,
    skip_profiles: frozenset[str] | None = None,
) -> str | None:
    """Compute NBA hint for L4 rendering (no reply mutation)."""
    skip = skip_profiles or frozenset({"guided_filing", "clarify", "casual"})
    if profile in skip:
        return None
    return build_next_best_action(state)


def enrich_outcome_with_nba(
    *,
    reply: str,
    state: FilingSessionState,
    profile: str | None,
    skip_profiles: frozenset[str] | None = None,
) -> tuple[str, str | None]:
    """Attach NBA metadata without appending to reply body."""
    nba = resolve_turn_nba(state, profile, skip_profiles=skip_profiles)
    return reply, nba
