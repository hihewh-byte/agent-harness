#!/usr/bin/env python3
"""M1-P8: migrate mislabeled Apple SDNN from hrv_rmssd_ms / metric_type=hrv → SDNN.

Evidence: zip-era ``wearable_data`` sample_id values are
``HKQuantityTypeIdentifierHeartRateVariabilitySDNN|…`` (or daily mirrors
``default|hrv|…`` built from that series). The warehouse never stored RMSSD.

Idempotent. Prefer ``--dry-run`` first.

  python3 scripts/pha_migrate_hrv_rmssd_to_sdnn.py --dry-run
  python3 scripts/pha_migrate_hrv_rmssd_to_sdnn.py
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

_SDNN_MARK = "HeartRateVariabilitySDNN"


def _db_path() -> Path:
    override = (os.environ.get("PHA_STORAGE_DB") or "").strip()
    if override:
        return Path(override)
    from pha.sqlite_storage import DEFAULT_DB_PATH

    return Path(DEFAULT_DB_PATH)


def _counts(conn: sqlite3.Connection) -> dict[str, int]:
    def n(sql: str) -> int:
        return int(conn.execute(sql).fetchone()[0])

    return {
        "daily_rmssd": n(
            "SELECT COUNT(*) FROM wearable_daily WHERE hrv_rmssd_ms IS NOT NULL"
        ),
        "daily_sdnn": n(
            "SELECT COUNT(*) FROM wearable_daily WHERE hrv_sdnn_ms IS NOT NULL"
        ),
        "daily_rmssd_only": n(
            "SELECT COUNT(*) FROM wearable_daily "
            "WHERE hrv_rmssd_ms IS NOT NULL AND hrv_sdnn_ms IS NULL"
        ),
        "data_hrv": n("SELECT COUNT(*) FROM wearable_data WHERE metric_type='hrv'"),
        "data_hrv_sdnn": n(
            "SELECT COUNT(*) FROM wearable_data WHERE metric_type='hrv_sdnn'"
        ),
        "data_hrv_sdnn_mark": n(
            "SELECT COUNT(*) FROM wearable_data "
            f"WHERE metric_type='hrv' AND sample_id LIKE '%{_SDNN_MARK}%'"
        ),
        "data_hrv_mirror": n(
            "SELECT COUNT(*) FROM wearable_data "
            "WHERE metric_type='hrv' AND ("
            "sample_id LIKE '%|hrv|%' OR sample_id LIKE 'default|hrv|%'"
            ")"
        ),
    }


def migrate(conn: sqlite3.Connection, *, dry_run: bool) -> dict[str, int]:
    before = _counts(conn)
    # 1) Daily: copy mislabeled RMSSD column into SDNN when SDNN empty.
    daily_sql = (
        "UPDATE wearable_daily "
        "SET hrv_sdnn_ms = hrv_rmssd_ms "
        "WHERE hrv_sdnn_ms IS NULL AND hrv_rmssd_ms IS NOT NULL"
    )
    # 2) Sample rows that are Apple SDNN (or daily mirrors of that series).
    data_sql = (
        "UPDATE wearable_data SET metric_type = 'hrv_sdnn' "
        "WHERE metric_type = 'hrv' AND ("
        f"sample_id LIKE '%{_SDNN_MARK}%' "
        "OR sample_id LIKE 'default|hrv|%' "
        "OR sample_id LIKE 'healthkit|%|hrv|%'"
        ")"
    )
    if dry_run:
        return {
            **{f"before_{k}": v for k, v in before.items()},
            "would_copy_daily": before["daily_rmssd_only"],
            "would_relabel_data": before["data_hrv_sdnn_mark"] + before["data_hrv_mirror"],
            "dry_run": 1,
        }
    cur = conn.cursor()
    cur.execute(daily_sql)
    copied = cur.rowcount
    cur.execute(data_sql)
    relabeled = cur.rowcount
    conn.commit()
    after = _counts(conn)
    return {
        **{f"before_{k}": v for k, v in before.items()},
        **{f"after_{k}": v for k, v in after.items()},
        "copied_daily": copied,
        "relabeled_data": relabeled,
        "dry_run": 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    path = _db_path()
    if not path.is_file():
        print(f"FAIL db missing: {path}")
        return 1
    conn = sqlite3.connect(str(path))
    try:
        result = migrate(conn, dry_run=args.dry_run)
    finally:
        conn.close()
    tag = "DRY-RUN" if args.dry_run else "DONE"
    print(f"pha_migrate_hrv_rmssd_to_sdnn: {tag}")
    for key, value in result.items():
        print(f"  {key}={value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
