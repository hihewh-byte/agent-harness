"""M1-P9.1/P9.4: user-triggered fact-card interpretation via fact_card_interpret profile."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

from pha.fact_card import load_fact_card
from pha.fact_card_locale import DEFAULT_LOCALE as _DEFAULT_LOCALE, strip_markdown_markers
from pha.fact_card_prefs import load_assessment_prompt, load_fact_card_locale
from pha.harness_plan import FACT_CARD_INTERPRET_USER_MESSAGE, fact_card_interpret_task_text
from pha.numerics_manifest import (
    FACT_CARD_AUDIT_POLICY_REV,
    audit_response_numerics,
    build_fact_card_numerics_manifest,
)

_LOCK = threading.Lock()
_INFLIGHT: set[str] = set()


def _interpret_prompt_rev() -> str:
    from pha.harness_plan import PHA_FACT_CARD_SOUL_MINIMAL

    blob = (
        f"{fact_card_interpret_task_text('en')}|"
        f"{FACT_CARD_AUDIT_POLICY_REV}|"
        f"{PHA_FACT_CARD_SOUL_MINIMAL}"
    )
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:12]


def interpret_dir() -> Path:
    override = (os.environ.get("PHA_FACT_CARD_INTERPRET_DIR") or "").strip()
    if override:
        return Path(override)
    return Path(__file__).resolve().parent.parent / "data" / "fact_card_interpret"


def fact_card_digest(card: dict[str, Any]) -> str:
    facts = card.get("facts") or {}
    rows = []
    for item in facts.get("metrics") or []:
        if not isinstance(item, dict):
            continue
        rows.append(
            {
                "id": item.get("metric"),
                "value": item.get("value"),
                "window": item.get("baseline_window"),
                "n": item.get("baseline_n"),
            }
        )
    blob = json.dumps(rows, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def interpret_cache_key(
    user_id: str,
    as_of: Optional[str],
    assessment_prompt: str,
    *,
    card_digest: str = "",
    locale: str = _DEFAULT_LOCALE,
    calendar_day: str = "",
    bg_brief_digest: str = "",
) -> str:
    uid = (user_id or "default").strip() or "default"
    raw = (
        f"{uid}|{as_of or ''}|{calendar_day or ''}|"
        f"{card_digest or ''}|"
        f"{(locale or _DEFAULT_LOCALE).strip() or _DEFAULT_LOCALE}|"
        f"{assessment_prompt or ''}|"
        f"{bg_brief_digest or ''}|"
        f"{_interpret_prompt_rev()}"
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _cache_path(key: str) -> Path:
    return interpret_dir() / f"{key}.json"


def _read_cache(key: str) -> Optional[dict[str, Any]]:
    path = _cache_path(key)
    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return raw if isinstance(raw, dict) else None


def _write_cache(key: str, payload: dict[str, Any]) -> None:
    path = _cache_path(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    fd, tmp = tempfile.mkstemp(prefix="interpret.", suffix=".json", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(body)
        os.replace(tmp, path)
    except Exception:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def _default_model() -> str:
    return (os.environ.get("OLLAMA_MODEL") or "").strip()


def build_fact_card_context_block(card: dict[str, Any]) -> str:
    facts = card.get("facts") or {}
    assessment = card.get("assessment") or {}
    summary = assessment.get("summary") or {}
    slim = {
        "as_of": facts.get("as_of"),
        "calendar_day": facts.get("calendar_day"),
        "stale": facts.get("stale"),
        "metrics": facts.get("metrics"),
        "summary": summary.get("text") if isinstance(summary, dict) else summary,
        "advice": assessment.get("advice"),
    }
    return (
        "以下为唯一可引用数字与日期。大纲是 USER_ASSESSMENT_PROMPT，不是 summary/advice。\n"
        + json.dumps(slim, ensure_ascii=False, indent=2)
    )


def _audit_interpretation_text(
    text: str,
    card: dict[str, Any],
    *,
    user_id: str = "default",
) -> dict[str, Any]:
    """Single audit: harness fact_card strategy on the day's card manifest."""
    manifest = build_fact_card_numerics_manifest(card, user_id=user_id)
    return audit_response_numerics(text or "", manifest)


def _numerics_rejected(audit: Optional[dict[str, Any]]) -> bool:
    if not audit:
        return False
    return audit.get("passed") is False


def humanize_interpret_failure(payload: dict[str, Any], *, locale: str = _DEFAULT_LOCALE) -> str:
    from pha.fact_card_copy import card_copy, format_audit_violations

    err = str(payload.get("error") or "failed")
    if err == "model_unavailable":
        return card_copy(locale, "model_unavailable")
    if err != "audit_rejected":
        return err
    summary = format_audit_violations(payload.get("violations") or [], locale=locale)
    if summary:
        return card_copy(locale, "audit_rejected_toks", toks=summary)
    return card_copy(locale, "audit_rejected")


StreamFn = Callable[..., Any]


def run_interpretation(
    *,
    user_id: str,
    card: dict[str, Any],
    assessment_prompt: str,
    model: str,
    stream_fn: Optional[StreamFn] = None,
    locale: str = _DEFAULT_LOCALE,
) -> dict[str, Any]:
    """Synchronously generate one interpretation; used by worker and selfcheck."""
    from pha.chat_service import stream_pha_chat_events

    stream = stream_fn or stream_pha_chat_events
    digest = fact_card_digest(card)
    text = ""
    model_used = model
    numerics_audit: Optional[dict[str, Any]] = None
    try:
        for raw in stream(
            user_id=user_id,
            user_message=FACT_CARD_INTERPRET_USER_MESSAGE,
            model=model,
            session_id=None,
            profile_override="fact_card_interpret",
            fact_card_payload=card,
            fact_card_context=build_fact_card_context_block(card),
            user_assessment_prompt=assessment_prompt or "",
            response_locale=locale,
        ):
            try:
                evt = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if not isinstance(evt, dict):
                continue
            if evt.get("event") == "error":
                return {
                    "status": "failed",
                    "error": "model_unavailable",
                    "message": str(evt.get("message") or "error"),
                    "text": None,
                    "model": model_used,
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                    "harness_profile": "fact_card_interpret",
                    "card_digest": digest,
                }
            if evt.get("event") == "done":
                model_used = str(evt.get("model") or model_used)
                answer = evt.get("answer") or {}
                text = str(answer.get("answer_text") or "")
                numerics_audit = evt.get("numerics_audit")
    except Exception as exc:
        return {
            "status": "failed",
            "error": "model_unavailable",
            "message": f"{type(exc).__name__}: {exc}",
            "text": None,
            "model": model_used,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "harness_profile": "fact_card_interpret",
            "card_digest": digest,
        }
    generated_at = datetime.now(timezone.utc).isoformat()
    from pha.fact_card_background_brief import build_fact_card_background_brief

    _brief_text, brief_meta = build_fact_card_background_brief(
        user_id,
        locale=locale,
        as_of=str((card.get("facts") or {}).get("as_of") or ""),
    )
    notes_used = int(brief_meta.get("notes_used") or 0)
    base_meta = {
        "model": model_used,
        "generated_at": generated_at,
        "harness_profile": "fact_card_interpret",
        "numerics_audit": numerics_audit,
        "card_digest": digest,
        "background_used": notes_used > 0,
        "background_notes_used": notes_used,
    }
    if not (text or "").strip():
        return {
            "status": "failed",
            "error": "model_unavailable",
            "message": "empty_answer",
            "text": None,
            **base_meta,
        }
    # Single source of truth: always re-audit with the card manifest (fact_card policy).
    # Stream/harness audit may be mocked in selfcheck; card audit must still run.
    audit = _audit_interpretation_text(text, card, user_id=user_id)
    base_meta["numerics_audit"] = audit
    if _numerics_rejected(audit):
        violations = [str(v) for v in (audit or {}).get("violations") or []]
        return {
            "status": "failed",
            "error": "audit_rejected",
            "message": "numerics_audit",
            "text": None,
            "rejected_text": text,
            "violations": violations,
            **base_meta,
        }
    return {
        "status": "done",
        "error": None,
        "text": strip_markdown_markers(text.strip()),
        **base_meta,
    }


def _bg_brief_digest_for(user_id: str, card: dict[str, Any], locale: str) -> str:
    from pha.fact_card_background_brief import background_brief_digest

    as_of = str((card.get("facts") or {}).get("as_of") or "")
    return background_brief_digest(user_id, locale=locale, as_of=as_of)


def current_interpret_key(
    user_id: str,
    card: Optional[dict[str, Any]] = None,
    *,
    locale: str = _DEFAULT_LOCALE,
) -> str:
    uid = (user_id or "default").strip() or "default"
    card = card or load_fact_card(uid)
    as_of = (card.get("facts") or {}).get("as_of")
    calendar_day = str((card.get("facts") or {}).get("calendar_day") or "")
    prompt = load_assessment_prompt(uid)
    return interpret_cache_key(
        uid,
        as_of,
        prompt,
        card_digest=fact_card_digest(card),
        locale=locale,
        calendar_day=calendar_day,
        bg_brief_digest=_bg_brief_digest_for(uid, card, locale),
    )


def load_interpretation_for_user(
    user_id: str,
    *,
    card: Optional[dict[str, Any]] = None,
    locale: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    loc = locale or load_fact_card_locale(user_id)
    key = current_interpret_key(user_id, card, locale=loc)
    got = _read_cache(key)
    if got is None:
        return None
    return {**got, "key": key}


def start_interpretation(
    user_id: str,
    *,
    card: Optional[dict[str, Any]] = None,
    stream_fn: Optional[StreamFn] = None,
    locale: Optional[str] = None,
) -> dict[str, Any]:
    """POST handler: return cache hit or enqueue pending generation."""
    uid = (user_id or "default").strip() or "default"
    card = card or load_fact_card(uid)
    loc = locale or load_fact_card_locale(uid)
    prompt = load_assessment_prompt(uid)
    as_of = (card.get("facts") or {}).get("as_of")
    calendar_day = str((card.get("facts") or {}).get("calendar_day") or "")
    digest = fact_card_digest(card)
    from pha.fact_card_background_brief import build_fact_card_background_brief

    _brief_text, brief_meta = build_fact_card_background_brief(
        uid, locale=loc, as_of=str(as_of or "")
    )
    bg_digest = str(brief_meta.get("digest") or "")
    key = interpret_cache_key(
        uid,
        as_of,
        prompt,
        card_digest=digest,
        locale=loc,
        calendar_day=calendar_day,
        bg_brief_digest=bg_digest,
    )
    existing = _read_cache(key)
    if existing and existing.get("status") in {"pending", "done"}:
        return {**existing, "key": key, "started": False}

    model = _default_model()
    if not model:
        payload = {
            "status": "failed",
            "error": "model_unavailable",
            "message": "OLLAMA_MODEL unset",
            "text": None,
            "model": None,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "user_id": uid,
            "as_of": as_of,
            "harness_profile": "fact_card_interpret",
            "card_digest": digest,
        }
        _write_cache(key, payload)
        return {**payload, "key": key, "started": False}

    pending = {
        "status": "pending",
        "error": None,
        "text": None,
        "model": model,
        "generated_at": None,
        "user_id": uid,
        "as_of": as_of,
        "harness_profile": "fact_card_interpret",
        "card_digest": digest,
        "background_used": int(brief_meta.get("notes_used") or 0) > 0,
        "background_notes_used": int(brief_meta.get("notes_used") or 0),
    }
    with _LOCK:
        if key in _INFLIGHT:
            existing = _read_cache(key) or pending
            return {**existing, "key": key, "started": False}
        _INFLIGHT.add(key)
    _write_cache(key, pending)

    def worker() -> None:
        try:
            result = run_interpretation(
                user_id=uid,
                card=card,
                assessment_prompt=prompt,
                model=model,
                stream_fn=stream_fn,
                locale=loc,
            )
            result["user_id"] = uid
            result["as_of"] = as_of
            _write_cache(key, result)
        finally:
            with _LOCK:
                _INFLIGHT.discard(key)

    threading.Thread(target=worker, name=f"fact-card-interpret-{key[:8]}", daemon=True).start()
    return {**pending, "key": key, "started": True}


__all__ = [
    "build_fact_card_context_block",
    "current_interpret_key",
    "fact_card_digest",
    "humanize_interpret_failure",
    "interpret_cache_key",
    "interpret_dir",
    "load_interpretation_for_user",
    "run_interpretation",
    "start_interpretation",
]
