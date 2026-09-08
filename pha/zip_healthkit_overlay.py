"""Zip import is the ledger truth; HealthKit incrementals on overlapping days are dropped."""

from __future__ import annotations

import json
import logging
import os
import tempfile
from datetime import date, datetime
from pathlib import Path
from typing import Any, Optional, Sequence

from pha.models import WearableDailySummary
from pha.sqlite_storage import (
    delete_healthkit_through_day,
    query_healthkit_metric_on_day,
    query_healthkit_days,
    rebuild_wearable_daily_for_days,
)

logger = logging.getLogger(__name__)

_COMPARE_FIELDS: tuple[tuple[str, str], ...] = (
    ("steps", "steps"),
    ("resting_heart_rate_bpm", "rhr"),
    ("hrv_sdnn_ms", "hrv_sdnn"),
    ("active_energy_kcal", "active_energy"),
    ("spo2_pct", "spo2"),
    ("respiratory_rate_bpm", "respiratory_rate"),
    ("vo2max_ml_kg_min", "vo2max"),
    ("wrist_temp_c", "wrist_temp"),
    ("sleep_hours", "sleep"),
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def reconcile_report_path() -> Path:
    override = (os.environ.get("PHA_ZIP_HK_RECONCILE") or "").strip()
    if override:
        return Path(override)
    return _repo_root() / "data" / "zip_vs_healthkit_reconcile.json"


def _rel_ok(zip_value: float, hk_value: float, *, field: str) -> bool:
    if field == "steps":
        return abs(zip_value - hk_value) <= max(50.0, 0.02 * max(abs(zip_value), 1.0))
    if field in {"sleep_hours", "sleep_deep_hours"}:
        return abs(zip_value - hk_value) <= 0.2
    return abs(zip_value - hk_value) <= max(0.5, 0.05 * max(abs(zip_value), 1.0))


def build_zip_healthkit_reconcile(
    user_id: str,
    zip_rows: Sequence[WearableDailySummary],
) -> dict[str, Any]:
    uid = (user_id or "default").strip() or "default"
    mismatches: list[dict[str, Any]] = []
    compared = 0
    for row in zip_rows:
        for field, metric in _COMPARE_FIELDS:
            zip_raw = getattr(row, field, None)
            if zip_raw is None:
                continue
            hk = query_healthkit_metric_on_day(uid, metric, row.day)
            if hk is None:
                continue
            compared += 1
            zip_v = float(zip_raw)
            if _rel_ok(zip_v, hk, field=field):
                continue
            mismatches.append(
                {
                    "day": row.day.isoformat(),
                    "field": field,
                    "zip": zip_v,
                    "healthkit": hk,
                }
            )
    return {
        "user_id": uid,
        "at": datetime.now().replace(microsecond=0).isoformat(),
        "zip_days": len(zip_rows),
        "compared": compared,
        "mismatch_count": len(mismatches),
        "mismatches": mismatches[:200],
    }


def write_reconcile_report(payload: dict[str, Any]) -> Path:
    path = reconcile_report_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    fd, tmp = tempfile.mkstemp(prefix="zip-hk-reconcile.", suffix=".json", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
        os.replace(tmp, path)
    except Exception:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise
    return path


def apply_zip_wins_overlay(
    user_id: str,
    *,
    xml_max_dt: Optional[datetime],
    zip_rows: Sequence[WearableDailySummary],
) -> dict[str, Any]:
    """Drop HealthKit rows on days the zip snapshot covers; rebuild leftover incrementals."""
    uid = (user_id or "default").strip() or "default"
    report = build_zip_healthkit_reconcile(uid, zip_rows)
    path = write_reconcile_report(report)
    through = xml_max_dt.date() if xml_max_dt is not None else None
    if through is None and zip_rows:
        through = max(row.day for row in zip_rows)
    deleted = 0
    if through is not None:
        deleted = delete_healthkit_through_day(uid, through)
    leftover = [
        day
        for day in query_healthkit_days(uid)
        if through is None or day > through
    ]
    rebuilt = rebuild_wearable_daily_for_days(uid, leftover) if leftover else 0
    logger.info(
        "zip_wins user=%s through=%s deleted_hk=%s leftover_days=%s rebuilt=%s mismatches=%s report=%s",
        uid,
        through.isoformat() if through else None,
        deleted,
        len(leftover),
        rebuilt,
        report.get("mismatch_count"),
        path,
    )
    report["healthkit_deleted"] = deleted
    report["through_day"] = through.isoformat() if through else None
    report["leftover_healthkit_days"] = [d.isoformat() for d in leftover]
    write_reconcile_report(report)
    return report


__all__ = [
    "apply_zip_wins_overlay",
    "build_zip_healthkit_reconcile",
    "reconcile_report_path",
]
