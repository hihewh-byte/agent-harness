#!/usr/bin/env python3
"""Selfcheck: wearable_metric_registry.json loads and matches CompareTable expectations (3d-δ-c)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pha.wearable_compare_table_v1 import COMPARABLE_METRIC_SPECS, WORKOUT_METRICS
from pha.wearable_metric_registry import (
    comparable_wearable_daily_specs,
    fact_card_eligible_entries,
    fact_card_sync_complete,
    list_ingest_modules,
    load_wearable_metric_registry,
    registry_path,
    workout_compare_metric_ids,
)
from pha.shortcut_find_catalog import (
    DEVICE_VERIFIED,
    find_catalog_entry,
    find_catalog_path,
    never_use_find_labels,
)


def main() -> int:
    errors: list[str] = []
    if not registry_path().is_file():
        errors.append(f"missing registry file: {registry_path()}")
    doc = load_wearable_metric_registry()
    if doc.get("schema_version") != "wearable_metric_registry_v1":
        errors.append(f"unexpected schema_version: {doc.get('schema_version')!r}")

    daily = comparable_wearable_daily_specs()
    if daily != COMPARABLE_METRIC_SPECS:
        errors.append(f"daily specs drift: registry={daily!r} module={COMPARABLE_METRIC_SPECS!r}")

    workout = workout_compare_metric_ids()
    if workout != WORKOUT_METRICS:
        errors.append(f"workout ids drift: registry={workout!r} module={WORKOUT_METRICS!r}")

    if len(daily) < 7:
        errors.append(f"expected >=7 daily comparable metrics, got {len(daily)}")

    if len(list_ingest_modules()):
        errors.append(
            "ingest_modules must be empty (full import only); "
            f"got {[m.get('module_id') for m in list_ingest_modules()]}"
        )

    for entry in fact_card_eligible_entries():
        if not fact_card_sync_complete(entry):
            errors.append(
                f"eligible {entry.get('metric_id')!r} is half-finished: "
                "need ingest_key+shortcut_health_type, sleep value, or shortcut_skip_reason"
            )
        fc = entry.get("fact_card") or {}
        temporal = fc.get("temporal") if isinstance(fc, dict) else None
        if not isinstance(temporal, dict) or not str(temporal.get("kind") or "").strip():
            errors.append(f"eligible {entry.get('metric_id')!r} missing fact_card.temporal.kind")

    pack = str(doc.get("shortcut_pack_version") or "").strip()
    if not pack:
        errors.append("missing shortcut_pack_version")

    if not find_catalog_path().is_file():
        errors.append(f"missing Find catalog: {find_catalog_path()}")
    forbidden = set(never_use_find_labels())
    for entry in fact_card_eligible_entries():
        mid = str(entry.get("metric_id") or "").strip()
        fc = entry.get("fact_card") or {}
        cat = find_catalog_entry(mid)
        if cat is None:
            errors.append(f"eligible {mid!r} missing from shortcut_health_find_catalog.json")
            continue
        skip = str(fc.get("shortcut_skip_reason") or "").strip()
        health_type = str(fc.get("shortcut_health_type") or "").strip()
        sleep_value = str(fc.get("shortcut_sleep_value") or "").strip()
        if skip:
            if str(cat.get("status") or "") != "skipped":
                errors.append(f"{mid!r} has shortcut_skip_reason but catalog status is {cat.get('status')!r}")
            continue
        if str(cat.get("status") or "") != DEVICE_VERIFIED:
            errors.append(
                f"{mid!r} has Find fields but catalog status is {cat.get('status')!r}; "
                "only device_verified may be written into a shortcut"
            )
            continue
        if health_type and health_type in forbidden:
            errors.append(f"{mid!r} uses forbidden Find label {health_type!r}")
        if sleep_value:
            if str(cat.get("shortcut_sleep_value") or "") != sleep_value:
                errors.append(f"{mid!r} sleep value {sleep_value!r} != catalog")
        elif health_type and str(cat.get("shortcut_find_type") or "") != health_type:
            errors.append(
                f"{mid!r} shortcut_health_type {health_type!r} != catalog "
                f"{cat.get('shortcut_find_type')!r}"
            )

    if errors:
        for e in errors:
            print(f"FAIL  {e}")
        return 1
    print("PASS  wearable_metric_registry selfcheck (3d-δ-c)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
