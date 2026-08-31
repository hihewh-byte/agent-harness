#!/usr/bin/env python3
"""Phase C2: profile preference readback (llm + verbosity)."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tax_agent.answer_composer import max_reply_chars_for_profile
from tax_agent.chat_turn_service import ChatTurnRequest, resolve_chat_turn
from tax_agent.filing_session_state import FilingSessionState
from tax_agent.session_context import SessionContext
from tax_agent.tax_user_profile import (
    clear_tax_user_profile,
    get_tax_user_profile,
    profile_preferences_payload,
    resolve_profile_preferences,
    save_tax_user_profile,
    sync_profile_from_session,
    TaxUserProfile,
)


def main() -> int:
    user = "c2-selfcheck-user"
    clear_tax_user_profile(user)

    save_tax_user_profile(
        TaxUserProfile(
            user_key=user,
            llm_preference="__off__",
            reply_verbosity="brief",
            progress_summary="已上传 2023 年富途税表",
        )
    )
    model, verb = resolve_profile_preferences(user, llm_model="auto")
    assert model == "__off__" and verb == "brief", (model, verb)
    model2, verb2 = resolve_profile_preferences(user, llm_model="qwen2.5:7b", reply_verbosity="detailed")
    assert model2 == "qwen2.5:7b" and verb2 == "detailed"
    print("PASS C2-1 resolve_profile_preferences readback + request override")

    payload = profile_preferences_payload(user)
    assert payload["hasProfile"] and payload["llmPreference"] == "__off__"
    assert payload["replyVerbosity"] == "brief"
    assert "12345" not in (payload.get("progressSummary") or "")
    print("PASS C2-2 profile API payload")

    brief = max_reply_chars_for_profile("policy_qa", reply_verbosity="brief")
    normal = max_reply_chars_for_profile("policy_qa", reply_verbosity="normal")
    detailed = max_reply_chars_for_profile("filing_narrative", reply_verbosity="detailed")
    assert brief < normal < detailed
    print("PASS C2-3 verbosity affects max_chars")

    state = FilingSessionState(dataset_id="ds1", uploaded_years=[2023], has_compute=True, focus_tax_year=2023)
    sync_profile_from_session(
        user,
        state=state,
        session_id="s1",
        llm_preference="__off__",
        reply_verbosity="detailed",
    )
    prof = get_tax_user_profile(user)
    assert prof and prof.reply_verbosity == "detailed"
    print("PASS C2-4 sync saves reply_verbosity")

    save_tax_user_profile(
        TaxUserProfile(
            user_key=user,
            llm_preference="__off__",
            reply_verbosity="brief",
            progress_summary="已上传 2023 年富途税表",
        )
    )
    req = ChatTurnRequest(
        session_id="c2-chat",
        user_key=user,
        message="你好",
        llm_model="auto",
        reply_verbosity=None,
    )
    ctx = SessionContext(session_id=req.session_id, user_key=user, tax_year=2024)
    outcome = resolve_chat_turn(req, ctx, apply_composer=False)
    assert req.llm_model == "__off__"
    assert req.reply_verbosity == "brief"
    assert outcome.llm_meta.get("userProfile", {}).get("llmPreference") == "__off__"
    print("PASS C2-5 chat_turn_service applies profile")

    clear_tax_user_profile(user)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
