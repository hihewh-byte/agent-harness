"""Shared /tax/chat turn pipeline (sync + SSE — Tax Chat Experience v2 · C3)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from tax_agent.answer_composer import finalize_turn_with_composer
from tax_agent.chat_orchestrator import ChatTurnResult, orchestrate_user_message
from tax_agent.chat_turn_fsm import TaxTurnPhase, TaxTurnPhaseRecorder
from tax_agent.coverage_check import try_coverage_fast_turn
from tax_agent.filing_narrative import should_polish_narrative, try_narrative_fast_turn
from tax_agent.filing_session_state import FilingSessionState
from tax_agent.harness_plan import build_filing_turn_plan
from tax_agent.llm_orchestrator import SessionContext, llm_enabled, orchestrate_with_llm
from tax_agent.filing_journey_coach import (
    enrich_outcome_with_nba,
    resolve_turn_nba,
    try_guided_filing_fast_turn,
)
from tax_agent.policy_kb import try_policy_qa_fast_turn
from tax_agent.session_turn_focus import episodic_bridge_block, record_turn_focus, revive_tax_session_focus
from tax_agent.tax_insight import try_insight_fast_turn
from tax_agent.tax_provenance import try_provenance_fast_turn
from tax_agent.tax_turn_resolver import resolve_turn_scope, scope_primary_year, try_clarify_turn
from tax_agent.tax_user_profile import (
    normalize_reply_verbosity,
    resolve_profile_preferences,
    sync_profile_from_session,
    try_profile_command_turn,
)


@dataclass
class ChatTurnRequest:
    session_id: str
    message: str
    dataset_id: str | None = None
    last_run_id: str | None = None
    tax_year: int = 2022
    resident_status: str = "cn_tax_resident"
    fx_policy: str = "cn_supplemental"
    filing_date: str | None = None
    filing_scope: str = "foreign_only"
    llm_model: str | None = None
    reply_verbosity: str | None = None
    narrative_polish: bool | None = None
    broker_template_id: str = "broker_futu_v1"
    user_key: str | None = None


@dataclass
class ChatTurnOutcome:
    reply: str
    action: str
    session_id: str
    plan: Any
    turn_scope: Any
    ctx: SessionContext
    llm_meta: dict[str, Any] = field(default_factory=dict)
    turn: ChatTurnResult | None = None
    clarify_choices: list[int] | None = None
    follow_ups: list[str] | None = None
    nba: str | None = None
    harness: dict[str, Any] = field(default_factory=dict)
    insight: dict[str, Any] | None = None
    provenance: dict[str, Any] | None = None
    filing_table: dict[str, Any] | None = None
    compute_params: dict[str, Any] | None = None


def chat_turn_request_from_body(body: Any) -> ChatTurnRequest:
    return ChatTurnRequest(
        session_id=body.sessionId,
        user_key=getattr(body, "userKey", None) or None,
        message=body.message,
        dataset_id=body.datasetId,
        last_run_id=body.lastRunId,
        tax_year=body.taxYear,
        resident_status=body.residentStatus,
        fx_policy=body.fxPolicy,
        filing_date=body.filingDate,
        filing_scope=body.filingScope,
        llm_model=body.llmModel,
        reply_verbosity=getattr(body, "replyVerbosity", None),
        narrative_polish=body.narrativePolish,
    )


def _llm_on(req: ChatTurnRequest) -> bool:
    return llm_enabled() and req.llm_model != "__off__"


def _narr_override(req: ChatTurnRequest) -> str | None:
    if req.llm_model and req.llm_model not in ("auto", "__off__"):
        return req.llm_model
    return None


def _fast_lane_mode(plan_profile: str) -> str:
    return {
        "policy_explain": "provenance_fast",
        "policy_qa": "policy_qa_fast",
        "guided_filing": "guided_filing_fast",
        "coverage_check": "coverage_fast",
        "filing_narrative": "narrative_fast",
    }.get(plan_profile, "insight_fast")


def resolve_chat_turn(
    req: ChatTurnRequest,
    ctx: SessionContext,
    *,
    apply_composer: bool = True,
) -> ChatTurnOutcome:
    """Core chat turn — shared by POST /tax/chat and GET /tax/chat/stream."""
    phase_rec = TaxTurnPhaseRecorder()
    phase_rec.enter(TaxTurnPhase.INIT)

    sid = req.session_id
    message = req.message
    if req.user_key:
        ctx.user_key = req.user_key

    phase_rec.enter(TaxTurnPhase.SESSION)
    eff_model, eff_verbosity = resolve_profile_preferences(
        req.user_key,
        llm_model=req.llm_model,
        reply_verbosity=req.reply_verbosity,
    )
    req.llm_model = eff_model
    req.reply_verbosity = eff_verbosity

    profile_turn = try_profile_command_turn(message, ctx)
    if profile_turn:
        phase_rec.enter(TaxTurnPhase.DONE)
        return ChatTurnOutcome(
            reply=profile_turn.reply,
            action=profile_turn.action,
            session_id=sid,
            plan=None,
            turn_scope=None,
            ctx=ctx,
            llm_meta={"mode": "profile_memory", "model": None, "modelUsed": False},
            turn=profile_turn,
            harness={
                "profile": "profile_memory",
                "turnPhases": phase_rec.as_names(),
            },
        )

    active_focus = revive_tax_session_focus(sid, message) if sid else None
    focus_year = (
        active_focus.focus_tax_year if active_focus and active_focus.active else None
    )

    phase_rec.enter(TaxTurnPhase.SCOPE)
    turn_scope = resolve_turn_scope(
        message,
        req.tax_year,
        data_quality=ctx.data_quality,
        fx_provider=ctx.fx_provider,
        episodic=active_focus,
    )
    clarify_turn = try_clarify_turn(turn_scope)
    if clarify_turn:
        phase_rec.enter(TaxTurnPhase.CLARIFY)
        record_turn_focus(
            sid,
            tax_year=scope_primary_year(turn_scope, req.tax_year),
            tax_years=turn_scope.tax_years,
            profile="clarify",
            user_message=message,
            assistant_reply=clarify_turn.reply,
            mode="clarify",
        )
        phase_rec.enter(TaxTurnPhase.DONE)
        return ChatTurnOutcome(
            reply=clarify_turn.reply,
            action=clarify_turn.action,
            session_id=sid,
            plan=None,
            turn_scope=turn_scope,
            ctx=ctx,
            llm_meta={
                "mode": "clarify",
                "turnScope": {
                    "taxYears": turn_scope.tax_years,
                    "yearSource": turn_scope.year_source,
                },
            },
            turn=clarify_turn,
            clarify_choices=list(turn_scope.tax_years),
            harness={
                "profile": "clarify",
                "turnPhases": phase_rec.as_names(),
            },
        )

    phase_rec.enter(TaxTurnPhase.PLAN)
    resolved_year = scope_primary_year(turn_scope, req.tax_year)
    plan = build_filing_turn_plan(
        message,
        default_tax_year=req.tax_year,
        has_dataset=bool(req.dataset_id),
        has_compute=bool(ctx.last_run_id or ctx.last_summary),
        focus_tax_year=focus_year,
        resolved_tax_year=resolved_year,
        episodic_profile=active_focus.focus_profile if active_focus else None,
    )
    ctx.tax_year = plan.tax_year
    if plan.inject_insight and req.dataset_id:
        from tax_agent.tax_insight import build_tax_insight as _build_insight

        ctx.tax_insight_plan = plan.profile
        ctx.tax_insight = _build_insight(
            focus=plan.focus,
            tax_year=plan.tax_year,
            data_quality=ctx.data_quality,
            events=ctx.events,
            last_summary=ctx.last_summary,
            fx_provider=ctx.fx_provider,
        )

    llm_on = _llm_on(req)
    narrative_polish = req.narrative_polish
    if narrative_polish is None:
        narrative_polish = should_polish_narrative(message, llm_on=llm_on)
    narr_override = _narr_override(req)
    llm_meta: dict[str, Any] = {}
    epi_block = episodic_bridge_block(active_focus)
    filing_state = FilingSessionState.from_session_context(ctx)
    turn_nba = resolve_turn_nba(filing_state, plan.profile)

    phase_rec.assert_plan_before_compose()
    fast = (
        try_provenance_fast_turn(message, ctx)
        or try_policy_qa_fast_turn(message, ctx)
        or try_guided_filing_fast_turn(message, ctx)
        or try_coverage_fast_turn(message, ctx)
        or try_narrative_fast_turn(
            message,
            ctx,
            plan,
            polish=bool(narrative_polish and llm_on),
            model_override=narr_override,
        )
        or try_insight_fast_turn(message, ctx)
    )

    if fast:
        phase_rec.enter(TaxTurnPhase.FAST_LANE)
        mode = _fast_lane_mode(plan.profile)
        turn = fast
        llm_meta = {
            "mode": mode,
            "model": None,
            "modelUsed": False,
            "insightProfile": plan.profile,
            "harnessProfile": plan.profile,
            "journeyPhase": plan.journey_phase,
            "turnScope": {
                "taxYears": turn_scope.tax_years,
                "yearSource": turn_scope.year_source,
                "episodicRevived": turn_scope.episodic_revived,
            },
        }
        if plan.profile == "filing_narrative":
            llm_meta["narrativePolished"] = bool(getattr(ctx, "last_narrative_polished", False))
        if apply_composer:
            turn, composer_wrap = finalize_turn_with_composer(
                turn,
                user_message=message,
                episodic_block=epi_block,
                llm_on=llm_on,
                model_override=narr_override,
                nba=turn_nba,
                reply_verbosity=req.reply_verbosity,
            )
            if composer_wrap.get("composer"):
                llm_meta.setdefault("runtime", {})
                llm_meta["runtime"].update(composer_wrap)
            if composer_wrap.get("nba"):
                turn_nba = composer_wrap["nba"]
            if turn.follow_ups:
                llm_meta["followUps"] = list(turn.follow_ups)
    elif req.llm_model == "__off__" or not llm_enabled():
        phase_rec.enter(TaxTurnPhase.COMPOSE)
        turn = orchestrate_user_message(
            message,
            dataset_id=req.dataset_id,
            last_run_id=req.last_run_id,
            default_tax_year=req.tax_year,
            broker_template_id=req.broker_template_id,
        )
        llm_meta = {"mode": "rules", "model": None, "modelUsed": False}
    else:
        phase_rec.enter(TaxTurnPhase.COMPOSE)
        turn, llm_meta = orchestrate_with_llm(
            message,
            ctx,
            model_override=narr_override,
            session_id=sid,
            narrative_polish=narrative_polish,
            reply_verbosity=req.reply_verbosity,
        )
        llm_meta.setdefault("modelUsed", True)

    phase_rec.enter(TaxTurnPhase.POST_AUDIT)
    llm_meta.setdefault("harnessProfile", plan.profile)
    llm_meta.setdefault("journeyPhase", plan.journey_phase)
    llm_meta.setdefault(
        "turnScope",
        {
            "taxYears": turn_scope.tax_years,
            "yearSource": turn_scope.year_source,
            "episodicRevived": turn_scope.episodic_revived,
        },
    )
    llm_meta["turnPhases"] = phase_rec.as_names()

    outcome = ChatTurnOutcome(
        reply=turn.reply,
        action=turn.action,
        session_id=sid,
        plan=plan,
        turn_scope=turn_scope,
        ctx=ctx,
        llm_meta=llm_meta,
        turn=turn,
        follow_ups=list(turn.follow_ups) if turn.follow_ups else None,
        harness={
            "profile": plan.profile,
            "journeyPhase": plan.journey_phase,
            "uploadedYears": filing_state.uploaded_years,
            "focusTaxYear": plan.tax_year,
            "turnPhases": phase_rec.as_names(),
        },
    )
    if turn.action == "show_filing_table" and turn.compute_params:
        outcome.filing_table = turn.compute_params.get("filingTable")
    if ctx.tax_insight and not ctx.tax_insight.get("error"):
        outcome.insight = ctx.tax_insight
    if ctx.tax_provenance:
        outcome.provenance = ctx.tax_provenance
    if turn.action == "compute" and req.dataset_id:
        outcome.compute_params = turn.compute_params or {}

    reply, nba = enrich_outcome_with_nba(
        reply=outcome.reply,
        state=filing_state,
        profile=plan.profile,
    )
    outcome.reply = reply
    outcome.nba = nba or turn_nba
    if outcome.nba:
        outcome.llm_meta["nba"] = outcome.nba

    if req.user_key and outcome.plan is not None:
        sync_profile_from_session(
            req.user_key,
            state=filing_state,
            session_id=sid,
            resident_status=req.resident_status,
            llm_preference=req.llm_model or "auto",
            reply_verbosity=req.reply_verbosity,
            last_mode=str(outcome.llm_meta.get("mode") or ""),
        )
        outcome.llm_meta["userProfile"] = {
            "llmPreference": req.llm_model or "auto",
            "replyVerbosity": normalize_reply_verbosity(req.reply_verbosity),
        }

    phase_rec.enter(TaxTurnPhase.DONE)
    outcome.harness["turnPhases"] = phase_rec.as_names()
    outcome.llm_meta["turnPhases"] = phase_rec.as_names()
    # Soft: mirror domain phases onto harness_core spine (no behavior change)
    try:
        from tax_agent.harness_core_adapter import harness_core_available, record_domain_phases

        if harness_core_available():
            core_rec = record_domain_phases(phase_rec.as_names())
            core_rec.assert_plan_before_compose()
            outcome.harness["corePhases"] = core_rec.as_names()
            outcome.llm_meta["corePhases"] = core_rec.as_names()
    except Exception:
        pass
    return outcome
