"""User-selected fact-card metrics. Catalog is the allowlist; prefs are not code."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional, Sequence

from pha.models import WearableDailySummary
from pha.wearable_metric_registry import (
    default_fact_card_metric_ids,
    fact_card_eligible_entries,
)
from pha.fact_card_locale import DEFAULT_LOCALE, normalize_fact_card_locale

SCHEMA = "pha.fact_card_prefs/v1"
_GROUP_ORDER = ("睡眠", "心脏", "活动", "呼吸与血氧", "体能")


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
    reference_range: Optional[dict[str, Any]] = None
    temporal: dict[str, Any] = field(default_factory=dict)
    catalog_group: str = ""
    coverage_denominator: bool = True
    label_en: str = ""


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
    label_en = str((entry.get("ui") or {}).get("label_en") or "").strip()
    group = str((entry.get("ui") or {}).get("group_zh") or "").strip()
    if not mid or not field or field not in WearableDailySummary.model_fields:
        return None
    include_raw = fc.get("include_when_selected") or []
    include_when = tuple(
        str(x).strip() for x in include_raw if str(x).strip()
    ) if isinstance(include_raw, list) else ()
    raw_ref = fc.get("reference_range")
    reference_range = dict(raw_ref) if isinstance(raw_ref, dict) and raw_ref else None
    raw_temporal = fc.get("temporal")
    temporal = dict(raw_temporal) if isinstance(raw_temporal, dict) and raw_temporal else {}
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
        reference_range=reference_range,
        temporal=temporal,
        catalog_group=group,
        coverage_denominator=bool(fc.get("coverage_denominator", True)),
        label_en=label_en,
    )


def _shortcut_channel(spec: FactCardMetricSpec) -> str:
    if spec.shortcut_skip_reason == "derived_from_asleep_stages":
        return "sleep"
    if spec.shortcut_skip_reason:
        return "history"
    if spec.shortcut_sleep_value:
        return "sleep"
    if spec.shortcut_health_type and spec.ingest_key:
        from pha.shortcut_find_catalog import quantity_find_allowed

        if quantity_find_allowed(spec.metric_id, spec.shortcut_health_type):
            return "quantity"
        return "history"
    return "history"


def spec_display_label(spec: FactCardMetricSpec, locale: str) -> str:
    if normalize_fact_card_locale(locale) == "en-US":
        return (spec.label_en or spec.label).strip()
    return spec.label


def _shortcut_hint(spec: FactCardMetricSpec, locale: str = "") -> str:
    from pha.fact_card_copy import card_copy

    loc = locale or DEFAULT_LOCALE
    channel = _shortcut_channel(spec)
    if channel == "sleep":
        return card_copy(loc, "hint_sleep")
    if channel == "quantity":
        return card_copy(loc, "hint_quantity")
    return card_copy(loc, "hint_history")


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
        # M1-P8: prefs that still list the deprecated RMSSD id → SDNN.
        if mid == "hrv_rmssd_ms":
            mid = "hrv_sdnn_ms"
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
    return [known[mid] for mid in ids if mid in known]


def _write_doc(path: Path, doc: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
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


def _merge_user_prefs(user_id: str, **fields: Any) -> dict[str, Any]:
    uid = (user_id or "default").strip() or "default"
    path = prefs_path()
    doc = _load_doc(path)
    users = doc.setdefault("users", {})
    if not isinstance(users, dict):
        users = {}
        doc["users"] = users
    prev = users.get(uid) if isinstance(users.get(uid), dict) else {}
    block: dict[str, Any] = dict(prev) if isinstance(prev, dict) else {}
    block.update(fields)
    users[uid] = block
    doc["schema"] = SCHEMA
    _write_doc(path, doc)
    return block


def save_enabled_metric_ids(user_id: str, ids: Sequence[str]) -> list[str]:
    cleaned = sanitize_metric_ids(ids)
    _merge_user_prefs(user_id, enabled_metric_ids=cleaned)
    return cleaned


ASSESSMENT_PROMPT_MAX = 2000


def load_assessment_prompt(user_id: str) -> str:
    uid = (user_id or "default").strip() or "default"
    doc = _load_doc(prefs_path())
    users = doc.get("users") or {}
    block = users.get(uid) if isinstance(users, dict) else None
    if isinstance(block, dict):
        return str(block.get("assessment_prompt") or "")
    return ""


def save_assessment_prompt(user_id: str, prompt: str) -> str:
    text = str(prompt or "")
    if len(text) > ASSESSMENT_PROMPT_MAX:
        raise ValueError("assessment_prompt_too_long")
    uid = (user_id or "default").strip() or "default"
    doc = _load_doc(prefs_path())
    users = doc.get("users") or {}
    prev = users.get(uid) if isinstance(users, dict) else None
    if not (isinstance(prev, dict) and isinstance(prev.get("enabled_metric_ids"), list)):
        enabled, _ = load_enabled_metric_ids(uid)
        _merge_user_prefs(uid, enabled_metric_ids=enabled, assessment_prompt=text)
    else:
        _merge_user_prefs(uid, assessment_prompt=text)
    return text


def load_fact_card_locale(user_id: str) -> str:
    uid = (user_id or "default").strip() or "default"
    doc = _load_doc(prefs_path())
    users = doc.get("users") or {}
    block = users.get(uid) if isinstance(users, dict) else None
    if isinstance(block, dict):
        return normalize_fact_card_locale(str(block.get("locale") or ""))
    return DEFAULT_LOCALE


def save_fact_card_locale(user_id: str, locale: str) -> str:
    loc = normalize_fact_card_locale(locale)
    _merge_user_prefs(user_id, locale=loc)
    return loc


def load_fact_card_timezone(user_id: str) -> str:
    uid = (user_id or "default").strip() or "default"
    doc = _load_doc(prefs_path())
    users = doc.get("users") or {}
    block = users.get(uid) if isinstance(users, dict) else None
    if isinstance(block, dict):
        return str(block.get("timezone") or "").strip()
    return ""


def prefs_payload(user_id: str) -> dict[str, Any]:
    uid = (user_id or "default").strip() or "default"
    enabled, source = load_enabled_metric_ids(uid)

    def _rank(spec: FactCardMetricSpec) -> tuple[int, str]:
        group = spec.catalog_group or "其他"
        try:
            idx = _GROUP_ORDER.index(group)
        except ValueError:
            idx = len(_GROUP_ORDER)
        return idx, spec.metric_id

    loc = load_fact_card_locale(uid)
    from pha.fact_card_copy import group_label

    catalog_specs_sorted = sorted(catalog_specs(), key=_rank)
    return {
        "schema": SCHEMA,
        "user_id": uid,
        "enabled_metric_ids": enabled,
        "assessment_prompt": load_assessment_prompt(uid),
        "assessment_prompt_max": ASSESSMENT_PROMPT_MAX,
        "locale": loc,
        "timezone": load_fact_card_timezone(uid),
        "source": source,
        "catalog": [
            {
                "metric_id": spec.metric_id,
                "label": spec_display_label(spec, loc),
                "unit": spec.unit,
                "ingest_key": spec.ingest_key or None,
                "enabled_default": spec.enabled_default,
                "selected": spec.metric_id in enabled,
                "shortcut_sync": _shortcut_channel(spec) == "quantity",
                "shortcut_skip_reason": spec.shortcut_skip_reason or None,
                "shortcut_channel": _shortcut_channel(spec),
                "shortcut_hint": _shortcut_hint(spec, loc),
                "group": group_label(spec.catalog_group or "其他", loc),
                "coverage_denominator": spec.coverage_denominator,
            }
            for spec in catalog_specs_sorted
        ],
    }


__all__ = [
    "ASSESSMENT_PROMPT_MAX",
    "FactCardMetricSpec",
    "SCHEMA",
    "catalog_specs",
    "default_enabled_metric_ids",
    "load_assessment_prompt",
    "load_enabled_metric_ids",
    "load_fact_card_locale",
    "load_fact_card_timezone",
    "prefs_path",
    "prefs_payload",
    "resolve_metric_specs",
    "sanitize_metric_ids",
    "save_assessment_prompt",
    "save_enabled_metric_ids",
    "save_fact_card_locale",
    "spec_display_label",
]
