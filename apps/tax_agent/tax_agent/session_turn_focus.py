"""Session episodic focus — 多轮保持纳税年度 / 主题（v1.6，仿 PHA session_turn_focus）。"""

from __future__ import annotations

import json
import os
import re
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tax_agent.tax_intent_catalog import catalog_topic_markers, matches_anaphora, token_in_message


def _db_path() -> Path:
    env = os.environ.get("TAX_AGENT_DB")
    if env:
        return Path(env)
    data_dir = Path(__file__).resolve().parent.parent / ".data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / "tax_agent.db"


def _focus_ttl_turns() -> int:
    try:
        return max(1, int(os.environ.get("TAX_SESSION_FOCUS_TTL_TURNS", "8")))
    except ValueError:
        return 8


_FOCUS_SCHEMA = """
CREATE TABLE IF NOT EXISTS tax_session_turn_focus (
    session_id TEXT PRIMARY KEY,
    focus_tax_year INTEGER NOT NULL DEFAULT 0,
    focus_profile TEXT NOT NULL DEFAULT '',
    focus_summary TEXT NOT NULL DEFAULT '',
    focus_tokens_json TEXT NOT NULL DEFAULT '[]',
    turns_remaining INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL,
    focus_tax_years_json TEXT NOT NULL DEFAULT '[]',
    last_user_message TEXT NOT NULL DEFAULT '',
    last_assistant_digest TEXT NOT NULL DEFAULT '',
    last_mode TEXT NOT NULL DEFAULT ''
);
"""


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(_db_path())
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_columns(conn: sqlite3.Connection) -> None:
    cols = {r[1] for r in conn.execute("PRAGMA table_info(tax_session_turn_focus)")}
    migrations = {
        "focus_tax_years_json": "TEXT NOT NULL DEFAULT '[]'",
        "last_user_message": "TEXT NOT NULL DEFAULT ''",
        "last_assistant_digest": "TEXT NOT NULL DEFAULT ''",
        "last_mode": "TEXT NOT NULL DEFAULT ''",
    }
    for name, typedef in migrations.items():
        if name not in cols:
            conn.execute(f"ALTER TABLE tax_session_turn_focus ADD COLUMN {name} {typedef}")


def init_tax_session_focus_schema() -> None:
    with _connect() as conn:
        conn.executescript(_FOCUS_SCHEMA)
        _ensure_columns(conn)
        conn.commit()


@dataclass
class TaxSessionTurnFocus:
    session_id: str
    focus_tax_year: int
    focus_profile: str
    focus_summary: str
    focus_tokens: list[str]
    turns_remaining: int
    updated_at: str = ""
    focus_tax_years: list[int] = field(default_factory=list)
    last_user_message: str = ""
    last_assistant_digest: str = ""
    last_mode: str = ""

    @property
    def active(self) -> bool:
        return self.focus_tax_year > 0 and self.turns_remaining > 0


def _normalize_years(
    tax_year: int,
    tax_years: list[int] | None,
) -> list[int]:
    if tax_years:
        ys = sorted({int(y) for y in tax_years if int(y) > 0})
        if ys:
            return ys
    if tax_year > 0:
        return [int(tax_year)]
    return []


def summarize_assistant_digest(reply: str, *, max_len: int = 320) -> str:
    text = re.sub(r"\s+", " ", (reply or "").strip())
    if len(text) <= max_len:
        return text
    return text[: max_len - 1] + "…"


def save_tax_session_focus(
    session_id: str,
    *,
    focus_tax_year: int,
    focus_profile: str = "",
    focus_summary: str = "",
    focus_tokens: list[str] | None = None,
    turns_remaining: int | None = None,
    focus_tax_years: list[int] | None = None,
    last_user_message: str = "",
    last_assistant_digest: str = "",
    last_mode: str = "",
) -> None:
    sid = (session_id or "").strip()
    years = _normalize_years(focus_tax_year, focus_tax_years)
    if not sid or not years:
        return
    primary = years[0]
    ttl = turns_remaining if turns_remaining is not None else _focus_ttl_turns()
    init_tax_session_focus_schema()
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    tokens = [str(t) for t in (focus_tokens or []) if str(t).strip()][:32]
    for y in years:
        if str(y) not in tokens:
            tokens.insert(0, str(y))
    summary = (focus_summary or f"{', '.join(str(y) for y in years)} 年度报税").strip()[:2000]
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO tax_session_turn_focus (
                session_id, focus_tax_year, focus_profile, focus_summary,
                focus_tokens_json, turns_remaining, updated_at,
                focus_tax_years_json, last_user_message, last_assistant_digest, last_mode
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(session_id) DO UPDATE SET
                focus_tax_year = excluded.focus_tax_year,
                focus_profile = excluded.focus_profile,
                focus_summary = excluded.focus_summary,
                focus_tokens_json = excluded.focus_tokens_json,
                turns_remaining = excluded.turns_remaining,
                updated_at = excluded.updated_at,
                focus_tax_years_json = excluded.focus_tax_years_json,
                last_user_message = excluded.last_user_message,
                last_assistant_digest = excluded.last_assistant_digest,
                last_mode = excluded.last_mode
            """,
            (
                sid,
                int(primary),
                (focus_profile or "")[:64],
                summary,
                json.dumps(tokens, ensure_ascii=False),
                int(ttl),
                now,
                json.dumps(years, ensure_ascii=False),
                (last_user_message or "")[:2000],
                (last_assistant_digest or "")[:2000],
                (last_mode or "")[:64],
            ),
        )
        conn.commit()


def get_tax_session_focus(session_id: str) -> TaxSessionTurnFocus | None:
    sid = (session_id or "").strip()
    if not sid:
        return None
    init_tax_session_focus_schema()
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT session_id, focus_tax_year, focus_profile, focus_summary,
                   focus_tokens_json, turns_remaining, updated_at,
                   focus_tax_years_json, last_user_message, last_assistant_digest, last_mode
            FROM tax_session_turn_focus WHERE session_id = ?
            """,
            (sid,),
        ).fetchone()
    if not row:
        return None
    try:
        tokens = json.loads(row["focus_tokens_json"] or "[]")
    except json.JSONDecodeError:
        tokens = []
    try:
        years = json.loads(row["focus_tax_years_json"] or "[]")
    except json.JSONDecodeError:
        years = []
    years_norm = _normalize_years(int(row["focus_tax_year"] or 0), [int(y) for y in years])
    return TaxSessionTurnFocus(
        session_id=row["session_id"],
        focus_tax_year=int(row["focus_tax_year"] or 0),
        focus_profile=row["focus_profile"] or "",
        focus_summary=row["focus_summary"] or "",
        focus_tokens=[str(t) for t in tokens if str(t).strip()],
        turns_remaining=int(row["turns_remaining"] or 0),
        updated_at=row["updated_at"] or "",
        focus_tax_years=years_norm,
        last_user_message=row["last_user_message"] or "",
        last_assistant_digest=row["last_assistant_digest"] or "",
        last_mode=row["last_mode"] or "",
    )


def user_hits_focus_tokens(message: str, tokens: list[str]) -> bool:
    msg = (message or "").strip()
    if not msg or not tokens:
        return False
    low = msg.lower()
    for t in tokens:
        tok = (t or "").strip()
        if not tok:
            continue
        if tok in msg or tok.lower() in low:
            return True
    return bool(matches_anaphora(msg) and tokens)


def _topic_continues(message: str, focus: TaxSessionTurnFocus) -> bool:
    msg = message or ""
    if matches_anaphora(msg):
        return True
    hint = None
    for topic in ("policy_explain", "coverage_check", "filing_coach", "filing_narrative"):
        for tok in catalog_topic_markers(topic):
            if token_in_message(tok, msg):
                hint = topic
                break
        if hint:
            break
    if hint and focus.focus_profile and hint == focus.focus_profile:
        return True
    if focus.last_assistant_digest:
        from tax_agent.chat_context import extract_tax_keywords

        overlap = set(extract_tax_keywords(msg)) & set(
            extract_tax_keywords(focus.last_assistant_digest)
        )
        if overlap:
            return True
    return False


def revive_tax_session_focus(session_id: str, user_message: str) -> TaxSessionTurnFocus | None:
    focus = get_tax_session_focus(session_id)
    if not focus or focus.focus_tax_year <= 0:
        return None
    if focus.active:
        return focus
    if not _topic_continues(user_message, focus) and not user_hits_focus_tokens(
        user_message, focus.focus_tokens
    ):
        return None
    save_tax_session_focus(
        session_id,
        focus_tax_year=focus.focus_tax_year,
        focus_tax_years=focus.focus_tax_years,
        focus_profile=focus.focus_profile,
        focus_summary=focus.focus_summary,
        focus_tokens=focus.focus_tokens,
        turns_remaining=_focus_ttl_turns(),
        last_user_message=focus.last_user_message,
        last_assistant_digest=focus.last_assistant_digest,
        last_mode=focus.last_mode,
    )
    return get_tax_session_focus(session_id)


def consume_tax_session_focus(session_id: str) -> TaxSessionTurnFocus | None:
    focus = get_tax_session_focus(session_id)
    if not focus or not focus.active:
        return None
    remaining = max(0, focus.turns_remaining - 1)
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    with _connect() as conn:
        conn.execute(
            """
            UPDATE tax_session_turn_focus
            SET turns_remaining = ?, updated_at = ?
            WHERE session_id = ?
            """,
            (remaining, now, focus.session_id),
        )
        conn.commit()
    focus.turns_remaining = remaining
    return focus


def resolve_focus_tax_year(
    message: str,
    default_year: int,
    focus: TaxSessionTurnFocus | None,
) -> int:
    from tax_agent.chat_orchestrator import infer_tax_year
    from tax_agent.tax_turn_resolver import anaphora_shift_year

    explicit = infer_tax_year(message, default_year)
    if explicit != default_year or re.search(r"(20\d{2}|\d{2}\s*年)", message or ""):
        return explicit
    if focus and focus.focus_tax_years:
        shifted = anaphora_shift_year(message, focus.focus_tax_years)
        if shifted:
            return shifted[0]
    if focus and focus.active:
        if matches_anaphora(message or "") or user_hits_focus_tokens(
            message, focus.focus_tokens
        ):
            return focus.focus_tax_year
    return infer_tax_year(message, default_year)


def record_turn_focus(
    session_id: str,
    *,
    tax_year: int,
    tax_years: list[int] | None = None,
    profile: str,
    user_message: str,
    assistant_reply: str = "",
    mode: str = "",
) -> None:
    """每轮对话结束：递减 TTL 并刷新焦点年度/主题/episodic 摘要。"""
    sid = (session_id or "").strip()
    years = _normalize_years(tax_year, tax_years)
    if not sid or not years:
        return
    from tax_agent.chat_context import extract_tax_keywords

    consume_tax_session_focus(sid)
    save_tax_session_focus(
        sid,
        focus_tax_year=years[0],
        focus_tax_years=years,
        focus_profile=profile,
        focus_summary=f"{', '.join(str(y) for y in years)} 年 · {profile}",
        focus_tokens=extract_tax_keywords(user_message) + [str(y) for y in years],
        last_user_message=(user_message or "")[:2000],
        last_assistant_digest=summarize_assistant_digest(assistant_reply),
        last_mode=(mode or "")[:64],
    )


def focus_tier0_block(focus: TaxSessionTurnFocus | None) -> str:
    if not focus or not focus.active:
        return ""
    years = focus.focus_tax_years or [focus.focus_tax_year]
    return (
        f"【回合焦点 · TTL={focus.turns_remaining}】\n"
        f"- 关注年度: {', '.join(str(y) for y in years)}\n"
        f"- 主题: {focus.focus_profile or 'general'}\n"
        f"- 摘要: {focus.focus_summary[:400]}"
    )


def episodic_bridge_block(focus: TaxSessionTurnFocus | None) -> str:
    if not focus:
        return ""
    if not (focus.last_user_message or focus.last_assistant_digest):
        return ""
    years = focus.focus_tax_years or ([focus.focus_tax_year] if focus.focus_tax_year else [])
    lines = [
        "【上轮对话摘要 · EPISODIC_BRIDGE】",
        f"- 焦点年度: {', '.join(str(y) for y in years) if years else '—'}",
        f"- 主题: {focus.focus_profile or '—'}",
    ]
    if focus.last_user_message:
        lines.append(f"- 用户：{summarize_assistant_digest(focus.last_user_message, max_len=200)}")
    if focus.last_assistant_digest:
        lines.append(f"- 助手：{focus.last_assistant_digest}")
    if focus.active:
        lines.append(f"- 续焦剩余: {focus.turns_remaining} 轮")
    return "\n".join(lines)
