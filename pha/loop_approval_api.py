"""Ops API: Loop weekly approvals (human gate; no catalog auto-merge)."""

from __future__ import annotations

import html
from typing import Optional

from fastapi import APIRouter, Header, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from pha.loop_weekly import (
    approve_and_execute,
    get_approval,
    list_pending_approvals,
    reject_approval,
    verify_approve_token,
)

router = APIRouter(tags=["ops-loop"])


def _auth(token: Optional[str], x_pha_ingest_token: Optional[str], x_pha_loop_token: Optional[str]) -> None:
    provided = (token or x_pha_loop_token or x_pha_ingest_token or "").strip()
    if not verify_approve_token(provided):
        raise HTTPException(status_code=401, detail="invalid_or_missing_loop_approve_token")


def _wants_html(request: Request) -> bool:
    accept = (request.headers.get("accept") or "").lower()
    return "text/html" in accept and "application/json" not in accept.split(",")[0]


@router.get("/ops/loop/inbox")
def loop_inbox(
    token: Optional[str] = Query(None),
    x_pha_ingest_token: Optional[str] = Header(None, alias="X-PHA-Ingest-Token"),
    x_pha_loop_token: Optional[str] = Header(None, alias="X-PHA-Loop-Token"),
) -> dict:
    _auth(token, x_pha_ingest_token, x_pha_loop_token)
    pending = list_pending_approvals()
    return {"ok": True, "pending_n": len(pending), "pending": pending}


@router.get("/ops/loop/approvals/{approval_id}")
def loop_approval_get(
    approval_id: str,
    token: Optional[str] = Query(None),
    x_pha_ingest_token: Optional[str] = Header(None, alias="X-PHA-Ingest-Token"),
    x_pha_loop_token: Optional[str] = Header(None, alias="X-PHA-Loop-Token"),
) -> dict:
    _auth(token, x_pha_ingest_token, x_pha_loop_token)
    doc = get_approval(approval_id)
    if not doc:
        raise HTTPException(status_code=404, detail="not_found")
    return {"ok": True, "approval": doc}


@router.get("/ops/loop/approvals/{approval_id}/view", response_class=HTMLResponse)
def loop_approval_view(
    approval_id: str,
    token: Optional[str] = Query(None),
) -> HTMLResponse:
    """Phone/Mac friendly approve page. Token via query (same as fact-card Safari)."""
    if not verify_approve_token(token):
        return HTMLResponse(
            "<h1>401</h1><p>Missing or invalid token. Append ?token=…</p>",
            status_code=401,
        )
    doc = get_approval(approval_id)
    if not doc:
        return HTMLResponse("<h1>404</h1><p>Approval not found.</p>", status_code=404)
    aid = html.escape(str(doc.get("approval_id") or ""))
    status = html.escape(str(doc.get("status") or ""))
    aliases = "".join(f"<li>{html.escape(str(a))}</li>" for a in (doc.get("aliases") or []))
    tok = html.escape(token or "")
    pending = status == "pending"
    result_block = ""
    exec_info = doc.get("execution") or {}
    if exec_info:
        veto = exec_info.get("full_veto") or {}
        result_block = (
            f"<p class='fine'>Veto passed: {html.escape(str(veto.get('passed')))}"
            f"<br/>Verdict: <code>{html.escape(str(veto.get('verdict_path') or ''))}</code>"
            f"<br/>Catalog merged: <b>false</b></p>"
        )
    btns = ""
    if pending:
        btns = f"""
<form method="post" action="/ops/loop/approvals/{aid}/approve?token={tok}&amp;confirm=YES" style="display:inline">
  <button type="submit">Approve · run full-veto</button>
</form>
<form method="post" action="/ops/loop/approvals/{aid}/reject?token={tok}&amp;reason=rejected_by_operator" style="display:inline;margin-left:1rem">
  <button type="submit">Reject</button>
</form>
<p class="fine">Approve does <b>not</b> merge catalog. It only runs full-veto
(+ optional Draft PR if enabled). Catalog still needs a human Ready PR.</p>
"""
    body = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>PHA Loop approval</title>
<style>
body{{font-family:system-ui,sans-serif;max-width:40rem;margin:2rem auto;padding:0 1rem;line-height:1.45}}
.fine{{color:#555;font-size:.9rem}} button{{font-size:1rem;padding:.5rem 1rem}}
</style></head><body>
<h1>PHA Loop approval</h1>
<p>Status: <b>{status}</b><br/>Id: <code>{aid}</code></p>
<p>Aliases:</p><ul>{aliases or "<li>(none)</li>"}</ul>
{result_block}
{btns}
<p class="fine">Educational / ops tooling — not medical advice.</p>
</body></html>"""
    return HTMLResponse(body)


def _safe_next(next_url: Optional[str]) -> Optional[str]:
    """Only allow same-origin relative redirects back to fact-card / ops views."""
    raw = (next_url or "").strip()
    if not raw.startswith("/"):
        return None
    if raw.startswith("//"):
        return None
    if not (
        raw.startswith("/proactive/fact-card")
        or raw.startswith("/ops/loop/approvals/")
    ):
        return None
    return raw


@router.post("/ops/loop/approvals/{approval_id}/approve")
async def loop_approval_approve(
    request: Request,
    approval_id: str,
    token: Optional[str] = Query(None),
    confirm: str = Query("YES"),
    draft_pr: bool = Query(False),
    next: Optional[str] = Query(None),
    x_pha_ingest_token: Optional[str] = Header(None, alias="X-PHA-Ingest-Token"),
    x_pha_loop_token: Optional[str] = Header(None, alias="X-PHA-Loop-Token"),
):
    _auth(token, x_pha_ingest_token, x_pha_loop_token)
    result = approve_and_execute(approval_id, confirm=confirm or "YES", run_draft_pr=draft_pr)
    if result.get("error") == "not_found":
        raise HTTPException(status_code=404, detail=result)
    if result.get("error") == "confirm_must_be_YES":
        raise HTTPException(status_code=400, detail=result)
    dest = _safe_next(next)
    if dest and token:
        sep = "&" if "?" in dest else "?"
        return RedirectResponse(url=f"{dest}{sep}token={token}", status_code=303)
    if token and _wants_html(request):
        return RedirectResponse(
            url=f"/ops/loop/approvals/{approval_id}/view?token={token}",
            status_code=303,
        )
    return JSONResponse(result)


@router.post("/ops/loop/approvals/{approval_id}/reject")
async def loop_approval_reject(
    request: Request,
    approval_id: str,
    token: Optional[str] = Query(None),
    reason: str = Query("rejected_by_operator"),
    next: Optional[str] = Query(None),
    x_pha_ingest_token: Optional[str] = Header(None, alias="X-PHA-Ingest-Token"),
    x_pha_loop_token: Optional[str] = Header(None, alias="X-PHA-Loop-Token"),
):
    _auth(token, x_pha_ingest_token, x_pha_loop_token)
    result = reject_approval(approval_id, reason=reason)
    if result.get("error") == "not_found":
        raise HTTPException(status_code=404, detail=result)
    dest = _safe_next(next)
    if dest and token:
        sep = "&" if "?" in dest else "?"
        return RedirectResponse(url=f"{dest}{sep}token={token}", status_code=303)
    if token and _wants_html(request):
        return RedirectResponse(
            url=f"/ops/loop/approvals/{approval_id}/view?token={token}",
            status_code=303,
        )
    return JSONResponse(result)
