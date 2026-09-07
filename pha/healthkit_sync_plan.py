"""Which HealthKit types the ingest shortcut may Find — registry + user prefs."""

from __future__ import annotations

from dataclasses import dataclass

from pha.fact_card_prefs import catalog_specs, load_enabled_metric_ids


@dataclass(frozen=True)
class ShortcutSyncSpec:
    metric_id: str
    ingest_key: str
    label: str
    unit: str
    health_type: str
    stat: str
    unit_health: str


def shortcut_sync_specs(user_id: str = "default") -> list[ShortcutSyncSpec]:
    """User-selected ∩ registry rows that have a quantity Find + one-number POST."""
    enabled, _source = load_enabled_metric_ids(user_id)
    wanted = set(enabled)
    out: list[ShortcutSyncSpec] = []
    seen_types: set[str] = set()
    for spec in catalog_specs():
        pulled_in = bool(wanted.intersection(spec.include_when_selected))
        if spec.metric_id not in wanted and not pulled_in:
            continue
        if not spec.ingest_key or not spec.shortcut_health_type:
            continue
        if spec.shortcut_sleep_value:
            continue
        stat = spec.shortcut_stat or "Sum"
        if spec.shortcut_health_type in seen_types:
            continue
        seen_types.add(spec.shortcut_health_type)
        out.append(
            ShortcutSyncSpec(
                metric_id=spec.metric_id,
                ingest_key=spec.ingest_key,
                label=spec.label,
                unit=spec.unit,
                health_type=spec.shortcut_health_type,
                stat=stat,
                unit_health=spec.shortcut_unit or spec.unit,
            )
        )
    out.sort(key=lambda item: (0 if item.stat == "Sum" else 1, item.metric_id))
    return out


def shortcut_sleep_specs(user_id: str = "default") -> list[ShortcutSyncSpec]:
    """User-selected ∩ Sleep Analysis stages: one duration-hour POST each."""
    enabled, _source = load_enabled_metric_ids(user_id)
    wanted = set(enabled)
    out: list[ShortcutSyncSpec] = []
    seen_values: set[str] = set()
    for spec in catalog_specs():
        pulled_in = bool(wanted.intersection(spec.include_when_selected))
        if spec.metric_id not in wanted and not pulled_in:
            continue
        if not spec.ingest_key or not spec.shortcut_sleep_value:
            continue
        if spec.shortcut_sleep_value in seen_values:
            continue
        seen_values.add(spec.shortcut_sleep_value)
        out.append(
            ShortcutSyncSpec(
                metric_id=spec.metric_id,
                ingest_key=spec.ingest_key,
                label=spec.label,
                unit=spec.unit,
                health_type=spec.shortcut_health_type or "Sleep",
                stat=spec.shortcut_stat or "Sum",
                unit_health=spec.shortcut_sleep_value,
            )
        )
    order = ("In Bed", "Asleep Core", "Asleep Deep", "Asleep REM", "Awake", "Asleep")
    rank = {name: idx for idx, name in enumerate(order)}
    out.sort(key=lambda item: (rank.get(item.unit_health, 99), item.metric_id))
    return out


__all__ = ["ShortcutSyncSpec", "shortcut_sleep_specs", "shortcut_sync_specs"]
