#!/usr/bin/env python3
"""Offline: fact card binds calendar day, never fills today from MAX(day), no LLM."""

from __future__ import annotations

import os
import re
import sys
from datetime import date, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from pha.fact_card import (  # noqa: E402
    DISCLAIMER,
    compose_fact_card,
    fact_card_numeric_atoms,
)
from pha.models import WearableDailySummary  # noqa: E402


def _row(day: date, *, steps: int | None = None, hrv: float | None = None) -> WearableDailySummary:
    return WearableDailySummary(
        user_id="selfcheck",
        day=day,
        steps=steps,
        hrv_rmssd_ms=hrv,
    )


def _fail(msg: str) -> int:
    print(f"FAIL: {msg}")
    return 1


def main() -> int:
    calendar = date(2026, 9, 6)
    yesterday = date(2026, 9, 5)
    hist = [
        _row(yesterday - timedelta(days=i), steps=8000 + i * 10, hrv=40.0 + i)
        for i in range(1, 20)
    ]
    y_row = _row(yesterday, steps=14872, hrv=33.0)

    empty = compose_fact_card(calendar_day=calendar, rows=[], user_id="selfcheck")
    if empty["facts"]["as_of"] is not None or empty["facts"]["today"]["steps"] is not None:
        return _fail("empty ledger must not invent as_of or today steps")
    if "14872" in empty["notification"]["body"]:
        return _fail("empty card leaked a number")

    stale = compose_fact_card(calendar_day=calendar, rows=hist + [y_row], user_id="selfcheck")
    if stale["facts"]["stale"] is not True:
        return _fail("calendar after MAX(day) must be stale")
    if stale["facts"]["today"]["steps"] is not None or stale["facts"]["today"]["present"]:
        return _fail("today must stay empty when the point-day row is missing")
    if stale["facts"]["as_of"] != "2026-09-05":
        return _fail("as_of must be MAX(day), not calendar day")
    steps_m = next(m for m in stale["facts"]["metrics"] if m["metric"] == "steps")
    if steps_m["value"] != 14872 or steps_m["day"] != "2026-09-05":
        return _fail("as_of steps must come from MAX(day) row")
    if "今日" in stale["notification"]["body"] and "非今日" not in stale["notification"]["body"]:
        return _fail("stale notification must not claim 今日")
    if DISCLAIMER not in stale["notification"]["body"]:
        return _fail("notification missing disclaimer")
    body = stale["notification"]["body"]
    for label in ("步数", "HRV", "睡眠", "静息心率", "活动消耗"):
        if label not in body:
            return _fail(f"notification must enumerate {label}")
    if "睡眠无" not in body or "静息心率无" not in body or "活动消耗无" not in body:
        return _fail("missing metrics must show 无, not be omitted")
    if "HRV33" not in body and "HRV33.0" not in body:
        return _fail("present HRV must appear as a number, not be dropped")
    if "评估：" not in body or "建议：" not in body:
        return _fail("notification must include assessment and advice lines")
    summary = stale["assessment"].get("summary") or {}
    if summary.get("coverage_present") != 2 or summary.get("coverage_total") != 5:
        return _fail(f"coverage must be 2/5 on this fixture, got {summary}")

    fresh = compose_fact_card(
        calendar_day=yesterday,
        rows=hist + [y_row],
        user_id="selfcheck",
    )
    if fresh["facts"]["stale"] is not False:
        return _fail("as_of == calendar must not be stale")
    if fresh["facts"]["today"]["steps"] != 14872:
        return _fail("today.steps must bind the point-day row")

    body = stale["notification"]["body"]
    if "14872" not in body or "2026-09-05" not in body:
        return _fail("stale notification must cite as_of steps and day")
    atoms = fact_card_numeric_atoms(stale)
    leaked = {
        n
        for n in re.findall(r"\d+(?:\.\d+)?", body)
        if float(n) >= 100 and n not in atoms and n not in {"2026"}
    }
    if leaked:
        return _fail(f"notification numbers not in card atoms: {leaked}")

    if any("诊断" in a["text"] or "处方" in a["text"] for a in stale["assessment"]["advice"]):
        return _fail("assessment used diagnostic/prescriptive copy")

    print("pha_fact_card_selfcheck: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
