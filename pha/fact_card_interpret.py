"""M1-P9.1: user-triggered fact-card interpretation via fact_card_interpret profile."""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

from pha.fact_card import _fmt, fact_card_numeric_atoms, load_fact_card
from pha.fact_card_locale import DEFAULT_LOCALE as _DEFAULT_LOCALE, strip_markdown_markers
from pha.fact_card_prefs import load_assessment_prompt, load_fact_card_locale
from pha.harness_plan import FACT_CARD_INTERPRET_USER_MESSAGE
from pha.numerics_manifest import (
    _DATE_CN_MD_RE,
    _DATE_CN_RE,
    _DATE_EN_RE,
    _DATE_ISO_RE,
    _EN_MONTH_NUM,
    _extract_normalized_dates,
    _normalize_cn_date,
    _normalize_en_date,
)

_T1_BLOCK_RE = re.compile(
    r"【参考标准[^】]*】.*?"
    r"[（(]来源[:：][^）)]{2,}[，,][^）)]*?"
    r"(?:请自行查证|请自行核对)[^）)]*?[）)]",
    re.S,
)
_NUM_RE = re.compile(r"\d+(?:\.\d+)?")
_WINDOW_NUM_RE = re.compile(r"^(\d+)d$", re.I)
_ISO_DATE_RE = re.compile(r"\b20\d{2}-\d{2}-\d{2}\b")
_LOCK = threading.Lock()
_INFLIGHT: set[str] = set()
_INTERPRET_PROMPT_REV = "task_outline_v2"


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
) -> str:
    uid = (user_id or "default").strip() or "default"
    raw = (
        f"{uid}|{as_of or ''}|{calendar_day or ''}|"
        f"{card_digest or ''}|"
        f"{(locale or _DEFAULT_LOCALE).strip() or _DEFAULT_LOCALE}|"
        f"{assessment_prompt or ''}|"
        f"{_INTERPRET_PROMPT_REV}"
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


def _strip_t1_blocks(text: str) -> str:
    return _T1_BLOCK_RE.sub(" ", text or "")


def _allowed_card_dates(card: dict[str, Any]) -> set[str]:
    facts = card.get("facts") or {}
    out: set[str] = set()
    for key in ("as_of", "calendar_day"):
        val = str(facts.get(key) or "")[:10]
        if _ISO_DATE_RE.fullmatch(val):
            out.add(val)
    for item in facts.get("metrics") or []:
        if not isinstance(item, dict):
            continue
        for key in ("day", "baseline_earliest"):
            val = str(item.get(key) or "")[:10]
            if _ISO_DATE_RE.fullmatch(val):
                out.add(val)
    return out


def _month_day_hits(month: int, day: int, allowed: set[str]) -> list[str]:
    suffix = f"-{month:02d}-{day:02d}"
    return sorted(iso for iso in allowed if iso.endswith(suffix))


def _guess_month_day_iso(month: int, day: int, allowed: set[str]) -> str:
    hits = _month_day_hits(month, day, allowed)
    if hits:
        return hits[-1]
    year = "2026"
    for iso in sorted(allowed, reverse=True):
        if _ISO_DATE_RE.fullmatch(iso):
            year = iso[:4]
            break
    return f"{year}-{month:02d}-{day:02d}"


def _extract_card_dates(text: str, allowed: set[str]) -> list[str]:
    found = list(_extract_normalized_dates(text))
    for month_s, day_s in _DATE_CN_MD_RE.findall(text or ""):
        found.append(_guess_month_day_iso(int(month_s), int(day_s), allowed))
    for mon, day_s, year in _DATE_EN_RE.findall(text or ""):
        if year:
            continue
        month = _EN_MONTH_NUM.get((mon or "").strip(".").lower())
        if month is None:
            continue
        found.append(_guess_month_day_iso(month, int(day_s), allowed))
    return found


def _blank_dates(text: str, allowed: set[str]) -> str:
    def iso_sub(match: re.Match[str]) -> str:
        return " " if match.group(1) in allowed else match.group(0)

    body = _DATE_ISO_RE.sub(iso_sub, text or "")

    def cn_sub(match: re.Match[str]) -> str:
        iso = _normalize_cn_date(match.group(1), match.group(2), match.group(3))
        return " " if iso in allowed else match.group(0)

    body = _DATE_CN_RE.sub(cn_sub, body)

    def en_sub(match: re.Match[str]) -> str:
        year = match.group(3) or ""
        iso = _normalize_en_date(match.group(1), match.group(2), year)
        if iso and iso in allowed:
            return " "
        if not year:
            month = _EN_MONTH_NUM.get((match.group(1) or "").strip(".").lower())
            if month is not None and _month_day_hits(month, int(match.group(2)), allowed):
                return " "
        return match.group(0)

    body = _DATE_EN_RE.sub(en_sub, body)

    def md_sub(match: re.Match[str]) -> str:
        if _month_day_hits(int(match.group(1)), int(match.group(2)), allowed):
            return " "
        return match.group(0)

    return _DATE_CN_MD_RE.sub(md_sub, body)


def _blank_card_times(text: str, card: dict[str, Any]) -> str:
    body = text
    facts = card.get("facts") or {}
    for item in facts.get("metrics") or []:
        if not isinstance(item, dict):
            continue
        stamp = str(item.get("as_of_time") or "").strip()
        if stamp:
            body = body.replace(stamp, " ")
    return body


def _reference_tokens(card: dict[str, Any]) -> set[str]:
    facts = card.get("facts") or {}
    out: set[str] = set()
    for item in facts.get("metrics") or []:
        if not isinstance(item, dict):
            continue
        ref = item.get("reference") or {}
        if not isinstance(ref, dict):
            continue
        unit = str(ref.get("unit") or item.get("unit") or "")
        for key in ("low", "high"):
            raw = ref.get(key)
            if raw is None:
                continue
            out.add(_fmt(float(raw), unit))
            if abs(float(raw) - round(float(raw))) < 1e-6:
                out.add(str(int(round(float(raw)))))
    return out


def _body_numeric_atoms(card: dict[str, Any]) -> set[str]:
    """Numbers allowed outside T1: facts ∪ baseline ∪ on-card reference range.

    FR-6.3 lets the model cite registry reference bounds that already appear on
    the card. T1 remains the only exit for off-card extras (training zones).
    """
    atoms = fact_card_numeric_atoms(card)
    atoms = {a for a in atoms if not _ISO_DATE_RE.fullmatch(a)}
    atoms |= _reference_tokens(card)
    facts = card.get("facts") or {}
    for item in facts.get("metrics") or []:
        if not isinstance(item, dict):
            continue
        window = str(item.get("baseline_window") or "")
        match = _WINDOW_NUM_RE.fullmatch(window)
        if match:
            atoms.add(match.group(1))
    atoms.update({"7", "12"})
    return atoms


def _audit_interpretation_text(text: str, card: dict[str, Any]) -> list[str]:
    body = _strip_t1_blocks(text)
    allowed_dates = _allowed_card_dates(card)
    violations: list[str] = []
    for day in _extract_card_dates(body, allowed_dates):
        if day not in allowed_dates:
            violations.append(f"unauthorized_date:{day}")
    if violations:
        return violations
    body = _blank_dates(body, allowed_dates)
    body = _blank_card_times(body, card)
    atoms = _body_numeric_atoms(card)
    for token in _NUM_RE.findall(body):
        if token in atoms:
            continue
        violations.append(f"unauthorized_value:{token}")
    return violations


def _numerics_rejected(audit: Optional[dict[str, Any]]) -> bool:
    if not audit:
        return False
    return audit.get("passed") is False


def humanize_interpret_failure(payload: dict[str, Any], *, locale: str = _DEFAULT_LOCALE) -> str:
    from pha.fact_card_copy import card_copy

    err = str(payload.get("error") or "failed")
    if err == "model_unavailable":
        return card_copy(locale, "model_unavailable")
    if err != "audit_rejected":
        return err
    toks: list[str] = []
    for raw in payload.get("violations") or []:
        item = str(raw)
        toks.append(item.split(":", 1)[1] if ":" in item else item)
    if toks:
        shown = "、".join(toks[:8])
        return card_copy(locale, "audit_rejected_toks", toks=shown)
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
    base_meta = {
        "model": model_used,
        "generated_at": generated_at,
        "harness_profile": "fact_card_interpret",
        "numerics_audit": numerics_audit,
        "card_digest": digest,
    }
    if not (text or "").strip():
        return {
            "status": "failed",
            "error": "model_unavailable",
            "message": "empty_answer",
            "text": None,
            **base_meta,
        }
    if _numerics_rejected(numerics_audit):
        violations = [str(v) for v in (numerics_audit or {}).get("violations") or []]
        return {
            "status": "failed",
            "error": "audit_rejected",
            "message": "numerics_audit",
            "text": None,
            "violations": violations,
            **base_meta,
        }
    bad = _audit_interpretation_text(text, card)
    if bad:
        return {
            "status": "failed",
            "error": "audit_rejected",
            "message": "unauthorized_value" if any("value:" in v for v in bad) else "unauthorized_date",
            "text": None,
            "violations": bad,
            **base_meta,
        }
    return {
        "status": "done",
        "error": None,
        "text": strip_markdown_markers(text.strip()),
        **base_meta,
    }


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
    key = interpret_cache_key(
        uid,
        as_of,
        prompt,
        card_digest=digest,
        locale=loc,
        calendar_day=calendar_day,
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
