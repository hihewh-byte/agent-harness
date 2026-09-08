"""Which HealthKit types the ingest shortcut may Find — registry only (FR-1.5 v1.7).

``user_id`` is kept on the public functions so existing callers do not break.
The body does not read prefs: shortcuts sync the registry universe, the fact
card filters display by user selection.
"""

from __future__ import annotations

from dataclasses import dataclass

from pha.fact_card_prefs import catalog_specs
from pha.shortcut_find_catalog import quantity_find_allowed, sleep_find_allowed


@dataclass(frozen=True)
class ShortcutSyncSpec:
    metric_id: str
    ingest_key: str
    label: str
    unit: str
    health_type: str
    stat: str
    unit_health: str
    temporal_kind: str = ""
    freshness_days: int = 2


def shortcut_sync_specs(user_id: str = "default") -> list[ShortcutSyncSpec]:
    """Quantity Finds: registry row ∩ Find catalog ``device_verified``.

    Independent of user selection (FR-1.5 v1.7). Sleep stages are excluded
    (they belong to the sleep shortcut). Guessed / skipped Find labels never
    enter a shortcut — look up ``shortcut_health_find_catalog.json`` first.
    """
    del user_id
    out: list[ShortcutSyncSpec] = []
    seen_types: set[str] = set()
    for spec in catalog_specs():
        if spec.shortcut_skip_reason:
            continue
        if not spec.ingest_key or not spec.shortcut_health_type:
            continue
        if spec.shortcut_sleep_value:
            continue
        if not quantity_find_allowed(spec.metric_id, spec.shortcut_health_type):
            continue
        if spec.shortcut_health_type in seen_types:
            continue
        seen_types.add(spec.shortcut_health_type)
        temporal = spec.temporal or {}
        out.append(
            ShortcutSyncSpec(
                metric_id=spec.metric_id,
                ingest_key=spec.ingest_key,
                label=spec.label,
                unit=spec.unit,
                health_type=spec.shortcut_health_type,
                stat=spec.shortcut_stat or "Sum",
                unit_health=spec.shortcut_unit or spec.unit,
                temporal_kind=str(temporal.get("kind") or ""),
                freshness_days=int(temporal.get("freshness_days") or 2),
            )
        )
    out.sort(key=lambda item: (0 if item.stat == "Sum" else 1, item.metric_id))
    return out


def shortcut_sleep_specs(user_id: str = "default") -> list[ShortcutSyncSpec]:
    """Full sleep-stage pack from the registry (FR-1.6). Independent of prefs."""
    del user_id
    out: list[ShortcutSyncSpec] = []
    seen_values: set[str] = set()
    for spec in catalog_specs():
        if spec.shortcut_skip_reason:
            continue
        if not spec.ingest_key or not spec.shortcut_sleep_value:
            continue
        if not sleep_find_allowed(spec.metric_id, spec.shortcut_sleep_value):
            continue
        if spec.shortcut_sleep_value in seen_values:
            continue
        seen_values.add(spec.shortcut_sleep_value)
        temporal = spec.temporal or {}
        out.append(
            ShortcutSyncSpec(
                metric_id=spec.metric_id,
                ingest_key=spec.ingest_key,
                label=spec.label,
                unit=spec.unit,
                health_type=spec.shortcut_health_type or "Sleep",
                stat=spec.shortcut_stat or "Sum",
                unit_health=spec.shortcut_sleep_value,
                temporal_kind=str(temporal.get("kind") or "overnight"),
                freshness_days=int(temporal.get("freshness_days") or 2),
            )
        )
    order = ("In Bed", "Asleep Core", "Asleep Deep", "Asleep REM", "Awake", "Asleep")
    rank = {name: idx for idx, name in enumerate(order)}
    out.sort(key=lambda item: (rank.get(item.unit_health, 99), item.metric_id))
    return out


__all__ = ["ShortcutSyncSpec", "shortcut_sleep_specs", "shortcut_sync_specs"]
