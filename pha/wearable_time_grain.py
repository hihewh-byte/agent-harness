"""Bind 1E-a time-anchor slots to a wearable evidence window.

Catalog aliases are metric identity only. Time tokens are stripped into
Tier-C slots (``TIME_ANCHOR_TOKENS``) and must not enter the catalog.
Skip-LLM / Numerics previously ignored those slots and always used the
default 90-day mean — that is why 「今天」 vanished from the answer.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Callable, Optional

from pha.health_data import effective_query_reference_date
from pha.loop_keyword_conflicts import TIME_ANCHOR_TOKENS

# Anaphora lives on TIME_ANCHOR_TOKENS for catalog denylist, not as a calendar window.
_ANAPHORA_TIME_TOKENS = frozenset({"刚才", "上一个"})

_ASCII_TOKEN_RE_CACHE: dict[str, re.Pattern[str]] = {}

GrainBuilder = Callable[[date], tuple[date, date, str]]


def _point_day(offset: int) -> GrainBuilder:
    def build(ref: date) -> tuple[date, date, str]:
        day = ref + timedelta(days=offset)
        return day, day, "point"

    return build


def _iso_week(weeks_ago: int) -> GrainBuilder:
    def build(ref: date) -> tuple[date, date, str]:
        monday = ref - timedelta(days=ref.weekday()) - timedelta(weeks=weeks_ago)
        sunday = monday + timedelta(days=6)
        end = min(sunday, ref) if weeks_ago == 0 else sunday
        if end < monday:
            end = monday
        return monday, end, "mean"

    return build


def _month_to_date() -> GrainBuilder:
    def build(ref: date) -> tuple[date, date, str]:
        return ref.replace(day=1), ref, "mean"

    return build


def _previous_month() -> GrainBuilder:
    def build(ref: date) -> tuple[date, date, str]:
        first = ref.replace(day=1)
        end_prev = first - timedelta(days=1)
        return end_prev.replace(day=1), end_prev, "mean"

    return build


def _rolling_days(days: int) -> GrainBuilder:
    def build(ref: date) -> tuple[date, date, str]:
        start = ref - timedelta(days=max(1, days) - 1)
        return start, ref, "mean"

    return build


def _calendar_year(year_offset: int) -> GrainBuilder:
    def build(ref: date) -> tuple[date, date, str]:
        year = ref.year + year_offset
        start = date(year, 1, 1)
        end = date(year, 12, 31)
        if end > ref:
            end = ref
        if start > ref:
            start = ref
        return start, end, "mean"

    return build


# Longest tokens first in each group. Rank: wider/explicit duration beats a day grain.
_TOKEN_SPECS: tuple[tuple[tuple[str, ...], int, GrainBuilder], ...] = (
    (("近90天", "近九十天", "last 90 days", "past 90 days"), 50, _rolling_days(90)),
    (("近7天", "近七天", "last 7 days", "past 7 days"), 40, _rolling_days(7)),
    (("去年", "last year"), 35, _calendar_year(-1)),
    (("前年",), 34, _calendar_year(-2)),
    (("上个月", "上月", "last month"), 30, _previous_month()),
    (("这个月", "本月", "this month"), 29, _month_to_date()),
    (("上周", "last week"), 20, _iso_week(1)),
    (("本周", "这周", "this week"), 19, _iso_week(0)),
    (("前天",), 12, _point_day(-2)),
    (("昨天", "昨晚", "yesterday", "last night"), 11, _point_day(-1)),
    (
        ("今天", "今日", "当天", "今早", "今夜", "今晚", "today", "tonight"),
        10,
        _point_day(0),
    ),
)

_ROLLING_KEYWORD_SPECS: tuple[tuple[re.Pattern[str], int], ...] = (
    (re.compile(r"一年|365|12\s*个月"), 365),
    (re.compile(r"6\s*个月|半年"), 180),
    (re.compile(r"30\s*天|一个?月|1\s*个月"), 30),
    (re.compile(r"3\s*个月|三个月|近三月|最近3个月|90\s*天"), 90),
)

# Duration phrases are a class (过去N天 / last N days), not frozen aliases.
_CN_DAY_COUNT = {
    "两": 2,
    "七": 7,
    "十": 10,
    "十四": 14,
    "十五": 15,
    "二十": 20,
    "三十": 30,
    "六十": 60,
    "九十": 90,
}
_ROLLING_N_RE = re.compile(
    r"(?:过去|近|最近)\s*(\d+|九十|六十|三十|二十|十五|十四|十|七|两)\s*天"
    r"|(?:last|past)\s+(\d+)\s+days?",
    re.I,
)
_ROLLING_WEEK_RE = re.compile(r"过去一周|近一周|最近一周|(?<![A-Za-z])past\s+week(?![A-Za-z])", re.I)


@dataclass(frozen=True)
class WearableTimeGrain:
    start: date
    end: date
    aggregation: str
    source: str
    token: str = ""

    def is_point_day(self) -> bool:
        return self.aggregation == "point" and self.start == self.end

    def is_default_90d(self) -> bool:
        return self.source == "default"


def _ascii_token_re(token: str) -> re.Pattern[str]:
    cached = _ASCII_TOKEN_RE_CACHE.get(token)
    if cached is None:
        cached = re.compile(rf"(?<![A-Za-z]){re.escape(token)}(?![A-Za-z])", re.I)
        _ASCII_TOKEN_RE_CACHE[token] = cached
    return cached


def time_token_in_message(token: str, text: str) -> bool:
    if not token or not text:
        return False
    if any(ch.isascii() and ch.isalpha() for ch in token):
        return _ascii_token_re(token).search(text) is not None
    return token in text


def _known_time_tokens() -> tuple[str, ...]:
    extra = tuple(tok for group, _rank, _fn in _TOKEN_SPECS for tok in group)
    seen = set(TIME_ANCHOR_TOKENS)
    out = list(TIME_ANCHOR_TOKENS)
    for tok in extra:
        if tok not in seen:
            seen.add(tok)
            out.append(tok)
    return tuple(out)


def matched_time_anchor_tokens(text: str) -> list[str]:
    """Longest-first time anchors present in the message (substring-safe)."""
    raw = text or ""
    hits = [tok for tok in _known_time_tokens() if tok not in _ANAPHORA_TIME_TOKENS and time_token_in_message(tok, raw)]
    hits.sort(key=len, reverse=True)
    chosen: list[str] = []
    for tok in hits:
        if any(tok != other and tok in other for other in chosen):
            continue
        chosen.append(tok)
    return chosen


def _spec_for_token(token: str) -> tuple[int, GrainBuilder] | None:
    for group, rank, builder in _TOKEN_SPECS:
        if token in group:
            return rank, builder
    return None


def _parse_day_count(raw: str) -> Optional[int]:
    token = (raw or "").strip().lower()
    if token.isdigit():
        n = int(token)
        return n if 1 <= n <= 365 else None
    return _CN_DAY_COUNT.get(token)


def _rolling_n_rank(days: int) -> int:
    if days >= 80:
        return 50
    if days >= 28:
        return 42
    if days >= 7:
        return 40
    return 36


def _parse_rolling_n_days(text: str) -> Optional[tuple[int, str]]:
    raw = text or ""
    if _ROLLING_WEEK_RE.search(raw):
        return 7, "过去一周"
    match = _ROLLING_N_RE.search(raw)
    if not match:
        return None
    token = match.group(1) or match.group(2) or ""
    days = _parse_day_count(token)
    if days is None:
        return None
    return days, match.group(0)


def point_day_grain(ref: date, *, token: str = "today") -> WearableTimeGrain:
    """Calendar-day slot. Binders must return that day or empty — never another day."""
    start, end, agg = _point_day(0)(ref)
    return WearableTimeGrain(
        start=start,
        end=end,
        aggregation=agg,
        source="time_slot",
        token=token,
    )


def rolling_n_grain(days: int, ref: date, *, token: str = "") -> WearableTimeGrain:
    start, end, agg = _rolling_days(days)(ref)
    return WearableTimeGrain(
        start=start,
        end=end,
        aggregation=agg,
        source="rolling_n",
        token=token or f"rolling_{days}",
    )


def _default_grain(ref: date) -> WearableTimeGrain:
    start, end, agg = _rolling_days(90)(ref)
    return WearableTimeGrain(start=start, end=end, aggregation=agg, source="default")


def resolve_wearable_time_grain(
    user_message: str,
    *,
    reference: Optional[date] = None,
    episodic: Any = None,
) -> WearableTimeGrain:
    """Map a user message onto a wearable window + aggregation.

    Explicit ISO/CN ranges are handled by ``default_wearable_window``.
    Episodic compare follow-ups keep the default 90-day grain so screenshot
    delta skip-LLM is not stolen by a lone 「上周」 token.
    """
    ref = reference or effective_query_reference_date()
    text = user_message or ""
    if not text.strip():
        return _default_grain(ref)

    from pha.health_intent_catalog import is_episodic_delta_followup_message

    if is_episodic_delta_followup_message(text):
        return _default_grain(ref)

    ranked: list[tuple[int, WearableTimeGrain]] = []
    rolling_n = _parse_rolling_n_days(text)
    if rolling_n is not None:
        days, token = rolling_n
        start, end, agg = _rolling_days(days)(ref)
        ranked.append(
            (
                _rolling_n_rank(days),
                WearableTimeGrain(
                    start=start,
                    end=end,
                    aggregation=agg,
                    source="rolling_n",
                    token=token,
                ),
            )
        )
    rolling_ranks = {365: 48, 180: 45, 90: 50, 30: 38}
    for pat, days in _ROLLING_KEYWORD_SPECS:
        if not pat.search(text):
            continue
        if days == 30 and re.search(r"90\s*天", text):
            continue
        start, end, agg = _rolling_days(days)(ref)
        ranked.append(
            (
                rolling_ranks.get(days, 38),
                WearableTimeGrain(
                    start=start,
                    end=end,
                    aggregation=agg,
                    source="rolling_keyword",
                    token=pat.pattern,
                ),
            )
        )
        break

    for tok in matched_time_anchor_tokens(text):
        spec = _spec_for_token(tok)
        if spec is None:
            continue
        rank, builder = spec
        start, end, agg = builder(ref)
        ranked.append(
            (
                rank,
                WearableTimeGrain(
                    start=start,
                    end=end,
                    aggregation=agg,
                    source="time_slot",
                    token=tok,
                ),
            )
        )

    if not ranked:
        if (os.environ.get("PHA_EPISODIC_GRAIN_ANCHOR") or "1").strip().lower() in (
            "1",
            "true",
            "yes",
        ) and episodic is not None:
            start_s = str(getattr(episodic, "focus_grain_start", "") or "").strip()
            end_s = str(getattr(episodic, "focus_grain_end", "") or "").strip()
            agg = str(getattr(episodic, "focus_grain_aggregation", "") or "point").strip() or "point"
            if start_s and end_s:
                from pha.intent_gates import infer_wearable_metric_ids

                if infer_wearable_metric_ids(text):
                    try:
                        return WearableTimeGrain(
                            start=date.fromisoformat(start_s),
                            end=date.fromisoformat(end_s),
                            aggregation=agg,
                            source="episodic_anchor",
                            token="episodic",
                        )
                    except ValueError:
                        pass
        return _default_grain(ref)
    ranked.sort(key=lambda item: item[0], reverse=True)
    return ranked[0][1]


__all__ = [
    "WearableTimeGrain",
    "matched_time_anchor_tokens",
    "point_day_grain",
    "resolve_wearable_time_grain",
    "rolling_n_grain",
    "time_token_in_message",
]
