"""Parse explicit calendar date ranges from user chat messages (v2.2.1)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from typing import Any, Optional

from pha.date_parser import safe_parse_date
from pha.health_data import effective_query_reference_date

_ISO_RANGE_RE = re.compile(
    r"(20\d{2}|19\d{2})[-/.](\d{1,2})[-/.](\d{1,2})\s*(?:到|至|—|-|~|～)\s*"
    r"(20\d{2}|19\d{2})[-/.](\d{1,2})[-/.](\d{1,2})",
    re.I,
)
_CN_RANGE_RE = re.compile(
    r"(20\d{2}|19\d{2})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日\s*"
    r"(?:到|至|—|-|~|～)\s*"
    r"(20\d{2}|19\d{2})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日",
    re.I,
)

_META_RANGE_QUESTION_RE = re.compile(
    r"日期范围|时间范围|精确日期|哪段时间|什么时候到|从哪天|到哪一天|数据区间",
    re.I,
)

_SNAPSHOT_SPAN_RE = re.compile(
    r"User Data Snapshot[^）)]*?"
    r"(\d{4}-\d{2}-\d{2})\s*[~～\-至到]+\s*(\d{4}-\d{2}-\d{2})",
    re.I,
)


@dataclass(frozen=True)
class ParsedDateRange:
    start: date
    end: date

    def iso_span(self) -> str:
        return f"{self.start.isoformat()}～{self.end.isoformat()}"


def _triplet_to_date(y: str, m: str, d: str) -> Optional[date]:
    try:
        return date(int(y), int(m), int(d))
    except ValueError:
        return None


def parse_user_date_range(text: str) -> Optional[ParsedDateRange]:
    """Extract inclusive [start, end] from explicit user calendar spans."""
    raw = (text or "").strip()
    if not raw:
        return None
    for pat in (_ISO_RANGE_RE, _CN_RANGE_RE):
        m = pat.search(raw)
        if not m:
            continue
        start = _triplet_to_date(m.group(1), m.group(2), m.group(3))
        end = _triplet_to_date(m.group(4), m.group(5), m.group(6))
        if start is None or end is None:
            continue
        if end < start:
            start, end = end, start
        ref = effective_query_reference_date()
        if end > ref:
            end = ref
        return ParsedDateRange(start=start, end=end)
    return None


def is_meta_date_range_question(text: str) -> bool:
    return bool(_META_RANGE_QUESTION_RE.search(text or ""))


def extract_snapshot_span_from_text(text: str) -> Optional[ParsedDateRange]:
    """Pull ``start~end`` from a prior ``User Data Snapshot`` line."""
    m = _SNAPSHOT_SPAN_RE.search(text or "")
    if not m:
        return None
    s = safe_parse_date(m.group(1))
    e = safe_parse_date(m.group(2))
    if s is None or e is None:
        return None
    if e < s:
        s, e = e, s
    return ParsedDateRange(start=s, end=e)


def default_wearable_window(
    user_message: str,
    *,
    reference: Optional[date] = None,
    episodic: Any = None,
) -> ParsedDateRange:
    """Explicit calendar span wins; else 1E-a time-anchor grain; else 90-day default."""
    explicit = parse_user_date_range(user_message)
    if explicit:
        return explicit
    from pha.wearable_time_grain import resolve_wearable_time_grain

    ref = reference or effective_query_reference_date()
    grain = resolve_wearable_time_grain(user_message, reference=ref, episodic=episodic)
    return ParsedDateRange(start=grain.start, end=grain.end)
