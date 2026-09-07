#!/usr/bin/env python3
"""T5: list or delete leftover HealthKit sleep daily-key rows for one wake day.

Only touches ``sample_id LIKE 'healthkit|%'`` sleep-family metrics.
Does not delete zip / noon-mirror rows.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    parser = argparse.ArgumentParser(description="Clean HealthKit sleep daily-key leftovers")
    parser.add_argument("--day", required=True, help="Wake day YYYY-MM-DD")
    parser.add_argument("--user-id", default="default")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        day = date.fromisoformat(args.day)
    except ValueError:
        print("FAIL unreadable --day", args.day)
        return 2

    from pha.sqlite_storage import (
        delete_healthkit_sleep_family_on_day,
        list_healthkit_sleep_family_on_day,
        query_wearable_daily_range,
        rebuild_wearable_daily_for_days,
    )

    rows = list_healthkit_sleep_family_on_day(args.user_id, day)
    print(f"day={day.isoformat()} user_id={args.user_id} healthkit_sleep_rows={len(rows)}")
    for row in rows:
        print(
            f"  {row.get('sample_id')} metric={row.get('metric_type')} "
            f"ts={row.get('timestamp')} value={row.get('value')}"
        )
    if args.dry_run:
        print("dry-run: no delete")
        return 0
    deleted = delete_healthkit_sleep_family_on_day(args.user_id, day)
    rebuilt = rebuild_wearable_daily_for_days(args.user_id, [day])
    daily = query_wearable_daily_range(args.user_id, day, day)
    print(f"deleted={deleted} days_rebuilt={rebuilt}")
    if daily:
        row = daily[0]
        print(
            "daily "
            f"sleep={row.sleep_hours} core={row.sleep_core_hours} "
            f"deep={row.sleep_deep_hours} rem={row.sleep_rem_hours} "
            f"awake={row.awake_duration_hours} in_bed={row.in_bed_hours}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
