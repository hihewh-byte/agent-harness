"""Bind a WearableTimeGrain to wearable_daily rows.

A labeled slot (今日 / 昨天 / 近7日) may only read days inside that grain.
Point-day slots never fall back to the latest row in a wider window.
"""

from __future__ import annotations

from datetime import date
from typing import Iterable, Optional, Sequence

from pha.models import WearableDailySummary
from pha.wearable_time_grain import WearableTimeGrain, point_day_grain, rolling_n_grain


def pick_point_day_row(
    rows: Sequence[WearableDailySummary],
    day: date,
) -> Optional[WearableDailySummary]:
    """Exact calendar day, or None. No latest-row / nearest-day substitute."""
    matches = [row for row in rows if row.day == day]
    if not matches:
        return None
    return matches[0]


def rows_inside_grain(
    rows: Sequence[WearableDailySummary],
    grain: WearableTimeGrain,
) -> list[WearableDailySummary]:
    return [row for row in rows if grain.start <= row.day <= grain.end]


def mean_present(rows: Iterable[WearableDailySummary], attr: str) -> Optional[float]:
    vals = [float(getattr(row, attr)) for row in rows if getattr(row, attr) is not None]
    if not vals:
        return None
    return sum(vals) / len(vals)


def compose_hero_wearable(
    *,
    ref: date,
    today_row: Optional[WearableDailySummary],
    week_rows: Sequence[WearableDailySummary],
) -> dict:
    """Hero cards: 今日 is the point-day grain; 7d means stay inside the 7d grain."""
    week_grain = rolling_n_grain(7, ref)
    bounded_week = rows_inside_grain(week_rows, week_grain)
    today_steps = today_row.steps if today_row is not None and today_row.day == ref else None
    hrv = mean_present(bounded_week, "hrv_sdnn_ms")
    if hrv is None:
        hrv = mean_present(bounded_week, "hrv_rmssd_ms")
    sleep = mean_present(bounded_week, "sleep_hours")
    return {
        "today_steps": today_steps,
        "today_steps_day": ref.isoformat(),
        "avg_hrv_7d": round(hrv, 1) if hrv is not None else None,
        "avg_sleep_7d": round(sleep, 2) if sleep is not None else None,
    }


def load_hero_wearable(user_id: str, ref: date) -> dict:
    from pha.sqlite_storage import query_wearable_daily_range

    uid = (user_id or "default").strip() or "default"
    today_grain = point_day_grain(ref)
    week_grain = rolling_n_grain(7, ref)
    today_rows = query_wearable_daily_range(uid, today_grain.start, today_grain.end)
    week_rows = query_wearable_daily_range(uid, week_grain.start, week_grain.end)
    return compose_hero_wearable(
        ref=ref,
        today_row=pick_point_day_row(today_rows, ref),
        week_rows=week_rows,
    )


__all__ = [
    "compose_hero_wearable",
    "load_hero_wearable",
    "mean_present",
    "pick_point_day_row",
    "rows_inside_grain",
]
