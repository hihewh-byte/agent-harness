"""Fact card JSON, mobile HTML view, and user metric prefs. Same ingest token. No LLM."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Header, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel, Field

from pha.fact_card import load_fact_card
from pha.fact_card_html import render_fact_card_html
from pha.fact_card_prefs import prefs_payload, save_enabled_metric_ids
from pha.healthkit_ingest import require_ingest_token

router = APIRouter(tags=["proactive"])


class FactCardPrefsBody(BaseModel):
    enabled_metric_ids: list[str] = Field(default_factory=list)


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
        return load_fact_card(uid)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail={"error": "fact_card_failed", "reason": type(exc).__name__},
        ) from exc


@router.get("/proactive/fact-card/view", response_class=HTMLResponse)
def get_fact_card_view(
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
    html = render_fact_card_html(card, prefs=prefs, token=token)
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
    qs = f"user_id={uid}"
    if offered:
        qs += f"&token={offered}"
    return RedirectResponse(
        url=f"/proactive/fact-card/view?{qs}",
        status_code=303,
    )
