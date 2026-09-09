"""Wearable Metric Registry — config-driven CompareTable & ingest modules (Wave 3d-δ-c)."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Tuple

_REGISTRY_PATH = (
    Path(__file__).resolve().parent.parent / "storage" / "registry" / "wearable_metric_registry.json"
)

MetricTriple = Tuple[str, str, str]


@lru_cache(maxsize=1)
def load_wearable_metric_registry() -> Dict[str, Any]:
    if not _REGISTRY_PATH.is_file():
        return {"schema_version": "wearable_metric_registry_v1", "metrics": [], "ingest_modules": []}
    with _REGISTRY_PATH.open(encoding="utf-8") as fh:
        return json.load(fh)


def registry_path() -> Path:
    return _REGISTRY_PATH


def list_metric_entries() -> List[Dict[str, Any]]:
    doc = load_wearable_metric_registry()
    metrics = doc.get("metrics") or []
    return [m for m in metrics if isinstance(m, dict) and m.get("metric_id")]


def metric_entry(metric_id: str) -> Optional[Dict[str, Any]]:
    mid = (metric_id or "").strip()
    for m in list_metric_entries():
        if str(m.get("metric_id") or "").strip() == mid:
            return m
    return None


def comparable_wearable_daily_specs() -> Tuple[MetricTriple, ...]:
    """(metric_id, wearable_daily field, snapshot unit) for 90d warehouse rollups."""
    out: List[MetricTriple] = []
    for m in list_metric_entries():
        l1 = m.get("l1") or {}
        if str(l1.get("kind") or "") != "wearable_daily":
            continue
        compare = m.get("compare") or {}
        if not compare.get("comparable_90d"):
            continue
        field = str(l1.get("field") or "").strip()
        unit = str((m.get("snapshot") or {}).get("unit") or "").strip()
        mid = str(m.get("metric_id") or "").strip()
        if mid and field:
            out.append((mid, field, unit))
    return tuple(out)


def workout_compare_metric_ids() -> Tuple[str, ...]:
    out: List[str] = []
    for m in list_metric_entries():
        l1 = m.get("l1") or {}
        if str(l1.get("kind") or "") != "workout_sessions":
            continue
        compare = m.get("compare") or {}
        if not compare.get("conditional_row"):
            continue
        mid = str(m.get("metric_id") or "").strip()
        if mid:
            out.append(mid)
    return tuple(out)


def snapshot_only_fallback_metric_ids() -> Tuple[str, ...]:
    """Daily metrics that emit snapshot_only row when OCR has value but warehouse has no baseline."""
    out: List[str] = []
    for m in list_metric_entries():
        compare = m.get("compare") or {}
        if not compare.get("snapshot_only_if_no_baseline"):
            continue
        mid = str(m.get("metric_id") or "").strip()
        if mid:
            out.append(mid)
    return tuple(out)


def metric_labels_zh() -> Dict[str, str]:
    labels: Dict[str, str] = {}
    for m in list_metric_entries():
        mid = str(m.get("metric_id") or "").strip()
        zh = str((m.get("ui") or {}).get("label_zh") or "").strip()
        if mid and zh:
            labels[mid] = zh
    return labels


_METRIC_LABEL_EN_FALLBACK: Dict[str, str] = {
    "sleep_time_asleep": "Sleep duration",
    "hrv_rmssd_ms": "HRV (legacy)",
    "hrv_sdnn_ms": "HRV",
    "resting_heart_rate_bpm": "Resting HR",
    "spo2_percent": "SpO2",
    "respiratory_rate": "Respiratory rate",
    "sleep_deep": "Deep sleep",
    "sleep_rem": "REM",
    "workout_heart_rate_range_bpm": "Workout HR range",
    "workout_count_recent": "Recent workout days",
}


def metric_labels_en() -> Dict[str, str]:
    labels: Dict[str, str] = {}
    for m in list_metric_entries():
        mid = str(m.get("metric_id") or "").strip()
        en = str((m.get("ui") or {}).get("label_en") or "").strip()
        if mid and en:
            labels[mid] = en
    for mid, fallback in _METRIC_LABEL_EN_FALLBACK.items():
        labels.setdefault(mid, fallback)
    return labels


def _catalog_block(entry: Mapping[str, Any] | None) -> Dict[str, Any]:
    raw = (entry or {}).get("catalog") or {}
    return dict(raw) if isinstance(raw, dict) else {}


def catalog_key_for(metric_id: str) -> Optional[str]:
    entry = metric_entry(metric_id)
    key = str(_catalog_block(entry).get("key") or "").strip()
    return key or None


def metric_ids_for_catalog_key(key: str) -> Tuple[str, ...]:
    want = (key or "").strip()
    if not want:
        return ()
    out: List[str] = []
    for m in list_metric_entries():
        cat = _catalog_block(m)
        if cat.get("hidden"):
            continue
        if str(cat.get("key") or "").strip() == want:
            mid = str(m.get("metric_id") or "").strip()
            if mid:
                out.append(mid)
    return tuple(out)


def cluster_of(metric_id: str) -> Optional[str]:
    cid = str(_catalog_block(metric_entry(metric_id)).get("cluster") or "").strip()
    return cid or None


def cluster_members(cluster_id: str, *, expand_only: bool = True) -> Tuple[str, ...]:
    want = (cluster_id or "").strip()
    if not want:
        return ()
    out: List[str] = []
    for m in list_metric_entries():
        cat = _catalog_block(m)
        if cat.get("hidden"):
            continue
        if str(cat.get("cluster") or "").strip() != want:
            continue
        if expand_only and not cat.get("expand_on_cluster_query"):
            continue
        mid = str(m.get("metric_id") or "").strip()
        if mid:
            out.append(mid)
    return tuple(out)


def cluster_primary_metric_id(cluster_id: str) -> Optional[str]:
    want = (cluster_id or "").strip()
    if not want:
        return None
    for m in list_metric_entries():
        cat = _catalog_block(m)
        if cat.get("hidden"):
            continue
        if str(cat.get("cluster") or "").strip() != want:
            continue
        if cat.get("cluster_primary"):
            mid = str(m.get("metric_id") or "").strip()
            if mid:
                return mid
    return None


def primary_metric_id_for_catalog_key(key: str) -> Optional[str]:
    ids = metric_ids_for_catalog_key(key)
    for mid in ids:
        if _catalog_block(metric_entry(mid)).get("cluster_primary"):
            return mid
    return ids[0] if ids else None


@dataclass(frozen=True)
class CatalogLabels:
    point_zh: str
    span_zh: str
    that_day_zh: str
    point_en: str
    span_en: str
    that_day_en: str
    stem_zh: str
    stem_en: str


def catalog_labels(metric_id: str) -> Optional[CatalogLabels]:
    entry = metric_entry(metric_id)
    cat = _catalog_block(entry)
    stem_zh = str(cat.get("label_zh") or "").strip()
    stem_en = str(cat.get("label_en") or "").strip()
    if not stem_zh or not stem_en:
        return None
    mean_suffix = str(cat.get("mean_suffix_zh") or "均值").strip() or "均值"
    return CatalogLabels(
        point_zh=str(cat.get("point_zh") or f"今日{stem_zh}").strip(),
        span_zh=str(cat.get("span_zh") or f"{stem_zh}{mean_suffix}").strip(),
        that_day_zh=str(cat.get("that_day_zh") or f"当日{stem_zh}").strip(),
        point_en=str(cat.get("point_en") or f"Today's {stem_en}").strip(),
        span_en=str(cat.get("span_en") or f"Mean {stem_en}").strip(),
        that_day_en=str(cat.get("that_day_en") or f"{stem_en} that day").strip(),
        stem_zh=stem_zh,
        stem_en=stem_en,
    )


def catalog_keys_canonical() -> Tuple[str, ...]:
    doc = load_wearable_metric_registry()
    declared = (doc.get("bundle_catalog") or {}).get("canonical")
    if isinstance(declared, list) and declared:
        return tuple(str(x).strip() for x in declared if str(x).strip())
    seen: List[str] = []
    for m in list_metric_entries():
        cat = _catalog_block(m)
        if cat.get("hidden"):
            continue
        key = str(cat.get("key") or "").strip()
        if key and key not in seen:
            seen.append(key)
    return tuple(seen)


def catalog_keys_core() -> Tuple[str, ...]:
    doc = load_wearable_metric_registry()
    declared = (doc.get("bundle_catalog") or {}).get("core")
    if isinstance(declared, list) and declared:
        return tuple(str(x).strip() for x in declared if str(x).strip())
    seen: List[str] = []
    for m in fact_card_eligible_entries():
        fc = m.get("fact_card") or {}
        if not fc.get("enabled_default"):
            continue
        cat = _catalog_block(m)
        if cat.get("hidden"):
            continue
        key = str(cat.get("key") or "").strip()
        if key and key not in seen:
            seen.append(key)
    return tuple(seen)


def wearable_daily_metric_ids() -> Tuple[str, ...]:
    out: List[str] = []
    for m in list_metric_entries():
        l1 = m.get("l1") or {}
        if str(l1.get("kind") or "") != "wearable_daily":
            continue
        mid = str(m.get("metric_id") or "").strip()
        if mid:
            out.append(mid)
    return tuple(out)


def l1_field_for(metric_id: str) -> Optional[str]:
    entry = metric_entry(metric_id)
    if not entry:
        return None
    field = str((entry.get("l1") or {}).get("field") or "").strip()
    return field or None


def display_fallback_metric_id(metric_id: str) -> Optional[str]:
    entry = metric_entry(metric_id)
    if not entry:
        return None
    fc = entry.get("fact_card") or {}
    raw = str(fc.get("display_fallback_metric_id") or "").strip() if isinstance(fc, dict) else ""
    return raw or None


def catalog_unit_for(metric_id: str) -> str:
    entry = metric_entry(metric_id)
    if not entry:
        return ""
    fc = entry.get("fact_card") or {}
    if isinstance(fc, dict):
        unit = str(fc.get("unit") or "").strip()
        if unit:
            return unit
    return str((entry.get("snapshot") or {}).get("unit") or "").strip()


_CJK_RE = re.compile(r"[\u4e00-\u9fff]")


def hint_match_metric_ids(user_message: str) -> Tuple[str, ...]:
    msg = user_message or ""
    blob = msg.lower()
    matches: List[tuple[str, str]] = []
    for mid, hints in metric_mention_hints().items():
        for h in hints:
            token = (h or "").strip()
            if not token:
                continue
            needle = token.lower()
            if _CJK_RE.search(token):
                hit = token in msg
            else:
                hit = needle in blob
            if hit:
                matches.append((mid, token))
                break
    kept: List[str] = []
    found: set[str] = set()
    for mid, token in matches:
        absorbed = False
        for other_mid, other in matches:
            if other_mid == mid:
                continue
            if token != other and token in other:
                absorbed = True
                break
        if absorbed:
            continue
        if mid not in found:
            found.add(mid)
            kept.append(mid)
    return tuple(kept)


def bundle_trigger_keywords() -> List[Dict[str, str]]:
    """Derive wearable_bundle trigger_keywords from Registry hints × catalog.key."""
    out: List[Dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for m in list_metric_entries():
        cat = _catalog_block(m)
        if cat.get("hidden"):
            continue
        key = str(cat.get("key") or "").strip()
        zh = str(cat.get("label_zh") or "").strip()
        if not key:
            continue
        hints = m.get("intent_hints") or []
        if not isinstance(hints, list):
            continue
        for raw in hints:
            token = str(raw or "").strip()
            if not token:
                continue
            pair = (token, key)
            if pair in seen:
                continue
            seen.add(pair)
            out.append({"token": token, "metric_id": key, "zh": zh or key})
    return out


def bundle_core_hint_keywords() -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    for key in catalog_keys_core()[:3]:
        mid = primary_metric_id_for_catalog_key(key)
        labels = catalog_labels(mid) if mid else None
        zh = labels.stem_zh if labels else key
        out.append({"zh": zh, "metric_id": key})
    return out


def registry_catalog_enabled() -> bool:
    raw = (os.environ.get("PHA_WEARABLE_REGISTRY_CATALOG") or "1").strip().lower()
    if raw in ("0", "false", "no"):
        raise RuntimeError("legacy path removed; rollback by git")
    return True


def cluster_expand_enabled() -> bool:
    return (os.environ.get("PHA_WEARABLE_CLUSTER_EXPAND") or "1").strip().lower() not in (
        "0",
        "false",
        "no",
    )


def metric_mention_hints() -> Dict[str, Tuple[str, ...]]:
    hints: Dict[str, Tuple[str, ...]] = {}
    for m in list_metric_entries():
        mid = str(m.get("metric_id") or "").strip()
        raw = m.get("intent_hints") or []
        if mid and isinstance(raw, list):
            hints[mid] = tuple(str(x) for x in raw if str(x).strip())
    return hints


def metrics_footer_when_snapshot_only() -> frozenset[str]:
    ids: List[str] = []
    for m in list_metric_entries():
        if not (m.get("ui") or {}).get("footer_when_snapshot_only"):
            continue
        mid = str(m.get("metric_id") or "").strip()
        if mid:
            ids.append(mid)
    return frozenset(ids)


def list_ingest_modules() -> List[Dict[str, Any]]:
    doc = load_wearable_metric_registry()
    modules = doc.get("ingest_modules") or []
    return [x for x in modules if isinstance(x, dict) and x.get("module_id")]


def ingest_module(module_id: str) -> Optional[Dict[str, Any]]:
    mid = (module_id or "").strip()
    for m in list_ingest_modules():
        if str(m.get("module_id") or "").strip() == mid:
            return m
    return None


def is_registered_comparable_metric(metric_id: str) -> bool:
    entry = metric_entry(metric_id)
    if not entry:
        return False
    return bool((entry.get("compare") or {}).get("comparable_90d"))


def shortcut_pack_version() -> str:
    doc = load_wearable_metric_registry()
    raw = str(doc.get("shortcut_pack_version") or doc.get("version") or "").strip()
    return raw or "unknown"


def fact_card_sync_complete(entry: Mapping[str, Any]) -> bool:
    """Eligible row must be shortcut-complete or explicitly skipped."""
    fc = entry.get("fact_card") or {}
    if not isinstance(fc, dict) or not fc.get("eligible"):
        return True
    if str(fc.get("shortcut_skip_reason") or "").strip():
        return True
    if str(fc.get("shortcut_sleep_value") or "").strip() and str(fc.get("ingest_key") or "").strip():
        return True
    if str(fc.get("shortcut_health_type") or "").strip() and str(fc.get("ingest_key") or "").strip():
        return True
    return False


def fact_card_eligible_entries() -> List[Dict[str, Any]]:
    """Daily metrics the fact card may render. Selection is user prefs, not code lists."""
    out: List[Dict[str, Any]] = []
    for m in list_metric_entries():
        fc = m.get("fact_card") or {}
        if not isinstance(fc, dict) or not fc.get("eligible"):
            continue
        l1 = m.get("l1") or {}
        if str(l1.get("kind") or "") != "wearable_daily":
            continue
        field = str(l1.get("field") or "").strip()
        mid = str(m.get("metric_id") or "").strip()
        if mid and field:
            out.append(m)
    return out


def default_fact_card_metric_ids() -> Tuple[str, ...]:
    ids: List[str] = []
    for m in fact_card_eligible_entries():
        fc = m.get("fact_card") or {}
        if fc.get("enabled_default"):
            mid = str(m.get("metric_id") or "").strip()
            if mid:
                ids.append(mid)
    return tuple(ids)


def fact_card_daily_ingest_keys() -> Tuple[str, ...]:
    """ingest_key values that use one HealthKit row per calendar day."""
    keys: List[str] = []
    for m in fact_card_eligible_entries():
        fc = m.get("fact_card") or {}
        if not fc.get("daily_key"):
            continue
        key = str(fc.get("ingest_key") or "").strip()
        if key:
            keys.append(key)
    return tuple(keys)


def clear_registry_cache() -> None:
    load_wearable_metric_registry.cache_clear()
    from pha.shortcut_find_catalog import clear_find_catalog_cache

    clear_find_catalog_cache()


__all__ = [
    "CatalogLabels",
    "bundle_core_hint_keywords",
    "bundle_trigger_keywords",
    "catalog_key_for",
    "catalog_keys_canonical",
    "catalog_keys_core",
    "catalog_labels",
    "catalog_unit_for",
    "clear_registry_cache",
    "cluster_expand_enabled",
    "cluster_members",
    "cluster_of",
    "cluster_primary_metric_id",
    "comparable_wearable_daily_specs",
    "default_fact_card_metric_ids",
    "display_fallback_metric_id",
    "fact_card_daily_ingest_keys",
    "fact_card_eligible_entries",
    "fact_card_sync_complete",
    "hint_match_metric_ids",
    "shortcut_pack_version",
    "ingest_module",
    "is_registered_comparable_metric",
    "l1_field_for",
    "list_ingest_modules",
    "list_metric_entries",
    "load_wearable_metric_registry",
    "metric_entry",
    "metric_ids_for_catalog_key",
    "metric_labels_en",
    "metric_labels_zh",
    "metric_mention_hints",
    "metrics_footer_when_snapshot_only",
    "primary_metric_id_for_catalog_key",
    "registry_catalog_enabled",
    "registry_path",
    "snapshot_only_fallback_metric_ids",
    "wearable_daily_metric_ids",
    "workout_compare_metric_ids",
]
