"""GET /proactive/fact-card — same ingest token, no LLM."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Header, HTTPException, Query

from pha.fact_card import load_fact_card
from pha.healthkit_ingest import require_ingest_token

router = APIRouter(tags=["proactive"])


@router.get("/proactive/fact-card")
def get_fact_card(
    user_id: str = Query("default"),
    x_pha_ingest_token: Optional[str] = Header(default=None),
) -> dict:
    require_ingest_token(x_pha_ingest_token, None)
    uid = (user_id or "default").strip() or "default"
    try:
        return load_fact_card(uid)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail={"error": "fact_card_failed", "reason": type(exc).__name__},
        ) from exc
