"""Fact card JSON, mobile HTML view, prefs, and user-triggered interpretation."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Header, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel, Field

from pha.fact_card import load_fact_card
from pha.fact_card_html import render_fact_card_html
from pha.fact_card_interpret import load_interpretation_for_user, start_interpretation
from pha.fact_card_locale import format_card_datetime, resolve_fact_card_locale
from pha.fact_card_prefs import (
    ASSESSMENT_PROMPT_MAX,
    load_fact_card_locale,
    load_fact_card_timezone,
    prefs_payload,
    save_assessment_prompt,
    save_enabled_metric_ids,
    save_fact_card_locale,
)
from pha.healthkit_ingest import require_ingest_token

router = APIRouter(tags=["proactive"])


class FactCardPrefsBody(BaseModel):
    enabled_metric_ids: list[str] = Field(default_factory=list)
    assessment_prompt: Optional[str] = None
    locale: Optional[str] = None


def _decorate_interpretation(payload: Optional[dict], user_id: str) -> Optional[dict]:
    if not payload:
        return payload
    loc = load_fact_card_locale(user_id)
    tz = load_fact_card_timezone(user_id)
    at = payload.get("generated_at")
    extra = {}
    if at:
        extra["generated_at_display"] = format_card_datetime(
            at, locale=loc, timezone_name=tz
        )
    notes = int(payload.get("background_notes_used") or 0)
    extra["background_used"] = bool(payload.get("background_used")) or notes > 0
    extra["background_notes_used"] = notes
    return {**payload, **extra}


def _auth(
    header_token: Optional[str],
    query_or_body_token: Optional[str],
) -> None:
    require_ingest_token(header_token, query_or_body_token)


@router.get("/proactive/fact-card")
def get_fact_card(
    user_id: str = Query("default"),
    token: Optional[str] = Query(default=None),
    x_pha_ingest_token: Optional[str] = Header(default=None),
) -> dict:
    _auth(x_pha_ingest_token, token)
    uid = (user_id or "default").strip() or "default"
    try:
        card = load_fact_card(uid)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail={"error": "fact_card_failed", "reason": type(exc).__name__},
        ) from exc
    try:
        from pha.chb_compiler import schedule_chb_autocompile

        schedule_chb_autocompile(uid)
    except Exception:
        pass
    return card


@router.get("/proactive/fact-card/view", response_class=HTMLResponse)
def get_fact_card_view(
    request: Request,
    user_id: str = Query("default"),
    token: Optional[str] = Query(default=None),
    x_pha_ingest_token: Optional[str] = Header(default=None),
) -> HTMLResponse:
    _auth(x_pha_ingest_token, token)
    uid = (user_id or "default").strip() or "default"
    try:
        card = load_fact_card(uid)
        prefs = prefs_payload(uid)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail={"error": "fact_card_failed", "reason": type(exc).__name__},
        ) from exc
    if not str(prefs.get("locale") or "").strip():
        prefs = {
            **prefs,
            "locale": resolve_fact_card_locale(
                accept_language=request.headers.get("accept-language"),
            ),
        }
    html = render_fact_card_html(
        card,
        prefs=prefs,
        token=token,
        accept_language=request.headers.get("accept-language"),
    )
    return HTMLResponse(content=html, media_type="text/html; charset=utf-8")


@router.get("/proactive/fact-card/prefs")
def get_fact_card_prefs(
    user_id: str = Query("default"),
    token: Optional[str] = Query(default=None),
    x_pha_ingest_token: Optional[str] = Header(default=None),
) -> dict:
    _auth(x_pha_ingest_token, token)
    uid = (user_id or "default").strip() or "default"
    return prefs_payload(uid)


@router.put("/proactive/fact-card/prefs")
def put_fact_card_prefs(
    body: FactCardPrefsBody,
    user_id: str = Query("default"),
    token: Optional[str] = Query(default=None),
    x_pha_ingest_token: Optional[str] = Header(default=None),
) -> dict:
    _auth(x_pha_ingest_token, token)
    uid = (user_id or "default").strip() or "default"
    save_enabled_metric_ids(uid, body.enabled_metric_ids)
    if body.locale is not None:
        save_fact_card_locale(uid, body.locale)
    if body.assessment_prompt is not None:
        try:
            save_assessment_prompt(uid, body.assessment_prompt)
        except ValueError as exc:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "assessment_prompt_too_long",
                    "max": ASSESSMENT_PROMPT_MAX,
                },
            ) from exc
    return prefs_payload(uid)


@router.post("/proactive/fact-card/prefs")
async def post_fact_card_prefs(
    request: Request,
    user_id: str = Query("default"),
    token: Optional[str] = Query(default=None),
    x_pha_ingest_token: Optional[str] = Header(default=None),
) -> RedirectResponse:
    form = await request.form()
    offered = token or (str(form.get("token") or "").strip() or None)
    _auth(x_pha_ingest_token, offered)
    uid = (user_id or "default").strip() or "default"
    raw = form.getlist("metric_id")
    save_enabled_metric_ids(uid, [str(x) for x in raw])
    if form.get("locale"):
        save_fact_card_locale(uid, str(form.get("locale") or ""))
    if "assessment_prompt" in form:
        try:
            save_assessment_prompt(uid, str(form.get("assessment_prompt") or ""))
        except ValueError as exc:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "assessment_prompt_too_long",
                    "max": ASSESSMENT_PROMPT_MAX,
                },
            ) from exc
    qs = f"user_id={uid}"
    if offered:
        qs += f"&token={offered}"
    return RedirectResponse(
        url=f"/proactive/fact-card/view?{qs}",
        status_code=303,
    )


@router.post("/proactive/fact-card/interpret")
def post_fact_card_interpret(
    user_id: str = Query("default"),
    token: Optional[str] = Query(default=None),
    x_pha_ingest_token: Optional[str] = Header(default=None),
) -> dict:
    _auth(x_pha_ingest_token, token)
    uid = (user_id or "default").strip() or "default"
    try:
        return _decorate_interpretation(start_interpretation(uid), uid)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail={"error": "interpret_failed", "reason": type(exc).__name__},
        ) from exc


@router.get("/proactive/fact-card/interpret")
def get_fact_card_interpret(
    user_id: str = Query("default"),
    token: Optional[str] = Query(default=None),
    x_pha_ingest_token: Optional[str] = Header(default=None),
) -> dict:
    _auth(x_pha_ingest_token, token)
    uid = (user_id or "default").strip() or "default"
    got = load_interpretation_for_user(uid)
    if got is None:
        return {
            "status": None,
            "ok": False,
            "error": None,
            "text": None,
            "model": None,
            "generated_at": None,
            "message": "not_requested",
        }
    return _decorate_interpretation(got, uid)
