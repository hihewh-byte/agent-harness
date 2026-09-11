"""Wake-day keying for sleep segments (Health app / HealthKit alignment).

A wake night ending on calendar day D lives in ``[D-1 12:00, D 12:00)``.
Zip import historically keyed ``day`` by segment *start* date, which parks
pre-midnight Core/Deep on the previous calendar day. HealthKit ingest already
uses wake day; this module is the shared rule for rebucket + future zip writes.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Optional


def as_naive_local(dt: datetime) -> datetime:
    if dt.tzinfo is not None:
        return dt.astimezone().replace(tzinfo=None)
    return dt


def sleep_wake_window(wake_day: date) -> tuple[datetime, datetime]:
    noon = datetime.combine(wake_day, time(12, 0, 0))
    return noon - timedelta(days=1), noon


def clip_to_wake_window(
    start: datetime,
    end: datetime,
    wake_day: date,
) -> Optional[tuple[datetime, datetime]]:
    window_start, window_end = sleep_wake_window(wake_day)
    clip_start = max(start, window_start)
    clip_end = min(end, window_end)
    if clip_end <= clip_start:
        return None
    return clip_start, clip_end


def wake_day_for_instant(ts: datetime) -> date:
    """Which wake night contains *ts* under the noon-to-noon rule."""
    local = as_naive_local(ts)
    noon = datetime.combine(local.date(), time(12, 0, 0))
    if local < noon:
        return local.date()
    return local.date() + timedelta(days=1)


def wake_day_for_segment(start: datetime, end: datetime) -> date:
    """Assign a segment to a wake day (start instant; overnight-safe)."""
    _ = end  # end reserved for future multi-window clip callers
    return wake_day_for_instant(start)


__all__ = [
    "as_naive_local",
    "clip_to_wake_window",
    "sleep_wake_window",
    "wake_day_for_instant",
    "wake_day_for_segment",
]
