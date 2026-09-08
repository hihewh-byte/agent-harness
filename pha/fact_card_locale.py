"""Fact-card display locale: dates for humans, ISO stays on the JSON."""

from __future__ import annotations

import re
from datetime import date, datetime, timezone
from typing import Any, Optional
from zoneinfo import ZoneInfo

ALLOWED_LOCALES = ("zh-CN", "en-US")
DEFAULT_LOCALE = "en-US"
_SLASH_DATE_RE = re.compile(r"(?<!\d)\d{1,2}/\d{1,2}(?:/\d{2,4})?(?!\d)")
_MD_WRAP_RE = re.compile(r"[*_`]+")
_MD_HEADING_RE = re.compile(r"^#{1,6}\s*", re.M)
_EN_MONTHS = (
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
)


def normalize_fact_card_locale(value: Optional[str]) -> str:
    raw = (value or "").strip()
    if raw in ALLOWED_LOCALES:
        return raw
    low = raw.lower().replace("_", "-")
    if low.startswith("en"):
        return "en-US"
    if low.startswith("zh"):
        return "zh-CN"
    return DEFAULT_LOCALE


def resolve_fact_card_locale(
    *,
    prefs_locale: Optional[str] = None,
    accept_language: Optional[str] = None,
) -> str:
    if (prefs_locale or "").strip():
        return normalize_fact_card_locale(prefs_locale)
    if accept_language:
        first = accept_language.split(",", 1)[0].split(";", 1)[0]
        if first.strip():
            return normalize_fact_card_locale(first)
    return DEFAULT_LOCALE


def display_timezone(prefs_timezone: Optional[str] = None):
    raw = (prefs_timezone or "").strip()
    if raw:
        try:
            return ZoneInfo(raw)
        except Exception:
            pass
    return datetime.now().astimezone().tzinfo or timezone.utc


def _as_date(value: Any) -> Optional[date]:
    if value is None or value == "" or value == "无":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if len(text) >= 10 and text[4] == "-" and text[7] == "-":
        try:
            return date.fromisoformat(text[:10])
        except ValueError:
            return None
    return None


def _as_datetime(value: Any, *, tz) -> Optional[datetime]:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        dt = value
        if dt.tzinfo is None:
            return dt.replace(tzinfo=tz)
        return dt.astimezone(tz)
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day, tzinfo=tz)
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        day = _as_date(text)
        if day is None:
            return None
        return datetime(day.year, day.month, day.day, tzinfo=tz)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=tz)
    return dt.astimezone(tz)


def format_card_day(
    value: Any,
    *,
    locale: str = DEFAULT_LOCALE,
    now: Optional[datetime] = None,
) -> str:
    day = _as_date(value)
    if day is None:
        return "无" if normalize_fact_card_locale(locale) == "zh-CN" else "none"
    loc = normalize_fact_card_locale(locale)
    clock = now or datetime.now()
    if loc == "en-US":
        return f"{_EN_MONTHS[day.month - 1]} {day.day}, {day.year}"
    if day.year != clock.year:
        return f"{day.year}年{day.month}月{day.day}日"
    return f"{day.month}月{day.day}日"


def format_card_datetime(
    value: Any,
    *,
    locale: str = DEFAULT_LOCALE,
    timezone_name: Optional[str] = None,
    now: Optional[datetime] = None,
) -> str:
    tz = display_timezone(timezone_name)
    dt = _as_datetime(value, tz=tz)
    if dt is None:
        return format_card_day(value, locale=locale, now=now)
    loc = normalize_fact_card_locale(locale)
    clock = now or datetime.now(tz)
    stamp = f"{dt.hour:02d}:{dt.minute:02d}"
    if loc == "en-US":
        month = _EN_MONTHS[dt.month - 1]
        if dt.year != clock.year:
            return f"{month} {dt.day}, {dt.year}, {stamp}"
        return f"{month} {dt.day}, {stamp}"
    day_part = format_card_day(dt.date(), locale=loc, now=clock)
    return f"{day_part} {stamp}"


def format_clock_hm(value: Any) -> str:
    text = str(value or "").strip()
    if re.fullmatch(r"\d{1,2}:\d{2}", text):
        hh, mm = text.split(":")
        return f"{int(hh):02d}:{mm}"
    dt = _as_datetime(value, tz=display_timezone())
    if dt is None:
        return text
    return f"{dt.hour:02d}:{dt.minute:02d}"


def numeric_band_label(numeric_band: Optional[str], *, locale: str = DEFAULT_LOCALE) -> str:
    loc = normalize_fact_card_locale(locale)
    key = str(numeric_band or "").strip()
    if loc == "en-US":
        return {
            "above": "higher",
            "below": "lower",
            "typical": "similar",
            "unknown": "no band",
            "pending": "in progress",
            "missing": "",
        }.get(key, "")
    return {
        "above": "高于",
        "below": "低于",
        "typical": "持平",
        "unknown": "暂不分档",
        "pending": "进行中",
        "missing": "",
    }.get(key, "")


def strip_markdown_markers(text: str) -> str:
    """Remove Markdown markers only; never rewrite digits or dates."""
    out = _MD_HEADING_RE.sub("", text or "")
    out = out.replace("**", "").replace("`", "")
    out = re.sub(r"(?<!\d)\*(?!\d)", "", out)
    out = _MD_WRAP_RE.sub("", out)
    return out


def html_has_slash_date(html: str) -> bool:
    return bool(_SLASH_DATE_RE.search(html or ""))


__all__ = [
    "ALLOWED_LOCALES",
    "DEFAULT_LOCALE",
    "display_timezone",
    "format_card_datetime",
    "format_card_day",
    "format_clock_hm",
    "html_has_slash_date",
    "normalize_fact_card_locale",
    "numeric_band_label",
    "resolve_fact_card_locale",
    "strip_markdown_markers",
]
