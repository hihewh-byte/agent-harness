#!/usr/bin/env python3
"""Tax user profile selfcheck (Tax Chat Experience v2 · C6)."""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tax_agent.chat_turn_service import ChatTurnRequest, resolve_chat_turn
from tax_agent.filing_session_state import FilingSessionState, master_anchor_with_profile
from tax_agent.numerics_audit import _FX_RATE_RE, extract_significant_numbers
from tax_agent.session_context import SessionContext
from tax_agent.tax_user_profile import (
    build_progress_summary,
    clear_tax_user_profile,
    get_tax_user_profile,
    is_clear_profile_message,
    is_recall_progress_message,
    sanitize_summary_no_amounts,
    sync_profile_from_session,
    try_profile_command_turn,
)

_USER = "c6-selfcheck-user"


def main() -> int:
    clear_tax_user_profile(_USER)

    assert is_recall_progress_message("上次我算到哪了")
    assert is_clear_profile_message("忘掉我的记录")
    print("PASS profile command detection")

    state = FilingSessionState(
        dataset_id="ds1",
        uploaded_years=[2022, 2023],
        focus_tax_year=2023,
        has_compute=True,
        journey_phase="computed",
        user_key=_USER,
    )
    summary = build_progress_summary(state, last_mode="provenance_fast")
    assert summary
    assert not _FX_RATE_RE.search(summary)
    nums = extract_significant_numbers(summary)
    assert all(len(n) == 4 and n.startswith("20") for n in nums), nums
    print("PASS C6-3 summary without amount numerics")

    dirty = sanitize_summary_no_amounts("已测算税额 12345.67 元，汇率 6.3757")
    assert "6.3757" not in dirty and "12345" not in dirty
    print("PASS sanitize_summary_no_amounts")

    sync_profile_from_session(_USER, state=state, session_id="sess-a", last_mode="compute")
    prof = get_tax_user_profile(_USER)
    assert prof and prof.progress_summary
    assert "2023" in prof.progress_summary or "2022" in prof.progress_summary
    print("PASS profile sync")

    ctx = SessionContext(session_id="sess-b", user_key=_USER, tax_year=2024)
    turn = try_profile_command_turn("上次我算到哪了", ctx)
    assert turn and "上次记录" in turn.reply or "本机" in turn.reply
    assert "根据本机上次记录" in turn.reply
    print("PASS C6-1 cross-session recall")

    anchor = master_anchor_with_profile(
        FilingSessionState(user_key=_USER, journey_phase="onboarding", focus_tax_year=2024)
    )
    assert "上次进度" in anchor
    print("PASS MASTER_ANCHOR profile line")

    clear_turn = try_profile_command_turn("忘掉我的记录", ctx)
    assert clear_turn and "清除" in clear_turn.reply
    assert get_tax_user_profile(_USER) is None
    print("PASS C6-2 clear profile")

    sync_profile_from_session(_USER, state=state, session_id="sess-c")
    req = ChatTurnRequest(
        session_id="sess-d",
        user_key=_USER,
        message="你好",
        llm_model="__off__",
    )
    ctx2 = SessionContext(session_id=req.session_id, user_key=_USER, tax_year=2024)
    outcome = resolve_chat_turn(req, ctx2, apply_composer=False)
    assert get_tax_user_profile(_USER) is not None
    print("PASS profile sync via chat_turn_service")

    clear_tax_user_profile(_USER)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
