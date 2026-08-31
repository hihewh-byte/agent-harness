"""SSE event stream for /tax/chat/stream (Tax Chat Experience v2 · C3)."""

from __future__ import annotations

import json
from typing import Any, Callable, Iterator

from tax_agent.answer_composer import (
    fact_bundle_fact_card,
    normalize_fallback_reason,
    stream_compose_grounded_reply,
)
from tax_agent.llm_orchestrator import llm_enabled
from tax_agent.chat_turn_service import ChatTurnOutcome, ChatTurnRequest, resolve_chat_turn
from tax_agent.llm_orchestrator import SessionContext
from tax_agent.session_turn_focus import record_turn_focus


def sse_format(event: str, data: dict[str, Any] | list[Any] | str) -> str:
    payload = data if isinstance(data, str) else json.dumps(data, ensure_ascii=False)
    return f"event: {event}\ndata: {payload}\n\n"


def _meta_payload(outcome: ChatTurnOutcome) -> dict[str, Any]:
    return {
        "sessionId": outcome.session_id,
        "action": outcome.action,
        "llm": outcome.llm_meta,
        "harness": outcome.harness,
        "clarifyChoices": outcome.clarify_choices,
    }


def _done_payload(
    outcome: ChatTurnOutcome,
    *,
    reply: str,
    follow_ups: list[str] | None,
    harness_report: dict[str, Any] | None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "reply": reply,
        "action": outcome.action,
        "sessionId": outcome.session_id,
        "llm": outcome.llm_meta,
        "harness": outcome.harness,
    }
    if follow_ups:
        payload["followUps"] = follow_ups
    if outcome.clarify_choices:
        payload["clarifyChoices"] = outcome.clarify_choices
    if outcome.filing_table:
        payload["filingTable"] = outcome.filing_table
    if outcome.insight:
        payload["insight"] = outcome.insight
    if outcome.provenance:
        payload["provenance"] = outcome.provenance
    if harness_report:
        payload["harnessReport"] = harness_report
    return payload


def iter_chat_sse_events(
    req: ChatTurnRequest,
    ctx: SessionContext,
    *,
    build_harness_report: Callable[..., dict[str, Any] | None] | None = None,
    turn_focus_payload: Callable[[str], dict[str, Any]] | None = None,
    stream_fn: Callable[..., Iterator[str]] | None = None,
) -> Iterator[str]:
    """meta → fact_card? → delta* → follow_ups → done."""
    # Fast path with deferred composer
    outcome_pre = resolve_chat_turn(req, ctx, apply_composer=False)
    turn = outcome_pre.turn
    bundle = turn.fact_bundle if turn else None

    yield sse_format("meta", _meta_payload(outcome_pre))

    if outcome_pre.clarify_choices is not None and outcome_pre.plan is None:
        yield sse_format(
            "done",
            _done_payload(outcome_pre, reply=outcome_pre.reply, follow_ups=None, harness_report=None),
        )
        return

    reply = outcome_pre.reply
    follow_ups = outcome_pre.follow_ups
    composed_meta: dict[str, Any] = {}

    if bundle is not None:
        yield sse_format("fact_card", fact_bundle_fact_card(bundle))
        llm_on = llm_enabled() and req.llm_model != "__off__"
        narr_override = req.llm_model if req.llm_model not in (None, "auto", "__off__") else None
        from tax_agent.session_turn_focus import episodic_bridge_block, revive_tax_session_focus

        focus = revive_tax_session_focus(req.session_id, req.message) if req.session_id else None
        epi = episodic_bridge_block(focus)

        for kind, payload in stream_compose_grounded_reply(
            bundle,
            user_message=req.message,
            episodic_block=epi,
            llm_on=llm_on,
            model_override=narr_override,
            stream_fn=stream_fn,
            reply_verbosity=req.reply_verbosity or "normal",
        ):
            if kind == "delta":
                yield sse_format("delta", {"text": payload})
            elif kind == "final":
                composed = payload
                reply = composed.reply
                follow_ups = composed.follow_ups
                composed_meta = {
                    "composer": {
                        "narrated": composed.narrated,
                        "fallbackReason": normalize_fallback_reason(
                            composed.fallback_reason, narrated=composed.narrated
                        ),
                        **composed.composer_meta,
                    }
                }
    if follow_ups:
        outcome_pre.llm_meta["followUps"] = list(follow_ups)
        yield sse_format("follow_ups", {"items": list(follow_ups)})

    if composed_meta:
        outcome_pre.llm_meta.setdefault("runtime", {})
        outcome_pre.llm_meta["runtime"].update(composed_meta)

    outcome_pre.reply = reply
    outcome_pre.follow_ups = follow_ups

    harness_report = None
    if build_harness_report and outcome_pre.plan is not None:
        harness_report = build_harness_report(
            session_id=req.session_id,
            user_message=req.message,
            plan=outcome_pre.plan,
            meta=outcome_pre.llm_meta,
            mode=str(outcome_pre.llm_meta.get("mode") or "rules"),
            turn_focus=turn_focus_payload(req.session_id) if turn_focus_payload else {},
            action=outcome_pre.action,
        )

    if outcome_pre.plan is not None:
        scope_years = (outcome_pre.llm_meta.get("turnScope") or {}).get("taxYears") or (
            outcome_pre.turn_scope.tax_years if outcome_pre.turn_scope else []
        )
        record_turn_focus(
            req.session_id,
            tax_year=outcome_pre.plan.tax_year,
            tax_years=list(scope_years) if scope_years else [outcome_pre.plan.tax_year],
            profile=outcome_pre.plan.profile,
            user_message=req.message,
            assistant_reply=reply,
            mode=str(outcome_pre.llm_meta.get("mode") or "rules"),
        )
    if turn_focus_payload:
        outcome_pre.harness["turnFocus"] = turn_focus_payload(req.session_id)

    yield sse_format(
        "done",
        _done_payload(
            outcome_pre,
            reply=reply,
            follow_ups=follow_ups,
            harness_report=harness_report,
        ),
    )
