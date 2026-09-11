#!/usr/bin/env python3
"""Selfcheck: unified wearable daily rollup (P1-2)."""

from __future__ import annotations

import sys
from datetime import date, datetime, timedelta
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from pha.models import WearableDailySummary
from pha.wearable_daily_aggregator import (
    WearableDayMetricAgg,
    accumulate_wearable_sample,
    build_wearable_daily_summary,
    resolve_daily_metrics,
    sleep_metrics_from_segment_rows,
)


def test_resolve_daily_metrics_rhr_fallback() -> bool:
    agg = WearableDayMetricAgg(hr_sum=80.0, hr_n=2)
    m = resolve_daily_metrics(agg)
    if m["resting_heart_rate_bpm"] != 40.0:
        print("FAIL rhr fallback from hr", m)
        return False
    agg2 = WearableDayMetricAgg(rhr_sum=55.0, rhr_n=1, hr_sum=80.0, hr_n=2)
    m2 = resolve_daily_metrics(agg2)
    if m2["resting_heart_rate_bpm"] != 55.0:
        print("FAIL rhr prefers METRIC_RHR", m2)
        return False
    print("OK resolve_daily_metrics rhr fallback")
    return True


def test_steps_max_per_source() -> bool:
    agg = WearableDayMetricAgg()
    accumulate_wearable_sample("steps", 1000.0, "a|watch", agg)
    accumulate_wearable_sample("steps", 1200.0, "b|iphone", agg)
    accumulate_wearable_sample("steps", 900.0, "c|watch", agg)
    m = resolve_daily_metrics(agg)
    if m["steps"] != 1900:
        print("FAIL steps max across sources", m["steps"])
        return False
    print("OK steps max per source")
    return True


def test_sleep_segment_roundtrip() -> bool:
    base = datetime(2026, 6, 9, 23, 0, 0)
    deep_end = base + timedelta(hours=1, minutes=30)
    rem_end = deep_end + timedelta(minutes=45)
    awake_end = rem_end + timedelta(minutes=15)
    segment_rows = [
        {
            "start_time": base.isoformat(),
            "end_time": deep_end.isoformat(),
            "source_name": "watch",
            "sample_id": "HKCategoryTypeIdentifierSleepAnalysis|s|e|HKCategoryValueSleepAnalysisAsleepDeep|watch",
            "is_awake": 0,
        },
        {
            "start_time": deep_end.isoformat(),
            "end_time": rem_end.isoformat(),
            "source_name": "watch",
            "sample_id": "HKCategoryTypeIdentifierSleepAnalysis|s|e|HKCategoryValueSleepAnalysisAsleepREM|watch",
            "is_awake": 0,
        },
        {
            "start_time": rem_end.isoformat(),
            "end_time": awake_end.isoformat(),
            "source_name": "watch",
            "sample_id": "HKCategoryTypeIdentifierSleepAnalysis|awake|z",
            "is_awake": 1,
        },
    ]
    sleep_h, awake_h, deep_h, rem_h, first_start = sleep_metrics_from_segment_rows(segment_rows)
    if first_start != base or deep_h is None or rem_h is None or awake_h is None:
        print("FAIL sleep segment roundtrip", sleep_h, awake_h, deep_h, rem_h, first_start)
        return False
    print("OK sleep segment roundtrip")
    return True


def test_build_summary_sleep_only_preserves_metrics() -> bool:
    existing = WearableDailySummary(
        user_id="default",
        day=date(2026, 6, 9),
        steps=8000,
        hrv_rmssd_ms=42.5,
    )
    row = build_wearable_daily_summary(
        "default",
        date(2026, 6, 9),
        existing=existing,
        segment_rows=[],
        sleep_only=True,
    )
    if row.steps != 8000 or row.hrv_rmssd_ms != 42.5:
        print("FAIL sleep_only preserved metrics", row.steps, row.hrv_rmssd_ms)
        return False
    print("OK sleep_only preserves metrics")
    return True


def test_build_matches_legacy_metric_resolution() -> bool:
    """Offline parity: steps/energy are max-by-source (not cross-source sum)."""
    from pha.wearable_daily_aggregator import resolve_additive_by_source

    agg = WearableDayMetricAgg()
    samples = [
        ("steps", 500.0, "x|watch"),
        ("steps", 700.0, "x|watch"),
        ("steps", 600.0, "y|phone"),
        ("rhr", 58.0, "a"),
        ("hrv", 33.0, "b"),
        ("active_energy", 12.5, "z|watch"),
        ("active_energy", 7.5, "z|phone"),
        ("active_energy", 30.0, "z|healthkit"),
        ("spo2", 98.0, "e"),
        ("respiratory_rate", 14.0, "f"),
        ("vo2max", 42.0, "g"),
        ("wrist_temp", 36.5, "h"),
    ]
    for mt, val, sid in samples:
        accumulate_wearable_sample(mt, val, sid, agg)

    resolved = resolve_daily_metrics(agg)
    expected_steps = resolve_additive_by_source(
        {key: float(val) for key, val in agg.steps_by_source.items()}
    )
    expected_kcal = resolve_additive_by_source(agg.active_energy_by_source)
    legacy = {
        "steps": int(round(expected_steps)) if expected_steps is not None else None,
        "resting_heart_rate_bpm": agg.rhr_sum / agg.rhr_n,
        "hrv_rmssd_ms": None,
        "hrv_sdnn_ms": agg.hrv_sdnn_sum / agg.hrv_sdnn_n,
        "active_energy_kcal": expected_kcal,
        "spo2_pct": agg.spo2_sum / agg.spo2_n,
        "respiratory_rate_bpm": agg.respiratory_sum / agg.respiratory_n,
        "vo2max_ml_kg_min": agg.vo2max_sum / agg.vo2max_n,
        "wrist_temp_c": agg.wrist_temp_sum / agg.wrist_temp_n,
    }
    if resolved != legacy:
        print("FAIL legacy metric resolution", resolved, legacy)
        return False
    # watch steps 1200 > phone 600; energy max(watch 12.5, phone 7.5, hk 30) = 30
    row = build_wearable_daily_summary("default", date(2026, 6, 9), metrics=agg)
    if row.steps != 1200 or abs(float(row.active_energy_kcal or 0) - 30.0) > 1e-6:
        print("FAIL build_wearable_daily_summary metrics", row.steps, row.active_energy_kcal)
        return False
    # Undeduped healthkit ≈ watch+phone steps → drop hk, keep max device
    agg2 = WearableDayMetricAgg()
    for mt, val, sid in (
        ("steps", 6862.0, "x|Watch"),
        ("steps", 5792.0, "y|iPhone"),
        ("steps", 12812.0, "z|healthkit"),
        ("active_energy", 343.7, "x|Watch"),
        ("active_energy", 355.6, "z|healthkit"),
    ):
        accumulate_wearable_sample(mt, val, sid, agg2)
    got = resolve_daily_metrics(agg2)
    if got["steps"] != 6862:
        print("FAIL drop undeduped healthkit steps", got["steps"])
        return False
    if abs(float(got["active_energy_kcal"] or 0) - 355.6) > 1e-6:
        print("FAIL energy max(watch, hk)", got["active_energy_kcal"])
        return False
    print("OK legacy metric resolution parity")
    return True


def test_wake_day_for_overnight_segment() -> bool:
    from pha.sleep_wake_day import wake_day_for_segment

    # Pre-midnight Core on Sep 10 belongs to wake day Sep 11
    d = wake_day_for_segment(
        datetime(2026, 9, 10, 23, 26, 0),
        datetime(2026, 9, 10, 23, 49, 0),
    )
    if d != date(2026, 9, 11):
        print("FAIL overnight pre-midnight wake day", d)
        return False
    d2 = wake_day_for_segment(
        datetime(2026, 9, 11, 0, 26, 0),
        datetime(2026, 9, 11, 0, 37, 0),
    )
    if d2 != date(2026, 9, 11):
        print("FAIL post-midnight wake day", d2)
        return False
    d3 = wake_day_for_segment(
        datetime(2026, 9, 10, 7, 50, 0),
        datetime(2026, 9, 10, 7, 51, 0),
    )
    if d3 != date(2026, 9, 10):
        print("FAIL morning wake day", d3)
        return False
    print("OK wake_day_for_segment overnight")
    return True


def test_zip_only_emits_core_via_t2_fields() -> bool:
    """Zip HKCategory rows alone must populate core (same T2 path as HealthKit)."""
    day = date(2026, 9, 10)
    zip_rows = [
        {
            "start_time": "2026-09-10T00:34:20+08:00",
            "end_time": "2026-09-10T05:00:00+08:00",
            "source_name": "Watch",
            "sample_id": (
                "HKCategoryTypeIdentifierSleepAnalysis|a|b|"
                "HKCategoryValueSleepAnalysisAsleepCore|Watch"
            ),
            "is_awake": 0,
        },
        {
            "start_time": "2026-09-10T05:00:00+08:00",
            "end_time": "2026-09-10T06:00:00+08:00",
            "source_name": "Watch",
            "sample_id": (
                "HKCategoryTypeIdentifierSleepAnalysis|c|d|"
                "HKCategoryValueSleepAnalysisAsleepDeep|Watch"
            ),
            "is_awake": 0,
        },
    ]
    row = build_wearable_daily_summary(
        "default",
        day,
        segment_rows=zip_rows,
        sleep_only=True,
    )
    expected_core = (5 * 3600 - (34 * 60 + 20)) / 3600.0
    if row.sleep_core_hours is None or abs(float(row.sleep_core_hours) - expected_core) > 0.02:
        print("FAIL zip-only core", row.sleep_core_hours, "expected", expected_core)
        return False
    if row.sleep_deep_hours is None or abs(float(row.sleep_deep_hours) - 1.0) > 0.01:
        print("FAIL zip-only deep", row.sleep_deep_hours)
        return False
    print("OK zip-only emits core via T2 fields")
    return True


def test_mixed_segments_prefer_healthkit() -> bool:
    """When zip and HealthKit coexist, daily sleep must follow healthkit| (Health app)."""
    day = date(2026, 9, 11)
    # Incomplete zip: missing pre-midnight deep (~37m) — mirrors real 2026-09-11 dual-source night.
    zip_rows = [
        {
            "start_time": "2026-09-11T00:26:08+08:00",
            "end_time": "2026-09-11T00:37:10+08:00",
            "source_name": "Wind’s Apple Watch",
            "sample_id": (
                "HKCategoryTypeIdentifierSleepAnalysis|a|b|"
                "HKCategoryValueSleepAnalysisAsleepCore|Wind’s Apple Watch"
            ),
            "is_awake": 0,
        },
        {
            "start_time": "2026-09-11T06:05:00+08:00",
            "end_time": "2026-09-11T06:23:00+08:00",
            "source_name": "Wind’s Apple Watch",
            "sample_id": (
                "HKCategoryTypeIdentifierSleepAnalysis|c|d|"
                "HKCategoryValueSleepAnalysisAsleepDeep|Wind’s Apple Watch"
            ),
            "is_awake": 0,
        },
    ]
    hk_rows = [
        {
            "start_time": "2026-09-10T23:26:00",
            "end_time": "2026-09-10T23:49:00",
            "source_name": "healthkit",
            "sample_id": "healthkit|default|sleep_core|2026-09-10T23:26:00|2026-09-10T23:49:00|healthkit",
            "is_awake": 0,
        },
        {
            "start_time": "2026-09-10T23:49:00",
            "end_time": "2026-09-11T00:26:00",
            "source_name": "healthkit",
            "sample_id": "healthkit|default|sleep_deep|2026-09-10T23:49:00|2026-09-11T00:26:00|healthkit",
            "is_awake": 0,
        },
        {
            "start_time": "2026-09-11T00:26:00",
            "end_time": "2026-09-11T00:37:00",
            "source_name": "healthkit",
            "sample_id": "healthkit|default|sleep_core|2026-09-11T00:26:00|2026-09-11T00:37:00|healthkit",
            "is_awake": 0,
        },
        {
            "start_time": "2026-09-11T06:05:00",
            "end_time": "2026-09-11T06:23:00",
            "source_name": "healthkit",
            "sample_id": "healthkit|default|sleep_deep|2026-09-11T06:05:00|2026-09-11T06:23:00|healthkit",
            "is_awake": 0,
        },
    ]
    row = build_wearable_daily_summary(
        "default",
        day,
        segment_rows=zip_rows + hk_rows,
        sleep_only=True,
    )
    deep = float(row.sleep_deep_hours or 0.0)
    core = float(row.sleep_core_hours or 0.0)
    # healthkit deep = 37m + 18m = 0.917h; zip-only deep would be 0.3h
    if abs(deep - (37 + 18) / 60.0) > 0.02:
        print("FAIL mixed prefer healthkit deep", row.sleep_deep_hours)
        return False
    if abs(core - (23 + 11) / 60.0) > 0.02:
        print("FAIL mixed prefer healthkit core", row.sleep_core_hours)
        return False
    print("OK mixed segments prefer healthkit|")
    return True


def test_sleep_hours_scalar_fallback() -> bool:
    agg = WearableDayMetricAgg()
    accumulate_wearable_sample("sleep", 7.5, "healthkit|u|sleep|t|healthkit", agg)
    accumulate_wearable_sample("sleep_hours", 6.0, "healthkit|u|sleep|t2|healthkit", agg)
    row = build_wearable_daily_summary(
        "default",
        date(2026, 8, 31),
        metrics=agg,
        segment_rows=[],
    )
    if row.sleep_hours != 7.5:
        print("FAIL scalar sleep fallback expected max 7.5 got", row.sleep_hours)
        return False
    print("OK scalar sleep_hours fallback when no segments")
    return True


def main() -> int:
    ok = all(
        [
            test_resolve_daily_metrics_rhr_fallback(),
            test_steps_max_per_source(),
            test_sleep_segment_roundtrip(),
            test_build_summary_sleep_only_preserves_metrics(),
            test_build_matches_legacy_metric_resolution(),
            test_wake_day_for_overnight_segment(),
            test_zip_only_emits_core_via_t2_fields(),
            test_mixed_segments_prefer_healthkit(),
            test_sleep_hours_scalar_fallback(),
        ],
    )
    print("pha_wearable_daily_aggregator_selfcheck:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
