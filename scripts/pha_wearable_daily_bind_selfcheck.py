#!/usr/bin/env python3
"""Offline: 今日步数 binds to the calendar-day grain, never the latest window row."""

from __future__ import annotations

import os
import sys
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from pha.models import WearableDailySummary
from pha.wearable_daily_bind import compose_hero_wearable, pick_point_day_row


def _row(day: date, steps: int | None) -> WearableDailySummary:
    return WearableDailySummary(user_id="selfcheck", day=day, steps=steps)


def main() -> int:
    ref = date(2026, 9, 5)
    yesterday = _row(date(2026, 9, 4), 11259)
    today = _row(ref, 14872)

    if pick_point_day_row([yesterday], ref) is not None:
        print("FAIL: yesterday row must not bind to today's grain")
        return 1
    if pick_point_day_row([yesterday, today], ref) is not today:
        print("FAIL: today grain must pick the exact calendar row")
        return 1

    empty = compose_hero_wearable(ref=ref, today_row=None, week_rows=[yesterday])
    if empty["today_steps"] is not None:
        print("FAIL: hero today_steps must be None when the point-day row is missing")
        print(empty)
        return 1
    if empty["today_steps_day"] != "2026-09-05":
        print("FAIL: hero must disclose the bound calendar day")
        return 1

    filled = compose_hero_wearable(ref=ref, today_row=today, week_rows=[yesterday, today])
    if filled["today_steps"] != 14872:
        print("FAIL: hero today_steps must be today's value, not yesterday")
        print(filled)
        return 1

    wrong_day = compose_hero_wearable(ref=ref, today_row=yesterday, week_rows=[yesterday])
    if wrong_day["today_steps"] is not None:
        print("FAIL: a row whose day != ref must not fill today_steps")
        print(wrong_day)
        return 1

    print("pha_wearable_daily_bind_selfcheck: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
