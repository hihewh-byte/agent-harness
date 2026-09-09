"""Stage 3C-ε — GroundedAnswerComposer SSE (meta / fact_card / follow_ups)."""

from __future__ import annotations

import os
from datetime import date
from typing import Any

from pha.health_intent_catalog import load_health_intent_catalog
from pha.numerics_manifest import NumericsManifest

_PROFILE_FOLLOWUPS: dict[str, list[tuple[str, str]]] = {
    "wearable_only": [
        ("hrv_trend", "近90天 HRV 趋势如何？"),
        ("sleep", "睡眠怎么样？"),
        ("steps", "步数呢？"),
    ],
    "lab_cross_year": [
        ("ldl_year", "每年的 LDL 对比"),
        ("ldl_latest", "最近一次血脂怎么样"),
        ("lab_trend", "历年血脂趋势"),
    ],
    "combined_review": [
        ("ldl", "血脂怎么样"),
        ("hrv", "HRV 怎么样"),
        ("sleep", "睡眠呢"),
    ],
    "lifestyle": [
        ("ldl", "血脂怎么样"),
        ("hrv", "HRV 怎么样"),
        ("steps", "最近步数"),
    ],
}


def grounded_composer_enabled() -> bool:
    return (os.environ.get("PHA_GROUNDED_COMPOSER") or "0").strip().lower() in (
        "1",
        "true",
        "yes",
    )


def build_composer_meta_event(
    *,
    session_id: str,
    profile: str,
    turn_scope: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "event": "meta",
        "session_id": session_id,
        "profile": profile,
        "turn_scope": dict(turn_scope or {}),
    }


def _metric_id_for_manifest_label(label: str) -> str | None:
    from pha.wearable_metric_registry import catalog_labels, list_metric_entries

    needle = (label or "").strip()
    if not needle:
        return None
    for entry in list_metric_entries():
        mid = str(entry.get("metric_id") or "").strip()
        labels = catalog_labels(mid) if mid else None
        if labels is None:
            continue
        if needle in (
            labels.point_zh,
            labels.span_zh,
            labels.that_day_zh,
            labels.point_en,
            labels.span_en,
            labels.that_day_en,
            labels.stem_zh,
            labels.stem_en,
        ):
            return mid
    return None


def _label_display_for_manifest_metric(metric: str, *, locale: str | None) -> str:
    from pha.response_language import default_response_locale, normalize_response_locale
    from pha.wearable_metric_registry import catalog_labels

    loc = normalize_response_locale(locale) or default_response_locale()
    mid = _metric_id_for_manifest_label(metric)
    labels = catalog_labels(mid) if mid else None
    if labels is None:
        return metric
    if loc == "en":
        if metric in (labels.span_zh, labels.span_en):
            return labels.span_en
        if metric in (labels.that_day_zh, labels.that_day_en):
            return labels.that_day_en
        return labels.point_en
    if metric in (labels.span_zh, labels.span_en):
        return labels.span_zh
    if metric in (labels.that_day_zh, labels.that_day_en):
        return labels.that_day_zh
    return labels.point_zh


def _available_not_selected_ids(
    user_id: str,
    *,
    grain_start: str,
    grain_end: str,
    metrics_in_scope: list[str],
) -> list[str]:
    from datetime import date as _date

    from pha.health_data import get_health_data
    from pha.wearable_metric_registry import list_metric_entries

    in_scope = {str(x).strip() for x in (metrics_in_scope or []) if str(x).strip()}
    remaining: list[str] = []
    for entry in list_metric_entries():
        fc = entry.get("fact_card") or {}
        if not isinstance(fc, dict) or not fc.get("eligible"):
            continue
        mid = str(entry.get("metric_id") or "").strip()
        if mid and mid not in in_scope:
            remaining.append(mid)
    if not remaining or not grain_start:
        return []
    try:
        start = _date.fromisoformat(grain_start[:10])
        end = _date.fromisoformat((grain_end or grain_start)[:10])
    except ValueError:
        return []
    hd = get_health_data(user_id, start, end, remaining)
    out: list[str] = []
    for mid in remaining:
        sm = (hd.summaries or {}).get(mid)
        if sm is not None and sm.average is not None:
            out.append(mid)
    return out


def build_fact_card_event(
    manifest: NumericsManifest | None,
    *,
    locale: str | None = None,
    user_id: str | None = None,
    user_message: str = "",
    fact_card_payload: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """T0 fact card — numbers must ⊆ numerics_manifest entries."""
    if manifest is None or not manifest.entries:
        return None
    items = []
    for entry in manifest.entries[:16]:
        items.append(
            {
                "domain": entry.domain,
                "metric": entry.metric,
                "value": entry.value,
                "unit": entry.unit,
                "anchor": entry.anchor,
                "label": f"{entry.metric} {entry.value:g}{entry.unit or ''}".strip(),
                "label_display": (
                    f"{_label_display_for_manifest_metric(entry.metric, locale=locale)} "
                    f"{entry.value:g}{entry.unit or ''}"
                ).strip(),
            },
        )
    payload = fact_card_payload if isinstance(fact_card_payload, dict) else {}
    scope = [str(x) for x in (payload.get("enabled_metric_ids") or []) if str(x).strip()]
    if not scope:
        from pha.intent_gates import infer_wearable_metric_ids

        scope = list(infer_wearable_metric_ids(user_message))
    interp = payload.get("interpretation") if isinstance(payload.get("interpretation"), dict) else {}
    notes_used = int(interp.get("background_notes_used") or payload.get("background_notes_used") or 0)
    available: list[str] = []
    if user_id:
        available = _available_not_selected_ids(
            user_id,
            grain_start=str(manifest.wearable_window_start or ""),
            grain_end=str(manifest.wearable_window_end or ""),
            metrics_in_scope=scope,
        )
    return {
        "event": "fact_card",
        "profile": manifest.profile,
        "reference_date": manifest.reference_date,
        "items": items,
        "entry_count": len(manifest.entries),
        "metrics_in_scope": scope,
        "available_not_selected": available,
        "background_notes_used": notes_used,
    }


def build_follow_ups_event(
    *,
    profile: str,
    metric_keys: list[str] | None = None,
    locale: str | None = None,
) -> dict[str, Any]:
    """L4: catalog-allowed next steps (deterministic, not LLM-generated)."""
    from pha.fact_card_copy import card_copy
    from pha.response_language import default_response_locale, normalize_response_locale
    from pha.wearable_metric_registry import cluster_members

    prof = (profile or "lifestyle").strip() or "lifestyle"
    loc = normalize_response_locale(locale) or default_response_locale()
    catalog = load_health_intent_catalog()
    markers = (catalog.get("topic_markers") or {}).get(prof) or []
    by_profile = (catalog.get("follow_ups") or {}).get("by_profile") or {}
    catalog_rows = by_profile.get(prof) or []
    choices: list[dict[str, Any]] = []
    seen: set[str] = set()
    if isinstance(catalog_rows, list) and catalog_rows:
        for row in catalog_rows:
            if not isinstance(row, dict):
                continue
            cid = str(row.get("id") or "").strip()
            label = str(row.get("label_en" if loc == "en" else "label_zh") or "").strip()
            if not cid or not label or cid in seen:
                continue
            seen.add(cid)
            choice: dict[str, Any] = {"id": cid, "label": label}
            payload = row.get("payload")
            if isinstance(payload, dict) and payload:
                expanded = dict(payload)
                cluster = str(expanded.get("cluster") or "").strip()
                if expanded.get("action") == "metric_scope" and cluster and not expanded.get("metric_ids"):
                    expanded["metric_ids"] = list(cluster_members(cluster, expand_only=False))
                choice["payload"] = expanded
            choices.append(choice)
            if len(choices) >= 3:
                break
    if len(choices) < 3:
        canned = list(_PROFILE_FOLLOWUPS.get(prof) or _PROFILE_FOLLOWUPS["lifestyle"])
        for cid, label in canned:
            if cid in seen:
                continue
            seen.add(cid)
            choices.append({"id": cid, "label": label})
            if len(choices) >= 3:
                break
    if len(choices) < 3 and markers:
        for tok in markers:
            cid = f"topic_{tok}"
            if cid in seen:
                continue
            seen.add(cid)
            choices.append(
                {
                    "id": cid,
                    "label": card_copy(loc, "followup_continue_topic", tok=tok),
                }
            )
            if len(choices) >= 3:
                break
    if metric_keys:
        for mk in metric_keys[:2]:
            cid = f"metric_{mk}"
            if cid in seen or len(choices) >= 3:
                continue
            seen.add(cid)
            choices.append(
                {
                    "id": cid,
                    "label": card_copy(loc, "followup_look_at_metric", mk=mk),
                }
            )
    return {"event": "follow_ups", "choices": choices[:3]}


def fact_card_values_subset_of_manifest(
    fact_card: dict[str, Any],
    manifest: NumericsManifest,
) -> bool:
    allowed = {(e.metric, e.anchor, float(e.value)) for e in manifest.entries}
    for item in fact_card.get("items") or []:
        key = (
            str(item.get("metric") or ""),
            str(item.get("anchor") or ""),
            float(item.get("value")),
        )
        if key not in allowed:
            return False
    return True


def _is_single_day_anchor(anchor: str) -> bool:
    raw = (anchor or "").strip()
    if not raw:
        return False
    if "~" not in raw:
        return True
    start, end = raw.split("~", 1)
    return start == end


def _focus_summary_header(entries: list, loc: str) -> str:
    if not entries:
        if loc == "en":
            return "From your ~90-day health records:"
        return "根据您近 90 天的健康记录："
    if all(_is_single_day_anchor(e.anchor) for e in entries):
        day = entries[0].anchor.split("~", 1)[0]
        if loc == "en":
            return f"From your health records for {day}:"
        return f"根据您 {day} 的健康记录："
    span = entries[0].anchor
    if _anchor_looks_like_90d(span):
        if loc == "en":
            return "From your ~90-day health records:"
        return "根据您近 90 天的健康记录："
    if loc == "en":
        return f"From your health records ({span}):"
    return f"根据您 {span} 的健康记录："


def _anchor_looks_like_90d(anchor: str) -> bool:
    raw = (anchor or "").strip()
    if "~" not in raw:
        return False
    start_s, end_s = raw.split("~", 1)
    try:
        start = date.fromisoformat(start_s)
        end = date.fromisoformat(end_s)
    except ValueError:
        return False
    return 80 <= (end - start).days <= 100


def _display_manifest_metric(metric: str, *, locale: str) -> str:
    from pha.wearable_metric_registry import catalog_labels, list_metric_entries

    if locale != "en":
        return metric
    for m in list_metric_entries():
        mid = str(m.get("metric_id") or "").strip()
        labels = catalog_labels(mid)
        if not labels:
            continue
        if metric in (
            labels.point_zh,
            labels.span_zh,
            labels.that_day_zh,
        ):
            if metric == labels.span_zh:
                return labels.span_en
            if metric == labels.that_day_zh:
                return labels.that_day_en
            return labels.point_en
    return metric


def build_manifest_metric_focus_summary(
    manifest: NumericsManifest | None,
    *,
    locale: str | None = None,
    missing_ids: list[str] | None = None,
    grain: Any = None,
) -> str:
    """Warehouse-only cluster/single-metric answer (no screenshot CompareTable)."""
    from pha.response_language import default_response_locale, normalize_response_locale

    loc = normalize_response_locale(locale) or default_response_locale()
    lines: list[str] = []
    if manifest is not None and manifest.entries:
        focus = list(manifest.entries[:8])
        lines = [_focus_summary_header(focus, loc), ""]
        for entry in focus:
            val_s = f"{entry.value:g}{entry.unit or ''}"
            metric = _display_manifest_metric(entry.metric, locale=loc)
            if loc == "en":
                lines.append(f"- **{metric}**: {val_s} ({entry.anchor})")
            else:
                lines.append(f"- **{metric}**：{val_s}（{entry.anchor}）")
    missing_text = ""
    if missing_ids:
        missing_text = _missing_grain_summary(grain, locale=loc, requested_ids=missing_ids)
    body = "\n".join(lines).strip()
    if body and missing_text:
        return f"{body}\n{missing_text}"
    return body or missing_text


def build_generic_english_locale_fallback(*, user_message: str = "") -> str:
    """Last-resort English reply when manifest-backed fallback is unavailable."""
    _ = user_message
    return (
        "From the available health records in your account, I can review verified lab and "
        "wearable values when you name a specific metric or time window.\n\n"
        "Educational context only, not a medical diagnosis. "
        "Ask a clinician for persistent symptoms or treatment decisions."
    )


def resolve_locale_fallback_manifest(
    manifest: NumericsManifest | None,
    *,
    user_id: str,
    profile: str,
    user_message: str = "",
) -> NumericsManifest | None:
    """Build or reuse a manifest suitable for English locale fallback."""
    if manifest is not None and manifest.entries:
        return manifest
    from pha.numerics_manifest import build_numerics_manifest

    uid = (user_id or "default").strip() or "default"
    prof = (profile or "").strip()
    candidates: list[str] = []
    for p in (prof, "combined_review", "lab_cross_year", "lifestyle", "wearable_only"):
        if p and p not in candidates:
            candidates.append(p)
    for cand in candidates:
        built = build_numerics_manifest(
            uid,
            profile=cand,
            user_message=user_message,
            include_lipid=True,
            include_wearable=True,
        )
        if built.entries:
            return built
    return manifest if manifest is not None and manifest.entries else None


def build_manifest_locale_fallback_summary(
    manifest: NumericsManifest | None,
    *,
    user_message: str = "",
    locale: str | None = None,
) -> str:
    """Deterministic fallback when an English LLM answer leaks substantial CJK."""
    if manifest is None or not manifest.entries:
        return ""
    from pha.response_language import default_response_locale, normalize_response_locale

    loc = normalize_response_locale(locale) or default_response_locale()
    if loc != "en":
        return ""
    lines = ["From the available health records:", ""]
    for entry in manifest.entries[:8]:
        val_s = f"{entry.value:g}{(' ' + entry.unit) if entry.unit else ''}"
        metric = _display_manifest_metric(entry.metric, locale="en")
        anchor = f" ({entry.anchor})" if entry.anchor else ""
        lines.append(f"- **{metric}**: {val_s}{anchor}")
    lines.append("")
    lines.append(
        "Educational context only, not a medical diagnosis. "
        "Ask a clinician for persistent symptoms or treatment decisions.",
    )
    return "\n".join(lines).strip()


def apply_english_locale_leak_guard(
    answer_text: str,
    *,
    locale: str | None,
    numerics_manifest: NumericsManifest | None,
    user_id: str,
    profile: str,
    user_message: str = "",
) -> tuple[str, dict[str, object]]:
    """Replace English answers that leak substantial CJK with manifest or generic fallback."""
    if not answer_has_cjk_locale_leak(answer_text, locale=locale):
        return answer_text, {}
    manifest = resolve_locale_fallback_manifest(
        numerics_manifest,
        user_id=user_id,
        profile=profile,
        user_message=user_message,
    )
    fallback = build_manifest_locale_fallback_summary(
        manifest,
        user_message=user_message,
        locale=locale,
    )
    mode = "manifest"
    if not fallback:
        fallback = build_generic_english_locale_fallback(user_message=user_message)
        mode = "generic"
    return fallback, {
        "locale_fallback_applied": True,
        "locale_fallback_reason": "english_cjk_leak",
        "locale_fallback_mode": mode,
    }


def answer_has_cjk_locale_leak(text: str, *, locale: str | None = None) -> bool:
    """Detect substantial CJK leakage in an English user-visible answer."""
    from pha.response_language import normalize_response_locale

    if normalize_response_locale(locale) != "en":
        return False
    blob = text or ""
    if len(blob) < 80:
        return False
    import re

    cjk = len(re.findall(r"[\u4e00-\u9fff]", blob))
    return (cjk / max(len(blob), 1)) > 0.12


def _label_for_metric_id(mid: str, *, locale: str, grain_point: bool, same_day_today: bool) -> str:
    from pha.wearable_metric_registry import catalog_labels

    labels = catalog_labels(mid)
    if labels is None:
        return mid
    if locale == "en":
        if grain_point:
            return labels.point_en if same_day_today else labels.that_day_en
        return labels.span_en
    if grain_point:
        return labels.point_zh if same_day_today else labels.that_day_zh
    return labels.span_zh


def _requested_focus_metric_ids(user_message: str) -> list[str]:
    from pha.intent_gates import infer_wearable_metric_ids
    from pha.wearable_metric_registry import cluster_of

    ids = infer_wearable_metric_ids(user_message)
    if not ids:
        return []
    clusters = {cluster_of(mid) or mid for mid in ids}
    if len(clusters) <= 1:
        return ids
    return ids


def is_warehouse_metric_focus_turn(user_message: str) -> bool:
    """Pure warehouse cluster/single-metric query (skip heavy 90d snapshot assembly)."""
    msg = (user_message or "").strip()
    if not msg:
        return False
    from pha.intent_gates import infer_wearable_metric_ids
    from pha.wearable_metric_registry import cluster_of

    ids = infer_wearable_metric_ids(msg)
    if not ids:
        return False
    clusters = {cluster_of(mid) or f"solo:{mid}" for mid in ids}
    return len(clusters) == 1


def _filter_manifest_to_metric_focus(
    manifest: NumericsManifest,
    requested_ids: list[str],
    *,
    user_message: str = "",
    episodic: Any = None,
) -> NumericsManifest:
    if not requested_ids:
        return manifest
    from pha.health_data import effective_query_reference_date
    from pha.wearable_time_grain import resolve_wearable_time_grain

    grain = resolve_wearable_time_grain(
        user_message,
        reference=effective_query_reference_date(),
        episodic=episodic,
    )
    same_day_today = grain.is_point_day() and grain.end == effective_query_reference_date()
    labels: list[str] = []
    for mid in requested_ids:
        labels.append(
            _label_for_metric_id(
                mid,
                locale="zh",
                grain_point=grain.is_point_day(),
                same_day_today=same_day_today,
            )
        )
    allowed = set(labels)
    filtered = [e for e in manifest.entries if e.metric in allowed]
    if not filtered:
        return NumericsManifest(
            profile=manifest.profile,
            user_id=manifest.user_id,
            entries=[],
            reference_date=manifest.reference_date,
            forbidden_dates=manifest.forbidden_dates,
            wearable_grain_source=manifest.wearable_grain_source,
            wearable_window_start=manifest.wearable_window_start,
            wearable_window_end=manifest.wearable_window_end,
        )
    return NumericsManifest(
        profile=manifest.profile,
        user_id=manifest.user_id,
        entries=filtered,
        reference_date=manifest.reference_date,
        forbidden_dates=manifest.forbidden_dates,
        wearable_grain_source=manifest.wearable_grain_source,
        wearable_window_start=manifest.wearable_window_start,
        wearable_window_end=manifest.wearable_window_end,
    )


def _missing_grain_summary(
    grain: Any,
    *,
    locale: str | None,
    requested_ids: list[str],
) -> str:
    from pha.response_language import default_response_locale, normalize_response_locale
    from pha.wearable_metric_registry import catalog_labels
    from pha.wearable_time_grain import WearableTimeGrain

    loc = normalize_response_locale(locale) or default_response_locale()
    if not isinstance(grain, WearableTimeGrain):
        return ""
    if grain.is_point_day():
        span = grain.start.isoformat()
    else:
        span = f"{grain.start.isoformat()}~{grain.end.isoformat()}"
    lines: list[str] = []
    for mid in requested_ids:
        labels = catalog_labels(mid)
        stem_zh = labels.stem_zh if labels else mid
        stem_en = labels.stem_en if labels else mid
        if loc == "en":
            lines.append(
                f"No verified {stem_en} in your records for {span}. "
                "Not filled from another date or metric."
            )
        else:
            lines.append(
                f"库内没有 {span} 的{stem_zh}记录，不会用其他日期或其他指标的数字代替。"
            )
    return "\n".join(lines).strip()


def try_warehouse_metric_focus_skip(
    *,
    user_id: str,
    profile: str,
    user_message: str,
    manifest: NumericsManifest | None,
    response_locale: str | None = None,
    episodic: Any = None,
) -> str:
    """
    Pure warehouse wearable follow-up: skip LLM when manifest focus is available.

    Builds manifest lazily when plan omitted NUMERICS_MANIFEST (legacy); wearable_only now includes the slot.
    """
    from pha.health_data import effective_query_reference_date
    from pha.numerics_manifest import build_numerics_manifest
    from pha.wearable_time_grain import resolve_wearable_time_grain

    msg = (user_message or "").strip()
    if not msg:
        return ""
    requested_ids = _requested_focus_metric_ids(msg)
    if not is_warehouse_metric_focus_turn(msg):
        return ""
    grain = resolve_wearable_time_grain(
        msg,
        reference=effective_query_reference_date(),
        episodic=episodic,
    )
    wm = manifest
    # Non-default grains must not reuse a 90-day mean already sitting in the turn manifest.
    if wm is None or not wm.entries or grain.source != "default":
        wm = build_numerics_manifest(
            user_id,
            profile=profile,
            user_message=user_message,
            include_lipid=False,
            include_wearable=True,
            episodic=episodic,
        )
    wm = _filter_manifest_to_metric_focus(
        wm,
        requested_ids,
        user_message=msg,
        episodic=episodic,
    )
    present_labels = {e.metric for e in wm.entries}
    missing_ids: list[str] = []
    same_day_today = grain.is_point_day() and grain.end == effective_query_reference_date()
    for mid in requested_ids:
        label = _label_for_metric_id(
            mid,
            locale="zh",
            grain_point=grain.is_point_day(),
            same_day_today=same_day_today,
        )
        if label not in present_labels:
            missing_ids.append(mid)
    summary = build_manifest_metric_focus_summary(
        wm,
        locale=response_locale,
        missing_ids=missing_ids,
        grain=grain,
    )
    if summary:
        return summary
    if grain.source != "default":
        return _missing_grain_summary(grain, locale=response_locale, requested_ids=requested_ids)
    return ""


__all__ = [
    "build_composer_meta_event",
    "build_fact_card_event",
    "build_follow_ups_event",
    "build_manifest_metric_focus_summary",
    "build_manifest_locale_fallback_summary",
    "build_generic_english_locale_fallback",
    "resolve_locale_fallback_manifest",
    "apply_english_locale_leak_guard",
    "answer_has_cjk_locale_leak",
    "is_warehouse_metric_focus_turn",
    "try_warehouse_metric_focus_skip",
    "fact_card_values_subset_of_manifest",
    "grounded_composer_enabled",
]
