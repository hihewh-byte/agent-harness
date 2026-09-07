"""Robust ISO / Apple Health datetime parsing for PHA (Python 3.9+)."""

from __future__ import annotations

import logging
import re
from datetime import date, datetime, time
from typing import Any, Optional, Union

logger = logging.getLogger(__name__)

DateLike = Union[str, date, datetime, None]

# 2025-12-07, 2025-12-07T23:59:59, 2025-12-07 23:59:59.123+08:00
_ISO_PREFIX_RE = re.compile(
    r"^(\d{4})-(\d{2})-(\d{2})"
    r"(?:[T\s](\d{2}):(\d{2})(?::(\d{2})(?:\.(\d+))?)?)?"
    r"(?:\s*([Zz]|([+-])(\d{2}):?(\d{2})))?$",
)


_MONTH_NAME = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}

# iOS Shortcuts Get Details → Start/End Date, e.g. "7 Sep 2026 at 12:01 AM"
_SHORTCUT_DMY_RE = re.compile(
    r"^(?P<day>\d{1,2})\s+(?P<mon>[A-Za-z]+)\s+(?P<year>\d{4})\s+at\s+"
    r"(?P<hour>\d{1,2}):(?P<minute>\d{2})(?::(?P<sec>\d{2}))?\s*(?P<ampm>AM|PM)$",
    re.IGNORECASE,
)
_SHORTCUT_MDY_RE = re.compile(
    r"^(?P<mon>[A-Za-z]+)\s+(?P<day>\d{1,2}),\s+(?P<year>\d{4})\s+at\s+"
    r"(?P<hour>\d{1,2}):(?P<minute>\d{2})(?::(?P<sec>\d{2}))?\s*(?P<ampm>AM|PM)$",
    re.IGNORECASE,
)


def _normalize_dt_text(raw: str) -> str:
    text = str(raw).strip()
    for ch in ("\u202f", "\xa0", "\u2007", "\u2009", "\u200a", "\u2060"):
        text = text.replace(ch, " ")
    return re.sub(r"\s+", " ", text).strip()


def _parse_shortcut_datetime(raw: str) -> Optional[datetime]:
    match = _SHORTCUT_DMY_RE.match(raw) or _SHORTCUT_MDY_RE.match(raw)
    if match is None:
        return None
    month = _MONTH_NAME.get(match.group("mon").lower())
    if month is None:
        return None
    hour = int(match.group("hour"))
    ampm = match.group("ampm").upper()
    if hour == 12:
        hour = 0 if ampm == "AM" else 12
    elif ampm == "PM":
        hour += 12
    try:
        return datetime(
            int(match.group("year")),
            month,
            int(match.group("day")),
            hour,
            int(match.group("minute")),
            int(match.group("sec") or 0),
        )
    except ValueError:
        return None


def safe_parse_datetime(value: DateLike) -> Optional[datetime]:
    """
    Parse timestamps from SQLite TEXT, Apple Health export, or medical_reports.

    Never raises — returns ``None`` on unrecoverable input.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime.combine(value, time.min)

    raw = _normalize_dt_text(str(value))
    if not raw:
        return None

    s = raw.replace("Z", "+00:00").replace("z", "+00:00")
    if re.match(r"^\d{4}-\d{2}-\d{2} ", s) and "T" not in s:
        s = s.replace(" ", "T", 1)

    try:
        return datetime.fromisoformat(s)
    except ValueError:
        pass

    m = _ISO_PREFIX_RE.match(raw)
    if m:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        hh = int(m.group(4) or 0)
        mm = int(m.group(5) or 0)
        ss = int(m.group(6) or 0)
        try:
            return datetime(y, mo, d, hh, mm, ss)
        except ValueError:
            pass

    shortcut = _parse_shortcut_datetime(raw)
    if shortcut is not None:
        return shortcut

    try:
        from dateutil import parser as dateutil_parser  # type: ignore

        return dateutil_parser.parse(raw)
    except ImportError:
        pass
    except (ValueError, TypeError, OverflowError):
        pass

    if len(raw) >= 10:
        try:
            d = date.fromisoformat(raw[:10])
            return datetime.combine(d, time.min)
        except ValueError:
            pass

    logger.warning("safe_parse_datetime: could not parse %r", value)
    return None


def safe_parse_date(value: DateLike) -> Optional[date]:
    """
    Parse calendar dates from ``YYYY-MM-DD`` or ``YYYY-MM-DDTHH:MM:SS`` storage.

    ``date.fromisoformat`` rejects time components on Python 3.9 — this helper
  always normalizes to a ``date``.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value

    raw = str(value).strip()
    if not raw:
        return None

    if len(raw) >= 10 and raw[4:5] == "-" and raw[7:8] == "-":
        try:
            return date.fromisoformat(raw[:10])
        except ValueError:
            pass

    dt = safe_parse_datetime(raw)
    if dt is not None:
        return dt.date()

    logger.warning("safe_parse_date: could not parse %r", value)
    return None


def safe_parse_date_required(value: DateLike, *, field: str = "date") -> date:
    """Like ``safe_parse_date`` but raises ``ValueError`` with context."""
    parsed = safe_parse_date(value)
    if parsed is None:
        raise ValueError(f"Invalid {field}: {value!r}")
    return parsed
