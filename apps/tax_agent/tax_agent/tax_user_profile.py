"""Cross-session user profile — local SQLite, privacy-first (Tax Chat Experience v2 · C6)."""

from __future__ import annotations

import json
import os
import re
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tax_agent.filing_session_state import FilingSessionState
from tax_agent.numerics_audit import _FX_RATE_RE

_CLEAR_RE = re.compile(
    r"(忘掉我的记录|忘记我的记录|清除我的记录|删除我的记录|清除本地记录|忘记进度)",
)
_RECALL_RE = re.compile(
    r"(上次算到哪|上次进度|上次算到哪里|继续上次|我算到哪了|进度到哪了|上次进行)",
)

_YEAR_STATUS_VALUES = frozenset({"none", "uploaded", "computed", "reviewing", "filed"})
_VERBOSITY_VALUES = frozenset({"brief", "normal", "detailed"})


def _db_path() -> Path:
    env = os.environ.get("TAX_AGENT_DB")
    if env:
        return Path(env)
    data_dir = Path(__file__).resolve().parent.parent / ".data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / "tax_agent.db"


_SCHEMA = """
CREATE TABLE IF NOT EXISTS tax_user_profile (
    user_key TEXT PRIMARY KEY,
    resident_status TEXT NOT NULL DEFAULT 'cn_tax_resident',
    years_status_json TEXT NOT NULL DEFAULT '{}',
    llm_preference TEXT NOT NULL DEFAULT 'auto',
    reply_verbosity TEXT NOT NULL DEFAULT 'normal',
    progress_summary TEXT NOT NULL DEFAULT '',
    last_session_id TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL
);
"""


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(_db_path())
    conn.row_factory = sqlite3.Row
    return conn


def init_tax_user_profile_schema() -> None:
    with _connect() as conn:
        conn.executescript(_SCHEMA)
        conn.commit()


@dataclass
class TaxUserProfile:
    user_key: str
    resident_status: str = "cn_tax_resident"
    years_status: dict[str, str] = field(default_factory=dict)
    llm_preference: str = "auto"
    reply_verbosity: str = "normal"
    progress_summary: str = ""
    last_session_id: str = ""
    updated_at: str = ""


def is_clear_profile_message(message: str) -> bool:
    return bool(_CLEAR_RE.search((message or "").strip()))


def is_recall_progress_message(message: str) -> bool:
    return bool(_RECALL_RE.search((message or "").strip()))


def sanitize_summary_no_amounts(text: str) -> str:
    """Remove amount-like numerics from profile summary (C6 red line)."""
    out = text or ""
    out = _FX_RATE_RE.sub("", out)
    # Strip decimals and comma-grouped amounts; preserve 4-digit tax years (20xx).
    out = re.sub(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?", "", out)
    out = re.sub(r"(?<!\d)\d+\.\d+(?!\d)", "", out)
    out = re.sub(r"\s{2,}", " ", out)
    out = re.sub(r"[；;]{2,}", "；", out)
    return out.strip(" ；;")[:500]


def build_progress_summary(state: FilingSessionState, *, last_mode: str = "") -> str:
    """Deterministic progress blurb — no tax amounts."""
    parts: list[str] = []
    if state.uploaded_years:
        yrs = "、".join(str(y) for y in state.uploaded_years[:8])
        parts.append(f"已上传 {yrs} 年富途税表")
    if state.has_compute:
        y = state.focus_tax_year or (state.uploaded_years[-1] if state.uploaded_years else "")
        if y:
            parts.append(f"{y} 年度已完成测算")
        else:
            parts.append("已完成税额测算")
    if state.guided_wizard_active and state.guided_step:
        parts.append(f"申报向导停在 {state.guided_step} 步")
    elif state.journey_phase:
        phase_zh = {
            "onboarding": "入门",
            "collecting": "收集中",
            "ready": "可测算",
            "computed": "已测算",
            "reviewing": "填表辅导",
            "export": "导出",
        }.get(state.journey_phase, state.journey_phase)
        parts.append(f"旅程阶段 {phase_zh}")
    if last_mode and last_mode not in ("rules", "clarify"):
        parts.append(f"上轮 {last_mode}")
    if not parts:
        return ""
    return sanitize_summary_no_amounts("；".join(parts))


def _infer_year_statuses(state: FilingSessionState) -> dict[str, str]:
    out: dict[str, str] = {}
    for y in state.uploaded_years:
        out[str(y)] = "uploaded"
    if state.has_compute and state.focus_tax_year:
        out[str(state.focus_tax_year)] = "computed"
    if state.journey_phase in ("reviewing", "export") and state.focus_tax_year:
        out[str(state.focus_tax_year)] = "reviewing"
    return out


def get_tax_user_profile(user_key: str) -> TaxUserProfile | None:
    key = (user_key or "").strip()
    if not key:
        return None
    init_tax_user_profile_schema()
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM tax_user_profile WHERE user_key = ?",
            (key,),
        ).fetchone()
    if not row:
        return None
    try:
        years = json.loads(row["years_status_json"] or "{}")
    except json.JSONDecodeError:
        years = {}
    clean_years = {str(k): str(v) for k, v in years.items() if str(v) in _YEAR_STATUS_VALUES}
    return TaxUserProfile(
        user_key=row["user_key"],
        resident_status=row["resident_status"] or "cn_tax_resident",
        years_status=clean_years,
        llm_preference=row["llm_preference"] or "auto",
        reply_verbosity=row["reply_verbosity"] or "normal",
        progress_summary=sanitize_summary_no_amounts(row["progress_summary"] or ""),
        last_session_id=row["last_session_id"] or "",
        updated_at=row["updated_at"] or "",
    )


def save_tax_user_profile(profile: TaxUserProfile) -> None:
    key = (profile.user_key or "").strip()
    if not key:
        return
    init_tax_user_profile_schema()
    summary = sanitize_summary_no_amounts(profile.progress_summary)
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO tax_user_profile (
                user_key, resident_status, years_status_json, llm_preference,
                reply_verbosity, progress_summary, last_session_id, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_key) DO UPDATE SET
                resident_status = excluded.resident_status,
                years_status_json = excluded.years_status_json,
                llm_preference = excluded.llm_preference,
                reply_verbosity = excluded.reply_verbosity,
                progress_summary = excluded.progress_summary,
                last_session_id = excluded.last_session_id,
                updated_at = excluded.updated_at
            """,
            (
                key,
                profile.resident_status,
                json.dumps(profile.years_status, ensure_ascii=False),
                profile.llm_preference,
                profile.reply_verbosity,
                summary,
                profile.last_session_id,
                now,
            ),
        )
        conn.commit()


def clear_tax_user_profile(user_key: str) -> bool:
    key = (user_key or "").strip()
    if not key:
        return False
    init_tax_user_profile_schema()
    with _connect() as conn:
        cur = conn.execute("DELETE FROM tax_user_profile WHERE user_key = ?", (key,))
        conn.commit()
        return cur.rowcount > 0


def normalize_reply_verbosity(raw: str | None) -> str:
    v = (raw or "normal").strip().lower()
    return v if v in _VERBOSITY_VALUES else "normal"


def resolve_profile_preferences(
    user_key: str | None,
    *,
    llm_model: str | None = None,
    reply_verbosity: str | None = None,
) -> tuple[str, str]:
    """Merge request with stored profile (C2 readback). Request wins when explicit."""
    model = (llm_model or "auto").strip() or "auto"
    verbosity = normalize_reply_verbosity(reply_verbosity)
    key = (user_key or "").strip()
    if not key:
        return model, verbosity
    prof = get_tax_user_profile(key)
    if not prof:
        return model, verbosity
    if model == "auto" and prof.llm_preference:
        model = prof.llm_preference
    if reply_verbosity is None and prof.reply_verbosity:
        verbosity = normalize_reply_verbosity(prof.reply_verbosity)
    return model, verbosity


def profile_preferences_payload(user_key: str) -> dict[str, Any]:
    """API-safe preferences (no amounts in summary)."""
    prof = get_tax_user_profile(user_key)
    if not prof:
        return {
            "userKey": user_key,
            "llmPreference": "auto",
            "replyVerbosity": "normal",
            "hasProfile": False,
        }
    return {
        "userKey": user_key,
        "llmPreference": prof.llm_preference or "auto",
        "replyVerbosity": normalize_reply_verbosity(prof.reply_verbosity),
        "hasProfile": True,
        "progressSummary": prof.progress_summary or "",
        "updatedAt": prof.updated_at,
    }


def profile_anchor_line(user_key: str) -> str:
    prof = get_tax_user_profile(user_key)
    if not prof or not prof.progress_summary:
        return ""
    return f"- 上次进度（本地）: {prof.progress_summary}"


def sync_profile_from_session(
    user_key: str,
    *,
    state: FilingSessionState,
    session_id: str = "",
    resident_status: str = "cn_tax_resident",
    llm_preference: str = "auto",
    reply_verbosity: str | None = None,
    last_mode: str = "",
) -> TaxUserProfile | None:
    key = (user_key or "").strip()
    if not key:
        return None
    existing = get_tax_user_profile(key)
    years = _infer_year_statuses(state)
    if existing and existing.years_status:
        merged = dict(existing.years_status)
        for y, st in years.items():
            if y not in merged or _status_rank(st) > _status_rank(merged[y]):
                merged[y] = st
        years = merged
    summary = build_progress_summary(state, last_mode=last_mode)
    if not summary and existing:
        summary = existing.progress_summary
    prof = TaxUserProfile(
        user_key=key,
        resident_status=resident_status or (existing.resident_status if existing else "cn_tax_resident"),
        years_status=years,
        llm_preference=llm_preference or (existing.llm_preference if existing else "auto"),
        reply_verbosity=normalize_reply_verbosity(
            reply_verbosity or (existing.reply_verbosity if existing else "normal")
        ),
        progress_summary=summary,
        last_session_id=session_id or (existing.last_session_id if existing else ""),
    )
    save_tax_user_profile(prof)
    return prof


def _status_rank(status: str) -> int:
    order = {"none": 0, "uploaded": 1, "computed": 2, "reviewing": 3, "filed": 4}
    return order.get(status, 0)


def try_profile_command_turn(
    message: str,
    ctx: Any,
) -> Any | None:
    """Clear or recall profile — deterministic, no LLM."""
    from tax_agent.chat_orchestrator import ChatTurnResult

    user_key = getattr(ctx, "user_key", None) or ""
    if not user_key:
        if is_clear_profile_message(message) or is_recall_progress_message(message):
            return ChatTurnResult(
                reply="本地用户标识未启用，无法读写跨会话进度。请刷新页面后重试。",
                action="none",
            )
        return None

    if is_clear_profile_message(message):
        clear_tax_user_profile(user_key)
        return ChatTurnResult(
            reply="已清除您在本机的报税进度记录（不含已上传税表与测算结果本身）。",
            action="none",
        )

    if is_recall_progress_message(message):
        prof = get_tax_user_profile(user_key)
        if not prof or not prof.progress_summary:
            return ChatTurnResult(
                reply="暂无本地进度记录。上传税表并说「带我申报」可开始新旅程。",
                action="none",
            )
        years_hint = ""
        if prof.years_status:
            items = [f"{y}({s})" for y, s in sorted(prof.years_status.items())[:6]]
            years_hint = f"\n\n年度状态：{', '.join(items)}。"
        body = f"根据本机上次记录：{prof.progress_summary}"
        if years_hint:
            body += years_hint
        return ChatTurnResult(reply=body + "。", action="none")
    return None
