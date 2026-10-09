#!/usr/bin/env python3
"""Wearable time grain: calendar months, sub-month ranges, rolling weeks, episodic anchor scope."""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pha.wearable_time_grain import resolve_wearable_time_grain  # noqa: E402

REF = date(2026, 10, 9)
D = date.fromisoformat

CASES: list[tuple[str, str, str, str]] = [
    ("八月的跑步功率", "calendar_month", "2026-08-01", "2026-08-31"),
    ("8月份呢？", "calendar_month", "2026-08-01", "2026-08-31"),
    ("十一月呢？", "calendar_month", "2025-11-01", "2025-11-30"),
    ("一月份步数", "calendar_month", "2026-01-01", "2026-01-31"),
    ("今年三月", "calendar_month", "2026-03-01", "2026-03-31"),
    ("去年十二月的睡眠", "calendar_month", "2025-12-01", "2025-12-31"),
    ("2025年5月", "calendar_month", "2025-05-01", "2025-05-31"),
    ("那八月最后一周呢？", "calendar_month", "2026-08-25", "2026-08-31"),
    ("9月第一周呢？", "calendar_month", "2026-09-01", "2026-09-07"),
    ("八月中旬", "calendar_month", "2026-08-11", "2026-08-20"),
    ("8月底", "calendar_month", "2026-08-21", "2026-08-31"),
    ("上个月最后一周", "calendar_month", "2026-09-24", "2026-09-30"),
    ("本月第一周", "calendar_month", "2026-10-01", "2026-10-07"),
    ("How was my sleep in August?", "calendar_month", "2026-08-01", "2026-08-31"),
    ("last week of August", "calendar_month", "2026-08-25", "2026-08-31"),
    ("mid September", "calendar_month", "2026-09-11", "2026-09-20"),
    ("最近两周", "rolling_n", "2026-09-26", "2026-10-09"),
    ("past two weeks", "rolling_n", "2026-09-26", "2026-10-09"),
    ("上上周呢？", "time_slot", "2026-09-21", "2026-09-27"),
    ("上周呢？", "time_slot", "2026-09-28", "2026-10-04"),
    ("上上个月", "time_slot", "2026-08-01", "2026-08-31"),
    ("上个月呢？", "time_slot", "2026-09-01", "2026-09-30"),
    ("近一个月", "rolling_keyword", "2026-09-10", "2026-10-09"),
    ("近三月", "rolling_keyword", "2026-07-12", "2026-10-09"),
    ("我8月20日睡得怎么样", "time_slot", "2026-08-20", "2026-08-20"),
    ("May I see my steps?", "default", "2026-07-12", "2026-10-09"),
]


def _focus(metric: str) -> SimpleNamespace:
    return SimpleNamespace(
        focus_grain_start="2026-10-09",
        focus_grain_end="2026-10-09",
        focus_grain_aggregation="point",
        focus_metric=metric,
    )


def main() -> int:
    failures = 0
    for text, source, start, end in CASES:
        g = resolve_wearable_time_grain(text, reference=REF)
        ok = g.source == source and g.start == D(start) and g.end == D(end)
        failures += not ok
        print(f"[{'PASS' if ok else 'FAIL'}] {text} → {g.source} {g.start}~{g.end}")

    anchor_cases = [
        ("核心睡眠是多少？", _focus("sleep"), "episodic_anchor"),
        ("我的跑步功率怎么样？", _focus("time_in_daylight"), "default"),
        ("我的跑步功率怎么样？", _focus(""), "default"),
        ("那跑步功率呢？", _focus("time_in_daylight"), "episodic_anchor"),
    ]
    for text, focus, source in anchor_cases:
        g = resolve_wearable_time_grain(text, reference=REF, episodic=focus)
        ok = g.source == source
        failures += not ok
        print(f"[{'PASS' if ok else 'FAIL'}] anchor {text} (focus={focus.focus_metric or '-'}) → {g.source}")

    print("pha_wearable_time_grain_selfcheck: " + ("PASS" if not failures else f"FAIL ({failures})"))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
