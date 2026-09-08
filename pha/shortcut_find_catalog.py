"""Find Health Samples labels — device-verified catalog is the only source.

Registry ``shortcut_health_type`` must copy a ``device_verified`` row.
Guessed SDK / Health-app titles never enter a shortcut.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional

_CATALOG_PATH = (
    Path(__file__).resolve().parent.parent
    / "storage"
    / "registry"
    / "shortcut_health_find_catalog.json"
)

DEVICE_VERIFIED = "device_verified"
SKIPPED = "skipped"
GUESSED = "guessed"


@lru_cache(maxsize=1)
def load_shortcut_find_catalog() -> Dict[str, Any]:
    if not _CATALOG_PATH.is_file():
        return {
            "schema_version": "shortcut_health_find_catalog_v1",
            "never_use_find_labels": [],
            "entries": [],
        }
    with _CATALOG_PATH.open(encoding="utf-8") as fh:
        return json.load(fh)


def find_catalog_path() -> Path:
    return _CATALOG_PATH


def never_use_find_labels() -> tuple[str, ...]:
    doc = load_shortcut_find_catalog()
    raw = doc.get("never_use_find_labels") or []
    return tuple(str(x).strip() for x in raw if str(x).strip())


def list_find_catalog_entries() -> list[dict[str, Any]]:
    doc = load_shortcut_find_catalog()
    entries = doc.get("entries") or []
    return [e for e in entries if isinstance(e, dict) and e.get("metric_id")]


def find_catalog_entry(metric_id: str) -> Optional[dict[str, Any]]:
    mid = (metric_id or "").strip()
    if not mid:
        return None
    for entry in list_find_catalog_entries():
        if str(entry.get("metric_id") or "").strip() == mid:
            return entry
    return None


def quantity_find_allowed(metric_id: str, health_type: str) -> bool:
    """True only when the quantity Find label is device-verified for this metric."""
    label = (health_type or "").strip()
    if not label or label in never_use_find_labels():
        return False
    entry = find_catalog_entry(metric_id)
    if not entry:
        return False
    if str(entry.get("status") or "") != DEVICE_VERIFIED:
        return False
    if str(entry.get("channel") or "") != "quantity":
        return False
    return str(entry.get("shortcut_find_type") or "").strip() == label


def sleep_find_allowed(metric_id: str, sleep_value: str) -> bool:
    value = (sleep_value or "").strip()
    if not value:
        return False
    entry = find_catalog_entry(metric_id)
    if not entry:
        return False
    if str(entry.get("status") or "") != DEVICE_VERIFIED:
        return False
    if str(entry.get("channel") or "") != "sleep":
        return False
    return str(entry.get("shortcut_sleep_value") or "").strip() == value


def clear_find_catalog_cache() -> None:
    load_shortcut_find_catalog.cache_clear()


__all__ = [
    "DEVICE_VERIFIED",
    "GUESSED",
    "SKIPPED",
    "clear_find_catalog_cache",
    "find_catalog_entry",
    "find_catalog_path",
    "list_find_catalog_entries",
    "load_shortcut_find_catalog",
    "never_use_find_labels",
    "quantity_find_allowed",
    "sleep_find_allowed",
]
