"""Tax chat message stack — PHA recency-optimized layout (v1.6 P4)."""

from __future__ import annotations

import json
from typing import Any

FILING_LEDGER_PREAMBLE = (
    "【报税会话账本 · FILING_LEDGER】\n"
    "以下为 Python 从 dataset / filing_table / manifest 注入的权威上下文；"
    "答复中数字须与此一致，禁止编造税额或汇率。"
)

SESSION_JSON_PREAMBLE = "【会话快照 · SESSION_STATE】"


def build_tax_chat_message_stack(
    *,
    system_soul: str,
    task_text: str = "",
    history_messages: list[dict[str, str]] | None = None,
    filing_ledger: str = "",
    episodic_block: str = "",
    tax_insight_block: str = "",
    session_snapshot: dict[str, Any] | None = None,
    raw_user_message: str,
) -> list[dict[str, str]]:
    """
    Physical message stack (recency-optimized, 仿 PHA build_pha_chat_message_stack):

    1) system: 角色灵魂 + 本轮 TASK（短）
    2) sliding-window session history
    3) user: FILING_LEDGER（Tier0 证据，紧贴当前问题）
    4) user: EPISODIC_BRIDGE / CHAT_RECALL
    5) user: TAX_INSIGHT（若有）
    6) user: SESSION_STATE JSON（结构化快照）
    7) user: 用户原文（Raw User Lane）
    """
    soul = (system_soul or "").strip()
    if (task_text or "").strip():
        soul = f"{soul}\n\n【本轮任务】\n{task_text.strip()}"

    messages: list[dict[str, str]] = [{"role": "system", "content": soul}]

    for item in history_messages or []:
        role = item.get("role") or "user"
        if role not in ("user", "assistant"):
            continue
        content = (item.get("content") or "").strip()
        if content:
            messages.append({"role": role, "content": content[:1200]})

    ledger = (filing_ledger or "").strip()
    if ledger:
        messages.append(
            {
                "role": "user",
                "content": f"{FILING_LEDGER_PREAMBLE}\n\n{ledger}",
            }
        )

    episodic = (episodic_block or "").strip()
    if episodic:
        messages.append({"role": "user", "content": episodic})

    insight = (tax_insight_block or "").strip()
    if insight:
        messages.append({"role": "user", "content": insight})

    if session_snapshot:
        snap = json.dumps(session_snapshot, ensure_ascii=False)
        if len(snap) > 1800:
            snap = snap[:1800] + "…"
        messages.append(
            {
                "role": "user",
                "content": f"{SESSION_JSON_PREAMBLE}\n{snap}",
            }
        )

    raw = (raw_user_message or "").strip()
    messages.append({"role": "user", "content": raw})
    return messages


def build_session_snapshot_dict(ctx: Any, *, user_message: str = "") -> dict[str, Any]:
    """Compact session state for LLM (non-authoritative; 数字以 FILING_LEDGER 为准)."""
    return {
        "userMessage": user_message,
        "hasDataset": bool(getattr(ctx, "dataset_id", None)),
        "datasetId": getattr(ctx, "dataset_id", None),
        "lastRunId": getattr(ctx, "last_run_id", None),
        "eventCount": getattr(ctx, "event_count", None),
        "defaultTaxYear": getattr(ctx, "tax_year", None),
        "hasTaxInsight": bool(getattr(ctx, "tax_insight", None)),
        "riskLevel": getattr(ctx, "risk_level", None),
        "filingScope": getattr(ctx, "filing_scope", None),
    }
