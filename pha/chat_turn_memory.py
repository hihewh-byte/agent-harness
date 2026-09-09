"""Turn-scoped chat-memory writes, gated by harness ``memory_write_policy``.

Interpret / other ``none`` profiles reuse the chat orchestrator for SSE + audit
but must not create sessions, messages, background notes, or focus rows.
Callers decide via ``profile_writes_chat_memory`` — never by profile name.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from pha.chat_background import maybe_capture_chat_background
from pha.chat_storage import (
    append_message,
    create_session,
    get_session,
    maybe_set_title_from_first_message,
)


@dataclass
class NullChatMessage:
    """Stand-in when the turn is not allowed to persist chat rows."""

    id: Optional[int] = None
    session_id: str = ""
    role: str = ""
    content: str = ""


class TurnMemorySink:
    """Session + message persistence for one chat turn."""

    def __init__(
        self,
        *,
        writes: bool,
        user_id: str,
        session_id: Optional[str] = None,
    ) -> None:
        self.writes = bool(writes)
        self.uid = (user_id or "default").strip() or "default"
        self.sid: Optional[str] = (session_id or "").strip() or None if self.writes else None
        self.session_error: Optional[str] = None

    def ensure_session(self) -> bool:
        """Bind or create a session when writes are allowed.

        Returns False when the caller supplied a missing session id (chat path).
        """
        if not self.writes:
            self.sid = None
            return True
        if self.sid:
            if not get_session(self.sid, self.uid):
                self.session_error = "会话不存在"
                return False
            return True
        sess = create_session(self.uid)
        self.sid = sess.id
        return True

    def append(
        self,
        role: str,
        content: str,
        **kwargs: Any,
    ) -> Any:
        if not self.writes or not self.sid:
            return NullChatMessage(role=role, content=content)
        return append_message(self.sid, role, content, **kwargs)

    def set_title_from_first_message(self, msg: str) -> None:
        if self.writes and self.sid:
            maybe_set_title_from_first_message(self.sid, msg)

    def on_request_start(self, msg: str) -> dict[str, Any]:
        if not self.writes:
            return {}
        from pha.dynamic_slot_registry import on_request_start

        return on_request_start(self.uid, msg)

    def capture_background(
        self,
        msg: str,
        *,
        source_message_id: Optional[int] = None,
    ) -> tuple[bool, Optional[str]]:
        if not self.writes:
            return False, None
        return maybe_capture_chat_background(
            self.uid,
            msg,
            session_id=self.sid or "",
            source_message_id=source_message_id,
        )

    def on_background_captured(self, msg: str) -> None:
        if not self.writes:
            return
        from pha.dynamic_slot_registry import on_background_captured

        on_background_captured(self.uid, msg)

    def record_health_turn_focus(self, **kwargs: Any) -> None:
        if not self.writes or not self.sid:
            return
        from pha.health_session_focus_store import record_health_turn_focus

        record_health_turn_focus(self.sid, **kwargs)

    def get_session_turn_focus(self) -> Any:
        if not self.writes or not self.sid:
            return None
        from pha.session_turn_focus import get_session_turn_focus

        return get_session_turn_focus(self.sid)

    def revive_session_turn_focus(self, raw_user_msg: str) -> Any:
        if not self.writes or not self.sid:
            return None
        from pha.session_turn_focus import revive_session_turn_focus_for_message

        return revive_session_turn_focus_for_message(self.sid, raw_user_msg)

    def save_session_turn_focus(self, **kwargs: Any) -> None:
        if not self.writes or not self.sid:
            return
        from pha.session_turn_focus import save_session_turn_focus

        save_session_turn_focus(self.sid, **kwargs)

    def consume_session_turn_focus(self) -> Any:
        if not self.writes or not self.sid:
            return None
        from pha.session_turn_focus import consume_session_turn_focus

        return consume_session_turn_focus(self.sid)

    def clear_session_turn_focus(self) -> None:
        if not self.writes or not self.sid:
            return
        from pha.session_turn_focus import clear_session_turn_focus

        clear_session_turn_focus(self.sid)

    def load_health_session_focus(self) -> Any:
        if not self.writes or not self.sid:
            return None
        from pha.health_session_focus_store import load_health_session_focus

        return load_health_session_focus(self.sid)

    def revive_health_session_focus(self, raw_user_msg: str) -> Any:
        if not self.writes or not self.sid:
            return None
        from pha.health_session_focus_store import revive_health_session_focus

        return revive_health_session_focus(self.sid, raw_user_msg)


__all__ = [
    "NullChatMessage",
    "TurnMemorySink",
]
