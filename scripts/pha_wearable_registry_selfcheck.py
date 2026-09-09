#!/usr/bin/env python3
"""Selfcheck: wearable_metric_registry.json loads and matches CompareTable expectations (3d-δ-c)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pha.wearable_compare_table_v1 import COMPARABLE_METRIC_SPECS, WORKOUT_METRICS
from pha.wearable_metric_registry import (
    catalog_key_for,
    catalog_keys_canonical,
    catalog_labels,
    comparable_wearable_daily_specs,
    fact_card_eligible_entries,
    fact_card_sync_complete,
    list_ingest_modules,
    list_metric_entries,
    load_wearable_metric_registry,
    metric_ids_for_catalog_key,
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

    import re

    _cjk = re.compile(r"[\u4e00-\u9fff]")
    _latin = re.compile(r"[A-Za-z]")
    cluster_primary: dict[str, list[str]] = {}
    catalog_keys: set[str] = set()
    for entry in list_metric_entries():
        mid = str(entry.get("metric_id") or "").strip()
        cat = entry.get("catalog") or {}
        if not isinstance(cat, dict) or not cat:
            continue
        key = str(cat.get("key") or "").strip()
        if key:
            catalog_keys.add(key)
        if cat.get("hidden"):
            continue
        if key and (not str(cat.get("label_zh") or "").strip() or not str(cat.get("label_en") or "").strip()):
            errors.append(f"{mid!r} catalog.label_zh/label_en must both be set")
        if catalog_labels(mid) is None and key:
            errors.append(f"{mid!r} catalog_labels() missing")
        hints = [str(h) for h in (entry.get("intent_hints") or []) if str(h).strip()]
        if key and (
            not any(_cjk.search(h) for h in hints) or not any(_latin.search(h) for h in hints)
        ):
            errors.append(f"{mid!r} intent_hints must include CJK and Latin tokens")
        cid = str(cat.get("cluster") or "").strip()
        if cid and cat.get("cluster_primary"):
            cluster_primary.setdefault(cid, []).append(mid)

    for cid, mids in cluster_primary.items():
        if len(mids) != 1:
            errors.append(f"cluster {cid!r} must have exactly one primary, got {mids}")

    bundle_path = ROOT / "storage" / "schemas" / "wearable_bundle.schema.json"
    if bundle_path.is_file():
        bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
        canonical = set((bundle.get("metrics") or {}).get("canonical") or [])
        missing = canonical - catalog_keys
        if missing:
            errors.append(f"registry catalog.key missing bundle canonical {sorted(missing)}")

    import subprocess

    gen = ROOT / "scripts" / "pha_wearable_bundle_schema_generate.py"
    check = subprocess.run([sys.executable, str(gen), "--check"], capture_output=True, text=True)
    if check.returncode != 0:
        errors.append(
            "wearable_bundle.schema.json drifted; run pha_wearable_bundle_schema_generate.py --write"
        )

    if errors:
        for e in errors:
            print(f"FAIL  {e}")
        return 1
    print("PASS  wearable_metric_registry selfcheck (3d-δ-c)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
