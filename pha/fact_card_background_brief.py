"""USER_BACKGROUND_BRIEF — non-numeric self-report slot for fact_card_interpret."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import unicodedata
from datetime import date, datetime
from typing import Any

from pha.chat_background import is_system_tag_message, list_background_notes
from pha.fact_card_copy import card_copy
from pha.harness_plan import FACT_CARD_INTERPRET_USER_MESSAGE
from pha.numerics_manifest import leftover_s_level_numeric_tokens

logger = logging.getLogger(__name__)

ALLOWED_CATEGORIES = frozenset(
    {"supplement", "medication", "sleep_lifestyle", "symptom", "general"},
)
CATEGORY_ORDER = ("supplement", "medication", "sleep_lifestyle", "symptom", "general")
DEFAULT_QUOTA = {
    "supplement": 6,
    "medication": 4,
    "sleep_lifestyle": 3,
    "symptom": 3,
    "general": 2,
}

# Same family as scripts/pha_memory_hygiene.py LEGACY_SYNTHETIC_USER_MESSAGES.
_LEGACY_SYNTHETIC_PREFIXES = (
    "请根据系统提供的当日事实卡数字与基线摘要，写一段简短的健康教育解读。",
)

_HYPHEN_ID_RE = re.compile(r"\b[A-Za-z][A-Za-z0-9]*-\d+\b")
# Letter-then-digit identifiers only (D3 / B12 / CoQ10 / SpO2). Digit-leading
# tokens like 400mg are doses, not identifiers.
_IDENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\d[A-Za-z0-9_]*")
_TIME_RE = re.compile(r"\b\d{1,2}:\d{2}(?::\d{2})?\b")
_ISO_DATE_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
_CN_YMD_RE = re.compile(r"\d{4}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日")
_CN_MD_RE = re.compile(r"\d{1,2}\s*月\s*\d{1,2}\s*日")
_EN_MD_RE = re.compile(
    r"\b(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
    r"Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|"
    r"Dec(?:ember)?)\.?\s+\d{1,2}(?:,\s*\d{4})?\b",
    re.I,
)
_UNIT_RE = (
    r"(?:mg|mcg|μg|ug|IU|ml|mL|kg|kcal|bpm|ms|g|粒|片|次|小时|h|点|%)"
)
_ARABIC_DOSE_RE = re.compile(rf"\d+(?:[.,]\d+)?\s*{_UNIT_RE}", re.I)
_ARABIC_NUM_RE = re.compile(r"\d+(?:[.,]\d+)?")
_CN_DOSE_RE = re.compile(r"[零一二三四五六七八九十百千万两半几]+(?:多)?(?:粒|片|次|小时)")
_PUNCT_RE = re.compile(r"[\s\W_]+", re.UNICODE)


def background_brief_enabled() -> bool:
    return (os.environ.get("PHA_FACT_CARD_BG_BRIEF") or "1").strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )


def _quota() -> dict[str, int]:
    raw = (os.environ.get("PHA_FACT_CARD_BG_BRIEF_QUOTA") or "").strip()
    out = dict(DEFAULT_QUOTA)
    if not raw:
        return out
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return out
    if not isinstance(parsed, dict):
        return out
    for key, val in parsed.items():
        if key in out:
            try:
                out[key] = max(0, int(val))
            except (TypeError, ValueError):
                continue
    return out


def _max_chars(locale: str) -> int:
    raw = (os.environ.get("PHA_FACT_CARD_BG_BRIEF_MAX_CHARS") or "").strip()
    if raw.isdigit():
        return max(120, int(raw))
    loc = (locale or "en").strip().lower()
    return 600 if loc.startswith("zh") else 900


def _is_synthetic_content(text: str) -> bool:
    body = (text or "").strip()
    if not body:
        return False
    prefixes = [FACT_CARD_INTERPRET_USER_MESSAGE.strip(), *_LEGACY_SYNTHETIC_PREFIXES]
    for prefix in prefixes:
        if not prefix:
            continue
        if body == prefix or body.startswith(prefix) or body.startswith(prefix[:40]):
            return True
    return False


def _norm_dedupe_key(text: str) -> str:
    folded = unicodedata.normalize("NFKC", text or "").casefold()
    return _PUNCT_RE.sub("", folded)


def _parse_day(raw: str) -> date | None:
    text = (raw or "").strip()[:10]
    if not text:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def _relative_key(note_day: date | None, as_of: date | None) -> str:
    if note_day is None or as_of is None:
        return "bg_brief_rel_earlier"
    delta = (as_of - note_day).days
    if delta <= 7:
        return "bg_brief_rel_week"
    if delta <= 31:
        return "bg_brief_rel_month"
    return "bg_brief_rel_earlier"


def _placeholder(idx: int) -> str:
    """Letter-only token so later digit stripping cannot eat the marker."""
    n = idx
    letters = []
    while n > 0:
        n, rem = divmod(n - 1, 26)
        letters.append(chr(65 + rem))
    return "«PH" + "".join(reversed(letters)) + "»"


def _protect_identifiers(text: str) -> tuple[str, list[str]]:
    found: list[str] = []

    def _protect(pattern: re.Pattern[str], src: str) -> str:
        def _repl(match: re.Match[str]) -> str:
            found.append(match.group(0))
            return _placeholder(len(found))

        return pattern.sub(_repl, src)

    out = _protect(_HYPHEN_ID_RE, text or "")
    out = _protect(_IDENT_RE, out)
    return out, found


def _restore_identifiers(text: str, found: list[str]) -> str:
    out = text
    for idx in range(len(found), 0, -1):
        out = out.replace(_placeholder(idx), found[idx - 1])
    return out


def _strip_dates_and_times(text: str) -> str:
    out = _ISO_DATE_RE.sub(" ", text or "")
    out = _CN_YMD_RE.sub(" ", out)
    out = _EN_MD_RE.sub(" ", out)
    out = _CN_MD_RE.sub(" ", out)
    out = _TIME_RE.sub(" ", out)
    return out


def _denumerize_line(text: str, *, locale: str) -> str:
    omitted = card_copy(locale, "bg_brief_omitted")
    protected, ids = _protect_identifiers(text)
    protected = _strip_dates_and_times(protected)
    protected = _ARABIC_DOSE_RE.sub(omitted, protected)
    protected = _CN_DOSE_RE.sub(omitted, protected)
    protected = _ARABIC_NUM_RE.sub(omitted, protected)
    protected = re.sub(rf"(?:{re.escape(omitted)}\s*)+", omitted + " ", protected)
    protected = re.sub(r"[ \t]{2,}", " ", protected)
    protected = re.sub(r"\s+([，。,.;；])", r"\1", protected)
    return _restore_identifiers(protected, ids).strip()


def _truncate_lines(lines: list[str], limit: int) -> list[str]:
    kept: list[str] = []
    used = 0
    for line in lines:
        extra = len(line) + (1 if kept else 0)
        if used + extra > limit:
            break
        kept.append(line)
        used += extra
    return kept


def build_fact_card_background_brief(
    user_id: str,
    *,
    locale: str = "en",
    as_of: str | None = None,
) -> tuple[str, dict[str, Any]]:
    """Return (slot body, meta). Empty body when flag off or no usable notes."""
    empty_meta = {"notes_used": 0, "lines_dropped": 0, "digest": "", "brief_source": "live_notes"}
    if not background_brief_enabled():
        return "", empty_meta
    uid = (user_id or "default").strip() or "default"
    loc = (locale or "en").strip() or "en"
    as_of_day = _parse_day(as_of)
    notes = list_background_notes(uid, limit=200)
    filtered: list[dict[str, Any]] = []
    for row in notes:
        cat = str(row.get("category") or "").strip()
        content = str(row.get("content") or "").strip()
        if cat not in ALLOWED_CATEGORIES:
            continue
        if is_system_tag_message(content) or _is_synthetic_content(content):
            continue
        if not content:
            continue
        filtered.append(row)

    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for row in filtered:
        key = _norm_dedupe_key(str(row.get("content") or ""))
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(row)

    quota = _quota()
    per_cat: dict[str, list[dict[str, Any]]] = {c: [] for c in CATEGORY_ORDER}
    for row in unique:
        cat = str(row.get("category") or "")
        bucket = per_cat.get(cat)
        if bucket is None:
            continue
        if len(bucket) >= quota.get(cat, 0):
            continue
        bucket.append(row)

    dropped = 0
    body_lines: list[str] = []
    used = 0
    for cat in CATEGORY_ORDER:
        rows = per_cat.get(cat) or []
        if not rows:
            continue
        section: list[str] = [card_copy(loc, f"bg_brief_cat_{cat}")]
        kept_in_section = 0
        for row in rows:
            cleaned = _denumerize_line(str(row.get("content") or ""), locale=loc)
            if not cleaned:
                dropped += 1
                continue
            leftover = leftover_s_level_numeric_tokens(cleaned)
            if leftover:
                dropped += 1
                logger.info("bg_brief_line_dropped leftover=%s", leftover)
                continue
            note_day = _parse_day(str(row.get("note_date") or ""))
            rel = card_copy(loc, _relative_key(note_day, as_of_day))
            section.append(f"- {cleaned}（{rel}）" if loc.lower().startswith("zh") else f"- {cleaned} ({rel})")
            kept_in_section += 1
            used += 1
        if kept_in_section:
            body_lines.extend(section)

    body_lines = _truncate_lines(body_lines, _max_chars(loc))
    while body_lines and not body_lines[-1].startswith("- "):
        body_lines.pop()
    used = sum(1 for line in body_lines if line.startswith("- "))
    if not body_lines:
        return "", {**empty_meta, "lines_dropped": dropped}

    title = card_copy(loc, "bg_brief_title")
    lead = card_copy(loc, "bg_brief_lead")
    header = f"【{title}】\n{lead}"
    body = "\n".join(body_lines)
    digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
    text = f"{header}\n{body}"
    return text, {
        "notes_used": used,
        "lines_dropped": dropped,
        "digest": digest,
        "brief_source": "live_notes",
    }


def background_brief_digest(
    user_id: str,
    *,
    locale: str = "en",
    as_of: str | None = None,
) -> str:
    if not background_brief_enabled():
        return ""
    _text, meta = build_fact_card_background_brief(user_id, locale=locale, as_of=as_of)
    return str(meta.get("digest") or "")
