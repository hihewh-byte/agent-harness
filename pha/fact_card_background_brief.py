"""USER_BACKGROUND_BRIEF — non-numeric self-report slot for fact_card_interpret."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import unicodedata
from dataclasses import asdict, dataclass
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
_SENTENCE_SPLIT_RE = re.compile(r"[。！？；;]+")
_MIN_PORTRAIT_CHUNK = 8


@dataclass(frozen=True)
class BackgroundStatementRow:
    """Compiled non-numeric self-report. Never a T0 fact (no value/unit/metric_id)."""

    category: str
    text: str
    rel_key: str
    prov_type: str = "user_statement"

    def as_dict(self) -> dict[str, str]:
        return asdict(self)


def background_brief_enabled() -> bool:
    return (os.environ.get("PHA_FACT_CARD_BG_BRIEF") or "1").strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )


def note_hits_capture_negative(content: str) -> bool:
    """Same capture-negative table as P18 write-side (questions / list-imperatives)."""
    from pha.schema_intent_router import schema_hits_capture_negative
    from pha.universal_catalog_manager import get_catalog_manager

    schema = get_catalog_manager().get_asset("supplement_bg")
    return schema_hits_capture_negative(content, schema)


def _schema_background_brief() -> dict[str, Any]:
    try:
        from pha.universal_catalog_manager import get_catalog_manager

        doc = get_catalog_manager().get_asset("supplement_bg") or {}
        block = doc.get("background_brief")
        return block if isinstance(block, dict) else {}
    except Exception:
        return {}


def _parse_cap_pipe(raw: str) -> dict[str, int]:
    out: dict[str, int] = {}
    for part in (raw or "").split("|"):
        part = part.strip()
        if not part or ":" not in part:
            continue
        key, _, val = part.partition(":")
        key = key.strip()
        if key not in ALLOWED_CATEGORIES:
            continue
        try:
            out[key] = max(0, int(val.strip()))
        except (TypeError, ValueError):
            continue
    return out


def _caps_from_schema(key: str) -> dict[str, int]:
    block = _schema_background_brief()
    raw = block.get(key)
    if not isinstance(raw, dict):
        return {}
    out: dict[str, int] = {}
    for cat, val in raw.items():
        if cat not in ALLOWED_CATEGORIES:
            continue
        try:
            out[cat] = max(0, int(val))
        except (TypeError, ValueError):
            continue
    return out


def _note_caps(*, locale: str) -> dict[str, int]:
    """How many original notes to consider per category (copy/schema; env override)."""
    out = _caps_from_schema("note_caps")
    if not out:
        out = _parse_cap_pipe(card_copy(locale, "bg_brief_note_caps"))
    raw = (os.environ.get("PHA_FACT_CARD_BG_BRIEF_QUOTA") or "").strip()
    if not raw:
        return out
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return out
    if not isinstance(parsed, dict):
        return out
    for key, val in parsed.items():
        if key not in ALLOWED_CATEGORIES:
            continue
        try:
            out[key] = max(0, int(val))
        except (TypeError, ValueError):
            continue
    return out


def _row_caps(*, locale: str) -> dict[str, int]:
    """How many compiled one-item rows to keep per category (copy/schema only)."""
    out = _caps_from_schema("row_caps")
    if out:
        return out
    return _parse_cap_pipe(card_copy(locale, "bg_brief_row_caps"))


def _item_seps(*, locale: str) -> list[str]:
    block = _schema_background_brief()
    raw = block.get("item_seps")
    if isinstance(raw, list) and raw:
        return [str(s) for s in raw if str(s)]
    return [
        part
        for part in card_copy(locale, "bg_brief_item_seps").split("|")
        if part != ""
    ]


def is_background_text_stub(text: str, *, locale: str) -> bool:
    """True when a denumerized fragment has no usable self-report content.

    Same empty-after-denumerize / stub-mark rule as v1.20 lineage (no header
    keyword table).
    """
    body = (text or "").strip().lstrip("-–—• ").strip()
    if not body:
        return True
    omitted = card_copy(locale, "bg_brief_omitted")
    compact = body.replace(omitted, "")
    compact = re.sub(r"[\s:：\-–—/·,，.。pct]+", "", compact, flags=re.I)
    if len(compact) < 4:
        return True
    marks = card_copy(locale, "bg_lineage_stub_marks")
    for token in (marks or "").split("|"):
        tok = token.strip()
        if tok and tok in body:
            return True
    return False


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


def _table_headers(*, locale: str) -> list[str]:
    block = _schema_background_brief()
    raw = block.get("table_headers")
    if isinstance(raw, list) and raw:
        return [str(s).strip() for s in raw if str(s).strip()]
    return [
        part.strip()
        for part in card_copy(locale, "bg_brief_table_headers").split("|")
        if part.strip()
    ]


def _note_structure_score(content: str) -> int:
    """Prefer tab-structured self-reports over space-collapsed duplicates."""
    text = content or ""
    return text.count("\t") * 10 + text.count("\n")


def expand_background_note_units(content: str, *, locale: str) -> list[str]:
    """Split a note into schedule+items units.

    Tab-separated regimen tables use columns from copy/schema headers; only the
    schedule column and the items column are kept (logic column dropped). Plain
    notes stay a single unit. No drug-name tables.
    """
    text = (content or "").strip()
    if not text:
        return []
    if "\t" not in text:
        return [text]
    headers = {h.casefold() for h in _table_headers(locale=locale)}
    units: list[str] = []
    for line in text.splitlines():
        raw = line.strip()
        if not raw:
            continue
        if "\t" not in raw:
            # Leading prose before the table.
            if raw.casefold() in headers:
                continue
            units.append(raw)
            continue
        cols = [c.strip() for c in raw.split("\t")]
        if not cols:
            continue
        if any(c.casefold() in headers for c in cols if c):
            continue
        when = cols[0] if cols else ""
        # Items column: prefer 3rd column when present (时间/项目/具体内容/…).
        items = cols[2] if len(cols) >= 3 else (cols[1] if len(cols) > 1 else "")
        if not items:
            continue
        unit = f"{when} {items}".strip() if when else items
        if unit:
            units.append(unit)
    return units or [text]


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


def denumerize_background_line(text: str, *, locale: str) -> str:
    """Public alias used by CHB lineage / §Background (same denumerizer as P14)."""
    return _denumerize_line(text, locale=locale)


def split_background_portrait_chunks(text: str, *, locale: str) -> list[str]:
    """Split a denumerized self-report into short one-item bullets.

    Schedule marks and item separators live in ``fact_card_copy`` /
    ``supplement_bg`` schema — no drug-name tables. When schedule marks are
    present, unmarked preamble (table headers) is dropped.
    """
    cleaned = re.sub(r"[ \t]{2,}", " ", (text or "").strip())
    if not cleaned:
        return []
    marks = [
        part.strip()
        for part in card_copy(locale, "bg_brief_split_marks").split("|")
        if part.strip()
    ]
    seps = _item_seps(locale=locale)
    glue = card_copy(locale, "bg_brief_item_glue") or " · "
    pieces = _split_keep_schedule_marks(cleaned, marks)
    out: list[str] = []
    for piece in pieces:
        for chunk in _SENTENCE_SPLIT_RE.split(piece):
            chunk = re.sub(r"[ \t]{2,}", " ", chunk).strip(" ，,")
            if not _keep_portrait_chunk(chunk, marks):
                continue
            for item in _split_item_seps(chunk, seps=seps, marks=marks, glue=glue):
                item = re.sub(r"[ \t]{2,}", " ", item).strip(" ，,")
                if _keep_item_chunk(item, marks=marks, glue=glue):
                    out.append(item)
    return out or [cleaned]


def _keep_portrait_chunk(chunk: str, marks: list[str]) -> bool:
    if not chunk:
        return False
    for mark in marks:
        if chunk.startswith(mark):
            return bool(chunk[len(mark) :].strip())
    return len(chunk) >= _MIN_PORTRAIT_CHUNK


def _keep_item_chunk(chunk: str, *, marks: list[str], glue: str) -> bool:
    """One-item rows may be short (e.g. a single name); do not require sentence length."""
    if not chunk:
        return False
    for mark in marks:
        prefixed = f"{mark}{glue}"
        if chunk.startswith(prefixed):
            return bool(chunk[len(prefixed) :].strip())
        if chunk.startswith(mark):
            return bool(chunk[len(mark) :].strip())
    compact = re.sub(r"[\s·.•\-–—]+", "", chunk)
    return len(compact) >= 1


def _split_item_seps(
    text: str,
    *,
    seps: list[str],
    marks: list[str],
    glue: str,
) -> list[str]:
    if not text:
        return []

    def _with_mark_glue(raw: str) -> str:
        for mark in sorted(marks, key=len, reverse=True):
            if raw.startswith(f"{mark}{glue}"):
                return raw
            if raw.startswith(mark):
                rest = raw[len(mark) :].lstrip(" ：:·•\-–—")
                if rest:
                    return f"{mark}{glue}{rest}"
        return raw

    if not seps or not any(sep in text for sep in seps):
        return [_with_mark_glue(text)]
    prefix = ""
    rest = text
    for mark in sorted(marks, key=len, reverse=True):
        if rest.startswith(mark):
            prefix = mark
            rest = rest[len(mark) :].lstrip(" ：:·•\-–—")
            break
    alts = [re.escape(sep) for sep in sorted(seps, key=len, reverse=True)]
    bits = re.split("|".join(alts), rest)
    items = [b.strip(" ，,") for b in bits if b and b.strip(" ，,")]
    if not items:
        return [_with_mark_glue(text)]
    if prefix:
        return [f"{prefix}{glue}{item}" for item in items]
    return items


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


def _split_keep_schedule_marks(text: str, marks: list[str]) -> list[str]:
    if not marks or not any(mark in text for mark in marks):
        return [text]
    alts: list[str] = []
    for mark in sorted(marks, key=len, reverse=True):
        esc = re.escape(mark)
        if mark.isascii() and mark.isalpha():
            alts.append(rf"\b{esc}\b")
        else:
            alts.append(esc)
    bits = re.split(f"({'|'.join(alts)})", text)
    chunks: list[str] = []
    # Drop unmarked preamble when schedule marks are present (table headers).
    idx = 1
    while idx < len(bits):
        mark = bits[idx]
        rest = bits[idx + 1] if idx + 1 < len(bits) else ""
        piece = f"{mark}{rest}".strip()
        if piece:
            chunks.append(piece)
        idx += 2
    return chunks or [text]


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


def compile_background_statement_rows(
    user_id: str,
    *,
    locale: str = "en",
    as_of: str | None = None,
) -> tuple[list[BackgroundStatementRow], dict[str, Any]]:
    """Compile notes into denumerized statement rows. Quota is on original notes."""
    empty_meta = {
        "notes_used": 0,
        "lines_dropped": 0,
        "digest": "",
        "brief_source": "live_notes",
    }
    if not background_brief_enabled():
        return [], empty_meta
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
        if note_hits_capture_negative(content):
            continue
        filtered.append(row)

    seen: dict[str, dict[str, Any]] = {}
    unique: list[dict[str, Any]] = []
    for row in filtered:
        key = _norm_dedupe_key(str(row.get("content") or ""))
        if not key:
            continue
        prev = seen.get(key)
        if prev is None:
            seen[key] = row
            unique.append(row)
            continue
        # Same denumerize-key: keep the richer (tab-structured) variant.
        if _note_structure_score(str(row.get("content") or "")) > _note_structure_score(
            str(prev.get("content") or "")
        ):
            idx = unique.index(prev)
            unique[idx] = row
            seen[key] = row

    quota = _note_caps(locale=loc)
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
    compiled: list[BackgroundStatementRow] = []
    for cat in CATEGORY_ORDER:
        for row in per_cat.get(cat) or []:
            note_day = _parse_day(str(row.get("note_date") or ""))
            rel_key = _relative_key(note_day, as_of_day)
            units = expand_background_note_units(
                str(row.get("content") or ""), locale=loc
            )
            kept_chunks = 0
            for unit in units:
                cleaned = _denumerize_line(unit, locale=loc)
                if not cleaned or is_background_text_stub(cleaned, locale=loc):
                    dropped += 1
                    continue
                leftover = leftover_s_level_numeric_tokens(cleaned)
                if leftover:
                    dropped += 1
                    logger.info("bg_brief_line_dropped leftover=%s", leftover)
                    continue
                chunks = split_background_portrait_chunks(cleaned, locale=loc)
                for chunk in chunks:
                    if leftover_s_level_numeric_tokens(chunk):
                        dropped += 1
                        continue
                    if is_background_text_stub(chunk, locale=loc):
                        dropped += 1
                        continue
                    compiled.append(
                        BackgroundStatementRow(
                            category=cat,
                            text=chunk,
                            rel_key=rel_key,
                        )
                    )
                    kept_chunks += 1
            if not kept_chunks:
                dropped += 1

    # Same-text rows (e.g. tab vs space-collapsed note variants) keep one.
    seen_row: set[str] = set()
    deduped_rows: list[BackgroundStatementRow] = []
    for row in compiled:
        key = _norm_dedupe_key(row.text)
        if not key or key in seen_row:
            dropped += 1
            continue
        seen_row.add(key)
        deduped_rows.append(row)
    compiled = deduped_rows

    row_lim = _row_caps(locale=loc)
    compiled, extra_drop = _apply_row_caps(compiled, row_lim=row_lim, locale=loc)
    dropped += extra_drop

    lines = render_background_statement_lines(compiled, locale=loc)
    lines = _truncate_lines(lines, _max_chars(loc))
    while lines and not lines[-1].startswith("- "):
        lines.pop()
    kept_texts: list[str] = []
    for line in lines:
        if line.startswith("- "):
            kept_texts.append(_bullet_text(line, locale=loc))
    text_i = 0
    kept_rows: list[BackgroundStatementRow] = []
    for row in compiled:
        if text_i >= len(kept_texts):
            break
        if row.text == kept_texts[text_i]:
            kept_rows.append(row)
            text_i += 1
    digest = hashlib.sha256(
        json.dumps([r.as_dict() for r in kept_rows], ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    return kept_rows, {
        "notes_used": len(kept_rows),
        "lines_dropped": dropped,
        "digest": digest,
        "brief_source": "live_notes",
    }


def _schedule_bucket(text: str, *, marks: list[str], glue: str) -> str:
    body = (text or "").strip()
    for mark in sorted(marks, key=len, reverse=True):
        if body.startswith(f"{mark}{glue}") or body.startswith(mark):
            return mark
    return ""


def _interleave_ends(items: list[BackgroundStatementRow]) -> list[BackgroundStatementRow]:
    if len(items) <= 2:
        return list(items)
    out: list[BackgroundStatementRow] = []
    i, j = 0, len(items) - 1
    while i <= j:
        out.append(items[i])
        if i != j:
            out.append(items[j])
        i += 1
        j -= 1
    return out


def _apply_row_caps(
    rows: list[BackgroundStatementRow],
    *,
    row_lim: dict[str, int],
    locale: str,
) -> tuple[list[BackgroundStatementRow], int]:
    """Keep up to row_lim rows per category, round-robin across schedule marks.

    Recency order inside each mark bucket is preserved (notes were already
    newest-first). No drug-name preference.
    """
    marks = [
        part.strip()
        for part in card_copy(locale, "bg_brief_split_marks").split("|")
        if part.strip()
    ]
    glue = card_copy(locale, "bg_brief_item_glue") or " · "
    kept: list[BackgroundStatementRow] = []
    dropped = 0
    for cat in CATEGORY_ORDER:
        cat_rows = [r for r in rows if r.category == cat]
        lim = int(row_lim.get(cat, 0))
        if lim <= 0 or not cat_rows:
            dropped += len(cat_rows)
            continue
        buckets: dict[str, list[BackgroundStatementRow]] = {}
        order: list[str] = []
        for row in cat_rows:
            key = _schedule_bucket(row.text, marks=marks, glue=glue)
            if key not in buckets:
                buckets[key] = []
                order.append(key)
            buckets[key].append(row)
        # Prefer named schedule marks before unmarked leftovers.
        order.sort(key=lambda k: (0 if k else 1, marks.index(k) if k in marks else 99))
        # Long "a + b + … + z" chains: surface both ends so late items are not
        # starved by round-robin + char truncation.
        for key in order:
            buckets[key] = _interleave_ends(buckets[key])
        idxs = {k: 0 for k in order}
        taken = 0
        progress = True
        while taken < lim and progress:
            progress = False
            for key in order:
                if taken >= lim:
                    break
                i = idxs[key]
                bucket = buckets[key]
                if i >= len(bucket):
                    continue
                kept.append(bucket[i])
                idxs[key] = i + 1
                taken += 1
                progress = True
        dropped += max(0, len(cat_rows) - taken)
    return kept, dropped


def _bullet_text(line: str, *, locale: str) -> str:
    body = line[2:]
    for key in ("bg_brief_rel_week", "bg_brief_rel_month", "bg_brief_rel_earlier"):
        rel = card_copy(locale, key)
        suffix = f"（{rel}）" if (locale or "").lower().startswith("zh") else f" ({rel})"
        if body.endswith(suffix):
            return body[: -len(suffix)]
    return body


def render_background_statement_lines(
    rows: list[BackgroundStatementRow],
    *,
    locale: str,
) -> list[str]:
    loc = (locale or "en").strip() or "en"
    zh = loc.lower().startswith("zh")
    lines: list[str] = []
    last_cat = ""
    for row in rows:
        if row.category != last_cat:
            lines.append(card_copy(loc, f"bg_brief_cat_{row.category}"))
            last_cat = row.category
        rel = card_copy(loc, row.rel_key)
        suffix = f"（{rel}）" if zh else f" ({rel})"
        lines.append(f"- {row.text}{suffix}")
    return lines


def render_background_brief_markdown(
    rows: list[BackgroundStatementRow],
    *,
    locale: str,
) -> str:
    loc = (locale or "en").strip() or "en"
    lines = render_background_statement_lines(rows, locale=loc)
    if not lines:
        return ""
    title = card_copy(loc, "bg_brief_title")
    lead = card_copy(loc, "bg_brief_lead")
    return f"【{title}】\n{lead}\n" + "\n".join(lines)


def build_live_notes_background_brief(
    user_id: str,
    *,
    locale: str = "en",
    as_of: str | None = None,
) -> tuple[str, dict[str, Any]]:
    """P14 live-notes projection. Does not read CHB (avoids compile recursion)."""
    empty_meta = {
        "notes_used": 0,
        "lines_dropped": 0,
        "digest": "",
        "brief_source": "live_notes",
    }
    if not background_brief_enabled():
        return "", empty_meta
    rows, meta = compile_background_statement_rows(
        user_id, locale=locale, as_of=as_of
    )
    text = render_background_brief_markdown(rows, locale=locale)
    if not text:
        return "", {**empty_meta, "lines_dropped": int(meta.get("lines_dropped") or 0)}
    return text, meta


def build_fact_card_background_brief(
    user_id: str,
    *,
    locale: str = "en",
    as_of: str | None = None,
    prefer_chb: bool = True,
) -> tuple[str, dict[str, Any]]:
    """Return (slot body, meta). Empty body when flag off or no usable notes.

    Prefer a fresh CHB projection (P15) when present; otherwise live notes (P14).
    """
    empty_meta = {
        "notes_used": 0,
        "lines_dropped": 0,
        "digest": "",
        "brief_source": "live_notes",
    }
    if not background_brief_enabled():
        return "", empty_meta
    uid = (user_id or "default").strip() or "default"
    loc = (locale or "en").strip() or "en"
    if prefer_chb:
        chb_text, chb_meta = _try_chb_interpret_brief(uid, locale=loc)
        if chb_text:
            return chb_text, chb_meta
    return build_live_notes_background_brief(uid, locale=loc, as_of=as_of)


def _try_chb_interpret_brief(
    user_id: str,
    *,
    locale: str,
) -> tuple[str, dict[str, Any]]:
    try:
        from pha.chb_compiler import (
            chb_stale_status,
            load_latest_chb_artifact,
            project_chb_for_fact_card_interpret,
        )
    except Exception as exc:  # pragma: no cover - import cycle guard
        logger.info("bg_brief_chb_import_skipped: %s", exc)
        return "", {}
    try:
        status = chb_stale_status(user_id)
        if status.get("is_stale"):
            return "", {}
        artifact = load_latest_chb_artifact(user_id)
    except Exception as exc:
        logger.info("bg_brief_chb_lookup_failed: %s", exc)
        return "", {}
    if artifact is None:
        return "", {}
    text = project_chb_for_fact_card_interpret(artifact, locale=locale)
    if not (text or "").strip():
        return "", {}
    leftover = leftover_s_level_numeric_tokens(text)
    if leftover:
        logger.info("bg_brief_chb_dropped leftover=%s", leftover)
        return "", {}
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    used = sum(1 for line in text.splitlines() if line.startswith("- "))
    return text, {
        "notes_used": used,
        "lines_dropped": 0,
        "digest": digest,
        "brief_source": "chb",
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
