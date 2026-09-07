"""User-selected fact-card metrics. Catalog is the allowlist; prefs are not code."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, Sequence

from pha.models import WearableDailySummary
from pha.wearable_metric_registry import (
    default_fact_card_metric_ids,
    fact_card_eligible_entries,
)

SCHEMA = "pha.fact_card_prefs/v1"


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def prefs_path() -> Path:
    override = (os.environ.get("PHA_FACT_CARD_PREFS") or "").strip()
    if override:
        return Path(override)
    return _repo_root() / "data" / "fact_card_prefs.json"


@dataclass(frozen=True)
class FactCardMetricSpec:
    metric_id: str
    field: str
    label: str
    unit: str
    higher_is_better: bool
    ingest_key: str
    enabled_default: bool
    daily_key: bool = False
    shortcut_health_type: str = ""
    shortcut_stat: str = ""
    shortcut_unit: str = ""
    shortcut_skip_reason: str = ""
    include_when_selected: tuple[str, ...] = ()
    display_fallback_metric_id: str = ""
    shortcut_sleep_value: str = ""
    reveal_when_selected: tuple[str, ...] = ()
    reference_range: Optional[dict[str, Any]] = None


def _unit_from_entry(entry: dict[str, Any]) -> str:
    fc = entry.get("fact_card") or {}
    raw = str(fc.get("unit") or "").strip()
    if raw:
        return raw
    snap = str((entry.get("snapshot") or {}).get("unit") or "").strip()
    if snap == "hr":
        return "h"
    return snap or "count"


def _spec_from_entry(entry: dict[str, Any]) -> Optional[FactCardMetricSpec]:
    fc = entry.get("fact_card") or {}
    if not isinstance(fc, dict):
        return None
    mid = str(entry.get("metric_id") or "").strip()
    field = str((entry.get("l1") or {}).get("field") or "").strip()
    label = str((entry.get("ui") or {}).get("label_zh") or mid).strip()
    if not mid or not field or field not in WearableDailySummary.model_fields:
        return None
    include_raw = fc.get("include_when_selected") or []
    include_when = tuple(
        str(x).strip() for x in include_raw if str(x).strip()
    ) if isinstance(include_raw, list) else ()
    reveal_raw = fc.get("reveal_when_selected") or []
    reveal_when = tuple(
        str(x).strip() for x in reveal_raw if str(x).strip()
    ) if isinstance(reveal_raw, list) else ()
    raw_ref = fc.get("reference_range")
    reference_range = dict(raw_ref) if isinstance(raw_ref, dict) and raw_ref else None
    return FactCardMetricSpec(
        metric_id=mid,
        field=field,
        label=label,
        unit=_unit_from_entry(entry),
        higher_is_better=bool(fc.get("higher_is_better", True)),
        ingest_key=str(fc.get("ingest_key") or "").strip(),
        enabled_default=bool(fc.get("enabled_default")),
        daily_key=bool(fc.get("daily_key")),
        shortcut_health_type=str(fc.get("shortcut_health_type") or "").strip(),
        shortcut_stat=str(fc.get("shortcut_stat") or "").strip(),
        shortcut_unit=str(fc.get("shortcut_unit") or "").strip(),
        shortcut_skip_reason=str(fc.get("shortcut_skip_reason") or "").strip(),
        include_when_selected=include_when,
        display_fallback_metric_id=str(fc.get("display_fallback_metric_id") or "").strip(),
        shortcut_sleep_value=str(fc.get("shortcut_sleep_value") or "").strip(),
        reveal_when_selected=reveal_when,
        reference_range=reference_range,
    )


def catalog_specs() -> tuple[FactCardMetricSpec, ...]:
    out: list[FactCardMetricSpec] = []
    for entry in fact_card_eligible_entries():
        spec = _spec_from_entry(entry)
        if spec is not None:
            out.append(spec)
    return tuple(out)


def catalog_by_id() -> dict[str, FactCardMetricSpec]:
    return {spec.metric_id: spec for spec in catalog_specs()}


def _load_doc(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"schema": SCHEMA, "users": {}}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"schema": SCHEMA, "users": {}}
    if not isinstance(raw, dict):
        return {"schema": SCHEMA, "users": {}}
    users = raw.get("users")
    if not isinstance(users, dict):
        raw["users"] = {}
    return raw


def sanitize_metric_ids(ids: Sequence[str]) -> list[str]:
    known = catalog_by_id()
    seen: set[str] = set()
    out: list[str] = []
    for raw in ids:
        mid = str(raw or "").strip()
        if not mid or mid in seen or mid not in known:
            continue
        seen.add(mid)
        out.append(mid)
    return out


def default_enabled_metric_ids() -> list[str]:
    defaults = sanitize_metric_ids(default_fact_card_metric_ids())
    if defaults:
        return defaults
    return [spec.metric_id for spec in catalog_specs()]


def load_enabled_metric_ids(user_id: str) -> tuple[list[str], str]:
    """Return (ids, source) where source is user|catalog_default."""
    uid = (user_id or "default").strip() or "default"
    doc = _load_doc(prefs_path())
    users = doc.get("users") or {}
    block = users.get(uid) if isinstance(users, dict) else None
    if isinstance(block, dict) and "enabled_metric_ids" in block:
        raw = block.get("enabled_metric_ids")
        if isinstance(raw, list):
            return sanitize_metric_ids([str(x) for x in raw]), "user"
    return default_enabled_metric_ids(), "catalog_default"


def resolve_metric_specs(
    user_id: str,
    enabled_metric_ids: Optional[Sequence[str]] = None,
) -> list[FactCardMetricSpec]:
    known = catalog_by_id()
    if enabled_metric_ids is None:
        ids, _source = load_enabled_metric_ids(user_id)
    else:
        ids = sanitize_metric_ids(enabled_metric_ids)
    out = [known[mid] for mid in ids if mid in known]
    if enabled_metric_ids is not None:
        return out
    wanted = set(ids)
    for spec in catalog_specs():
        if spec.metric_id in wanted or not spec.reveal_when_selected:
            continue
        if wanted.intersection(spec.reveal_when_selected):
            out.append(spec)
            wanted.add(spec.metric_id)
    return out


def save_enabled_metric_ids(user_id: str, ids: Sequence[str]) -> list[str]:
    uid = (user_id or "default").strip() or "default"
    cleaned = sanitize_metric_ids(ids)
    path = prefs_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = _load_doc(path)
    users = doc.setdefault("users", {})
    if not isinstance(users, dict):
        users = {}
        doc["users"] = users
    users[uid] = {"enabled_metric_ids": cleaned}
    doc["schema"] = SCHEMA
    payload = json.dumps(doc, ensure_ascii=False, indent=2) + "\n"
    fd, tmp = tempfile.mkstemp(prefix="fact_card_prefs.", suffix=".json", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(payload)
        os.replace(tmp, path)
    except Exception:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise
    return cleaned


def prefs_payload(user_id: str) -> dict[str, Any]:
    uid = (user_id or "default").strip() or "default"
    enabled, source = load_enabled_metric_ids(uid)
    return {
        "schema": SCHEMA,
        "user_id": uid,
        "enabled_metric_ids": enabled,
        "source": source,
        "catalog": [
            {
                "metric_id": spec.metric_id,
                "label": spec.label,
                "unit": spec.unit,
                "ingest_key": spec.ingest_key or None,
                "enabled_default": spec.enabled_default,
                "selected": spec.metric_id in enabled,
                "shortcut_sync": bool(spec.shortcut_health_type and spec.ingest_key),
                "shortcut_skip_reason": spec.shortcut_skip_reason or None,
            }
            for spec in catalog_specs()
        ],
    }


__all__ = [
    "FactCardMetricSpec",
    "SCHEMA",
    "catalog_specs",
    "default_enabled_metric_ids",
    "load_enabled_metric_ids",
    "prefs_path",
    "prefs_payload",
    "resolve_metric_specs",
    "sanitize_metric_ids",
    "save_enabled_metric_ids",
]
