#!/usr/bin/env python3
"""M1 batch-2: 19 fact-card metrics; HK docs for agg; Find still unverified."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pha.data_importer import _SUPPORTED_RECORD_TYPES
from pha.health_intent_catalog import infer_metrics_from_message
from pha.models import WearableDailySummary
from pha.healthkit_sync_plan import shortcut_sync_specs
from pha.shortcut_find_catalog import (
    find_catalog_entry,
    never_use_find_labels,
    picker_search_probes,
    quantity_find_allowed,
)
from pha.wearable_daily_aggregator import WearableDayMetricAgg, accumulate_wearable_sample, resolve_daily_metrics
from pha.wearable_metric_registry import (
    clear_registry_cache,
    l1_field_for,
    metric_entry,
    zip_passthrough_rollups,
)
from pha.fact_card_prefs import load_enabled_metric_ids

BATCH2 = (
    "wrist_temp",
    "apple_exercise_time_min",
    "apple_stand_time_min",
    "distance_walking_running_km",
    "walking_hr_avg_bpm",
    "walking_steadiness",
    "time_in_daylight_min",
    "flights_climbed",
    "walking_speed_kmh",
    "six_minute_walk_m",
    "body_mass_kg",
    "body_fat_fraction",
    "physical_effort",
    "basal_energy_kcal",
    "running_speed_kmh",
    "running_power_w",
    "walking_step_length_cm",
    "environmental_audio_db",
    "headphone_audio_db",
)


def _assert(cond: bool, msg: object) -> None:
    if not cond:
        raise AssertionError(msg)


def test_registry_and_find() -> None:
    clear_registry_cache()
    rollups = zip_passthrough_rollups()
    for mid in BATCH2:
        entry = metric_entry(mid) or {}
        fc = entry.get("fact_card") or {}
        _assert(fc.get("eligible") is True, mid)
        _assert(fc.get("enabled_default") is False, mid)
        _assert(str(fc.get("shortcut_skip_reason") or ""), mid)
        _assert(not str(fc.get("shortcut_health_type") or ""), mid)
        cat = find_catalog_entry(mid) or {}
        _assert(str(cat.get("status") or "") == "skipped", (mid, cat.get("status")))
        _assert(not cat.get("shortcut_find_type"), mid)
        probes = picker_search_probes(mid)
        _assert(len(probes) >= 1, (mid, probes))
        for probe in probes:
            _assert(not quantity_find_allowed(mid, probe), (mid, probe))
        if mid == "wrist_temp":
            continue
        hk = str((entry.get("l1") or {}).get("zip_metric_type") or "")
        _assert(hk.startswith("HKQuantityTypeIdentifier"), (mid, hk))
        _assert(hk not in _SUPPORTED_RECORD_TYPES, hk)
        spec = rollups.get(hk)
        _assert(spec is not None, (mid, hk))
        field, how = spec
        _assert(field == l1_field_for(mid), (field, mid))
        _assert(hasattr(WearableDailySummary, field) or field in WearableDailySummary.model_fields, field)
        _assert(how in ("sum", "mean", "max", "latest"), (mid, how))
    print("OK registry eligible; importer allow-set unchanged; Find skipped")


def test_prefs() -> None:
    ids, _src = load_enabled_metric_ids("default")
    for mid in BATCH2:
        _assert(mid in ids, (mid, ids))
    _assert(len(ids) >= 30, len(ids))
    print("OK default prefs include 19 batch-2 ids; n=", len(ids))


def test_sum_not_mean() -> None:
    agg = WearableDayMetricAgg()
    hk = "HKQuantityTypeIdentifierAppleExerciseTime"
    accumulate_wearable_sample(hk, 1.0, "a", agg)
    accumulate_wearable_sample(hk, 1.0, "b", agg)
    out = resolve_daily_metrics(agg)
    _assert(out.get("apple_exercise_time_min") == 2.0, out)
    print("OK exercise minutes daily_agg=sum")


def test_aliases() -> None:
    _assert(infer_metrics_from_message("锻炼分钟怎么样") == ["exercise_minutes"], infer_metrics_from_message("锻炼分钟怎么样"))
    _assert("walking_steadiness" in infer_metrics_from_message("步行稳定性"), infer_metrics_from_message("步行稳定性"))
    _assert("body_mass" in infer_metrics_from_message("体重"), infer_metrics_from_message("体重"))
    print("OK catalog aliases")


def test_verified_find_frozen_and_probes_excluded() -> None:
    frozen = {
        "steps": "Steps",
        "active_energy": "Active Calories",
        "hrv_sdnn_ms": "Heart Rate Variability",
        "resting_heart_rate_bpm": "Resting Heart Rate",
        "spo2_percent": "Oxygen Saturation",
        "respiratory_rate": "Respiratory Rate",
        "vo2max": "VO2 Max",
    }
    for mid, label in frozen.items():
        cat = find_catalog_entry(mid) or {}
        _assert(str(cat.get("status") or "") == "device_verified", mid)
        _assert(str(cat.get("shortcut_find_type") or "") == label, (mid, cat.get("shortcut_find_type")))
    banned = set(never_use_find_labels())
    _assert("Step Count" in banned, banned)
    _assert("Sleep Analysis" in banned, banned)
    _assert(not quantity_find_allowed("steps", "Step Count"), "Step Count must not unlock steps")
    _assert(not quantity_find_allowed("cardio_recovery_1min_bpm", "Cardio Recovery"), "probe is not verified")
    _assert(picker_search_probes("cardio_recovery_1min_bpm"), "cardio probes")
    sync_ids = {s.metric_id for s in shortcut_sync_specs("default")}
    for mid in BATCH2:
        _assert(mid not in sync_ids, mid)
    _assert("cardio_recovery_1min_bpm" not in sync_ids, sync_ids)
    print("OK verified Find frozen; probes excluded from shortcut sync")


def main() -> int:
    test_registry_and_find()
    test_prefs()
    test_sum_not_mean()
    test_aliases()
    test_verified_find_frozen_and_probes_excluded()
    print("pha_m1_batch2_selfcheck: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
