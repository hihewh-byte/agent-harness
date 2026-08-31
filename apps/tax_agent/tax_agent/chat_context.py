"""Tax chat context — 会话内关键词召回（仿 PHA chat_context）。"""

from __future__ import annotations

import re
from typing import Any

TAX_KEYWORD_LEXICON: tuple[str, ...] = (
    "汇率",
    "中间价",
    "折算",
    "补缴",
    "汇算",
    "富途",
    "annual",
    "税表",
    "fifo",
    "合理费用",
    "资产原值",
    "总收入",
    "净损益",
    "财产转让",
    "期权",
    "到期",
    "持仓",
    "未实现",
    "ambiguous",
    "申报",
    "四列",
    "amzn",
    "tsla",
    "nvda",
)


def extract_tax_keywords(text: str) -> list[str]:
    raw = (text or "").lower()
    found: list[str] = []
    for kw in TAX_KEYWORD_LEXICON:
        if kw.lower() in raw or kw in (text or ""):
            found.append(kw)
    for m in re.finditer(r"(?<!\d)(20\d{2})(?!\d)", text or ""):
        y = m.group(1)
        if y not in found:
            found.append(y)
    for m in re.finditer(r"\b[A-Z]{2,5}\b", text or ""):
        sym = m.group(0)
        if sym not in found:
            found.append(sym)
    return found[:16]


def _excerpt(content: str, *, max_len: int = 220) -> str:
    t = (content or "").strip().replace("\n", " ")
    if len(t) <= max_len:
        return t
    return t[: max_len - 1] + "…"


def recent_turns_from_history(
    chat_history: list[dict[str, str]] | None,
    *,
    max_turns: int = 4,
) -> list[dict[str, str]]:
    if not chat_history:
        return []
    collected: list[dict[str, str]] = []
    turn = 0
    for item in reversed(chat_history):
        role = item.get("role") or "user"
        content = (item.get("content") or "").strip()
        if not content:
            continue
        collected.insert(0, {"role": role, "content": content})
        if role == "user":
            turn += 1
        if turn >= max_turns:
            break
    return collected


def search_history_by_keywords(
    chat_history: list[dict[str, str]] | None,
    keywords: list[str],
    *,
    limit: int = 4,
) -> list[dict[str, str]]:
    if not chat_history or not keywords:
        return []
    hits: list[dict[str, str]] = []
    for item in reversed(chat_history):
        content = item.get("content") or ""
        low = content.lower()
        if any(kw.lower() in low or kw in content for kw in keywords):
            hits.append(item)
        if len(hits) >= limit:
            break
    return list(reversed(hits))


def search_chat_by_keywords_sqlite(
    session_id: str,
    keywords: list[str],
    *,
    limit: int = 6,
) -> list[dict[str, Any]]:
    if not session_id or not keywords:
        return []
    try:
        from tax_agent.storage.sqlite_store import SqliteDatasetStore

        store = SqliteDatasetStore()
        if not hasattr(store, "_connect"):
            return []
    except Exception:
        return []

    patterns = [f"%{kw}%" for kw in keywords[:8]]
    clauses = " OR ".join(["content LIKE ?"] * len(patterns))
    sql = f"""
        SELECT role, content, created_at FROM chat_message
        WHERE session_id = ? AND ({clauses})
        ORDER BY created_at DESC LIMIT ?
    """
    with store._connect() as conn:
        rows = conn.execute(sql, (session_id, *patterns, limit)).fetchall()
    return [
        {"role": r["role"], "content": r["content"], "createdAt": r["created_at"]}
        for r in reversed(rows)
    ]


def build_chat_recall_block(
    user_message: str,
    *,
    session_id: str = "",
    chat_history: list[dict[str, str]] | None = None,
    focus_block: str = "",
    episodic_block: str = "",
) -> str:
    """Tier1 CHAT_RECALL 文本块。"""
    keywords = extract_tax_keywords(user_message)
    parts: list[str] = []
    if episodic_block.strip():
        parts.append(episodic_block.strip())
    if focus_block.strip():
        parts.append(focus_block.strip())

    recent = recent_turns_from_history(chat_history, max_turns=4)
    if recent:
        parts.append("【当前会话 · 最近对话】")
        for m in recent:
            role = "用户" if m.get("role") == "user" else "助手"
            parts.append(f"- {role}：{_excerpt(m.get('content', ''))}")

    recalled = search_history_by_keywords(chat_history, keywords, limit=3)
    if session_id and keywords:
        sql_hits = search_chat_by_keywords_sqlite(session_id, keywords, limit=4)
        seen = {(_excerpt(m.get("content", ""))) for m in recalled}
        for m in sql_hits:
            ex = _excerpt(m.get("content", ""))
            if ex not in seen:
                recalled.append(m)
                seen.add(ex)

    if keywords and recalled:
        parts.append(f"【关键词召回 · {', '.join(keywords[:8])}】")
        for m in recalled[-4:]:
            role = "用户" if m.get("role") == "user" else "助手"
            parts.append(f"- {role}：{_excerpt(m.get('content', ''))}")

    return "\n".join(parts).strip()
